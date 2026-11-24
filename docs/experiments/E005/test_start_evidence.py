"""Exercise the evidence checker with redacted host and SQLite fixtures."""

import csv
import hashlib
import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRATCH = HERE.parents[2] / ".canon/canon-implement/P009/S2"
UNIT = "20260101T000005Z-abcdef"
CONV = "00000000-0000-4000-8000-000000000001"
OTHER = "00000000-0000-4000-8000-000000000002"
BUBBLE = "10000000-0000-4000-8000-000000000001/t:toolu_Example"
SCRIPT = ".agents/skills/canon/scripts/canon.py"
SKILL = ".agents/skills/canon-blind-review"
BASE = "abcdef0" * 5 + "12345"
PARENT = "20251231T235959Z-012345"
COMMAND = f"python3 {SCRIPT} trace start gate D001 D002 --tier L2 --skill {SKILL} --model example --parent {PARENT} --base {BASE[:7]}"


def shell(command):
    return {"role": "assistant", "message": {"content": [
        {"type": "tool_use", "name": "Shell", "input": {"command": command}}]}}


def millis(value):
    return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp() * 1000)


def jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))


class StartEvidence(unittest.TestCase):
    def setUp(self):
        SCRATCH.mkdir(parents=True, exist_ok=True)
        self.root = Path(tempfile.mkdtemp(dir=SCRATCH))
        self.project = self.root / "project"
        self.home = self.root / "cursor"
        self.export = self.home / "projects/example/agent-transcripts" / CONV / (CONV + ".jsonl")
        self.end_command = f"python3 {SCRIPT} trace end {UNIT} delivered"
        jsonl(self.export, [shell("pwd"), shell(self.end_command)])
        self.event = dict(type="start", id=UNIT, at="2026-01-01T00:00:05Z", host="cursor",
                          conversation=CONV, kind="gate", docs=["D001@r2", "D002@r1"],
                          parent=PARENT, tier="L2", model="example", skill=str(self.project / SKILL),
                          base=BASE)
        self.end = dict(type="end", id=UNIT, kind="gate", outcome="delivered", at="2026-01-01T00:01:00Z")
        self.events = self.project / ".canon/canon/trace/events.jsonl"
        jsonl(self.events, [self.event, self.end])
        self.case = dict(project="Example", host="cursor", unit=UNIT, kind="gate", tier="L2",
                    parent=PARENT, outcome="delivered", start_event=1, end_event=2,
                    host_start="local-db", host_end=2)
        self.ledger = self.root / "ledger.tsv"
        self.write_case()
        self.db = self.root / "state.vscdb"
        with sqlite3.connect(self.db) as conn:
            conn.execute("CREATE TABLE cursorDiskKV(key TEXT PRIMARY KEY, value BLOB)")

    def write_case(self):
        with self.ledger.open("w", newline="") as stream:
            writer = csv.DictWriter(stream, self.case, delimiter="\t")
            writer.writeheader()
            writer.writerow(self.case)

    def record(self, command=COMMAND, conversation=CONV, bubble=BUBBLE, status="completed",
               trace_output=None, rejected=False, start="2026-01-01T00:00:03Z",
               finish="2026-01-01T00:00:09Z", name="run_terminal_command_v2"):
        words = command.split(" && ")[0].split()
        parsed = {"name": words[0], "args": [{"type": "word", "value": word} for word in words[1:]],
                  "fullText": " ".join(words)}
        params = dict(command=command, cwd=str(self.project),
                      parsingResult={"executableCommands": [parsed]})
        raw = dict(command=command, workingDirectory=str(self.project), conversationId=conversation)
        tool = dict(toolCallId=bubble.split("/t:")[1], name=name, status=status,
                    rawArgs=json.dumps(raw), params=json.dumps(params),
                    result=json.dumps(dict(rejected=rejected, output=(
                        "trace " + UNIT + "\n" if trace_output is None else trace_output))))
        record = dict(type=2, bubbleId=bubble, createdAt=start, startedAtMs=millis(start),
                      completedAtMs=millis(finish), text="PRIVATE CONVERSATION TEXT", toolFormerData=tool)
        key = f"bubbleId:{conversation}:{bubble}"
        with sqlite3.connect(self.db) as conn:
            conn.execute("INSERT OR REPLACE INTO cursorDiskKV VALUES (?,?)", (key, json.dumps(record)))
        return key

    def check(self, status, *options):
        run = subprocess.run([sys.executable, str(HERE / "check_starts.py"), "--project",
                              "Example=" + str(self.project), "--ledger", str(self.ledger),
                              "--cursor-home", str(self.home), "--cursor-db", str(self.db),
                              "--codex-home", str(self.root / "codex"), *options],
                             capture_output=True, text=True)
        self.assertNotIn("PRIVATE", run.stdout + run.stderr)
        rows = json.loads(run.stdout)
        self.assertEqual(rows[0]["source"], status, run.stdout + run.stderr)
        self.assertEqual(run.returncode, int(status == "unknown"), run.stderr)
        return rows[0]

    def test_completed_execution_and_its_result_locate_one_boundary(self):
        key = self.record(command=COMMAND + " && echo done", trace_output=f"trace {UNIT}\ndone\n")
        row = self.check("cursor-db")
        self.assertEqual(row["location"], key)
        self.assertEqual(row["conversation"], CONV)

    def test_only_the_successful_result_for_this_unit_corroborates_the_command(self):
        for options in (dict(status="pending"), dict(rejected=True), dict(trace_output=""),
                        dict(trace_output=f"trace {PARENT}\n"),
                        dict(trace_output=f"trace {UNIT} ended\n"),
                        dict(trace_output=f"trace {UNIT}\ntrace {PARENT}\n"),
                        dict(trace_output=f"PRIVATE example: trace {UNIT}\n")):
            with self.subTest(options=options):
                self.record(**options)
                self.check("unknown")

    def test_missing_and_unsupported_database_remain_unknown_without_creating_files(self):
        self.db = self.root / "missing.db"
        self.check("unknown")
        self.assertFalse(self.db.exists())
        self.db.write_text("PRIVATE invalid database")
        self.check("unknown")
        self.assertEqual(self.db.read_text(), "PRIVATE invalid database")

    def test_a_successful_lookup_leaves_the_inputs_unchanged(self):
        self.record()
        def digests():
            return {p: hashlib.sha256(p.read_bytes()).digest() for p in self.root.rglob("*") if p.is_file()}
        before = digests()
        self.check("cursor-db")
        self.assertEqual(before, digests())

    def test_the_tool_record_id_and_arguments_must_agree_with_its_key_and_command(self):
        key = self.record()
        with sqlite3.connect(self.db) as con:
            data = json.loads(con.execute("SELECT value FROM cursorDiskKV WHERE key=?", (key,)).fetchone()[0])
            tool = data["toolFormerData"]
            raw = json.loads(tool["rawArgs"])
            raw["command"] = "echo PRIVATE"
            tool["rawArgs"] = json.dumps(raw)
            con.execute("UPDATE cursorDiskKV SET value=? WHERE key=?", (json.dumps(data), key))
        self.check("unknown")
        self.record()
        with sqlite3.connect(self.db) as con:
            con.execute("UPDATE cursorDiskKV SET key=?", (key + "Changed",))
        self.check("unknown")

    def test_duplicate_recorded_starts_leave_the_unit_unresolved(self):
        self.record()
        jsonl(self.events, [self.event, self.end, self.event])
        self.check("unknown")

    def test_the_executed_start_must_match_all_distinguishing_arguments(self):
        changes = [("gate", "design"), ("D001 D002", "D002 D001"), ("D001 D002", "D001"),
                   ("L2", "L1"), (PARENT, UNIT), ("--parent", "--continues"),
                   ("--model example", "--model different"), (BASE[:7], "def1234"),
                   (SKILL + " --model", "other/canon-blind-review --model"),
                   ("--tier", "--slice S1 --tier"), ("python3", "echo python3")]
        for original, replacement in changes:
            with self.subTest(original=original):
                self.record(command=COMMAND.replace(original, replacement))
                self.check("unknown")

    def test_missing_other_conversation_and_duplicate_calls(self):
        self.check("unknown")
        self.record(conversation=OTHER)
        self.check("unknown")
        self.record()
        self.check("cursor-db")
        self.record(bubble=BUBBLE.replace("0001/t:", "0002/t:") + "Second")
        self.check("unknown")

    def test_an_incomplete_second_terminal_record_cannot_establish_uniqueness(self):
        self.record()
        second = self.record(bubble=BUBBLE + "Second")
        with sqlite3.connect(self.db) as con:
            raw = json.loads(con.execute("SELECT value FROM cursorDiskKV WHERE key=?", (second,)).fetchone()[0])
            del raw["completedAtMs"]
            con.execute("UPDATE cursorDiskKV SET value=? WHERE key=?", (json.dumps(raw), second))
        self.check("unknown")

    def test_a_changed_record_cannot_verify_the_published_receipt(self):
        self.record()
        row = self.check("cursor-db")
        row["result_sha256"] = ""
        receipt = self.root / "receipts.tsv"
        with receipt.open("w", newline="") as stream:
            w = csv.DictWriter(stream, row, delimiter="\t")
            w.writeheader()
            w.writerow(row)
        self.check("cursor-db", "--receipts", str(receipt))
        self.record(trace_output=f"trace {UNIT}\nchanged note\n")
        self.check("unknown", "--receipts", str(receipt))

    def test_execution_must_contain_event_time_and_respect_neighboring_boundaries(self):
        self.record(start="2026-01-01T00:00:10Z", finish="2026-01-01T00:00:16Z")
        self.check("unknown")
        self.record()
        earlier = dict(self.event, id=PARENT, at="2026-01-01T00:00:04Z")
        jsonl(self.events, [self.event, self.end, earlier])
        self.check("unknown")

    def test_named_export_takes_precedence_over_a_database_hit(self):
        self.record()
        jsonl(self.export, [shell(COMMAND), shell(self.end_command)])
        row = self.check("export")
        self.assertEqual(row["location"], "L1")

    def test_a_unique_exported_start_can_be_read_without_a_later_end(self):
        jsonl(self.export, [shell(COMMAND)])
        self.db = self.root / "absent.db"
        self.check("export")
        self.assertFalse(self.db.exists())

    def test_one_terminal_record_with_two_start_invocations_is_ambiguous(self):
        self.record(command=COMMAND + " && " + COMMAND)
        self.check("unknown")

    def test_a_missing_export_or_an_unverified_closing_anchor_is_incomplete(self):
        self.record()
        jsonl(self.export, [shell("pwd"), shell(self.end_command.replace(UNIT, PARENT))])
        self.check("unknown")
        self.export.rename(self.root / "different.jsonl")
        self.check("unknown")

    def test_ambiguous_export_stays_unknown_even_with_a_database_hit(self):
        self.record()
        duplicate = shell(COMMAND)
        duplicate["message"]["content"] *= 2
        jsonl(self.export, [duplicate, shell(self.end_command)])
        self.check("unknown")

    def test_codex_export_requires_the_output_of_the_same_command(self):
        self.case.update(host="codex", host_start=2)
        self.write_case()
        self.event["host"] = "codex"
        jsonl(self.events, [self.event, self.end])
        path = self.root / "codex/sessions/2026/01/01" / ("rollout-example-" + CONV + ".jsonl")
        meta = {"type": "session_meta", "payload": {"id": CONV}}
        call = dict(type="response_item", timestamp="2026-01-01T00:00:04.912Z",
                    payload=dict(type="custom_tool_call", name="exec", call_id="call_a",
                                 input="text(await tools.exec_command({cmd:" + json.dumps(COMMAND) + "}))"))
        reply = dict(type="response_item", timestamp="2026-01-01T00:00:05.900Z",
                     payload=dict(type="custom_tool_call_output", call_id="call_a",
                                  output=[dict(type="input_text", text=json.dumps(
                                      dict(exit_code=0, output=f"trace {UNIT}\n")))]))
        jsonl(path, [meta, call, reply])
        self.assertEqual(self.check("export")["location"], "L2/L3")
        reply["payload"]["call_id"] = "another_call"
        jsonl(path, [meta, call, reply])
        self.check("unknown")


if __name__ == "__main__":
    unittest.main()
