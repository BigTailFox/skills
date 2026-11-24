"""Recheck E005's two preselected Codex slices against the local host and Git records."""

import argparse
import csv
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re
import subprocess
import sys

HERE = Path(__file__).resolve().parent
SELECTION = "d1454e9b0dea2ee6139034f766e219ddd46ce7c8"


class MissingEvidence(ValueError):
    pass


def require(ok, message):
    if not ok:
        raise MissingEvidence(message)


def utc(stamp):
    return datetime.fromisoformat(stamp.replace("Z", "+00:00")).astimezone(timezone.utc)


def events(path):
    with path.open(encoding="utf-8") as stream:
        for number, line in enumerate(stream, 1):
            yield number, json.loads(line)


def git(project, *args):
    return subprocess.check_output(["git", "-C", str(project), *args],
                                   text=True, stderr=subprocess.DEVNULL).strip()


def session_path(home, identifier):
    require(re.fullmatch(r"[a-f0-9-]{36}", identifier), "invalid session identifier")
    found = [p for store in ("sessions", "archived_sessions") for p in
             (home / store).glob("**/rollout-*-" + identifier + ".jsonl")]
    require(len(found) == 1, "missing or ambiguous session")
    return found[0]


def slice_commit(project, commit, plan, sid):
    require(re.fullmatch(r"[a-f0-9]{40}|[a-f0-9]{64}", commit), "invalid commit identifier")
    git(project, "merge-base", "--is-ancestor", SELECTION, commit)
    path = git(project, "ls-tree", "-r", "--name-only", commit, "docs/plans")
    choices = [p for p in path.splitlines() if Path(p).name.startswith(plan + "-") and p.endswith(".md")]
    require(len(choices) == 1, "plan missing at slice commit")

    def status(tree):
        doc = git(project, "show", tree + ":" + choices[0])
        section = doc.split("### " + sid + ":", 1)[1].split("\n### ", 1)[0]
        return re.search(r"^Status: (\S+)", section, re.M)[1]

    require(status(commit) == "done" and status(commit + "^") in {"todo", "paused", "in-progress"},
            "commit did not close the slice")
    return utc(git(project, "show", "-s", "--format=%cI", commit))


def child_inventory(home, parent, start, end):
    current = start.date()
    found = []
    paths = list((home / "archived_sessions").glob("**/rollout-*.jsonl"))
    while current <= end.date():
        paths.extend((home / "sessions" / current.strftime("%Y/%m/%d")).glob("rollout-*.jsonl"))
        current += timedelta(days=1)
    for path in paths:
        with path.open(encoding="utf-8") as stream:
            meta = json.loads(next(stream))["payload"]
        source = meta.get("source")
        if isinstance(source, dict):
            link = source.get("subagent", {}).get("thread_spawn", {})
            if link.get("parent_thread_id") == parent and start <= utc(meta["timestamp"]) < end:
                found.append((path, meta, link))
    return found


