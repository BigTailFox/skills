"""Exercise the offline report through its public command, using redacted host records."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/trace_report.py"
TRACE = Path(".canon/canon/trace")
UNIT = "20260101T000005Z-abcdef"
GATE = "20260101T000025Z-012345"
PRIOR = "20251231T235000Z-123456"
CONV = "00000000-0000-4000-8000-000000000001"
SECOND = "00000000-0000-4000-8000-000000000002"


def write_lines(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join((row if isinstance(row, str) else json.dumps(row)) + "\n" for row in rows))


def start(unit=UNIT, kind="implement", at="2026-01-01T00:00:05Z", **fields):
    return dict({"v": 1, "type": "start", "kind": kind, "at": at, "id": unit, "host": "other",
                 "docs": [], "parent": None, "tier": "L1", "manifest": None}, **fields)


def end(unit=UNIT, kind="implement", at="2026-01-01T00:01:05Z", outcome="delivered", **fields):
    return dict(v=1, type="end", kind=kind, at=at, id=unit, outcome=outcome, **fields)


def contents(root):
    return {str(p.relative_to(root)): (hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None)
            for p in root.rglob("*")}


class ReportFixture(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.project = self.root / "project"
        self.cursor = self.root / "cursor"
        self.codex = self.root / "codex"
        self.log = self.project / TRACE / "events.jsonl"

    def cli(self, *args, text=False):
        before = contents(self.root)
        proc = subprocess.run([sys.executable, str(SCRIPT), "--cursor-home", str(self.cursor),
                               "--codex-home", str(self.codex), *map(str, args), *([] if text else ["--json"])],
                              cwd=self.project, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn("PRIVATE", proc.stdout + proc.stderr)
        self.assertEqual(before, contents(self.root))
        return proc.stdout if text else json.loads(proc.stdout)


class TraceReport(ReportFixture):
    def test_population_keeps_projects_stores_lines_and_inclusive_date(self):
        write_lines(self.log, [
            start(PRIOR, at="2025-12-31T23:50:00Z"), start(), "PRIVATE damaged event",
            start(GATE, "gate", "2026-01-01T00:00:25Z", parent=UNIT),
            end(at="2026-01-01T08:01:05+08:00"), end(PRIOR, "retro"),
        ])
        other = self.root / "elsewhere" / "project"
        write_lines(other / TRACE / "events.jsonl", [start(), end(outcome="handoff")])
        report = self.cli("--project", self.project, "--project", other, "--project", self.project, "--since", "2026-01-01")
        self.assertIn("population", report)
        p = report["population"]
        self.assertEqual(p["projects"], [str(self.project), str(other)])
        self.assertEqual(len(p["stores"]), 2)
        self.assertEqual([(x["reason"], x["location"].split("#")[-1]) for x in p["skipped"]],
                         [("malformed", "L3")])
        self.assertEqual(p["orphans"][0]["location"], str(self.log) + "#L6")
        self.assertIn("untraced work is unknown", p["caveat"].lower())
        self.assertEqual(len(report["cases"]), 3)
        self.assertEqual(len({c["case"] for c in report["cases"]}), 3)
        by_unit = {c["unit"]: c for c in report["cases"] if c["project"] == str(self.project)}
        self.assertEqual(by_unit[UNIT]["wall_seconds"], 60)
        self.assertEqual(by_unit[UNIT]["start_location"], str(self.log) + "#L2")
        self.assertEqual(by_unit[UNIT]["end_location"], str(self.log) + "#L5")
        self.assertEqual(p["open"], [by_unit[GATE]["case"]])
        self.assertIn(by_unit[GATE]["case"], p["incomplete"])
        rendered = self.cli("--since", "2026-01-01", text=True)
        self.assertIn("untraced work is unknown", rendered.lower())
        self.assertIn(str(self.log) + "#L3", rendered)
        self.assertIn(GATE, rendered)

    def test_cursor_export_precedes_verified_database_and_wait_is_wall_time(self):
        import sqlite3
        native = ".agents/skills/canon/scripts/canon.py"
        skill = ".agents/skills/canon-blind-review"
        command = f"python3 {native} trace start gate D001 --tier L1 --skill {skill}"
        finish = f"python3 {native} trace end {UNIT} delivered"
        s = start(kind="gate", host="cursor", conversation=CONV, docs=["D001@r1"], skill=str(self.project / skill))
        write_lines(self.log, [s, end(kind="gate")])
        export = self.cursor / "projects/redacted/agent-transcripts" / CONV / (CONV + ".jsonl")

        def shell(cmd):
            return {"role": "assistant", "message": {"content": [
                {"type": "tool_use", "name": "Shell", "input": {"command": cmd, "working_directory": str(self.project)}}]}}

        user = {"role": "user", "message": {"content": [{"type": "text", "text": "<timestamp>2026-01-01T00:01Z</timestamp>PRIVATE"}]}}
        write_lines(export, [shell(command), user, shell(finish)])
        database = self.root / "state.vscdb"
        with sqlite3.connect(database) as db:
            db.execute("CREATE TABLE cursorDiskKV (key TEXT PRIMARY KEY, value BLOB)")

        def bubble(key, conversation=CONV, rejected=False, output=None):
            words = command.split()
            params = {"command": command, "cwd": str(self.project), "parsingResult": {"executableCommands": [
                {"name": "python3", "args": [{"type": "word", "value": w} for w in words[1:]], "fullText": command}]}}
            raw = {"command": command, "workingDirectory": str(self.project), "conversationId": conversation}
            bid = SECOND + "/t:toolu_" + key
            host = {"type": 2, "bubbleId": bid, "createdAt": "2026-01-01T08:00:04+08:00",
                    "startedAtMs": 1767225604000, "completedAtMs": 1767225606000, "text": "PRIVATE",
                    "toolFormerData": {"name": "run_terminal_command_v2", "toolCallId": "toolu_" + key,
                                       "status": "completed", "params": json.dumps(params), "rawArgs": json.dumps(raw),
                                       "result": json.dumps({"rejected": rejected, "output": output or "trace " + UNIT})}}
            address = "bubbleId:" + conversation + ":" + bid
            with sqlite3.connect(database) as db:
                db.execute("INSERT OR REPLACE INTO cursorDiskKV VALUES (?,?)", (address, json.dumps(host)))
            return address

        def row(*args):
            return self.cli(*args)["cases"][0]

        c = row()
        self.assertIn("host_start", c)
        self.assertEqual((c["host_start"]["source"], c["host_start"]["location"]), ("export", str(export) + "#L1"))
        self.assertEqual((c["wall_seconds"], c["parent_cost"]["tokens"]), (60, "unknown"))
        key = bubble("First")
        with_db = ("--cursor-state-db", database)
        self.assertEqual(row(*with_db)["host_start"]["source"], "export")
        write_lines(export, [user, shell(finish)])
        self.assertEqual(row()["host_start"]["source"], "unknown")
        c = row(*with_db)
        self.assertEqual((c["host_start"]["source"], c["host_start"]["location"]), ("cursor-db", str(database) + "#" + key))
        self.assertEqual(c["host_end"]["location"], str(export) + "#L2")
        bubble("First", output="PRIVATE trace " + UNIT)
        self.assertEqual(row(*with_db)["host_start"]["source"], "unknown")
        bubble("First", rejected=True)
        bubble("Foreign", conversation=SECOND)
        self.assertEqual(row(*with_db)["host_start"]["source"], "unknown")
        bubble("First")
        duplicate = bubble("Duplicate")
        self.assertEqual(row(*with_db)["host_start"]["source"], "unknown")
        # Keep a writer open: the latest committed rows exist only in the WAL.
        db = sqlite3.connect(database)
        self.addCleanup(db.close)
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("DELETE FROM cursorDiskKV WHERE key=?", (duplicate,))
        db.commit()
        self.assertEqual(row(*with_db)["host_start"]["source"], "cursor-db")

    @staticmethod
    def native(second, kind, **p):
        return {"timestamp": f"2026-01-01T00:{second // 60:02}:{second % 60:02}.100Z", "type": kind, "payload": p}

    def rollout(self, uid, rows, home=None, parent=None, key=None, archived=False):
        path = (home or self.codex) / ("archived_sessions" if archived else "sessions/day") / f"rollout-fixture-{uid}.jsonl"
        source = {"subagent": {"thread_spawn": {"parent_thread_id": parent, "agent_path": "/root/" + key}}} if parent else "cli"
        write_lines(path, [self.native(0, "session_meta", id=uid, source=source, cwd=str(self.project)), *rows])
        return path

    def counters(self, t, n, **extra):
        total = dict(input_tokens=n * 3, cached_input_tokens=n, output_tokens=n * 2,
                     reasoning_output_tokens=n, total_tokens=n * 5, **extra)
        return self.native(t, "event_msg", type="token_count", info={"total_token_usage": total})

    def boundary(self, t, tail, receipt, call="a", compound=False):
        command = "python3 .agents/skills/canon/scripts/canon.py trace " + tail
        if compound:
            return [self.native(t, "response_item", type="custom_tool_call", namespace="functions", name="exec",
                                call_id=call, input='const r=await tools.exec_command({cmd:' + json.dumps(command) + '});text(r)'),
                    self.native(t + 1, "response_item", type="custom_tool_call_output", call_id=call,
                                output=[{"type": "text", "text": json.dumps(["shell", {"exit_code": 0, "output": receipt}])}])]
        return [self.native(t, "response_item", type="function_call", namespace="functions", name="exec_command",
                            call_id=call, arguments=json.dumps({"cmd": command})),
                self.native(t + 1, "response_item", type="function_call_output", call_id=call,
                            output="Process exited with code 0\nOutput:\n" + receipt)]

    def test_codex_receipt_lookup_and_independent_cumulative_components(self):
        write_lines(self.log, [start(host="codex", conversation=None), end()])
        a = self.boundary(4, "start implement --tier L1", "trace " + UNIT, compound=True)
        # A code-mode shell writes a heredoc first; only the invocation after its terminator executes.
        a[0]["payload"]["input"] = a[0]["payload"]["input"].replace(
            "python3 .agents", "python3 - <<'PYEND'\\npass\\nPYEND\\npython3 .agents")
        z = self.boundary(64, "end " + UNIT + " delivered", "trace " + UNIT + " ended", "z")
        ctx = self.native(1, "turn_context", model="example", effort="high")
        second_home = self.root / "other-profile"
        path = self.rollout(CONV, [ctx, self.counters(3, 4), *a, self.counters(59, 8), *z], home=second_home, archived=True)
        self.rollout(SECOND, self.boundary(4, "start implement --tier L1", "PRIVATE trace " + UNIT))
        opts = ("--codex-home", second_home)
        c = self.cli(*opts)["cases"][0]
        self.assertEqual(c["host_start"]["source"], "export")
        self.assertEqual(c["conversation"], CONV)
        self.assertEqual(c["host_start"]["location"], str(path) + "#L4")
        self.assertEqual(c["host_start"]["receipt_location"], str(path) + "#L5")
        self.assertEqual((c["model"], c["effort"]), ("example", "high"))
        self.assertEqual(c["parent_cost"]["tokens"],
                         {"input_tokens": 12, "cached_input_tokens": 4, "output_tokens": 8, "reasoning_output_tokens": 4,
                          "total_tokens": 20})
        self.assertEqual(c["parent_cost"]["locations"], [str(path) + "#L3", str(path) + "#L6"])
        self.rollout(CONV, [ctx, self.counters(3, 4), *a, self.counters(59, 8, extra_tokens=5), *z], home=second_home, archived=True)
        self.assertEqual(self.cli(*opts)["cases"][0]["parent_cost"]["tokens"], "unknown")
        self.rollout(CONV, [ctx, self.counters(3, 4), *a, self.counters(24, 1), self.counters(59, 8), *z],
                     home=second_home, archived=True)
        self.assertEqual(self.cli(*opts)["cases"][0]["parent_cost"]["tokens"], "unknown")

    def dispatch(self, t, verb, target, call, receipt):
        args = {"task_name" if verb == "spawn_agent" else "target": target, "message": "PRIVATE worker brief"}
        return [self.native(t, "response_item", type="function_call", namespace="collaboration", name=verb,
                            arguments=json.dumps(args), call_id=call),
                self.native(t, "response_item", type="function_call_output", call_id=call, output=receipt)]

    def worker_turn(self, first, last, lo, hi, status="done"):
        return [self.counters(first, lo), self.native(first + 1, "event_msg", type="task_started"),
                self.counters(last - 2, hi),
                self.native(last - 1, "response_item", type="message", role="assistant", phase="final_answer",
                            content=[{"type": "output_text", "text": "Status: " + status}]),
                self.native(last, "event_msg", type="task_complete", last_agent_message="Status: " + status)]

    def test_review_counts_launches_in_span_and_resumed_child_costs_separately(self):
        write_lines(self.log, [start(kind="gate", host="codex", conversation=CONV), end(kind="gate")])
        first = self.boundary(4, "start gate --tier L1", "trace " + UNIT)
        last = self.boundary(64, "end " + UNIT + " delivered", "trace " + UNIT + " ended", "end")
        outside = "00000000-0000-4000-8000-000000000003"
        rows = [self.counters(1, 1), *first,
                *self.dispatch(10, "spawn_agent", "reviewer", "one", json.dumps({"agent_id": SECOND})),
                *self.dispatch(30, "followup_task", "/root/reviewer", "two", "Follow-up task sent to /root/reviewer."),
                self.counters(61, 20), *last,
                *self.dispatch(70, "spawn_agent", "other", "three", json.dumps({"agent_id": outside}))]
        parent = self.rollout(CONV, rows)
        child = self.rollout(SECOND, [*self.worker_turn(11, 20, 2, 6), *self.worker_turn(31, 40, 6, 13)],
                             parent=CONV, key="reviewer")
        self.rollout(outside, self.worker_turn(71, 80, 1, 5), parent=CONV, key="other")
        # The host also runs internal subagents with a parent_thread_id; they are not user-launched workers.
        native_service = "00000000-0000-4000-8000-000000000007"
        service = self.rollout(native_service, [])
        write_lines(service, [self.native(15, "session_meta", id=native_service, parent_thread_id=CONV,
                                          source={"subagent": {"other": "guardian"}})])
        report = self.cli()
        c = report["cases"][0]
        self.assertEqual(c["fresh_subagents"], 1)
        self.assertEqual([a["mode"] for a in c["worker_attempts"]], ["launch", "resume"])
        self.assertEqual([a["session"] for a in c["worker_attempts"]], [SECOND, SECOND])
        self.assertEqual(c["parent_cost"]["tokens"]["total_tokens"], 95)
        self.assertEqual([a["child_cost"]["tokens"]["total_tokens"] for a in c["worker_attempts"]], [20, 35])
        self.assertEqual(c["worker_attempts"][0]["dispatch_location"], str(parent) + "#L5")
        self.assertEqual(c["worker_attempts"][0]["terminal_location"], str(child) + "#L6")
        self.assertEqual(report["questions"]["6"]["groups"][0]["wall_seconds"]["known"], 1)
        group = report["questions"]["6"]["groups"][0]
        self.assertIn(c["case"], group["cases"])
        self.assertIn("worker_intervals", group)
        self.assertEqual(group["worker_intervals"]["contained"]["numerator"], 2)
        self.assertEqual(group["child_costs"][0]["tokens"]["total_tokens"]["total"], 55)
        human = self.cli(text=True)
        self.assertIn("Wall time, subagents and tokens", human)
        self.assertIn("few units", human)
        self.assertIn(str(child) + "#L6", human)

    def test_reviewer_session_cost_joins_agent_paths_and_command_run_ids_once(self):
        command_id = "00000000-0000-4000-8000-000000000003"
        people = [{"role": "cross-family", "model": "model-a", "id": "/root/reviewer"},
                  {"role": "cross-family", "key": "cross-family-2", "model": "model-a", "id": SECOND},
                  {"role": "same-model", "model": "model-b", "id": command_id},
                  {"role": "same-model", "key": "same-model-2", "model": "model-b", "id": None}]
        archive = self.log.parent / UNIT
        archive.mkdir(parents=True)
        for r in people:
            stem = r.get("key", r["role"])
            (archive / (stem + ".md")).write_text("No findings.")
            (archive / (stem + "-id.txt")).write_text(r["id"] or "")
        write_lines(self.log, [start(kind="gate", host="codex", conversation=CONV),
                               end(kind="gate", archive="ok", dispositions=dict(reviewers=people, findings=[], new_blockers=0))])
        self.rollout(CONV, [*self.boundary(4, "start gate", "trace " + UNIT),
                            *self.dispatch(10, "spawn_agent", "reviewer", "one", json.dumps({"agent_id": SECOND})),
                            *self.boundary(64, "end " + UNIT + " delivered", "trace " + UNIT + " ended", "end")])
        child = self.rollout(SECOND, self.worker_turn(11, 20, 2, 6), parent=CONV, key="reviewer")
        command = self.rollout(command_id, self.worker_turn(30, 45, 1, 5))
        output = self.cli()
        costs = output["cases"][0]["review"]["session_costs"]
        self.assertEqual(len(costs), 3)
        repeated = next(r for r in costs if r["session"] == SECOND)
        self.assertEqual(repeated["keys"], ["cross-family", "cross-family-2"])
        self.assertEqual(repeated["tokens"]["total_tokens"], 20)
        self.assertIn(str(child), str(repeated["locations"]))
        external = next(r for r in costs if r["session"] == command_id)
        self.assertEqual(external["tokens"]["total_tokens"], 20)
        self.assertIn(str(command), str(external["locations"]))
        group, = output["questions"]["1"]["groups"]
        self.assertEqual(group["reviewer_cost"]["tokens"]["total_tokens"]["total"], 40)
        self.assertEqual(group["reviewer_cost"]["wall_seconds"]["unknown"], 1)

    def git(self, *args, at=None):
        env = dict(os.environ, GIT_AUTHOR_NAME="Fixture", GIT_AUTHOR_EMAIL="fixture@example.invalid",
                   GIT_COMMITTER_NAME="Fixture", GIT_COMMITTER_EMAIL="fixture@example.invalid")
        if at:
            env.update(GIT_AUTHOR_DATE=at, GIT_COMMITTER_DATE=at)
        r = subprocess.run(["git", *args], cwd=self.project, env=env, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout.strip()

    def plan(self, status="todo", risk=True, revision=1, pause=False):
        path = self.project / "docs/plans/P001-example.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        body = (f"---\nrevision: {revision}\n---\n\n# P001: Example\n\n## Slices\n\n### S1: First\n\n"
                f"Status: {status}\n\n" + ("Risk: PRIVATE risk\n\n" if risk else "") + "## Log\n\n" +
                ("- S1 paused. Stashed as P001 S1 PRIVATE.\n" if pause else "Started.\n"))
        path.write_text(body)
        return path

    def base_plan(self):
        self.project.mkdir()
        self.git("init", "-q")
        self.assertEqual(self.git("rev-parse", "--show-toplevel"), str(self.project))
        self.plan()
        self.git("add", "docs")
        self.git("commit", "-qm", "start", at="2025-12-31T23:00:00Z")
        return self.git("rev-parse", "HEAD")

    def test_earliest_git_boundary_excludes_late_worker_and_deduplicates_a_resumed_slice(self):
        base = self.base_plan()
        self.plan("done")
        self.git("commit", "-qam", "complete the slice", at="2026-01-01T00:00:50Z")
        final = self.git("rev-parse", "HEAD")
        implement2 = "20260101T000025Z-111111"
        resumed = "20260101T000030Z-222222"
        lost = "00000000-0000-4000-8000-000000000003"
        parent = start(PRIOR, at="2025-12-31T23:59:59Z", host="codex", conversation=CONV, head=base)
        def slice_open(uid, when, parent):
            return start(uid, "slice", when, host="codex", conversation=CONV, docs=["P001@r1"],
                         slice="S1", parent=parent, head=base)
        write_lines(self.log, [parent, slice_open(UNIT, "2026-01-01T00:00:05Z", PRIOR),
                               end(PRIOR, at="2026-01-01T00:00:23Z", outcome="handoff", head=base),
                               start(implement2, at="2026-01-01T00:00:25Z", host="codex", conversation=CONV, head=base),
                               slice_open(resumed, "2026-01-01T00:00:30Z", implement2),
                               end(implement2, at="2026-01-01T00:01:05Z", head=final)])
        child3 = "00000000-0000-4000-8000-000000000004"
        parent_path = self.rollout(CONV, [
            *self.boundary(4, "start slice P001 --slice S1 --parent " + PRIOR, "trace " + UNIT),
            *self.dispatch(8, "spawn_agent", "p001_s1", "one", json.dumps({"agent_id": SECOND})),
            *self.boundary(29, "start slice P001 --slice S1 --parent " + implement2, "trace " + resumed, "b"),
            *self.dispatch(32, "followup_task", "/root/p001_s1", "two", "Follow-up task sent to /root/p001_s1."),
            *self.dispatch(39, "spawn_agent", "p001_s1_replacement", "three", json.dumps({"agent_id": child3})),
            *self.dispatch(45, "spawn_agent", "p001_s1_other", "four", json.dumps({"agent_id": lost}))])
        self.rollout(SECOND, [*self.worker_turn(9, 16, 1, 2, "blocked"),
                              self.native(33, "event_msg", type="task_started"),
                              self.native(37, "event_msg", type="turn_aborted")], parent=CONV, key="p001_s1")
        self.rollout(child3, self.worker_turn(40, 54, 1, 5), parent=CONV, key="p001_s1_replacement")
        stored = self.project / ".canon/canon-implement/P001/S1-id.txt"
        stored.parent.mkdir(parents=True)
        stored.write_text(child3)
        report = self.cli()
        by_id = {c["unit"]: c for c in report["cases"]}
        first, second = by_id[UNIT], by_id[resumed]
        self.assertEqual((first["wall_seconds"], first["upper_bound_seconds"]), ("unknown", 18))
        self.assertEqual((second["commit"], second["wall_seconds"]), (final, 20))
        self.assertEqual([a["containment"] for a in second["worker_attempts"]], ["contained", "outside", "unknown"])
        self.assertEqual(second["worker_attempts"][0]["terminal"], "stopped")
        self.assertEqual(second["worker_attempts"][1]["child_cost"]["wall_seconds"], "unknown")
        self.assertEqual(second["worker_attempts"][1]["child_cost"]["tokens"], "unknown")
        self.assertEqual(second["worker_attempts"][1]["stored_dispatch_location"], str(stored))
        self.assertTrue(second["worker_attempts"][2]["dispatch_location"].startswith(str(parent_path)))
        self.assertIn("4", report["questions"])
        q = report["questions"]["4"]
        self.assertEqual((q["denominator"], len(q["slices"])), (1, 1))
        self.assertEqual(q["slices"][0]["risk"], "present")
        self.assertEqual(set(q["slices"][0]["cases"]), {first["case"], second["case"]})
        self.assertEqual(q["slices"][0]["stop"], "confirmed")
        self.assertIn("host stopped", q["slices"][0]["reasons"])
        self.assertEqual(q["groups"][0]["stopped"]["numerator"], 1)

    def test_cursor_foreground_worker_links_child_and_commit_before_next_start(self):
        base = self.base_plan()
        self.plan("done")
        self.git("commit", "-qam", "complete the slice", at="2026-01-01T00:00:50Z")
        final = self.git("rev-parse", "HEAD")
        write_lines(self.log, [
            start(PRIOR, at="2025-12-31T23:59:59Z", host="cursor", conversation=CONV, head=base),
            start(kind="slice", host="cursor", conversation=CONV, docs=["P001@r1"], slice="S1", parent=PRIOR, head=base),
            end(PRIOR, at="2026-01-01T00:01:05Z", head=final)])
        parent = self.cursor / "projects/redacted/agent-transcripts" / CONV / (CONV + ".jsonl")
        child = parent.parent / "subagents" / (SECOND + ".jsonl")

        def record(role, *content):
            return {"role": role, "message": {"content": list(content)}}
        def shell(cmd):
            return record("assistant", {"type": "tool_use", "name": "Shell", "input": {"command": cmd}})
        def task(brief, background=False):
            opts = {"description": "P001 S1", "prompt": brief, "run_in_background": background}
            return record("assistant", {"type": "tool_use", "name": "CallDynamicTool",
                                         "input": {"toolName": "Task", "arguments": json.dumps(opts)}})
        def text(value):
            return {"type": "text", "text": value}
        native = "python3 .agents/skills/canon/scripts/canon.py trace "
        write_lines(parent, [shell(native + "start implement --tier L1"), shell(native + "start slice P001 --slice S1 --parent " + PRIOR),
                             task("PRIVATE brief"), shell("git commit -q -F - <<'MSG'\ncomplete the slice\n\nPRIVATE body\nMSG"), shell(native + "end " + PRIOR + " delivered")])
        write_lines(child, [record("user", text("Envelope: PRIVATE brief")), record("assistant", text("Status: done")),
                            {"type": "turn_ended", "status": "success"}])
        def read():
            return next(c for c in self.cli()["cases"] if c["unit"] == UNIT)
        c = read()
        self.assertEqual(c["fresh_subagents"], 1)
        self.assertEqual(c["host_end"]["location"], str(parent) + "#L4")
        a, = c["worker_attempts"]
        self.assertEqual((a["session"], a["containment"], a["report_status"]), (SECOND, "contained", "done"))
        self.assertEqual(a["terminal_location"], str(child) + "#L3")
        self.assertEqual(a["child_cost"]["wall_seconds"], "unknown")
        write_lines(child, [record("user", text("Envelope: PRIVATE brief")), record("assistant", text("Status: done"))])
        self.assertEqual(read()["worker_attempts"][0]["containment"], "unknown")

    def test_unknown_final_report_and_same_git_second_do_not_measure_a_worker(self):
        base = self.base_plan()
        self.plan("done")
        self.git("commit", "-qam", "complete the slice", at="2026-01-01T00:00:20Z")
        final = self.git("rev-parse", "HEAD")
        write_lines(self.log, [
            start(PRIOR, at="2025-12-31T23:59:59Z", host="codex", conversation=CONV, head=base),
            start(kind="slice", host="codex", conversation=CONV, docs=["P001@r1"], slice="S1", parent=PRIOR, head=base),
            end(PRIOR, at="2026-01-01T00:00:35Z", head=final)])
        self.rollout(CONV, [*self.boundary(4, "start slice P001 --slice S1 --parent " + PRIOR, "trace " + UNIT),
                            *self.dispatch(9, "spawn_agent", "p001_s1", "a2", json.dumps({"agent_id": SECOND}))])
        for last, contradictory in ((20, False), (18, True)):
            with self.subTest(last=last):
                rows = self.worker_turn(10, last, 1, 5)
                if contradictory:
                    rows[-1]["payload"]["last_agent_message"] = "Status: blocked"
                self.rollout(SECOND, rows, parent=CONV, key="p001_s1")
                report = self.cli()
                unit = next(c for c in report["cases"] if c["unit"] == UNIT)
                attempt, = unit["worker_attempts"]
                self.assertEqual((attempt["containment"], attempt["child_cost"]["tokens"]), ("unknown", "unknown"))
                self.assertEqual(report["questions"]["4"]["slices"][0]["stop"], "unknown")

    def test_pause_requires_matching_log_stash_and_the_same_plan_revision(self):
        base = self.base_plan()
        self.plan(status="paused", risk=False, pause=True)
        (self.project / "work.txt").write_text("PRIVATE pending work")
        self.git("add", "work.txt")
        self.git("stash", "push", "-qm", "P001 S1 PRIVATE", "--", "work.txt", at="2026-01-01T00:00:23Z")
        newrev = "20260101T000100Z-333333"
        write_lines(self.log, [start(PRIOR, at="2025-12-31T23:59:59Z", head=base),
                               start(kind="slice", docs=["P001@r1"], parent=PRIOR, slice="S1", head=base),
                               start(newrev, "slice", "2026-01-01T00:01:00Z", docs=["P001@r2"],
                                     parent=PRIOR, slice="S1", head=base)])
        q = self.cli()["questions"]["4"]
        self.assertEqual(q["denominator"], 2)
        rows = {s["plan"]: s for s in q["slices"]}
        self.assertEqual((rows["P001@r1"]["stop"], rows["P001@r1"]["outcome"]), ("confirmed", "paused"))
        self.assertEqual(rows["P001@r1"]["risk"], "present")
        self.assertTrue(any("docs/plans/P001-example.md#L" in s for s in rows["P001@r1"]["locations"]))
        self.assertEqual(rows["P001@r2"]["stop"], "unknown")

    def test_same_physical_main_store_and_distinct_fallback_stay_identifiable(self):
        self.base_plan()
        linked = self.project / ".worktrees/linked"
        self.git("worktree", "add", "-q", "--detach", str(linked))
        write_lines(self.log, [start(), end()])
        write_lines(linked / TRACE / "events.jsonl", [start(), end(outcome="blocked")])
        report = self.cli("--project", linked, "--project", self.project)
        cases = report["cases"]
        self.assertEqual(len({c["case"] for c in cases}), 2)
        self.assertEqual(sorted(c["outcome"] for c in cases), ["blocked", "delivered"])
        self.assertEqual(len(report["population"]["stores"]), 2)

    def test_unmatched_native_child_does_not_become_zero_subagents(self):
        write_lines(self.log, [start(kind="code-review", host="codex", conversation=CONV), end(kind="code-review")])
        self.rollout(CONV, [*self.boundary(4, "start code-review --tier L1", "trace " + UNIT),
                            *self.boundary(64, "end " + UNIT + " delivered", "trace " + UNIT + " ended", "end")])
        path = self.rollout(SECOND, self.worker_turn(11, 20, 1, 6), parent=CONV, key="reviewer")
        data = [json.loads(line) for line in path.read_text().splitlines()]
        data[0]["timestamp"] = self.native(10, "session_meta")["timestamp"]
        write_lines(path, data)
        c = self.cli()["cases"][0]
        self.assertEqual(c["fresh_subagents"], "unknown")
        a, = c["worker_attempts"]
        self.assertEqual((a["session"], a["containment"]), (SECOND, "unknown"))
        self.assertEqual((a["dispatch_location"], a["child_location"]), ("unknown", str(path) + "#L1"))

    def test_printing_a_command_and_id_is_not_an_executed_codex_boundary(self):
        write_lines(self.log, [start(host="codex", conversation=CONV), end()])
        a = self.boundary(4, "start implement --tier L1", "trace " + UNIT, compound=True)
        a[0]["payload"]["input"] = ('await tools.exec_command({cmd:"pwd"}); '
            'text("python3 .agents/skills/canon/scripts/canon.py trace start implement --tier L1"); text("trace ' + UNIT + '")')
        self.rollout(CONV, a)
        self.assertEqual(self.cli()["cases"][0]["host_start"]["source"], "unknown")
