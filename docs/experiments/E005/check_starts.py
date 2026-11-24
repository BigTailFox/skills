"""Check host start anchors in the E003 case ledger, using only supplied local records."""

import argparse
import csv
import hashlib
import json
import re
import shlex
import sqlite3
from collections import defaultdict
from contextlib import closing
from datetime import datetime
from functools import lru_cache
from pathlib import Path

HERE = Path(__file__).resolve().parent
UUID = r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}"
UNIT = r"\d{8}T\d{6}Z-[0-9a-f]{6}"
SCRIPTS = {".agents/skills/canon/scripts/canon.py", ".claude/skills/canon/scripts/canon.py",
           "skills/governance/canon/scripts/canon.py"}


def json_lines(path):
    with path.open() as stream:
        return [json.loads(line) for line in stream]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def successful_result(tool, unit):
    if tool.get("status") != "completed":
        return False
    result = json.loads(tool.get("result", "{}"))
    if (result.get("rejected") is not False or set(result) - {"rejected", "output", "exitCode", "exit_code"}
            or result.get("exitCode", 0) != 0 or result.get("exit_code", 0) != 0):
        return False
    lines = [s for s in result.get("output", "").splitlines() if s.startswith("trace ")]
    return lines == ["trace " + unit]


def same_start(words, event, cwd):
    docs = [d.split("@")[0] for d in event["docs"]]
    prefix = [event["kind"], *docs]
    if words[:len(prefix)] != prefix:
        return False
    tail = words[len(prefix):]
    flags = dict(zip(tail[::2], tail[1::2]))
    if len(flags) * 2 != len(tail):
        return False
    expected = {"--" + k: event[k] for k in ("slice", "parent", "continues", "tier", "model")
                if event.get(k)}
    if event["kind"] in {"slice", "end-check"} and "--tier" not in flags:
        expected.pop("--tier", None)
    if event["kind"] == "slice" and "--model" not in flags:
        expected.pop("--model", None)
    skill = flags.pop("--skill", None)
    if skill:
        recorded = Path(event["skill"])
        if cwd is None and not str(recorded).endswith("/" + skill):
            return False
        if cwd is not None and Path(cwd) / skill != recorded:
            return False
    elif event["kind"] != "slice":
        return False
    base = flags.pop("--base", None)
    if base:
        if base == "HEAD":
            base = event.get("head")
        if not base or not re.fullmatch("[0-9a-f]{7,40}", base) or not (event.get("base") or "").startswith(base):
            return False
    elif event.get("base"):
        return False
    return flags == expected


def executed_start(tool, event):
    params = json.loads(tool["params"])
    if " trace start " not in params.get("command", ""):
        return False
    executable = params["parsingResult"]["executableCommands"][0]
    if executable["name"] != "python3" or any(a["type"] != "word" for a in executable["args"]):
        return False
    words = [a["value"] for a in executable["args"]]
    command = params["command"]
    full = executable["fullText"]
    if (len(words) < 4 or words[0] not in SCRIPTS or words[1:3] != ["trace", "start"]
            or shlex.split(full) != ["python3", *words] or command.count(" trace start ") != 1
            or not (command == full or command.startswith(full + " && "))):
        return False
    raw = json.loads(tool["rawArgs"])
    return (raw["command"] == command and raw["conversationId"] == event["conversation"]
            and raw["workingDirectory"] == params["cwd"] and same_start(words[3:], event, params["cwd"]))


def milliseconds(value):
    return round(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp() * 1000)


def neighboring_times(event, events):
    units = {e["id"] for e in events if e.get("type") == "start" and e.get("conversation") == event["conversation"]}
    times = [milliseconds(e["at"]) for e in events if e.get("type") in {"start", "end"} and e["id"] in units]
    at = milliseconds(event["at"])
    return max((t for t in times if t < at), default=0), min((t for t in times if t > at), default=float("inf"))


def database_start(path, event, events):
    if not path:
        return
    path = path.resolve()
    conversation = event["conversation"]
    prefix = "bubbleId:" + conversation + ":"
    at = milliseconds(event["at"])
    before, after = neighboring_times(event, events)
    query = """SELECT key, json_extract(value, '$.bubbleId'), json_extract(value, '$.createdAt'),
                      json_extract(value, '$.startedAtMs'), json_extract(value, '$.completedAtMs'),
                      json_extract(value, '$.toolFormerData'), value
               FROM cursorDiskKV WHERE key GLOB ?
               AND json_extract(value, '$.type') = 2
               AND json_extract(value, '$.toolFormerData.name') = 'run_terminal_command_v2'
               AND coalesce(json_extract(value, '$.startedAtMs'), 0) < ?
               AND coalesce(json_extract(value, '$.completedAtMs'), 9223372036854775807) >= ?"""
    hits = []
    uri = path.resolve().as_uri() + "?mode=ro"
    with path.open("rb") as file:
        uses_wal = file.read(20)[18:19] == b"\x02"
    if uses_wal:
        wal, shm = (Path(str(path) + suffix).exists() for suffix in ("-wal", "-shm"))
        if wal != shm:
            return None
        if not wal:
            uri += "&immutable=1"  # A checkpoint without sidecars must not acquire new ones.
    with closing(sqlite3.connect(uri, uri=True)) as db:
        db.execute("PRAGMA query_only=ON")
        for key, bubble, created, start, finish, encoded, value in db.execute(query, (prefix + "*/t:*", at + 1000, at)):
            if key != prefix + bubble or not re.fullmatch(UUID + r"/t:toolu_[a-zA-Z0-9]{1,64}", bubble):
                continue
            tool = json.loads(encoded)
            if not bubble.endswith("/t:" + tool["toolCallId"]) or not executed_start(tool, event):
                continue
            if start is None or finish is None or created is None:
                hits.append(None)
                continue
            if milliseconds(created) != start or not (before <= start <= finish < after):
                continue
            source = value.encode() if isinstance(value, str) else value
            hits.append((key, digest(source)) if successful_result(tool, event["id"]) else None)
    return hits[0] if len(hits) == 1 else None


