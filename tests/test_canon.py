"""Regression tests for skills/governance/canon/scripts/canon.py; scripts/validate.py runs them."""

import contextlib
import datetime
import hashlib
import importlib.util
import json
import os
import re
import shutil
import socket
import stat
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
INSTALL = ".agents/skills/canon/scripts/canon.py"
sys.dont_write_bytecode = True
_spec = importlib.util.spec_from_file_location("canon", SCRIPT)
canon = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(canon)

FINDINGS = "## Scope\n\nFixture.\n\n## Findings\n\n| ID | Severity | Finding | Disposition |\n|---|---|---|---|\n{}\n"
DESIGN = "## Goals\n\nFrom {}.\n\n## Spec\n\nX.\n\n## Decisions\n\nNone.\n"
PLAN = "## Current state\n\nNext: S1.\n\n## Slices\n\n### S1: First\n\nStatus: todo\n\n## Notes\n\n{}\n\n## Log\n\nStarted.\n"
ISSUES = "\n## Known issues\n\n| ID | Severity | Issue | Source | Since | Next |\n|---|---|---|---|---|---|\n{}\n"
EXPERIMENT = "## Question\n\nFast?\n\n## Setup\n\n{}\n\n## Results\n\nFast.\n\n## Conclusion\n\n{}\n"
RUN = "- Commit: 3f9a1c2\n- Environment: x\n- Command: y"
NO_OVERVIEW = "ERROR docs: no D000, the project overview every project keeps; run `canon.py init` at the repo root"
OUTSIDE_INSTALL = ("canon: canon runs only from an install inside the project, and this canon.py is {}; install canon in "
                   "the project as https://github.com/BigTailFox/skills#install says, and remove a user install of "
                   "canon with `npx skills remove -g`\n")
UNIT_TIME_FORMAT = "%Y%m%dT%H%M%SZ"
RUN_DIR = None


def setUpModule():
    """One directory per run under TMPDIR holds every test's directories, so a stray write to `../` stays in it."""
    global RUN_DIR
    run = tempfile.TemporaryDirectory(prefix="test_canon-")
    unittest.addModuleCleanup(run.cleanup)
    RUN_DIR = Path(run.name).resolve()


def within(path, top):
    return path == top or top in path.parents


class CanonTest(unittest.TestCase):
    OVERVIEW = "docs/designs/D000-project-overview.md"
    MODULES = "| Module | Path | Purpose | Entry points | Design |\n|---|---|---|---|---|\n"

    def setUp(self):
        self.root = self.tmpdir()
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.name", "canon test")
        self.git("config", "user.email", "canon@example.invalid")
        self.ok("init")
        (self.root / "src").mkdir()
        (self.root / "src/base.py").write_text("value = 1\n")

    def repository_without_docs(self):
        self.root = self.tmpdir()
        self.git("init", "-q", "-b", "main")

    outside = ()

    def tmpdir(self):
        tmp = tempfile.TemporaryDirectory(dir=RUN_DIR)
        self.addCleanup(tmp.cleanup)
        return Path(tmp.name)

    def outside_checkouts(self):
        """A new directory in no checkout: `canon.py` run there would otherwise act on the checkout around TMPDIR."""
        path = self.tmpdir()
        for parent in path.resolve().parents:
            if (parent / ".git").exists() or (parent / "AGENTS.md").exists():
                self.skipTest("TMPDIR is inside {}, which holds .git or AGENTS.md".format(parent))
        self.outside = (*self.outside, path.resolve())
        return path

    def run_here(self, *args):
        return subprocess.run(args, cwd=self.root, capture_output=True, text=True)

    def git(self, *args):
        result = self.run_here("git", *args)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def canon_process(self, *args, cwd=None, script=None, start=subprocess.run, **options):
        """`canon.py args` started with `start` and `options`, its output captured as text, by the path `script`, by
        default the project's installed canon.py (`install`). `cwd`, by default the test repository, must lie in a
        test repository or in a directory from `outside_checkouts`: anywhere else canon.py would act on the checkout
        around TMPDIR."""
        cwd = Path(cwd or self.root)
        top = self.project_top(cwd.resolve())
        script = script or self.install(*top)
        return start([sys.executable, "-B", str(script), *args], cwd=str(cwd), stdout=subprocess.PIPE,
                     stderr=subprocess.PIPE, text=True, **options)

    def project_top(self, cwd):
        """The directory canon.py's location check finds for `cwd`, and whether it holds `.git`: the nearest test
        repository at or above `cwd`; else, within its `outside_checkouts` directory, the nearest directory at or above
        it that holds an AGENTS.md, else `cwd`."""
        for path in (cwd, *cwd.parents):
            if within(path, RUN_DIR) and (path / ".git").exists():
                return path, True
        outside = next((path for path in self.outside if within(cwd, path)), None)
        if outside is None:
            self.fail("canon.py would run in {}, in no test repository and not from outside_checkouts()".format(cwd))
        return next((path for path in (cwd, *cwd.parents) if within(path, outside) and (path / "AGENTS.md").exists()),
                    cwd), False

    def install(self, top, is_git):
        """The project's installed canon.py: the link `<top>/INSTALL` to SCRIPT, created when missing, which no test
        writes through; in a Git checkout, the repository's info/exclude names it, so Git never sees it."""
        link = top / INSTALL
        if not os.path.lexists(str(link)):
            link.parent.mkdir(parents=True, exist_ok=True)
            with contextlib.suppress(FileExistsError):
                link.symlink_to(SCRIPT)
        if not (link.is_symlink() and link.resolve() == SCRIPT):
            self.fail("{} is not a link to {}".format(link, SCRIPT))
        if is_git:
            exclude = top / subprocess.run(["git", "rev-parse", "--git-path", "info/exclude"], cwd=str(top),
                                           capture_output=True, text=True, check=True).stdout.strip()
            text = exclude.read_text() if exclude.exists() else ""
            if "/" + INSTALL not in text.splitlines():
                exclude.parent.mkdir(parents=True, exist_ok=True)
                exclude.write_text(text + ("\n" if text and not text.endswith("\n") else "") + "/" + INSTALL + "\n")
        return link

    def canon(self, *args, **options):
        return self.canon_process(*args, **options)

    def ok(self, *args, **options):
        result = self.canon(*args, **options)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result.stdout

    def fails(self, *args):
        result = self.canon(*args)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        return result.stdout + result.stderr

    def refuses(self, message, *args):
        """`canon.py args` exits 1 with `canon: message` and changes no file."""
        self.assertEqual(self.fails(*args), "canon: {}\n".format(message))
        self.assertEqual(self.git("status", "--porcelain"), "")

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

    def modules(self, *cells, design="none"):
        """Give D000's Modules table one row per Path cell, each with `design` in its Design cell."""
        path = self.root / self.OVERVIEW
        rows = "".join("| m{} | {} | Fixture | none | {} |\n".format(i, cell, design) for i, cell in enumerate(cells, 1))
        path.write_text(path.read_text().replace(self.MODULES, self.MODULES + rows))

    def init_module(self, path, *args):
        """`init --root <path>` with `args`, on `path` made a directory first, as a module's code makes it."""
        (self.root / path).mkdir(parents=True, exist_ok=True)
        return self.ok("init", "--root", path, *args)

    def problems(self, out):
        """The ERROR and WARN lines of `check`'s output."""
        return [line for line in out.splitlines() if line.startswith(("ERROR", "WARN"))]

    def create(self, *names):
        for name in names:
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.exists():
                path.write_text("x\n")

    def edit_commit(self, *names):
        for name in names:
            path = self.root / name
            path.write_text(path.read_text() + "x\n")
        self.git("add", "-A")
        self.git("commit", "-qm", "edit " + ", ".join(names))

    def section(self, out, heading):
        """The indented lines that follow `heading` in a report such as `audit`'s; None without the heading."""
        lines = out.splitlines()
        if heading not in lines:
            return None
        found = []
        for line in lines[lines.index(heading) + 1:]:
            if not line.startswith("  "):
                break
            found.append(line)
        return found


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

    def test_a_pending_review_without_reviewed_reads_none(self):
        self.design(status="accepted", reviewed=None, reviewers=None, implemented=None)
        self.assertIn("revision 1 is not reviewed (reviewed: none)", self.ok("check", "--fix"))


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


class ApprovedTest(CanonTest):
    def test_approved_up_to_reviewed_gives_no_error(self):
        self.design(revision=3, reviewed=3, approved=3, implemented=3)
        self.doc("P", "work", reviewed=1, reviewers=["fixture"], approved=1, refs=["D001"], based_on=["D001@r3"])
        self.assertNotIn("`approved`", self.ok("check", "--fix"))

    def test_approved_outside_one_to_reviewed_fails_and_fix_neither_sets_nor_deletes_it(self):
        error = re.escape("`approved` must be an integer revision from 1 to `reviewed`")
        design = self.design(revision=3, reviewed=3, implemented=3)
        plan = self.doc("P", "work", approved=1, refs=["D001"], based_on=["D001@r3"])
        self.assertRegex(self.fails("check", "--fix"), "ERROR docs/plans/P001-work.md: " + error)
        self.assertIn("\napproved: 1\n", plan.read_text())
        self.assertNotIn("\napproved:", design.read_text())
        self.set(plan, approved=None)
        for value in (4, 0, "x"):
            self.set(design, approved=value)
            self.assertRegex(self.fails("check"), "ERROR docs/designs/D001-area.md: " + error)

    def test_approved_on_another_type_gets_only_the_unknown_field_error(self):
        self.doc("C", "idea", approved=1)
        out = self.fails("check")
        self.assertIn("unknown frontmatter field `approved`", out)
        self.assertNotIn("must be an integer revision", out)


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

    def test_renumber_normalizes_a_requested_sub_design_id(self):
        self.design()
        child = self.design("part", parent="D001")
        self.design("other-part", parent="D001")
        self.commit()
        self.refuses("D0001B is already used", "renumber", "D001A", "D0001B")
        self.refuses("new id must be a sub-design of D001", "renumber", "D001A", "D0002C")
        self.assertEqual(self.ok("renumber", "D001A", "D0001C").splitlines()[0], "D001A -> D001C")
        self.assertTrue(child.with_name("D001C-part.md").is_file())

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

    def test_renumber_carries_links_to_the_headings_it_renames(self):
        self.design(body="## Goals\n\nBack to [the top](#d001-fixture).\n\n## Spec\n\n### D001-K1 history\n\nX.\n\n"
                         "## Decisions\n\nNone.\n")
        plan = self.doc("P", "work", body="Implements [D001§d001-fixture: Fixture](../designs/D001-area.md#d001-fixture), "
                                          "[D001§goals: goals](../designs/D001-area.md#goals) and [D001§d001-k1-history: "
                                          "history](../designs/D001-area.md#d001-k1-history).\n\n" + PLAN.format("None."))
        self.commit()
        self.ok("renumber", "D001", "D005")
        self.assertIn("Implements [D005§d005-fixture: Fixture](../designs/D005-area.md#d005-fixture), "
                      "[D005§goals: goals](../designs/D005-area.md#goals) and [D005§d005-k1-history: "
                      "history](../designs/D005-area.md#d005-k1-history).", plan.read_text())
        self.assertIn("Back to [the top](#d005-fixture).", (self.root / "docs/designs/D005-area.md").read_text())
        self.ok("check", "--fix")

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
        self.assertRegex(self.fails("renumber", target), r"cannot tell which D001 owns .* or pass --base <ref>")
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
            waiter = self.canon_process("new", "E", "waiter", cwd=root, start=subprocess.Popen)
            time.sleep(1)
            self.assertIsNone(waiter.poll())
        out, err = waiter.communicate(timeout=60)
        self.assertEqual(waiter.returncode, 0, out + err)


class HistoryIdTest(CanonTest):
    def three_designs(self):
        return [self.design(slug) for slug in ("a", "b", "c")]

    def new(self, *args):
        return self.ok("new", "D", *args).strip()

    def test_an_id_a_renumber_left_stays_taken(self):
        self.three_designs()
        self.commit()
        self.ok("renumber", "D003", "D004")
        self.commit()
        self.assertEqual(self.new("x"), "docs/designs/D005-x.md")
        (self.root / "notes.md").write_text("# Notes\n\nKept notes.\n")
        self.assertIn("notes.md -> docs/designs/D006-notes.md", self.ok("adopt", "notes.md", "design"))
        self.assertIn("D001 -> D007", self.ok("renumber", "D001"))
        status = self.git("status", "--porcelain")
        self.assertIn("already used", self.fails("renumber", "D002", "D003"))
        self.assertEqual(self.git("status", "--porcelain"), status)

    def test_a_sub_design_letter_a_renumber_left_stays_taken(self):
        self.design()
        self.design("part", parent="D001")
        self.commit()
        self.ok("renumber", "D001A", "D001B")
        self.commit()
        self.assertEqual(self.new("y", "--parent", "D001"), "docs/designs/D001C-y.md")

    def test_outside_git_ids_follow_the_files_alone(self):
        self.root = self.outside_checkouts()
        self.ok("init")
        self.assertEqual([self.new("x"), self.new("x")], ["docs/designs/D001-x.md", "docs/designs/D002-x.md"])

    def test_on_an_unborn_branch_ids_follow_the_files_alone(self):
        self.assertEqual([self.new("x"), self.new("x")], ["docs/designs/D001-x.md", "docs/designs/D002-x.md"])

    def run_with_path(self, bin_dir, *args, cwd=None):
        return self.canon_process(*args, cwd=cwd, env=dict(os.environ, PATH=str(bin_dir)))

    def new_with_git_from(self, bin_dir):
        """The error of `new D x` run with `bin_dir` as the whole PATH, after D003 was committed and deleted; `which`,
        which assigns no id, still runs."""
        design = self.three_designs()[2]
        self.commit()
        self.git("rm", "-q", str(design.relative_to(self.root)))
        self.commit(check=False)
        result = self.run_with_path(bin_dir, "new", "D", "x")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertFalse((self.root / "docs/designs/D003-x.md").exists())
        which = self.run_with_path(bin_dir, "which", "src/base.py")
        self.assertEqual(which.returncode, 0, which.stderr)
        self.assertTrue(which.stdout.startswith("src/base.py: D001 docs/designs/D001-a.md"), which.stdout)
        return result.stderr

    @unittest.skipIf(os.name == "nt", "the refusing git is a shell script")
    def test_a_git_that_refuses_the_checkout_ends_new_instead_of_reusing_an_id(self):
        refusing = self.tmpdir()
        (refusing / "git").write_text("#!/bin/sh\necho 'fatal: detected dubious ownership in repository' >&2\nexit 128\n")
        (refusing / "git").chmod(0o755)
        self.assertEqual(self.new_with_git_from(refusing),
                         "canon: cannot read the history of HEAD in {}: fatal: detected dubious ownership in "
                         "repository\n".format(self.root.resolve()))

    def test_a_checkout_without_git_on_path_ends_new_instead_of_reusing_an_id(self):
        no_git = self.tmpdir()
        message = "canon: cannot read the history of HEAD in {}: git is not on PATH\n".format(self.root.resolve())
        self.assertEqual(self.new_with_git_from(no_git), message)
        nested = self.root / "pkg"
        nested.mkdir()
        shutil.copy(self.root / "AGENTS.md", nested / "AGENTS.md")
        result = self.run_with_path(no_git, "new", "D", "y", cwd=nested)
        self.assertEqual((result.returncode, result.stderr), (1, message))

    def test_a_checkout_without_git_on_path_ends_renumber_with_a_base_with_the_history_error(self):
        self.three_designs()
        self.commit()
        result = self.run_with_path(self.tmpdir(), "renumber", "D001", "--base", "main")
        message = "canon: cannot read the history of HEAD in {}: git is not on PATH\n".format(self.root.resolve())
        self.assertEqual((result.returncode, result.stderr), (1, message))
        self.assertEqual(self.git("status", "--porcelain"), "")

    def test_the_id_of_a_deleted_design_stays_taken(self):
        design = self.three_designs()[2]
        self.commit()
        self.git("rm", "-q", str(design.relative_to(self.root)))
        self.commit(check=False)
        self.assertEqual(self.new("x"), "docs/designs/D004-x.md")

    def test_the_id_of_a_deleted_design_stays_taken_under_a_module_path_git_quotes(self):
        self.three_designs()[2].unlink()
        self.init_module("模块")
        design = self.new("c", "--root", "模块")
        self.assertEqual(design, "模块/docs/designs/D003-c.md")
        self.commit(check=False)
        self.git("rm", "-q", design)
        self.commit(check=False)
        self.assertEqual(self.new("x"), "docs/designs/D004-x.md")

    def test_a_design_a_discarding_merge_left_out_stays_taken(self):
        self.three_designs()
        self.commit()
        self.git("checkout", "-q", "-b", "side")
        self.new("d")
        self.commit(check=False)
        self.git("checkout", "-q", "main")
        self.git("merge", "-q", "-s", "ours", "--no-edit", "side")
        self.assertEqual(self.new("x"), "docs/designs/D005-x.md")

    def test_a_design_only_a_merge_resolution_added_stays_taken_once_a_merge_discards_it(self):
        self.three_designs()
        self.commit()
        self.git("checkout", "-q", "-b", "side")
        (self.root / "src/side.py").write_text("side = 1\n")
        self.commit(check=False)
        self.git("checkout", "-q", "main")
        (self.root / "src/main.py").write_text("main = 1\n")
        self.commit(check=False)
        self.git("checkout", "-q", "side")
        self.git("merge", "-q", "--no-ff", "--no-commit", "main")
        self.new("d")
        self.git("add", "-A")
        self.git("commit", "-q", "--no-edit")
        self.git("checkout", "-q", "main")
        self.git("merge", "-q", "-s", "ours", "--no-edit", "side")
        self.assertEqual(self.new("x"), "docs/designs/D005-x.md")


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

    def test_an_answered_experiment_must_be_finished_while_a_running_one_only_warns(self):
        path = self.doc("E", "bench", body=EXPERIMENT.format(RUN, ""), status="answered")
        self.set(path, summary="")
        mine = "docs/experiments/E001-bench.md: "
        self.assertCountEqual([p for p in self.problems(self.fails("check", "--fix")) if mine in p],
                              ["ERROR " + mine + "`summary` is empty", "ERROR " + mine + "Conclusion is empty"])
        self.set(path, status="running")
        self.assertEqual([p for p in self.problems(self.ok("check", "--fix")) if mine in p],
                         ["WARN " + mine + "`summary` is empty"])

    def test_a_live_concluded_experiment_must_be_finished(self):
        path = self.doc("E", "bench", body=EXPERIMENT.format(RUN, ""), status="concluded")
        self.doc("P", "work", body=PLAN.format("From [E001: Fixture](../experiments/E001-bench.md)."))
        self.set(path, summary="")
        mine = "docs/experiments/E001-bench.md: "
        self.assertCountEqual([p for p in self.problems(self.fails("check", "--fix")) if mine in p],
                              ["ERROR " + mine + "`summary` is empty", "ERROR " + mine + "Conclusion is empty"])

    def test_guidance_fails_once_past_the_review_gate(self):
        path = self.root / self.ok("new", "D", "gated").strip()
        self.set(path, status="accepted", reviewed=1, reviewers=["fixture"], summary="Fixture")
        self.assertRegex(self.fails("check"), r"ERROR .*template guidance")

    def test_a_guidance_marker_quoted_in_code_is_no_guidance(self):
        design = self.design()
        design.write_text(design.read_text() + "\nThe index starts at `<!-- canon:index:start -->`.\n\n"
                          "```markdown\n<!-- canon:agents:start -->\n```\n")
        self.assertNotIn("D001-area.md: template guidance", self.ok("check", "--fix"))


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

    def test_affected_counts_a_renamed_file_under_its_old_and_new_path(self):
        self.design()
        self.commit()
        self.git("config", "diff.renames", "true")
        self.git("branch", "before")
        self.git("mv", "src/base.py", "src/moved.py")
        self.assertIn("\n  src/base.py\n  src/moved.py\n", self.ok("affected"))
        self.git("commit", "-qm", "move")
        self.assertIn("\n  src/base.py\n  src/moved.py\n", self.ok("affected", "--base", "before"))


