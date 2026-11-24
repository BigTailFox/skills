"""Recheck E005's two preselected Codex slices against the local host and Git records."""

import argparse
import csv
import hashlib
from datetime import timedelta
import json
from pathlib import Path
import re
import subprocess
import sys

from check_frozen_workers import git, slice_transition, time as utc

HERE = Path(__file__).resolve().parent
SELECTION = "d1454e9b0dea2ee6139034f766e219ddd46ce7c8"


class MissingEvidence(ValueError):
    pass


def require(ok, message):
    if not ok:
        raise MissingEvidence(message)


def events(path):
    with path.open(encoding="utf-8") as stream:
        for number, line in enumerate(stream, 1):
            yield number, json.loads(line)


def session_path(home, identifier):
    require(re.fullmatch(r"[a-f0-9-]{36}", identifier), "invalid session identifier")
    found = [p for store in ("sessions", "archived_sessions") for p in
             (home / store).glob("**/rollout-*-" + identifier + ".jsonl")]
    require(len(found) == 1, "missing or ambiguous session")
    return found[0]


def child_inventory(home, parent):
    children = []
    for store in ("sessions", "archived_sessions"):
        for path in (home / store).glob("**/rollout-*.jsonl"):
            with path.open(encoding="utf-8") as stream:
                meta = json.loads(next(stream))["payload"]
            source = meta.get("source")
            if isinstance(source, dict):
                link = source.get("subagent", {}).get("thread_spawn", {})
                if link.get("parent_thread_id") == parent:
                    children.append((path, meta, link))
    return children


def named_worker(name, expected):
    return bool(re.match(re.escape(expected) + r"(?:$|[^a-z0-9])", name.split("/")[-1].lower()))


def next_boundary(trace, start):
    position = trace.index(start)
    return next((utc(e["at"]) for e in trace[position + 1:]
                 if (e.get("type") == "start" and e.get("parent") == start["parent"])
                 or (e.get("type") == "end" and e.get("id") == start["parent"])), None)


def verify_slice(row, start, trace, project, home, parent_path, children, observation):
    cutoff = utc(observation["at"])
    nonworkers = {r["session"] for r in observation["review_calls"]}
    review_lines = {r["line"] for r in observation["review_calls"]}
    sid = start["slice"]
    expected_task = "p009_" + sid.lower()
    require(start.get("docs") == ["P009@r1"], "wrong plan revision")
    began = utc(start["at"])
    require(re.fullmatch(r"[a-f0-9]{40}|[a-f0-9]{64}", row["commit"]), "invalid commit")
    git(project, "merge-base", "--is-ancestor", SELECTION, row["commit"])
    committed = slice_transition(project, row["commit"], "P009", sid)
    boundary = next_boundary(trace, start)
    require((boundary is None or committed < boundary) and utc(row["git_commit_time"]) == committed,
            "unexpected or ambiguous closing boundary")
    close = committed
    children = [(path, meta, link) for path, meta, link in children
                if meta["id"] not in nonworkers and utc(meta["timestamp"]) <= cutoff and
                (named_worker(link["agent_path"], expected_task) or began <= utc(meta["timestamp"]) < close)]
    require(len(children) == 1, "missing or additional child")
    child_path, meta, link = children[0]
    child_id = meta["id"]
    require(row["child_session"] == child_id and child_path == session_path(home, child_id)
            and link["agent_path"] == "/root/" + expected_task, "child mismatch")

    dispatches, notices = [], []
    for n, record in events(parent_path):
        if n > observation["line"]:
            break
        if n in review_lines:
            continue
        msg = record["payload"]
        if record["type"] != "response_item":
            continue
        stamp = utc(record["timestamp"])
        if msg.get("namespace") == "collaboration" and msg.get("name") in {"spawn_agent", "followup_task", "resume_agent"}:
            args = json.loads(msg["arguments"])
            key = args.get("task_name") or args.get("target", "")
            if msg["name"] != "spawn_agent" and (named_worker(key, expected_task) or key == child_id):
                raise MissingEvidence("additional attempt targeting the worker")
            if named_worker(key, expected_task) or began <= stamp < close:
                dispatches.append((n, stamp, msg["name"], args))
        if msg.get("type") == "agent_message" and msg.get("author") == "/root/" + expected_task:
            if any(c.get("text", "").startswith("Message Type: FINAL_ANSWER\n") for c in msg["content"]):
                body = "".join(c.get("text", "") for c in msg["content"]).partition("Payload:\n")[2].strip()
                require(body, "parent received no final report")
                notices.append((n, stamp, body))
    require(len(dispatches) == len(notices) == 1, "missing or ambiguous parent dispatch or delivery")
    n, dispatch, kind, args = dispatches[0]
    require(kind == "spawn_agent" and args["task_name"] == expected_task
            and args.get("message") and n == int(row["host_dispatch"]), "wrong parent dispatch")
    received_line, received, delivered_report = notices[0]
    require(received_line == int(row["host_receipt"]), "wrong parent receipt")

    briefs, finals, completions = [], [], []
    for n, record in events(child_path):
        if utc(record["timestamp"]) > cutoff:
            continue
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
            text = "".join(c.get("text", "") for c in msg.get("content", [])).strip()
            require(text and text == delivered_report, "worker final and parent receipt disagree")
            finals.append((n, utc(record["timestamp"])))
        if record["type"] == "event_msg" and msg.get("type") == "task_complete":
            require((msg.get("last_agent_message") or "").strip() == delivered_report, "completion report mismatch")
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


