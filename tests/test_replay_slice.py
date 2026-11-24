"""Run historical slices at the public CLI with a real worker protocol peer."""
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys

import test_trace_report
from test_replay_prepare import PLAN, PLAN_BODY, digest
from test_replay_run import RunnerFixture
from test_trace_report import CONV, GATE, PRIOR, SECOND, UNIT, start, write_lines
from test_trace_reviews import review_end, reviewer, sha, table


class SliceFixture(RunnerFixture):
    def dynamic_shell(self):
        """Identify the prerequisites of a trusted system program for the real namespace tests."""
        if sys.platform != "linux" or not shutil.which("bwrap") or not shutil.which("ldd"):
            self.skipTest("Linux Bubblewrap and a dynamic shell are required for this isolation check")
        shell = "/bin/sh"
        libraries = subprocess.run(["ldd", shell], text=True, capture_output=True)
        paths = re.findall(r"(?:=>\s+|^\s*)(/\S+)\s+\(", libraries.stdout, re.M)
        if libraries.returncode or len(paths) < 2:
            self.skipTest("the system shell does not have a separately testable loader and library")
        probe = ["bwrap", "--unshare-user", "--unshare-pid", "--unshare-net", "--disable-userns",
                 "--clearenv", "--ro-bind", shell, shell]
        fixtures = self.root / "fixture-sources"
        fixtures.mkdir()
        mappings = []
        for i, path in enumerate(paths):
            name = f"lib-{i}"
            shutil.copy2(path, fixtures / name)
            mappings.append(dict(fixture=name, target=path))
            probe.extend(["--ro-bind", path, path])
        result = subprocess.run([*probe, "--remount-ro", "/", "--", shell, "-c", "exit 0"], capture_output=True)
        if result.returncode:
            self.skipTest("host disallows Bubblewrap namespaces: " + result.stderr.decode(errors="replace").strip())
        self.config["settings"].update(test_runtime_files=mappings, bundle={})
        self.config["test_tools"] = [shell]
        self.write_config()
        return shell, fixtures

    def mapping(self, target, commands):
        path = self.root / "criteria.json"
        path.write_text(json.dumps(dict(schema=1, slice="S1", plan_blob=self.git(self.store, "rev-parse", target + ":" + PLAN),
                                        criteria=[dict(id=name, argv=argv, first_line=14, last_line=16)
                                                  for name, argv in commands])))
        return path

    def worker_slice(self, entries=None, brief="PRIVATE initial worker brief"):
        target = self.slice(entries)
        host = test_trace_report.TraceReport()
        host.project, host.codex = self.project, self.codex
        self.repo(self.project)
        opening = self.commit(self.project, PLAN_BODY.rstrip(), path=PLAN)
        done = self.commit(self.project, PLAN_BODY.replace("Status: in-progress", "Status: done").rstrip(),
                           at="2026-01-01T00:00:50Z", path=PLAN)
        self.events[1].update(at="2025-12-31T23:59:59Z", head=opening)
        self.events[2]["head"] = opening
        self.events[3]["head"] = done
        write_lines(self.log, self.events)
        boundary = host.boundary(4, "start slice P001 --slice S1 --parent " + PRIOR, "trace " + UNIT)
        launch = host.dispatch(8, "spawn_agent", "p001_s1", "launch", json.dumps({"agent_id": SECOND}))
        launch[0]["payload"]["arguments"] = json.dumps({"task_name": "p001_s1", "message": brief})
        resume = host.dispatch(22, "followup_task", "/root/p001_s1", "resume", json.dumps({"agent_id": SECOND}))
        resume[0]["payload"]["arguments"] = json.dumps({"target": "/root/p001_s1", "message": "PRIVATE later turn"})
        host.rollout(CONV, [host.native(1, "turn_context", model="model-a", effort="medium"), *boundary, *launch,
                            *resume, host.native(55, "turn_context", model="model-a", effort="medium")])
        host.rollout(SECOND, [host.native(9, "turn_context", model="worker-model", effort="low"),
                              *host.worker_turn(10, 17, 1, 2), *host.worker_turn(24, 32, 2, 3)],
                     parent=CONV, key="p001_s1")
        self.config["roles"]["worker"] = dict(model="worker-model", effort=None)
        self.write_config()
        return target