class FrontmatterTest(CanonTest):
    def test_brackets_make_lists_only_in_list_fields(self):
        concept = self.doc("C", "idea")
        self.set(concept, summary="[a, b]")
        self.ok("check", "--fix")
        self.assertIn(" - [a, b]", self.ok("find", "C001"))

    def test_a_missing_status_gives_only_the_missing_field_error(self):
        self.set(self.design(), status=None)
        out = self.fails("check")
        self.assertIn("missing frontmatter field `status`", out)
        self.assertNotIn("status `None`", out)

    def test_reviewed_on_another_type_gets_only_the_unknown_field_error(self):
        self.doc("C", "idea", reviewed=2)
        out = self.fails("check")
        self.assertIn("unknown frontmatter field `reviewed`", out)
        self.assertNotIn("`reviewers` must list", out)
        self.assertNotIn("must be an integer revision", out)

    def test_show_prints_no_frontmatter_lines_for_a_doc_without_any(self):
        concept = self.root / "docs/concepts/C001-raw.md"
        concept.parent.mkdir(parents=True, exist_ok=True)
        body = "# C001: Raw\n\n## Motivation\n\nX.\n\n## Ideas\n\nY.\n"
        outline = "docs/concepts/C001-raw.md\n# C001: Raw\nMotivation  #motivation\nIdeas  #ideas\n"
        for text in (body, "---\n---\n" + body):
            concept.write_text(text)
            self.assertEqual(self.ok("show", "C001"), outline)


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
        self.assertNotIn("commits since", self.ok("audit"))

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

    def test_a_paths_entry_outside_the_repository_counts_no_commits(self):
        self.design(paths=["../elsewhere/**", "/elsewhere/**"])
        self.commit()
        self.code_commit("fix: unchecked")
        self.assertNotIn("commits since", self.ok("audit"))

    def test_a_reconciliation_restarts_the_count_and_a_trailer_naming_the_design_does_not(self):
        self.design()
        self.commit()
        last = self.git("rev-parse", "HEAD").strip()
        self.code_commit("fix: unchecked")
        self.git("commit", "-q", "--allow-empty", "-m", "docs: checked\n\nRefs: D001")
        self.git("commit", "-q", "--allow-empty", "-m", "docs: reconciled\n\nSee Reconciled: D001")
        out = self.ok("audit")
        self.assertIn("Designs with code commits since the design last changed or was reconciled that no `Refs:` "
                      "trailer names (most first; review `git log <since>..HEAD` on its paths):", out)
        self.assertRegex(out, r"  1 commits since {}  D001 ".format(last[:12]))
        self.git("commit", "-q", "--allow-empty", "-m", "docs: reconciled\n\nreconciled: D002, D001")
        reconciled = self.git("rev-parse", "HEAD").strip()
        self.assertNotIn("commits since", self.ok("audit"))
        self.code_commit("fix: later")
        self.git("commit", "-q", "--allow-empty", "-m", "docs: reconciled\n\nReconciled: D002")
        self.assertRegex(self.ok("audit"), r"  1 commits since {}  D001 ".format(reconciled[:12]))

    def test_a_reconciliation_on_a_merged_branch_leaves_the_commits_it_does_not_descend_from_counted(self):
        self.design()
        self.create("src/a.py", "src/b.py")
        self.commit()
        self.git("checkout", "-qb", "side")
        self.edit_commit("src/a.py")
        self.git("commit", "-q", "--allow-empty", "-m", "docs: reconciled\n\nReconciled: D001")
        reconciled = self.git("rev-parse", "HEAD").strip()
        self.git("checkout", "-q", "main")
        self.edit_commit("src/b.py")
        self.git("merge", "-q", "--no-edit", "side")
        self.assertRegex(self.ok("audit"), r"  2 commits since {}  D001 ".format(reconciled[:12]))

    def test_a_clean_merge_counts_when_the_other_side_changed_nothing_under_the_paths(self):
        self.design()
        self.create("src/a.py", "other/w.txt")
        self.commit()
        self.git("checkout", "-qb", "side")
        self.edit_commit("src/a.py")
        self.git("commit", "-q", "--allow-empty", "-m", "docs: reconciled\n\nReconciled: D001")
        reconciled = self.git("rev-parse", "HEAD").strip()
        self.git("checkout", "-q", "main")
        self.edit_commit("other/w.txt")
        self.git("merge", "-q", "--no-edit", "side")
        self.assertRegex(self.ok("audit"), r"  1 commits since {}  D001 ".format(reconciled[:12]))

    def test_entries_with_brackets_wildcards_in_a_segment_or_globs_above_a_match_count_what_they_govern(self):
        self.design(paths=["src/**.py", "lib/*", "a[1]/x.txt"])
        self.design("config", paths=["*.cfg"])
        names = ("src/deep/y.py", "lib/sub/z.txt", "a[1]/x.txt", "top.cfg", "a1/x.txt", "other/w.txt")
        self.create(*names)
        self.commit()
        for name in names:
            self.edit_commit(name)
        out = self.ok("audit")
        self.assertRegex(out, r"  3 commits since [0-9a-f]+  D001 ")
        self.assertRegex(out, r"  1 commits since [0-9a-f]+  D002 ")

    def test_idle_docs_skip_concepts(self):
        self.doc("C", "backlog", created="2020-01-01", updated="2020-01-01")
        self.doc("I", "flaky", created="2020-01-01", updated="2020-01-01")
        out = self.ok("audit")
        self.assertIn("I001", out)
        self.assertNotIn("C001", out)

    def test_idle_docs_skip_live_concluded_experiments(self):
        old = dict(created="2020-01-01", updated="2020-01-01")
        self.doc("E", "bench", body=EXPERIMENT.format(RUN, "Fast enough."), status="concluded", **old)
        self.doc("E", "load", body=EXPERIMENT.format(RUN, ""), status="running", **old)
        idle = self.section(self.ok("audit"), "Open docs untouched for over 30 days:")
        self.assertEqual([line.split()[0] for line in idle], ["E002"])


@unittest.skipIf(os.name == "nt", "the failing git is a shell script")
class GitFailureTest(CanonTest):
    def fails_with_git(self, failing, *args):
        """The error of `args` run with a `git` first on PATH that fails with `fatal: boom` when its arguments start
        with `failing`, and runs the real Git otherwise."""
        bin_dir = self.tmpdir()
        (bin_dir / "git").write_text('#!/bin/sh\ncase "$*" in "{}"*) echo "fatal: boom" >&2; exit 128;; esac\n'
                                     'exec "{}" "$@"\n'.format(failing, shutil.which("git")))
        (bin_dir / "git").chmod(0o755)
        result = self.canon_process(*args, env=dict(os.environ, PATH=str(bin_dir) + os.pathsep + os.environ["PATH"]))
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        return result.stderr

    def message(self, subcommand):
        return "canon: git {} failed in {}: fatal: boom\n".format(subcommand, self.root.resolve())

    def test_a_failing_head_lookup_ends_new_instead_of_reading_as_an_unborn_branch(self):
        self.design()
        self.commit()
        self.assertEqual(self.fails_with_git("rev-parse --verify -q HEAD", "new", "D", "x"), self.message("rev-parse"))
        self.assertFalse((self.root / "docs/designs/D002-x.md").exists())

    def test_a_failing_file_listing_ends_check_instead_of_finding_no_docs(self):
        self.design()
        self.assertEqual(self.fails_with_git("ls-files -z -co", "check"), self.message("ls-files"))

    def test_a_failing_unmerged_lookup_ends_adopt_before_any_change(self):
        self.commit()
        (self.root / "notes.md").write_text("# Notes\n\nKept notes.\n")
        status = self.git("status", "--porcelain")
        self.assertEqual(self.fails_with_git("ls-files -u", "adopt", "notes.md", "design"), self.message("ls-files"))
        self.assertEqual(self.git("status", "--porcelain"), status)

    def test_a_failing_diff_ends_affected_instead_of_finding_no_changes(self):
        self.design()
        self.commit()
        (self.root / "src/base.py").write_text("value = 2\n")
        self.assertEqual(self.fails_with_git("diff -z --name-only --no-renames HEAD", "affected"), self.message("diff"))
        self.assertEqual(self.fails_with_git("ls-files -z -o", "affected"), self.message("ls-files"))

    def test_a_failing_history_query_ends_audit_instead_of_reporting_nothing(self):
        self.design()
        self.commit()
        self.assertEqual(self.fails_with_git("log", "audit"), self.message("log"))

    def test_audit_in_a_checkout_git_cannot_read_ends_instead_of_reporting_nothing(self):
        self.design()
        self.commit()
        self.assertEqual(self.fails_with_git("", "audit"),
                         "canon: cannot read the history of HEAD in {}: fatal: boom\n".format(self.root.resolve()))


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

    def test_show_says_a_design_without_known_issues_has_none(self):
        self.design()
        self.assertEqual(self.ok("show", "D001#known-issues"), "D001 has no known issues\n")
        self.assertIn("canon: D001 has no section #nope", self.fails("show", "D001#nope"))
        self.assertIn("canon: D000 has no section #nope", self.fails("show", "D000#nope"))

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

    def test_rows_inside_code_fences_are_no_rows(self):
        fenced = "```markdown\n| Example | row |\n```\n"
        design = self.design()
        self.issues(design, "| D001-K1 | minor | A gap | P001 gate | 2020-10-01 | fix |")
        design.write_text(design.read_text() + "\n" + fenced)
        self.doc("R", "audit", body=FINDINGS.format("| R001-F1 | minor | A finding | open |\n\n" + fenced))
        self.assertNotIn("row must be", self.ok("check", "--fix"))


class FindingDispositionTest(CanonTest):
    def test_check_resolves_the_doc_a_finding_is_fixed_in_or_moved_to(self):
        self.design()
        rows = ("| R001-F1 | major | Fixed by a commit | fixed 3f9a1c2 |",
                "| R001-F2 | major | Fixed in a doc | fixed D001@r1 |",
                "| R001-F3 | minor | Fixed with a free-form note | fixed in the next release |",
                "| R001-F4 | major | Fixed in a missing doc | fixed D009@r2 |",
                "| R001-F5 | minor | Moved to a missing doc | moved C007 |",
                "| R001-F6 | minor | Unknown disposition | later |",
                "| R001-F7 | minor | Declined | declined out of scope |")
        self.doc("R", "audit", body=FINDINGS.format("\n".join(rows)))
        out = self.fails("check")
        self.assertIn("R001-F4 fixed in unknown doc `D009`", out)
        self.assertIn("R001-F5 moved to unknown doc `C007`", out)
        self.assertIn("R001-F6 disposition must start with one of open, fixed, moved, declined", out)
        for fid in ("R001-F1", "R001-F2", "R001-F3", "R001-F7"):
            self.assertNotIn(fid, out)


