"""Regression tests for scripts/validate.py, run on a copy in a scratch repository with no tests of its own."""

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


class SkillPlacementTest(unittest.TestCase):
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

    def validate(self):
        return subprocess.run([sys.executable, "-B", "scripts/validate.py"], cwd=self.root, capture_output=True,
                              text=True)

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


if __name__ == "__main__":
    unittest.main()