def verify_slice(row, start, trace, project, home, parent_path):
    parent = start["conversation"]
    sid = start["slice"]
    expected_task = "p009_" + sid.lower()
    require(start.get("docs") == ["P009@r1"], "wrong plan revision")
    began = utc(start["at"])
    committed = slice_commit(project, row["commit"], "P009", sid)
    possible = [utc(e["at"]) for e in trace if e.get("at") and utc(e["at"]) > began
                and ((e.get("type") == "start" and e.get("parent") == start["parent"])
                     or (e.get("type") == "end" and e.get("id") == start["parent"]))]
    close = min([committed] + possible)
    require(close == committed and utc(row["git_commit_time"]) == committed, "unexpected closing boundary")
    children = child_inventory(home, parent, began, close)
    require(len(children) == 1, "missing or additional child")
    child_path, meta, link = children[0]
    child_id = meta["id"]
    require(row["child_session"] == child_id and child_path == session_path(home, child_id)
            and link["agent_path"] == "/root/" + expected_task, "child mismatch")

    dispatches, notices = [], []
    for n, record in events(parent_path):
        msg = record["payload"]
        if record["type"] != "response_item":
            continue
        stamp = utc(record["timestamp"])
        if msg.get("namespace") == "collaboration" and msg.get("name") in {"spawn_agent", "followup_task", "resume_agent"}:
            args = json.loads(msg["arguments"])
            if msg["name"] != "spawn_agent" and args.get("target", "").split("/")[-1] in {expected_task, child_id}:
                raise MissingEvidence("additional attempt targeting the worker")
            if began <= stamp < close:
                dispatches.append((n, stamp, msg["name"], args))
        if msg.get("type") == "agent_message" and msg.get("author") == "/root/" + expected_task:
            if any(c.get("text", "").startswith("Message Type: FINAL_ANSWER\n") for c in msg["content"]):
                notices.append((n, stamp))
    require(len(dispatches) == len(notices) == 1, "missing or ambiguous parent dispatch or delivery")
    n, dispatch, kind, args = dispatches[0]
    require(kind == "spawn_agent" and args["task_name"] == expected_task
            and args.get("message") and n == int(row["host_dispatch"]), "wrong parent dispatch")
    received_line, received = notices[0]
    require(received_line == int(row["host_receipt"]), "wrong parent receipt")

    briefs, finals, completions = [], [], []
    for n, record in events(child_path):
        msg = record["payload"]
        if record["type"] == "response_item" and msg.get("type") == "agent_message" and msg.get("author") == "/root":
            parts = msg["content"]
            prefix = "Message Type: NEW_TASK\nTask name: /root/" + expected_task + "\n"
            if any(part.get("text", "").startswith(prefix) for part in parts):
                briefs.append(n)
                require(any(part.get("encrypted_content") == args["message"] or
                            args["message"] in part.get("text", "") for part in parts),
                        "child brief disagrees with parent dispatch")
        if record["type"] == "response_item" and msg.get("role") == "assistant" and msg.get("phase") == "final_answer":
            finals.append((n, utc(record["timestamp"])))
        if record["type"] == "event_msg" and msg.get("type") == "task_complete":
            completions.append((n, utc(record["timestamp"])))
    require(len(briefs) == len(finals) == len(completions) == 1, "missing or extra worker turn")
    final_line, final = finals[0]
    complete_line, complete = completions[0]
    require((final_line, complete_line) == (int(row["child_final"]), int(row["child_complete"]))
            and briefs[0] < final_line < complete_line, "wrong terminal record")
    # Trace and Git carry whole seconds. Exclude ambiguous overlaps with either boundary.
    require(began + timedelta(seconds=1) <= dispatch <= utc(meta["timestamp"]) <= final <= complete < close
            and final <= received < close, "unknown or outside worker span")
    require(row["extra_attempts"] == "0" and row["result"] == "contained", "receipt disagrees with evidence")


def check(project, home, receipts):
    with receipts.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream, delimiter="\t"))
    require([r["slice"] for r in rows] == ["S1", "S2"], "expected the two preselected slices")
    trace = [e for _, e in events(project / ".canon/canon/trace/events.jsonl")]
    ids = [row["unit"] for row in rows]
    starts = [e for e in trace if e.get("type") == "start" and e.get("id") in ids]
    require([s["id"] for s in starts] == ids and [s.get("slice") for s in starts] == ["S1", "S2"]
            and all(s.get("kind") == "slice" and s.get("docs") == ["P009@r1"] and s.get("host") == "codex"
                    for s in starts), "slice selection mismatch")
    require(len({(s["parent"], s["conversation"]) for s in starts}) == 1, "slices lack a common parent")
    first, last = (utc(s["at"]) for s in starts)
    selection_time = utc(git(project, "show", "-s", "--format=%cI", SELECTION))
    require(selection_time < first, "selection did not precede the first slice")
    between = [e["id"] for e in trace if e.get("kind") == "slice" and e.get("type") == "start"
               and e.get("host") == "codex" and first <= utc(e["at"]) <= last]
    require(between == ids, "the slices were not consecutive")
    parent_path = session_path(home, starts[0]["conversation"])
    for row, start in zip(rows, starts):
        verify_slice(row, start, trace, project, home, parent_path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--codex-home", type=Path, required=True)
    parser.add_argument("--receipts", type=Path, default=HERE / "prospective-dispatch.tsv")
    args = parser.parse_args()
    try:
        check(args.project, args.codex_home, args.receipts)
    except (OSError, ValueError, KeyError, IndexError, TypeError, StopIteration, subprocess.SubprocessError) as exc:
        reason = str(exc) if isinstance(exc, MissingEvidence) else type(exc).__name__
        print("prospective result unknown:", reason, file=sys.stderr)
        return 1
    print("P009@r1 S1 and S2: 2/2 contained, one dispatch and terminal report per slice")
    return 0


if __name__ == "__main__":
    sys.exit(main())