class DocRulesTest(CanonTest):
    def pad(self, path, lines):
        """Append filler lines until `path` holds `lines` lines, the last one ending in a newline."""
        text = path.read_text()
        text = text if text.endswith("\n") else text + "\n"
        path.write_text(text + "Filler.\n" * (lines - text.count("\n")))

    def test_line_limits_count_lines_as_wc_does_and_hint_by_design_level(self):
        design = self.design()
        part = self.design("part", parent="D001")
        agents = self.root / "AGENTS.md"
        for path, limit in ((design, 500), (part, 500), (agents, 150)):
            self.pad(path, limit)
        self.assertNotIn("lines (max", self.ok("check", "--fix"))
        for path, limit in ((design, 501), (part, 501), (agents, 151)):
            self.pad(path, limit)
        out = self.ok("check")
        self.assertIn("D001-area.md: 501 lines (max 500); split into sub-designs (D001A, D001B, ...)", out)
        self.assertIn("D001A-part.md: 501 lines (max 500); make it a new top-level design", out)
        self.assertIn("AGENTS.md: 151 lines (max 150); move detail into docs", out)

    def test_line_limits_hint_by_type_and_skip_archived_docs(self):
        concept = self.doc("C", "idea")
        plan = self.doc("P", "work")
        self.pad(concept, 501)
        self.pad(plan, 501)
        out = self.ok("check", "--fix")
        self.assertIn("C001-idea.md: 501 lines (max 500); split it into several concepts", out)
        self.assertIn("P001-work.md: 501 lines (max 500); move detail into docs/plans/P001/", out)
        self.commit()
        self.ok("archive", "C001", "dropped")
        self.assertNotIn("C001-idea.md: 501 lines", self.ok("check"))

    def test_an_adopted_concept_stays_live_and_warns_until_a_design_links_it(self):
        concept = self.doc("C", "idea", status="adopted")
        out = self.ok("check", "--fix")
        self.assertIn("WARN docs/concepts/C001-idea.md: adopted, but no design links it", out)
        self.assertNotIn("requires the doc to be in archived/", out)
        self.design(body=DESIGN.format("[C001: Idea](../concepts/C001-idea.md)"))
        self.ok("check", "--fix")
        self.assertNotIn("no design links it", self.ok("check"))
        self.set(concept, summary="")
        self.assertIn("ERROR docs/concepts/C001-idea.md: `summary` is empty", self.fails("check"))
        self.set(concept, summary="Fixture")
        self.commit()
        self.assertIn("docs/archived/concepts/C001-idea.md", self.ok("archive", "C001", "adopted"))
        self.assertNotIn("C001", self.ok("check"))

    def experiment_problems(self, out):
        return [p for p in self.problems(out) if "E001-bench.md" in p]

    def test_a_concluded_experiment_stays_live_while_the_body_of_a_live_design_or_plan_links_it(self):
        self.doc("E", "bench", body=EXPERIMENT.format(RUN, "Fast enough."), status="concluded")
        link = "[E001: Fixture](../experiments/E001-bench.md)"
        plan = self.doc("P", "work", body=PLAN.format("From " + link + "."))
        self.assertEqual(self.experiment_problems(self.ok("check", "--fix")), [])
        plan.write_text(plan.read_text().replace(link, "nothing"))
        anchored = "[E001§results: Fixture](../experiments/E001-bench.md#results)"
        design = self.design(body=DESIGN.format(anchored))
        self.assertEqual(self.experiment_problems(self.ok("check", "--fix")), [])
        design.write_text(design.read_text().replace(anchored, "nothing"))
        self.init_module("mod")
        part = self.root / self.ok("new", "D", "part", "--root", "mod").strip()
        part.write_text(part.read_text().replace("<!-- canon: What", "[E001: Fixture](../../../docs/experiments/"
                                                 "E001-bench.md). <!-- canon: What"))
        self.assertEqual(self.experiment_problems(self.ok("check", "--fix")), [])

    def test_a_concluded_experiment_warns_when_only_archived_docs_concepts_experiments_or_its_attachments_link_it(self):
        self.doc("E", "bench", body=EXPERIMENT.format(RUN, "Fast enough."), status="concluded")
        link = "[E001: Fixture](../experiments/E001-bench.md)"
        self.design(body=DESIGN.format(link))
        self.doc("P", "work", body=PLAN.format("From " + link + "."))
        self.doc("C", "idea", body="## Motivation\n\n{}\n\n## Ideas\n\nX.\n\n## Open questions\n\nNone.\n".format(link))
        self.doc("E", "other", body=EXPERIMENT.format(RUN, "As [E001: Fixture](E001-bench.md)."))
        self.create("docs/experiments/E001/raw.txt")
        self.doc("P", "data", body=PLAN.format("[Raw data](../experiments/E001/raw.txt)."))
        self.commit()
        self.ok("archive", "D001", "retired")
        self.ok("archive", "P001", "abandoned")
        self.assertEqual(self.experiment_problems(self.ok("check", "--fix")), [
            "WARN docs/experiments/E001-bench.md: concluded, but no live design or plan links it; link it or archive "
            "it as concluded"])

    def test_an_archived_concluded_experiment_that_nothing_links_does_not_warn(self):
        self.doc("E", "bench", body=EXPERIMENT.format(RUN, "Fast enough."), status="concluded")
        self.commit()
        self.ok("archive", "E001", "concluded")
        self.assertEqual(self.experiment_problems(self.ok("check")), [])

    def test_a_live_status_inside_archived_names_the_terminal_statuses(self):
        self.design()
        self.commit()
        self.ok("archive", "D001", "retired")
        archived = self.root / "docs/archived/designs/D001-area.md"
        self.set(archived, status="active")
        self.assertIn("status `active` requires the doc to be outside archived/; set one of superseded, retired",
                      self.fails("check"))

    def test_only_concluded_is_a_terminal_status_an_experiment_may_hold_live(self):
        self.doc("E", "bench", body=EXPERIMENT.format(RUN, "Fast enough."), status="concluded")
        self.commit()
        self.ok("archive", "E001", "concluded")
        self.set(self.root / "docs/archived/experiments/E001-bench.md", status="answered")
        self.doc("E", "load", body=EXPERIMENT.format(RUN, "No longer matters."), status="dropped")
        out = self.fails("check")
        self.assertIn("ERROR docs/experiments/E002-load.md: status `dropped` requires the doc to be in archived/; use "
                      "`canon.py archive`", out)
        self.assertIn("ERROR docs/archived/experiments/E001-bench.md: status `answered` requires the doc to be outside "
                      "archived/; set one of concluded, superseded, overturned, dropped", out)

    def test_check_skips_the_setup_labels_of_an_archived_dropped_experiment_only(self):
        self.doc("E", "bench", body=EXPERIMENT.format("- Commit:\n- Environment:\n- Command:",
                                                      "The question no longer matters."), status="planned")
        self.commit()
        self.ok("archive", "E001", "dropped")
        self.assertEqual(self.experiment_problems(self.ok("check")), [])
        self.set(self.root / "docs/archived/experiments/E001-bench.md", status="superseded")
        error = ("ERROR docs/archived/experiments/E001-bench.md: Setup: `{}` is empty (research lists `- Sources:` "
                 "instead)")
        self.assertCountEqual(self.experiment_problems(self.fails("check")),
                              [error.format(label) for label in ("Commit", "Environment", "Command")])

    def test_an_archived_design_does_not_warn_about_unmatched_paths(self):
        self.design(paths=["src/gone.py"])
        self.assertIn("`paths` entry `src/gone.py` matches no file", self.ok("check", "--fix"))
        self.commit()
        self.ok("archive", "D001", "retired")
        self.assertNotIn("matches no file", self.ok("check"))

    def test_a_design_with_no_implemented_does_not_warn_about_unmatched_paths(self):
        design = self.design(status="accepted", implemented=None, paths=["src/gone.py"])
        self.assertNotIn("matches no file", self.ok("check", "--fix"))
        self.set(design, status="active", implemented=1)
        self.assertIn("`paths` entry `src/gone.py` matches no file", self.ok("check", "--fix"))

    def test_new_experiment_asks_its_conclusion_for_the_answer_only(self):
        path = self.root / self.ok("new", "E", "bench").strip()
        self.assertTrue(path.read_text().endswith(
            "## Conclusion\n\n<!-- canon: The answer the Results give to the Question. -->\n"))

    def test_new_rejects_from_on_another_type_and_root_with_parent(self):
        self.design()
        self.assertIn("canon: --from only applies to plans", self.fails("new", "D", "other", "--from", "D001"))
        self.assertIn("canon: --parent puts the sub-design beside its parent; drop --root",
                      self.fails("new", "D", "part", "--parent", "D001", "--root", "."))
        self.assertEqual(sorted(p.name for p in (self.root / "docs/designs").iterdir()),
                         ["D000-project-overview.md", "D001-area.md"])

    def test_new_with_parent_needs_no_agents_md_above_the_working_directory(self):
        self.init_module("mod")
        self.ok("new", "D", "area", "--root", "mod")
        (self.root / "AGENTS.md").unlink()
        self.ok("new", "D", "part", "--parent", "D001")
        self.assertTrue((self.root / "mod/docs/designs/D001A-part.md").is_file())

    def test_archive_checks_every_terminal_condition(self):
        self.ok("new", "C", "idea")
        self.doc("P", "work", body="## Current state\n\nDone.\n\n## Slices\n\nNone.\n\n## Notes\n\nNone.\n\n"
                                   "## Log\n\nDone.\n")
        self.doc("E", "bench", body="## Question\n\nFast?\n\n## Setup\n\n- Commit: 3f9a1c2\n- Environment: x\n"
                                    "- Command: y\n\n## Results\n\nFast.\n\n## Conclusion\n\n<!-- canon: z -->\n")
        self.commit(check=False)
        out = self.fails("archive", "C001", "dropped")
        self.assertIn("ERROR docs/concepts/C001-idea.md: `summary` is empty", out)
        self.assertIn("ERROR docs/concepts/C001-idea.md: template guidance `<!-- canon: ... -->` left in the doc", out)
        self.assertIn("ERROR docs/plans/P001-work.md: plan has no slices", self.fails("archive", "P001", "done"))
        self.assertIn("Conclusion is empty", self.fails("archive", "E001", "dropped"))
        self.assertEqual(self.git("status", "--porcelain"), "")

    def test_archive_as_concluded_refuses_an_experiment_with_another_status_before_its_links(self):
        path = self.doc("E", "bench", body=EXPERIMENT.format(RUN, "Fast enough."), status="running")
        self.doc("P", "work", body=PLAN.format("From [E001: Fixture](../experiments/E001-bench.md)."))
        self.commit()
        self.refuses("E001 is running, not concluded; archive an experiment nothing absorbed as dropped",
                     "archive", "E001", "concluded")
        self.set(path, status="answered")
        self.commit()
        self.refuses("E001 is answered, not concluded; archive an experiment nothing absorbed as dropped",
                     "archive", "E001", "concluded")

    def test_archive_as_concluded_refuses_an_experiment_a_live_design_or_plan_links(self):
        self.doc("E", "bench", body=EXPERIMENT.format(RUN, "Fast enough."), status="concluded")
        link = "[E001: Fixture](../experiments/E001-bench.md)"
        design = self.design(body=DESIGN.format(link))
        self.doc("P", "work", body=PLAN.format("From " + link + "."))
        self.commit()
        self.refuses("E001 is linked by D001, P001; it stays live while a live design or plan links it",
                     "archive", "E001", "concluded")
        design.write_text(design.read_text().replace(link, "nothing"))
        self.ok("archive", "P001", "abandoned")
        self.commit()
        self.assertEqual(self.ok("archive", "E001", "concluded"),
                         "docs/experiments/E001-bench.md -> docs/archived/experiments/E001-bench.md\n")
        self.assertIn("From [E001: Fixture](../experiments/E001-bench.md).",
                      (self.root / "docs/archived/plans/P001-work.md").read_text())

    def test_archive_as_dropped_needs_a_conclusion_but_no_setup(self):
        no_setup = "- Commit:\n- Environment:\n- Command:"
        self.doc("E", "bench", body=EXPERIMENT.format(no_setup, "The question no longer matters."), status="planned")
        self.doc("E", "load", body=EXPERIMENT.format(no_setup, ""), status="planned")
        self.commit()
        error = "ERROR docs/experiments/E001-bench.md: Setup: `{}` is empty (research lists `- Sources:` instead)"
        for status in ("superseded", "overturned"):
            self.assertCountEqual(self.fails("archive", "E001", status).splitlines(),
                                  [error.format(label) for label in ("Commit", "Environment", "Command")])
        self.assertEqual(self.git("status", "--porcelain"), "")
        self.ok("archive", "E001", "dropped")
        self.assertEqual(self.fails("archive", "E002", "dropped"),
                         "ERROR docs/experiments/E002-load.md: Conclusion is empty\n")

    def test_archive_refuses_a_design_with_live_sub_designs(self):
        self.design()
        self.design("part", parent="D001")
        self.commit()
        self.assertIn("canon: D001 has live sub-designs D001A; archive them first",
                      self.fails("archive", "D001", "retired"))
        self.ok("archive", "D001A", "retired")
        self.ok("archive", "D001", "retired")

    def test_links_in_attachment_markdown_are_checked_live_and_archived_and_need_no_refs(self):
        self.design()
        self.design("other")
        self.commit()
        notes = self.root / "docs/designs/D001/notes.md"
        notes.parent.mkdir()
        notes.write_text("# Notes\n\n[D002: Other](../D002-other.md) and [Notes](#notes).\n")
        self.assertNotIn("D001/notes.md", self.ok("check"))
        self.commit()
        notes.write_text(notes.read_text() + "[gone](missing.md), [here](#nowhere) and [other](../D002-other.md).\n")
        out = self.fails("check")
        for problem in ("broken link missing.md", "missing anchor #nowhere", "link to D002 must read"):
            self.assertIn("ERROR docs/designs/D001/notes.md:4: " + problem, out)
        self.assertNotIn("missing from `refs`", out)
        self.git("checkout", "--", "docs/designs/D001/notes.md")
        self.ok("archive", "D001", "retired")
        archived = self.root / "docs/archived/designs/D001/notes.md"
        self.assertIn("[D002: Other](../../../designs/D002-other.md)", archived.read_text())
        self.commit()
        archived.write_text(archived.read_text() + "[gone](missing.md)\n")
        self.assertIn("ERROR docs/archived/designs/D001/notes.md:4: broken link missing.md", self.fails("check"))

    def test_an_unknown_entry_inside_archived_lists_only_what_archived_allows(self):
        self.create("docs/archived/guides/howto.md")
        out = self.fails("check")
        self.assertIn("ERROR docs/archived/guides: unknown entry; allowed: README.md, concepts/, designs/, plans/, "
                      "reviews/, experiments/, investigations/", out)

    def test_base_without_shared_history_ends_with_no_merge_base(self):
        self.assertIn("canon: no merge base with main", self.fails("check", "--base", "main"))
        self.commit()
        tree = self.git("hash-object", "-t", "tree", "/dev/null")
        orphan = self.git("commit-tree", tree, "-m", "unrelated")
        self.assertIn("canon: no merge base with " + orphan, self.fails("check", "--base", orphan))
        self.assertIn("canon: cannot diff against nope...HEAD", self.fails("check", "--base", "nope"))


class StatusTest(CanonTest):
    def frontmatter(self, path):
        return path.read_text().split("\n---\n", 1)[0].splitlines()

    def index_line(self, doc_id):
        return next(line for line in (self.root / "docs/README.md").read_text().splitlines()
                    if line.startswith("- [{}:".format(doc_id)))

    def test_status_moves_a_reviewed_draft_design_to_accepted_and_regenerates_the_index(self):
        design = self.design(status="draft", implemented=None, updated="2026-01-01")
        self.commit(check=False)
        self.assertIn(" · draft · ", self.index_line("D001"))
        before = self.frontmatter(design)
        self.assertEqual(self.ok("status", "D001", "accepted"), "D001: draft -> accepted\n")
        changed = {"status: draft": "status: accepted",
                   "updated: 2026-01-01": "updated: " + datetime.date.today().isoformat()}
        self.assertEqual(self.frontmatter(design), [changed.get(line, line) for line in before])
        self.assertIn(" · accepted · ", self.index_line("D001"))

    def test_status_may_skip_a_status_and_sets_a_live_concept_adopted(self):
        self.design(status="draft")
        concept = self.doc("C", "idea")
        self.doc("P", "work", reviewed=1, reviewers=["fixture"], refs=["D001"], based_on=["D001@r1"])
        self.commit(check=False)
        self.assertEqual(self.ok("status", "D001", "active"), "D001: draft -> active\n")
        self.assertEqual(self.ok("status", "C001", "adopted"), "C001: draft -> adopted\n")
        self.assertIn("status: adopted", concept.read_text())
        self.assertEqual(self.ok("status", "P001", "in-progress"), "P001: draft -> in-progress\n")

    def test_status_sets_a_complete_running_experiment_answered(self):
        self.doc("E", "bench", body=EXPERIMENT.format(RUN, "Fast enough."), status="running")
        self.commit(check=False)
        self.assertEqual(self.ok("status", "E001", "answered"), "E001: running -> answered\n")
        self.assertNotIn("E001-bench.md", self.ok("check"))

    def test_answered_needs_the_terminal_conditions_of_concluded_and_changes_no_file_without_them(self):
        path = self.doc("E", "bench", status="running", body=EXPERIMENT.format(
            "- Commit: 3f9a1c2\n- Environment: x\n- Command:", "<!-- canon: The answer. -->"))
        self.commit(check=False)
        error = "ERROR docs/experiments/E001-bench.md: "
        self.assertCountEqual(self.fails("status", "E001", "answered").splitlines(), [
            error + "Setup: `Command` is empty (research lists `- Sources:` instead)",
            error + "Conclusion is empty",
            error + "template guidance `<!-- canon: ... -->` left in the doc"])
        self.assertEqual(self.git("status", "--porcelain"), "")
        path.write_text(path.read_text().replace(
            "- Command:\n", "- Command:\n- Sources:\n  - [Spec](https://example.com/spec)\n"))
        self.commit(check=False)
        out = self.fails("status", "E001", "answered")
        self.assertNotIn("Setup:", out)
        self.assertIn(error + "Conclusion is empty", out)

    def linked_experiment(self, slug, status):
        """A complete experiment that the Notes of a live draft plan link."""
        path = self.doc("E", slug, body=EXPERIMENT.format(RUN, "Fast enough."), status=status)
        self.doc("P", "uses-" + slug, body=PLAN.format("From [{}: Fixture](../experiments/{}).".format(
            path.name.split("-", 1)[0], path.name)))
        self.commit()
        return path

    def test_status_sets_a_linked_answered_or_complete_running_experiment_concluded_and_leaves_it_live(self):
        self.linked_experiment("bench", "answered")
        self.assertEqual(self.ok("status", "E001", "concluded"), "E001: answered -> concluded\n")
        self.assertIn("status: concluded", (self.root / "docs/experiments/E001-bench.md").read_text())
        running = self.linked_experiment("load", "running")
        self.assertEqual(self.ok("status", "E002", "concluded"), "E002: running -> concluded\n")
        self.assertIn("status: concluded", running.read_text())

    def refused(self, message, *args):
        """`status args` exits 1 with `canon: message` and changes no file."""
        self.refuses(message, "status", *args)

    def test_concluded_needs_a_live_link_first_then_the_terminal_conditions_and_changes_no_file_without_them(self):
        path = self.doc("E", "bench", body=EXPERIMENT.format(RUN, "Fast enough."), status="answered")
        self.commit()
        message = "E001 needs a live design or plan that links it to become concluded"
        self.refused(message, "E001", "concluded")
        path.write_text(path.read_text().replace("Fast enough.", ""))
        self.commit(check=False)
        self.refused(message, "E001", "concluded")
        self.doc("P", "work", body=PLAN.format("From [E001: Fixture](../experiments/E001-bench.md)."))
        self.commit(check=False)
        self.assertEqual(self.fails("status", "E001", "concluded"),
                         "ERROR docs/experiments/E001-bench.md: Conclusion is empty\n")
        self.assertEqual(self.git("status", "--porcelain"), "")

    def test_status_moves_an_answered_experiment_that_only_an_archived_design_links_back_to_running(self):
        path = self.doc("E", "bench", body=EXPERIMENT.format(RUN, "Fast enough."), status="answered")
        self.design(body=DESIGN.format("[E001: Fixture](../experiments/E001-bench.md)"))
        self.commit()
        self.ok("archive", "D001", "retired")
        self.commit()
        self.assertEqual(self.ok("status", "E001", "running"), "E001: answered -> running\n")
        self.assertIn("status: running", path.read_text())

    def test_status_refuses_to_move_an_answered_experiment_a_live_plan_links_back_to_running(self):
        self.linked_experiment("bench", "answered")
        self.refused("E001 is linked by P001; a later run gets a new experiment that links it", "E001", "running")

    def test_status_refuses_an_unknown_or_archived_doc(self):
        self.design()
        self.commit()
        self.refused("unknown document D009", "D009", "active")
        self.ok("archive", "D001", "retired")
        self.commit()
        self.refused("D001 is archived", "D001", "active")

    def test_status_takes_only_the_types_statuses_and_leaves_terminal_ones_to_archive(self):
        self.design(status="draft")
        self.doc("C", "idea")
        self.commit(check=False)
        self.refused("done is not a status of D001; use one of draft, accepted, active", "D001", "done")
        self.refused("done is not a status of C001; use one of draft, adopted", "C001", "done")
        self.refused("retired is terminal for D001; use `canon.py archive`", "D001", "retired")

    def test_status_moves_only_forward_and_lists_the_later_statuses(self):
        design = self.design(status="accepted", implemented=None)
        self.commit(check=False)
        self.refused("D001 is accepted; status moves only forward, to active", "D001", "accepted")
        self.set(design, status="active", implemented=1)
        self.commit(check=False)
        self.refused("D001 is active; status moves only forward", "D001", "accepted")

    def test_only_an_answered_experiment_moves_back_and_its_refusal_names_the_move_back(self):
        path = self.doc("E", "bench", body=EXPERIMENT.format(RUN, "Fast enough."), status="answered")
        self.commit(check=False)
        for status in ("planned", "answered"):
            self.refused("E001 is answered; status moves only forward, to concluded, or back to running",
                         "E001", status)
        self.set(path, status="concluded")
        self.commit(check=False)
        self.refused("E001 is concluded; status moves only forward", "E001", "running")
        self.set(path, status="running")
        self.commit(check=False)
        self.refused("E001 is running; status moves only forward, to answered, concluded", "E001", "planned")

    def test_accepted_and_in_progress_need_the_revision_reviewed(self):
        self.design(status="draft", revision=2, reviewed=1, implemented=None)
        self.doc("P", "work", refs=["D001"], based_on=["D001@r1"])
        self.commit(check=False)
        self.refused("D001 needs `reviewed` equal to `revision` to become accepted", "D001", "accepted")
        self.refused("P001 needs `reviewed` equal to `revision` to become in-progress", "P001", "in-progress")

    def test_a_doc_with_neither_revision_nor_reviewed_is_not_reviewed(self):
        design = self.design(status="draft", implemented=None)
        design.write_text(re.sub(r"^(revision|reviewed): \d+\n", "", design.read_text(), flags=re.M))
        self.commit(check=False)
        self.refused("D001 needs `reviewed` equal to `revision` to become accepted", "D001", "accepted")

    def test_a_draft_skipping_accepted_needs_the_revision_reviewed_first(self):
        design = self.design(status="draft", revision=2, reviewed=1, implemented=1)
        self.commit(check=False)
        message = "D001 needs `reviewed` equal to `revision` to become active"
        self.refused(message, "D001", "active")
        self.set(design, implemented=2)
        self.commit(check=False)
        self.refused(message, "D001", "active")

    def test_active_needs_implemented_not_above_reviewed(self):
        design = self.design(status="accepted", implemented=None)
        message = "D001 needs `implemented` not above `reviewed` to become active"
        for fields in ({}, dict(revision=2, implemented=2), dict(revision=1, reviewed=None, implemented=1),
                       dict(implemented=0)):
            self.set(design, **fields)
            self.commit(check=False)
            self.refused(message, "D001", "active")


