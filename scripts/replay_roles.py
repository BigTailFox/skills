"""Keep historical identities and private briefs bound to the original role and dispatch."""
from pathlib import Path

from replay_git import sha256
from trace_codex import CodexSession
from trace_hosts import CursorSession, object_value, records
from trace_records import UNKNOWN, stamp
from trace_review_evidence import Archive
from trace_reviewer_cost import reviewer_session
from trace_workers import cursor_children


def known(value):
    return value if isinstance(value, str) and value and value != UNKNOWN else None


def dispatch(case, attempt):
    """Recover the actual tool arguments, including when Cursor exports several calls on one line."""
    session = case.host_session
    if not session or not known(attempt.get("session")):
        return None
    path, _, n = attempt["dispatch_location"].rpartition("#L")
    if path != str(session.path) or not n.isdecimal():
        return None
    line = int(n)
    if isinstance(session, CodexSession):
        calls = [(cid, d) for cid, d in session.dispatches.items() if d.point.line == line and d.verb == "spawn_agent"]
        if len(calls) != 1 or len(calls[0][1].receipts) != 1 or len(calls[0][1].receipts[0][1]) > 1:
            return None
        cid = calls[0][0]
        part = next((row.get("payload", {}) for i, row in records(session.path) if i == line), {})
        if part.get("name") != "spawn_agent" or part.get("call_id") != cid:
            return None
        return cid, object_value(part.get("arguments")), "message"
    if isinstance(session, CursorSession):
        child = Path(attempt.get("child_location", "").rpartition("#L")[0])
        opening = cursor_children(session).get(child)
        if not opening:
            return None
        matches = [(i, args) for i, (n, args) in enumerate(session.dispatches)
                   if n == line and not args.get("resume") and isinstance(args.get("prompt"), str)
                   and args["prompt"] and args["prompt"] in opening]
        if len(matches) == 1:
            return matches[0][0], matches[0][1], "prompt"
    return None


def initial_worker(case):
    unavailable = dict(status="unavailable", source=None, sha256=None, text=None)
    attempts = case.data["worker_attempts"]
    if not attempts or any(a["mode"] == UNKNOWN for a in attempts):
        return unavailable, None
    first = attempts[0]
    if (first["mode"] != "launch" or first["containment"] != "contained" or
            not known(first["terminal_location"]) or not known(first["session"])):
        return unavailable, None
    bound = dispatch(case, first)
    model = known(first.get("model"))
    effort = known(first.get("effort"))
    if bound is None:
        return unavailable, None
    cid, args, field = bound
    if isinstance(case.host_session, CursorSession):
        model = known(args.get("model"))
    settings = dict(model=model, effort=effort)
    text = args.get(field)
    if not isinstance(text, str) or not text.strip():
        return unavailable, settings
    source = {k: first[k] for k in ("session", "dispatch_location", "terminal_location")}
    source["call_id"] = cid
    return dict(status="available", text=text, sha256=sha256(text.encode()), source=source), settings


def reviewer_interval(case, catalog, report, archive):
    """A later confirmation in the same child rollout can have a different model."""
    if catalog is None or case.data["host"] != "codex":
        return None
    session = reviewer_session(catalog, [case], report["session"])
    body = archive.read(report["stem"] + ".md")
    if not session or body is None:
        return None
    parent = case.data["conversation"]
    if any(parent != owner and any(uid == session.session_id for uid, _ in children)
           for owner, children in catalog.children.items()):
        return None
    opened, closed = case.history.started, stamp(case.closing.get("at"))
    if not opened or not closed:
        return None
    wanted = sha256(body.decode().strip().encode())
    intervals = []
    for i, opening in enumerate(session.starts):
        stop = session.starts[i+1].line if i+1 < len(session.starts) else float("inf")
        events = [t for t in session.terminals if opening.line < t.point.line < stop]
        ends = [t for t in events if t.kind in {"task_complete", "turn_complete"}]
        if (len(ends) != 1 or not opening.at or not ends[0].point.at or
                not opened <= opening.at <= ends[0].point.at <= closed):
            continue
        end = ends[0].point.line
        if any(opening.line <= n <= end for n in session.holes):
            continue
        fingerprints = {t.body for t in events if t.body}
        intervals.append((opening.line, end, fingerprints))
    matches = [(a, b) for a, b, prints in intervals if prints == {wanted}]
    # A single registered dispatch may finish without preserving the report text
    # in its terminal receipt. An explicitly different report belongs to another turn.
    if not matches and len(intervals) == 1 and not intervals[0][2]:
        matches = [intervals[0][:2]]
    if len(matches) != 1:
        return None
    first, last = matches[0]
    current = [n for n, _, _ in session.contexts if first <= n <= last]
    start = current[0] if current else first
    if not any(n <= start for n, _, _ in session.contexts):
        return None
    return session.model(start, last)


def role_evidence(case, catalog):
    data = case.data
    conflicts = []
    host = data["host"]
    if host not in ("codex", "cursor", "claude-code"):
        conflicts.append("historical host unavailable")
    roles = {}

    def add(key, model, effort):
        if not model or model.startswith("manual:"):
            conflicts.append(f"{key} historical model unavailable for headless comparison")
        roles[key] = dict(model=model, effort=effort)

    recorded, observed = known(data["recorded_model"]), known(data["host_model"])
    if recorded and observed and recorded != observed:
        conflicts.append("parent model conflicts with the trace")
    add("parent", known(data["model"]), known(data["effort"]))
    brief = None
    if case.history.kind == "slice":
        brief, worker = initial_worker(case)
        add("worker", (worker or {}).get("model"), (worker or {}).get("effort"))
    else:
        archive = Archive(case, {})
        for report in data["review"]["reports"]:
            key, model = report["key"], known(report["model"])
            effort = None
            observed = reviewer_interval(case, catalog, report, archive)
            if observed:
                observed_model, effort = observed
                if not observed_model or (model and model != observed_model):
                    conflicts.append(f"{key} historical model conflict")
                model = observed_model or model
            if not known(report["session"]):
                conflicts.append(f"{key} historical reviewer session unavailable")
            add(key, model, effort)
    return roles, brief, conflicts
