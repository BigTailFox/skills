"""Regression tests for skills/governance/canon/scripts/canon.py; scripts/validate.py runs them."""

import contextlib
import datetime
import hashlib
import importlib.util
import json
import os
import re
import socket
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
ISSUES = "\n## Known issues\n\n| ID | Severity | Issue | Source | Since | Next |\n|---|---|---|---|---|---|\n{}\n"
UNIT_TIME_FORMAT = "%Y%m%dT%H%M%SZ"


class CanonTest(unittest.TestCase):
    def setUp(self):
        self.root = self.tmpdir()
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.name", "canon test")
        self.git("config", "user.email", "canon@example.invalid")
        self.ok("init", "--no-architecture")
        (self.root / "src").mkdir()
        (self.root / "src/base.py").write_text("value = 1\n")

    def tmpdir(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        return Path(tmp.name)

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

    def issues(self, design, *rows):
        design.write_text(design.read_text() + ISSUES.format("\n".join(rows)))


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

    def test_renumbered_design_rewrites_its_known_issue_ids(self):
        self.issues(self.design(), "| D001-K1 | minor | A gap | P001 gate | 2020-10-01 | fix |")
        self.commit()
        self.ok("renumber", "D001", "D002")
        self.ok("check", "--fix")
        self.assertIn("| D002-K1 |", (self.root / "docs/designs/D002-area.md").read_text())

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

    def test_changing_known_issues_alone_keeps_the_baseline_and_bumping_updated_moves_it(self):
        design = self.design(created="2020-01-01", updated="2020-01-01")
        self.commit()
        self.code_commit("fix: unchecked")
        self.issues(design, "| D001-K1 | minor | A gap | R001-F1 | 2020-10-01 | fix |")
        self.commit(check=False)
        self.assertRegex(self.ok("audit"), r"1 commits since [0-9a-f]+  D001 ")
        self.set(design, updated=canon.today())
        self.commit(check=False)
        self.assertNotIn("commits since", self.ok("audit"))

    def test_a_known_issue_linking_a_design_and_the_removal_of_the_section_keep_the_baseline(self):
        design = self.design()
        self.design("other", paths=["lib/**"])
        self.commit()
        self.code_commit("fix: unchecked")
        self.issues(design, "| D001-K1 | minor | Breaks [D002: Other](D002-other.md) | R001-F1 | 2020-10-01 | fix |")
        self.commit()
        self.assertIn("refs: [D002]", design.read_text())
        self.assertRegex(self.ok("audit"), r"1 commits since [0-9a-f]+  D001 ")
        design.write_text(design.read_text().split("\n## Known issues")[0] + "\n\n")
        self.commit()
        self.assertRegex(self.ok("audit"), r"1 commits since [0-9a-f]+  D001 ")

    def test_idle_docs_skip_concepts(self):
        self.doc("C", "backlog", created="2020-01-01", updated="2020-01-01")
        self.doc("I", "flaky", created="2020-01-01", updated="2020-01-01")
        out = self.ok("audit")
        self.assertIn("I001", out)
        self.assertNotIn("C001", out)


class KnownIssuesTest(CanonTest):
    K1 = "| D001-K1 | major | Retry contradicts the queue limit | P001 gate | 2020-10-01 | decide |"
    K2 = "| D001-K2 | minor | Log lines lack the unit id | code review 3f9a1c2 | 2020-10-02 | fix |"

    def test_check_accepts_well_formed_known_issues_and_reports_each_malformed_row(self):
        design = self.design()
        self.issues(design, self.K1, self.K2)
        self.ok("check", "--fix")
        self.issues(self.design("other"),
                    "| D002-K1 | blocker | No plan can meet the budget | R001-F2 | 2020-10-03 | L2 |",
                    "| D001-K3 | minor | Another design's id | R001-F3 | 2020-10-03 | fix |",
                    "| D002-K2 | critical | Unknown severity | R001-F4 | 2020-10-03 | fix |",
                    "| D002-K3 | minor | No source |  | 2020-10-03 | fix |",
                    "| D002-K4 | minor | Not a date | R001-F5 | 2020-13-03 | fix |",
                    "| D002-K5 | minor | Unknown next step | R001-F6 | 2020-10-03 | later |",
                    "| D002-K1 | minor | Reused id | R001-F7 | 2020-10-03 | L1 |",
                    "| D002-K6 | minor | No next step | R001-F8 | 2020-10-03 |",
                    "| D002-K7 | minor | A trailing cell is ignored | R001-F9 | 2020-10-03 | fix | note |")
        out = self.fails("check", "--fix")
        self.assertNotIn("D001-area.md", out)
        self.assertNotIn("D002-K7", out)
        self.assertEqual(out.count("known issue row must be | D002-K<n> | severity | issue | source | since | next |"),
                         2)
        for problem in ("D002-K2 severity must be one of blocker, major, minor",
                        "D002-K3 needs the issue and its source",
                        "D002-K4 since must be the date it was recorded",
                        "D002-K5 next must be one of decide, fix, L1, L2",
                        "duplicate known issue id D002-K1"):
            self.assertIn(problem, out)

    def test_the_index_and_the_design_listings_count_known_issues(self):
        self.issues(self.design(), self.K1, self.K2)
        self.issues(self.design("other"), "| D002-K1 | minor | A gap | P001 gate | 2020-10-01 | fix |")
        self.ok("check", "--fix")
        index = (self.root / "docs/README.md").read_text()
        self.assertRegex(index, r"\(designs/D001-area\.md\) · active · 2 known issues · Fixture")
        self.assertRegex(index, r"\(designs/D002-other\.md\) · active · 1 known issue · Fixture")
        self.assertIn("D001 docs/designs/D001-area.md - Fixture [2 known issues]", self.ok("which", "src/base.py"))
        self.assertIn(" - Fixture [1 known issue]", self.ok("find", "D002"))
        self.assertIn("D001 active docs/designs/D001-area.md - Fixture [2 known issues]",
                      self.ok("affected", "src/base.py"))

    def test_check_rejects_a_future_date_and_warns_on_a_section_without_issues(self):
        later = datetime.date.today() + datetime.timedelta(days=1)
        self.issues(self.design(), "| D001-K1 | minor | Not yet | R001-F1 | {} | fix |".format(later))
        self.issues(self.design("other"), "")
        out = self.fails("check")
        self.assertIn("D001-K1 since {} is later than today".format(later), out)
        self.assertIn("D002-other.md: `## Known issues` lists no issue; delete the section", out)

    def test_audit_lists_known_issues_oldest_first_with_their_age(self):
        day = datetime.date.today()
        self.issues(self.design(), "| D001-K1 | minor | Newer | P001 gate | {} | fix |".format(
            day - datetime.timedelta(days=3)))
        self.issues(self.design("other"), "| D002-K1 | major | Older | R001-F2 | {} | decide |".format(
            day - datetime.timedelta(days=40)))
        self.assertIn("  D002-K1 major, 40 days, next decide: Older\n  D001-K1 minor, 3 days, next fix: Newer\n",
                      self.ok("audit"))

    def test_a_design_cannot_be_archived_while_it_lists_known_issues(self):
        design = self.design()
        self.issues(design, self.K1)
        self.commit()
        self.assertIn("known issue D001-K1 is still listed", self.fails("archive", "D001", "retired"))
        self.assertEqual(self.git("status", "--porcelain"), "")

    def test_check_reports_an_archived_design_that_lists_known_issues(self):
        self.design()
        self.commit()
        self.ok("archive", "D001", "retired")
        archived = next((self.root / "docs").rglob("D001-area.md"))
        self.issues(archived, self.K1)
        self.assertIn("known issue D001-K1 is still listed", self.fails("check"))


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


class TraceCase(CanonTest):
    HOST_VARS = ("CURSOR_AGENT", "CURSOR_CONVERSATION_ID", "CODEX_THREAD_ID", "CLAUDECODE")

    def setUp(self):
        super().setUp()
        self.config = self.tmpdir()
        self.events = self.root / ".canon/canon/trace/events.jsonl"

    def trace(self, *args, cwd=None, stdin="", returncode=0, **env):
        """Run `canon.py trace` with the machine switch under a temporary XDG_CONFIG_HOME, no host variables but
        those in `env`, and `stdin` as its standard input; assert that it exits with `returncode`."""
        full = {key: value for key, value in os.environ.items() if key not in self.HOST_VARS}
        full.update(XDG_CONFIG_HOME=str(self.config), **env)
        result = subprocess.run([sys.executable, "-B", str(SCRIPT), "trace", *args], cwd=str(cwd or self.root),
                                env=full, input=stdin, capture_output=True, text=True)
        self.assertEqual(result.returncode, returncode, result.stdout + result.stderr)
        return result.stdout

    def files(self):
        return sorted(p for top in (self.root, self.config) for p in top.rglob("*"))

    def start(self, *args, **env):
        out = self.trace("start", *args, **env)
        self.assertRegex(out, r"^trace \d{8}T\d{6}Z-[0-9a-f]{6}\n$")
        return out.split()[1]

    def start_line(self, *args, **env):
        unit = self.start(*args, **env)
        return next(line for line in self.lines() if line.get("id") == unit)

    def lines(self, events=None):
        return [json.loads(line) for line in (events or self.events).read_text(encoding="utf-8").splitlines()]

    def rejects(self, *args, **env):
        """Assert that the call prints a trace error, exits 0 and leaves the events file as it was."""
        before = self.events.read_bytes() if self.events.exists() else None
        self.assertRegex(self.trace(*args, **env), r"^trace error: ")
        self.assertEqual(self.events.read_bytes() if self.events.exists() else None, before, args)

    def unit_id(self, ago, number):
        """The id of a unit started `ago` before now, in the documented format."""
        started = datetime.datetime.now(datetime.timezone.utc) - ago
        return started.strftime(UNIT_TIME_FORMAT) + "-{:06x}".format(number)

    def started(self, unit):
        """The UTC start time that the id of `unit` begins with."""
        return datetime.datetime.strptime(unit[:16], UNIT_TIME_FORMAT).replace(tzinfo=datetime.timezone.utc)

    def snap(self, *args):
        """Run git in the snapshot repository, as `git -C .canon/canon/trace`; return its stripped output."""
        return self.git("-C", ".canon/canon/trace", *args)

    def snapshot_objects(self):
        return set(self.snap("cat-file", "--batch-all-objects", "--batch-check=%(objectname)").split())

    @contextlib.contextmanager
    def lock_held(self, name):
        """Hold the trace directory's lock `name` as a trace call does, so calls started meanwhile wait on it."""
        if fcntl is None:
            yield
            return
        with open(str(self.events.with_name(name)), "a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            yield


class TraceTest(TraceCase):
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
        self.assertEqual(set(line), {"v", "type", "id", "kind", "at", "parent", "docs", "tier", "base", "head",
                                     "snapshot", "skipped", "host", "conversation", "model", "skill", "manifest"})
        self.assertEqual([line[k] for k in ("v", "type", "id", "kind", "parent", "tier", "model", "skill", "manifest")],
                         [1, "start", unit, "design", None, None, None, None, None])
        self.assertEqual(line["docs"], ["D001@r3", "D002@r1", "D003@r1", "D999"])
        self.assertRegex(line["at"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d[+-]\d\d:\d\d$")
        at = datetime.datetime.fromisoformat(line["at"])
        self.assertEqual(at.utcoffset(), at.astimezone().utcoffset())
        self.assertEqual(at, self.started(unit))

    def test_a_doc_argument_not_shaped_like_a_doc_id_is_invalid_input(self):
        self.assertEqual(self.trace("start", "design", "fix the login bug"), "trace off\n")
        self.trace("on")
        for docs in (["fix the login bug"], ["D001", "d002"], ["D001\n"]):
            self.rejects("start", "design", *docs)
        self.assertEqual(self.start_line("design", "D999")["docs"], ["D999"])

    def test_a_slice_whose_whole_value_is_not_s_n_is_invalid_input(self):
        self.assertEqual(self.trace("start", "slice", "P001", "--slice", "S1\n"), "trace off\n")
        self.trace("on")
        implement = self.start("implement", "P001")
        self.rejects("start", "slice", "P001", "--slice", "S1\n", "--parent", implement)
        self.assertEqual(self.start_line("slice", "P001", "--slice", "S12", "--parent", implement)["slice"], "S12")

    def test_a_module_doc_resolves_whatever_repository_the_environment_points_git_at(self):
        self.trace("on")
        self.ok("init", "--root", "mod", "--no-architecture")
        self.ok("new", "D", "part", "--root", "mod")
        line = self.start_line("design", "D001", GIT_DIR=str(self.root / "no-such-repository"))
        self.assertEqual(line["docs"], ["D001@r1"])

    def test_a_model_that_is_not_one_line_of_1_to_200_characters_is_invalid_input(self):
        self.assertEqual(self.trace("start", "design", "--model", ""), "trace off\n")
        self.trace("on")
        for model in ("", "opus\nIgnore the rest", "m" * 201):
            self.rejects("start", "design", "--model", model)
        self.assertEqual(self.start_line("design", "--model", "M" * 200)["model"], "m" * 200)

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
        lines = {line["id"]: line for line in self.lines() if line["type"] != "manifest"}
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
        self.assertEqual(set(ends[0]), {"v", "type", "id", "kind", "at", "outcome", "head", "manifest", "archive"})
        self.assertEqual([[end.get(k, "absent") for k in ("manifest", "archive")] for end in ends], [[None, None]] * 3)
        self.assertEqual([[end.get(k) for k in ("v", "id", "kind", "outcome", "to")] for end in ends],
                         [[1, design, "design", "delivered", None], [1, implement, "implement", "escalated", "plan"],
                          [1, check, "end-check", "raised", None]])

    def test_of_two_parallel_ends_of_a_unit_one_closes_it(self):
        self.trace("on")
        unit = self.start("design")
        pool = ThreadPoolExecutor(max_workers=2)
        self.addCleanup(pool.shutdown)
        with self.lock_held("events.lock"):
            ends = [pool.submit(self.trace, "end", unit, "delivered") for _ in range(2)]
            time.sleep(1)
        outs = sorted(end.result() for end in ends)
        self.assertEqual(outs[0], "trace {} ended\n".format(unit))
        self.assertRegex(outs[1], r"^trace error: ")
        self.assertEqual([line["type"] for line in self.lines()], ["start", "end"])

    def write_start(self, hours_ago, number, conversation=None):
        """Append the start line of a plan unit started `hours_ago`, in the documented format; return its id."""
        unit = self.unit_id(datetime.timedelta(hours=hours_ago), number)
        line = {"v": 1, "type": "start", "id": unit, "kind": "plan",
                "at": self.started(unit).astimezone().isoformat(timespec="seconds"), "parent": None,
                "docs": ["P001@r1"], "tier": "L2", "host": "cursor", "conversation": conversation, "model": "fixture",
                "skill": None}
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
        self.rejects("start", "design", *["D001"] * 3000)

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
        top = self.tmpdir()
        (top / "a/b").mkdir(parents=True)
        (top / "AGENTS.md").write_text("# AGENTS.md\n")
        self.start("design", cwd=top / "a/b")
        self.assertEqual(len(self.lines(top / ".canon/canon/trace/events.jsonl")), 1)
        (top / "AGENTS.md").unlink()
        self.start("design", cwd=top / "a/b")
        self.assertEqual(len(self.lines(top / "a/b/.canon/canon/trace/events.jsonl")), 1)


class SnapshotTest(TraceCase):
    def setUp(self):
        super().setUp()
        self.trace("on")

    def project_state(self):
        """The project's work tree outside .canon/, HEAD, refs, the files under its object directory, and its index."""
        def files(top, skip=()):
            return {p.relative_to(top).as_posix(): p.read_bytes() for p in top.rglob("*")
                    if p.is_file() and p.relative_to(top).parts[0] not in skip}
        git_dir = self.root / ".git"
        return {"work tree": files(self.root, (".git", ".canon")), "HEAD": (git_dir / "HEAD").read_bytes(),
                "refs": self.git("for-each-ref", "--format=%(refname) %(objectname)"),
                "objects": files(git_dir / "objects"), "index": (git_dir / "index").read_bytes()}

    def stored_once(self):
        """Whether the snapshot repository stores each of its objects once, loose or in a single pack."""
        counts = dict(line.split(": ") for line in self.snap("count-objects", "-v").splitlines())
        return int(counts["count"]) + int(counts["in-pack"]) == len(self.snapshot_objects())

    def test_a_clean_checkouts_snapshot_and_its_parent_have_heads_tree_and_end_records_a_later_head(self):
        self.commit()
        head, tree = self.git("rev-parse", "HEAD"), self.git("rev-parse", "HEAD^{tree}")
        line = self.start_line("implement")
        self.assertEqual([line[k] for k in ("base", "head", "skipped")], [None, head, None])
        self.assertEqual(self.snap("rev-parse", "refs/trace/" + line["id"]), line["snapshot"])
        self.assertEqual([self.snap("rev-parse", line["snapshot"] + rev) for rev in ("^{tree}", "^^{tree}")],
                         [tree, tree])
        self.assertEqual(self.snap("rev-list", "--count", line["snapshot"]), "2")
        (self.root / "src/base.py").write_text("value = 2\n")
        self.git("commit", "-qam", "during the unit")
        self.trace("end", line["id"], "delivered")
        self.assertEqual(self.lines()[-1]["head"], self.git("rev-parse", "HEAD"))

    def test_a_dirty_checkouts_snapshot_holds_what_a_commit_would_and_leaves_the_project_unchanged(self):
        origin = self.tmpdir()
        (origin / "lib.txt").write_text("lib 1\n")
        identity = ["-c", "user.name=fixture", "-c", "user.email=fixture@example.invalid"]
        for args in (["init", "-q"], ["add", "-A"], [*identity, "commit", "-qm", "lib"]):
            subprocess.run(["git", *args], cwd=str(origin), check=True, capture_output=True)
        self.git("-c", "protocol.file.allow=always", "submodule", "add", "-q", str(origin), "sub")
        with (self.root / ".gitignore").open("a") as ignore:
            ignore.write("*.log\n")
        (self.root / ".git/info").mkdir(exist_ok=True)
        (self.root / ".git/info/exclude").write_text("*.tmp\n")
        excludes = self.tmpdir() / "excludes"
        excludes.write_text("*.secret\n")
        self.git("config", "core.excludesFile", str(excludes))
        for name in ("staged.txt", "unstaged.txt", "touched.txt"):
            (self.root / name).write_text("v1\n")
        self.commit()
        (self.root / "staged.txt").write_text("v2 staged\n")
        self.git("add", "staged.txt")
        (self.root / "unstaged.txt").write_text("v2 unstaged\n")
        (self.root / "untracked.txt").write_text("new\n")
        for name in ("build.log", "scratch.tmp", "key.secret"):
            (self.root / name).write_text("ignored\n")
        (self.root / "sub/lib.txt").write_text("lib 2\n")
        self.git("-C", "sub", *identity, "commit", "-qam", "lib 2")
        (self.root / "sub/lib.txt").write_text("lib 3, not committed\n")
        touched = self.root / "touched.txt"
        os.utime(str(touched), ns=(touched.stat().st_atime_ns, touched.stat().st_mtime_ns - 10 ** 10))
        before = self.project_state()
        snapshot = self.start_line("implement")["snapshot"]
        after = self.project_state()
        self.assertEqual([part for part in before if after[part] != before[part]], [])
        files = set(self.snap("ls-tree", "-r", "--name-only", snapshot).splitlines())
        self.assertEqual(files & {"build.log", "scratch.tmp", "key.secret"}, set())
        self.assertEqual({name: self.snap("show", "{}:{}".format(snapshot, name)) for name in
                          ("staged.txt", "unstaged.txt", "untracked.txt", "touched.txt")},
                         {"staged.txt": "v2 staged", "unstaged.txt": "v2 unstaged", "untracked.txt": "new",
                          "touched.txt": "v1"})
        self.assertEqual(self.snap("ls-tree", snapshot, "sub").split()[:3],
                         ["160000", "commit", self.git("-C", "sub", "rev-parse", "HEAD")])

    def test_on_an_unborn_branch_without_an_index_the_snapshot_has_no_parent_and_head_is_null(self):
        self.assertFalse((self.root / ".git/index").exists())
        line = self.start_line("design")
        self.assertEqual([line[k] for k in ("base", "head", "skipped")], [None, None, None])
        self.assertEqual(self.snap("rev-list", "--parents", "-n", "1", line["snapshot"]), line["snapshot"])
        self.assertIn("src/base.py", self.snap("ls-tree", "-r", "--name-only", line["snapshot"]).splitlines())
        self.assertFalse((self.root / ".git/index").exists())

    def test_a_failed_step_records_its_reason_and_gits_message_and_status_counts_each_skip(self):
        self.commit()
        copies = self.root / ".canon/canon/trace/.git"
        self.start_line("design")
        self.assertEqual(list(copies.glob("index-*")), [])
        self.assertRegex(self.trace("status"), r"(?m)^snapshots: 1, [\d.]+ [KMG]iB on disk\nskipped starts: none$")
        index = self.root / ".git/index"
        good = index.read_bytes()
        index.write_bytes(b"XXXX" + good[4:])
        line = self.start_line("design", LC_ALL="C")
        self.assertEqual([line["snapshot"], line["skipped"]], [None, "git status: exit 128"])
        error = self.root / ".canon/canon/trace" / line["id"] / "snapshot-error.txt"
        self.assertIn("index file corrupt", error.read_text())
        index.write_bytes(good)
        with (self.root / ".gitattributes").open("a") as attributes:
            attributes.write("*.dat filter=noisy\n")
        noise = "import sys; sys.stderr.write('x' * 100000); sys.exit(3)"
        self.git("config", "filter.noisy.clean", "\"{}\" -c \"{}\"".format(sys.executable, noise))
        self.git("config", "filter.noisy.required", "true")
        (self.root / "data.dat").write_text("data\n")
        line = self.start_line("design", LC_ALL="C")
        self.assertEqual([line["snapshot"], line["skipped"]], [None, "git add: exit 128"])
        message = (self.root / ".canon/canon/trace" / line["id"] / "snapshot-error.txt").read_bytes()
        self.assertEqual(len(message), 64 * 1024)
        self.assertEqual(message[:3], b"xxx")
        self.assertTrue(message.endswith(b"\nfatal: data.dat: clean filter 'noisy' failed\n"), message[-100:])
        self.assertEqual(list(copies.glob("index-*")), [])
        skips = re.search(r"(?m)^skipped starts: (.*)$", self.trace("status")).group(1)
        self.assertEqual(sorted(skips.split("; ")), ["1 git add: exit 128", "1 git status: exit 128"])

    def test_base_is_the_merge_base_and_the_snapshot_diff_is_the_change_under_review(self):
        (self.root / "shared.txt").write_text("1\n")
        self.commit()
        fork = self.git("rev-parse", "HEAD")
        self.git("checkout", "-qb", "topic")
        (self.root / "topic.txt").write_text("topic\n")
        self.git("add", "topic.txt")
        self.git("commit", "-qm", "topic")
        self.git("checkout", "-q", "main")
        (self.root / "shared.txt").write_text("2\n")
        self.git("commit", "-qam", "main moves on")
        self.git("checkout", "-q", "topic")
        (self.root / "topic.txt").write_text("topic, edited\n")
        (self.root / "fresh.txt").write_text("fresh\n")
        line = self.start_line("code-review", "--base", "main")
        self.assertEqual(line["base"], fork)
        snapshot = line["snapshot"]
        self.assertEqual(self.snap("diff", "--full-index", snapshot + "^", snapshot, "--", ".", ":(exclude)fresh.txt"),
                         self.git("diff", "--full-index", fork))
        self.assertEqual(self.snap("diff", "--name-status", snapshot + "^", snapshot, "--", "fresh.txt"),
                         "A\tfresh.txt")
        unrelated = self.git("commit-tree", "-m", "unrelated", fork + "^{tree}")
        line = self.start_line("code-review", "--base", unrelated)
        self.assertIsNone(line["base"])
        self.assertEqual(self.snap("rev-parse", line["snapshot"] + "^^{tree}"), self.git("rev-parse", "HEAD^{tree}"))
        for ref in ("no-such-ref", "--git-dir=x"):
            self.rejects("start", "code-review", "--base=" + ref)

    def test_a_snapshot_adds_only_the_objects_its_repository_lacks(self):
        (self.root / "src/deep").mkdir()
        for name in ("src/deep/one.txt", "src/deep/two.txt", "src/three.txt"):
            (self.root / name).write_text(name + "\n")
        self.commit()
        self.start("implement")
        before = self.snapshot_objects()
        (self.root / "src/deep/one.txt").write_text("changed\n")
        snapshot = self.start_line("implement")["snapshot"]
        added = self.snapshot_objects() - before
        self.assertIn(snapshot, added)
        self.assertEqual(added - {snapshot, self.snap("rev-parse", snapshot + "^")},
                         {self.snap("rev-parse", snapshot + suffix) for suffix in
                          (":src/deep/one.txt", ":src/deep", ":src", "^{tree}")})
        self.git("checkout", "-q", "src/deep/one.txt")
        self.git("checkout", "-qb", "topic")
        for name in ("src/deep/two.txt", "src/three.txt"):
            (self.root / name).write_text("topic\n")
        self.git("commit", "-qam", "topic")
        self.start("implement")
        self.git("checkout", "-q", "main")
        before = self.snapshot_objects()
        snapshot = self.start_line("implement")["snapshot"]
        self.assertEqual(self.snapshot_objects() - before - {snapshot, self.snap("rev-parse", snapshot + "^")}, set())
        self.assertTrue(self.stored_once())

    def test_no_push_clone_or_bundle_of_the_project_carries_a_snapshot(self):
        self.commit()
        snapshot = self.start_line("implement")["snapshot"]
        copies = self.tmpdir()
        self.git("init", "-q", "--bare", str(copies / "pushed.git"))
        self.git("push", "-q", "--mirror", str(copies / "pushed.git"))
        self.git("clone", "-q", "--mirror", str(self.root), str(copies / "cloned.git"))
        self.git("bundle", "create", str(copies / "all.bundle"), "--all")
        self.assertNotIn("refs/trace/", self.git("bundle", "list-heads", str(copies / "all.bundle")))
        self.git("init", "-q", "--bare", str(copies / "unbundled.git"))
        self.git("-C", str(copies / "unbundled.git"), "bundle", "unbundle", str(copies / "all.bundle"))
        for repo in (self.root, copies / "pushed.git", copies / "cloned.git", copies / "unbundled.git"):
            self.assertNotIn("refs/trace/", self.git("-C", str(repo), "for-each-ref"))
            self.assertNotEqual(self.run_here("git", "-C", str(repo), "cat-file", "-e", snapshot).returncode, 0, repo)

    def test_snapshots_survive_a_reset_reflog_expiry_and_gc_in_the_project(self):
        self.commit()
        start = self.git("rev-parse", "HEAD")
        (self.root / "gone.txt").write_text("only in a dropped commit\n")
        self.git("add", "gone.txt")
        self.git("commit", "-qm", "dropped later")
        dropped = self.git("rev-parse", "HEAD:gone.txt")
        self.start("implement")
        (self.root / "src/base.py").write_text("value = 3\n")
        self.git("add", "src/base.py")
        self.start("implement")
        self.git("reset", "-q", "--hard", start)
        self.git("reflog", "expire", "--expire=now", "--all")
        self.git("gc", "-q", "--prune=now")
        self.assertNotEqual(self.run_here("git", "cat-file", "-e", dropped).returncode, 0)
        self.snap("fsck", "--strict")
        refs = self.snap("for-each-ref", "--format=%(refname)", "refs/trace/").splitlines()
        self.assertEqual(len(refs), 2)
        for ref in refs:
            self.snap("ls-tree", "-r", ref)
        self.assertEqual(self.snap("cat-file", "blob", dropped), "only in a dropped commit")

    def test_without_any_ignore_rule_git_neither_adds_nor_cleans_the_trace_directory(self):
        (self.root / ".gitignore").write_text("")
        self.commit()
        self.start("implement")
        (self.root / ".canon/canon/.gitignore").unlink()
        self.git("clean", "-qfdx")
        self.assertTrue((self.root / ".canon/canon/trace/events.jsonl").is_file())
        self.git("add", "-A")
        self.assertIn(self.git("ls-files", "-s", ".canon"),
                      ["", "160000 {} 0\t.canon/canon/trace".format(self.snap("rev-parse", "HEAD"))])
        self.git("status")

    def test_a_failed_creation_of_the_snapshot_repository_leaves_nothing_behind(self):
        trace = self.root / ".canon/canon/trace"
        trace.mkdir(parents=True)
        (trace / ".git").write_text("not a repository\n")
        line = self.start_line("design")
        self.assertRegex(line["skipped"], r"^git init: E[A-Z]+$")
        self.assertEqual([path.name for path in trace.iterdir() if path.name.startswith(".init-")], [])

    def test_snapshots_need_no_git_identity_and_their_commits_carry_canon_trace(self):
        self.commit()
        self.git("config", "--unset", "user.name")
        self.git("config", "--unset", "user.email")
        empty = self.tmpdir() / "gitconfig"
        empty.write_text("")
        snapshot = self.start_line("implement", GIT_CONFIG_GLOBAL=str(empty), GIT_CONFIG_NOSYSTEM="1")["snapshot"]
        self.assertIsNotNone(snapshot)
        self.assertEqual(self.snap("log", "--format=%an <%ae>, %cn <%ce>", snapshot).splitlines(),
                         ["canon-trace <trace@canon.invalid>, canon-trace <trace@canon.invalid>"] * 2)

    def test_ten_parallel_first_starts_each_record_a_snapshot(self):
        self.commit()
        with ThreadPoolExecutor(max_workers=10) as pool:
            units = list(pool.map(lambda _: self.start("implement"), range(10)))
        lines = {line["id"]: line for line in self.lines()}
        self.assertEqual([lines[unit]["skipped"] for unit in units], [None] * 10)
        self.assertEqual(sorted(self.snap("for-each-ref", "--format=%(refname:lstrip=2) %(objectname)",
                                          "refs/trace/").splitlines()),
                         sorted("{} {}".format(unit, lines[unit]["snapshot"]) for unit in units))
        self.snap("fsck", "--strict")

    @unittest.skipIf(fcntl is None, "the test holds snapshot.lock with flock")
    def test_a_start_that_cannot_take_snapshot_lock_skips_its_snapshot_and_stores_no_skills(self):
        self.commit()
        self.start("design")
        skill = self.tmpdir() / "canon-x"
        skill.mkdir()
        (skill / "SKILL.md").write_text("canon-x\n")
        with self.lock_held("snapshot.lock"):
            line = self.start_line("design", "--skill", str(skill))
        self.assertEqual([line["snapshot"], line["skipped"]], [None, "snapshot lock: timeout"])
        self.assertIsNotNone(line["manifest"])
        self.assertEqual(self.snap("for-each-ref", "refs/skills/"), "")

    def committed_project(self, object_format):
        """A project of its own with one commit, made with `git init --object-format=<object_format>`; None when this
        Git cannot make it."""
        project = self.tmpdir()
        if self.run_here("git", "init", "-q", "--object-format=" + object_format, str(project)).returncode:
            return None
        (project / "a.txt").write_text("a\n")
        self.git("-C", str(project), "add", "-A")
        self.git("-C", str(project), "-c", "user.name=fixture", "-c", "user.email=f@example.invalid",
                 "commit", "-qm", "a")
        return project

    def test_a_sha256_project_gets_snapshots(self):
        project = self.committed_project("sha256")
        if project is None:
            self.skipTest("this Git cannot create a SHA-256 repository")
        self.start("implement", cwd=project)
        [line] = self.lines(project / ".canon/canon/trace/events.jsonl")
        self.assertRegex(line["snapshot"] or line["skipped"], r"^[0-9a-f]{64}$")
        snap = str(project / ".canon/canon/trace")
        self.assertEqual(self.git("-C", snap, "rev-parse", line["snapshot"] + "^{tree}"),
                         self.git("-C", str(project), "rev-parse", "HEAD^{tree}"))
        self.git("-C", snap, "fsck", "--strict")

    def test_a_sha1_project_gets_snapshots_when_sha256_is_the_default_object_format(self):
        if self.committed_project("sha256") is None:
            self.skipTest("this Git cannot create a SHA-256 repository")
        config = self.tmpdir() / "gitconfig"
        config.write_text("[init]\n\tdefaultObjectFormat = sha256\n")
        for env in ({"GIT_CONFIG_GLOBAL": str(config)}, {"GIT_DEFAULT_HASH": "sha256"}):
            project = self.committed_project("sha1")
            self.start("implement", cwd=project, **env)
            [line] = self.lines(project / ".canon/canon/trace/events.jsonl")
            self.assertRegex(line["snapshot"] or line["skipped"], r"^[0-9a-f]{40}$", env)
            snap = str(project / ".canon/canon/trace")
            self.assertEqual(self.git("-C", snap, "rev-parse", "--show-object-format"), "sha1")

    def test_a_directory_outside_git_records_no_git_with_null_head_and_base(self):
        outside = self.tmpdir()
        (outside / "AGENTS.md").write_text("# AGENTS.md\n")
        self.start("code-review", "--base", "main", cwd=outside)
        [line] = self.lines(outside / ".canon/canon/trace/events.jsonl")
        self.assertEqual([line[k] for k in ("base", "head", "snapshot", "skipped")], [None, None, None, "no-git"])
        self.assertRegex(self.trace("status", cwd=outside), r"(?m)^skipped starts: 1 no-git$")

    def test_untracked_and_unstaged_files_over_10_mib_skip_the_snapshot(self):
        big = self.root / "big.bin"
        big.write_bytes(b"\0" * (5 << 20))
        self.commit()
        big.write_bytes(b"\1" * (5 << 20))
        self.git("add", "big.bin")
        (self.root / "new.bin").write_bytes(b"\0" * (6 << 20))
        self.assertIsNotNone(self.start_line("design")["snapshot"])
        big.write_bytes(b"\2" * (5 << 20))
        line = self.start_line("design")
        self.assertEqual([line["snapshot"], line["skipped"]], [None, "changes-over-10MiB"])


class DispositionsTest(TraceCase):
    GATE = {"reviewers": [{"role": "same-model", "model": "claude-opus-5.5", "id": "a3f0c2e1"},
                          {"role": "cross-family", "model": "manual:gpt-6-astra", "id": None}],
            "findings": [{"by": ["same-model:F1", "cross-family:F2"], "severity": "major", "disposition": "accepted",
                          "confirmed": "resolved"},
                         {"by": ["cross-family:F1"], "severity": "blocker", "disposition": "escalated"},
                         {"by": ["same-model:F2"], "severity": "minor", "disposition": "declined"},
                         {"by": ["same-model:F3"], "severity": "major", "disposition": "deferred"}],
            "new_blockers": 0}
    CODE_REVIEW = {"reviewers": [{"role": "spec", "model": "claude-opus-5.5", "id": "b71e09d2"},
                                 {"role": "standards", "model": "claude-opus-5.5", "id": "c03d5a7f"},
                                 {"role": "cross-family", "model": "gpt-6-astra", "id": "/root/p007_review"}],
                   "findings": [{"by": ["spec:F1"], "severity": "major", "disposition": "accepted", "axis": "spec",
                                 "confirmed": "not-resolved"},
                                {"by": ["standards:F1", "cross-family:F3"], "severity": "minor",
                                 "disposition": "deferred", "axis": "standards"}],
                   "new_blockers": 1}

    def setUp(self):
        super().setUp()
        self.trace("on")

    def end_line(self, unit):
        return next(line for line in self.lines() if line["id"] == unit and line["type"] == "end")

    def test_valid_dispositions_appear_in_the_end_line_unchanged(self):
        gate, review, bare = self.start("gate", "D001"), self.start("code-review"), self.start("gate", "D001")
        self.trace("end", gate, "delivered", "--input", "-", stdin=json.dumps(self.GATE))
        path = self.config / "dispositions.json"
        path.write_text(json.dumps(self.CODE_REVIEW))
        self.trace("end", review, "delivered", "--input", str(path))
        self.trace("end", bare, "blocked")
        raw = self.events.read_text(encoding="utf-8")
        for unit, dispositions in ((gate, self.GATE), (review, self.CODE_REVIEW)):
            self.assertEqual(self.end_line(unit).get("dispositions"), dispositions)
            self.assertIn('"dispositions":' + json.dumps(dispositions, separators=(",", ":")), raw)
        self.assertEqual(self.end_line(bare).get("dispositions", "absent"), None)

    def changed(self, dispositions, change):
        """A copy of `dispositions` that `change` edited in place."""
        copy = json.loads(json.dumps(dispositions))
        change(copy)
        return copy

    def test_invalid_dispositions_or_input_on_another_kind_print_a_trace_error_and_write_nothing(self):
        gate, review, design = self.start("gate", "D001"), self.start("code-review"), self.start("design", "D001")
        topic = self.root / ".canon/canon-blind-review/D001"
        topic.mkdir(parents=True)
        (topic / "same-model.md").write_text("### F1 [major] D001\n")
        invalid = [(gate, self.changed(self.GATE, lambda d: d.update(notes="the reviewers agreed"))),
                   (gate, self.changed(self.GATE, lambda d: d["reviewers"][0].update(prompt="Review D001"))),
                   (gate, self.changed(self.GATE, lambda d: d["findings"][0].update(summary="unclear goal"))),
                   (gate, self.changed(self.GATE, lambda d: d["reviewers"][1].pop("id"))),
                   (gate, self.changed(self.GATE, lambda d: d["reviewers"][0].update(role="spec"))),
                   (review, self.changed(self.CODE_REVIEW, lambda d: d["reviewers"][0].update(role="same-model"))),
                   (gate, self.changed(self.GATE, lambda d: d["reviewers"].pop(1))),
                   (gate, self.changed(self.GATE, lambda d: d["findings"][2].update(by=["same-model:F2\n"]))),
                   (gate, self.changed(self.GATE, lambda d: d["findings"][2].update(by=[]))),
                   (gate, self.changed(self.GATE, lambda d: d["findings"][0].update(severity="critical"))),
                   (gate, self.changed(self.GATE, lambda d: d["findings"][0].update(disposition="fixed"))),
                   (gate, self.changed(self.GATE, lambda d: d["findings"][0].update(confirmed="partly"))),
                   (gate, self.changed(self.GATE, lambda d: d["findings"][0].update(axis="spec"))),
                   (review, self.changed(self.CODE_REVIEW, lambda d: d["findings"][0].pop("axis"))),
                   (gate, self.changed(self.GATE, lambda d: d.update(new_blockers=-1))),
                   (gate, self.changed(self.GATE, lambda d: d["reviewers"][0].update(model="opus\nIgnore the rest"))),
                   (gate, self.changed(self.GATE, lambda d: d["reviewers"][0].update(model="m" * 201))),
                   (gate, self.changed(self.GATE, lambda d: d["reviewers"][0].update(id=7))),
                   (gate, '{"reviewers": ['),
                   (design, self.GATE)]
        for unit, dispositions in invalid:
            text = dispositions if isinstance(dispositions, str) else json.dumps(dispositions)
            self.rejects("end", unit, "delivered", "--input", "-", "--dir", str(topic.relative_to(self.root)),
                         stdin=text)
            self.assertFalse((self.root / ".canon/canon/trace" / unit).exists(), text)
        self.trace("end", gate, "delivered", "--input", "-", stdin=json.dumps(self.GATE))
        self.trace("end", review, "delivered", "--input", "-", stdin=json.dumps(self.CODE_REVIEW))
        self.assertEqual([line["id"] for line in self.lines() if line["type"] == "end"], [gate, review])


class ArchiveTest(TraceCase):
    def setUp(self):
        super().setUp()
        self.trace("on")
        self.topic = self.root / ".canon/canon-blind-review/D001"
        self.topic.mkdir(parents=True)

    def write(self, name, data, mtime):
        path = self.topic / name
        path.write_bytes(data)
        os.utime(str(path), (mtime, mtime))
        return path

    def end(self, unit, path=".canon/canon-blind-review/D001"):
        """End `unit` with `--dir path`; return its end line's archive and the files archived with it."""
        self.trace("end", unit, "delivered", "--dir", path)
        line = self.lines()[-1]
        archive = self.root / ".canon/canon/trace" / unit
        return line.get("archive", "absent"), {p.name: p.read_bytes() for p in archive.glob("*")}

    @unittest.skipIf(os.name == "nt", "symlinks need privileges on Windows")
    def test_dir_archives_the_regular_files_directly_in_it_that_changed_since_the_unit_started(self):
        unit = self.start("gate", "D001")
        started = self.started(unit).timestamp()
        self.write("earlier.md", b"an earlier review\n", started - 1)
        self.write("same-model-prompt.md", b"You are reviewing\n", started)
        self.write("same-model.md", b"### F1 [major] D001\n", started + 5)
        (self.topic / "previous").mkdir()
        self.write("previous/same-model.md", b"an earlier round\n", started + 5)
        os.utime(str(self.root / "src/base.py"), (started + 5, started + 5))
        (self.topic / "link.md").symlink_to("same-model.md")
        (self.topic / "outside.md").symlink_to(self.root / "src/base.py")
        self.assertEqual(self.end(unit), ("ok", {"same-model-prompt.md": b"You are reviewing\n",
                                                 "same-model.md": b"### F1 [major] D001\n"}))

    def test_changed_files_over_2_mib_in_total_copy_nothing_and_give_over_2mib(self):
        unit = self.start("gate", "D001")
        started = self.started(unit).timestamp()
        self.write("earlier.bin", b"e" * (3 << 20), started - 1)
        halves = {"a.bin": b"a" * (1 << 20), "b.bin": b"b" * (1 << 20)}
        for name, data in halves.items():
            self.write(name, data, started)
        self.assertEqual(self.end(unit), ("ok", halves))
        unit = self.start("gate", "D001")
        started = self.started(unit).timestamp()
        for name, data in dict(halves, **{"c.bin": b"c"}).items():
            self.write(name, data, started)
        self.assertEqual(self.end(unit), ("over-2MiB", {}))

    @unittest.skipIf(os.name == "nt" or (hasattr(os, "geteuid") and os.geteuid() == 0),
                     "Windows has no unreadable mode, and root reads any file")
    def test_an_unreadable_file_gives_copy_eacces_and_no_path(self):
        unit = self.start("gate", "D001")
        started = self.started(unit).timestamp()
        self.write("cross-family.md", b"### F1 [minor] D001\n", started)
        self.write("same-model.md", b"### F1 [major] D001\n", started).chmod(0)
        self.assertEqual(self.end(unit), ("copy: EACCES", {}))
        line = self.events.read_text(encoding="utf-8").splitlines()[-1]
        self.assertNotIn("same-model", line)
        self.assertNotIn("canon-blind-review", line)

    def test_a_copy_that_fails_while_writing_leaves_no_file_archived(self):
        unit = self.start("gate", "D001")
        started = self.started(unit).timestamp()
        self.write("cross-family.md", b"### F1 [minor] D001\n", started)
        self.write("same-model.md", b"### F1 [major] D001\n", started)
        archive = self.root / ".canon/canon/trace" / unit
        (archive / "same-model.md").mkdir(parents=True)
        self.trace("end", unit, "delivered", "--dir", ".canon/canon-blind-review/D001")
        self.assertRegex(self.lines()[-1]["archive"], r"^copy: E[A-Z]+$")
        self.assertEqual(sorted(path.name for path in archive.iterdir()), ["same-model.md"])

    def test_no_changed_file_gives_none_and_a_missing_dir_names_the_failed_copy(self):
        unit = self.start("gate", "D001")
        self.write("earlier.md", b"an earlier review\n", self.started(unit).timestamp() - 1)
        (self.topic / "previous").mkdir()
        self.assertEqual(self.end(unit), ("none", {}))
        unit = self.start("gate", "D001")
        self.assertEqual(self.end(unit, ".canon/canon-blind-review/D999"), ("copy: ENOENT", {}))

    @unittest.skipIf(os.name == "nt", "symlinks need privileges on Windows")
    def test_a_dir_outside_canon_directly_or_through_a_symlink_is_a_trace_error(self):
        unit = self.start("gate", "D001")
        started = self.started(unit).timestamp()
        os.utime(str(self.root / "src/base.py"), (started, started))
        (self.root / ".canon/escape").symlink_to(self.root / "src")
        (self.root / ".canon/up").symlink_to("..")
        for path in ("src", str(self.root / "src"), ".canon/../src", ".canon/escape", ".canon/up/src"):
            self.rejects("end", unit, "delivered", "--dir", path)
        self.assertFalse((self.root / ".canon/canon/trace" / unit).exists())
        self.assertEqual(self.end(unit), ("none", {}))

    def test_a_relative_dir_is_taken_from_the_checkout_and_a_relative_input_from_the_working_directory(self):
        unit = self.start("gate", "D001")
        self.write("same-model.md", b"### F1 [major] D001\n", self.started(unit).timestamp())
        dispositions = {"reviewers": [], "findings": [], "new_blockers": 0}
        (self.root / "src/dispositions.json").write_text(json.dumps(dispositions))
        out = self.trace("end", unit, "delivered", "--dir", ".canon/canon-blind-review/D001",
                         "--input", "dispositions.json", cwd=self.root / "src")
        self.assertEqual(out, "trace {} ended\n".format(unit))
        line = self.lines()[-1]
        self.assertEqual([line["archive"], line["dispositions"]], ["ok", dispositions])
        self.assertEqual([path.name for path in (self.root / ".canon/canon/trace" / unit).iterdir()],
                         ["same-model.md"])

    def test_of_two_parallel_ends_of_a_unit_only_the_one_that_closes_it_archives_its_files(self):
        unit = self.start("gate", "D001")
        started = self.started(unit).timestamp()
        self.write("same-model.md", b"### F1 [major] D001\n", started)
        other = self.root / ".canon/canon-blind-review/D002/cross-family.md"
        other.parent.mkdir()
        other.write_bytes(b"### F1 [minor] D002\n")
        os.utime(str(other), (started, started))
        names = {".canon/canon-blind-review/D001": ["same-model.md"],
                 ".canon/canon-blind-review/D002": ["cross-family.md"]}
        pool = ThreadPoolExecutor(max_workers=2)
        self.addCleanup(pool.shutdown)
        with self.lock_held("events.lock"):
            ends = {path: pool.submit(self.trace, "end", unit, "delivered", "--dir", path) for path in names}
            time.sleep(1)
        outs = {path: end.result() for path, end in ends.items()}
        [closed] = [path for path, out in outs.items() if out == "trace {} ended\n".format(unit)]
        [rejected] = [out for path, out in outs.items() if path != closed]
        self.assertRegex(rejected, r"^trace error: ")
        self.assertEqual([line["type"] for line in self.lines()], ["start", "end"])
        self.assertEqual(sorted(path.name for path in (self.root / ".canon/canon/trace" / unit).iterdir()),
                         names[closed])


class SkillDigestTest(TraceCase):
    def setUp(self):
        super().setUp()
        self.trace("on")

    def skill(self, top, name, files=()):
        """Create the skill directory `top/name` holding a SKILL.md and `files`, given by relative path; return it."""
        directory = top / name
        for rel in ("SKILL.md", *files):
            (directory / rel).parent.mkdir(parents=True, exist_ok=True)
            (directory / rel).write_text("{} of {}\n".format(rel, name), encoding="utf-8")
        return directory

    def manifest(self, *args, **env):
        """Start a unit; return the manifest line of the digest its start line records, None when it records none."""
        digest = self.start_line(*args, **env).get("manifest")
        return next((line for line in self.lines() if line["type"] == "manifest" and line["digest"] == digest), None)

    def blob(self, path):
        return self.git("hash-object", "--no-filters", str(path))

    def test_a_skills_digest_is_the_design_formula_over_the_blob_ids_of_its_covered_files(self):
        top = self.tmpdir()
        self.skill(top, "canon")
        skill = self.skill(top, "canon-x", ("notes-é.md", "scripts/run.py"))

        def digest(directory, covered):
            pairs = sorted([rel, self.blob(directory / rel)] for rel in covered)
            return hashlib.sha256(json.dumps(pairs, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()

        def expected():
            return {"canon": digest(top / "canon", ["SKILL.md"]),
                    "canon-x": digest(skill, ["SKILL.md", "notes-é.md", "scripts/run.py"])}

        first = self.manifest("design", "--skill", str(skill))
        self.assertEqual(first and first["skills"], expected())
        self.assertEqual(first["digest"], hashlib.sha256(json.dumps(first["skills"], sort_keys=True,
                                                                    separators=(",", ":")).encode()).hexdigest())
        (skill / "scripts/run.py").write_text("edited\n")
        edited = self.manifest("design", "--skill", str(skill))
        self.assertEqual(edited["skills"], expected())
        self.assertNotEqual(edited["skills"]["canon-x"], first["skills"]["canon-x"])
        for rel in ("LICENSE", "NOTICE", "__pycache__/x.pyc", ".DS_Store"):
            (skill / rel).parent.mkdir(exist_ok=True)
            (skill / rel).write_text("not covered\n")
        self.assertEqual(self.manifest("design", "--skill", str(skill)), edited)

    def test_the_installed_and_the_source_layouts_find_every_canon_skill_and_no_other_directory(self):
        installed = self.tmpdir()
        for name in ("canon", "canon-design", "canonical", "other", "more/canon-nested"):
            self.skill(installed, name)
        (installed / "canon-empty").mkdir()
        (installed / "canon-file").write_text("not a directory\n")
        found = {"canon", "canon-design"}
        if os.name != "nt":
            (installed / "canon-linked").symlink_to(self.skill(self.tmpdir(), "canon-linked"), target_is_directory=True)
            found.add("canon-linked")
        self.assertEqual(set(self.manifest("design", "--skill", str(installed / "canon-design"))["skills"]), found)
        source = self.tmpdir() / "skills"
        for name in ("governance/canon", "execution/canon-tdd", "execution/other"):
            self.skill(source, name)
        (source / "execution/canon-empty").mkdir()
        self.skill(source.parent, "canon-beside")
        self.assertEqual(set(self.manifest("design", "--skill", str(source / "execution/canon-tdd"))["skills"]),
                         {"canon", "canon-tdd"})

    def test_each_manifest_line_appears_once_before_its_first_use_and_top_level_ends_compute_their_own(self):
        skill = self.skill(self.tmpdir(), "canon-x")
        plan = self.start("plan")
        with ThreadPoolExecutor(max_workers=10) as pool, self.lock_held("events.lock"):
            starts = [pool.submit(self.start, "design", "--skill", str(skill)) for _ in range(10)]
            time.sleep(2)
        self.assertEqual(len({start.result() for start in starts}), 10)
        implement = self.start("implement", "--skill", str(skill))
        gate = self.start("gate", "--parent", implement, "--skill", str(skill))
        (skill / "SKILL.md").write_text("edited\n")
        piece = self.start("slice", "P001", "--slice", "S1", "--parent", implement)
        self.trace("end", gate, "delivered")
        self.trace("end", implement, "delivered")
        lines = self.lines()
        manifests = [line["digest"] for line in lines if line["type"] == "manifest"]
        self.assertEqual(len(manifests), 2)
        self.assertEqual(len(set(manifests)), 2)
        for n, line in enumerate(lines):
            if line.get("manifest"):
                self.assertIn(line["manifest"], [other.get("digest") for other in lines[:n]], n)
        starts = {line["id"]: line for line in lines if line["type"] == "start"}
        ends = {line["id"]: line for line in lines if line["type"] == "end"}
        self.assertIsNone(starts[plan]["manifest"])
        self.assertEqual(starts[gate]["manifest"], starts[implement]["manifest"])
        self.assertEqual(ends[implement].get("manifest"), starts[piece]["manifest"])
        self.assertNotEqual(ends[implement].get("manifest"), starts[implement]["manifest"])
        self.assertNotIn("manifest", ends[gate])

    @unittest.skipIf(os.name == "nt", "Windows has no executable bit")
    def test_a_manifest_the_snapshot_repository_lacks_is_stored_once_with_each_files_mode(self):
        self.commit()
        top = self.tmpdir()
        self.skill(top, "canon")
        skill = self.skill(top, "canon-x", ("scripts/run.sh", "LICENSE"))
        (skill / "scripts/run.sh").chmod(0o755)
        digest = self.start_line("design", "--skill", str(skill))["manifest"]
        refs = self.snap("for-each-ref", "--format=%(refname) %(objectname)", "refs/skills/")
        self.assertEqual(refs.split(" ")[0], "refs/skills/" + digest)
        tree = {}
        for entry in self.snap("ls-tree", "-r", "refs/skills/" + digest).splitlines():
            info, path = entry.split("\t")
            tree[path] = (info.split()[0], info.split()[2])
        self.assertEqual(tree, {"canon/SKILL.md": ("100644", self.blob(top / "canon/SKILL.md")),
                                "canon-x/SKILL.md": ("100644", self.blob(skill / "SKILL.md")),
                                "canon-x/scripts/run.sh": ("100755", self.blob(skill / "scripts/run.sh"))})
        self.assertEqual(self.snap("rev-list", "--parents", "refs/skills/" + digest), refs.split(" ")[1])
        before = self.snapshot_objects()
        line = self.start_line("design", "--skill", str(skill))
        self.assertEqual(line["manifest"], digest)
        self.assertEqual(self.snapshot_objects() - before,
                         {line["snapshot"], self.snap("rev-parse", line["snapshot"] + "^")})
        self.assertEqual(self.snap("for-each-ref", "--format=%(refname) %(objectname)", "refs/skills/"), refs)
        outside = self.tmpdir()
        (outside / "AGENTS.md").write_text("# AGENTS.md\n")
        self.start("design", "--skill", str(skill), cwd=outside)
        self.assertEqual(self.lines(outside / ".canon/canon/trace/events.jsonl")[-1]["manifest"], digest)
        self.assertFalse((outside / ".canon/canon/trace/.git").exists())

    def test_two_parallel_starts_with_the_same_new_manifest_store_it_once(self):
        self.commit()
        skill = self.skill(self.tmpdir(), "canon-x")
        with ThreadPoolExecutor(max_workers=2) as pool:
            units = list(pool.map(lambda _: self.start("design", "--skill", str(skill)), range(2)))
        starts = {line["id"]: line for line in self.lines() if line["type"] == "start"}
        self.assertEqual([starts[unit]["skipped"] for unit in units], [None, None])
        [digest] = {starts[unit]["manifest"] for unit in units}
        ref = "refs/skills/" + digest
        self.assertEqual(self.snap("rev-list", "--parents", ref), self.snap("rev-parse", ref))
        objects = self.snap("cat-file", "--batch-all-objects", "--batch-check=%(objectname) %(objecttype)")
        commits = [line.split()[0] for line in objects.splitlines() if line.endswith(" commit")]
        subjects = [self.snap("log", "-1", "--format=%s", commit) for commit in commits]
        self.assertEqual(subjects.count("skills " + digest), 1)


class PruneTest(TraceCase):
    def setUp(self):
        super().setUp()
        self.trace("on")
        self.commit()
        self.trace_dir = self.root / ".canon/canon/trace"

    def backdate(self, unit, days):
        """Turn `unit` into a unit started `days` days earlier, in the documented formats: its id and start time in
        the events file, its snapshot ref and its archive; return its new id."""
        ago = datetime.timedelta(days=days)
        old = (self.started(unit) - ago).strftime(UNIT_TIME_FORMAT) + unit[16:]
        lines = self.lines()
        for line in lines:
            if line.get("id") == unit:
                line.update(id=old, at=(datetime.datetime.fromisoformat(line["at"]) - ago).isoformat())
        self.events.write_text("".join(json.dumps(line, separators=(",", ":")) + "\n" for line in lines),
                               encoding="utf-8")
        if self.snap("for-each-ref", "refs/trace/" + unit):
            self.snap("update-ref", "refs/trace/" + old, "refs/trace/" + unit)
            self.snap("update-ref", "-d", "refs/trace/" + unit)
        if (self.trace_dir / unit).exists():
            (self.trace_dir / unit).rename(self.trace_dir / old)
        return old

    def snapshot_refs(self):
        return sorted(self.snap("for-each-ref", "--format=%(refname)", "refs/trace/").splitlines())

    def reviewed_gate(self):
        """Start a gate and end it with its review file archived; return its id."""
        topic = self.root / ".canon/canon-blind-review/D001"
        topic.mkdir(parents=True, exist_ok=True)
        unit = self.start("gate", "D001")
        (topic / "same-model.md").write_text("### F1 [major] {}\n".format(unit))
        self.trace("end", unit, "delivered", "--dir", ".canon/canon-blind-review/D001")
        self.assertEqual(self.lines()[-1]["archive"], "ok")
        return unit

    def test_snapshots_and_archives_of_units_started_more_than_n_days_ago_go_and_lines_and_skills_stay(self):
        skill = self.tmpdir() / "canon-x"
        skill.mkdir()
        (skill / "SKILL.md").write_text("canon-x\n")
        old = [self.backdate(self.start("design", "--skill", str(skill)), 8), self.backdate(self.reviewed_gate(), 8)]
        kept = [self.backdate(self.reviewed_gate(), 6), self.start("design")]
        skills = self.snap("for-each-ref", "refs/skills/")
        self.assertNotEqual(skills, "")
        events = self.events.read_bytes()
        self.assertRegex(self.trace("prune", "--days", "7"),
                         r"^removed 2 snapshots and 1 archive of units started more than 7 days ago\n"
                         r"removed 0 index copies and 0 build directories left by interrupted starts\n"
                         r"snapshots: 2, [\d.]+ [KMG]iB on disk\n$")
        self.assertEqual(self.snapshot_refs(), sorted("refs/trace/" + unit for unit in kept))
        self.assertEqual([unit for unit in old + kept if (self.trace_dir / unit).exists()], [kept[0]])
        self.assertEqual([path.name for path in (self.trace_dir / kept[0]).iterdir()], ["same-model.md"])
        self.assertEqual(self.snap("for-each-ref", "refs/skills/"), skills)
        self.assertEqual(self.events.read_bytes(), events)

    def test_index_copies_and_build_directories_of_starts_more_than_an_hour_ago_go(self):
        self.start("design")
        git_dir, index_time = self.trace_dir / ".git", time.time() - 3 * 86400
        units = {}
        for minutes in (90, 30):
            unit = units[minutes] = self.unit_id(datetime.timedelta(minutes=minutes), minutes)
            copy = git_dir / ("index-" + unit)
            copy.write_bytes((self.root / ".git/index").read_bytes())
            os.utime(str(copy), (index_time, index_time))
            self.git("init", "-q", "--template=", str(self.trace_dir / (".init-" + unit)))
        self.assertIn("\nremoved 1 index copy and 1 build directory left by interrupted starts\n",
                      self.trace("prune", "--days", "7"))
        self.assertEqual(sorted(path.name for path in git_dir.glob("index-*")), ["index-" + units[30]])
        self.assertEqual(sorted(path.name for path in self.trace_dir.glob(".init-*")), [".init-" + units[30]])

    def test_pruned_snapshots_objects_dated_over_an_hour_back_free_their_space_and_newer_objects_stay(self):
        kept = self.start("implement")
        pruned, size = self.root / "src/pruned.bin", 1 << 20
        pruned.write_bytes(os.urandom(size))
        old = self.backdate(self.start("implement"), 2)
        blob = self.snap("rev-parse", "refs/trace/{}:src/pruned.bin".format(old))
        pruned.unlink()
        git_dir = self.trace_dir / ".git"
        hours_ago = time.time() - 2 * 3600
        for path in (git_dir / "objects").rglob("*"):
            if path.is_file():
                os.utime(str(path), (hours_ago, hours_ago))
        in_progress = self.tmpdir() / "in-progress.txt"
        in_progress.write_text("written by a start in progress\n")
        recent = self.snap("hash-object", "-w", str(in_progress))

        def disk_size():
            return sum(path.stat().st_size for path in git_dir.rglob("*") if path.is_file())

        before = disk_size()
        self.trace("prune", "--days", "1")
        self.assertLess(disk_size(), before - size // 2)
        self.snap("fsck", "--strict")
        self.assertNotEqual(self.run_here("git", "-C", str(self.trace_dir), "cat-file", "-e", blob).returncode, 0)
        self.snap("cat-file", "-e", recent)
        self.assertIn("src/base.py", self.snap("ls-tree", "-r", "--name-only", "refs/trace/" + kept).splitlines())

    def test_prune_runs_with_the_machine_switch_absent(self):
        old = self.backdate(self.reviewed_gate(), 2)
        self.trace("off")
        self.assertFalse((self.config / "canon/trace").exists())
        self.assertRegex(self.trace("prune", "--days", "1"),
                         r"^removed 1 snapshot and 1 archive of units started more than 1 day ago\n")
        self.assertEqual(self.snapshot_refs(), [])
        self.assertFalse((self.trace_dir / old).exists())

    def test_days_must_be_a_whole_number_of_zero_or_more(self):
        old = self.backdate(self.start("design"), 2)
        for days in ("-1", "x"):
            self.trace("prune", "--days", days, returncode=2)
        self.assertEqual(self.snapshot_refs(), ["refs/trace/" + old])

    def test_a_gc_already_running_in_the_snapshot_repository_is_a_trace_error_after_the_deletions(self):
        self.backdate(self.reviewed_gate(), 2)
        (self.trace_dir / ".git/gc.pid").write_text("{} {}".format(os.getpid(), socket.gethostname()))
        out = self.trace("prune", "--days", "1")
        self.assertRegex(out, r"^removed 1 snapshot and 1 archive of units started more than 1 day ago\n"
                              r"removed 0 index copies and 0 build directories left by interrupted starts\n"
                              r"trace error: git gc: exit 128\n$")
        self.assertEqual(self.snapshot_refs(), [])

    @unittest.skipIf(fcntl is None, "the test holds snapshot.lock with flock")
    def test_a_prune_that_cannot_take_snapshot_lock_is_a_trace_error_and_deletes_nothing(self):
        old = self.backdate(self.reviewed_gate(), 2)
        interrupted = self.unit_id(datetime.timedelta(hours=2), 1)
        copy, build = self.trace_dir / ".git" / ("index-" + interrupted), self.trace_dir / (".init-" + interrupted)
        copy.write_bytes(b"")
        build.mkdir()
        with self.lock_held("snapshot.lock"):
            out = self.trace("prune", "--days", "1")
        self.assertRegex(out, r"^trace error: [^\n]*\n$")
        self.assertEqual(self.snapshot_refs(), ["refs/trace/" + old])
        self.assertEqual([path.exists() for path in (self.trace_dir / old, copy, build)], [True, True, True])

    def test_outside_git_prune_deletes_old_archives_and_creates_nothing(self):
        outside = self.tmpdir()
        (outside / "AGENTS.md").write_text("# AGENTS.md\n")
        out = self.trace("prune", "--days", "7", cwd=outside)
        self.assertEqual(out.splitlines()[-1], "snapshots: 0, 0.0 KiB on disk")
        self.assertEqual([path.name for path in outside.iterdir()], ["AGENTS.md"])
        archive = outside / ".canon/canon/trace" / self.unit_id(datetime.timedelta(days=8), 1)
        archive.mkdir(parents=True)
        (archive / "snapshot-error.txt").write_text("fatal: index file corrupt\n")
        self.assertRegex(self.trace("prune", "--days", "7", cwd=outside),
                         r"^removed 0 snapshots and 1 archive of units started more than 7 days ago\n")
        self.assertEqual(list(archive.parent.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
