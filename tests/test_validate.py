"""Regression tests for scripts/validate.py, run on a copy in a scratch repository with no tests of its own."""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

VALIDATE = Path(__file__).resolve().parent.parent / "scripts" / "validate.py"
SKILL = "---\nname: canon-x\ndescription: Does x. Use when x is asked for.\n---\n\n# X\n"
README = ("# skills\n\n## Skills\n\n### execution\n\n| Skill | Summary | Trigger |\n|---|---|---|\n"
          "| `canon-x` | Does x. | Auto |\n")
WORD_TOKENS = ("class Encoding:\n    def encode(self, text):\n        return text.split()\n\n\n"
               "def get_encoding(name):\n    assert name == 'cl100k_base'\n    return Encoding()\n")
SUITE = '''import time, unittest
from pathlib import Path


def meet(mine, theirs):
    """Pass only while the test that touches `theirs` runs at the same time."""
    (Path(__file__).parent / mine).touch()
    deadline = time.time() + 10
    while not (Path(__file__).parent / theirs).exists():
        if time.time() > deadline:
            raise AssertionError("ran alone")
        time.sleep(0.05)


class T(unittest.TestCase):
    def test_a(self):
        meet("a", "b")

    def test_b(self):
        meet("b", "a")

    def test_fails(self):
        self.assertEqual(1, 2)

    @unittest.skip("fixture")
    def test_skipped(self):
        pass
'''


class ScratchRepoTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        (self.root / "scripts").mkdir()
        shutil.copy(VALIDATE, self.root / "scripts")
        self.write("skills/execution/canon-x/SKILL.md", SKILL)
        self.write("README.md", README)
        subprocess.run(["git", "init", "-q"], cwd=self.root, check=True)

    def write(self, rel, text):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def validate(self, tiktoken=None, extra_env=None):
        """Run validate.py, with `tiktoken` as the source of the tiktoken module it imports when given."""
        env = dict(os.environ)
        for key, value in (extra_env or {}).items():
            if value is None:
                env.pop(key, None)
            else:
                env[key] = value
        if tiktoken is not None:
            module = Path(tempfile.mkdtemp(dir=self.root))
            (module / "tiktoken.py").write_text(tiktoken)
            env["PYTHONPATH"] = str(module)
        return subprocess.run([sys.executable, "-B", "scripts/validate.py"], cwd=self.root, capture_output=True,
                              text=True, env=env)


class SkillPlacementTest(ScratchRepoTest):
    def test_a_skill_md_outside_skills_category_name_fails_validation(self):
        self.write(".gitignore", ".tmp/\n")
        self.write(".tmp/scratch/SKILL.md", SKILL)
        self.write("gone/SKILL.md", SKILL)
        subprocess.run(["git", "add", "gone"], cwd=self.root, check=True)
        (self.root / "gone/SKILL.md").unlink()
        result = self.validate()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("ok   SKILL.md placement", result.stdout)
        strays = ["docs/SKILL.md", "skills/execution/.draft/SKILL.md", "skills/execution/canon-x/templates/SKILL.md"]
        for rel in strays:
            self.write(rel, SKILL)
        subprocess.run(["git", "add", "docs"], cwd=self.root, check=True)
        result = self.validate()
        self.assertEqual(result.returncode, 1, result.stdout)
        reported = result.stdout.split("FAIL SKILL.md placement\n", 1)[1].split("\n", len(strays))[:len(strays)]
        self.assertEqual(reported, ["  - {} is not a skill's own skills/<category>/<name>/SKILL.md, yet the skills CLI "
                                    "would treat it as an installable skill".format(rel) for rel in strays])