class IndexTest(CanonTest):
    BROKEN = "ERROR {}: index start marker with no end marker after it; fix the markers"
    REFUSED = "canon: {} has an index start marker with no end marker after it; fix the markers and rerun"

    def commit_readme(self, readme, text):
        readme.write_text(text)
        self.git("commit", "-qam", "index markers")

    def test_commands_refuse_an_index_start_marker_with_no_end_marker_after_it(self):
        self.design(status="draft", implemented=None)
        (self.root / "notes.md").write_text("# Notes\n")
        self.commit()
        readme = self.root / "docs/README.md"
        intro = readme.read_text().split(canon.INDEX_START)[0]
        for tail in ("{}\nOld.\n\n{}\nNotes to keep.\n".format(canon.INDEX_END, canon.INDEX_START),
                     "{}\nNotes to keep.\n".format(canon.INDEX_START)):
            self.commit_readme(readme, intro + tail)
            out = self.fails("check")
            self.assertIn(self.BROKEN.format("docs/README.md"), out)
            self.assertNotIn("index out of date", out)
            for args in (("check", "--fix"), ("index",), ("new", "C", "idea"), ("adopt", "notes.md", "C"),
                         ("archive", "D001", "retired"), ("status", "D001", "accepted"), ("rename", "D001", "zone"),
                         ("renumber", "D001"), ("init",)):
                self.assertIn(self.REFUSED.format("docs/README.md"), self.fails(*args), args)
                self.assertEqual(self.git("status", "--porcelain"), "", args)

    def test_a_module_index_with_no_end_marker_blocks_commands_at_the_repo_root(self):
        self.init_module("mod")
        self.commit()
        readme = self.root / "mod/docs/README.md"
        self.commit_readme(readme, readme.read_text().split(canon.INDEX_END)[0])
        self.assertIn(self.REFUSED.format("mod/docs/README.md"), self.fails("new", "C", "idea"))
        self.assertEqual(self.git("status", "--porcelain"), "")

    def test_init_refuses_a_broken_index_in_the_project_it_sets_up(self):
        readme = self.root / "mod/docs/README.md"
        readme.parent.mkdir(parents=True)
        readme.write_text("# Docs\n\n{}\nNotes to keep.\n".format(canon.INDEX_START))
        self.commit()
        self.assertIn(self.REFUSED.format("mod/docs/README.md"), self.fails("init", "--root", "mod"))
        self.assertEqual(self.git("status", "--porcelain"), "")

    def test_markers_outside_the_index_stay_as_text(self):
        readme = self.root / "docs/README.md"
        readme.write_text(readme.read_text() + "\nA stray {} after the index.\n".format(canon.INDEX_START))
        self.ok("check")
        readme.write_text("# Docs\n\nA stray {} before any index.\n".format(canon.INDEX_END))
        self.assertIn("wrote docs/README.md", self.ok("index"))
        self.assertTrue(readme.read_text().startswith(
            "# Docs\n\nA stray {} before any index.\n\n{}\n".format(canon.INDEX_END, canon.INDEX_START)))
        self.ok("check")


class InitTest(CanonTest):
    def refuses(self, message, *args):
        """`init` with `args` exits with `message` and changes no file."""
        if self.git("status", "--porcelain"):
            self.commit()
        self.assertIn(message, self.fails("init", *args))
        self.assertEqual(self.git("status", "--porcelain"), "")

    def test_init_refuses_a_canon_block_start_marker_with_no_end_marker_after_it(self):
        (self.root / "mod").mkdir()
        message = ("canon: the repo root's AGENTS.md has a canon block start marker with no end marker after it; fix "
                   "the markers and rerun `init`")
        agents = self.root / "AGENTS.md"
        (self.root / ".gitattributes").unlink()
        agents.write_text("# AGENTS.md\n\n{}\n\nNotes.\n\n{}\nOld block.\n".format(canon.AGENTS_END, canon.AGENTS_START))
        self.refuses(message)
        agents.write_text("# AGENTS.md\n\n{}\nNotes to keep.\n".format(canon.AGENTS_START))
        self.refuses(message)
        self.refuses(message, "--root", "mod")

    HOOK = ('#!/bin/sh\nc=.agents/skills/canon/scripts/canon.py\n[ -f "$c" ] && exec python3 "$c" check\n'
            'echo "canon: no canon skill installed in this checkout; install it as the canon block of AGENTS.md says" '
            '>&2\nexit 1\n')

    def test_init_at_the_repo_root_replaces_the_hook_a_project_with_a_copy_had_and_keeps_any_other(self):
        hook = self.root / ".git/hooks/pre-commit"
        self.init_module("mod")
        for old in ("#!/bin/sh\nexec python3 scripts/canon.py check\n", "#!/bin/sh\nexec python3 tools/canon.py check"):
            with self.subTest(old=old):
                hook.write_text(old)
                self.assertNotIn("pre-commit", self.ok("init", "--root", "mod"))
                self.assertIn("kept the existing pre-commit hook", self.ok("init", "--root", "mod", "--hook"))
                self.assertEqual(hook.read_text(), old)
                self.assertIn("updated .git/hooks/pre-commit", self.ok("init").splitlines())
                self.assertEqual(hook.read_text(), self.HOOK)
        other = "#!/bin/sh\nexec python3 scripts/canon.py check\nmake lint\n"
        hook.write_text(other)
        self.assertNotIn("pre-commit", self.ok("init"))
        self.assertIn("kept the existing pre-commit hook; add `canon.py check` to it\n", self.ok("init", "--hook"))
        self.assertEqual(hook.read_text(), other)

    def test_init_hook_writes_a_hook_that_runs_check_through_the_installed_canon_py_or_says_to_install_it(self):
        self.repository_without_docs()
        self.ok("init", "--hook")
        hook = self.root / ".git/hooks/pre-commit"
        self.assertEqual(hook.read_text(), self.HOOK)
        self.assertEqual(stat.S_IMODE(hook.stat().st_mode), 0o755)
        self.create("docs/stray/x.md")
        self.git("add", "-A")
        result = self.run_here("git", "commit", "-qm", "stray")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("ERROR docs/stray: unknown entry", result.stderr)
        self.git("rm", "-rq", "--cached", "docs/stray")
        shutil.rmtree(str(self.root / "docs/stray"))
        self.git("commit", "-qm", "setup")
        (self.root / INSTALL).unlink()
        self.create("src/a.py")
        self.git("add", "-A")
        result = self.run_here("git", "commit", "-qm", "without the link")
        self.assertEqual((result.returncode, result.stderr),
                         (1, "canon: no canon skill installed in this checkout; install it as the canon block of "
                             "AGENTS.md says\n"))

    def test_init_that_cannot_write_the_hook_finishes_and_says_how_to_add_it(self):
        self.repository_without_docs()
        hooks = self.root / ".git/hooks"
        shutil.rmtree(str(hooks))
        hooks.write_text("a file where the hooks directory belongs\n")
        out = self.ok("init", "--hook")
        self.assertIn("warning: cannot write the pre-commit hook: ", out)
        self.assertIn("; rerun `canon.py init --hook` where .git is writable\n", out)
        self.assertIn("created AGENTS.md", out)
        self.assertIn(canon.INDEX_START, (self.root / "docs/README.md").read_text())

    @unittest.skipIf(os.name == "nt" or os.geteuid() == 0, "file modes stop only a non-root POSIX user")
    def test_init_that_cannot_write_the_hook_warns_under_hook_or_for_an_old_hook_and_finishes(self):
        self.repository_without_docs()
        hooks = self.root / ".git/hooks"
        hooks.chmod(0o555)
        self.addCleanup(hooks.chmod, 0o755)
        out = self.ok("init", "--hook")
        self.assertRegex(out, r"(?m)^warning: cannot write the pre-commit hook: .+; rerun `canon\.py init --hook` "
                              r"where \.git is writable$")
        self.assertIn("created AGENTS.md", out)
        self.assertIn(canon.INDEX_START, (self.root / "docs/README.md").read_text())
        self.assertNotIn("pre-commit", self.ok("init"))
        hooks.chmod(0o755)
        hook = hooks / "pre-commit"
        hook.write_text("#!/bin/sh\nexec python3 scripts/canon.py check\n")
        hook.chmod(0o555)
        self.assertRegex(self.ok("init"), r"(?m)^warning: cannot write the pre-commit hook: .+; rerun "
                                          r"`canon\.py init --hook` where \.git is writable$")
        self.assertEqual(hook.read_text(), "#!/bin/sh\nexec python3 scripts/canon.py check\n")

    @unittest.skipIf(os.name == "nt" or os.geteuid() == 0, "file modes stop only a non-root POSIX user")
    def test_init_hook_keeps_an_existing_hook_it_cannot_read(self):
        self.repository_without_docs()
        hook = self.root / ".git/hooks/pre-commit"
        hook.write_text("#!/bin/sh\nexit 0\n")
        hook.chmod(0)
        out = self.ok("init", "--hook")
        self.assertIn("kept the existing pre-commit hook; add `canon.py check` to it\n", out)
        self.assertNotIn("warning", out)

    @unittest.skipIf(os.name == "nt", "the stand-in git is a shell script")
    def test_init_whose_git_cannot_name_the_hook_path_finishes_and_says_how_to_add_it(self):
        self.repository_without_docs()
        bin_dir = self.tmpdir()
        (bin_dir / "git").write_text('#!/bin/sh\ncase "$*" in *--git-path*) exit 128;; esac\nexec {} "$@"\n'
                                     .format(shutil.which("git")))
        (bin_dir / "git").chmod(0o755)
        result = self.canon_process("init", env=dict(os.environ, PATH=str(bin_dir)))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("pre-commit", result.stdout)
        result = self.canon_process("init", "--hook", env=dict(os.environ, PATH=str(bin_dir)))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("warning: cannot write the pre-commit hook: git rev-parse --git-path hooks/pre-commit failed; "
                      "rerun `canon.py init --hook` where .git is writable\n", result.stdout)
        self.assertIn(canon.INDEX_START, (self.root / "docs/README.md").read_text())

    def test_init_refuses_a_root_that_is_not_a_directory_inside_the_repository(self):
        outside = self.tmpdir()
        for root in ("mod", "src/base.py", str(outside)):
            self.refuses("canon: --root {} is not a directory inside the repository".format(root), "--root", root)
        self.assertFalse((self.root / "mod").exists())
        self.assertEqual(list(outside.iterdir()), [])

    def test_init_writes_no_copy_and_the_canon_block_names_the_installed_canon_py_and_how_to_install_it(self):
        self.repository_without_docs()
        self.ok("init")
        self.assertEqual([p.relative_to(self.root).as_posix() for p in self.root.rglob("canon.py")], [INSTALL])
        agents = (self.root / "AGENTS.md").read_text()
        self.assertIn("\n- Tool: `scripts/canon.py` of the `canon` skill installed in this project, "
                      "`.agents/skills/canon/scripts/canon.py` as `npx skills` installs it, canon version {} or later, "
                      "run from the repo root (`-h` lists commands).".format(canon.CANON_VERSION), agents)
        self.assertIn("`npx skills add BigTailFox/skills@<tag> -s '*' -a claude-code -a codex -a cursor -y`", agents)
        self.assertIn("`<tag>` is the name after `refs/tags/` on the first line of `git ls-remote --tags --refs "
                      "--sort=-v:refname https://github.com/BigTailFox/skills 'v*'`", agents)
        self.assertIn("`npx skills experimental_install`", agents)
        readme = (self.root / "docs/README.md").read_text()
        self.assertIn("`canon.py find <words>`", readme)
        self.assertNotIn("python3", readme)
        self.assertEqual(self.canon("init", "--script", "x").returncode, 2)

    OLD_COPY_WARNING = ("the project no longer keeps a copy of canon.py; remove {0} and replace `python3 {0}` where files "
                "still name it, such as CI and each `docs/README.md`")

    def old_copy(self, rel, text='#!/usr/bin/env python3\nCANON_VERSION = "18"\n'):
        """A tracked file at `rel` holding `text`, by default a copy of canon.py version 18, committed."""
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        self.commit()
        return path

    def test_init_and_check_warn_of_a_tracked_old_copy_and_leave_it_to_the_user(self):
        agents = self.root / "AGENTS.md"
        agents.write_text(re.sub(r"`scripts/canon.py` of .*?\(`-h` lists commands\)\.",
                                 "`python3 scripts/canon.py` from the repo root (`-h` lists commands).",
                                 agents.read_text()))
        copy = self.old_copy("scripts/canon.py")
        self.init_module("mod")
        self.git("add", "-A")
        self.git("commit", "-qm", "module")
        out = self.ok("init")
        self.assertTrue(out.startswith("warning: {}\nupdated AGENTS.md\n".format(self.OLD_COPY_WARNING.format(
            "scripts/canon.py"))), out)
        self.assertEqual(copy.read_text(), '#!/usr/bin/env python3\nCANON_VERSION = "18"\n')
        self.assertNotIn("python3 scripts/canon.py", agents.read_text())
        warning = "WARN scripts/canon.py: " + self.OLD_COPY_WARNING.format("scripts/canon.py")
        out = self.ok("check")
        problems = self.problems(out)
        self.assertIn(warning, problems)
        self.assertIn(", 0 errors, {} warnings".format(len(problems)), out)
        self.assertNotIn("copy", self.ok("init", "--root", "mod"))
        self.git("rm", "-q", "scripts/canon.py")
        out = self.ok("check")
        self.assertEqual(self.problems(out), [p for p in problems if p != warning])
        self.assertIn(", 0 errors, {} warnings".format(len(problems) - 1), out)

    @unittest.skipIf(os.name == "nt", "symlinks need privileges on Windows")
    def test_an_old_copy_is_a_tracked_canon_py_with_the_version_line_no_installed_skill_file_nor_the_canon_source(self):
        copy = '#!/usr/bin/env python3\nCANON_VERSION = "18"\n'
        self.git("add", "-f", INSTALL)
        for rel, name in (("tools/canon", "canon"), ("tools/other", "other")):
            self.create(rel + "/SKILL.md")
            (self.root / rel / "SKILL.md").write_text("---\nname: {}\ndescription: Fixture.\n---\n".format(name))
            self.create(rel + "/scripts/canon.py")
            (self.root / rel / "scripts/canon.py").write_text(copy)
        self.create(".agents/skills/canon-x/scripts/canon.py")
        (self.root / ".agents/skills/canon-x/scripts/canon.py").write_text(copy)
        (self.root / "bin").mkdir()
        (self.root / "bin/canon.py").symlink_to("../.agents/skills/canon-x/scripts/canon.py")
        self.old_copy("lib/canon.py", text="print('a project script')\n")
        (self.root / "scripts").mkdir()
        (self.root / "scripts/canon.py").write_text(copy)
        message = self.OLD_COPY_WARNING.format("tools/other/scripts/canon.py")
        self.assertEqual(self.ok("init").splitlines()[:1], ["warning: " + message])
        self.assertEqual([p for p in self.problems(self.ok("check")) if "copy" in p],
                         ["WARN tools/other/scripts/canon.py: " + message])

    def test_a_canon_py_at_the_repo_root_is_an_old_copy_whatever_lies_above_the_repository(self):
        outer = self.tmpdir()
        (outer / "SKILL.md").write_text("---\nname: canon\ndescription: Fixture.\n---\n")
        self.root = outer / "scripts"
        self.root.mkdir()
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.name", "canon test")
        self.git("config", "user.email", "canon@example.invalid")
        self.ok("init")
        self.old_copy("canon.py")
        self.assertIn("WARN canon.py: " + self.OLD_COPY_WARNING.format("canon.py"), self.problems(self.ok("check")))

    def test_the_canon_block_exempts_docs_only_changes_that_bump_no_revision_from_a_tier(self):
        self.repository_without_docs()
        self.ok("init")
        self.assertIn("\n- State each change's tier (L0, L1, L2) before starting, unless it touches only docs that no "
                      "design's `paths` names and bumps no revision. Designs and plans pass the review gate defined by "
                      "the `canon` skill.\n", (self.root / "AGENTS.md").read_text())


class AdoptTest(CanonTest):
    def test_a_rewritten_link_target_stays_percent_encoded(self):
        (self.root / "other doc.md").write_text("# Other\n")
        (self.root / "notes.md").write_text("# Notes\n\nSee [Other](other%20doc.md#other).\n")
        self.ok("adopt", "notes.md", "design")
        self.assertIn("[Other](../../other%20doc.md#other)", (self.root / "docs/designs/D001-notes.md").read_text())

    def test_a_rewritten_link_target_encodes_only_what_a_link_cannot_hold(self):
        self.create("my notes/b.md", "设计 (1).md")
        (self.root / "my notes/a.md").write_text("# A\n\nSee [B](b.md) and [Draft](../%E8%AE%BE%E8%AE%A1%20%281%29.md).\n")
        self.ok("adopt", "my notes/a.md", "design")
        self.assertIn("See [B](../../my%20notes/b.md) and [Draft](../../设计%20%281%29.md).",
                      (self.root / "docs/designs/D001-a.md").read_text())

    def test_links_follow_the_h1_adopt_rewrites_and_a_prepended_h1_shifts_no_anchor(self):
        (self.root / "notes.md").write_text("# Notes\n\n## Usage\n\nBack to [the top](#notes).\n")
        (self.root / "plain.md").write_text("## Usage\n\nPlain.\n")
        (self.root / "index.md").write_text("[N](notes.md#notes), [U](notes.md#usage), [P](plain.md#usage).\n")
        self.ok("adopt", "notes.md", "design")
        self.ok("adopt", "plain.md", "design")
        self.assertEqual((self.root / "index.md").read_text(),
                         "[D001§d001-notes: N](docs/designs/D001-notes.md#d001-notes), "
                         "[D001§usage: U](docs/designs/D001-notes.md#usage), "
                         "[D002§usage: P](docs/designs/D002-plain.md#usage).\n")
        self.assertIn("Back to [the top](#d001-notes).", (self.root / "docs/designs/D001-notes.md").read_text())

    def test_adopt_shifts_a_numbered_anchor_and_ignores_frontmatter_and_empty_anchors(self):
        (self.root / "usage.md").write_text("---\n# generated\ntitle: Usage\n---\n# Usage\n\n## Usage\n\nText.\n")
        (self.root / "star.md").write_text("# ★\n")
        (self.root / "index.md").write_text("[Top](usage.md#usage), [Section](usage.md#usage-1), [All](usage.md), "
                                            "[Star](star.md).\n")
        self.ok("adopt", "usage.md", "design")
        self.ok("adopt", "star.md", "design")
        self.assertEqual((self.root / "index.md").read_text(),
                         "[D001§d001-usage: Top](docs/designs/D001-usage.md#d001-usage), "
                         "[D001§usage: Section](docs/designs/D001-usage.md#usage), "
                         "[D001: All](docs/designs/D001-usage.md), [D002: Star](docs/designs/D002-star.md).\n")


