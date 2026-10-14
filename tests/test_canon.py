"""Regression tests for skills/governance/canon/scripts/canon.py; scripts/validate.py runs them."""

import importlib.util
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


if __name__ == "__main__":
    unittest.main()
