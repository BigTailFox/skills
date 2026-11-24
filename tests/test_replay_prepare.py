"""Prepare historical inputs through the public replay command with real Git and trace stores."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import test_trace_analysis
from test_trace_report import CONV, GATE, PRIOR, SECOND, TRACE, UNIT, ReportFixture, end, start, write_lines
from test_trace_reviews import review_end, reviewer


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/replay_workflows.py"
DESIGN = "docs/designs/D001-example.md"
PLAN = "docs/plans/P001-example.md"
PLAN_BODY = ("---\nrevision: 2\n---\n# P001: Example\n\n## Slices\n\n### S1: First\n\n"
             "Status: in-progress\n\nRisk: Files may move.\n\nPreserve the ABI.\n\nTest the executable.\n\n"
             "### S2: Second\n\nStatus: todo\n\nAdd a renderer.\n\n## Log\n\nPRIVATE history.\n")


def digest(data):
    return hashlib.sha256(data).hexdigest()


class ReplayFixture(ReportFixture):
    object_format = "sha1"
    git = test_trace_analysis.OfflineAnalysis.git
    repo = test_trace_analysis.OfflineAnalysis.repo
    commit = test_trace_analysis.OfflineAnalysis.commit
    archived_review = test_trace_analysis.OfflineAnalysis.archived_review

    def setUp(self):
        super().setUp()
        self.store = self.log.parent
        self.skills = self.root / "skills-repo"
        self.out = self.root / "case"
        self.store.mkdir(parents=True)
        supported = subprocess.run(["git", "-C", self.store, "init", "-q", "--object-format=" + self.object_format],
                                   capture_output=True)
        if supported.returncode and self.object_format == "sha256":
            self.skipTest("Git does not support SHA-256 repositories")
        self.assertEqual(supported.returncode, 0, supported.stderr)
        self.assertEqual(self.git(self.store, "rev-parse", "--show-toplevel"), str(self.store))
        self.repo(self.skills)
        self.files = {"canon/SKILL.md": "Old suite.\n", "canon/scripts/canon.py": ("100755", "# tool\n")}
        self.suite = self.tree(self.store, self.files)
        self.candidate = self.pin(self.skills, self.tree(self.skills, {
            "skills/governance/" + k: v for k, v in self.files.items()
        } | {"skills/governance/canon/NOTICE": "not installed"}))
        self.git(self.skills, "update-ref", "HEAD", self.candidate)
        entries = [["SKILL.md", self.git(self.skills, "hash-object", "--stdin", data="Old suite.\n")],
                   ["scripts/canon.py", self.git(self.skills, "hash-object", "--stdin", data="# tool\n")]]
        skill = digest(json.dumps(entries, separators=(",", ":")).encode())
        manifest = {"canon": skill}
        self.manifest = digest(json.dumps(manifest, separators=(",", ":")).encode())
        self.events = [dict(v=1, type="manifest", skills=manifest, digest=self.manifest)]
        self.git(self.store, "update-ref", "refs/skills/" + self.manifest, self.pin(self.store, self.suite))

    def tree(self, root, entries):
        self.git(root, "read-tree", "--empty")
        for name, value in entries.items():
            mode, data = value if isinstance(value, tuple) else ("100644", value)
            blob = self.git(root, "hash-object", "-w", "--stdin", data=data)
            self.git(root, "update-index", "--add", "--cacheinfo", mode + "," + blob + "," + name)
        return self.git(root, "write-tree")

    def pin(self, root, tree, *parents, message="historical commit"):
        args = [arg for parent in parents for arg in ("-p", parent)]
        return self.git(root, "commit-tree", tree, *args, "-m", message)

    def review(self, kind, entries, *, baseline=None, opening=None, docs=None, prompts=None, people=None, findings=()):
        tree = self.tree(self.store, entries)
        target = self.pin(self.store, tree, *([baseline] if baseline else []))
        opening = opening or target
        people = people or [reviewer("same-model" if kind == "gate" else "spec", "historical-reviewer")]
        roles = [p.get("key", p["role"]) for p in people]
        prompts = prompts or {key: "Target: " + DESIGN for key in roles}
        self.archived_review(UNIT, target, baseline or "none", people, dict.fromkeys(roles, target), prompts)
        self.git(self.store, "update-ref", "refs/trace/" + UNIT, opening)
        self.git(self.store, "update-ref", "refs/review-input/" + UNIT, target)
        self.events.extend([start(UNIT, kind, host="codex", conversation=CONV, model="model-a",
                                  snapshot=opening, manifest=self.manifest, docs=docs or []),
                            review_end(UNIT, kind, people, list(findings), review_input=target, manifest=self.manifest)])
        write_lines(self.log, self.events)
        return target

    def prepare(self, *args, out=None, error=None):
        dest = out or self.out
        result = subprocess.run([sys.executable, SCRIPT, "prepare", "--project", self.project, "--unit", UNIT,
                                 "--candidate", "HEAD", "--out", dest, "--skills-repo", self.skills,
                                 "--cursor-home", self.cursor, "--codex-home", self.codex, *map(str, args)],
                                capture_output=True, text=True)
        if error is not None:
            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertIn(error, result.stderr)
            self.assertNotIn("Traceback", result.stderr)
            return
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads((dest / "private/receipt.json").read_bytes())

    def slice(self):
        target = self.pin(self.store, self.tree(self.store, {PLAN: PLAN_BODY}))
        self.git(self.store, "update-ref", "refs/trace/" + UNIT, target)
        self.events.extend([start(PRIOR), start(UNIT, "slice", parent=PRIOR, docs=["P001@r2"], slice="S1",
                                                host="codex", conversation=CONV, model="model-a",
                                                manifest=self.manifest, snapshot=target), end(PRIOR)])
        write_lines(self.log, self.events)
        return target


class Prepare(ReplayFixture):
    def test_document_diff_restores_separate_parentless_as_built_code(self):
        self.repo(self.project)
        code = self.commit(self.project, "approved")
        tree = self.tree(self.store, {"rule": "approved\n"})
        saved_code = self.pin(self.store, tree)
        entries = {DESIGN: f"---\nrevision: 3\nas_built: {code}\n---\nNew design.\n"}
        base = self.pin(self.store, self.tree(self.store, {DESIGN: "Old design.\n"}))
        opening = self.pin(self.store, self.tree(self.store, entries), base, saved_code)
        prompts = {"same-model": f"Target: {DESIGN}\nChanges since: {base}\nAs-built: approved {code}\n"}
        self.review("gate", entries, opening=opening, baseline=base, docs=["D001@r3"], prompts=prompts)
        receipt = self.prepare()
        task = receipt["task"]["input"]
        self.assertEqual((task["form"], task["paths"]), ("document diff", [DESIGN]))
        repo = self.out / "private/input"
        self.assertEqual(self.git(repo, "rev-parse", "refs/replay/as-built"), task["as_built"])
        self.assertEqual(self.git(repo, "rev-list", "--parents", "refs/replay/as-built"), task["as_built"])
        self.assertEqual(self.git(repo, "show", task["as_built"] + ":rule"), "approved")
        self.assertEqual(self.git(repo, "rev-list", "--parents", "HEAD").splitlines(),
                         [task["target"] + " " + task["baseline"], task["baseline"]])
        self.assertEqual(receipt["source"]["original"]["as_built"], code)
        self.assertIsNone(receipt["task"]["delivery"])

    def test_exclusions_unknown_and_mixed_manifests_and_missing_baseline_stop_preparation(self):
        base = self.pin(self.store, self.tree(self.store, {"rule": "old"}))
        opening = self.pin(self.store, self.tree(self.store, {"rule": "opening"}))
        self.review("code-review", {"rule": "new"}, baseline=base, opening=opening,
                    prompts={"spec": f"Target: `git diff {base}`\nUntracked files: none"})
        first, last = self.events[-2:]
        for patch, reason in ((dict(outcome="handoff"), "handoff"), (dict(manifest="f"*64), "mixed"),
                              (dict(manifest=None), "unknown")):
            write_lines(self.log, [self.events[0], first, dict(last, **patch)])
            self.prepare(error=reason)
            self.assertFalse((self.out / "private/receipt.json").exists())
        write_lines(self.log, self.events)
        obj = self.store / ".git/objects" / base[:2] / base[2:]
        obj.rename(self.root / "lost-object")
        self.prepare(error="unverified")
        self.assertFalse((self.out / "private/receipt.json").exists())

    def test_unit_selector_rejects_ambiguity_and_pins_exact_store(self):
        self.review("gate", {DESIGN: "---\nrevision: 3\n---\n"}, docs=["D001@r3"])
        self.repo(self.project)
        self.commit(self.project, "one")
        linked = self.project / ".worktrees/linked"
        self.git(self.project, "worktree", "add", "-q", "--detach", str(linked))
        write_lines(linked / TRACE / "events.jsonl", [start(UNIT), end(UNIT)])
        self.prepare("--project", linked, error="ambiguous")
        selected = self.prepare("--project", linked, "--store", self.store)
        self.assertEqual(selected["store"], str(self.store))
        self.prepare("--project", linked, "--store", linked / TRACE, error="ineligible")

    def test_historical_inventory_joins_sources_or_preserves_raw_groups_as_unknown(self):
        from test_trace_reviews import ReviewReport, sha, table
        helper = ReviewReport()
        helper.root, helper.project, helper.log = self.root, self.project, self.log
        rows, catalog, event = helper.paired_review()
        people = event["dispositions"]["reviewers"]
        reports = {p["role"]: (self.store / UNIT / (p["role"] + ".md")).read_bytes() for p in people}
        entries = {"abi.h": "changed"}
        base = self.pin(self.store, self.tree(self.store, {"abi.h": "old"}))
        target = self.pin(self.store, self.tree(self.store, entries), base)
        prompt = f"Target: `git diff {base} {target} -- abi.h`"
        self.review("code-review", entries, baseline=base, people=people, prompts={p["role"]: prompt for p in people},
                    findings=event["dispositions"]["findings"])
        for stem, data in reports.items():
            (self.store / UNIT / (stem + ".md")).write_bytes(data)
        for r in rows + catalog:
            r["prompt_sha256"] = sha(prompt)
        for r in rows:
            r["end_sha256"] = sha(json.dumps(self.events[-1]))
        table(helper.evidence, rows)
        table(helper.catalog, catalog)
        verified = self.prepare("--review-evidence", helper.evidence)["history"]
        known = {g["id"]: g for g in verified["groups"]}
        self.assertEqual(set(known), {"merge-amendment", "template-comment"})
        self.assertEqual(known["merge-amendment"]["sources"], ["spec:F1", "standards:F1"])
        self.assertTrue(all(g["disposition"] == "accepted" for g in known.values()))
        self.assertIn("PRIVATE spec", str(known["merge-amendment"]["evidence"]))
        self.assertEqual(verified["unknown"], [])
        self.assertEqual(verified["raw_count"], 4)
        helper.catalog.rename(self.root / "no-adjudications")
        provisional = self.prepare("--review-evidence", helper.evidence, out=self.root / "unverified")["history"]
        self.assertEqual(provisional["groups"], [])
        self.assertEqual(provisional["raw_count"], 4)
        self.assertEqual({s for row in provisional["unknown"] for s in row["sources"]},
                         {"spec:F1", "spec:F2", "standards:F1", "standards:F2"})
        without = self.prepare(out=self.root / "no-table")["history"]
        self.assertEqual(without["groups"], [])
        self.assertEqual([row["sources"] for row in without["unknown"]],
                         [[f"{stem}:F{i}"] for stem in ("spec", "standards") for i in (1, 2)])

    def test_slice_distinguishes_no_attributed_review_from_one_with_unknown_findings(self):
        from test_trace_reviews import sha, table
        self.slice()
        absent = self.prepare()["history"]
        self.assertIsNone(absent["review"])
        people = [reviewer("spec", "one")]
        self.archived_review(GATE, None, None, people, {}, {"spec": "Target: archived code"})
        (self.store / GATE / "spec.md").write_text("### F1 [major] ABI mismatch\n")
        later = [start(GATE, "code-review", "2026-01-01T00:01:00Z", parent=PRIOR, docs=["P001@r2"]),
                 review_end(GATE, "code-review", people, [dict(by=["spec:F1"], severity="major",
                                                               axis="spec", disposition="accepted")])]
        write_lines(self.log, self.events[:-1] + later + self.events[-1:])
        unknown = self.prepare(out=self.root / "unknown")["history"]
        self.assertEqual(unknown["review"], GATE)
        self.assertEqual(unknown["groups"], [])
        self.assertEqual(unknown["unknown"][0]["sources"], ["spec:F1"])
        evidence = self.root / "later.tsv"
        table(evidence, [dict(project=str(self.project), unit=GATE, raw_row="1", report_stem="spec",
                              finding_id="F1", defect_group="later-abi", disposition="accepted",
                              end_sha256=sha(json.dumps(later[-1])), report_sha256=sha("### F1 [major] ABI mismatch\n"),
                              source_locator="spec.md:L1")])
        joined = self.prepare("--review-evidence", evidence, out=self.root / "joined")["history"]
        self.assertEqual([(g["id"], g["sources"]) for g in joined["groups"]], [("later-abi", ["spec:F1"])])
        self.assertEqual(joined["unknown"], [])
        # One candidate review with prior work by two slices cannot be assigned to either one.
        sibling = dict(self.events[2], id="20260101T000019Z-555555", at="2026-01-01T00:00:19Z", slice="S2")
        write_lines(self.log, self.events[:-1] + [sibling] + later + self.events[-1:])
        self.assertIsNone(self.prepare(out=self.root / "ambiguous-review")["history"]["review"])

    def test_identical_prepare_rechecks_the_seal_and_does_not_overwrite_damaged_content(self):
        self.review("gate", {DESIGN: "---\nrevision: 3\n---\n"}, docs=["D001@r3"])
        self.prepare()
        private = self.out / "private"
        suite = private / "suites/candidate/canon/SKILL.md"
        suite.write_bytes(b"changed")
        self.prepare(error="suite")
        self.assertEqual(suite.read_bytes(), b"changed")
        suite.write_bytes(b"Old suite.\n")
        (private / "input" / DESIGN).write_bytes(b"tampered target")
        self.prepare(error="input")
        (private / "input" / DESIGN).write_bytes(b"---\nrevision: 3\n---\n")
        (private / "receipt.sha256").write_text("0"*64)
        self.prepare(error="receipt digest")

    def test_registered_reviewer_uses_the_matching_rollout_turn_and_unknown_effort_stays_null(self):
        from test_trace_report import TraceReport
        people = [reviewer("same-model", "/root/review")]
        self.review("gate", {DESIGN: "---\nrevision: 3\n---\n"}, docs=["D001@r3"], people=people)
        initial = self.prepare()
        self.assertEqual(initial["roles"], {"parent": {"model": "model-a", "effort": None},
                                            "same-model": {"model": "model-a", "effort": None}})
        host = TraceReport()
        host.project, host.codex = self.project, self.codex
        seq = [host.native(1, "turn_context", model="model-a", effort="high"),
               *host.boundary(4, "start gate D001 --tier L1 --model model-a", "trace " + UNIT),
               *host.dispatch(9, "spawn_agent", "review", "first-review", json.dumps({"agent_id": SECOND})),
               *host.boundary(64, "end " + UNIT + " delivered", "trace " + UNIT + " ended", "end")]
        host.rollout(CONV, seq)
        def turn(t, model, effort, body):
            return [host.native(t, "turn_context", model=model, effort=effort),
                    host.native(t + 1, "event_msg", type="task_started"),
                    host.native(t + 2, "response_item", type="message", role="assistant", phase="final_answer",
                                content=[dict(type="output_text", text=body)]),
                    host.native(t + 3, "event_msg", type="task_complete", last_agent_message=body)]
        profile = self.root / "second-profile"
        host.rollout(SECOND, turn(12, "model-a", "medium", "No findings.") +
                     turn(30, "other-model", "low", "A later confirmation."), home=profile, parent=CONV, key="review")
        observed = self.prepare("--codex-home", profile, out=self.root / "bound")
        self.assertEqual(observed["roles"]["same-model"], {"model": "model-a", "effort": "medium"})
        self.assertEqual(observed["roles"]["parent"], {"model": "model-a", "effort": "high"})
        self.assertEqual(observed["incompatibilities"], [])
        host.rollout(SECOND, turn(12, "other-model", "low", "No findings."), home=profile, parent=CONV, key="review")
        conflict = self.prepare("--codex-home", profile, out=self.root / "different-model")
        self.assertTrue(any("model" in reason for reason in conflict["incompatibilities"]))

    def test_initial_contained_slice_brief_survives_removal_of_the_host_profile(self):
        from test_trace_report import TraceReport
        self.slice()
        host = TraceReport()
        host.project, host.codex = self.project, self.codex
        self.repo(self.project)
        opening = self.commit(self.project, PLAN_BODY.rstrip(), path=PLAN)
        done = self.commit(self.project, PLAN_BODY.replace("Status: in-progress", "Status: done").rstrip(),
                           at="2026-01-01T00:00:50Z", path=PLAN)
        self.events[1].update(at="2025-12-31T23:59:59Z", head=opening)
        self.events[2]["head"] = opening
        self.events[3]["head"] = done
        write_lines(self.log, self.events)
        boundary = host.boundary(4, "start slice P001 --slice S1 --parent " + PRIOR, "trace " + UNIT)
        prefix = [host.native(1, "turn_context", model="model-a", effort="medium"), *boundary]
        suffix = [host.native(55, "turn_context", model="later-parent", effort="high")]
        before = self.prepare()
        self.assertEqual(before["historical_brief"]["status"], "unavailable")
        replacement = "00000000-0000-4000-8000-000000000009"
        def launch(t, name, child, message):
            seq = host.dispatch(t, "spawn_agent", name, name, json.dumps({"agent_id": child}))
            seq[0]["payload"]["arguments"] = json.dumps({"task_name": name, "message": message})
            return seq
        first = launch(8, "p001_s1", SECOND, "PRIVATE initial brief")
        later = [*host.dispatch(21, "followup_task", "/root/p001_s1", "resume", json.dumps({"agent_id": SECOND})),
                 *launch(31, "p001_s1_replacement", replacement, "PRIVATE replacement")]
        host.rollout(CONV, prefix + first + later + suffix)
        host.rollout(SECOND, [host.native(9, "turn_context", model="worker", effort="low"),
                              *host.worker_turn(10, 17, 1, 2),
                              host.native(21, "turn_context", model="later-worker", effort="high"),
                              *host.worker_turn(23, 29, 2, 3)], parent=CONV, key="p001_s1")
        host.rollout(replacement, host.worker_turn(33, 40, 3, 4), parent=CONV, key="p001_s1_replacement")
        saved = self.prepare(out=self.root / "contained")
        brief = saved["historical_brief"]
        self.assertEqual((brief["status"], brief["text"], brief["sha256"]),
                         ("available", "PRIVATE initial brief", digest(b"PRIVATE initial brief")))
        self.assertEqual((brief["source"]["session"], brief["source"]["call_id"]), (SECOND, "p001_s1"))
        self.assertEqual(saved["roles"]["worker"], {"model": "worker", "effort": "low"})
        self.assertNotIn("PRIVATE", str(saved["task"]))
        no_brief = host.dispatch(8, "spawn_agent", "p001_s1", "first-empty", json.dumps({"agent_id": SECOND}))
        no_brief[0]["payload"]["arguments"] = json.dumps({"task_name": "p001_s1"})
        host.rollout(CONV, prefix + no_brief + later + suffix)
        self.assertEqual(self.prepare(out=self.root / "no-brief")["historical_brief"]["status"], "unavailable")
        outside = launch(1, "p001_s1", SECOND, "PRIVATE outside")
        host.rollout(CONV, outside + prefix + later + suffix)
        self.assertEqual(self.prepare(out=self.root / "outside")["historical_brief"]["status"], "unavailable")
        first[1]["payload"]["output"] = json.dumps([SECOND, replacement])
        host.rollout(CONV, prefix + first + later + suffix)
        self.assertEqual(self.prepare(out=self.root / "ambiguous")["historical_brief"]["status"], "unavailable")
        self.codex.rename(self.root / "removed-host")
        self.assertEqual(json.loads((self.root / "contained/private/receipt.json").read_bytes())["historical_brief"], brief)

    def test_prepared_diff_pins_archived_delivery_and_keeps_conflicts_unknown(self):
        base = self.pin(self.store, self.tree(self.store, {"abi.h": "old"}))
        entries = {"abi.h": "new"}
        target = self.pin(self.store, self.tree(self.store, entries), base)
        line = f"Target: `git diff -U8 {base} {target} -- abi.h`\n"
        requirement = "Implement the existing C ABI."
        roles = ("spec", "standards")
        self.review("code-review", entries, baseline=base, people=[reviewer(r, r) for r in roles],
                    prompts={r: line + "Requested delivery: " + requirement for r in roles})
        known = self.prepare()
        self.assertEqual(known["task"]["delivery"], requirement)
        self.assertEqual(known["delivery"]["sha256"], digest(requirement.encode()))
        self.assertIn("spec-prompt.md", str(known["delivery"]["source"]))
        self.assertEqual(known["task"]["input"]["form"], "prepared diff")
        self.assertEqual(known["task"]["input"]["paths"], ["abi.h"])
        old = (self.out / "private/receipt.json").read_bytes()
        (self.store / UNIT / "standards-prompt.md").write_text(line + "Requested delivery: Add a new ABI.")
        unknown = self.prepare(out=self.root / "conflict")
        self.assertIsNone(unknown["task"]["delivery"])
        self.assertIsNone(unknown["delivery"])
        self.prepare(error="fresh case directory")
        self.assertEqual((self.out / "private/receipt.json").read_bytes(), old)
        for role in roles:
            (self.store / UNIT / (role + "-prompt.md")).write_text(line)
        self.assertIsNone(self.prepare(out=self.root / "missing")["delivery"])

    def test_plan_delivery_selects_named_or_all_slices_at_the_frozen_revision(self):
        base = self.pin(self.store, self.tree(self.store, {PLAN: PLAN_BODY, "rule": "old"}))
        entries = {PLAN: PLAN_BODY, "rule": "new"}
        target = self.pin(self.store, self.tree(self.store, entries), base)
        prompt = f"Target: `git diff {base} {target} -- rule`\n"
        self.review("code-review", entries, baseline=base, docs=["P001@r2"],
                    prompts={"spec": prompt + "Requested delivery: P001@r2, S1."})
        single = self.prepare()
        self.assertIn("Preserve the ABI.", single["task"]["delivery"])
        self.assertIn("Test the executable.", single["task"]["delivery"])
        self.assertNotIn("Add a renderer.", single["task"]["delivery"])
        self.assertIn(PLAN, str(single["delivery"]["source"]))
        (self.store / UNIT / "spec-prompt.md").write_text(prompt + "Requested delivery: P001@r2, whole plan.")
        whole = self.prepare(out=self.root / "whole")
        self.assertIn("Add a renderer.", whole["task"]["delivery"])
        self.assertNotIn("PRIVATE history", whole["task"]["delivery"])

    def test_slice_freezes_the_actual_span_and_only_explicit_criterion_commands(self):
        opened = self.slice()
        blob = self.git(self.store, "rev-parse", opened + ":" + PLAN)
        receipt = self.prepare()
        self.assertIsNone(receipt["task"]["delivery"])
        frozen = receipt["slice_plan"]
        self.assertEqual((frozen["path"], frozen["blob"], frozen["first_line"], frozen["last_line"]),
                         (PLAN, blob, 8, 17))
        self.assertEqual(frozen["text"], "".join(PLAN_BODY.splitlines(keepends=True)[7:17]))
        sole, = receipt["criteria"]
        self.assertEqual((sole["text"], sole["argv"]), (frozen["text"], None))
        self.assertEqual(receipt["task"]["criteria"], [dict(id=sole["id"], text=sole["text"])])
        mapping = self.root / "criteria.json"
        criterion = dict(id="execute", first_line=16, last_line=16, argv=["./test", "--quiet"])
        spec = dict(schema=1, plan_blob=blob, slice="S1", criteria=[criterion])
        mapping.write_text(json.dumps(spec))
        mapped = self.prepare("--criteria", mapping, out=self.root / "mapped")
        by_text = {item["text"].strip(): item for item in mapped["criteria"]}
        self.assertEqual(set(by_text), {"Preserve the ABI.", "Test the executable."})
        self.assertIsNone(by_text["Preserve the ABI."]["argv"])
        self.assertEqual(by_text["Test the executable."]["argv"], ["./test", "--quiet"])
        for change in (dict(plan_blob="f" * 40), dict(slice="S2"), dict(criteria=[criterion, criterion]),
                       dict(criteria=[dict(criterion, argv=[])]), dict(criteria=[dict(criterion, last_line=18)])):
            with self.subTest(change=change):
                mapping.write_text(json.dumps(spec | change))
                self.prepare("--criteria", mapping, out=self.root / "invalid", error="criteria")
                self.assertFalse((self.root / "invalid/private/receipt.json").exists())

    def test_live_patch_keeps_staged_addition_deletion_and_executable_untracked(self):
        base = self.pin(self.store, self.tree(self.store, {"src/deleted": "old\n", "outside": "old\n"}))
        tracked = {"src/added": "staged\n", "outside": "changed\n"}
        expected_tree = self.tree(self.store, tracked)
        prompt = f"Target: `git diff --binary --full-index {base} -- src`\nUntracked files: src/deleted, src/run"
        self.review("code-review", tracked | {"src/deleted": "replacement\n", "src/run": ("100755", "run\n")},
                    baseline=base, prompts={"spec": prompt})
        expected = subprocess.check_output(["git", "-C", self.store, "diff", "--binary", "--full-index",
                                            base, expected_tree, "--", "src"])
        fixtures = self.root / "fixtures"
        (fixtures / "local").mkdir(parents=True)
        tool = fixtures / "local/helper"
        tool.write_bytes(b"fixture\n")
        tool.chmod(0o755)
        receipt = self.prepare("--fixtures", fixtures)
        task = receipt["task"]["input"]
        self.assertEqual((task["form"], task["paths"], task["diff_args"]),
                         ("live diff", ["src"], ["--binary", "--full-index"]))
        repo = self.out / "private/input"
        actual = subprocess.check_output(["git", "-C", repo, "diff", "--binary", "--full-index", task["baseline"], "--", "src"])
        self.assertEqual(actual, expected)
        self.assertEqual(receipt["source"]["patch_sha256"], digest(expected))
        self.assertEqual(self.git(repo, "ls-files", "--others"), "src/deleted\nsrc/run")
        self.assertEqual((repo / "src/deleted").read_text(), "replacement\n")
        self.assertEqual((repo / "src/run").stat().st_mode & 0o777, 0o755)
        self.assertEqual((self.out / "private/fixtures/local/helper").stat().st_mode & 0o777, 0o755)
        self.assertEqual(receipt["fixtures"]["local/helper"], dict(mode="100755", sha256=digest(b"fixture\n")))
        for path in ("src/added", "src/deleted", ".git/config", ".agents/skills/canon/new", ".claude/skills"):
            with self.subTest(path=path):
                bad = self.root / "bad" / path.replace("/", "-")
                file = bad / path
                file.parent.mkdir(parents=True)
                file.write_text("overlaps")
                self.prepare("--fixtures", bad, out=self.root / "invalid", error="overlap")
        (fixtures / "escape").symlink_to(self.log)
        self.prepare("--fixtures", fixtures, out=self.root / "invalid", error="fixture")
        self.assertFalse((self.root / "invalid/private/receipt.json").exists())

    def test_full_document_and_identical_suite_survive_the_original_checkout(self):
        body = "---\nrevision: 3\n---\n# D001: Design\n"
        opening = self.pin(self.store, self.tree(self.store, {"private-later-file": "unrelated"}))
        original = self.review("gate", {DESIGN: body}, opening=opening, docs=["D001@r3"])
        receipt = self.prepare("--store", self.store)
        self.assertEqual(receipt["schema"], 1)
        task = receipt["task"]
        self.assertIsNone(task["delivery"])
        restored = task["input"]
        self.assertEqual((restored["form"], restored["paths"], restored["baseline"]), ("full document", [DESIGN], None))
        self.assertNotEqual(restored["target"], original)
        for arm in ("recorded", "candidate"):
            self.assertEqual(receipt["suites"][arm]["manifest"], self.manifest)
            self.assertEqual(receipt["suites"][arm]["tree"], self.suite)
            folder = self.out / "private/suites" / arm / "canon"
            self.assertEqual((folder / "scripts/canon.py").stat().st_mode & 0o777, 0o755)
            self.assertFalse((folder / "NOTICE").exists())
        path = self.out / "private/receipt.json"
        before = path.stat().st_mtime_ns, path.read_bytes()
        self.prepare("--store", self.store)
        self.assertEqual((path.stat().st_mtime_ns, path.read_bytes()), before)
        self.project.rename(self.root / "retired")
        repo = self.out / "private/input"
        self.assertEqual(self.git(repo, "rev-list", "--all"), restored["target"])
        self.assertEqual((repo / DESIGN).read_text(), body)
        self.assertFalse((repo / "private-later-file").exists())
        self.assertEqual(self.git(repo, "cat-file", "--batch-check", data=opening + "\n"), opening + " missing")
        self.assertFalse((repo / ".git/objects/info/alternates").exists())


class PrepareSHA256(ReplayFixture):
    object_format = "sha256"

    def test_sha256_source_and_shallow_flat_candidate_restore_canonical_sha1_suites(self):
        self.review("gate", {DESIGN: "---\nrevision: 3\n---\n"}, docs=["D001@r3"])
        flat = self.tree(self.skills, {"skills/canon/SKILL.md": "New flat suite.\n",
                                      "skills/canon/scripts/canon.py": ("100755", "new tool\n"),
                                      "skills/canon/.hidden": "must stay excluded"})
        new = self.pin(self.skills, flat, self.candidate)
        self.git(self.skills, "update-ref", "HEAD", new)
        shallow = self.root / "shallow"
        self.git(self.root, "clone", "--quiet", "--depth=1", self.skills.as_uri(), str(shallow))
        receipt = self.prepare("--skills-repo", shallow)
        self.assertEqual(receipt["source"]["object_format"], "sha256")
        self.assertEqual(len(receipt["task"]["input"]["target"]), 64)
        expected = self.tree(self.skills, self.files)
        self.assertEqual(receipt["suites"]["recorded"]["tree"], expected)
        distinct = self.tree(self.skills, {"canon/SKILL.md": "New flat suite.\n",
                                          "canon/scripts/canon.py": ("100755", "new tool\n")})
        self.assertEqual(receipt["suites"]["candidate"]["tree"], distinct)
        self.assertEqual(receipt["suites"]["candidate"]["commit"], new)
        self.assertNotEqual(receipt["suites"]["candidate"]["manifest"], self.manifest)
        self.assertFalse((self.out / "private/suites/candidate/canon/.hidden").exists())