@lru_cache(maxsize=None)
def cursor_shells(home, conversation):
    path, = (home / "projects").glob(f"*/agent-transcripts/{conversation}/{conversation}.jsonl")
    calls = []
    with path.open("rb") as stream:
        for line, raw in enumerate(stream, 1):
            record = json.loads(raw)
            if record.get("role") != "assistant":
                continue
            for part in record.get("message", {}).get("content", []):
                if part.get("type") != "tool_use" or part.get("name") != "Shell":
                    continue
                command = part["input"].get("command", "")
                if "trace start " in command or "trace end " in command:
                    calls.append((line, command, part["input"].get("working_directory"), digest(raw.rstrip(b"\r\n"))))
    return calls


def invocations(command, verb):
    # Recognize the two locally defined aliases used in the frozen Cursor exports.
    lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|()")
    lexer.whitespace_split = True
    words = list(lexer)
    for i in range(1, len(words) - 1):
        if words[i:i + 2] != ["trace", verb]:
            continue
        if words[i - 1] == "c" and any(f'c() {{ python3 {p} "$@"; }}' in command for p in SCRIPTS):
            start = i - 1
        elif i >= 2 and words[i - 2] == "python3":
            path = words[i - 1]
            if path not in SCRIPTS and not (path == "$P" and any("P=" + p in words[:i] for p in SCRIPTS)):
                continue
            start = i - 2
        else:
            continue
        if start and not re.fullmatch("[;&|()]+", words[start - 1]):
            continue
        end = next((j for j in range(i + 2, len(words)) if re.fullmatch("[;&|()]+", words[j])), len(words))
        args = words[i + 2:end]
        if "$base" in args and "base=$(git rev-parse --short HEAD)" in command:
            args = ["HEAD" if a == "$base" else a for a in args]
        yield args


def cursor_start(case, event, events, cursor_home, cursor_db=None):
    calls = cursor_shells(cursor_home, event["conversation"])
    local_gap = case["host_start"] == "local-db"
    if local_gap:
        end_line = int(case["host_end"])
        candidates = [c for c in calls if c[0] <= end_line]
    else:
        candidates = [c for c in calls if c[0] == int(case["host_start"])]
    hits = [(line, sha) for line, command, cwd, sha in candidates for words in invocations(command, "start")
            if same_start(words, event, cwd)]
    if len(hits) == 1:
        line, sha = hits[0]
        return dict(source="export", location=f"L{line}", record_sha256=sha)
    if not hits and local_gap:
        end_events = [(i, e) for i, e in enumerate(events, 1) if e.get("type") == "end" and e.get("id") == event["id"]]
        if (len(end_events) != 1 or end_events[0][0] != int(case["end_event"])
                or end_events[0][1]["outcome"] != case["outcome"]):
            return {}
        closings = [words for line, command, _, _ in calls if line == end_line
                    for words in invocations(command, "end") if words[:2] == [event["id"], case["outcome"]]]
        if len(closings) != 1:
            return {}
        hit = database_start(cursor_db, event, events)
        if hit:
            key, sha = hit
            return dict(source="cursor-db", location=key, record_sha256=sha)
    return {}


def result_text(value):
    # The pilot's Codex exec calls returned shell results directly or as labeled tuples.
    if isinstance(value, dict):
        if value.get("exit_code") == 0:
            return value.get("output", "")
        if value.get("exit") == 0:
            return value.get("text", "")
    if isinstance(value, list) and len(value) == 2:
        return result_text(value[1]) if isinstance(value[1], dict) else value[1]
    if isinstance(value, list) and len(value) == 3 and value[1] == 0:
        return value[2]
    return ""