class RunSlices(SliceFixture):
    def test_resuming_after_a_stop_reblinds_every_previously_exported_slice_file(self):
        self.worker_slice()
        self.prepare()
        later = "PRIVATE retry instruction"
        stop = dict(envelope={"outcome": "stopped", "worker_status": None}, remove=["worker"])
        self.config["settings"].update(bundle={"files": {"note": later}}, actions=[stop, {}, {}, {}, {}, {}, {"brief": later}])
        self.write_config()
        self.replay()
        blind = self.out / "blind"
        prior = digest((blind / "packet.json").read_bytes())
        self.replay()
        self.assertNotEqual(digest((blind / "packet.json").read_bytes()), prior)
        for path in blind.rglob("*"):
            if path.is_file():
                self.assertNotIn(later.encode(), path.read_bytes(), path.name)

    def test_only_new_nonignored_project_files_reach_the_artifact_and_a_stop_cannot_freeze_a_final_tree(self):
        self.worker_slice({".gitignore": "*.log\n", "tracked.log": "tracked input"})
        self.prepare()
        files = {"ignored.log": "private diagnostic", "new": "project output"}
        self.config["settings"]["actions"] = [dict(bundle=dict(files=files, force="ignored.log")),
            dict(bundle=dict(files=files), envelope={"outcome": "stopped", "worker_status": None}, remove=["worker"]),
            dict(bundle=dict(files=files))]
        self.write_config()
        self.replay()
        first, stopped, good = self.journal()["attempts"][:3]
        self.assertEqual(first["worker_status"], "done")
        self.assertIsNone(first["artifact"])
        self.assertIn("ignored", first["artifact_reason"])
        self.assertEqual(stopped["outcome"], "stopped")
        self.assertIsNone(stopped["artifact"])
        packet = json.loads((self.out / "blind/packet.json").read_bytes())
        ref = next(a["artifact"] for a in packet["attempts"] if a["id"] == good["id"])
        view = json.loads((self.out / "blind" / ref["path"]).read_bytes())
        self.assertEqual({f["path"] for f in view["files"]}, {".gitignore", PLAN, "new", "tracked.log"})

    def test_a_worker_link_at_a_fixture_parent_cannot_read_or_overwrite_the_host_sentinel(self):
        opened = self.worker_slice()
        fixtures = self.root / "inputs"
        (fixtures / "dependency").mkdir(parents=True)
        (fixtures / "dependency/key").write_text("prepared fixture")
        outside = self.root / "outside"
        outside.mkdir()
        sentinel = outside / "key"
        sentinel.write_text("outside sentinel bytes")
        self.config["settings"]["bundle"] = dict(links={"dependency": str(outside)})
        self.config["test_tools"] = ["/bin/sh"]
        self.write_config()
        mapping = self.mapping(opened, [("observe", ["/bin/sh", "-c", "exit 0"])])
        self.prepare("--fixtures", fixtures, "--criteria", mapping)
        self.replay()
        for row in self.journal()["attempts"]:
            self.assertEqual(row["worker_status"], "done")
            test, = row["tests"]
            self.assertEqual(test["outcome"], "unavailable")
            self.assertIn("fixture", test["reason"])
        self.assertEqual(sentinel.read_text(), "outside sentinel bytes")
        self.assertNotIn(b"outside sentinel bytes",
                         b"".join(p.read_bytes() for p in (self.out / "blind").rglob("*") if p.is_file()))

    def test_later_review_matches_have_opaque_artifact_references_and_cannot_disclose_either_brief(self):
        self.worker_slice()
        people = [reviewer("spec", "one")]
        self.archived_review(GATE, None, None, people, {}, {"spec": "Target: archived code"})
        report = "### F1 [major] ABI defect\n"
        (self.store / GATE / "spec.md").write_text(report)
        later = [start(GATE, "code-review", "2026-01-01T00:01:00Z", parent=PRIOR, docs=["P001@r2"]),
                 review_end(GATE, "code-review", people, [dict(by=["spec:F1"], severity="major",
                                                               axis="spec", disposition="accepted")])]
        write_lines(self.log, self.events[:-1] + later + self.events[-1:])
        evidence = self.root / "later.tsv"
        table(evidence, [dict(project=str(self.project), unit=GATE, raw_row="1", report_stem="spec",
                              finding_id="F1", defect_group="private-abi", disposition="accepted",
                              end_sha256=sha(json.dumps(later[-1])), report_sha256=sha(report), source_locator="spec.md:L1")])
        receipt = self.prepare("--review-evidence", evidence)
        self.assertEqual(len(receipt["history"]["groups"]), 1)
        self.config["settings"].update(bundle={"files": {"notes": "PRIVATE initial worker brief\nPRIVATE changed dispatch"}},
                                       actions=[{"brief": "PRIVATE changed dispatch"}])
        self.write_config()
        self.replay()
        blind = self.out / "blind"
        packet = json.loads((blind / "packet.json").read_bytes())
        judgments = json.loads((blind / "judgments-template.json").read_bytes())
        gid = packet["history"]["groups"][0]["id"]
        self.assertNotEqual(gid, "private-abi")
        by_id = {a["id"]: a for a in packet["attempts"]}
        for row in judgments["attempts"]:
            self.assertEqual(row["groups"], [])
            self.assertEqual(row["later"], [dict(historical=gid, match="unknown", evidence=[by_id[row["id"]]["artifact"]])])
        public = b"".join(p.read_bytes() for p in blind.rglob("*") if p.is_file())
        for secret in (b"PRIVATE initial worker brief", b"PRIVATE changed dispatch", b"private-abi", b"worker-model"):
            self.assertNotIn(secret, public)

    def test_a_missing_dynamic_loader_or_library_is_unavailable(self):
        shell, fixtures = self.dynamic_shell()
        opened = self.worker_slice()
        mapping = self.mapping(opened, [("version", [shell, "-c", "exit 0"])])
        required = self.config["settings"]["test_runtime_files"]
        for i, missing in enumerate(required):
            with self.subTest(missing=missing["target"]):
                out = self.root / f"missing-runtime-{i}"
                self.prepare("--fixtures", fixtures, "--criteria", mapping, out=out)
                self.config["settings"]["test_runtime_files"] = [r for r in required if r != missing]
                self.write_config()
                self.replay(out=out)
                for row in self.journal(out)["attempts"]:
                    test, = row["tests"]
                    self.assertEqual(row["outcome"], "completed")
                    self.assertEqual(test["outcome"], "unavailable", missing)
                    self.assertIn("runtime", test["reason"])

    def test_real_dynamic_criteria_have_fresh_trees_fixtures_and_only_the_granted_files(self):
        shell, fixtures = self.dynamic_shell()
        (fixtures / "dependency").write_text("clean\n")
        opened = self.worker_slice()
        self.config["settings"]["bundle"] = dict(files={"source": "frozen\n",
            "project-test": ["100755", "#!/bin/sh\nread value < source && test \"$value\" = frozen\n"],
            "needs-interpreter": ["100755", "#!/usr/bin/env ungranted-interpreter\n"]})
        self.config["test_tools"].append("/usr/bin/env")
        self.write_config()
        private_path = shlex.quote(str(self.out / "private/receipt.json"))
        sibling = shlex.quote(str(self.out / "work"))
        checks = (f"test ! -e {private_path} && test ! -e {sibling} && test ! -e /etc/passwd && "
                  "test ! -e /proc/1/root && test ! -e /usr/bin/git && test ! -e .git && "
                  "test ! -e .agents/skills && test -z \"$REPLAY_TEST_SECRET\" && "
                  "test \"$PWD\" = /work && ! (echo writable > /root-file) && "
                  "read v < source && test \"$v\" = frozen && read d < dependency && test \"$d\" = clean")
        mapping = self.mapping(opened, [
            ("change-copy", [shell, "-c", checks + " && echo modified > source && echo modified > dependency"]),
            ("clean-copy", [shell, "-c", checks + " && echo 'worker-model on candidate arm'"]),
            ("project-command", ["./project-test"]), ("ordinary-failure", [shell, "-c", "exit 1"]),
            ("exit-127", [shell, "-c", "exit 127"]), ("ungranted", ["/usr/bin/git"]),
            ("missing-interpreter", ["./needs-interpreter"]), ("prose", None)])
        receipt = self.prepare("--fixtures", fixtures, "--criteria", mapping)
        self.replay(env=dict(os.environ, REPLAY_TEST_SECRET="outside-only"))
        expected = {"change-copy": "pass", "clean-copy": "pass", "project-command": "pass",
                    "ordinary-failure": "fail", "exit-127": "fail", "ungranted": "unavailable",
                    "missing-interpreter": "unavailable", "prose": "unavailable"}
        for a in self.journal()["attempts"]:
            self.assertEqual({t["id"]: t["outcome"] for t in a["tests"]}, expected,
                             [(t["id"], t["reason"]) for t in a["tests"]])
        packet = json.loads((self.out / "blind/packet.json").read_bytes())
        names = {p["id"]: c["id"] for p, c in zip(packet["task"]["criteria"], receipt["criteria"])}
        self.assertTrue(names.keys().isdisjoint(expected))
        for a in packet["attempts"]:
            tests = {names[t["id"]]: t for t in a["tests"]}
            self.assertEqual({k: t["outcome"] for k, t in tests.items()}, expected)
            body = json.loads((self.out / "blind" / tests["clean-copy"]["evidence"]["path"]).read_bytes())
            self.assertIn("[redacted]", body["stdout"])
            self.assertNotIn("worker-model", str(body))
            self.assertNotIn("candidate", str(body))
            artifact = json.loads((self.out / "blind" / a["artifact"]["path"]).read_bytes())
            self.assertEqual(next(f["content"] for f in artifact["files"] if f["path"] == "source"), "frozen\n")
        self.assertEqual((fixtures / "dependency").read_text(), "clean\n")
        self.assertEqual((self.out / "private/fixtures/dependency").read_text(), "clean\n")

    def test_runtime_grants_cannot_add_host_files_directories_or_overlapping_mounts(self):
        self.worker_slice()
        fixtures = self.root / "inputs"
        fixtures.mkdir()
        (fixtures / "granted").write_text("pinned runtime")
        self.prepare("--fixtures", fixtures)
        self.config["test_tools"] = ["/bin/sh"]
        def mapped(target, source="granted"):
            return dict(fixture=source, target=target)
        invalid = [[mapped("/lib/extra", str(self.out / "private/receipt.json"))],
                   [mapped("/lib/extra", "../outside")], [mapped("/lib/extra", "unsealed")],
                   [mapped("/work/lib")], [mapped("/proc/file")], [mapped("/sys/file")], [mapped("/dev/file")],
                   [mapped("/lib//file")], [mapped("/lib/../file")], [mapped(str(self.out / "private/file"))],
                   [mapped("/lib/runtime"), mapped("/lib/runtime/sub")], [mapped("/bin/sh")]]
        for grants in invalid:
            with self.subTest(grants=grants):
                self.config["settings"]["test_runtime_files"] = grants
                self.write_config()
                self.replay(error="grant")
        self.config["settings"].pop("test_runtime_files")
        for unsafe in (str(fixtures), str(self.out / "private/receipt.json")):
            with self.subTest(tool=unsafe):
                self.config["test_tools"] = [unsafe]
                self.write_config()
                self.replay(error="grant")
        self.assertEqual(self.calls(), [])

    def test_missing_isolation_and_prose_only_criteria_cannot_be_scored_as_test_failures(self):
        opened = self.worker_slice()
        mapping = self.mapping(opened, [("no-command", None), ("executable", ["/bin/sh", "-c", "exit 0"])])
        self.prepare("--criteria", mapping)
        self.config["test_tools"] = ["/bin/sh"]
        self.config["settings"]["bundle"] = {}
        self.write_config()
        tools = self.root / "commands"
        tools.mkdir()
        (tools / "git").symlink_to(shutil.which("git"))
        (tools / "python3").symlink_to(sys.executable)
        self.replay(env=dict(os.environ, PATH=str(tools)))
        packet = json.loads((self.out / "blind/packet.json").read_bytes())
        ids = {c["id"] for c in packet["task"]["criteria"]}
        self.assertEqual(len(ids), 2)
        self.assertTrue(ids.isdisjoint({"no-command", "executable"}))
        for attempt in packet["attempts"]:
            self.assertEqual({t["id"]: t["outcome"] for t in attempt["tests"]}, dict.fromkeys(ids, "unavailable"))
        for attempt in self.journal()["attempts"]:
            self.assertEqual(attempt["outcome"], "completed")
            tests = {t["id"]: t for t in attempt["tests"]}
            self.assertIn("command", tests["no-command"]["reason"])
            self.assertIn("sandbox", tests["executable"]["reason"])
            for criterion in tests.values():
                ref = criterion["evidence"]
                raw = (self.out / "private" / ref["path"]).read_bytes()
                self.assertEqual(digest(raw), ref["sha256"])
                self.assertEqual(json.loads(raw)["argv"], criterion["argv"])

    def test_incomplete_unexpected_and_conflicting_bundles_keep_only_the_verified_worker_observation(self):
        self.worker_slice()
        fixtures = self.root / "inputs"
        fixtures.mkdir()
        (fixtures / "fixture").write_text("prepared")
        self.prepare("--fixtures", fixtures)
        cases = [dict(ref="refs/heads/result"), dict(extra=True), dict(history=True), dict(prerequisite=True),
                 dict(version=2), dict(wrong_format=True), dict(force=".agents/skills/canon/SKILL.md"),
                 dict(force=".claude/skills/canon"), dict(force="fixture"), dict(gitlink=True), dict(corrupt=True),
                 dict(files={".agents/skills/canon/worker-note": "added inside the injected installation"})]
        self.config["settings"]["actions"] = [dict(bundle={"files": {"new": "new"}} | case) for case in cases]
        self.write_config()
        self.replay("--repetitions", 6)
        rows = self.journal()["attempts"]
        for i, case in enumerate(cases):
            with self.subTest(case=case):
                self.assertEqual((rows[i]["outcome"], rows[i]["worker_status"]), ("completed", "done"))
                self.assertIsNone(rows[i]["artifact"])
                self.assertTrue(rows[i]["artifact_reason"])
        packet = json.loads((self.out / "blind/packet.json").read_bytes())
        self.assertTrue(all(a["artifact"] is None for a in packet["attempts"]))

    def test_frozen_artifact_preserves_modes_deletions_and_link_targets_in_a_neutral_view(self):
        self.worker_slice({"obsolete": "deleted", "bin/run": "old"})
        self.prepare()
        sentinel = self.root / "sentinel"
        sentinel.write_text("host-only sentinel bytes")
        self.config["settings"]["bundle"] = dict(delete=["obsolete"], files={
            "bin/run": ["100755", "new executable\n"], "link": ["120000", "bin/run"],
            "external": ["120000", str(sentinel)], "candidate-note": "worker-model on candidate arm"})
        self.write_config()
        self.replay()
        blind = self.out / "blind"
        saved = (blind / "packet.json").read_bytes()
        for attempt in json.loads(saved)["attempts"]:
            self.assertIsInstance(attempt.get("artifact"), dict)
            ref = attempt["artifact"]
            raw = (blind / ref["path"]).read_bytes()
            self.assertEqual(digest(raw), ref["sha256"])
            files = {f["path"]: f for f in json.loads(raw)["files"]}
            self.assertEqual((files["bin/run"]["mode"], files["bin/run"]["content"]), ("100755", "new executable\n"))
            self.assertEqual((files["link"]["mode"], files["link"]["content"]), ("120000", "bin/run"))
            self.assertNotIn("obsolete", files)
            for secret in (b"host-only sentinel bytes", b"worker-model", b"candidate", str(self.root).encode(),
                           b".agents/skills", b".claude/skills"):
                self.assertNotIn(secret, raw)
        self.assertTrue(all(a["outcome"] == "completed" for a in self.journal()["attempts"]))
        (self.project / "bin").mkdir()
        (self.project / "bin/run").write_text("later repair")
        for obs in self.calls():
            (Path(obs["workspace"]) / "bin/run").write_text("mutable worker tree")
        self.replay()
        self.assertEqual((blind / "packet.json").read_bytes(), saved)

    def test_brief_comparison_uses_the_frozen_initial_launch_after_the_host_is_removed(self):
        self.worker_slice()
        receipt = self.prepare()
        self.codex.rename(self.root / "removed-host")
        self.config["settings"]["actions"] = [{}, {"brief": "PRIVATE changed instruction"},
                                              {"brief": None}, {"brief": ""}, {"brief": "PRIVATE later turn"}]
        self.write_config()
        self.replay()
        results = [r.get("brief_comparison", {}) for r in self.journal()["attempts"]]
        self.assertEqual([r.get("status") for r in results],
                         ["identical", "changed", "unavailable", "unavailable", "changed", "identical"])
        self.assertTrue(all(r["historical_sha256"] == receipt["historical_brief"]["sha256"] for r in results))
        self.assertEqual(results[1]["dispatched_sha256"], digest(b"PRIVATE changed instruction"))
        changed = self.journal()["attempts"][1]["id"]
        diff = (self.out / "private/jobs" / changed / "brief.diff").read_text().splitlines()
        self.assertIn("-PRIVATE initial worker brief", diff)
        self.assertIn("+PRIVATE changed instruction", diff)
        self.assertIsNone(results[2]["dispatched_sha256"])
        blind = b"".join(p.read_bytes() for p in (self.out / "blind").rglob("*") if p.is_file())
        for secret in (b"PRIVATE", b"cached_input", b"wall_seconds", b"brief_comparison"):
            self.assertNotIn(secret, blind)

    def test_a_later_turn_cannot_fill_in_an_absent_historical_brief(self):
        self.worker_slice(brief=None)
        receipt = self.prepare()
        self.assertEqual(receipt["historical_brief"]["status"], "unavailable")
        self.codex.rename(self.root / "removed-host")
        self.replay()
        for row in self.journal()["attempts"]:
            self.assertEqual(row["outcome"], "completed")
            comparison = row["brief_comparison"]
            self.assertEqual((comparison["status"], comparison["historical_sha256"]), ("unavailable", None))
            self.assertEqual(comparison["dispatched_sha256"], digest(b"PRIVATE initial worker brief"))

    def test_completed_workers_remain_measurable_without_an_artifact_and_host_stops_stay_distinct(self):
        self.worker_slice()
        self.prepare()
        self.config["settings"]["actions"] = [
            dict(envelope={"worker_status": status}) for status in ("done", "blocked", "stuck")
        ] + [dict(envelope={"outcome": "stopped", "reason": "host stopped", "worker_status": None}, remove=["worker"])]
        self.write_config()
        self.replay()
        rows = self.journal()["attempts"]
        self.assertEqual([(a["outcome"], a["worker_status"]) for a in rows[:4]],
                         [("completed", "done"), ("completed", "blocked"), ("completed", "stuck"), ("stopped", None)])
        self.assertEqual(self.journal()["comparable_pairs"], 2)
        self.assertEqual({c["stop_after"] for c in self.calls()}, {"worker_report"})
        self.assertTrue(all(set(c["roles"]) == {"parent", "worker"} for c in self.calls()))


class SHA256Slice(SliceFixture):
    object_format = "sha256"

    def test_imports_the_workers_sha256_tree_with_its_native_object_id(self):
        self.worker_slice()
        self.prepare()
        self.config["settings"]["bundle"] = dict(files={"result": "terminal bytes"})
        self.write_config()
        self.replay()
        for row in self.journal()["attempts"]:
            self.assertEqual(row["outcome"], "completed")
            self.assertEqual(len(row.get("artifact_tree", "")), 64)