class ProjectOverviewTest(CanonTest):
    def test_init_creates_a_draft_d000_that_check_only_warns_about(self):
        self.repository_without_docs()
        self.assertIn("created " + self.OVERVIEW, self.ok("init"))
        text = (self.root / self.OVERVIEW).read_text()
        self.assertEqual([line.rstrip() for line in text.split("---\n")[1].splitlines()],
                         ["status: draft", "created: " + canon.today(), "updated: " + canon.today(), "revision: 1",
                          "modules: []", "summary:", "refs: []", "owns: [architecture]", "paths: []"])
        headings = re.findall(r"(?m)^#+ .*$", text)
        self.assertEqual(headings, ["# D000: Project overview", "## Goals", "## Spec", "### Capabilities",
                                    "### Modules", "### Dependencies", "### Glossary", "## Decisions"])
        sections = dict(zip(headings, re.split(r"(?m)^#+ .*$", text)[1:]))
        for heading in headings[1:]:
            self.assertIn("<!-- canon:", sections[heading], heading)
        self.assertIn("| Capability | Modules | Design |\n|---|---|---|\n", sections["### Capabilities"])
        self.assertIn(self.MODULES, sections["### Modules"])
        self.assertIn("`### Standards`", sections["### Glossary"])
        self.assertIn("`| Standard | Design |`", sections["### Glossary"])
        self.assertEqual([line for line in self.ok("check").splitlines() if self.OVERVIEW in line],
                         ["WARN {}: `summary` is empty".format(self.OVERVIEW),
                          "WARN {}: template guidance `<!-- canon: ... -->` left in the doc".format(self.OVERVIEW)])
        self.assertEqual(self.ok("init"), "canon init: nothing to do\n")

    def test_init_of_a_module_creates_no_d000_and_no_flag_skips_it(self):
        self.repository_without_docs()
        result = self.canon("init", "--no-architecture")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("unrecognized arguments: --no-architecture", result.stderr)
        self.init_module("mod")
        self.assertTrue((self.root / "mod/AGENTS.md").is_file())
        self.assertTrue((self.root / "mod/docs/README.md").is_file())
        self.assertEqual(list(self.root.glob("**/D000-*")), [])

    def test_the_agents_block_links_d000_and_the_index(self):
        agents = (self.root / "AGENTS.md").read_text()
        self.assertIn("]({})".format(self.OVERVIEW), agents)
        self.assertIn("](docs/README.md)", agents)
        self.assertNotRegex(self.ok("check"), r"(?m)^(ERROR|WARN) AGENTS\.md")

    def test_init_creates_d000_when_only_an_archived_design_owns_architecture(self):
        (self.root / self.OVERVIEW).unlink()
        self.design("architecture")
        self.ok("archive", "D001", "retired")
        self.assertIn("created " + self.OVERVIEW, self.ok("init"))
        self.ok("check")

    def test_d000_cannot_be_archived(self):
        self.commit()
        self.assertIn("D000", self.fails("archive", "D000", "retired"))
        self.assertEqual(self.git("status", "--porcelain"), "")

    def test_d000_keeps_its_file_name(self):
        self.commit()
        message = "D000 keeps its file name, which the AGENTS.md block links"
        self.refuses(message, "rename", "D000", "overview")
        self.refuses(message, "rename", "D000", "Not_A_Slug")

    def test_only_a_d000_in_a_module_s_docs_is_renumbered(self):
        self.commit()
        message = "D000 is the project overview every project keeps; renumber only a D000 in a module's docs"
        self.refuses(message, "renumber", "D000")
        self.init_module("mod")
        module_overview = self.root / "mod" / self.OVERVIEW
        module_overview.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(self.root / self.OVERVIEW, module_overview)
        self.commit(check=False)
        self.refuses(message, "renumber", self.OVERVIEW)
        self.assertEqual(self.ok("renumber", "mod/" + self.OVERVIEW).splitlines()[0], "D000 -> D001")


class OverviewMoveTest(CanonTest):
    """A project set up by an older canon.py, whose design owning `architecture` the upgrade moves to D000."""
    ARCHITECTURE = ("## Goals\n\nFixture goals.\n\n## Spec\n\nThe module map.\n\n![Module map](D003/map.svg)\n\n"
                    "### Modules\n\n" + CanonTest.MODULES + "| base | src/ | Fixture | src/base.py | none |\n\n"
                    "## Decisions\n\nFixture decisions.\n")

    def setUp(self):
        super().setUp()
        (self.root / self.OVERVIEW).unlink()
        agents = self.root / "AGENTS.md"
        agents.write_text(re.sub(r"\[D000: [^]]*\]\([^)]*\)", "docs/README.md", agents.read_text()))

    def commit(self, check=True):
        """Commit; until `init` has moved a design to D000, `check` may fail for the missing D000 alone."""
        if check and not (self.root / self.OVERVIEW).exists():
            errors = [line for line in self.fails("check", "--fix").splitlines() if line.startswith("ERROR")]
            self.assertEqual(errors, [NO_OVERVIEW])
            check = False
        super().commit(check)

    def project(self, **fields):
        self.design("a")
        self.design("b")
        values = dict(revision=2, reviewed=2, implemented=2, paths=["src/base.py"], body=self.ARCHITECTURE)
        values.update(fields)
        self.issues(self.design("architecture", **values), "| D003-K1 | minor | A gap | R001-F1 | 2020-10-01 | fix |")
        self.design("part", parent="D003")
        (self.root / "docs/designs/D003").mkdir()
        (self.root / "docs/designs/D003/map.svg").write_text("<svg/>\n")
        self.doc("P", "first", refs=["D001"], based_on=["D001@r1"])
        body = "Implements [D003: Fixture](../designs/D003-architecture.md).\n\n" + PLAN.format("None.")
        plan = self.doc("P", "upgrade", body=body, refs=["D003"], based_on=["D003@r2"])
        review = self.doc("R", "audit", body=FINDINGS.format("| R001-F1 | major | A spec fix | moved D003 |"))
        self.commit()
        return plan, review

    def test_init_moves_the_design_owning_architecture_to_d000(self):
        plan, review = self.project()
        out = self.ok("init")
        self.assertIn("moved docs/designs/D003-architecture.md -> " + self.OVERVIEW, out)
        overview = (self.root / self.OVERVIEW).read_text()
        self.assertRegex(overview, r"(?m)^# D000: Project overview$")
        self.assertIn("status: active", overview)
        self.assertIn("| D000-K1 |", overview)
        self.assertNotIn("D003", overview)
        self.assertTrue((self.root / "docs/designs/D000A-part.md").is_file())
        self.assertTrue((self.root / "docs/designs/D000/map.svg").is_file())
        self.assertEqual(list(self.root.glob("docs/designs/D003*")), [])
        self.assertIn("based_on: [D000@r2]", plan.read_text())
        self.assertIn("[D000: Fixture](../designs/D000-project-overview.md)", plan.read_text())
        self.assertIn("| moved D000 |", review.read_text())

    def test_init_carries_links_to_the_h1_and_to_headings_whose_numbered_anchor_shifts(self):
        self.project(body=self.ARCHITECTURE.replace("## Decisions", "## Glossary\n\nTerms.\n\n## Decisions"))
        concept = self.doc("C", "links", body="## Motivation\n\nSee [D003§glossary: terms]"
                                              "(../designs/D003-architecture.md#glossary) and [D003§d003-fixture: the "
                                              "map](../designs/D003-architecture.md#d003-fixture).\n\n## Ideas\n\n"
                                              "None.\n\n## Open questions\n\nNone.\n")
        self.ok("init")
        self.assertIn("See [D000§glossary-1: terms](../designs/D000-project-overview.md#glossary-1) and "
                      "[D000§d000-project-overview: the map](../designs/D000-project-overview.md#d000-project-overview)",
                      concept.read_text())
        self.assertIn("### Glossary", (self.root / self.OVERVIEW).read_text())

    def test_init_appends_the_subsections_d000_lacks_at_the_end_of_its_spec(self):
        self.project()
        self.ok("init")
        path = self.root / self.OVERVIEW
        overview = path.read_text()
        self.assertEqual(re.findall(r"(?m)^#+ .*$", overview),
                         ["# D000: Project overview", "## Goals", "## Spec", "### Modules", "### Capabilities",
                          "### Dependencies", "### Glossary", "## Decisions", "## Known issues"])
        spec = overview.split("\n## Spec\n", 1)[1].split("\n## Decisions\n", 1)[0]
        self.assertLess(spec.index("| base | src/ |"), spec.index("### Capabilities"))
        for name in ("Capabilities", "Dependencies", "Glossary"):
            self.assertIn("<!-- canon:", spec.split("### " + name + "\n", 1)[1].split("\n### ", 1)[0], name)
        self.assertNotIn("<!-- canon:", spec.split("### Modules\n", 1)[1].split("\n### ", 1)[0])
        self.assertEqual(self.problems(self.fails("check")),
                         ["ERROR {}: template guidance `<!-- canon: ... -->` left in the doc".format(self.OVERVIEW)])
        path.write_text(re.sub(r"<!-- canon:.*?-->", "Filled.", overview, flags=re.S))
        self.ok("check", "--fix")

    def test_a_draft_design_owning_architecture_moves_as_a_draft_whose_guidance_only_warns(self):
        self.project(status="draft", reviewed=None, implemented=None)
        self.ok("init")
        self.assertIn("status: draft", (self.root / self.OVERVIEW).read_text())
        self.assertEqual(self.problems(self.ok("check")),
                         ["WARN {}: template guidance `<!-- canon: ... -->` left in the doc".format(self.OVERVIEW)])

    def test_a_filled_d000_is_no_deleted_doc_while_other_deleted_designs_still_are(self):
        self.project()
        before = self.git("rev-parse", "HEAD")
        old_size = len(self.git("show", "HEAD:docs/designs/D003-architecture.md"))
        self.ok("init")
        path = self.root / self.OVERVIEW
        filler = "".join("- Fact {} that the overview records about the fixture.\n".format(i) for i in range(60))
        path.write_text(re.sub(r"<!-- canon:.*?-->", "Filled.", path.read_text(), flags=re.S)
                        .replace("\n## Decisions\n", "\n" + filler + "\n## Decisions\n"))
        self.assertGreater(len(path.read_text()), 2 * old_size)
        self.assertIn("D\tdocs/designs/D003-architecture.md", self.git("diff", "-M", "--name-status", "HEAD"))
        self.assertNotIn("deleted", self.ok("check"))
        self.commit()
        self.assertNotIn("deleted", self.ok("check", "--base", before))
        self.assertEqual(self.ok("new", "D", "x").strip(), "docs/designs/D004-x.md")
        self.git("rm", "-q", "docs/designs/D002-b.md")
        self.assertIn("D002 was deleted", self.fails("check"))
        self.commit(check=False)
        out = self.fails("check", "--base", before)
        self.assertIn("D002 was deleted", out)
        self.assertNotIn("D003 was deleted", out)

    def test_without_d000_the_design_owning_architecture_cannot_be_deleted(self):
        self.project()
        self.git("rm", "-q", "docs/designs/D003-architecture.md")
        self.assertIn("D003 was deleted", self.fails("check"))

    def test_init_moves_only_the_live_design_owning_architecture_and_only_once(self):
        self.project()
        self.design("old-architecture", owns=["architecture"])
        self.ok("archive", "D004", "retired")
        self.commit()
        archived = self.root / "docs/archived/designs/D004-old-architecture.md"
        kept = archived.read_text()
        self.assertIn("moved docs/designs/D003-architecture.md -> " + self.OVERVIEW, self.ok("init"))
        self.assertEqual(archived.read_text(), kept)
        docs = {p: p.read_text() for p in (self.root / "docs").rglob("*") if p.is_file()}
        self.assertEqual(self.ok("init"), "canon init: nothing to do\n")
        self.assertEqual({p: p.read_text() for p in (self.root / "docs").rglob("*") if p.is_file()}, docs)
        self.commit(check=False)
        self.git("rm", "-q", str(archived.relative_to(self.root)))
        self.assertIn("D004 was deleted", self.fails("check"))

    def refuses(self, *names):
        out = self.fails("init")
        for name in names:
            self.assertIn(name, out)
        self.assertEqual(self.git("status", "--porcelain"), "")
        return out

    def test_init_refuses_a_sub_design_or_module_design_owning_architecture_before_changing_any_file(self):
        self.design()
        sub = self.design("architecture", parent="D001")
        self.commit()
        out = self.refuses("D001A", "docs/designs/D001A-architecture.md")
        self.assertIn("take `architecture` out of its `owns` and rerun `init`", out)
        self.set(sub, owns=["part"])
        self.init_module("mod")
        module = self.ok("new", "D", "architecture", "--root", "mod").strip()
        self.set(self.root / module, owns=["architecture"], summary="Fixture")
        self.commit(check=False)
        out = self.refuses(module)
        self.assertIn("take `architecture` out of its `owns` and rerun `init`", out)
        self.design("other-architecture", owns=["architecture"])
        self.commit(check=False)
        self.assertIn("all but one", self.refuses(module, "D003"))

    def test_init_refusing_to_move_unclear_or_id_sharing_sub_designs_suggests_no_base(self):
        architecture = self.design("architecture", paths=["src/base.py"])
        part = self.design("part", parent="D001")
        rival = architecture.with_name("D001-other.md")
        rival.write_text(architecture.read_text().replace("owns: [architecture]", "owns: [other]"))
        out = self.fails("init")
        self.assertIn("cannot tell which D001 owns docs/designs/D001A-part.md; link each sub-design from its parent "
                      "design, then rerun", out)
        self.assertNotIn("--base", out)
        rival.unlink()
        part.with_name("D001A-copy.md").write_text(part.read_text().replace("owns: [part]", "owns: [copy]"))
        out = self.fails("init")
        self.assertIn("sub-designs of D001 share an id", out)
        self.assertNotIn("--base", out)


class WhichTest(CanonTest):
    def test_a_module_design_governs_only_the_files_of_its_module(self):
        self.init_module("mod")
        design = self.root / self.ok("new", "D", "part", "--root", "mod").strip()
        self.set(design, summary="Fixture", owns=["part"], paths=["**"])
        self.create("mod/x.py", "mod/README.md")
        lines = self.ok("which", "mod/x.py", "src/base.py", "mod/README.md").splitlines()
        self.assertRegex(lines[0], r"^mod/x\.py: D001 mod/docs/designs/D001-part\.md - Fixture")
        self.assertEqual(lines[1:], ["src/base.py: no design", "mod/README.md: doc"])


class HelpTest(CanonTest):
    def help(self, *command):
        result = self.canon_process(*command, "-h", env=dict(os.environ, COLUMNS="200"))
        self.assertEqual(result.returncode, 0, result.stderr)
        return " ".join(result.stdout.split())

    def test_a_commands_help_says_what_it_does_and_which_values_it_accepts(self):
        archive = self.help("archive")
        for letter, info in canon.TYPES.items():
            self.assertIn("{}: {}".format(letter, ", ".join(info["terminal"])), archive)
        self.assertIn("E: concluded, superseded, overturned, dropped", archive)
        self.assertIn("status move a doc's status forward, or an answered experiment back to running, and check the "
                      "move", self.help())
        self.assertIn("C: draft, adopted; D: draft, accepted, active; P: draft, accepted, in-progress; R: open; "
                      "E: planned, running, answered, concluded; I: open", self.help("status"))
        end = self.help("trace", "end")
        for kinds, outcomes in [("other kinds", canon.OUTCOMES)] + list(canon.KIND_OUTCOMES.items()):
            self.assertIn("{}: {}".format(kinds, ", ".join(outcomes)), end)
        self.assertIn("--input FILE|- a gate's, follow-up's or code review's dispositions", end)
        self.assertIn("`skill` for an installed skill file", self.help("which"))
        self.assertIn("`no design` for other files", self.help("which"))
        self.assertIn("only when `check` asks for it", self.help("renumber"))
        self.assertIn("an open doc other than a concept, active design or concluded experiment is idle",
                      self.help("audit"))


