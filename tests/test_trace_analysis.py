"""Offline report questions 7–9 and version coverage through the report command."""
import os
import hashlib
import json
from pathlib import Path
import subprocess

from test_trace_report import CONV, GATE, PRIOR, SECOND, TRACE, UNIT, ReportFixture, end, start, write_lines
from test_trace_reviews import reviewer, review_end


class OfflineAnalysis(ReportFixture):
    def git(self, root, *args, data=None, at="2025-12-31T22:00:00Z"):
        env = dict(os.environ, GIT_AUTHOR_NAME="Fixture", GIT_AUTHOR_EMAIL="f@example.invalid",
                   GIT_COMMITTER_NAME="Fixture", GIT_COMMITTER_EMAIL="f@example.invalid",
                   GIT_COMMITTER_DATE=at, GIT_AUTHOR_DATE=at)
        result = subprocess.run(["git", "-C", str(root), *args], env=env, input=data,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def repo(self, root):
        root.mkdir(parents=True, exist_ok=True)
        self.git(root, "init", "-q")
        self.assertEqual(self.git(root, "rev-parse", "--show-toplevel"), str(root))

    def commit(self, root, content, at="2025-12-31T22:00:00Z", path="rule"):
        (root / path).parent.mkdir(parents=True, exist_ok=True)
        (root / path).write_text(content + "\n")
        self.git(root, "add", "--", path)
        self.git(root, "commit", "-qm", "fixture", at=at)
        return self.git(root, "rev-parse", "HEAD")

    def notes(self, body):
        path = self.project / ".canon/canon-retro/notes.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body)
        return path

    def test_end_checks_keep_interruption_populations_costs_and_declined_history(self):
        open_unit = "20260101T001000Z-111111"
        write_lines(self.log, [
            start(), start(GATE, "end-check", parent=UNIT),
            end(GATE, "end-check", outcome="raised"), end(),
            start(PRIOR, "end-check", at="2025-12-31T23:59:00Z"),
            end(PRIOR, "end-check", at="2025-12-31T23:59:08Z", outcome="quiet"),
            start(open_unit)])
        note = self.notes(
            "## slow-check: noted\n- 2025-12-31 session: set declined\n"
            "- 2026-01-01 session: set noted\n## missing-label: declined\n"
            "- 2026-01-01 session: PRIVATE description (evidence)\n")
        q = self.cli()["questions"].get("8", {})
        self.assertIn("interruptions", q)
        rate = q["interruptions"]
        self.assertEqual((rate["numerator"], rate["denominator"], rate["sample"]), (1, 2, "few units"))
        self.assertEqual([r["case"].split("::")[-1] for r in rate["cases"]], [GATE])
        self.assertEqual({r["case"].split("::")[-1] for r in rate["eligible_cases"]}, {UNIT, PRIOR})
        checks = {r["case"].split("::")[-1]: r for r in q["checks"]}
        self.assertEqual((checks[GATE]["wall_seconds"], checks[PRIOR]["wall_seconds"]), (60, 8))
        self.assertEqual(checks[GATE]["tokens"], "unknown")
        self.assertEqual([(r["cause"], r["location"]) for r in q["declined"]],
                         [("slow-check", str(note) + "#L2"), ("missing-label", str(note) + "#L4")])
        self.assertIn("End-check cost and interruptions", self.cli(text=True))

    def test_outside_interruption_and_date_filtered_root(self):
        for closed in (False, True):
            events = [start(PRIOR, at="2025-12-31T23:59:00Z"), start(kind="end-check", parent=PRIOR),
                      end(kind="end-check", outcome="raised")]
            if closed:
                events.append(end(PRIOR))
            write_lines(self.log, events)
            args = ("--since", "2026-01-01") if closed else ()
            rate = self.cli(*args)["questions"]["8"]["interruptions"]
            self.assertEqual((rate["numerator"], rate["denominator"]), (0, 0))
            self.assertIn(UNIT, str(rate["outside_eligible_cases"]))

    def test_retro_fix_uses_snapshot_patch_and_traced_session_or_start_minute(self):
        self.repo(self.project)
        self.commit(self.project, "old")
        fix = self.commit(self.project, "new", "2026-01-01T01:00:00Z")
        store = self.log.parent
        self.repo(store)
        old = self.commit(store, "old")
        new = self.commit(store, "new")
        diverged = self.commit(store, "conflicts")
        cases = []
        for i, (time, snapshot, conv) in enumerate([
            ("00:00", old, CONV), ("02:00", new, SECOND), ("02:15", new, None),
            ("02:30", old, None), ("02:40", diverged, None), ("02:50", None, None),
            (None, new, None)]):
            uid = f"20260101T020000Z-{i:06d}"
            kind = "end-check" if i == 2 else "retro"
            cases.extend([start(uid, kind, f"2026-01-01T{time}:05Z" if time else None,
                                snapshot=snapshot, conversation=conv),
                          end(uid, kind, f"2026-01-01T{time}:35Z" if time else None,
                              outcome="quiet" if kind == "end-check" else "delivered")])
            if snapshot:
                self.git(store, "update-ref", "refs/trace/" + uid, snapshot)
        write_lines(self.log, cases)
        note = self.notes(f"## repeated-work: applied {fix[:10]}\n"
                          f"- 2026-01-01 {CONV}: set applied {fix[:10]}\n"
                          f"- 2026-01-01 {SECOND}: PRIVATE (fix {fix[:10]} fix=present)\n"
                          f"- 2026-01-01 20260101-0215: PRIVATE ({fix} fix=present)\n"
                          f"- 2026-01-01 20260101-0230: PRIVATE ({fix} fix=absent)\n"
                          f"- 2026-01-01 missing: PRIVATE ({fix} fix=present)\n"
                          f"- 2026-01-01 {SECOND}: PRIVATE (12345678 fix=present)\n")
        result = self.cli()["questions"].get("7", {})
        self.assertIn("fixes", result)
        row, = result["fixes"]
        self.assertEqual(row["commit"], fix)
        rate = row["recurrences"]
        self.assertEqual((rate["numerator"], rate["denominator"]), (2, 2))
        self.assertEqual({r["location"] for r in rate["cases"]}, {str(note) + "#L3", str(note) + "#L4"})
        self.assertEqual([r["case"][-6:] for r in rate["eligible_cases"]], ["000001", "000002"])
        self.assertEqual([r["case"][-6:] for r in rate["unknown_cases"]], ["000004", "000005", "000006"])
        self.assertEqual([r["case"][-6:] for r in row["absent_cases"]], ["000003"])
        self.assertIn(str(note) + "#L6", [r["location"] for r in row["unmatched_events"]])

    def test_repeated_commands_have_locators_without_command_text_and_keep_zeroes(self):
        self.repo(self.project)
        self.commit(self.project, "old")
        fix = self.commit(self.project, "new", "2026-01-01T01:00:00Z")
        store = self.log.parent
        self.repo(store)
        snapshot = self.commit(store, "new")
        early = start(host="cursor", conversation=CONV)
        late = start(GATE, at="2026-01-01T02:00:00Z", host="cursor", conversation=SECOND, snapshot=snapshot)
        write_lines(self.log, [early, end(), late, end(GATE, at="2026-01-01T02:03:00Z")])
        self.notes(f"## repeated: applied {fix}\n")
        for fields, repetitions in [(early, 3), (late, 1)]:
            uid, conv = fields["id"], fields["conversation"]
            transcript = self.cursor / "projects/example/agent-transcripts" / conv / (conv + ".jsonl")
            def shell(command):
                return {"role": "assistant", "message": {"content": [
                    {"type": "tool_use", "name": "Shell", "input": {"command": command}}]}}
            prefix = "python3 .agents/skills/canon/scripts/canon.py trace "
            write_lines(transcript, [shell(prefix + "start implement --tier L1"),
                                     *[shell("PRIVATE command") for _ in range(repetitions)],
                                     shell(prefix + f"end {uid} delivered")])
        fix_row, = self.cli()["questions"]["7"]["fixes"]
        self.assertIn("repeated_commands", fix_row)
        counts = fix_row["repeated_commands"]
        self.assertEqual([(r["count"], len(r["locations"])) for r in counts["before"]], [(2, 3)])
        self.assertEqual([r["count"] for r in counts["after"]], [0])
        self.assertEqual((fix_row["recurrences"]["numerator"], fix_row["recurrences"]["denominator"]), (0, 1))

    def test_undecoded_codex_shell_calls_leave_repetition_count_unknown(self):
        from test_trace_report import TraceReport
        self.repo(self.project)
        self.commit(self.project, "old")
        fix = self.commit(self.project, "new", "2026-01-01T01:00:00Z")
        self.notes(f"## repeated: applied {fix}\n")
        write_lines(self.log, [start(host="codex", conversation=CONV), end()])
        host = TraceReport()
        host.project, host.codex = self.project, self.codex
        missing = host.native(14, "response_item", type="custom_tool_call", name="exec", call_id="dynamic",
                              input="const options={cmd:'PRIVATE'};await tools.exec_command(options)")
        rows = [*host.boundary(4, "start implement --tier L1", "trace " + UNIT), missing, missing,
                *host.boundary(64, "end " + UNIT + " delivered", "trace " + UNIT + " ended", "close")]
        path = host.rollout(CONV, rows)
        result, = self.cli()["questions"]["7"]["fixes"][0]["repeated_commands"]["before"]
        self.assertEqual(result["count"], "unknown")
        self.assertEqual(result["undecoded_locations"], [str(path) + "#L4", str(path) + "#L5"])
        for code in ("const {exec_command}=tools; await exec_command({cmd:'private'})",
                     "for (const i of [0,1]) { await tools.exec_command({cmd:'private'}); }",
                     "await Promise.all([1,2].map(() => tools.exec_command({cmd:'private'})))",
                     "[1,2].forEach(() => tools.exec_command({cmd:'private'}))"):
            missing["payload"]["input"] = code
            host.rollout(CONV, rows)
            result, = self.cli()["questions"]["7"]["fixes"][0]["repeated_commands"]["before"]
            self.assertEqual(result["count"], "unknown", code)
        missing["payload"]["input"] = "const x=await tools.exec_command({cmd:'private'});text(x)"
        host.rollout(CONV, rows)
        result, = self.cli()["questions"]["7"]["fixes"][0]["repeated_commands"]["before"]
        self.assertEqual(result["count"], 1)

    def test_version_inventory_finds_reversions_local_content_and_mixed_children(self):
        skills = self.root / "skills-repo"
        self.repo(skills)
        path = "skills/governance/canon/SKILL.md"
        first = self.commit(skills, "before", path=path)
        changed = self.commit(skills, "after", path=path)
        reverted = self.commit(skills, "before", path=path)
        ignored = self.commit(skills, "PRIVATE", path="skills/governance/canon/NOTICE")
        def manifest(body):
            blob = self.git(skills, "hash-object", "--stdin", data=body + "\n")
            def digest(value):
                return hashlib.sha256(json.dumps(value, separators=(",", ":")).encode()).hexdigest()
            skill = digest([["SKILL.md", blob]])
            return dict(v=1, type="manifest", skills={"canon": skill}, digest=digest({"canon": skill}))
        one, two, local = [manifest(word) for word in ("before", "after", "local")]
        write_lines(self.log, [one, two, local, start(manifest=one["digest"], skill="skills/governance/canon"),
                               start(GATE, "gate", parent=UNIT, manifest=two["digest"], skill="/skills/canon"),
                               end(GATE, "gate"), end(manifest=one["digest"]),
                               start(PRIOR, manifest=local["digest"], skill="/skills/canon"),
                               end(PRIOR, manifest=two["digest"])])
        report = self.cli("--skills-repo", skills)
        self.assertIn("skill_versions", report)
        inventory = report["skill_versions"]
        def matches(name):
            return {r["digest"]: r for r in inventory[name]}
        self.assertEqual(set(matches("manifests")[one["digest"]]["commits"]), {first, reverted, ignored})
        self.assertEqual(matches("skills")[two["skills"]["canon"]]["commits"], [changed])
        self.assertEqual(matches("manifests")[local["digest"]]["status"], "local")
        units = {r["unit"]: r for r in report["cases"]}
        self.assertEqual(units[UNIT]["version"]["status"], "mixed")
        self.assertEqual(units[GATE]["version"]["status"], "single")
        self.assertEqual(units[PRIOR]["version"]["status"], "mixed")
        self.assertIn(str(self.log) + "#L5", units[UNIT]["version"]["locations"])
        self.assertIn("Skill versions", self.cli("--skills-repo", skills, text=True))
        shallow = self.root / "shallow"
        self.git(self.root, "clone", "--quiet", "--depth=1", skills.as_uri(), str(shallow))
        inventory = self.cli("--skills-repo", shallow)["skill_versions"]
        self.assertEqual(inventory["history"], "unknown")
        self.assertEqual(matches("manifests")[local["digest"]]["status"], "unknown")
        self.assertEqual(matches("manifests")[one["digest"]]["status"], "matched")

    def test_applied_note_without_a_commit_has_only_a_reason_and_location(self):
        write_lines(self.log, [start()])
        notes = self.notes("## use-local-check: applied (PRIVATE local configuration)\n")
        q = self.cli()["questions"]["7"]
        self.assertEqual(q["fixes"], [])
        self.assertEqual(q.get("unknown_fixes"), [dict(reason="applied fix has no commit", location=str(notes) + "#L1")])

    def test_recorded_fix_present_event_outside_verified_exposure_is_unmeasured(self):
        self.repo(self.project)
        self.commit(self.project, "old")
        fix = self.commit(self.project, "new")
        write_lines(self.log, [start(conversation=CONV), end()])
        notes = self.notes(f"## repeated: applied {fix}\n- 2026-01-01 {CONV}: PRIVATE ({fix} fix=present)\n")
        row, = self.cli()["questions"]["7"]["fixes"]
        self.assertEqual((row["recurrences"]["numerator"], row["recurrences"]["denominator"]), (0, 0))
        self.assertEqual(row["outside_eligible_events"][0]["location"], str(notes) + "#L2")

    def test_slice_replay_checks_snapshot_objects_and_plan_revision_without_fetching(self):
        store = self.log.parent
        self.repo(store)
        plan = "docs/plans/P001-example.md"
        body = "---\nrevision: 2\n---\n# P001: Example\n\n## Slices\n\n### S1: Work\n\nStatus: todo\n\nTest at the CLI."
        usable = self.commit(store, body, path=plan)
        missing = self.git(store, "hash-object", "--stdin", data="never stored")
        self.git(store, "update-index", "--add", "--cacheinfo", "100644," + missing + ",missing-file")
        tree = self.git(store, "write-tree", "--missing-ok")
        broken = self.git(store, "commit-tree", tree, "-m", "incomplete")
        self.git(store, "update-ref", "refs/trace/" + UNIT, usable)
        self.git(store, "update-ref", "refs/trace/" + GATE, broken)
        sentinel = self.root / "fetch-sentinel"
        sentinel.write_text('#!/bin/sh\nprintf attempted > "$0.called"\nexit 1\n')
        sentinel.chmod(0o755)
        self.git(store, "config", "protocol.ext.allow", "always")
        self.git(store, "config", "remote.origin.promisor", "true")
        self.git(store, "config", "remote.origin.url", "ext::" + str(sentinel))
        parent = start(PRIOR)
        first = start(UNIT, "slice", parent=PRIOR, slice="S1", docs=["P001@r2"], snapshot=usable)
        second = start(GATE, "slice", parent=PRIOR, slice="S1", docs=["P001@r2"], snapshot=broken)
        write_lines(self.log, [parent, first, second, end(PRIOR)])
        output = self.cli()
        replay = output["questions"].get("9", {})
        self.assertIn("units", replay)
        rows = {r["unit"]: r for r in replay["units"]}
        self.assertTrue(rows[UNIT]["eligible"])
        self.assertEqual(rows[UNIT]["steered"], "unknown")
        self.assertIn(plan, rows[UNIT]["score"]["test_criteria"])
        self.assertEqual(rows[UNIT]["parameters"]["slice"], "S1")
        self.assertFalse(rows[GATE]["eligible"])
        self.assertIn("opening snapshot unavailable", rows[GATE]["reasons"])
        self.assertFalse(Path(str(sentinel) + ".called").exists())
        self.assertEqual(replay["eligible"]["numerator"], 1)
        first["docs"] = ["P001@r3"]
        write_lines(self.log, [parent, first, end(PRIOR)])
        row, = self.cli()["questions"]["9"]["units"]
        self.assertIn("slice or plan revision unavailable", row["reasons"])

    def test_slice_score_joins_review_by_plan_parent_and_revision(self):
        sibling = "20260101T000019Z-555555"
        store = self.log.parent
        self.repo(store)
        path = "docs/plans/P001-example.md"
        plan = "---\nrevision: 2\n---\n# Plan\n\n## Slices\n\n### S1: First\n\nStatus: done\n\n### S2: Second\n\nStatus: done"
        opened = self.commit(store, plan, path=path)
        self.git(store, "update-ref", "refs/trace/" + UNIT, opened)
        people = [reviewer("spec", "one")]
        claim = dict(by=["spec:F1"], severity="major", axis="spec", disposition="accepted")
        self.archived_review(GATE, opened, None, people, {}, {"spec":"Target: fixture"})
        (store / GATE / "spec.md").write_text("### F1 [major] PRIVATE")
        events = [start(PRIOR), start(UNIT, "slice", parent=PRIOR, docs=["P001@r2"], slice="S1", snapshot=opened),
                  start(GATE, "code-review", "2026-01-01T00:01:00Z", parent=PRIOR, docs=["P001@r2"]),
                  review_end(GATE, "code-review", people, [claim]), end(PRIOR)]
        def score():
            write_lines(self.log, events)
            return self.cli()["questions"]["9"]["units"][0]["score"]["following_code_review"]
        self.assertEqual(score()["attribution"], "verified")
        self.assertIn("spec:F1", str(score()["findings"]))
        events.insert(2, start(sibling, "slice", "2026-01-01T00:00:19Z", parent=PRIOR, docs=["P001@r2"], slice="S2"))
        self.assertEqual(score()["attribution"], "unknown")
        self.assertIn(GATE, str(score()["candidate_reviews"]))
        events[3]["docs"] = ["P001@r3"]
        self.assertEqual(score()["candidate_reviews"], [])

    def tree(self, root, entries):
        self.git(root, "read-tree", "--empty")
        for name, data in entries.items():
            blob = self.git(root, "hash-object", "-w", "--stdin", data=data)
            self.git(root, "update-index", "--add", "--cacheinfo", "100644," + blob + "," + name)
        return self.git(root, "write-tree")

    def archived_review(self, unit, target, base, people, pins, prompts):
        directory = self.log.parent / unit
        directory.mkdir(parents=True, exist_ok=True)
        for stem, value in (("snapshot", target), ("baseline", base)):
            if value:
                (directory / (stem + ".txt")).write_text(value + "\n")
        for person in people:
            stem = person.get("key", person["role"])
            (directory / (stem + ".md")).write_text("No findings.\n")
            (directory / (stem + "-id.txt")).write_text(person["id"] or "")
            (directory / (stem + "-prompt.md")).write_text(prompts[stem])
            if stem in pins:
                (directory / (stem + "-snapshot.txt")).write_text(pins[stem] + "\n")

    def test_retained_prepared_pair_survives_loss_of_original_pins_but_not_unverified_supplement(self):
        source = self.project / ".canon/canon/snapshots"
        store = self.log.parent
        self.repo(source)
        original_base = self.commit(source, "base")
        original_target = self.commit(source, "target")
        self.repo(store)
        opening = self.commit(store, "opening")
        base_tree = self.tree(store, {"rule": "base\n"})
        target_tree = self.tree(store, {"rule": "target\n"})
        baseline = self.git(store, "commit-tree", base_tree, "-m", "synthetic baseline")
        retained = self.git(store, "commit-tree", target_tree, "-p", baseline, "-m", "synthetic first round")
        source.rename(self.root / "detached-source")
        self.assertNotEqual(original_base, baseline)
        self.assertNotEqual(original_target, retained)
        self.assertNotIn(original_base, self.git(store, "cat-file", "--batch-all-objects", "--batch-check=%(objectname)"))
        self.assertNotIn(original_target, self.git(store, "cat-file", "--batch-all-objects", "--batch-check=%(objectname)"))
        people = [reviewer("spec", "one"), reviewer("standards", "two")]
        prompt = f"Target: prepared patch from `git diff --binary --full-index {original_base} {original_target} -- rule`.\n"
        findings = [dict(by=["spec:F1"], severity="minor", disposition="declined", axis="spec")]
        events = []
        for uid in [UNIT, GATE]:
            members = people if uid == UNIT else [*people, reviewer("spec", "three", key="spec-2")]
            keys = [p.get("key", p["role"]) for p in members]
            pins = {k: original_target if k != "spec-2" else "a" * 40 for k in keys}
            self.archived_review(uid, original_target, original_base, members, pins, {k: prompt for k in keys})
            (store / uid / "spec.md").write_text("### F1 [minor] PRIVATE\n")
            self.git(store, "update-ref", "refs/trace/" + uid, opening)
            self.git(store, "update-ref", "refs/review-input/" + uid, retained)
            events += [start(uid, "code-review", snapshot=opening),
                       review_end(uid, "code-review", members, findings, review_input=retained)]
        write_lines(self.log, events)
        replay = self.cli()["questions"]["9"]
        rows = {r["unit"]: r for r in replay["units"]}
        self.assertTrue(rows[UNIT]["eligible"], rows[UNIT]["reasons"])
        given = rows[UNIT]["review_input"]
        self.assertEqual((given["target_tree"], given["baseline_tree"]), (target_tree, base_tree))
        self.assertEqual(given["source"], "retained first round")
        self.assertEqual(rows[UNIT]["score"]["dispositions"][0]["disposition"], "declined")
        self.assertIn("supplemental input unverified", rows[GATE]["reasons"])
        self.assertEqual(replay["eligible"]["numerator"], 1)
        archive = store / UNIT
        (archive / "standards-prompt.md").write_text(prompt + "Paths: absent.py\n")
        row = self.cli()["questions"]["9"]["units"][0]
        self.assertIn("archived prompt scope unverified", row["reasons"])
        for label in ("**Paths:**", "__Paths:__", "## Paths"):
            (archive / "standards-prompt.md").write_text(prompt + label + "\n- absent.py\n")
            row = self.cli()["questions"]["9"]["units"][0]
            self.assertIn("archived prompt scope unverified", row["reasons"], label)
        (archive / "standards-prompt.md").write_text(prompt)
        events[1]["dispositions"]["findings"][0]["by"] = ["spec:F99"]
        write_lines(self.log, events)
        row = self.cli()["questions"]["9"]["units"][0]
        self.assertFalse(row["eligible"])
        self.assertIn("spec:F99", str(row["score"]["unverified_sources"]))

    def test_gate_verifies_the_reviewed_as_built_tree_against_the_opening_second_parent(self):
        self.repo(self.project)
        old = self.commit(self.project, "first")
        new = self.commit(self.project, "second")
        store = self.log.parent
        self.repo(store)
        path = "docs/designs/D001-example.md"
        def target(code):
            return self.tree(store, {path: f"---\nrevision: 4\nas_built: {code}\n---\n# Design\n"})
        first_tree = target(old)
        prior = self.git(store, "commit-tree", first_tree, "-m", "baseline")
        code_tree = self.tree(store, {"rule": "first\n"})
        second = self.git(store, "commit-tree", code_tree, "-m", "as-built code")
        opening = self.git(store, "commit-tree", first_tree, "-p", prior, "-p", second, "-m", "opening")
        people = [reviewer("same-model", "one", targets=["D001@r4"])]
        rows = []
        for uid, code in ((UNIT, old), (GATE, new)):
            retained = self.git(store, "commit-tree", target(code), "-m", "retained full document")
            self.git(store, "update-ref", "refs/trace/" + uid, opening)
            self.git(store, "update-ref", "refs/review-input/" + uid, retained)
            self.archived_review(uid, retained, "none", people, {"same-model": retained},
                                 {"same-model": f"Target: {path}\nAs-built: the target records the code at {code}.\n"})
            rows += [start(uid, "gate", docs=["D001@r4"], snapshot=opening),
                     review_end(uid, "gate", people, [], review_input=retained)]
        write_lines(self.log, rows)
        units = {r["unit"]: r for r in self.cli()["questions"]["9"]["units"]}
        self.assertTrue(units[UNIT]["eligible"], units[UNIT]["reasons"])
        self.assertEqual(units[UNIT]["review_input"]["as_built_tree"], code_tree)
        self.assertIn("as-built code tree differs", units[GATE]["reasons"])
        self.assertFalse(units[GATE]["eligible"])

    def test_legacy_opening_requires_independent_input_and_excludes_handoffs_and_continuations(self):
        store = self.log.parent
        source = self.project / ".canon/canon/snapshots"
        self.repo(store)
        self.repo(source)
        path = "docs/designs/D002-example.md"
        body = "---\nrevision: 1\n---\n# D002\n"
        opening = self.git(store, "commit-tree", self.tree(store, {path: body}), "-m", "opening")
        original = self.git(source, "commit-tree", self.tree(source, {path: body}), "-m", "actual round")
        changed = self.git(source, "commit-tree", self.tree(source, {path: body + "Other content\n"}), "-m", "later")
        people = [reviewer("same-model", "one")]
        entries = []
        for i, pin in enumerate((original, changed, None, original, original)):
            uid = f"20260101T000005Z-{i:06}"
            who = {"continues": "20260101T000005Z-000003"} if i == 4 else {}
            self.git(store, "update-ref", "refs/trace/" + uid, opening)
            self.archived_review(uid, pin, None, people, {}, {"same-model": "Target: " + path})
            entries += [start(uid, "gate", docs=["D002@r1"], snapshot=opening, **who),
                        review_end(uid, "gate", people, [], outcome="handoff" if i == 3 else "delivered")]
        write_lines(self.log, entries)
        rows = self.cli()["questions"]["9"]["units"]
        self.assertTrue(rows[0]["eligible"], rows[0]["reasons"])
        self.assertEqual(rows[0]["review_input"]["source"], "independently verified opening")
        self.assertIn("different opening and first-round targets", rows[1]["reasons"])
        self.assertIn("legacy first-round target unverified", rows[2]["reasons"])
        self.assertIn("handoff", rows[3]["reasons"])
        self.assertIn("continuation", rows[4]["reasons"])
        self.assertEqual([r["eligible"] for r in rows], [True, False, False, False, False])

    def test_later_verdict_with_nonstandard_stem_is_separate_from_first_reports_and_replay(self):
        store = self.log.parent
        self.repo(store)
        path = "docs/designs/D001-example.md"
        opened = self.commit(store, "---\nrevision: 1\n---\n# Design", path=path)
        self.git(store, "update-ref", "refs/trace/" + UNIT, opened)
        self.git(store, "update-ref", "refs/review-input/" + UNIT, opened)
        people = [reviewer("cross-family", "one")]
        self.archived_review(UNIT, opened, "none", people, {"cross-family": opened}, {"cross-family": "Target: " + path})
        directory = store / UNIT
        (directory / "another-pass-snapshot.txt").write_text("c" * 40 + "\n")
        write_lines(self.log, [start(kind="gate", snapshot=opened, docs=["D001@r1"]),
                               review_end(UNIT, "gate", people, [], review_input=opened)])
        for label in ("N1", "B1"):
            with self.subTest(label=label):
                (directory / "another-pass.md").write_text(f"**{label} — resolved.** PRIVATE explanation.\n\nVerdict: sound\n")
                (directory / "another-pass-prompt.md").write_text(f"The author revised the target after your recheck. Confirm {label}: PRIVATE\n")
                report = self.cli()
                review = report["cases"][0]["review"]
                self.assertEqual([r["key"] for r in review["reports"]], ["cross-family"])
                self.assertIn(str(directory / "another-pass.md"), review["later_confirmation_reports"])
                self.assertTrue(report["questions"]["9"]["units"][0]["eligible"])
        (directory / "another-pass.md").write_text("### F1 [major] PRIVATE new first-round report.\n")
        self.assertFalse(self.cli()["questions"]["9"]["units"][0]["eligible"])

    def test_live_diff_verifies_separate_untracked_files_and_steering(self):
        store = self.log.parent
        self.repo(store)
        base = self.commit(store, "old")
        tracked_tree = self.tree(store, {"rule": "changed\n"})
        tree = self.tree(store, {"rule": "changed\n", ".fresh.txt": "PRIVATE new file\n"})
        retained = self.git(store, "commit-tree", tree, "-p", base, "-m", "live target")
        self.git(store, "update-ref", "refs/trace/" + UNIT, base)
        self.git(store, "update-ref", "refs/review-input/" + UNIT, retained)
        people = [reviewer("spec", "one")]
        prompt = f"Target: `git diff --binary --full-index {base}`\nUntracked files: .fresh.txt"
        self.archived_review(UNIT, retained, base, people, {"spec": retained}, {"spec": prompt})
        write_lines(self.log, [start(kind="code-review", host="cursor", conversation=CONV, snapshot=base),
                               review_end(UNIT, "code-review", people, [], review_input=retained)])
        transcript = self.cursor / "projects/example/agent-transcripts" / CONV / (CONV + ".jsonl")
        def shell(cmd):
            return {"role": "assistant", "message": {"content": [{"type": "tool_use", "name": "Shell", "input": {
                "command": "python3 .agents/skills/canon/scripts/canon.py trace " + cmd}}]}}
        write_lines(transcript, [shell("start code-review --tier L1"), {"role": "user", "message": {
            "content": [{"type": "text", "text": "PRIVATE steering"}]}}, shell(f"end {UNIT} delivered")])
        row, = self.cli()["questions"]["9"]["units"]
        self.assertTrue(row["eligible"], row["reasons"])
        self.assertIs(row["steered"], True)
        self.assertIn(str(transcript) + "#L2", row["steering_locations"])
        tracked = self.git(store, "diff", "--binary", "--full-index", base, tracked_tree).encode() + b"\n"
        self.assertEqual(row["review_input"]["patch_sha256"], hashlib.sha256(tracked).hexdigest())
        file, = row["review_input"]["untracked_files"]
        self.assertEqual(file["mode"], "100644")
        self.assertTrue(file["location"].endswith(":.fresh.txt"))
        (store / UNIT / "spec-prompt.md").write_text(prompt.replace("fresh.txt", "missing.txt"))
        row, = self.cli()["questions"]["9"]["units"]
        self.assertIn("archived prompt scope unverified", row["reasons"])

    def test_replay_explains_skipped_capture_and_rejects_missing_scoped_targets(self):
        store = self.log.parent
        self.repo(store)
        base = self.commit(store, "old")
        target = self.commit(store, "new")
        self.git(store, "update-ref", "refs/trace/" + UNIT, base)
        self.git(store, "update-ref", "refs/review-input/" + UNIT, target)
        people = [reviewer("spec", "one")]
        self.archived_review(UNIT, target, base, people, {"spec": target}, {
            "spec": f"Target: prepared `git diff {base} {target} -- missing-target`"})
        write_lines(self.log, [start(kind="code-review", snapshot=base),
                               review_end(UNIT, "code-review", people, [], review_input=target),
                               start(GATE, "gate", skipped="changes-over-10MiB"), end(GATE, "gate")])
        rows = self.cli()["questions"]["9"]["units"]
        self.assertFalse(rows[0]["eligible"])
        self.assertEqual(rows[1]["snapshot_issue"], "changes-over-10MiB")
