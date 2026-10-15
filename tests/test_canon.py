"""Regression tests for skills/governance/canon/scripts/canon.py; scripts/validate.py runs them."""

import contextlib
import datetime
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

try:
    import fcntl
except ImportError:  # Windows
    fcntl = None

SCRIPT = Path(__file__).resolve().parents[1] / "skills/governance/canon/scripts/canon.py"
sys.dont_write_bytecode = True
_spec = importlib.util.spec_from_file_location("canon", SCRIPT)
canon = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(canon)

FINDINGS = "## Scope\n\nFixture.\n\n## Findings\n\n| ID | Severity | Finding | Disposition |\n|---|---|---|---|\n{}\n"
PLAN = "## Current state\n\nNext: S1.\n\n## Slices\n\n### S1: First\n\nStatus: todo\n\n## Notes\n\n{}\n\n## Log\n\nStarted.\n"


class CanonTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.name", "canon test")
        self.git("config", "user.email", "canon@example.invalid")
        self.ok("init", "--no-architecture")
        (self.root / "src").mkdir()
        (self.root / "src/base.py").write_text("value = 1\n")

    def run_here(self, *args):
        return subprocess.run(args, cwd=self.root, capture_output=True, text=True)

    def git(self, *args):
        result = self.run_here("git", *args)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def canon(self, *args):
        return self.run_here(sys.executable, "-B", str(SCRIPT), *args)

    def ok(self, *args):
        result = self.canon(*args)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result.stdout

    def fails(self, *args):
        result = self.canon(*args)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        return result.stdout + result.stderr

    def set(self, path, **fields):
        text = path.read_text()
        for key, value in fields.items():
            text = canon.set_field(text, key, value)
        path.write_text(text)

    def doc(self, letter, slug, body=None, parent=None, **fields):
        path = self.root / self.ok("new", letter, slug, *(["--parent", parent] if parent else [])).strip()
        text = re.sub(r"<!-- canon:.*?-->", "Fixture content.", path.read_text(), flags=re.S)
        if body is not None:
            text = "{}\n# {}: Fixture\n\n{}".format(text.split("\n# ", 1)[0], path.name.split("-", 1)[0], body)
        path.write_text(text)
        self.set(path, summary="Fixture", **{k: v for k, v in fields.items() if v is not None})
        return path

    def design(self, slug="area", **fields):
        values = dict(status="active", reviewed=1, reviewers=["fixture"], implemented=1, owns=[slug],
                      paths=["src/**"])
        values.update(fields)
        return self.doc("D", slug, **values)

    def commit(self, check=True):
        if check:
            self.ok("check", "--fix")
        else:
            self.ok("index")
        self.git("add", "-A")
        self.git("commit", "-qm", "fixture")


class ReviewGateTest(CanonTest):
    def test_pending_revision_warns_locally_and_fails_with_base(self):
        design = self.design()
        self.commit()
        self.set(design, revision=2)
        out = self.ok("check")
        self.assertRegex(out, r"WARN .*revision 2 is not reviewed")
        self.assertRegex(self.fails("check", "--base", "HEAD"), r"ERROR .*revision 2 is not reviewed")

    def test_revising_a_plan_in_progress_warns_locally_and_fails_with_base(self):
        self.design()
        plan = self.doc("P", "work", status="in-progress", reviewed=1, reviewers=["fixture"], refs=["D001"],
                        based_on=["D001@r1"])
        self.commit()
        self.set(plan, revision=2)
        self.assertRegex(self.ok("check"), r"WARN .*revision 2 is not reviewed")
        self.assertRegex(self.fails("check", "--base", "HEAD"), r"ERROR .*revision 2 is not reviewed")