class SkillReferenceTest(ScratchRepoTest):
    def add_canon(self):
        self.write("skills/governance/canon/SKILL.md", SKILL.replace("canon-x", "canon") + "\nIn `trace` calls, x.\n")
        self.write("README.md", README + "\n### governance\n\n| `canon` | Core. | Auto |\n")

    def test_markdown_fragments_resolve_to_numbered_heading_slugs_and_report_the_source_line(self):
        skill = "skills/execution/canon-x"
        self.write(f"{skill}/guide.md", "# Run `git` (again)!\n## Queue\n## Queue\n")
        self.write(f"{skill}/notes.md", "# Notes\n[Here](#notes) [Command](guide.md#run-git-again)\n"
                   "[Second](guide.md#queue-1 \"Title\") [External](https://outside.example/guide.md#absent)\n")
        self.assertEqual(self.validate(WORD_TOKENS).returncode, 0)
        self.write("OTHER.md", "# Other\n[Gone](#gone)\n")
        self.write(f"{skill}/notes.md", "# Notes\n[Third](guide.md#queue-2 \"Title\")\n[Missing file](absent.md#topic)\n")
        result = self.validate(WORD_TOKENS)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("OTHER.md:2:", result.stdout)
        self.assertIn("#gone", result.stdout)
        self.assertRegex(result.stdout, rf"{skill}/notes\.md:2: [^\n]*guide\.md#queue-2")
        self.assertRegex(result.stdout, rf"{skill}/notes\.md:3: [^\n]*absent\.md#topic")

    def test_only_prose_outside_the_full_fence_supplies_references_and_headings(self):
        notes = "skills/execution/canon-x/notes.md"
        for fence in ("`", "~"):
            with self.subTest(fence=fence):
                self.write(notes, f"# Real\n{fence * 4}markdown\n{fence * 3}\n## Example heading\n"
                           f"[Example](absent.md)\n{fence * 4} info\n[Example](absent-again.md)\n"
                           f"{fence * 5}\n[Typo](#example-heading)\n")
                result = self.validate(WORD_TOKENS)
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertIn(f"{notes}:9: missing heading for #example-heading", result.stdout)
                self.assertNotIn("absent", result.stdout)
        self.write(notes, "```sample```\n[Details](#missing)\n")
        self.assertIn(f"{notes}:2: missing heading for #missing", self.validate(WORD_TOKENS).stdout)

    def test_named_skills_and_slash_commands_must_be_installed(self):
        notes = "skills/execution/canon-x/notes.md"
        examples = ("Use the `canon-x` skill or run `/canon-x D001` or `$canon-x D001`.\n"
                    "A log mentions canon-log. The flag is `--name canon-log`.\n"
                    "Literal: ``Use the `canon-example` skill.``\n"
                    "````markdown\n```\nUse `canon-example`.\n````\n")
        self.write(notes, examples)
        self.assertEqual(self.validate(WORD_TOKENS).returncode, 0)
        self.write(notes, examples + "Use `canon-gone`.\nRun `/canon-typo P001`.\nRead the `canom-x` skill.\n"
                   "Run `$canon-missing P001`.\n")
        result = self.validate(WORD_TOKENS)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertRegex(result.stdout, rf"{notes}:8: [^\n]*canon-gone")
        self.assertRegex(result.stdout, rf"{notes}:9: [^\n]*canon-typo")
        self.assertRegex(result.stdout, rf"{notes}:10: [^\n]*canom-x")
        self.assertRegex(result.stdout, rf"{notes}:11: [^\n]*canon-missing")
        self.assertNotIn("canon-example", result.stdout)

    def test_workflow_pointers_resolve_sections_and_children_in_the_named_workflow(self):
        notes = "skills/execution/canon-x/notes.md"
        workflow = "skills/governance/canon/workflow.md"
        self.write(workflow, "# Workflow\n## Subagents\n### Reviewer file\n### Reviewer setup\n"
                   "## Review gate\n### Reviewer prompt\n## Fixes and checks\n## Notes (draft)\n")
        self.add_canon()
        examples = ("Use the `canon` skill's workflow (Subagents → Reviewer file and Reviewer setup).\n"
                    "See its workflow (Reviewer file, Fixes and checks, and Notes (draft)).\n"
                    "- The build workflow (GitHub Actions) changed the workflow (during release week).\n"
                    "Literal: `the workflow (Lost)`.\n")
        self.write(notes, examples)
        result = self.validate(WORD_TOKENS)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.write(notes, examples + "Read the workflow (Missing (draft)).\n"
                   "Follow the `canon` skill's workflow (Subagents → Reviewer file and Reviewer prompt).\n"
                   "- workflow (Missing section)\n1. workflow (Missing ordered section)\n"
                   "  + workflow (Missing nested section)\n2) workflow (Missing final section)\n")
        result = self.validate(WORD_TOKENS)
        self.assertEqual(result.returncode, 1, result.stdout)
        for number, pointer in enumerate(("Missing (draft)", "Subagents → Reviewer file and Reviewer prompt",
                                          "Missing section", "Missing ordered section", "Missing nested section",
                                          "Missing final section"), 5):
            self.assertRegex(result.stdout, rf"{notes}:{number}: [^\n]*{re.escape(pointer)}[^\n]*workflow\.md")

    def test_a_named_doc_types_pointer_reports_a_missing_destination(self):
        self.add_canon()
        notes = "skills/execution/canon-x/notes.md"
        self.write(notes, "Use the `canon` skill's doc types (Deferred findings).\n")
        result = self.validate(WORD_TOKENS)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertRegex(result.stdout, rf"{notes}:1: [^\n]*Deferred findings[^\n]*doc-types\.md")
        self.write("skills/governance/canon/doc-types.md", "# Doc types\n## Deferred findings\n")
        result = self.validate(WORD_TOKENS)
        self.assertEqual(result.returncode, 0, result.stdout)