@lru_cache(maxsize=None)
def codex_calls(home, conversation):
    paths = [p for directory in ("sessions", "archived_sessions") for p in
             (home / directory).glob("**/rollout-*-" + conversation + ".jsonl")]
    path, = paths
    calls = {}
    ids = set()
    replies = defaultdict(list)
    with path.open("rb") as stream:
        header = json.loads(next(stream))
        if header.get("type") != "session_meta" or header["payload"]["id"] != conversation:
            return {}, {}
        for line, raw in enumerate(stream, 2):
            record = json.loads(raw)
            if record.get("type") != "response_item":
                continue
            part = record["payload"]
            ident = part.get("call_id")
            if part.get("type") in {"function_call", "custom_tool_call"} and part.get("name") in {"exec", "exec_command"}:
                command = part.get("input") or part.get("arguments", "")
                if "canon.py trace start " in command:
                    calls[line] = (ident, command, milliseconds(record["timestamp"]), digest(raw.rstrip(b"\r\n")))
                    ids.add(ident)
            if ident in ids and part.get("type") in {"function_call_output", "custom_tool_call_output"}:
                receipts = []
                for item in part["output"]:
                    try:
                        value = result_text(json.loads(item["text"]))
                    except (ValueError, KeyError, TypeError):
                        continue
                    if isinstance(value, str):
                        traces = [s for s in value.splitlines() if s.startswith("trace ")
                                  and not re.fullmatch("trace " + UNIT + " ended", s)]
                        if traces:
                            receipts.append(traces)
                replies[ident].append((line, receipts, milliseconds(record["timestamp"]), digest(raw.rstrip(b"\r\n"))))
    return calls, replies


def codex_start(case, event, home):
    calls, replies = codex_calls(home, event["conversation"])
    line = int(case["host_start"])
    ident, command, called, call_sha = calls[line]
    (output_line, receipts, finished, output_sha), = replies[ident]
    at = milliseconds(event["at"])
    executable = r"\bpython3 (?:" + "|".join(re.escape(p) for p in SCRIPTS) + r") trace start "
    if (not re.search(executable + re.escape(event["kind"]) + r"\b", command.replace("\\n", "\n"))
            or not (called < at + 1000 and finished >= at and line < output_line)
            or receipts.count(["trace " + event["id"]]) != 1):
        return {}
    return dict(source="export", location=f"L{line}/L{output_line}", record_sha256=call_sha, result_sha256=output_sha)


def locate(case, project, args):
    events = json_lines(project / ".canon/canon/trace/events.jsonl")
    line = int(case["start_event"])
    starts = [i for i, e in enumerate(events, 1) if e.get("type") == "start" and e.get("id") == case["unit"]]
    if starts != [line]:
        return {}
    event = events[line - 1]
    if (event["host"] != case["host"] or event["kind"] != case["kind"]
            or (event.get("tier") or "-") != case["tier"] or (event.get("parent") or "-") != case["parent"]
            or not re.fullmatch(UUID, event["conversation"])):
        return {}
    if event["host"] == "cursor":
        return dict(conversation=event["conversation"], **cursor_start(case, event, events, args.cursor_home, args.cursor_db))
    if event["host"] == "codex":
        return dict(conversation=event["conversation"], **codex_start(case, event, args.codex_home))
    return {}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", action="append", required=True, metavar="NAME=DIR")
    parser.add_argument("--ledger", type=Path, default=HERE.parent / "E003/cases.tsv")
    parser.add_argument("--receipts", type=Path, help="also verify the redacted E005 source locations and digests")
    parser.add_argument("--cursor-home", type=Path)
    parser.add_argument("--cursor-db", type=Path)
    parser.add_argument("--codex-home", type=Path)
    args = parser.parse_args()
    projects = {}
    for value in args.project:
        label, equals, path = value.partition("=")
        if not equals or not re.fullmatch("[A-Za-z0-9_-]+", label) or not path or label in projects:
            parser.error("supply each project once as NAME=DIR")
        projects[label] = Path(path)
    if len({p.resolve() for p in projects.values()}) != len(projects):
        parser.error("each project needs its own directory")
    with args.ledger.open() as stream:
        cases = [r for r in csv.DictReader(stream, delimiter="\t") if r["project"] in projects]
    keys = {(r["project"], r["unit"]) for r in cases}
    if (len(keys) != len(cases) or {p for p, _ in keys} != projects.keys()
            or any(not re.fullmatch(UNIT, u) for _, u in keys)):
        parser.error("missing or ambiguous ledger identity")
    receipts = {}
    if args.receipts:
        with args.receipts.open() as stream:
            expected = [r for r in csv.DictReader(stream, delimiter="\t") if r["project"] in projects]
        receipts = {(r["project"], r["unit"]): r for r in expected}
        if receipts.keys() != keys or len(receipts) != len(expected):
            parser.error("receipt inventory differs from the selected ledger")
    rows = []
    for case in cases:
        row = dict(project=case["project"], unit=case["unit"], source="unknown")
        try:
            found = locate(case, projects[case["project"]], args)
            receipt = receipts.get((case["project"], case["unit"]))
            if receipt is None or all(found.get(f, "") == receipt[f] for f in
                                      ("source", "conversation", "location", "record_sha256", "result_sha256")):
                row.update(found)
        except (OSError, sqlite3.Error, ValueError, KeyError, TypeError, IndexError, StopIteration, AttributeError):
            pass
        rows.append(row)
    print(json.dumps(rows, indent=2))
    return int(any(r["source"] == "unknown" for r in rows))


if __name__ == "__main__":
    raise SystemExit(main())