class ProjectDocsTest(CanonTest):
    """READMEs, AGENTS.md and the other project docs, and the files under a docs root, are docs, never code."""
    DOCS = ["README.md", "src/a/readme.rst", "AGENTS.md", "CLAUDE.md", "LICENSE", "NOTICE", "CHANGELOG.md",
            "CONTRIBUTING.md", "docs/README.md", "docs/assets/x.png"]

    def test_which_prints_doc_for_every_doc_under_a_design_holding_everything(self):
        self.design(paths=["**"])
        self.create(*self.DOCS, "src/a/x.py")
        lines = self.ok("which", *self.DOCS, "src/a/x.py").splitlines()
        self.assertEqual(lines[:-1], [name + ": doc" for name in self.DOCS])
        self.assertRegex(lines[-1], r"^src/a/x\.py: D001 docs/designs/D001-area\.md - Fixture")

    def test_a_doc_by_its_name_has_a_doc_extension_or_none(self):
        self.design(paths=["src/**"])
        docs = ["README.zh.md", "LICENSE-MIT", "src/a/readme.rst", "SECURITY.md", "CODE_OF_CONDUCT.md", "COPYING",
                "src/Readme.MARKDOWN", "src/license-apache.txt", "CHANGELOG.adoc", "contributing.org"]
        code = ["src/agents.py", "src/license.py"]
        self.create(*docs, *code, "notice.ts", "README.html")
        lines = self.ok("which", *docs, *code, "notice.ts", "README.html").splitlines()
        self.assertEqual(lines[:len(docs)], [name + ": doc" for name in docs])
        for name, line in zip(code, lines[len(docs):]):
            self.assertTrue(line.startswith(name + ": D001 docs/designs/D001-area.md - Fixture"), line)
        self.assertEqual(lines[len(docs) + len(code):], ["notice.ts: no design", "README.html: no design"])

    def test_a_design_governs_a_doc_only_through_an_entry_equal_to_its_path(self):
        design = self.design(paths=["src/auth/**"])
        self.create("src/auth/README.md", "src/auth/x.py")
        self.assertEqual(self.ok("which", "src/auth/README.md"), "src/auth/README.md: doc\n")
        self.assertEqual(self.ok("affected", "src/auth/README.md"), "no design governs the changed files\n")
        self.set(design, paths=["src/auth/**", "src/auth/README.md"])
        self.assertRegex(self.ok("which", "src/auth/README.md"), r"^src/auth/README\.md: D001 docs/designs/D001-")
        self.assertRegex(self.ok("affected", "src/auth/README.md"),
                         r"^D001 active docs/designs/D001-area\.md - Fixture\n  src/auth/README\.md\n")

    def test_a_commit_changing_only_docs_the_paths_do_not_list_is_no_unchecked_commit(self):
        self.design(paths=["src/auth/**"])
        self.create("src/auth/README.md", "src/auth/x.py")
        self.commit()
        self.edit_commit("src/auth/README.md")
        self.assertNotIn("commits since", self.ok("audit"))
        self.edit_commit("src/auth/README.md", "src/auth/x.py")
        self.assertRegex(self.ok("audit"), r"  1 commits since [0-9a-f]+  D001 ")

    def test_a_commit_changing_a_doc_the_paths_list_is_an_unchecked_commit(self):
        self.design(paths=["src/auth/**", "src/auth/README.md"])
        self.create("src/auth/README.md", "src/auth/x.py")
        self.commit()
        self.edit_commit("src/auth/README.md")
        self.assertRegex(self.ok("audit"), r"  1 commits since [0-9a-f]+  D001 ")

    def test_renaming_a_governed_file_to_a_doc_is_an_unchecked_commit(self):
        self.design(paths=["src/auth/**"])
        self.create("src/auth/notes.txt")
        self.commit()
        self.git("mv", "src/auth/notes.txt", "src/auth/README.md")
        self.git("commit", "-qm", "docs: notes become the README")
        self.assertRegex(self.ok("audit"), r"  1 commits since [0-9a-f]+  D001 ")

    def test_a_merge_is_an_unchecked_commit_unless_its_resolution_changes_only_docs_the_paths_do_not_list(self):
        self.design(paths=["src/auth/**"])
        self.create("src/auth/README.md", "src/auth/x.py")
        self.commit()
        readme = self.root / "src/auth/README.md"
        self.git("checkout", "-qb", "side")
        readme.write_text("side\n")
        self.git("commit", "-qam", "docs: side")
        self.git("checkout", "-q", "main")
        readme.write_text("main\n")
        self.git("commit", "-qam", "docs: main")
        self.assertNotEqual(self.run_here("git", "merge", "-q", "side").returncode, 0)
        readme.write_text("merged\n")
        self.git("commit", "-qam", "Merge branch 'side'")
        self.assertNotIn("commits since", self.ok("audit"))
        self.git("checkout", "-qb", "code")
        self.edit_commit("src/auth/x.py")
        self.git("checkout", "-q", "main")
        self.edit_commit("src/auth/README.md")
        self.git("merge", "-q", "--no-edit", "code")
        self.assertRegex(self.ok("audit"), r"  2 commits since [0-9a-f]+  D001 ")

    def clean_merge(self, ours, theirs, message="edit"):
        """Edit `theirs` on a side branch and `ours` on main, each in a commit with `message`, and merge the side
        branch, which no conflict stops."""
        self.git("checkout", "-qb", "side")
        self.edit_commit(theirs)
        self.git("commit", "-q", "--amend", "-m", message)
        self.git("checkout", "-q", "main")
        self.edit_commit(ours)
        self.git("commit", "-q", "--amend", "-m", message)
        self.git("merge", "-q", "--no-edit", "side")
        self.assertEqual(self.git("diff-tree", "-c", "--name-only", "--no-commit-id", "HEAD"), "")

    def test_a_clean_merge_of_branches_that_changed_only_docs_the_paths_do_not_list_is_no_unchecked_commit(self):
        self.design(paths=["src/**"])
        self.create("src/a/README.md", "src/b/README.md")
        self.commit()
        self.clean_merge("src/a/README.md", "src/b/README.md")
        self.assertNotIn("commits since", self.ok("audit"))

    def test_a_clean_merge_of_branches_that_changed_code_is_an_unchecked_commit_unless_a_trailer_names_the_design(self):
        self.design(paths=["src/**"])
        self.create("src/a/x.py", "src/b/y.py")
        self.commit()
        self.clean_merge("src/a/x.py", "src/b/y.py", message="fix: checked\n\nRefs: D001")
        self.assertRegex(self.ok("audit"), r"  1 commits since [0-9a-f]+  D001 ")
        self.git("commit", "-q", "--amend", "-m", "Merge branch 'side'\n\nRefs: D001")
        self.assertNotIn("commits since", self.ok("audit"))


@unittest.skipIf(os.name == "nt", "symlinks need privileges on Windows")
class InstalledSkillsTest(CanonTest):
    """The skills a project installs are tooling, neither code nor docs; here the install is left untracked."""
    committed = False
    SKILL = ".agents/skills/canon/SKILL.md"

    def install_skills(self, *extra):
        """Install canon as `npx skills` does, beside the harness's link at INSTALL: the skills in `.agents/skills/`,
        a link to each from `.claude/skills/` and `skills-lock.json`, with the files `extra`; when `committed`, commit
        the work tree with the harness's link."""
        self.create(self.SKILL, ".agents/skills/canon-tdd/LICENSE", "skills-lock.json", *extra)
        (self.root / ".claude/skills").mkdir(parents=True)
        (self.root / ".claude/skills/canon").symlink_to("../../.agents/skills/canon")
        if self.committed:
            self.git("add", "-A")
            self.git("add", "-f", INSTALL)
            self.git("commit", "-qm", "chore: install canon")

    def test_which_prints_skill_for_an_installed_skill_file_and_no_design_for_a_copy_outside_the_install(self):
        self.install_skills()
        copy = self.root / ".cursor/skills/canon/SKILL.md"
        copy.parent.mkdir(parents=True)
        shutil.copy(str(self.root / self.SKILL), str(copy))
        lines = self.ok("which", self.SKILL, ".claude/skills/canon/SKILL.md", "skills-lock.json",
                        ".agents/skills/canon-tdd/LICENSE", ".cursor/skills/canon/SKILL.md").splitlines()
        self.assertEqual(lines, [self.SKILL + ": skill", self.SKILL + ": skill", "skills-lock.json: skill",
                                 ".agents/skills/canon-tdd/LICENSE: skill", ".cursor/skills/canon/SKILL.md: no design"])

    def test_a_design_governs_an_installed_skill_file_only_through_an_entry_equal_to_its_path(self):
        self.design("everything", paths=["**"])
        self.design("agents", paths=[".agents/**"])
        self.design("skill", paths=[self.SKILL])
        self.install_skills()
        lines = self.ok("which", self.SKILL, ".claude/skills/canon/SKILL.md", "skills-lock.json",
                        ".agents/skills/canon-tdd/LICENSE").splitlines()
        governed = self.SKILL + ": D003 docs/designs/D003-skill.md - Fixture"
        self.assertEqual(lines, [governed, governed, "skills-lock.json: skill",
                                 ".agents/skills/canon-tdd/LICENSE: skill"])

    def test_an_agents_md_among_the_installed_skills_makes_no_project(self):
        self.install_skills(".agents/skills/canon/AGENTS.md", ".agents/skills/canon/docs/x.md")
        self.assertEqual(self.ok("which", ".agents/skills/canon/docs/x.md"), ".agents/skills/canon/docs/x.md: skill\n")
        result = self.canon("check")
        self.assertEqual([p for p in self.problems(result.stdout) if ".agents/" in p], [])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_new_and_adopt_walk_past_an_agents_md_among_the_installed_skills_to_the_project(self):
        self.install_skills(".agents/skills/canon/AGENTS.md", ".agents/skills/canon/notes.md")
        result = self.canon_process("new", "D", "x", cwd=self.root / ".agents/skills/canon")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue((self.root / "docs/designs/D001-x.md").is_file())
        self.ok("adopt", ".agents/skills/canon/notes.md", "D")
        self.assertTrue((self.root / "docs/designs/D002-notes.md").is_file())
        self.assertFalse((self.root / ".agents/skills/canon/docs").exists())

    @unittest.skipIf(os.name == "nt", "symlinks need privileges on Windows")
    def test_a_link_to_the_install_directory_itself_is_an_installed_skill_file(self):
        self.design(paths=[".codex/**"])
        self.commit()
        base = self.git("rev-parse", "HEAD")
        (self.root / ".codex").mkdir()
        (self.root / ".codex/skills").symlink_to("../.agents/skills")
        self.install_skills()
        self.assertEqual(self.ok("affected", "--base", base), "no design governs the changed files\n")

    def test_coverage_counts_no_installed_skill_file_in_a_module_at_the_project_directory(self):
        self.modules("./")
        self.design(paths=["src/**"])
        self.commit()
        self.install_skills()
        # ./ holds .gitattributes and .gitignore from `init`.
        self.assertEqual(self.section(self.ok("audit"), CoverageTest.AREAS), ["  1 commits  ./  2 of 2 files"])

    def test_affected_lists_no_file_of_the_install_named_on_the_command_line_or_changed(self):
        self.design(paths=[".claude/**", ".agents/**", "*.json"])
        self.commit()
        base = self.git("rev-parse", "HEAD")
        self.install_skills(".claude/settings.json")
        self.assertEqual(self.ok("affected", self.SKILL, ".claude/skills/canon", ".claude/skills/canon/SKILL.md",
                                 "skills-lock.json", ".agents/skills/canon-tdd/LICENSE", INSTALL),
                         "no design governs the changed files\n")
        self.assertEqual(self.ok("affected", "--base", base),
                         "D001 active docs/designs/D001-area.md - Fixture\n  .claude/settings.json\n")


class CommittedInstalledSkillsTest(InstalledSkillsTest):
    """The install of `InstalledSkillsTest`, committed with the project."""
    committed = True

    def retarget_install(self, target):
        link = self.root / INSTALL
        link.unlink()
        link.symlink_to(target)

    def test_a_commit_changing_only_an_installed_skill_file_is_no_unchecked_commit_of_a_design_globbing_it(self):
        self.create("src/a.py")
        self.install_skills()
        self.design(paths=["**/*.py"])
        self.commit()
        self.retarget_install(os.path.relpath(str(SCRIPT), str((self.root / INSTALL).parent)))
        self.git("commit", "-qam", "chore: update canon")
        self.assertNotIn("commits since", self.ok("audit"))
        self.retarget_install(SCRIPT)
        self.edit_commit("src/a.py")
        self.assertRegex(self.ok("audit"), r"  1 commits since [0-9a-f]+  D001 ")


@unittest.skipIf(os.name == "nt", "symlinks need privileges on Windows")
class LinkedSkillSourceTest(CanonTest):
    """A repository that develops canon, as this one does, loads its skills from their source through links:
    `.agents/skills/<name>` to `skills/<category>/<name>`, and `.claude/skills/<name>` to that link."""

    def link_skill_source(self):
        """Replace the harness's install with links to the canon skill's source, whose canon.py links to SCRIPT."""
        source = self.root / "skills/governance/canon"
        (source / "scripts").mkdir(parents=True)
        (source / "SKILL.md").write_text("---\nname: canon\n---\n")
        (source / "scripts/canon.py").symlink_to(SCRIPT)
        shutil.rmtree(str(self.root / ".agents"))
        for directory, target in ((".agents/skills", "../../skills/governance/canon"),
                                  (".claude/skills", "../../.agents/skills/canon")):
            (self.root / directory).mkdir(parents=True)
            (self.root / directory / "canon").symlink_to(target)

    def test_which_resolves_a_link_into_the_skill_source_to_the_source_which_stays_code(self):
        self.design("skills", paths=["skills/**"])
        self.link_skill_source()
        governed = "skills/governance/canon/SKILL.md: D001 docs/designs/D001-skills.md - Fixture"
        self.assertEqual(self.ok("which", ".agents/skills/canon/SKILL.md", ".claude/skills/canon/SKILL.md"),
                         governed + "\n" + governed + "\n")

    def test_an_install_directory_linked_to_the_skill_source_leaves_the_source_code(self):
        self.design("skills", paths=["skills/**"])
        self.link_skill_source()
        shutil.rmtree(str(self.root / ".agents"))
        shutil.rmtree(str(self.root / ".claude"))
        (self.root / ".agents").mkdir()
        (self.root / ".agents/skills").symlink_to("../skills/governance")
        governed = "skills/governance/canon/SKILL.md: D001 docs/designs/D001-skills.md - Fixture"
        self.assertEqual(self.ok("which", "skills/governance/canon/SKILL.md", ".agents/skills/canon/SKILL.md"),
                         governed + "\n" + governed + "\n")


class CoverageTest(CanonTest):
    """`audit`'s source areas: the tracked files under the Paths of D000's Modules rows that no design covers."""
    AREAS = "Source areas no design covers (commits in the last 90 days, most first):"

    def areas(self):
        return self.section(self.ok("audit"), self.AREAS) or []

    def test_a_fully_uncovered_module_is_one_area_never_above_its_path(self):
        self.modules("src/a/")
        self.create("src/a/x.py", "src/a/sub/y.py", "src/a/sub/deep/z.py")
        self.commit()
        self.assertEqual(self.areas(), ["  1 commits  src/a/  3 files"])

    def test_a_partly_covered_directory_counts_its_own_files_and_its_uncovered_subdirectory_is_an_area(self):
        self.modules("src/a/", "src/b/")
        self.design(paths=["src/b/c*.py"])
        self.create("src/a/x.py", "src/b/c1.py", "src/b/c2.py", "src/b/c3.py", "src/b/u1.py", "src/b/u2.py",
                    "src/b/gen/g1.py", "src/b/gen/g2.py")
        self.commit()
        self.assertEqual(self.areas(), ["  1 commits  src/b/  2 of 5 files", "  1 commits  src/b/gen/  2 files",
                                        "  1 commits  src/a/  1 files"])

    def test_only_tracked_files_under_the_module_paths_count_and_no_doc(self):
        self.modules("src/a/")
        self.init_module("src/a")
        self.create("src/a/x.py", "src/a/lib/y.py", "src/a/README.md", "src/a/docs/assets/map.svg", "tools/gen.py")
        self.commit()
        self.create("src/a/untracked.py")
        self.assertEqual(self.areas(), ["  1 commits  src/a/  2 files"])

    def test_path_cells_are_found_by_their_header_and_split_at_commas_into_directories(self):
        path = self.root / self.OVERVIEW
        path.write_text(path.read_text().replace(
            self.MODULES, "| Path | Module |\n|---|---|\n| ` src/a `, src/b/, , src/base.py, lib/, ../src/c | m |\n"
                          "| none |\n"))
        self.create("src/a/x.py", "src/b/y.py", "src/c/z.py")
        self.commit()
        self.assertEqual(self.areas(), ["  1 commits  src/a/  1 files", "  1 commits  src/b/  1 files"])

    def test_a_module_path_deleted_from_the_work_tree_holds_no_file_while_the_index_lists_its_files(self):
        self.modules("src/a/", "src/b/")
        self.create("src/a/x.py", "src/b/y.py")
        self.commit()
        shutil.rmtree(str(self.root / "src/b"))
        self.assertIn("src/b/y.py", self.git("ls-files"))
        self.assertEqual(self.areas(), ["  1 commits  src/a/  1 files"])

    def test_a_module_at_the_project_directory_counts_the_files_no_longer_path_holds(self):
        self.modules("./", "`src`")
        self.create("build.sh", ".github/ci.yml", "src/x.py")
        self.commit()
        # ./ holds build.sh, .github/ci.yml, and .gitattributes and .gitignore from `init`.
        self.assertEqual(self.areas(), ["  1 commits  ./  4 files", "  1 commits  src/  2 files"])
        self.ok("check")
        self.design(paths=["src/**"])
        self.commit()
        self.assertEqual(self.areas(), ["  1 commits  ./  4 files"])

    def commit_at(self, days, *names):
        """Commit the work tree, with each of `names` edited, dated `days` back."""
        for name in names:
            path = self.root / name
            path.write_text(path.read_text() + "x\n")
        self.git("add", "-A")
        stamp = "@{} +0000".format(int(time.time() - days * 86400))
        result = subprocess.run(["git", "commit", "-qm", "edit"], cwd=self.root, capture_output=True, text=True,
                                env=dict(os.environ, GIT_AUTHOR_DATE=stamp, GIT_COMMITTER_DATE=stamp))
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_areas_rank_by_commits_of_the_last_90_days_then_uncovered_files_then_path(self):
        self.modules("src/")
        self.design(paths=["src/base.py"])
        self.create(*["src/{}/x.py".format(area) for area in "abcdefghijkl"], "src/b/y.py", "src/d/y.py", "src/d/z.py")
        self.ok("check", "--fix")
        self.commit_at(91)
        self.commit_at(91, "src/l/x.py")
        self.commit_at(89, "src/a/x.py")
        self.commit_at(0, "src/b/x.py")
        for _ in range(10):
            self.commit_at(0, "src/c/x.py")
        self.assertEqual(self.areas(), ["  10 commits  src/c/  1 files",
                                        "   1 commits  src/b/  2 files",
                                        "   1 commits  src/a/  1 files",
                                        "   0 commits  src/d/  3 files"]
                         + ["   0 commits  src/{}/  1 files".format(area) for area in "efghij"]
                         + ["  and 2 more areas"])
        self.ok("check")