class TextBudgetTest(ScratchRepoTest):
    def call_site(self, words):
        """A step whose second sentence, a trace call site, is `words` tokens long as WORD_TOKENS counts them."""
        return "1. Write the doc. Run `canon.py trace end <id> <outcome>`{} then stop.\n".format(" x" * (words - 8))

    def wrapped_call_site(self, words, after=""):
        """`call_site` with the call site wrapped onto a second line and `after` following it on that line."""
        half = (words - 8) // 2
        return "1. Write the doc. Run `canon.py trace end <id> <outcome>`{}\n   {}then stop.{}\n".format(
            " x" * half, "x " * (words - 8 - half), after)

    def test_a_call_site_is_a_whole_sentence_across_wrapped_lines(self):
        self.write("skills/execution/canon-x/SKILL.md", SKILL + "\n" + self.wrapped_call_site(40, " **Then** check it twice.")
                   + self.wrapped_call_site(41, " 2 more words.") + "## Last step\n" + self.call_site(40)[18:])
        self.write("skills/governance/canon/SKILL.md", "---\nname: canon\n---\n\nIn `trace` calls, x.\n")
        self.assertIn("FAIL D001 text budgets\n"
                      "  - skills/execution/canon-x/SKILL.md:10: a trace call site of 41 tokens (max 40)\nok   tests\n",
                      self.validate(WORD_TOKENS).stdout)

    def test_d001_text_budgets_are_measured_when_tiktoken_imports_and_skipped_with_how_to_run_them_otherwise(self):
        self.write("skills/execution/canon-x/SKILL.md", SKILL + "\n" + self.call_site(40))
        self.write("skills/governance/canon/SKILL.md", "---\nname: canon\n---\n\nIn `trace` calls," + " x" * 107 + "\n")
        self.write("skills/governance/canon/trace.md", "x " * 420)
        self.assertIn("ok   D001 text budgets", self.validate(WORD_TOKENS).stdout)
        missing = self.validate("raise ImportError('No module named tiktoken')")
        self.assertIn("skip D001 text budgets: tiktoken is not installed; run "
                      "`uv run --no-project --with tiktoken python3 scripts/validate.py`\n", missing.stdout)
        offline = self.validate("def get_encoding(name):\n    raise OSError('offline')\n")
        self.assertIn("skip D001 text budgets: tiktoken cannot load cl100k_base (offline)\n", offline.stdout)
        self.write("skills/execution/canon-x/SKILL.md", SKILL + "\n" + self.call_site(41))
        self.write("skills/governance/canon/SKILL.md", "---\nname: canon\n---\n\nIn `trace` calls," + " x" * 108 + "\n")
        self.write("skills/governance/canon/trace.md", "x " * 421)
        self.assertIn("FAIL D001 text budgets\n"
                      "  - skills/execution/canon-x/SKILL.md:8: a trace call site of 41 tokens (max 40)\n"
                      "  - skills/governance/canon/SKILL.md: the paragraph on trace placeholders is 111 tokens (max 110)\n"
                      "  - skills/governance/canon/trace.md: 421 tokens (max 420)\n", self.validate(WORD_TOKENS).stdout)
        self.write("skills/governance/canon/SKILL.md", "---\nname: canon\n---\n\nWhen tracing, in `trace` calls, x.\n")
        self.assertIn("  - skills/governance/canon/SKILL.md: no paragraph starts with In `trace` calls\n",
                      self.validate(WORD_TOKENS).stdout)