class ImplementedTest(CanonTest):
    def test_fix_fills_implemented_for_a_design_never_revised(self):
        design = self.design(implemented=None)
        self.assertIn("needs `implemented`", self.fails("check"))
        self.ok("check", "--fix")
        self.assertIn("implemented: 1", design.read_text())

    def test_fix_reads_the_committed_revision_while_a_revision_awaits_implementation(self):
        design = self.design(implemented=None)
        self.commit(check=False)
        self.set(design, revision=2, reviewed=2)
        self.ok("check", "--fix")
        self.assertIn("implemented: 1", design.read_text())

    def test_no_fix_for_a_revised_design(self):
        design = self.design(revision=2, reviewed=2, implemented=None)
        self.commit(check=False)
        self.assertIn("needs `implemented`", self.fails("check", "--fix"))
        self.assertNotIn("implemented:", design.read_text())

    def test_no_fix_while_a_plan_is_open(self):
        self.design(implemented=None)
        self.doc("P", "work", based_on=["D001@r1"], refs=["D001"])
        self.assertIn("needs `implemented`", self.fails("check", "--fix"))

    def test_implemented_stays_within_review_and_status(self):
        design = self.design(revision=2, reviewed=1, implemented=2)
        self.assertIn("is above `reviewed`", self.fails("check"))
        self.set(design, status="accepted", reviewed=2, implemented=1)
        self.assertIn("status is `accepted`", self.fails("check"))

    def test_setting_implemented_alone_needs_no_updated_bump(self):
        design = self.design(implemented=None, created="2026-01-01", updated="2026-01-01")
        self.commit(check=False)
        self.set(design, implemented=1)
        self.ok("check")

    def test_which_marks_a_spec_that_leads_the_code(self):
        self.design(revision=2, reviewed=2, implemented=1)
        self.assertIn("[spec r2 leads code r1]", self.ok("which", "src/base.py"))


