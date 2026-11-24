"""Exercise the public replay CLI against a machine-local executable and real checkouts."""
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time

from test_replay_prepare import DESIGN, SCRIPT, ReplayFixture, digest
from test_trace_report import CONV, UNIT, write_lines
from test_trace_reviews import reviewer, table


PEER = Path(__file__).with_name("replay_runner_fixture.py")


class RunnerFixture(ReplayFixture):
    def setUp(self):
        super().setUp()
        self.runner = self.root / "offline-runner"
        shutil.copyfile(PEER, self.runner)
        self.runner.chmod(0o755)
        self.observations = self.root / "observations.jsonl"
        self.config_path = self.root / "runner.json"
        self.config = dict(schema=1, host="codex", default_effort="medium", destinations=["local"],
                           roles={k: dict(model="model-a", effort=None) for k in ("parent", "spec", "standards", "same-model")},
                           read_paths=["."], test_tools=[], settings={"log": str(self.observations)})
        self.write_config()

    def write_config(self):
        self.config_path.write_text(json.dumps(self.config))

    def command(self, *extra, out=None):
        return [sys.executable, str(SCRIPT), "run", str(out or self.out), "--runner", str(self.runner),
                "--runner-config", str(self.config_path), *map(str, extra)]

    def replay(self, *extra, out=None, error=None):
        result = subprocess.run(self.command(*extra, out=out), text=True, capture_output=True, timeout=45)
        if error:
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(error, result.stderr)
        else:
            self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        return result

    def calls(self):
        return [json.loads(line) for line in self.observations.read_text().splitlines()] if self.observations.exists() else []

    def gate(self, entries=None, **kwargs):
        self.review("gate", {DESIGN: "---\nrevision: 3\n---\n", **(entries or {})}, docs=["D001@r3"], **kwargs)

    def code_review(self):
        base = self.pin(self.store, self.tree(self.store, {"abi.h": "old"}))
        entries = {"abi.h": "new"}
        target = self.pin(self.store, self.tree(self.store, entries), base)
        people = [reviewer(r, r) for r in ("spec", "standards")]
        line = f"Target: `git diff {base} {target} -- abi.h`\nRequested delivery: Preserve the ABI."
        self.review("code-review", entries, baseline=base, people=people, prompts={p["role"]: line for p in people})

    def prepare_known_review(self):
        self.code_review()
        body = b"### F1 [major] ABI result in model-a\nProblem: Missing value.\n"
        findings = []
        for role in ("spec", "standards"):
            (self.store / UNIT / (role + ".md")).write_bytes(body)
            findings.append(dict(by=[role + ":F1"], axis=role, severity="major", disposition="accepted"))
        event = self.events[-1]
        event["dispositions"]["findings"] = findings
        write_lines(self.log, self.events)
        evidence = self.root / "review-evidence.tsv"
        rows, catalog = [], []
        for i, role in enumerate(("spec", "standards")):
            prompt = (self.store / UNIT / (role + "-prompt.md")).read_bytes()
            common = dict(project=str(self.project), unit=UNIT, report_stem=role, reviewer_key=role, phase="first",
                          report_sha256=digest(body), prompt_sha256=digest(prompt), scope_lines="1-1")
            rows.append(dict(common, raw_row=str(i+1), finding_id="F1", defect_group="private-defect",
                             disposition="accepted", raw_disposition="accepted",
                             end_sha256=digest(json.dumps(event).encode()), source_locator=f"{role}.md:L1"))
            catalog.append(dict(common, role=role, reviewer_id=role, model="model-a", groups="F1=private-defect",
                                decisions="", decision_locator="", decision_sha256=""))
        table(evidence, rows)
        table(self.root / "review-adjudications.tsv", catalog)
        return self.prepare("--review-evidence", evidence)

    def different_suite(self, tool="# tool\n"):
        files = {"canon/SKILL.md": "New suite.\n", "canon/scripts/canon.py": ("100755", tool)}
        new = self.pin(self.skills, self.tree(self.skills, {"skills/governance/" + k: v for k, v in files.items()}))
        self.git(self.skills, "update-ref", "HEAD", new)

    def journal(self, out=None):
        return json.loads(((out or self.out) / "private/run.json").read_bytes())

    def hold_peer(self):
        self.hold = self.root / "hold"
        self.hold.touch()
        self.config["settings"]["hold"] = str(self.hold)
        self.write_config()
        self.addCleanup(self.hold.unlink, missing_ok=True)

    def controller(self):
        if not hasattr(self, "_controllers"):
            self._controllers = []
            self.addCleanup(self.reap_children)
            if sys.platform == "linux":
                import ctypes
                self.libc = ctypes.CDLL(None)
                prior = ctypes.c_int()
                self.assertEqual(self.libc.prctl(37, ctypes.byref(prior), 0, 0, 0), 0)
                self.assertEqual(self.libc.prctl(36, 1, 0, 0, 0), 0)
                self.previous_subreaper = prior.value
        p = subprocess.Popen(self.command(), stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        self._controllers.append(p)
        return p

    def reap_children(self):
        for p in self._controllers:
            if p.poll() is None:
                p.kill()
            p.communicate(timeout=8)
        if hasattr(self, "hold"):
            self.hold.unlink(missing_ok=True)
        pids = {c[key] for c in self.calls() for key in ("pid", "supervisor")}
        for pid in pids:
            try:
                proc = Path("/proc") / str(pid) / "cmdline"
                if proc.is_file() and str(self.root).encode() in proc.read_bytes():
                    os.kill(pid, signal.SIGKILL)
            except (FileNotFoundError, ProcessLookupError):
                pass
        if hasattr(self, "previous_subreaper"):
            for pid in pids:
                try:
                    os.waitpid(pid, 0)
                except ChildProcessError:
                    pass
            self.libc.prctl(36, self.previous_subreaper, 0, 0, 0)

    def await_calls(self, count):
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if len(self.calls()) >= count:
                return self.calls()
            time.sleep(0.025)
        self.fail(f"only {len(self.calls())} runner calls before timeout")


class RunReviews(RunnerFixture):
    def test_public_live_diff_preserves_the_patch_and_visible_untracked_files_after_install(self):
        base = self.pin(self.store, self.tree(self.store, {"src/deleted": "old\n", "outside": "old\n"}))
        tracked = {"src/added": "staged\n", "outside": "changed\n"}
        tree = self.tree(self.store, tracked)
        expected = subprocess.check_output(["git", "-C", self.store, "diff", "--binary", "--full-index",
                                            base, tree, "--", "src"])
        prompt = f"Target: `git diff --binary --full-index {base} -- src`\nUntracked files: src/deleted, src/run"
        self.review("code-review", tracked | {"src/deleted": "replacement\n", "src/run": ("100755", "run\n")},
                    baseline=base, prompts={"spec": prompt})
        receipt = self.prepare()
        self.replay()
        for obs in self.calls():
            root = Path(obs["workspace"])
            self.assertEqual(obs["untracked"], ["src/deleted", "src/run"])
            self.assertEqual((root / "src/deleted").read_text(), "replacement\n")
            self.assertTrue(os.access(root / "src/run", os.X_OK))
            self.assertEqual(subprocess.check_output(["git", "-C", root, "diff", "--binary", "--full-index",
                                                      receipt["task"]["input"]["baseline"], "--", "src"]), expected)

    def test_observed_parent_effort_wins_and_conflicting_host_model_never_dispatches(self):
        from test_trace_report import TraceReport
        self.gate()
        host = TraceReport()
        host.project, host.codex = self.project, self.codex
        def record(model):
            seq = [host.native(1, "turn_context", model=model, effort="high"),
                   *host.boundary(4, "start gate D001 --tier L1 --model model-a", "trace " + UNIT),
                   *host.boundary(64, "end " + UNIT + " delivered", "trace " + UNIT + " ended", "end")]
            host.rollout(CONV, seq)
        record("model-a")
        self.config["roles"]["parent"]["effort"] = "low"
        self.config["roles"]["same-model"]["effort"] = "medium"
        self.write_config()
        self.prepare()
        record("changed-model")
        out = self.root / "conflicting"
        self.prepare(out=out)
        self.codex.rename(self.root / "removed-host-profile")
        self.replay(out=out, error="model")
        self.assertEqual(self.calls(), [])
        self.replay()
        self.assertTrue(all(c["roles"]["parent"]["effort"] == "high" and c["roles"]["same-model"]["effort"] == "medium"
                            for c in self.calls()))

    def test_unassigned_tracked_skill_or_suite_file_cannot_enter_an_install(self):
        for i, stale in enumerate((".agents/skills/canon-extra/SKILL.md", ".agents/skills/canon/extra.md",
                                   ".claude/skills/canon-extra/SKILL.md", ".gitignore")):
            self.events = self.events[:1]
            self.gate({stale: "!.agents/skills/canon/SKILL.md\n" if stale == ".gitignore" else "From a different installation."})
            out = self.root / f"collision-{i}"
            self.prepare(out=out)
            self.replay(out=out)
            self.assertTrue(all(a["outcome"] == "incompatible" for a in self.journal(out)["attempts"]), stale)
        self.assertEqual(self.calls(), [])

    def test_only_verified_objects_and_granted_installs_reach_cursor_and_claude_workspaces(self):
        for host in ("cursor", "claude-code"):
            self.events = self.events[:1]
            self.gate()
            self.events[1]["host"] = host
            write_lines(self.log, self.events)
            out = self.root / host
            receipt = self.prepare(out=out)
            saved = out / "private/input"
            self.git(saved, "remote", "add", "private-upstream", str(self.project))
            secret = self.pin(saved, self.tree(saved, {"private-repair": "a later repair"}))
            self.git(saved, "read-tree", receipt["task"]["input"]["target"])
            self.git(saved, "update-ref", "refs/private/later", secret)
            self.config.update(host=host, read_paths=[DESIGN, ".claude/skills" if host == "claude-code" else ".agents/skills"])
            self.write_config()
            self.replay(out=out)
            calls = self.calls()[-6:]
            self.assertEqual(len(calls), 6)
            self.assertTrue(all(c["skills"] == self.config["read_paths"][1] for c in calls))
            self.assertTrue(all("refs/private/later" not in c["refs"] and not c["remotes"] for c in calls))
            for c in calls:
                seen = subprocess.run(["git", "-C", c["workspace"], "cat-file", "-e", secret], capture_output=True)
                self.assertNotEqual(seen.returncode, 0)

    def test_dead_supervisor_without_a_terminal_record_leaves_its_slot_uncertain(self):
        self.gate()
        self.prepare()
        self.hold_peer()
        controller = self.controller()
        first, = self.await_calls(1)
        os.kill(first["supervisor"], signal.SIGKILL)
        self.hold.unlink()
        _, err = controller.communicate(timeout=15)
        self.assertEqual(controller.returncode, 0, err)
        self.replay()
        rows = self.journal()["attempts"]
        self.assertEqual(len(rows), 6)
        self.assertEqual((rows[0]["id"], rows[0]["outcome"]), (first["attempt"], "uncertain"))
        self.assertIn("terminal", rows[0]["reason"])
        self.assertEqual(self.journal()["incomplete_pairs"], [1])
        self.assertEqual(self.journal()["comparable_pairs"], 2)
        self.assertTrue(self.journal()["sparse_pairs"])
        self.assertEqual(len(self.calls()), 6)

    def test_verified_runner_termination_can_retry_its_slot_with_a_fresh_attempt(self):
        self.gate()
        self.prepare()
        self.hold_peer()
        controller = self.controller()
        first, = self.await_calls(1)
        os.kill(first["pid"], signal.SIGTERM)
        self.hold.unlink()
        _, err = controller.communicate(timeout=15)
        self.assertEqual(controller.returncode, 0, err)
        prior_digest = digest((self.out / "blind/packet.json").read_bytes())
        self.replay()
        self.assertNotEqual(digest((self.out / "blind/packet.json").read_bytes()), prior_digest)
        self.replay()
        rows = self.journal()["attempts"]
        self.assertEqual(len(self.calls()), 7)
        self.assertEqual((rows[0]["id"], rows[0]["outcome"], rows[0]["returncode"]),
                         (first["attempt"], "stopped", -signal.SIGTERM))
        completed = [a for a in rows if a["outcome"] == "completed"]
        self.assertEqual(len({(a["arm"], a["pair"]) for a in completed}), 6)
        self.assertEqual(self.journal()["comparable_pairs"], 3)
        self.assertFalse(self.journal()["sparse_pairs"])
        self.assertEqual((rows[-1]["pair"], rows[-1]["arm"]), (rows[0]["pair"], rows[0]["arm"]))
        self.assertNotEqual(rows[-1]["id"], rows[0]["id"])

    def test_blind_packet_seals_heading_ranges_validity_and_history_in_stable_opaque_order(self):
        receipt = self.prepare_known_review()
        self.assertEqual(len(receipt["history"]["groups"]), 1)
        first = ("RAW HOST PREAMBLE\n### F1 [major] {workspace}/abi.h\nProblem: Missing result for model-a on "
                 "candidate arm.\nEvidence: An incorrect width. See model-a-claim.txt in /home/host/.codex/private-session.\n")
        second = "### F2 [minor] ABI offset\nProblem: Incorrect offset.\n"
        tail = "Questions: RAW HOST TAIL\nVerdict: revise\n"
        self.config["settings"]["actions"] = [
            dict(reports=dict(spec=first + second + tail, standards=first + tail)), {},
            dict(reports={"spec": "### F1 [major] truncated report"}), dict(reports={"spec": " "}),
            dict(reports={"spec": "### F1 [major] one\n### F1 [minor] duplicate\nVerdict: revise\n"})]
        self.write_config()
        self.replay()
        blind = self.out / "blind"
        files = {p.relative_to(blind): p.read_bytes() for p in blind.rglob("*") if p.is_file()}
        self.assertIn(Path("packet.json"), files)
        packet = json.loads(files[Path("packet.json")])
        template = json.loads(files[Path("judgments-template.json")])
        self.assertEqual(template["packet_sha256"], digest(files[Path("packet.json")]))
        self.assertEqual([r["id"] for r in packet["attempts"]], sorted(r["id"] for r in packet["attempts"]))
        by_id = {r["id"]: r for r in packet["attempts"]}
        def exported(ref):
            data = files[Path(ref["path"])]
            self.assertEqual(digest(data), ref["sha256"])
            return data.decode()
        history, = packet["history"]["groups"]
        self.assertEqual(history["disposition"], "accepted")
        self.assertEqual(len(set(history["sources"])), 2)
        for ref in history["evidence"]:
            self.assertIn("Missing value", exported(ref))
        rows = self.journal()["attempts"]
        claims = by_id[rows[0]["id"]]["claims"]
        self.assertEqual([c["id"] for c in claims], sorted(c["id"] for c in claims))
        self.assertEqual(sorted(c["severity"] for c in claims), ["major", "major", "minor"])
        for claim in claims:
            text = exported(claim["evidence"])
            if claim["severity"] == "minor":
                self.assertIn("Incorrect offset", text)
                self.assertNotIn("incorrect width", text)
            else:
                self.assertIn("An incorrect width", text)
                self.assertNotIn("offset", text)
        self.assertEqual([by_id[a["id"]]["claims"] for a in (rows[1], rows[5])], [[], []])
        self.assertEqual([a["roles"]["spec"]["report_valid"] for a in rows], [True, True, False, False, False, True])
        self.assertEqual([c["first_line"] for c in rows[0]["roles"]["spec"]["claims"]], [2, 5])
        blinded = b"".join(files.values())
        for secret in ("model-a", "candidate", "recorded", "RAW HOST", str(self.root), "private-defect", "spec:F1",
                       "private-session",
                       "wall_seconds", "config_digest", "cached_input"):
            self.assertNotIn(secret.encode(), blinded)
        # Fixed IDs and evidence must determine all public bytes, independent of the private journal's order.
        journal = self.journal()
        journal["attempts"].reverse()
        (self.out / "private/run.json").write_text(json.dumps(journal))
        self.replay()
        self.assertEqual(files, {p.relative_to(blind): p.read_bytes() for p in blind.rglob("*") if p.is_file()})

    def test_git_dot_scope_uses_nested_project_instructions_and_preserves_literal_diff(self):
        self.different_suite(tool="# candidate tool\n")
        tool = "tools/canon.py"
        before = {"sub/AGENTS.md": "- Tool: `python3 tools/canon.py` from the repo root.\n",
                  "sub/abi.h": "old", tool: ("100755", "# tool\n")}
        base = self.pin(self.store, self.tree(self.store, before))
        after = dict(before, **{"sub/abi.h": "new"})
        self.review("code-review", after, baseline=base,
                    prompts={"spec": f"Target: `git diff -U8 {base} -- .`\nUntracked files: none"})
        self.prepare()
        self.replay()
        calls = self.calls()
        self.assertEqual(len(calls), 3)
        self.assertTrue(all(c["suite"] == "Old suite." for c in calls))
        self.assertTrue(all(c["task"]["input"]["paths"] == ["."] and
                            c["task"]["input"]["diff_args"] == ["-U8"] for c in calls))

    def test_measured_role_identity_evidence_and_stopping_boundary_control_comparability(self):
        self.gate()
        self.prepare()
        boundary = dict(reason="confirmation dispatched", evidence=None, wall_seconds=2.5,
                        tokens={"parent": dict(input=6, cached_input=2, output=3, reasoning_output=None)})
        actions = [dict(roles={"same-model": {"model": "unexpected"}}),
                   dict(roles={"parent": {"effort": "low"}}),
                   dict(envelope={"attempt": "wrong-attempt"}), dict(corrupt="same-model"),
                   dict(escape="same-model"), dict(envelope={"boundary_violation": boundary}),
                   dict(roles={"parent": {"loaded": [dict(path=".agents/skills/canon/SKILL.md", blob="a"*40)]}}),
                   dict(loaded_path="other/SKILL.md"), dict(envelope={"config_digest": "f"*64}),
                   dict(remove=["parent"]), dict(envelope={"host": "other-host"}), dict(change_loaded=True),
                   dict(envelope={"outcome": "stopped", "reason": "budget reached"}, remove=["same-model"]),
                   dict(exit=1, envelope={"outcome": "failed", "reason": "host stopped with partial evidence"})]
        self.config["settings"]["actions"] = actions
        self.write_config()
        self.replay("--repetitions", 7)
        rows = self.journal()["attempts"]
        self.assertEqual([a["outcome"] for a in rows],
                         ["incompatible", "incompatible", "failed", "failed", "failed", "incompatible",
                          "incompatible", "incompatible", "incompatible", "failed", "incompatible", "incompatible",
                          "stopped", "failed"])
        self.assertEqual(rows[5]["boundary_violation"], boundary)
        self.assertEqual(rows[-2]["roles"]["parent"]["tokens"]["cached_input"], 3)
        self.assertTrue(rows[-1]["roles"]["same-model"]["report_valid"])
        self.assertTrue(all(a["reason"] for a in rows))
        self.assertTrue(all(a["wall_seconds"] >= 0 for a in rows))

    def test_two_controllers_reattach_after_cli_termination_and_pin_runner_and_config_on_resume(self):
        self.gate()
        self.prepare()
        self.hold_peer()
        first = self.controller()
        live, = self.await_calls(1)
        second = self.controller()
        first.kill()
        first.wait(timeout=5)
        self.hold.unlink()
        _, error = second.communicate(timeout=30)
        self.assertEqual(second.returncode, 0, error)
        self.assertEqual(len(self.calls()), 6)
        rows = self.journal()["attempts"]
        self.assertEqual({r["id"] for r in rows}, {r["attempt"] for r in self.calls()})
        self.assertEqual(rows[0]["id"], live["attempt"])
        self.assertTrue(all(r["outcome"] == "completed" for r in rows))
        self.replay()
        self.assertEqual(len(self.calls()), 6)
        runner_bytes = self.runner.read_bytes()
        self.runner.write_bytes(runner_bytes + b"\n")
        self.replay(error="runner")
        self.runner.write_bytes(runner_bytes)
        original = self.runner
        self.runner = self.root / "different-path"
        shutil.copy2(original, self.runner)
        self.replay(error="runner")
        self.runner = original
        self.config_path.write_text(self.config_path.read_text() + "\n")
        self.replay(error="config")
        self.assertEqual(len(self.calls()), 6)

    def test_project_prescribed_tool_and_tracked_installs_must_resolve_to_the_assigned_suite(self):
        self.different_suite(tool="# changed tool\n")
        tool = "skills/governance/canon/scripts/canon.py"
        guide = ("Agents and reviewers run the working tree's canon.py as `python3 " + tool + "`.\n"
                 "- Tool: `scripts/canon.py` of the `canon` skill installed in this project, "
                 "`.agents/skills/canon/scripts/canon.py` as installed.\n")
        self.gate({"AGENTS.md": guide, tool: ("100755", "# tool\n"),
                   ".agents/skills/canon/SKILL.md": "Old suite.\n",
                   ".claude/skills/canon": ("120000", "../../.agents/skills/canon")})
        self.prepare()
        self.replay()
        self.assertEqual([r["suite"] for r in self.calls()], ["Old suite."] * 3)
        self.assertTrue(all(r["untracked"] == [] and r["claude_link"] for r in self.calls()))
        states = self.journal()["attempts"]
        self.assertEqual([(a["outcome"], a["arm"]) for a in states if a["arm"] == "candidate"],
                         [("incompatible", "candidate")] * 3)
        self.events = self.events[:1]
        self.gate({"AGENTS.md": guide, tool: ("100755", "# tool\n")})
        second = self.root / "self-review"
        self.prepare(out=second)
        self.replay(out=second)
        self.assertTrue(all("prescribed tool" in a["reason"] for a in self.journal(second)["attempts"]
                            if a["arm"] == "candidate"))
        self.assertEqual(len(self.calls()), 6)

    def test_preflight_rejects_short_runs_ungranted_input_or_destination_and_historical_model_conflicts(self):
        self.gate()
        self.prepare()
        self.replay("--repetitions", 2, error="three")
        self.config["read_paths"] = [DESIGN]
        self.write_config()
        self.replay(error="read_paths")
        self.config["read_paths"] = ["."]
        self.config["settings"]["role_destinations"] = {"same-model": "another-provider"}
        self.write_config()
        self.replay(error="destination")
        self.config["settings"].pop("role_destinations")
        self.config["roles"]["same-model"]["model"] = "other-model"
        self.write_config()
        self.replay(error="model")
        self.assertEqual(self.calls(), [])
        self.config["roles"]["same-model"]["model"] = "model-a"
        self.write_config()
        for name, model in (("missing", "unknown"), ("manual", "manual:model-a")):
            people = [dict(reviewer("same-model", "id"), model=model)]
            # Preserve the same input but freeze the actual historical reviewer identity.
            self.events = self.events[:1]
            self.gate(people=people)
            out = self.root / name
            self.prepare(out=out)
            self.replay(out=out, error="model")
        self.assertEqual(self.calls(), [])

    def test_three_alternating_pairs_use_the_same_neutral_task_and_fresh_workspaces(self):
        self.different_suite()
        self.code_review()
        fixtures = self.root / "fixtures"
        fixtures.mkdir()
        (fixtures / "dependency").write_text("local input")
        (fixtures / "dependency").chmod(0o755)
        receipt = self.prepare("--fixtures", fixtures)
        self.replay()
        rows = self.calls()
        self.assertEqual([r["suite"] for r in rows], ["Old suite.", "New suite.", "New suite.", "Old suite.",
                                                       "Old suite.", "New suite."])
        self.assertEqual(len({r["workspace"] for r in rows}), 6)
        self.assertEqual(len({r["attempt"] for r in rows}), 6)
        for row in rows:
            self.assertEqual(row["task"], receipt["task"])
            self.assertEqual(row["task"]["delivery"], "Preserve the ABI.")
            self.assertEqual(row["stop_after"], "first_round_reports")
            self.assertEqual(set(row["roles"]), {"parent", "spec", "standards"})
            self.assertEqual(row["roles"]["spec"], {"model": "model-a", "effort": "medium"})
            self.assertEqual(row["head"], row["task"]["input"]["target"])
            self.assertEqual(row["untracked"], [])
            self.assertTrue(row["fixture_executable"] and row["claude_link"])
        self.assertEqual([a["outcome"] for a in self.journal()["attempts"]], ["completed"] * 6)