def selected_sequence(trace, selection_time, starts):
    require(selection_time < utc(starts[0]["at"]), "selection did not precede first slice")
    stop = trace.index(starts[-1]) + 1
    between = [e["id"] for e in trace[:stop] if e.get("kind") == "slice" and e.get("type") == "start"
               and e.get("host") == "codex" and selection_time <= utc(e["at"])]
    require(between == [s["id"] for s in starts], "selection did not name the next two slices")


def record_hash(raw):
    return hashlib.sha256(raw.rstrip(b"\r\n")).hexdigest()


def audit_interval(project, parent_path, children, starts, trace, rows, selected_at, observed):
    """Account for every parent dispatch and linked child through the pinned host observation."""
    require(observed["parent"] == starts[0]["conversation"], "checkpoint belongs to another parent")
    cutoff = utc(observed["at"])
    require(utc(rows[-1]["git_commit_time"]) + timedelta(seconds=1) <= cutoff, "checkpoint precedes the pair")
    expected = {r["child_session"] for r in rows}
    reviews = {r["line"]: r for r in observed["review_calls"]}
    require(len(reviews) == len(observed["review_calls"]), "ambiguous review call")
    eligible = [(meta, link) for _, meta, link in children if selected_at <= utc(meta["timestamp"]) <= cutoff]
    paths = {meta["id"]: link["agent_path"].split("/")[-1] for meta, link in eligible}
    require(len(paths) == len(eligible) and set(paths) == expected | {r["session"] for r in reviews.values()},
            "unaccounted linked child through observation")
    dispatches = {int(r["host_dispatch"]): r for r in rows}
    seen = set()
    marker = "P009@r1 worker audit observation: " + " ".join(r["unit"] + "=" + r["commit"] for r in rows)
    with parent_path.open("rb") as stream:
        for number, raw in enumerate(stream, 1):
            event = json.loads(raw)
            msg = event["payload"]
            if number == observed["line"]:
                require(record_hash(raw) == observed["sha256"] and utc(event["timestamp"]) == cutoff
                        and event["type"] == "response_item"
                        and msg.get("type") in {"custom_tool_call_output", "function_call_output"}
                        and marker in str(msg.get("output", "")), "invalid host observation")
                break
            if event["type"] != "response_item" or utc(event["timestamp"]) < selected_at:
                continue
            if msg.get("namespace") != "collaboration" or msg.get("name") not in {"spawn_agent", "resume_agent", "followup_task"}:
                continue
            seen.add(number)
            args = json.loads(msg["arguments"])
            name = (args.get("task_name") or args.get("target", "")).split("/")[-1]
            if number in dispatches:
                require(msg["name"] == "spawn_agent" and name == paths[dispatches[number]["child_session"]],
                        "unmatched worker dispatch")
                continue
            receipt = reviews.get(number)
            require(receipt and record_hash(raw) == receipt["sha256"], "unaccounted dispatch through observation")
            require(name in {receipt["session"], paths[receipt["session"]]}, "wrong review session")
            unit, axis = receipt["review_unit"], receipt["axis"]
            gate = [e for e in trace if e.get("id") == unit and e.get("type") == "start"
                    and e.get("kind") == "code-review" and e.get("parent") == starts[0]["parent"]]
            require(len(gate) == 1 and utc(gate[0]["at"]) <= utc(event["timestamp"]) and axis in {"spec", "standards"},
                    "dispatch has no matching review")
            ends = [e for e in trace if e.get("id") == unit and e.get("type") == "end"]
            if ends:
                require(len(ends) == 1 and any(r["role"] == axis and r.get("id") == receipt["session"]
                        for r in ends[0]["dispositions"]["reviewers"]), "unbound archived reviewer")
            else:
                folder = project / ".canon/canon-blind-review/P009-code-review"
                require((folder / "trace-unit.txt").read_text().strip() == unit and
                        (folder / (axis + "-id.txt")).read_text().strip() == receipt["session"],
                        "unbound live reviewer")
        else:
            raise MissingEvidence("checkpoint not present")
    require(seen == set(dispatches) | set(reviews), "missing dispatch or reviewer receipt")


def check(project, home, receipts, observation):
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
    selected_at = utc(git(project, "show", "-s", "--format=%cI", SELECTION))
    selected_sequence(trace, selected_at, starts)
    parent_path = session_path(home, starts[0]["conversation"])
    children = child_inventory(home, starts[0]["conversation"])
    observed = json.loads(observation.read_text())
    audit_interval(project, parent_path, children, starts, trace, rows, selected_at, observed)
    for row, start in zip(rows, starts):
        verify_slice(row, start, trace, project, home, parent_path, children, observed)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--codex-home", type=Path, required=True)
    parser.add_argument("--receipts", type=Path, default=HERE / "prospective-dispatch.tsv")
    parser.add_argument("--observation", type=Path, default=HERE / "worker-observation.json")
    args = parser.parse_args()
    try:
        check(args.project, args.codex_home, args.receipts, args.observation)
    except (OSError, ValueError, KeyError, IndexError, TypeError, StopIteration, subprocess.SubprocessError) as exc:
        reason = str(exc) if isinstance(exc, MissingEvidence) else type(exc).__name__
        print("prospective result unknown:", reason, file=sys.stderr)
        return 1
    print("P009@r1 S1 and S2: 2/2 contained, one dispatch and terminal report per slice")
    return 0


if __name__ == "__main__":
    sys.exit(main())