class ReachTest(CanonTest):
    """`audit`'s designs that D000 does not reach through its links and the `refs` of the designs it reaches."""
    UNREACHED = "Designs D000 does not reach (link each from D000's rows or from a design D000 reaches):"

    def test_audit_lists_the_designs_neither_d000_nor_a_design_it_reaches_names(self):
        self.modules("src/", design="[D001: A](D001-a.md)")
        self.design("a", refs=["D001A", "D002", "P001"])
        self.design("b", refs=["D004"])
        self.design("c")
        self.design("d")
        self.design("e")
        self.design("a-part", parent="D001")
        self.design("b-part", parent="D002")
        self.doc("P", "first", refs=["D005"])
        self.ok("archive", "D003", "retired")
        self.ok("check", "--fix")
        self.assertIn("refs: [D001]", (self.root / self.OVERVIEW).read_text())
        self.assertEqual(self.section(self.ok("audit"), self.UNREACHED),
                         ["  D002A active docs/designs/D002A-b-part.md - Fixture",
                          "  D005 active docs/designs/D005-e.md - Fixture"])

    def project(self):
        self.modules("./")
        self.design(paths=["src/base.py"])
        self.create("lib/x.py")

    def test_outside_git_audit_prints_reach_but_no_coverage(self):
        self.root = self.outside_checkouts()
        self.ok("init")
        self.project()
        out = self.ok("audit")
        self.assertIn(self.UNREACHED, out)
        self.assertNotIn(CoverageTest.AREAS, out)

    def test_without_a_live_d000_at_the_repo_root_audit_prints_neither_coverage_nor_reach(self):
        self.project()
        self.commit()
        out = self.ok("audit")
        self.assertIn(self.UNREACHED, out)
        self.assertIn(CoverageTest.AREAS, out)
        self.init_module("mod")
        overview = self.root / self.OVERVIEW
        for moved in ("docs/archived/designs/D000-project-overview.md", "mod/docs/designs/D000-project-overview.md"):
            target = self.root / moved
            target.parent.mkdir(parents=True)
            overview = overview.rename(target)
            self.assertIn("D000 draft " + moved, self.ok("find", "D000", "--archived"))
            out = self.ok("audit")
            self.assertNotIn(self.UNREACHED, out)
            self.assertNotIn(CoverageTest.AREAS, out)


class AsBuiltTest(CanonTest):
    """`as_built`, the commit an as-built revision records while it awaits its gate."""

    def test_a_draft_pending_review_passes_naming_head_by_its_full_or_seven_digit_hash(self):
        design = self.doc("D", "area")
        self.commit()
        head = self.git("rev-parse", "HEAD")
        for value in (head, head[:7]):
            self.set(design, as_built=value)
            self.assertNotIn("as_built", self.ok("check"))

    def test_check_fails_an_as_built_that_names_no_commit_or_moves_once_the_change_commits(self):
        design = self.doc("D", "area")
        self.commit()
        head, tree = self.git("rev-parse", "HEAD", "HEAD^{tree}").split()
        for value in ("0123456", head[:6], tree, "HEAD", "main", "worktree"):
            self.set(design, as_built=value)
            self.assertRegex(self.fails("check"), r"ERROR docs/designs/D001-area\.md: `as_built` `{}` names no commit"
                             .format(value))

    def test_a_branch_or_tag_named_like_a_hash_names_no_commit(self):
        design = self.doc("D", "area")
        self.commit()
        self.git("branch", "deadbee")
        self.git("tag", "cafef00d")
        self.assertEqual(self.git("rev-parse", "--disambiguate=deadbee"), "")
        self.assertEqual(self.git("rev-parse", "--disambiguate=cafef00d"), "")
        for value in ("deadbee", "cafef00d"):
            self.set(design, as_built=value)
            self.assertIn("ERROR docs/designs/D001-area.md: `as_built` `{}` names no commit".format(value),
                          self.fails("check"))

    def test_worktree_passes_before_the_first_commit_and_outside_git_where_a_hash_fails(self):
        self.doc("D", "area", as_built="worktree")
        self.assertNotIn("as_built", self.ok("check", "--fix"))
        self.root = self.outside_checkouts()
        self.ok("init")
        design = self.doc("D", "area", as_built="worktree")
        self.assertNotIn("as_built", self.ok("check", "--fix"))
        self.set(design, as_built="0123456789abcdef0123456789abcdef01234567")
        self.assertIn("`as_built` `0123456789abcdef0123456789abcdef01234567` names no commit", self.fails("check"))

    def test_fix_deletes_the_as_built_line_alone_once_its_revision_is_reviewed(self):
        self.commit()
        head = self.git("rev-parse", "HEAD")
        design = self.design(created="2026-01-01", updated="2026-01-01", as_built=head)
        self.commit(check=False)
        text = design.read_text()
        out = self.fails("check")
        self.assertRegex(out, r"ERROR docs/designs/D001-area\.md: `as_built` remains on revision 1, which is reviewed")
        self.assertIn("; 1 fixable with --fix", out)
        self.ok("check", "--fix")
        self.assertEqual(design.read_text(), text.replace("as_built: {}\n".format(head), "", 1))
        self.assertNotIn("as_built", self.ok("check"))

    def test_as_built_on_a_plan_is_an_unknown_frontmatter_field(self):
        self.commit()
        self.doc("P", "work", as_built=self.git("rev-parse", "HEAD"))
        self.assertRegex(self.fails("check", "--fix"),
                         r"ERROR docs/plans/P001-work\.md: unknown frontmatter field `as_built`")


class OverviewCheckTest(CanonTest):
    """`check`'s rules for D000: one live D000 in the repo root's docs/ and none elsewhere, its four Spec
    subsections, only files in its `paths`, and a warning for a Modules Path that is no directory."""

    def test_a_repository_fresh_from_init_passes_with_only_the_warnings_of_an_unfinished_design(self):
        self.assertEqual(self.problems(self.ok("check")),
                         ["WARN {}: `summary` is empty".format(self.OVERVIEW),
                          "WARN {}: template guidance `<!-- canon: ... -->` left in the doc".format(self.OVERVIEW)])

    def test_check_fails_without_a_live_d000_in_the_repo_root_docs(self):
        path = self.root / self.OVERVIEW
        text = path.read_text()
        path.unlink()
        self.assertIn(NO_OVERVIEW, self.problems(self.fails("check", "--fix")))
        archived = self.root / "docs/archived/designs/D000-project-overview.md"
        archived.parent.mkdir(parents=True)
        archived.write_text(canon.set_field(text, "status", "retired"))
        out = self.problems(self.fails("check", "--fix"))
        self.assertNotIn(NO_OVERVIEW, out)
        self.assertTrue(any(line.startswith("ERROR docs/archived/designs/D000-project-overview.md: D000 is archived")
                            for line in out), out)

    def test_check_fails_with_a_second_d000_under_a_module_docs_root(self):
        self.init_module("mod")
        module = self.root / "mod" / self.OVERVIEW
        module.parent.mkdir(parents=True)
        module.write_text((self.root / self.OVERVIEW).read_text())
        self.assertIn("ERROR mod/{}: D000 belongs only in the repo root's docs/; give this doc another id with "
                      "`canon.py renumber mod/{}`".format(self.OVERVIEW, self.OVERVIEW),
                      self.problems(self.fails("check", "--fix")))

    def test_check_fails_when_d000_spec_lacks_one_of_its_four_subsections(self):
        path = self.root / self.OVERVIEW
        text = path.read_text()
        lacks = ("ERROR {}: `## Spec` lacks `### {{}}`; D000's Spec holds the subsections Capabilities, Modules, "
                 "Dependencies and Glossary").format(self.OVERVIEW)
        for name in ("Capabilities", "Modules", "Dependencies", "Glossary"):
            path.write_text(text.replace("\n### {}\n".format(name), "\n{}\n".format(name)))
            self.assertIn(lacks.format(name), self.problems(self.fails("check")))
        path.write_text(text.replace("\n### Glossary\n", "\n").replace("\n## Decisions\n", "\n## Decisions\n\n"
                                                                       "### Glossary\n"))
        self.assertIn(lacks.format("Glossary"), self.problems(self.fails("check")))

    def test_check_fails_a_glob_or_directory_in_d000_paths_and_passes_a_file(self):
        path = self.root / self.OVERVIEW
        names = ("ERROR {}: `paths` entry `{{}}` names a glob or directory; D000's `paths` list only files, since a "
                 "glob or directory makes every file under it look governed").format(self.OVERVIEW)
        for entry in ("src/**", "src/", "src", "./", "src/*.py", "src/base.p?", "src/[b]ase.py", "lib/"):
            self.set(path, paths=[entry])
            self.assertIn(names.format(entry), self.problems(self.fails("check")))
        self.set(path, paths=["src/base.py"])
        self.ok("check")

    def test_a_modules_path_that_is_no_directory_of_the_project_only_warns(self):
        self.modules("./", "`src/`, src", "lib/, src/base.py, ..")
        self.assertEqual([line for line in self.problems(self.ok("check")) if "Modules Path" in line],
                         ["WARN {}: Modules Path `{}` is not a directory of the project".format(self.OVERVIEW, entry)
                          for entry in ("lib/", "src/base.py", "..")])

    def test_a_modules_path_does_not_warn_while_its_row_links_only_designs_with_no_implemented(self):
        planned = self.design("planned", status="accepted", implemented=None, paths=["lib/**"])
        self.design("built")
        self.modules("lib/", design="[D001: Fixture](D001-planned.md)")
        self.modules("app/", design="none")
        self.modules("tools/", design="[D001: Fixture](D001-planned.md), [D002: Fixture](D002-built.md)")
        self.modules("web/", design="![D001](D001-planned.md), [Docs](../README.md)")
        path = self.root / self.OVERVIEW
        path.write_text(path.read_text().replace("| Entry points | Design |\n", "| Entry points | DESIGN |\n", 1))
        warning = "WARN {}: Modules Path `{{}}` is not a directory of the project".format(self.OVERVIEW)
        self.assertEqual(sorted(line for line in self.problems(self.ok("check", "--fix")) if "Modules Path" in line),
                         sorted(warning.format(entry) for entry in ("app/", "tools/", "web/")))
        self.set(planned, status="active", implemented=1)
        self.assertIn(warning.format("lib/"), self.problems(self.ok("check", "--fix")))


class TraceCase(CanonTest):
    HOST_VARS = ("CURSOR_AGENT", "CURSOR_CONVERSATION_ID", "CODEX_THREAD_ID", "CLAUDECODE")

    def setUp(self):
        super().setUp()
        self.config = self.tmpdir()
        self.events = self.root / ".canon/canon/trace/events.jsonl"

    def tool(self, *args, cwd=None, stdin="", returncode=0, **env):
        """Run `canon.py *args` with the machine switch under a temporary XDG_CONFIG_HOME, no host variables but
        those in `env`, and `stdin` as its standard input; assert that it exits with `returncode`, and return the
        finished process."""
        full = {key: value for key, value in os.environ.items() if key not in self.HOST_VARS}
        full.update(XDG_CONFIG_HOME=str(self.config), **env)
        result = self.canon_process(*args, cwd=cwd, env=full, input=stdin)
        self.assertEqual(result.returncode, returncode, result.stdout + result.stderr)
        return result

    def trace(self, *args, **options):
        """Run `canon.py trace` as `tool` does; return its output."""
        return self.tool("trace", *args, **options).stdout

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

    def project_state(self):
        """The project's work tree outside .canon/, HEAD, refs, the files under its object directory, and its index."""
        def files(top, skip=()):
            return {p.relative_to(top).as_posix(): p.read_bytes() for p in top.rglob("*")
                    if p.is_file() and p.relative_to(top).parts[0] not in skip}
        git_dir = self.root / ".git"
        return {"work tree": files(self.root, (".git", ".canon")), "HEAD": (git_dir / "HEAD").read_bytes(),
                "refs": self.git("for-each-ref", "--format=%(refname) %(objectname)"),
                "objects": files(git_dir / "objects"), "index": (git_dir / "index").read_bytes()}

    @contextlib.contextmanager
    def lock_held(self, name, directory=None):
        """Hold the lock `name` in `directory`, by default the trace directory, as a call does, so calls started
        meanwhile wait on it."""
        if fcntl is None:
            yield
            return
        with open(str((directory or self.events.parent) / name), "a") as lock:
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
        self.init_module("mod")
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
        self.init_module("mod")
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
        top = self.outside_checkouts()
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
        with (self.root / ".git/info/exclude").open("a") as exclude:
            exclude.write("*.tmp\n")
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

    def test_an_as_built_gate_gets_the_recorded_commits_tree_as_the_snapshots_second_parent(self):
        design = self.design("area")
        self.commit()
        moved_past = self.git("rev-parse", "HEAD")
        self.git("checkout", "-qb", "side")
        (self.root / "src/base.py").write_text("value = 3\n")
        self.git("commit", "-qam", "left out by a rebase")
        left_out = self.git("rev-parse", "HEAD")
        self.git("checkout", "-q", "main")
        self.git("branch", "-qD", "side")
        (self.root / "src/base.py").write_text("value = 2\n")
        self.git("commit", "-qam", "HEAD moves on")
        for recorded, value in ((moved_past, "value = 1"), (left_out, "value = 3")):
            self.set(design, revision=2, as_built=recorded[:7])
            snapshot = self.start_line("gate", "D001", "--tier", "L1", "--base", "HEAD")["snapshot"]
            self.assertEqual(self.snap("show", snapshot + "^2:src/base.py"), value)
            self.assertEqual(self.snap("rev-parse", snapshot + "^2^{tree}"), self.git("rev-parse", recorded + "^{tree}"))
            self.assertEqual(self.snap("rev-list", "--count", snapshot + "^2"), "1")
            self.assertEqual(self.snap("diff", "--name-only", snapshot + "^", snapshot), design.relative_to(self.root)
                             .as_posix())
        head = self.git("rev-parse", "HEAD")
        self.set(design, as_built=head[:7])
        snapshot = self.start_line("gate", "D001", "--tier", "L1")["snapshot"]
        self.assertEqual([self.snap("rev-parse", snapshot + rev) for rev in ("^1^{tree}", "^2^{tree}")],
                         [self.git("rev-parse", "HEAD^{tree}")] * 2)
        for args in (["code-review", "D001", "--base", "HEAD"], ["follow-up", "D001", "--tier", "L1"]):
            snapshot = self.start_line(*args)["snapshot"]
            self.assertEqual(len(self.snap("rev-list", "--parents", "-n", "1", snapshot).split()), 2, args)
        self.git("branch", "deadbee", moved_past)
        for value in ("worktree", "0123456", "deadbee"):
            self.set(design, as_built=value)
            snapshot = self.start_line("gate", "D001", "--tier", "L1", "--base", "HEAD")["snapshot"]
            self.assertEqual(len(self.snap("rev-list", "--parents", "-n", "1", snapshot).split()), 2, value)

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
        outside = self.outside_checkouts()
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