class RenumberTest(CanonTest):
    def test_renumber_normalizes_requested_id(self):
        design = self.design()
        child = self.design("part", parent="D001")
        body = "Implements [D001: Area](../designs/D001-area.md).\n\n" + PLAN.format("None.")
        plan = self.doc("P", "work", body=body, refs=["D001"], based_on=["D001@r1"])
        self.commit()
        self.ok("renumber", "D001", "D0002")
        self.ok("check", "--fix")
        self.assertTrue(design.with_name("D002-area.md").is_file())
        self.assertTrue(child.with_name("D002A-part.md").is_file())
        self.assertIn("based_on: [D002@r1]", plan.read_text())
        self.assertIn("refs: [D002]", plan.read_text())
        self.assertIn("[D002: Area](../designs/D002-area.md)", plan.read_text())
        self.ok("show", "D002")

    def test_padded_requested_id_cannot_reuse_an_existing_id(self):
        self.design()
        self.design("other")
        self.commit()
        self.assertIn("already used", self.fails("renumber", "D001", "D0002"))
        self.assertEqual(self.git("status", "--porcelain"), "")
        self.ok("check")

    def test_renumber_rewrites_structured_references(self):
        self.design()
        concept = self.doc("C", "refs-only", refs=["D001"])
        plan = self.doc("P", "work", based_on=["D001@r1"], refs=["D001"])
        review = self.doc("R", "audit", body=FINDINGS.format("| R001-F1 | major | A spec fix | moved D001 |"))
        self.commit()
        self.ok("renumber", "D001", "D005")
        self.ok("check", "--fix")
        self.assertIn("refs: [D005]", concept.read_text())
        self.assertIn("based_on: [D005@r1]", plan.read_text())
        self.assertIn("| moved D005 |", review.read_text())

    def test_renumbered_review_rewrites_its_finding_ids(self):
        self.doc("R", "audit", body=FINDINGS.format("| R001-F1 | major | A defect | open |"))
        self.commit()
        self.ok("renumber", "R001", "R002")
        self.ok("check", "--fix")
        self.assertIn("| R002-F1 |", (self.root / "docs/reviews/R002-audit.md").read_text())

    def test_renumber_after_a_collision_keeps_unlinked_references(self):
        ours = self.design()
        theirs = ours.with_name("D001-other.md")
        theirs.write_text(ours.read_text().replace("owns: [area]", "owns: [other]"))
        concept = self.doc("C", "refs-only", refs=["D001"])
        out = self.ok("renumber", str(ours.relative_to(self.root)))
        self.assertIn("kept D001", out)
        self.assertIn("refs: [D001]", concept.read_text())
        self.ok("check", "--fix")

    def test_collision_keeps_references_its_links_cannot_settle(self):
        ours = self.design()
        ours.with_name("D001-other.md").write_text(ours.read_text().replace("owns: [area]", "owns: [other]"))
        body = "Implements [D001: Other](../designs/D001-other.md).\n\n" + PLAN.format(
            "Related: [D001: Area](../designs/D001-area.md).")
        plan = self.doc("P", "work", body=body, refs=["D001"], based_on=["D001@r1"])
        out = self.ok("renumber", str(ours.relative_to(self.root)))
        self.assertIn("kept D001 in docs/plans/P001-work.md", out)
        self.assertIn("based_on: [D001@r1]", plan.read_text())
        self.ok("check", "--fix")
        self.assertIn("refs: [D001, D002]", plan.read_text())

    def test_collision_leaves_a_sub_design_linked_to_the_other_design(self):
        ours = self.design()
        ours.with_name("D001-other.md").write_text(ours.read_text().replace("owns: [area]", "owns: [other]"))
        child = ours.with_name("D001A-other-part.md")
        child.write_text(ours.read_text().replace("# D001:", "# D001A:").replace("owns: [area]", "owns: [other-part]")
                         + "\nPart of [D001: Other](D001-other.md).\n")
        self.ok("renumber", str(ours.relative_to(self.root)))
        self.assertTrue(child.is_file())
        self.ok("check", "--fix")

    def test_renumber_after_a_merge_sorts_sub_designs_by_the_base(self):
        self.commit()
        self.git("checkout", "-q", "-b", "other")
        self.design("other")
        theirs_child = self.design("their-part", parent="D001")
        self.commit()
        self.git("checkout", "-q", "main")
        target = str(self.design().relative_to(self.root))
        self.design("our-part", parent="D001")
        self.commit()
        self.git("merge", "-q", "--no-edit", "other")
        self.assertIn("cannot tell which D001 owns", self.fails("renumber", target))
        self.ok("renumber", target, "--base", "other")
        self.assertTrue(theirs_child.is_file())
        self.assertTrue((self.root / "docs/designs/D002A-our-part.md").is_file())
        self.ok("check", "--fix")

    def test_a_colliding_sub_design_takes_a_free_letter(self):
        self.design()
        self.commit()
        self.git("checkout", "-q", "-b", "other")
        self.design("their-part", parent="D001")
        self.commit()
        self.git("checkout", "-q", "main")
        ours = self.design("our-part", parent="D001")
        self.commit()
        self.assertIn("D001A was also added on other", self.fails("check", "--base", "other"))
        self.assertIn("D001A -> D001B", self.ok("renumber", str(ours.relative_to(self.root)), "--base", "other"))
        self.commit()
        self.git("merge", "-q", "--no-edit", "other")
        self.ok("check", "--fix")

    def test_commands_refuse_an_ambiguous_id(self):
        ours = self.design()
        ours.with_name("D001-other.md").write_text(ours.read_text().replace("owns: [area]", "owns: [other]"))
        self.assertIn("D001 is the id of", self.fails("new", "P", "work", "--from", "D001"))


