"""Recheck the eleven published P006/P007 worker intervals in the named local records."""

import argparse
import csv
import json
import re
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from check_starts import codex_start, cursor_start

HERE = Path(__file__).resolve().parent


def require(test):
    if not test:
        raise ValueError("unverified evidence")


def table(path):
    with path.open() as stream:
        return list(csv.DictReader(stream, delimiter="\t"))


def records(path):
    with path.open() as stream:
        return [json.loads(line) for line in stream]


def time(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def git(project, *args):
    return subprocess.check_output(["git", *args], cwd=project, text=True, stderr=subprocess.DEVNULL).strip()


def closing_commit(project, row, start, events):
    commit = row["commit"]
    files = git(project, "ls-tree", "-r", "--name-only", commit).splitlines()
    path, = [p for p in files if "/plans/" + row["plan"] + "-" in p and p.endswith(".md")]
    def status(revision):
        plan = git(project, "show", revision + ":" + path)
        section = plan.split("### " + row["slice"] + ":", 1)[1].split("\n### ", 1)[0]
        return re.search(r"^Status: (\S+)$", section, re.M)[1]
    require(status(commit) == "done" and status(commit + "^") != "done")
    close = time(git(project, "show", "-s", "--format=%cI", commit))
    require(close == time(row["commit_utc"]))
    # Each of the eleven Git seconds precedes the next sibling start or enclosing end.
    later = [time(e["at"]) for e in events
             if (e.get("type") == "start" and e.get("parent") == start["parent"]
                 or e.get("type") == "end" and e.get("id") == start["parent"])
             and time(e["at"]) > time(start["at"])]
    require(later and close < min(later))
    return close


def content(row):
    return row.get("message", {}).get("content", [])


def cursor_runs(rows, home, first, after, project):
    conversation = rows[0]["parent_session"]
    path, = (home / "projects").glob(f"*/agent-transcripts/{conversation}/{conversation}.jsonl")
    parent = records(path)
    calls = {}
    for n, record in enumerate(parent, 1):
        for part in content(record):
            tool = part.get("input", {})
            if (part.get("type") != "tool_use" or part.get("name") != "CallDynamicTool"
                    or tool.get("toolName") != "Task"):
                continue
            args = tool["arguments"]
            if isinstance(args, str):
                args = json.loads(args)
            if first <= n < after or re.search(r"\bP006\s+S[1-7]\b", args.get("description", ""), re.I):
                require(n not in calls)
                calls[n] = args
    require(set(calls) == {int(r["dispatch_line"]) for r in rows})
    for r in rows:
        dispatch, commit = int(r["dispatch_line"]), int(r["commit_line"])
        next_start = min((int(s["start_line"]) for s in rows if int(s["start_line"]) > int(r["start_line"])),
                         default=after)
        args = calls[dispatch]
        require(args.get("run_in_background") is False and not args.get("resume"))
        require(re.search(r"\bP006\s+" + r["slice"] + r"\b", args["description"], re.I))
        require(int(r["start_line"]) < dispatch < commit < next_start)
        subject = git(project, "show", "-s", "--format=%s", r["commit"])
        require(any(p.get("name") == "Shell" and "git commit" in p["input"]["command"]
                    and subject in p["input"]["command"] for p in content(parent[commit - 1])))
        children = []
        for file in (path.parent / "subagents").glob("*.jsonl"):
            with file.open() as stream:
                opening = json.loads(next(stream))
            if any(args["prompt"] in p.get("text", "") for p in content(opening)):
                children.append(file)
        child, = children
        require(child.stem == r["worker"])
        turns = records(child)
        require(len(turns) == int(r["complete_line"]) == int(r["report_line"]) + 1)
        require(sum(t.get("type") == "turn_ended" for t in turns) == 1)
        require(all(r[f] == "-" for f in ("dispatch_utc", "report_utc", "complete_utc")))
        require(turns[-1] == {"type": "turn_ended", "status": "success"} and turns[-2].get("role") == "assistant")
        require(any(re.search(r"\bdone\b", p.get("text", ""), re.I) for p in content(turns[-2])))
        require(r["result"] == "contained")


def codex_runs(rows, home, first, after, opened):
    conversation = rows[0]["parent_session"]
    paths = [p for folder in ("sessions", "archived_sessions") for p in
             (home / folder).glob("**/rollout-*.jsonl")]
    parent_path, = [p for p in paths if p.name.endswith("-" + conversation + ".jsonl")]
    parent = records(parent_path)
    require(parent[0]["payload"]["id"] == conversation)
    children = {}
    keys = {"p007_" + r["slice"].lower() for r in rows}
    for path in paths:
        with path.open() as stream:
            meta = json.loads(next(stream))["payload"]
        source = meta.get("source")
        link = source.get("subagent", {}).get("thread_spawn", {}) if isinstance(source, dict) else {}
        if link.get("parent_thread_id") != conversation:
            continue
        key = link.get("agent_path", "").split("/")[-1]
        if first <= time(meta["timestamp"]) < after or re.match(r"p007_s[1-4](?:\b|_)", key):
            require(key not in children)
            children[key] = (path, meta["id"])
    require(children.keys() == keys)
    launches = {}
    receipts = {}
    for n, event in enumerate(parent, 1):
        part = event.get("payload", {})
        name = part.get("name")
        if part.get("type") == "function_call_output" and part.get("call_id") in launches:
            receipts[part["call_id"]] = str(part["output"])
        if part.get("namespace") != "collaboration" or name not in {"spawn_agent", "followup_task", "resume_agent"}:
            continue
        args = json.loads(part["arguments"])
        key = (args.get("task_name") or args.get("target") or "").split("/")[-1]
        if (first <= time(event["timestamp"]) < after or re.match(r"p007_s[1-4](?:\b|_)", key)
                or key in {v[1] for v in children.values()}):
            require(name == "spawn_agent" and key in keys)
            launches[part["call_id"]] = (n, key, event["timestamp"])
    require(len(launches) == len(rows) and receipts.keys() == launches.keys())
    for r in rows:
        key = "p007_" + r["slice"].lower()
        path, child = children[key]
        call, = [ident for ident, (_, tag, _) in launches.items() if tag == key]
        n, _, sent = launches[call]
        require(n == int(r["dispatch_line"]) and sent == r["dispatch_utc"] and key in receipts[call])
        require(child == r["worker"] and int(r["start_line"]) < n)
        require(r["commit_line"] == "-")
        turns = records(path)
        def positions(kind, label):
            return [i for i, t in enumerate(turns, 1) if t["type"] == kind
                    and t["payload"].get("type") == label]
        require(len(positions("event_msg", "task_started")) == 1)
        require(positions("event_msg", "task_complete") == [int(r["complete_line"])])
        finals = [i for i, t in enumerate(turns, 1) if t["type"] == "response_item"
                  and t["payload"].get("role") == "assistant" and t["payload"].get("phase") == "final_answer"]
        require(finals == [int(r["report_line"])] and int(r["report_line"]) < int(r["complete_line"]))
        for field in ("report", "complete"):
            require(turns[int(r[field + "_line"]) - 1]["timestamp"] == r[field + "_utc"])
        final, complete = time(r["report_utc"]), time(r["complete_utc"])
        close = time(r["commit_utc"])
        require(opened[r["unit"]] + timedelta(seconds=1) <= time(sent) <= final <= complete)
        if complete < close:
            result = "contained"
        elif final >= close + timedelta(seconds=1):
            result = "outside"
        else:
            result = "unknown"
        require(result == r["result"] and result != "unknown")


def verify(project, cursor, codex):
    rows = table(HERE / "frozen-workers.tsv")
    ledger = table(HERE.parent / "E003/cases.tsv")
    cases = {r["unit"]: r for r in ledger if r["kind"] == "slice"}
    require(len(rows) == len(cases) == 11 and {r["unit"] for r in rows} == cases.keys())
    events = records(project / ".canon/canon/trace/events.jsonl")
    opened = {}
    for r in rows:
        case = cases[r["unit"]]
        require(r["project"] == case["project"] == "Canon" and r["host"] == case["host"])
        require((r["start_event"], r["start_line"], r["commit"]) ==
                (case["start_event"], case["host_start"], case["host_end"]))
        start, = [e for e in events if e.get("type") == "start" and e.get("id") == r["unit"]]
        require(start == events[int(r["start_event"]) - 1] and start["conversation"] == r["parent_session"])
        require(start["docs"] == [r["plan"] + "@r1"] and start["slice"] == r["slice"])
        require(sum(e.get("type") == "start" and e.get("parent") == start["parent"]
                    and e.get("slice") == r["slice"] for e in events) == 1)
        if r["host"] == "cursor":
            anchor = cursor_start(case, start, events, cursor)
        else:
            anchor = codex_start(case, start, codex)
        require(anchor.get("source") == "export")
        closing_commit(project, r, start, events)
        opened[r["unit"]] = time(start["at"])
    for host in ("cursor", "codex"):
        group = [r for r in rows if r["host"] == host]
        parent = cases[group[0]["unit"]]["parent"]
        review, = [r for r in ledger if r["parent"] == parent and r["kind"] == "code-review"]
        if host == "cursor":
            cursor_runs(group, cursor, min(int(r["start_line"]) for r in group), int(review["host_start"]), project)
        else:
            after = time(events[int(review["start_event"]) - 1]["at"])
            codex_runs(group, codex, min(opened[r["unit"]] for r in group), after, opened)
    return {key: sum(r["result"] == key for r in rows) for key in ("contained", "outside", "unknown")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--canon-project", required=True, type=Path)
    parser.add_argument("--cursor-home", required=True, type=Path)
    parser.add_argument("--codex-home", required=True, type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(verify(args.canon_project, args.cursor_home, args.codex_home)))
    except (ValueError, OSError, KeyError, IndexError, TypeError, StopIteration, subprocess.SubprocessError):
        print('{"status":"unknown"}')
        raise SystemExit(1)