class ReviewSnapshotTest(TraceCase):
    def setUp(self):
        super().setUp()
        self.snapshots = self.root / ".canon/canon/snapshots"

    def snapshot(self, cwd=None, returncode=0):
        """Run `canon.py snapshot` as `tool` does; return its standard output and standard error."""
        result = self.tool("snapshot", cwd=cwd, returncode=returncode)
        return result.stdout, result.stderr

    def take(self):
        out, err = self.snapshot()
        self.assertRegex(out, r"^[0-9a-f]{40}([0-9a-f]{24})?\n$")
        self.assertEqual(err, "")
        return out.strip()

    def review_git(self, *args):
        """Run git in the review snapshot repository, as the confirmation's diff command does."""
        return self.git("-C", ".canon/canon/snapshots", *args)

    def local_objects(self):
        """The objects the review snapshot repository stores itself, all loose until a gc packs them."""
        objects = self.snapshots / ".git/objects"
        self.assertEqual(list(objects.glob("pack/*.pack")), [])
        return {p.parent.name + p.name for p in objects.glob("??/*")}

    def test_with_tracing_off_a_snapshot_records_the_work_tree_in_its_own_repository_and_leaves_the_project(self):
        with (self.root / ".gitignore").open("a") as ignore:
            ignore.write("*.log\n")
        for name in ("staged.txt", "unstaged.txt"):
            (self.root / name).write_text("v1\n")
        self.commit()
        (self.root / "staged.txt").write_text("v2 staged\n")
        self.git("add", "staged.txt")
        (self.root / "unstaged.txt").write_text("v2 unstaged\n")
        (self.root / "untracked.txt").write_text("new\n")
        (self.root / "build.log").write_text("ignored\n")
        before = self.project_state()
        commit = self.take()
        after = self.project_state()
        self.assertEqual([part for part in before if after[part] != before[part]], [])
        self.assertFalse((self.root / ".canon/canon/trace").exists())
        self.assertEqual((self.root / ".canon/canon/.gitignore").read_text(), "*\n")
        refs = self.review_git("for-each-ref", "--format=%(refname) %(objectname)", "refs/snapshots/").splitlines()
        self.assertEqual(len(refs), 1)
        self.assertRegex(refs[0], r"^refs/snapshots/\d{8}T\d{6}Z-[0-9a-f]{6} " + commit + "$")
        self.assertEqual(self.review_git("rev-list", "--parents", "-n", "1", commit), commit)
        files = set(self.review_git("ls-tree", "-r", "--name-only", commit).splitlines())
        self.assertEqual({name for name in files if name == "build.log" or name.startswith(".canon/")}, set())
        self.assertEqual({name: self.review_git("show", "{}:{}".format(commit, name)) for name in
                          ("staged.txt", "unstaged.txt", "untracked.txt")},
                         {"staged.txt": "v2 staged", "unstaged.txt": "v2 unstaged", "untracked.txt": "new"})
        alternates = (self.snapshots / ".git/objects/info/alternates").read_text().splitlines()
        self.assertEqual(len(alternates), 1)
        self.assertTrue(os.path.isabs(alternates[0]))
        self.assertTrue(os.path.samefile(alternates[0], str(self.root / ".git/objects")))
        local = self.local_objects()
        self.assertIn(self.git("hash-object", "untracked.txt"), local)
        self.assertNotIn(self.git("rev-parse", "HEAD:src/base.py"), local)

    def test_the_diff_of_two_snapshots_shows_what_changed_between_them_committed_or_not(self):
        for name in ("kept.txt", "gone.txt"):
            (self.root / name).write_text(name + "\n")
        self.commit()
        (self.root / "draft.txt").write_text("draft 1\n")
        first = self.take()
        (self.root / "src/base.py").write_text("value = 2\n")
        self.git("commit", "-qam", "committed between the snapshots")
        (self.root / "draft.txt").write_text("draft 2\n")
        (self.root / "gone.txt").unlink()
        (self.root / "created.txt").write_text("created\n")
        second = self.take()
        self.assertEqual(self.review_git("diff", "--name-status", first, second).splitlines(),
                         ["A\tcreated.txt", "M\tdraft.txt", "D\tgone.txt", "M\tsrc/base.py"])
        self.assertEqual(self.review_git("diff", "--name-status", first, second, "--", "draft.txt", "gone.txt")
                         .splitlines(), ["M\tdraft.txt", "D\tgone.txt"])

    def test_each_snapshot_deletes_snapshots_older_than_30_days_and_leftovers_older_than_an_hour(self):
        first = self.take()
        old, kept = self.unit_id(datetime.timedelta(days=31), 1), self.unit_id(datetime.timedelta(days=29), 2)
        for unit in (old, kept):
            self.review_git("update-ref", "refs/snapshots/" + unit, first)
        hour, git_dir = datetime.timedelta(hours=1), self.snapshots / ".git"
        copies = [git_dir / ("index-" + self.unit_id(ago, n)) for ago, n in ((2 * hour, 3), (hour / 2, 4))]
        builds = [self.snapshots / (".init-" + self.unit_id(ago, n)) for ago, n in ((2 * hour, 5), (hour / 2, 6))]
        for path in copies:
            path.write_bytes(b"index")
        for path in builds:
            (path / ".git").mkdir(parents=True)
        second = self.take()
        refs = self.review_git("for-each-ref", "--format=%(refname:lstrip=2) %(objectname)", "refs/snapshots/")
        self.assertEqual(sorted(line.split()[1] for line in refs.splitlines()), sorted([first, first, second]))
        self.assertNotIn(old, refs)
        self.assertIn(kept, refs)
        self.assertEqual([path.exists() for path in copies + builds], [False, True, False, True])

    def test_a_snapshot_that_cannot_be_taken_prints_its_reason_and_exits_1(self):
        (self.root / "big.bin").write_bytes(b"\0" * (11 << 20))
        self.assertEqual(self.snapshot(returncode=1), ("snapshot error: changes-over-10MiB\n", ""))
        (self.root / "big.bin").unlink()
        (self.root / ".git/index").write_bytes(b"not an index")
        out, err = self.snapshot(returncode=1)
        self.assertEqual(out, "snapshot error: git status: exit 128\n")
        self.assertIn("index", err)
        self.assertEqual(self.snapshot(cwd=self.outside_checkouts(), returncode=1), ("snapshot error: no-git\n", ""))

    @unittest.skipIf(fcntl is None, "lock_held holds no lock without fcntl")
    def test_a_snapshot_that_waits_5_s_for_snapshot_lock_fails_and_records_nothing(self):
        self.snapshots.mkdir(parents=True)
        with self.lock_held("snapshot.lock", self.snapshots):
            self.assertEqual(self.snapshot(returncode=1), ("snapshot error: snapshot lock: timeout\n", ""))
        self.assertFalse((self.snapshots / ".git").exists())

    def test_with_tracing_on_a_snapshot_still_writes_nothing_in_the_trace_directory(self):
        self.trace("on")
        self.start("design")
        trace_dir = self.events.parent

        def files():
            return {p.relative_to(trace_dir).as_posix(): p.read_bytes() for p in trace_dir.rglob("*") if p.is_file()}

        before = files()
        self.take()
        self.assertEqual(files(), before)


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


class FollowUpTest(TraceCase):
    def setUp(self):
        super().setUp()
        self.trace("on")

    def test_a_follow_up_records_the_targets_it_revises_and_its_parent_and_is_top_level_without_one(self):
        self.design(revision=5, reviewed=4)
        design = self.start("design", "D001")
        line = self.start_line("follow-up", "D001", "--tier", "L2", "--skill", "skills/canon-blind-review",
                               "--model", "m", "--parent", design)
        self.assertEqual([line[k] for k in ("kind", "docs", "parent", "tier", "model")],
                         ["follow-up", ["D001@r5"], design, "L2", "m"])
        self.assertIsNone(self.start_line("follow-up", "D001", "--tier", "L2")["parent"])

    def test_a_follow_ups_end_takes_a_gates_dispositions_and_archives_the_rounds_files(self):
        unit = self.start("follow-up", "D001", "--tier", "L2")
        path = ".canon/canon-blind-review/D001-r4/followup-1"
        reports = {"same-model.md": b"### F1 [major] D001\n", "cross-family.md": b"### F1 [minor] D001\n"}
        (self.root / path).mkdir(parents=True)
        started = self.started(unit).timestamp()
        for name, data in reports.items():
            (self.root / path / name).write_bytes(data)
            os.utime(str(self.root / path / name), (started, started))
        spec = json.loads(json.dumps(DispositionsTest.GATE))
        spec["reviewers"][0]["role"] = "spec"
        self.rejects("end", unit, "delivered", "--dir", path, "--input", "-", stdin=json.dumps(spec))
        self.assertFalse((self.root / ".canon/canon/trace" / unit).exists())
        out = self.trace("end", unit, "delivered", "--dir", path, "--input", "-",
                         stdin=json.dumps(DispositionsTest.GATE))
        self.assertEqual(out, "trace {} ended\n".format(unit))
        line = self.lines()[-1]
        self.assertEqual([line["kind"], line["dispositions"], line["archive"]],
                         ["follow-up", DispositionsTest.GATE, "ok"])
        self.assertEqual({p.name: p.read_bytes() for p in (self.root / ".canon/canon/trace" / unit).iterdir()},
                         reports)

    def test_a_slice_or_end_check_cannot_parent_a_follow_up_and_input_comes_with_review_units_only(self):
        implement = self.start("implement", "P001")
        for parent in (self.start("slice", "P001", "--slice", "S1", "--parent", implement), self.start("end-check")):
            self.rejects("start", "follow-up", "D001", "--parent", parent)
        design = self.start("design", "D001")
        before = self.events.read_bytes()
        out = self.trace("end", design, "delivered", "--input", "-", stdin=json.dumps(DispositionsTest.GATE))
        self.assertEqual(out, "trace error: --input comes with gate, follow-up and code-review units only\n")
        self.assertEqual(self.events.read_bytes(), before)


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
        outside = self.outside_checkouts()
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
        outside = self.outside_checkouts()
        (outside / "AGENTS.md").write_text("# AGENTS.md\n")
        out = self.trace("prune", "--days", "7", cwd=outside)
        self.assertEqual(out.splitlines()[-1], "snapshots: 0, 0.0 KiB on disk")
        self.assertEqual([path.name for path in outside.iterdir() if path.name != ".agents"], ["AGENTS.md"])
        archive = outside / ".canon/canon/trace" / self.unit_id(datetime.timedelta(days=8), 1)
        archive.mkdir(parents=True)
        (archive / "snapshot-error.txt").write_text("fatal: index file corrupt\n")
        self.assertRegex(self.trace("prune", "--days", "7", cwd=outside),
                         r"^removed 0 snapshots and 1 archive of units started more than 7 days ago\n")
        self.assertEqual(list(archive.parent.iterdir()), [])


class OutsideCheckoutTest(CanonTest):
    def test_canon_py_runs_only_in_a_test_repository_or_a_directory_from_outside_checkouts(self):
        self.assertEqual(self.canon_process("which", "base.py", cwd=self.root / "src").returncode, 0)
        with self.assertRaisesRegex(AssertionError, "in no test repository and not from outside_checkouts"):
            self.canon_process("init", cwd=self.tmpdir())
        self.assertEqual(self.canon_process("init", cwd=self.outside_checkouts()).returncode, 0)

    def test_canon_py_runs_through_the_projects_link_to_script_that_git_never_sees(self):
        self.assertEqual(os.readlink(str(self.root / INSTALL)), str(SCRIPT))
        self.assertNotIn(".agents", self.git("status", "--porcelain", "--untracked-files=all"))
        self.repository_without_docs()
        (self.root / INSTALL).parent.mkdir(parents=True)
        (self.root / INSTALL).write_text(SCRIPT.read_text())
        with self.assertRaisesRegex(AssertionError, "is not a link to"):
            self.canon_process("init")


class InstallLocationTest(CanonTest):
    def refused(self, script, *args, **options):
        """`canon.py args` started by `script` exits 1 with the message that names `script`."""
        result = self.canon_process(*args, script=script, **options)
        self.assertEqual((result.returncode, result.stdout + result.stderr), (1, OUTSIDE_INSTALL.format(script)))

    def test_canon_py_started_by_its_own_path_refuses_every_command_but_help_and_version(self):
        self.commit()
        for args in (["which", "src/base.py"], ["check"]):
            self.refused(SCRIPT, *args)
        self.assertEqual(self.git("status", "--porcelain"), "")
        self.ok("-h", script=SCRIPT)
        self.assertEqual(self.ok("--version", script=SCRIPT), "canon {}\n".format(canon.CANON_VERSION))

    def test_the_projects_link_runs_from_the_repo_root_a_subdirectory_and_a_module_with_its_own_agents_md(self):
        self.init_module("mod")
        self.assertTrue((self.root / "mod/AGENTS.md").is_file())
        for cwd, base in ((self.root, "src/base.py"), (self.root / "src", "base.py"),
                          (self.root / "mod", "../src/base.py")):
            with self.subTest(cwd=cwd.name):
                self.assertEqual(self.ok("which", base, cwd=cwd), "src/base.py: no design\n")
                self.ok("check", cwd=cwd)

    @unittest.skipIf(os.name == "nt", "symlinks need privileges on Windows")
    def test_a_link_above_the_checkout_on_the_start_path_or_the_working_directory_runs(self):
        alias = self.root.with_name(self.root.name + "-link")
        alias.symlink_to(self.root, target_is_directory=True)
        self.addCleanup(alias.unlink)
        self.ok("which", "src/base.py", script=alias / INSTALL)
        self.ok("which", "src/base.py", cwd=alias, script=self.root / INSTALL)

    def test_a_linked_worktree_refuses_the_main_checkouts_install_and_runs_its_own(self):
        self.commit()
        worktree = self.tmpdir() / "worktree"
        self.git("worktree", "add", "-q", "--detach", str(worktree))
        self.refused(self.root / INSTALL, "which", "src/base.py", cwd=worktree)
        self.assertFalse((worktree / ".agents").exists())
        self.assertEqual(self.ok("which", "src/base.py", cwd=worktree), "src/base.py: no design\n")
        self.assertTrue((worktree / INSTALL).is_symlink())
        self.assertEqual(self.git("-C", str(worktree), "status", "--porcelain"), "")
        self.assertEqual(self.git("status", "--porcelain"), "")

    def test_the_check_runs_no_git(self):
        env = dict(os.environ, PATH=str(self.tmpdir()), XDG_CONFIG_HOME=str(self.tmpdir()))
        self.refused(SCRIPT, "trace", "status", env=env)
        self.assertRegex(self.ok("trace", "status", env=env), r"^trace off: no machine switch ")

    def test_outside_git_the_working_directory_and_each_directory_above_it_with_an_agents_md_hold_the_install(self):
        top = self.outside_checkouts()
        self.assertIn("created AGENTS.md", self.ok("init", cwd=top))
        self.assertTrue((top / INSTALL).is_symlink())
        (top / "sub").mkdir()
        self.assertEqual(self.ok("which", "x.py", cwd=top / "sub", script=top / INSTALL), "x.py: no design\n")
        sibling = self.outside_checkouts()
        self.refused(top / INSTALL, "which", "x.py", cwd=sibling)
        self.assertEqual(list(sibling.iterdir()), [])


class ProjectVersionTest(CanonTest):
    def setUp(self):
        super().setUp()
        self.init_module("mod")
        self.commit()

    def record(self, old, new):
        """Commit the repo root's AGENTS.md with `old`, in its canon block, replaced by `new`."""
        agents = self.root / "AGENTS.md"
        text = agents.read_text()
        self.assertIn(old, text)
        agents.write_text(text.replace(old, new))
        self.git("commit", "-qam", "record " + new, "--allow-empty")

    def run_canon(self, *args, script=None, cwd=None):
        """`canon.py args` with the machine's tracing switch under a temporary XDG_CONFIG_HOME: its exit code, standard
        output and standard error."""
        result = self.canon_process(*args, script=script, cwd=cwd,
                                    env=dict(os.environ, XDG_CONFIG_HOME=str(self.tmpdir())))
        return result.returncode, result.stdout, result.stderr

    @staticmethod
    def needs(version):
        return ("canon: this project needs canon version {} or later, and this canon.py is version {}; install a newer "
                "canon release as the canon block of AGENTS.md says\n".format(version, canon.CANON_VERSION))

    def test_a_project_that_needs_a_newer_canon_refuses_every_command_but_help_and_version(self):
        self.record("canon version {} or later".format(canon.CANON_VERSION), "canon version 9999 or later")
        for args, cwd in ((["which", "src/base.py"], None), (["check"], None), (["init"], None),
                          (["init", "--root", "mod"], None), (["trace", "status"], None),
                          (["which", "base.py"], self.root / "src"), (["which", "../src/base.py"], self.root / "mod")):
            with self.subTest(args=args, cwd=cwd):
                self.assertEqual(self.run_canon(*args, cwd=cwd), (1, "", self.needs(9999)))
                self.assertEqual(self.git("status", "--porcelain", "--untracked-files=all"), "")
        more_digits = 10 ** len(canon.CANON_VERSION)
        self.record("canon version 9999 or later", "canon version {} or later".format(more_digits))
        self.assertEqual(self.run_canon("which", "src/base.py"), (1, "", self.needs(more_digits)))
        self.assertEqual(self.run_canon("-h")[0], 0)
        self.assertEqual(self.run_canon("--version"), (0, "canon {}\n".format(canon.CANON_VERSION), ""))

    def test_outside_git_the_working_directorys_agents_md_records_the_version(self):
        top = self.outside_checkouts()
        self.assertEqual(self.run_canon("init", cwd=top)[0], 0)
        agents = top / "AGENTS.md"
        agents.write_text(agents.read_text().replace("canon version {} or".format(canon.CANON_VERSION),
                                                     "canon version 9999 or"))
        self.assertEqual(self.run_canon("which", "x.py", cwd=top), (1, "", self.needs(9999)))

    def test_a_project_set_up_for_an_older_canon_runs_with_a_reminder_until_init_at_the_repo_root_records_it(self):
        usual = self.run_canon("find", "x")
        current = "canon version {} or later".format(canon.CANON_VERSION)
        self.record(current, "canon version 1 or later")
        reminder = "this project is set up for canon version 1; run `/canon-init` to upgrade it to version {}".format(
            canon.CANON_VERSION)
        self.assertEqual(self.run_canon("find", "x"), usual[:2] + ("canon: {}\n".format(reminder),))
        code, out, err = self.run_canon("check")
        problems = self.problems(out)
        self.assertIn("WARN AGENTS.md: " + reminder, problems)
        self.assertIn(", 0 errors, {} warnings".format(len(problems)), out)
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(self.run_canon("init", "--root", "mod")[::2], (0, "canon: {}\n".format(reminder)))
        code, out, err = self.run_canon("init")
        self.assertEqual((code, out, err), (0, "updated AGENTS.md\n", ""))
        self.assertIn(current, (self.root / "AGENTS.md").read_text())
        code, out, err = self.run_canon("check")
        self.assertEqual((code, [p for p in self.problems(out) if "AGENTS.md" in p], err), (0, [], ""))
        self.record(current, "canon version 1 or later")
        self.assertEqual(self.run_canon("init", "--root", ".")[::2], (0, ""))
        self.assertIn(current, (self.root / "AGENTS.md").read_text())

    def test_a_block_whose_first_tool_line_names_no_version_records_none(self):
        tool = re.search(r"(?m)^- Tool: .*$", (self.root / "AGENTS.md").read_text()).group(0)
        self.record(tool, "- Tool: `python3 scripts/canon.py` from the repo root (`-h` lists commands).\n"
                          "- Tool: canon version 9999 or later.")
        self.record(canon.AGENTS_END, canon.AGENTS_END + "\n\nOnce on canon version 9999 or later.")
        reminder = "this project records no canon version; run `/canon-init` to upgrade it to version {}".format(
            canon.CANON_VERSION)
        self.assertEqual(self.run_canon("which", "src/base.py"),
                         (0, "src/base.py: no design\n", "canon: {}\n".format(reminder)))
        code, out, err = self.run_canon("check")
        self.assertEqual((code, [p for p in self.problems(out) if "AGENTS.md" in p], err),
                         (0, ["WARN AGENTS.md: " + reminder], ""))

    def test_no_reminder_at_the_recorded_version_nor_without_a_canon_block_with_an_end_marker_after_its_start(self):
        agents = self.root / "AGENTS.md"
        block = canon.AGENTS_START + agents.read_text().split(canon.AGENTS_START, 1)[1]
        for name, text in (("equal", agents.read_text()), ("no file", None), ("no block", "# AGENTS.md\n\nNotes.\n"),
                           ("no end marker", "# AGENTS.md\n\n{}\nNotes.\n".format(block.replace(canon.AGENTS_END, ""))),
                           ("end before start", "# AGENTS.md\n\n{}\n\n{}\n".format(
                               canon.AGENTS_END, block.replace(canon.AGENTS_END, "")))):
            with self.subTest(name):
                if text is None:
                    agents.unlink()
                else:
                    agents.write_text(text.replace("canon version {} or".format(canon.CANON_VERSION),
                                                   "canon version 1 or") if name != "equal" else text)
                self.assertEqual(self.run_canon("which", "src/base.py"), (0, "src/base.py: no design\n", ""))

    def test_a_canon_py_from_outside_the_project_refuses_before_the_version_check(self):
        self.record("canon version {} or later".format(canon.CANON_VERSION), "canon version 9999 or later")
        self.assertEqual(self.run_canon("which", "src/base.py", script=SCRIPT),
                         (1, "", OUTSIDE_INSTALL.format(SCRIPT)))


if __name__ == "__main__":
    unittest.main()
