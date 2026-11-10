"""Regression tests for scripts/validate.py, run on a copy in a scratch repository with no tests of its own."""

import os
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

    def validate(self, tiktoken=None):
        """Run validate.py, with `tiktoken` as the source of the tiktoken module it imports when given."""
        env = dict(os.environ)
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


if __name__ == "__main__":
    unittest.main()