class RunTestsTest(ScratchRepoTest):
    def test_skips_print_each_reason_once_with_the_affected_test_names_and_still_pass(self):
        self.write("tests/test_x.py", '''import unittest

class Fixture(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        raise unittest.SkipTest("missing fixture")

    def test_one(self):
        pass

    def test_two(self):
        pass

class Runtime(unittest.TestCase):
    def test_formats(self):
        with self.subTest(fmt="png"):
            self.skipTest("missing decoder")
''')
        result = self.validate("raise ImportError('tiktoken')")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("ok   tests (3 skipped)\n"
                      "  skipped: missing fixture\n"
                      "    test_x.Fixture.test_one\n"
                      "    test_x.Fixture.test_two\n"
                      "  skipped: missing decoder\n"
                      "    test_x.Runtime.test_formats (fmt='png')\n", result.stdout)

    @unittest.skipIf((getattr(os, "process_cpu_count", os.cpu_count)() or 1) < 2,
                     "two tests run at once only on two CPUs")
    def test_tests_run_in_parallel_and_their_line_counts_skips_and_names_each_failure_and_broken_module(self):
        self.write("tests/test_x.py", SUITE)
        self.write("tests/test_broken.py", "raise ImportError('broken')\n")
        result = self.validate()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        out = result.stdout
        self.assertIn("FAIL tests (1 skipped)\n  - unittest.loader._FailedTest.test_broken\n"
                      "ImportError: Failed to import test module: test_broken\n", out)
        self.assertIn("ImportError: broken\n  - test_x.T.test_fails\nTraceback", out)
        self.assertIn("AssertionError: 1 != 2\n", out)
        self.assertIn("  skipped: fixture\n    test_x.T.test_skipped\n", out)
        self.assertNotIn("ran alone", out)

    def test_a_run_records_each_tests_duration_over_an_unreadable_record(self):
        self.write("tests/test_y.py", "import unittest\n\n\nclass T(unittest.TestCase):\n"
                                      "    def test_one(self):\n        pass\n\n    def test_two(self):\n        pass\n")
        for record in ("{", "[]"):
            self.write(".tmp/test-durations.json", record)
            self.assertIn("ok   tests\n", self.validate().stdout)
            durations = json.loads((self.root / ".tmp/test-durations.json").read_text())
            self.assertEqual(sorted(durations), ["test_y.T.test_one", "test_y.T.test_two"])
            self.assertTrue(all(seconds >= 0 for seconds in durations.values()), durations)

    def test_a_tests_directory_without_tests_fails_and_so_does_a_test_that_ends_its_worker_process(self):
        self.write("tests/helper.py", "")
        self.assertIn("FAIL tests\n  - no tests in tests/\n", self.validate().stdout)
        self.write("tests/test_exit.py", "import os, unittest\n\n\nclass T(unittest.TestCase):\n"
                                         "    def test_exit(self):\n        os._exit(3)\n")
        self.assertIn("FAIL tests\n  - a worker process died: ", self.validate().stdout)

    def _clean_host_dir(self):
        candidates = ["/var/tmp", os.environ.get("XDG_RUNTIME_DIR"), "/tmp", os.environ.get("XDG_CACHE_HOME"),
                      "/dev/shm"]
        try:
            candidates.append(str(Path.home() / ".cache"))
        except RuntimeError:
            pass
        for raw in candidates:
            if not raw:
                continue
            base = Path(raw)
            if not base.is_dir():
                continue
            resolved = base.resolve()
            if any((p / ".git").exists() or (p / "AGENTS.md").exists() for p in (resolved, *resolved.parents)):
                continue
            try:
                temp = tempfile.TemporaryDirectory(dir=resolved, prefix="test-validate-clean-")
            except OSError:
                continue
            self.addCleanup(temp.cleanup)
            return Path(temp.name).resolve()
        self.skipTest("host has no writable clean directory outside checkouts")

    def test_outside_checkout_skips_rerun_under_a_verified_clean_temp_root_and_preserve_unrelated_skips(self):
        self.write("tests/test_outside.py", '''import tempfile, unittest
from pathlib import Path


def require_clean_tmpdir(case):
    root = Path(tempfile.gettempdir()).resolve()
    for parent in (root, *root.parents):
        if (parent / ".git").exists() or (parent / "AGENTS.md").exists():
            case.skipTest(f"TMPDIR is inside {parent}, which holds .git or AGENTS.md")
    return root


class Outside(unittest.TestCase):
    def test_needs_clean_temp(self):
        root = require_clean_tmpdir(self)
        marker = root / "probe.txt"
        marker.write_text("ok")
        self.assertEqual(marker.read_text(), "ok")

    def test_outside_then_capability_skip(self):
        require_clean_tmpdir(self)
        self.skipTest("host lacks capability")

    @unittest.skip("unrelated capability")
    def test_unrelated(self):
        pass
''')
        dirty_tmp = self.root / "dirty-tmp"
        dirty_tmp.mkdir()
        dirty_agents = self.root / "dirty-agents"
        dirty_agents.mkdir()
        (dirty_agents / "AGENTS.md").write_text("# Agents\n")
        clean_dir = self._clean_host_dir()
        result = self.validate(
            "raise ImportError('tiktoken')",
            extra_env={
                "TMPDIR": str(dirty_tmp),
                "CANON_VALIDATE_CLEAN_TMPDIR": os.pathsep.join([str(dirty_tmp), str(dirty_agents), str(clean_dir)]),
            },
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("ok   tests (2 skipped)\n", result.stdout)
        self.assertIn(f"  rerun 2 outside-checkout test(s) under clean temp root {clean_dir}: 1 passed, 1 skipped\n",
                      result.stdout)
        self.assertIn("  skipped: host lacks capability\n    test_outside.Outside.test_outside_then_capability_skip\n",
                      result.stdout)
        self.assertIn("  skipped: unrelated capability\n    test_outside.Outside.test_unrelated\n", result.stdout)
        self.assertNotIn("which holds .git or AGENTS.md", result.stdout)
        default_run = self.validate(
            "raise ImportError('tiktoken')",
            extra_env={"TMPDIR": str(dirty_tmp), "CANON_VALIDATE_CLEAN_TMPDIR": None},
        )
        self.assertEqual(default_run.returncode, 0, default_run.stdout + default_run.stderr)
        self.assertRegex(default_run.stdout,
                         r"  rerun 2 outside-checkout test\(s\) under clean temp root .+: 1 passed, 1 skipped\n")
        self.assertNotIn("which holds .git or AGENTS.md", default_run.stdout)

    def test_outside_checkout_rerun_failure_fails_validation(self):
        self.write("tests/test_outside_fail.py", '''import tempfile, unittest
from pathlib import Path


class OutsideFail(unittest.TestCase):
    def test_fails_when_clean(self):
        root = Path(tempfile.gettempdir()).resolve()
        for parent in (root, *root.parents):
            if (parent / ".git").exists() or (parent / "AGENTS.md").exists():
                self.skipTest(f"TMPDIR is inside {parent}, which holds .git or AGENTS.md")
        self.fail("real failure outside checkout")
''')
        dirty_tmp = self.root / "dirty-tmp"
        dirty_tmp.mkdir()
        clean_dir = self._clean_host_dir()
        result = self.validate(
            "raise ImportError('tiktoken')",
            extra_env={"TMPDIR": str(dirty_tmp), "CANON_VALIDATE_CLEAN_TMPDIR": str(clean_dir)},
        )
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("FAIL tests\n", result.stdout)
        self.assertIn("real failure outside checkout", result.stdout)
        self.assertIn(f"  rerun 1 outside-checkout test(s) under clean temp root {clean_dir}: 0 passed, 1 failed\n",
                      result.stdout)

    def test_outside_checkout_skips_report_when_no_clean_temp_root_is_available(self):
        self.write("tests/test_outside_none.py", '''import tempfile, unittest
from pathlib import Path


class OutsideNone(unittest.TestCase):
    def test_needs_clean_temp(self):
        root = Path(tempfile.gettempdir()).resolve()
        for parent in (root, *root.parents):
            if (parent / ".git").exists() or (parent / "AGENTS.md").exists():
                self.skipTest(f"TMPDIR is inside {parent}, which holds .git or AGENTS.md")
''')
        dirty_tmp = self.root / "dirty-tmp"
        dirty_tmp.mkdir()
        result = self.validate(
            "raise ImportError('tiktoken')",
            extra_env={"TMPDIR": str(dirty_tmp), "CANON_VALIDATE_CLEAN_TMPDIR": ""},
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("ok   tests (1 skipped)\n", result.stdout)
        self.assertIn("  rerun 1 outside-checkout test(s) unavailable: no verified clean temporary root found\n",
                      result.stdout)
        self.assertIn("which holds .git or AGENTS.md", result.stdout)


if __name__ == "__main__":
    unittest.main()