class IdAllocationTest(CanonTest):
    def parallel_new(self, slugs):
        with ThreadPoolExecutor(max_workers=len(slugs)) as pool:
            results = list(pool.map(lambda slug: self.canon("new", "E", slug), slugs))
        for result in results:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return [result.stdout.strip() for result in results]

    def test_parallel_new_allocates_unique_ids(self):
        paths = self.parallel_new(["topic-{}".format(i) for i in range(12)])
        self.assertEqual(len({Path(p).name.split("-", 1)[0] for p in paths}), 12)

    def test_parallel_new_with_one_slug_never_overwrites(self):
        paths = self.parallel_new(["same-topic"] * 3)
        self.assertEqual(len(set(paths)), 3)
        self.assertTrue(all((self.root / p).is_file() for p in paths))

    def test_a_held_lock_is_never_broken_by_its_age(self):
        root = Path(os.path.realpath(str(self.root)))
        with canon.id_lock(SimpleNamespace(root=root)):
            os.utime(str(root / ".canon/id.lock"), (0, 0))
            waiter = subprocess.Popen([sys.executable, "-B", str(SCRIPT), "new", "E", "waiter"], cwd=root,
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            time.sleep(1)
            self.assertIsNone(waiter.poll())
        out, err = waiter.communicate(timeout=60)
        self.assertEqual(waiter.returncode, 0, out + err)


class UnfinishedDocTest(CanonTest):
    def test_a_fresh_draft_only_warns_until_checked_against_a_base(self):
        self.commit()
        self.ok("new", "D", "half-written")
        out = self.ok("check")
        self.assertRegex(out, r"WARN .*`summary` is empty")
        self.assertRegex(out, r"WARN .*template guidance")
        self.assertRegex(self.fails("check", "--base", "HEAD"), r"ERROR .*template guidance")

    def test_running_research_only_warns(self):
        path = self.root / self.ok("new", "E", "research").strip()
        self.set(path, status="running")
        self.assertRegex(self.ok("check", "--fix"), r"WARN .*template guidance")

    def test_guidance_fails_once_past_the_review_gate(self):
        path = self.root / self.ok("new", "D", "gated").strip()
        self.set(path, status="accepted", reviewed=1, reviewers=["fixture"], summary="Fixture")
        self.assertRegex(self.fails("check"), r"ERROR .*template guidance")


class ChangedFilesTest(CanonTest):
    def test_affected_reads_names_with_spaces_and_non_ascii(self):
        self.design()
        self.commit()
        names = ["src/a b.py", "src/中文.py"]
        for name in names:
            (self.root / name).write_text("x = 1\n")
        untracked = self.ok("affected")
        self.commit()
        for name in names:
            (self.root / name).write_text("x = 2\n")
        modified = self.ok("affected")
        for name in names:
            self.assertIn("  " + name + "\n", untracked)
            self.assertIn("  " + name + "\n", modified)


class FrontmatterTest(CanonTest):
    def test_brackets_make_lists_only_in_list_fields(self):
        concept = self.doc("C", "idea")
        self.set(concept, summary="[a, b]")
        self.ok("check", "--fix")
        self.assertIn(" - [a, b]", self.ok("find", "C001"))


class AuditTest(CanonTest):
    def code_commit(self, message):
        code = self.root / "src/base.py"
        code.write_text(code.read_text() + "x = 1\n")
        self.git("add", "-A")
        self.git("commit", "-qm", message)

    def test_counts_commits_whose_trailer_omits_the_design(self):
        self.design()
        self.commit()
        self.code_commit("fix: same day")
        self.code_commit("fix: checked\n\nRefs: D001, P001")
        self.code_commit("fix: other design\n\nRefs: D002")
        self.assertRegex(self.ok("audit"), r"2 commits since [0-9a-f]+  D001 ")

    def test_changing_the_design_moves_the_baseline(self):
        design = self.design()
        self.commit()
        self.code_commit("fix: unchecked")
        design.write_text(design.read_text() + "\nChecked against the code.\n")
        self.commit()
        self.assertNotIn("D001", self.ok("audit"))

    def test_idle_docs_skip_concepts(self):
        self.doc("C", "backlog", created="2020-01-01", updated="2020-01-01")
        self.doc("I", "flaky", created="2020-01-01", updated="2020-01-01")
        out = self.ok("audit")
        self.assertIn("I001", out)
        self.assertNotIn("C001", out)


class InitTest(CanonTest):
    def test_init_replaces_an_older_script_copy(self):
        copy = self.root / "scripts/canon.py"
        copy.write_text(re.sub(r'^CANON_VERSION = "\d+"', 'CANON_VERSION = "2"', SCRIPT.read_text(), flags=re.M))
        self.assertIn("updated scripts/canon.py", self.ok("init", "--no-architecture"))
        self.assertEqual(copy.read_text(), SCRIPT.read_text())

    def test_init_warns_about_a_same_version_copy_that_differs(self):
        copy = self.root / "scripts/canon.py"
        copy.write_text(SCRIPT.read_text() + "# local edit\n")
        self.assertIn("differs from this canon.py", self.ok("init", "--no-architecture"))
        self.assertTrue(copy.read_text().endswith("# local edit\n"))


class TraceTest(CanonTest):
    HOST_VARS = ("CURSOR_AGENT", "CURSOR_CONVERSATION_ID", "CODEX_THREAD_ID", "CLAUDECODE")

    def setUp(self):
        super().setUp()
        config = tempfile.TemporaryDirectory()
        self.addCleanup(config.cleanup)
        self.config = Path(config.name)
        self.events = self.root / ".canon/canon/trace/events.jsonl"

    def trace(self, *args, cwd=None, **env):
        """Run `canon.py trace` with the machine switch under a temporary XDG_CONFIG_HOME and no host variables but
        those in `env`; assert that it exits 0."""
        full = {key: value for key, value in os.environ.items() if key not in self.HOST_VARS}
        full.update(XDG_CONFIG_HOME=str(self.config), **env)
        result = subprocess.run([sys.executable, "-B", str(SCRIPT), "trace", *args], cwd=str(cwd or self.root),
                                env=full, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result.stdout

    def files(self):
        return sorted(p for top in (self.root, self.config) for p in top.rglob("*"))

    def start(self, *args, **env):
        out = self.trace("start", *args, **env)
        self.assertRegex(out, r"^trace \d{8}T\d{6}Z-[0-9a-f]{6}\n$")
        return out.split()[1]

    def lines(self, events=None):
        return [json.loads(line) for line in (events or self.events).read_text(encoding="utf-8").splitlines()]

    def rejects(self, *args, **env):
        """Assert that the call prints a trace error, exits 0 and leaves the events file as it was."""
        before = self.events.read_bytes() if self.events.exists() else None
        self.assertRegex(self.trace(*args, **env), r"^trace error: ")
        self.assertEqual(self.events.read_bytes() if self.events.exists() else None, before, args)

    @unittest.skipIf(os.name == "nt", "the recording git is a shell script")
    def test_tracing_off_writes_nothing_and_runs_no_git(self):
        bin_dir, log = self.config / "bin", self.config / "git.log"
        bin_dir.mkdir()
        (bin_dir / "git").write_text("#!/bin/sh\necho \"$@\" >> '{}'\n".format(log))
        (bin_dir / "git").chmod(0o755)
        path = str(bin_dir) + os.pathsep + os.environ["PATH"]
        for opted_out in (False, True):
            if opted_out:
                (self.config / "canon").mkdir()
                (self.config / "canon/trace").touch()
                (self.root / ".canon/canon/trace").mkdir(parents=True)
                (self.root / ".canon/canon/trace/off").touch()
            files = self.files()
            for args in (["start", "design", "D001"], ["end", "20261015T081502Z-3f9a1c", "delivered"]):
                self.assertEqual(self.trace(*args, PATH=path), "trace off\n")
            self.assertEqual(self.files(), files)
        self.assertFalse(log.exists())

    def test_switches_and_status_say_why_tracing_is_on_or_off(self):
        switch, off = self.config / "canon/trace", self.root / ".canon/canon/trace/off"
        self.assertRegex(self.trace("status"), r"^trace off: no machine switch")
        notice = self.trace("on")
        self.assertTrue(switch.is_file())
        self.assertIn("must exclude .canon/", notice)
        self.assertRegex(self.trace("status"), r"^trace on: ")
        self.trace("off", "--here")
        self.assertTrue(off.is_file())
        self.assertRegex(self.trace("status"), r"^trace off: this checkout opted out")
        self.trace("on", "--here")
        self.assertFalse(off.exists())
        self.assertRegex(self.trace("status"), r"^trace on: ")
        self.trace("off")
        self.assertFalse(switch.exists())
        self.assertRegex(self.trace("status"), r"^trace off: no machine switch")

    def test_start_prints_an_id_and_records_each_doc_at_its_revision(self):
        self.trace("on")
        self.design(revision=3, reviewed=3)
        self.design("old")
        self.ok("archive", "D002", "retired")
        self.ok("init", "--root", "mod", "--no-architecture")
        self.ok("new", "D", "part", "--root", "mod")
        unit = self.start("design", "D001", "D002", "D003", "D999")
        [line] = self.lines()
        self.assertEqual(set(line), {"v", "type", "id", "kind", "at", "parent", "docs", "tier", "host", "conversation",
                                     "model", "skill"})
        self.assertEqual([line[k] for k in ("v", "type", "id", "kind", "parent", "tier", "model", "skill")],
                         [1, "start", unit, "design", None, None, None, None])
        self.assertEqual(line["docs"], ["D001@r3", "D002@r1", "D003@r1", "D999"])
        self.assertRegex(line["at"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d[+-]\d\d:\d\d$")
        at = datetime.datetime.fromisoformat(line["at"])
        self.assertEqual(at.utcoffset(), at.astimezone().utcoffset())
        self.assertEqual(at.astimezone(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ"), unit.split("-")[0])

    def test_host_and_conversation_come_from_the_environment_and_the_model_is_lowercased(self):
        self.trace("on")
        hosts = [({"CURSOR_AGENT": "1", "CURSOR_CONVERSATION_ID": "c-1"}, "cursor", "c-1"),
                 ({"CODEX_THREAD_ID": "t-1"}, "codex", "t-1"),
                 ({"CLAUDECODE": "1"}, "claude-code", None),
                 ({}, "other", None)]
        for env, _host, _conversation in hosts:
            self.start("design", **env)
        self.assertEqual([(line["host"], line["conversation"]) for line in self.lines()],
                         [(host, conversation) for _env, host, conversation in hosts])
        self.start("design", "--model", "Claude-Opus-5.5", "--skill", "skills/canon-design", cwd=self.root / "src")
        line = self.lines()[-1]
        self.assertEqual(line["model"], "claude-opus-5.5")
        self.assertEqual(line["skill"], os.path.join(os.path.realpath(self.root), "src", "skills", "canon-design"))

    def test_children_record_their_parent_and_a_slice_takes_its_parents_tier_skill_and_model(self):
        self.trace("on")
        implement = self.start("implement", "P001", "--tier", "L1", "--skill", "skills/canon-implement",
                               "--model", "Opus-X")
        gate = self.start("gate", "D001", "--parent", implement)
        piece = self.start("slice", "P001", "--slice", "S1", "--parent", implement)
        lone_gate, check = self.start("gate", "D001"), self.start("end-check")
        lines = {line["id"]: line for line in self.lines()}
        self.assertEqual((lines[gate]["parent"], lines[gate]["tier"]), (implement, "L1"))
        self.assertEqual([lines[piece][k] for k in ("parent", "slice", "tier", "skill", "model")],
                         [implement, "S1", "L1", os.path.join(os.path.realpath(self.root), "skills", "canon-implement"),
                          "opus-x"])
        self.assertEqual((lines[lone_gate]["parent"], lines[check]["parent"]), (None, None))
        self.trace("end", lone_gate, "delivered")
        for args in (["gate", "--parent", "20200101T000000Z-000000"],
                     ["gate", "--parent", lone_gate],
                     ["gate", "--parent", piece],
                     ["gate", "--parent", check],
                     ["slice", "P001", "--slice", "S2", "--parent", gate],
                     ["slice", "P001", "--slice", "S2"],
                     ["slice", "P001", "--parent", implement],
                     ["gate", "D001", "--slice", "S2"],
                     ["design", "D001", "--parent", implement]):
            self.rejects("start", *args)

    def test_end_closes_the_unit_it_names_with_an_outcome_its_kind_allows(self):
        self.trace("on")
        design = self.start("design", "D001")
        self.assertEqual(self.trace("end", design, "delivered"), "trace {} ended\n".format(design))
        implement = self.start("implement", "P001")
        piece = self.start("slice", "P001", "--slice", "S1", "--parent", implement)
        check = self.start("end-check")
        for args in ([design, "delivered"], [piece, "delivered"], ["20200101T000000Z-000000", "delivered"],
                     [implement, "quiet"], [check, "delivered"], [implement, "escalated"],
                     [implement, "delivered", "--to", "L1"]):
            self.rejects("end", *args)
        self.trace("end", implement, "escalated", "--to", "plan")
        self.trace("end", check, "raised")
        ends = [line for line in self.lines() if line["type"] == "end"]
        self.assertEqual(set(ends[0]), {"v", "type", "id", "kind", "at", "outcome"})
        self.assertEqual([[end.get(k) for k in ("v", "id", "kind", "outcome", "to")] for end in ends],
                         [[1, design, "design", "delivered", None], [1, implement, "implement", "escalated", "plan"],
                          [1, check, "end-check", "raised", None]])

    @contextlib.contextmanager
    def events_lock_held(self):
        """Hold events.lock as a trace call does, so calls started meanwhile queue on it after their first checks."""
        if fcntl is None:
            yield
            return
        with open(str(self.events.with_name("events.lock")), "a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            yield

    def test_of_two_parallel_ends_of_a_unit_one_closes_it(self):
        self.trace("on")
        unit = self.start("design")
        pool = ThreadPoolExecutor(max_workers=2)
        self.addCleanup(pool.shutdown)
        with self.events_lock_held():
            ends = [pool.submit(self.trace, "end", unit, "delivered") for _ in range(2)]
            time.sleep(1)
        outs = sorted(end.result() for end in ends)
        self.assertEqual(outs[0], "trace {} ended\n".format(unit))
        self.assertRegex(outs[1], r"^trace error: ")
        self.assertEqual([line["type"] for line in self.lines()], ["start", "end"])

    def write_start(self, hours_ago, number, conversation=None):
        """Append the start line of a plan unit started `hours_ago`, in the documented format; return its id."""
        when = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=hours_ago)
        unit = when.strftime("%Y%m%dT%H%M%SZ-") + "{:06x}".format(number)
        line = {"v": 1, "type": "start", "id": unit, "kind": "plan", "at": when.astimezone().isoformat(timespec="seconds"),
                "parent": None, "docs": ["P001@r1"], "tier": "L2", "host": "cursor", "conversation": conversation,
                "model": "fixture", "skill": None}
        self.events.parent.mkdir(parents=True, exist_ok=True)
        with self.events.open("a", encoding="utf-8") as events:
            events.write(json.dumps(line, separators=(",", ":")) + "\n")
        return unit

    def test_status_lists_the_open_units_of_the_last_24_hours_newest_first(self):
        self.trace("on")
        self.write_start(25, 1)
        earlier, later = self.write_start(2, 2, conversation="c-1"), self.write_start(1, 3)
        mine = self.start("design", "D001", CURSOR_AGENT="1", CURSOR_CONVERSATION_ID="c-1")
        implement = self.start("implement")
        self.start("slice", "P001", "--slice", "S1", "--parent", implement)
        ended = self.start("plan")
        self.trace("end", ended, "delivered")
        out = self.trace("status", CURSOR_AGENT="1", CURSOR_CONVERSATION_ID="c-1")
        listed = [(line.split()[0], line.endswith(" (this conversation)")) for line in out.splitlines()
                  if line.startswith("  ")]
        self.assertEqual({unit for unit, _mine in listed[:2]}, {mine, implement})
        self.assertEqual([unit for unit, _mine in listed[2:]], [later, earlier])
        self.assertEqual({unit for unit, marked in listed if marked}, {mine, earlier})
        at = next(line["at"] for line in self.lines() if line["id"] == mine)
        self.assertIn("  {} design D001 started {} (this conversation)\n".format(mine, at), out)

    @unittest.skipIf(hasattr(os, "geteuid") and os.geteuid() == 0, "root can write a read-only file")
    def test_an_events_file_that_cannot_be_written_is_a_trace_error(self):
        self.trace("on")
        self.start("design")
        self.events.chmod(0o444)
        self.rejects("start", "design")

    def test_fifty_parallel_starts_append_fifty_lines_that_parse(self):
        self.trace("on")
        with ThreadPoolExecutor(max_workers=50) as pool:
            units = list(pool.map(lambda _: self.start("design"), range(50)))
        self.assertEqual(sorted(line["id"] for line in self.lines()), sorted(units))

    def test_lines_that_do_not_parse_or_carry_another_version_are_skipped(self):
        self.trace("on")
        implement = self.start("implement")
        with self.events.open("ab") as events:
            events.write(b'{"v":1,"type":"end","id":"' + implement.encode() + b'"\n')
            events.write(b"\xff" + implement.encode() + b"\n")
            events.write(json.dumps({"v": 2, "type": "end", "id": implement, "kind": "implement",
                                     "outcome": "delivered"}).encode() + b"\n")
        piece = self.start("slice", "P001", "--slice", "S1", "--parent", implement)
        self.rejects("start", "gate", "--parent", piece)

    def test_a_line_over_16_kib_is_invalid_input(self):
        self.trace("on")
        self.rejects("start", "design", "--model", "m" * (16 * 1024))

    def test_the_trace_directory_stays_out_of_git_without_the_projects_ignore_rule(self):
        (self.root / ".gitignore").write_text("")
        ignore = self.root / ".canon/canon/.gitignore"
        self.trace("off", "--here")
        self.assertNotIn(".canon", self.git("status", "--porcelain", "--untracked-files=all"))
        self.trace("on", "--here")
        self.trace("on")
        for _ in range(2):
            ignore.unlink()
            self.start("design")
            self.assertEqual(ignore.read_text(), "*\n")
        self.assertNotIn(".canon", self.git("status", "--porcelain", "--untracked-files=all"))

    def test_the_trace_directory_is_the_nearest_with_git_else_agents_md_else_the_working_directory(self):
        self.trace("on")
        (self.root / "src/AGENTS.md").write_text("# AGENTS.md\n")
        self.start("design", cwd=self.root / "src")
        self.assertEqual(len(self.lines()), 1)
        outside = tempfile.TemporaryDirectory()
        self.addCleanup(outside.cleanup)
        top = Path(outside.name)
        (top / "a/b").mkdir(parents=True)
        (top / "AGENTS.md").write_text("# AGENTS.md\n")
        self.start("design", cwd=top / "a/b")
        self.assertEqual(len(self.lines(top / ".canon/canon/trace/events.jsonl")), 1)
        (top / "AGENTS.md").unlink()
        self.start("design", cwd=top / "a/b")
        self.assertEqual(len(self.lines(top / "a/b/.canon/canon/trace/events.jsonl")), 1)


if __name__ == "__main__":
    unittest.main()
