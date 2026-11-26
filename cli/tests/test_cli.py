import shutil
import subprocess
import sysconfig
import unittest
from importlib.metadata import version


class InstalledCliTest(unittest.TestCase):
    def test_version_reports_the_installed_distribution(self) -> None:
        command = shutil.which("canon", path=sysconfig.get_path("scripts"))
        if command is None:
            self.fail("Installing canon-cli must provide the canon command")

        result = subprocess.run(
            [command, "--version"], capture_output=True, text=True, check=True
        )

        self.assertEqual(result.stdout.strip(), f"canon {version('canon-cli')}")
