"""Distinguish an unavailable replay prerequisite from the result of a test that ran."""
import base64
import os
from pathlib import Path
import json
import shutil
import subprocess
import sys
from unittest.mock import patch

from test_replay_slice import SliceFixture


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from replay_git import ReplayError
from replay_sandbox import CriterionSandbox


class RuntimeFindings(SliceFixture):
    def test_slow_measured_exits_distinguish_a_required_grant_from_an_independent_assertion(self):
        shell, fixtures = self.dynamic_shell()
        opened = self.worker_slice()
        compiler = "missing-canon-replay-compiler"
        formatter = "missing-canon-replay-formatter"
        self.config["test_tools"].extend([shutil.which("sleep"), "/usr/bin/" + compiler,
                                          "/usr/bin/" + formatter])
        self.write_config()
        checks = [("assertion", [shell, "-c", "sleep 0.3; echo original; echo assertion >&2; test actual = expected"]),
                  ("compiler", [shell, "-c", f"sleep 0.3; echo build; {compiler} main.c"]),
                  ("expired", [shell, "-c", f"if command -v {formatter}; then sleep 1; fi; exit 1"])]
        self.prepare("--fixtures", fixtures, "--criteria", self.mapping(opened, checks))
        hook = self.root / "short-control-clock"
        hook.mkdir()
        (hook / "sitecustomize.py").write_text("import sys\nif sys.argv[0].endswith('replay_supervisor.py'):\n"
                                              "    import replay_sandbox\n    replay_sandbox.CONTROL_SECONDS = 0.12\n")
        scripts = Path(__file__).resolve().parents[1] / "scripts"
        self.replay(env=dict(os.environ, PYTHONPATH=os.pathsep.join((str(hook), str(scripts)))))
        for attempt in self.journal()["attempts"]:
            rows = {row["id"]: row for row in attempt["tests"]}
            row = rows["assertion"]
            self.assertEqual(row["outcome"], "fail", row["reason"])
            evidence = json.loads((self.out / "private" / row["evidence"]["path"]).read_bytes())
            self.assertEqual(evidence["exit_code"], 1)
            self.assertEqual(base64.b64decode(evidence["stdout_base64"]), b"original\n")
            self.assertEqual(base64.b64decode(evidence["stderr_base64"]), b"assertion\n")
            row = rows["compiler"]
            self.assertEqual(row["outcome"], "unavailable", row["reason"])
            self.assertIn(compiler, row["reason"])
            evidence = json.loads((self.out / "private" / row["evidence"]["path"]).read_bytes())
            self.assertEqual(evidence["exit_code"], 127)
            self.assertEqual(base64.b64decode(evidence["stdout_base64"]), b"build\n")
            self.assertIn(compiler.encode(), base64.b64decode(evidence["stderr_base64"]))
            self.assertEqual(rows["expired"]["outcome"], "fail")

    def test_nested_and_unobservable_build_products_keep_missing_prerequisites_out_of_the_denominator(self):
        shell, fixtures = self.dynamic_shell()
        opened = self.worker_slice({"tests/keep": "existing directory"})
        tool = "missing-canon-replay-compiler"
        self.config["test_tools"].append("/usr/bin/" + tool)
        self.write_config()
        def wrapped(program):
            return f"( {tool} main.c 2>&- && {program} 2>&- ) || exit 1"
        generated = 'name=compiled_program; cd tests; ' + wrapped('"./$name"')
        opaque = 'suffix=program; name=$(printf "compiled_%s" "$suffix"); cd tests; ' + wrapped('"./$name"')
        hints = " ".join(f"./unused-{i}" for i in range(22))
        boolean = f'if {tool} 2>&- && "./$name" 2>&-; then :; else false; fi'
        criteria = [("nested", [shell, "-c", "cd tests; " + wrapped("./compiled_program")]),
                    ("variable", [shell, "-c", generated]), ("computed", [shell, "-c", opaque]),
                    ("budget", [shell, "-c", f": {hints}; cd tests; " + wrapped("./compiled_program")]),
                    ("boolean", [shell, "-c", "name=compiled_program; cd tests; " + boolean]),
                    ("opaque-boolean", [shell, "-c", 'name=$(printf "%s_%s" compiled program); cd tests; ' + boolean]),
                    ("assertion", [shell, "-c", f"cd tests; {tool} 2>&-; : {hints}; test actual = expected"])]
        self.prepare("--fixtures", fixtures, "--criteria", self.mapping(opened, criteria))
        self.replay()
        for attempt in self.journal()["attempts"]:
            rows = {r["id"]: r for r in attempt["tests"]}
            for name in ("nested", "variable", "computed", "budget", "boolean", "opaque-boolean"):
                self.assertEqual(rows[name]["outcome"], "unavailable", name)
                self.assertIn(tool, rows[name]["reason"])
            self.assertEqual(rows["boolean"]["reason"], "granted child executable unavailable: /usr/bin/" + tool)
            self.assertEqual(rows["assertion"]["outcome"], "fail")

    def test_shell_line_boundaries_end_a_lookup_before_a_missing_compiler(self):
        shell, fixtures = self.dynamic_shell()
        opened = self.worker_slice()
        tool = "missing-canon-replay-compiler"
        formatter = "missing-canon-replay-formatter"
        self.config["test_tools"].extend("/usr/bin/" + name for name in (tool, formatter))
        self.write_config()
        setup = 'name=$(printf "%s_%s" compiled program); '
        lookup = "command -v " + formatter
        build = f'if {tool} 2>&- && "./$name" 2>&-; then :; else false; fi'
        builds = {"semicolon": lookup + "; " + build,
                  "newline": lookup + "\n" + build,
                  "comment": lookup + " # comment with an unmatched quote '\n" + build,
                  "quoted-lookup": 'command -v "first\n#literal"\n' + build,
                  "continued-name": lookup + "\n" + build.replace("-compiler", "-com\\\npiler"),
                  "continued-guard": lookup + "\n" + build.replace("&& ", "&& # next line\n"),
                  "multiline-then": f'{lookup}\nif {tool} 2>&-\nthen\n"./$name" 2>&-\nelse false; fi'}
        checks = [(name, [shell, "-c", setup + body]) for name, body in builds.items()]
        for name, argument in (("quoted", "'first\nsecond'"), ("continued-query", "first \\\n")):
            body = f'if command -v {argument} {tool} && "./$name" 2>&-; then :; fi; {tool} 2>&-; test a = b'
            checks.append((name, [shell, "-c", setup + body]))
        self.prepare("--fixtures", fixtures, "--criteria", self.mapping(opened, checks))
        self.replay()
        for attempt in self.journal()["attempts"]:
            for row in attempt["tests"]:
                with self.subTest(criterion=row["id"]):
                    if row["id"] in builds:
                        self.assertEqual(row["outcome"], "unavailable")
                        self.assertIn(tool, row["reason"])
                    else:
                        self.assertEqual(row["outcome"], "fail")

    def test_shell_command_invocations_and_lookups_distinguish_an_opaque_build_from_an_assertion(self):
        shell, fixtures = self.dynamic_shell()
        opened = self.worker_slice({"tests/keep": "existing directory"})
        tool = "missing-canon-replay-compiler"
        self.config["test_tools"].append("/usr/bin/" + tool)
        self.write_config()
        setup = 'name=$(printf "%s_%s" compiled program); cd tests; '
        checks = []
        for name, invocation in (("direct", ""), ("command", "command"), ("path", "command -p"),
                                 ("options-end", "command --"), ("path-options-end", "command -p --")):
            body = f'if {tool} 2>&- && {invocation} "./$name" 2>&-; then :; else false; fi'
            checks.append((name, [shell, "-c", setup + body]))
        for name, lookup in (("lookup", "command -v"), ("verbose-lookup", "command -V"),
                             ("lookup-with-options", "command -pv --")):
            body = f'if {tool} 2>&- && {lookup} "./$name"; then :; fi; test actual = expected'
            checks.append((name, [shell, "-c", setup + body]))
        checked = f'if command -p -V -- {tool}; then "./$name" 2>&-; fi; {tool} 2>&-; test actual = expected'
        checks.append(("lookup-of-tool", [shell, "-c", setup + checked]))
        self.prepare("--fixtures", fixtures, "--criteria", self.mapping(opened, checks))
        self.replay()
        for attempt in self.journal()["attempts"]:
            for row in attempt["tests"]:
                if "lookup" in row["id"]:
                    self.assertEqual(row["outcome"], "fail", row["id"])
                else:
                    self.assertEqual(row["outcome"], "unavailable", row["id"])
                    self.assertIn(tool, row["reason"])

    def test_a_normalized_build_failure_depends_on_the_compiler_reaching_its_generated_program(self):
        shell, fixtures = self.dynamic_shell()
        opened = self.worker_slice()
        compiler = "missing-canon-replay-compiler"
        formatter = "missing-canon-replay-formatter"
        self.config["test_tools"].extend("/usr/bin/" + name for name in (compiler, formatter))
        optional = f"if command -v {formatter} > lookup; then {formatter} 2>&- || :; fi"
        wrapped = f"( {compiler} main.c 2>&- && ./compiled_program 2>&- ) || exit 1"
        script = f"""#!/bin/sh
program='./compiled program'
({compiler} main.c 2>&- && "$program" 2>&-) || exit 1
"""
        self.config["settings"]["bundle"] = {"files": {"build-and-run": ["100755", script]}}
        self.write_config()
        command = f"echo original-output; echo original-error >&2; {optional}; {wrapped}"
        mapping = self.mapping(opened, [
            ("wrapped", [shell, "-c", command]), ("script", ["./build-and-run"]),
            ("producer-exit", [shell, "-c", f"{compiler} main.c 2>&- || exit 1; ./compiled_program 2>&-"]),
            ("tool-only", [shell, "-c", f"{optional}; {compiler} main.c 2>&- || exit 1"]),
            ("ignored", [shell, "-c", f"{compiler} main.c 2>&-; test actual = expected"]),
            ("unrelated-product", [shell, "-c", f"{compiler} main.c 2>&- || :; ./compiled_program 2>&- || exit 1"]),
            ("optional", [shell, "-c", f"{optional}; test actual = expected"])])
        self.prepare("--fixtures", fixtures, "--criteria", mapping)
        self.replay()
        for attempt in self.journal()["attempts"]:
            rows = {item["id"]: item for item in attempt["tests"]}
            for name in ("wrapped", "script", "producer-exit", "tool-only"):
                self.assertEqual(rows[name]["outcome"], "unavailable", name)
                self.assertIn(compiler, rows[name]["reason"])
                self.assertNotIn(formatter, rows[name]["reason"])
            for name in ("ignored", "unrelated-product", "optional"):
                self.assertEqual(rows[name]["outcome"], "fail", name)
            evidence = json.loads((self.out / "private" / rows["wrapped"]["evidence"]["path"]).read_bytes())
            self.assertEqual(evidence["exit_code"], 1)
            self.assertEqual(base64.b64decode(evidence["stdout_base64"]), b"original-output\n")
            self.assertEqual(base64.b64decode(evidence["stderr_base64"]), b"original-error\n")

    def test_child_tool_evidence_distinguishes_a_missing_compiler_from_an_intentional_failure(self):
        shell, fixtures = self.dynamic_shell()
        opened = self.worker_slice()
        compiler = "/usr/bin/missing-canon-replay-compiler"
        self.config["test_tools"].append(compiler)
        self.config["settings"]["bundle"] = dict(files={"build": ["100755", "#!/bin/sh\n" + compiler + " main.c\n"],
            "quiet": ["100755", "#!/bin/sh\n" + compiler + " main.c 2>&- || exit 42\n"]})
        self.write_config()
        optional = f"if command -v {compiler} >lookup.log; then {compiler} || :; fi; test actual = expected"
        guarded = f'if command -v {compiler}; then {compiler} 2>&- && :; fi; test "$actual" = expected'
        pipeline = f"{compiler} main.c 2>&- && ./expected-build 2>&-"
        mapping = self.mapping(opened, [("build", ["./build"]), ("quiet", ["./quiet"]), ("pipeline", [shell, "-c", pipeline]),
                                        ("independent", [shell, "-c", optional]),
                                        ("guarded-optional", [shell, "-c", guarded]),
                                        ("message", [shell, "-c", f"echo '{compiler}: not found' >&2; exit 127"]),
                                        ("deliberate", [shell, "-c", "exit 127"]),
                                        ("optional", [shell, "-c", "command -v missing-canon-replay-compiler || exit 0"])])
        self.prepare("--fixtures", fixtures, "--criteria", mapping)
        self.replay()
        for attempt in self.journal()["attempts"]:
            rows = {r["id"]: r for r in attempt["tests"]}
            self.assertEqual(rows["build"]["outcome"], "unavailable")
            self.assertEqual(rows["quiet"]["outcome"], "unavailable")
            self.assertIn(compiler, rows["quiet"]["reason"])
            self.assertEqual(rows["pipeline"]["outcome"], "unavailable")
            observed = self.out / "private" / rows["quiet"]["evidence"]["path"]
            self.assertEqual(json.loads(observed.read_bytes())["exit_code"], 42)
            self.assertIn(compiler, rows["build"]["reason"])
            self.assertEqual(rows["deliberate"]["outcome"], "fail", rows["deliberate"]["reason"])
            self.assertEqual(rows["message"]["outcome"], "fail")
            self.assertEqual(rows["independent"]["outcome"], "fail")
            self.assertEqual(rows["guarded-optional"]["outcome"], "fail")
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
