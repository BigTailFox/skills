"""Distinguish an unavailable replay prerequisite from the result of a test that ran."""
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

from test_replay_slice import SliceFixture


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from replay_git import ReplayError
from replay_sandbox import CriterionSandbox


class RuntimeFindings(SliceFixture):
    def test_child_tool_evidence_distinguishes_a_missing_compiler_from_an_intentional_failure(self):
        shell, fixtures = self.dynamic_shell()
        opened = self.worker_slice()
        compiler = "/usr/bin/missing-canon-replay-compiler"
        self.config["test_tools"].append(compiler)
        self.config["settings"]["bundle"] = dict(files={"build": ["100755", "#!/bin/sh\n" + compiler + " main.c\n"]})
        self.write_config()
        mapping = self.mapping(opened, [("build", ["./build"]), ("deliberate", [shell, "-c", "exit 127"]),
                                        ("optional", [shell, "-c", "command -v missing-canon-replay-compiler || exit 0"])])
        self.prepare("--fixtures", fixtures, "--criteria", mapping)
        self.replay()
        for attempt in self.journal()["attempts"]:
            rows = {r["id"]: r for r in attempt["tests"]}
            self.assertEqual(rows["build"]["outcome"], "unavailable")
            self.assertIn(compiler, rows["build"]["reason"])
            self.assertEqual(rows["deliberate"]["outcome"], "fail")
            self.assertEqual(rows["optional"]["outcome"], "pass")

    def test_a_worker_directory_obstructs_a_fixture_file_before_materialization(self):
        job = self.root / "case/private/jobs/attempt"
        job.mkdir(parents=True)
        with self.assertRaisesRegex(ReplayError, "obstructs a fixture destination: dependency"):
            CriterionSandbox(job, {"tools": {}, "runtime": {}}, {"dependency/child": ("100644", b"worker")},
                             {"dependency": {"sha256": "0" * 64, "mode": "100644"}})

    def test_loader_output_can_measure_an_absent_library_even_with_a_success_exit(self):
        sandbox = CriterionSandbox.__new__(CriterionSandbox)
        result = subprocess.CompletedProcess([], 0, stdout=b"  libabi.so => not found\n", stderr=b"")
        with patch.object(sandbox, "executable", side_effect=lambda name: (name, b"elf")), \
                patch("replay_sandbox.elf_interpreter", return_value="/loader"), \
                patch.object(sandbox, "invoke", return_value=(result, [{"exit-code": 0}])):
            with self.assertRaisesRegex(ReplayError, "libabi.so => not found"):
                sandbox.check_runtime(self.root, "/compiler")
