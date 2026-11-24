"""Link attempts to an actual host child and compare its own terminal event to the owning span."""
from collections import defaultdict
from datetime import timedelta
import re
import shlex

from trace_codex import CodexSession, worker_status
from trace_hosts import CursorSession, parts, records, shell_lines
from trace_records import UNKNOWN, git_bytes, loc, stamp


def empty_attempt(mode, location):
    return dict(mode=mode, session=UNKNOWN, dispatch_location=location, receipt_location=UNKNOWN,
                final_location=UNKNOWN, terminal_location=UNKNOWN, report_status=UNKNOWN, terminal=UNKNOWN,
                containment=UNKNOWN, child_cost={"wall_seconds": UNKNOWN, "tokens": UNKNOWN, "locations": []})


def slice_tag(case):
    plans = [d.partition("@")[0] for d in case.data["docs"] if re.fullmatch(r"P\d{3,}@r\d+", d)]
    return f"{plans[0]}/{case.start['slice']}" if len(plans) == 1 and case.history.kind == "slice" else None


def stored_worker(case):
    tag = slice_tag(case)
    if tag:
        p, sid = tag.split("/")
        path = case.project / ".canon/canon-implement" / p / (sid + "-id.txt")
        try:
            text = path.read_text().strip()
        except (OSError, UnicodeError):
            return None
        if re.fullmatch(r"(?:/root/)?[A-Za-z0-9_./-]{1,200}", text):
            return text, str(path)


def dispatch_links(session, catalog):
    children = catalog.children.get(session.session_id, [])
    output = []
    for d in session.dispatches.values():
        candidates = {uid for uid, path in children if d.target == uid or d.target == path or
                      path.rsplit("/", 1)[-1] == d.target}
        ids = set()
        receipt = None
        if len(d.receipts) == 1:
            receipt, ids, body = d.receipts[0]
            if d.verb == "spawn_agent" and not ids and d.target not in body:
                receipt = None
        matches = ids.intersection(uid for uid, _ in children) if ids else candidates
        contradicted = bool(candidates and ids and matches != candidates)
        if contradicted:
            matches = set()
        uid = next(iter(matches)) if len(matches) == 1 and receipt else None
        # A returned ID still locates the attempted child if its rollout was lost.
        returned = next(iter(ids)) if len(ids) == 1 and receipt and not contradicted else None
        output.append((d, uid, returned))
    return output


def codex_position(case, point):
    """Within, outside or unresolved at the recorded precision of a boundary."""
    first, last = case.host_span
    opening, closing = case.history.started, stamp(case.closing.get("at"))
    if not point.at or not opening:
        return UNKNOWN
    if point.at < opening or (first and point.line <= first):
        return "outside"
    if point.at < opening + timedelta(seconds=1) and not first:
        return UNKNOWN
    if last and point.line >= last:
        return "outside"
    if not closing:
        return UNKNOWN
    if point.at >= closing + timedelta(seconds=1):
        return "outside"
    if point.at >= closing and not last:
        return UNKNOWN
    return "within"


def relative_completion(case, point):
    closing = stamp(case.closing.get("at"))
    if not closing or not point.at:
        return UNKNOWN
    if point.at >= closing + timedelta(seconds=1):
        return "outside"
    if point.at >= closing or (case.history.kind == "slice" and not case.data["commit"]):
        return UNKNOWN
    return "contained"


def codex_attempt(case, session, d, child, next_at, place, returned):
    row = empty_attempt("launch" if d.verb == "spawn_agent" else "resume", loc(session.path, d.point.line))
    if len(d.receipts) == 1:
        row["receipt_location"] = loc(session.path, d.receipts[0][0].line)
    row.update(dispatched=d.point.at.isoformat() if d.point.at else UNKNOWN,
               session=child.session_id if child else returned or UNKNOWN)
    if not child or not d.point.at:
        return row
    def in_turn(p):
        return p.at and d.point.at <= p.at and (next_at is None or p.at < next_at)
    turns = [p for p in child.starts if in_turn(p)]
    terminal = [e for e in child.terminals if in_turn(e.point) and e.kind != "final"]
    finals = [e for e in child.terminals if in_turn(e.point) and e.kind == "final"]
    if len(terminal) != 1 or len(turns) > 1 or len(finals) > 1:
        return row
    t = terminal[0]
    row.update(terminal_location=loc(child.path, t.point.line), completed=t.point.at.isoformat())
    if turns and turns[0].line >= t.point.line:
        return row
    if t.kind in {"turn_aborted", "task_aborted", "task_failed"}:
        if finals:
            return row
        row.update(terminal="stopped", report_status="missing")
    elif finals:
        f = finals[0]
        row["final_location"] = loc(child.path, f.point.line)
        if not f.body or f.point.line >= t.point.line or f.point.at > t.point.at or (
                t.body and f.body != t.body) or (turns and turns[0].line > f.point.line):
            return row
        # A delayed notification never moves the child's completion. A contrary
        # delivered body is still conflicting evidence from the same attempt.
        names = {child.session_id, d.target, "/root/" + d.target}
        notices = [body for p, author, body in session.notices if author in names and in_turn(p)]
        if notices and f.body not in notices:
            return row
        row.update(terminal="completed", report_status=f.status)
    else:
        return row
    row["containment"] = "outside" if place == "outside" else (
        relative_completion(case, t.point) if place == "within" else UNKNOWN)
    if row["containment"] == "contained":
        seconds = (t.point.at - d.point.at).total_seconds()
        if turns:
            start_line = turns[0].line
        else:
            earlier = [p.line for p in child.times if p.at <= d.point.at]
            start_line = earlier[-1] if earlier else None
        row["child_cost"] = {"wall_seconds": seconds, **child.cost(start_line, t.point.line)}
        if start_line:
            model, effort = child.model(start_line, t.point.line)
            row.update(model=model or UNKNOWN, effort=effort or UNKNOWN)
    return row


def codex_workers(cases, catalog):
    grouped = defaultdict(list)
    for c in cases:
        if isinstance(c.host_session, CodexSession):
            grouped[c.host_session].append(c)
    for session, group in grouped.items():
        links = dispatch_links(session, catalog)
        next_start = {}
        for d, uid, returned in reversed(links):
            name = uid or returned or d.target
            next_start[d.point.line] = next_start.get(name)
            next_start[name] = d.point.at
        for case in group:
            tag = slice_tag(case)
            stored = stored_worker(case)
            attempts = case.data["worker_attempts"]
            launches, uncertain = set(), False
            first, last = case.host_span
            if case.data["commit"]:
                case.data["host_end"] = {"source": "git", "location": case.data["end_location"]}
                cutoff = stamp(case.closing["at"])
                earlier = [p.line for p in session.times if p.at < cutoff]
                same = [p for p in session.times if cutoff <= p.at < cutoff + timedelta(seconds=1)]
                if first and earlier and not any(n == p.line for n, _ in session.tokens for p in same):
                    case.data["parent_cost"].update(session.cost(first, earlier[-1]))
            for d, uid, returned in links:
                place = codex_position(case, d.point)
                named = bool(tag and (d.tag == tag or stored and stored[0] in (uid, returned, d.target)))
                # Out-of-span dispatches can only be assigned if there is one matching unit of this slice.
                if place != "within" and not (named and sum(slice_tag(c) == tag for c in group) == 1):
                    continue
                if d.verb == "spawn_agent" and place == "within":
                    if uid or returned:
                        launches.add(uid or returned)
                    else:
                        uncertain = True
                child = catalog.session(uid) if uid else None
                row = codex_attempt(case, session, d, child, next_start[d.point.line], place, returned)
                if stored and stored[0] in (uid, returned, d.target):
                    row["stored_dispatch_location"] = stored[1]
                attempts.append(row)
            linked = {uid or returned for _, uid, returned in links}
            for uid, _ in catalog.children.get(session.session_id, []):
                if uid in linked:
                    continue
                entries = catalog.entries.get(uid, [])
                if len(entries) != 1:
                    continue
                path, meta = entries[0]
                born = stamp(meta.get("timestamp")) or stamp(meta.get("_at"))
                opening, closing = case.history.started, stamp(case.closing.get("at"))
                if not born or not opening or not (opening <= born and (not closing or born < closing + timedelta(seconds=1))):
                    continue
                uncertain = True
                a = empty_attempt(UNKNOWN, UNKNOWN)
                a.update(session=uid, child_location=loc(path, 1))
                attempts.append(a)
            if (first and (last or case.data["commit"]) and not uncertain and
                not any(first < n < (last or float("inf")) for n in session.holes)):
                case.data["fresh_subagents"] = len(launches)


def commit_line(case, session):
    oid = case.data["commit"]
    if not oid:
        return None
    subject = git_bytes(case.project, "show", "-s", "--no-show-signature", "--format=%s", oid)
    if not subject:
        return None
    subject = subject.decode(errors="replace").strip()
    found = []
    for n, command in session.shells:
        if subject not in command or not re.search(r"(?:^|[;&|\n])\s*git\s+commit\b", command):
            continue
        heredoc_match = any(
            body and body[0].strip() == subject and
            re.search(r"(?:^|[;&|])\s*git\s+commit\b[^;&|]*\s(?:-F|--file)\s+-\s+<<", header)
            for header, body in shell_lines(command))
        if heredoc_match:
            found.append(n)
            continue
        lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|()")
        lexer.whitespace_split = True
        try:
            words = list(lexer)
        except ValueError:
            continue
        if any(w in {"-m", "--message"} and i + 1 < len(words) and
               words[i + 1].splitlines()[:1] == [subject] for i, w in enumerate(words)):
            found.append(n)
    return found[0] if len(found) == 1 else None


def cursor_children(session):
    openings = {}
    for path in (session.path.parent / "subagents").glob("*.jsonl"):
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", path.stem):
            continue
        try:
            it = records(path)
            _, first = next(it)
            it.close()
        except (OSError, StopIteration):
            continue
        openings[path] = "\n".join(p["text"] for p in parts(first) if isinstance(p.get("text"), str))
    return openings


def cursor_turns(path):
    turns, final = [], None
    try:
        for n, row in records(path):
            if row.get("role") == "assistant":
                text = "\n".join(p["text"] for p in parts(row) if p.get("type") == "text" and isinstance(p.get("text"), str))
                final = (n, worker_status(text)) if text.strip() else None
            elif row.get("type") == "turn_ended":
                state = row.get("status")
                if state == "success" and final:
                    turns.append((n, "completed", final))
                elif state in {"cancelled", "canceled", "failed", "aborted", "interrupted", "error"} and not final:
                    turns.append((n, "stopped", None))
                else:
                    turns.append(None)
                final = None
            elif row.get("role") == "user":
                final = None
    except OSError:
        return []
    return turns


def cursor_workers(cases):
    grouped = defaultdict(list)
    for c in cases:
        if isinstance(c.host_session, CursorSession):
            grouped[c.host_session].append(c)
    for session, group in grouped.items():
        openings = cursor_children(session)
        links, seen, turns = [], defaultdict(int), {}
        for n, args in session.dispatches:
            resume = args.get("resume")
            prompt = args.get("prompt")
            candidates = [p for p, text in openings.items() if (p.stem == resume if resume else
                          isinstance(prompt, str) and prompt and prompt in text)]
            child = candidates[0] if len(candidates) == 1 else None
            ordinal = seen[child]
            if child:
                seen[child] += 1
                if child not in turns:
                    turns[child] = cursor_turns(child)
            links.append((n, args, child, ordinal))
        starts = {c.history.unit: c.host_span[0] for c in group}
        ends = {c.history.unit: c.host_span[1] for c in group}
        for case in group:
            first, last = case.host_span
            if case.data["commit"]:
                last = commit_line(case, session)
                case.data["host_end"] = ({"source": "export", "location": loc(session.path, last),
                                          "commit_location": case.data["end_location"]} if last else
                                         {"source": "git", "location": case.data["end_location"]})
            elif case.history.kind == "slice" and case.closing:
                boundary = case.closing
                last = (starts if boundary["type"] == "start" else ends).get(boundary["id"])
            case.host_span = first, last
            if not first or not last or first >= last:
                continue
            launched, uncertain = set(), False
            for line, args, child, ordinal in links:
                inside = first < line < last
                sid = slice_tag(case)
                named = sid and re.search(r"\b" + sid.replace("/", r"[\s_:/-]+") + r"\b", str(args.get("description", "")), re.I)
                if not inside and not (named and sum(slice_tag(c) == sid for c in group) == 1):
                    continue
                mode = "resume" if args.get("resume") else "launch"
                a = empty_attempt(mode, loc(session.path, line))
                case.data["worker_attempts"].append(a)
                if not child:
                    uncertain = uncertain or (inside and mode == "launch")
                    continue
                a["session"] = child.stem
                a["child_location"] = loc(child, 1)
                if inside and mode == "launch":
                    launched.add(child.stem)
                evidence = turns[child]
                if ordinal >= len(evidence) or len(evidence) != seen[child] or not evidence[ordinal]:
                    continue
                n, terminal, final = evidence[ordinal]
                a.update(terminal=terminal, terminal_location=loc(child, n), report_status=final[1] if final else "missing")
                if final:
                    a["final_location"] = loc(child, final[0])
                if not inside:
                    a["containment"] = "outside"
                elif args.get("run_in_background") is False and (case.history.kind != "slice" or case.data["commit"]):
                    a["containment"] = "contained"
            if not uncertain:
                case.data["fresh_subagents"] = len(launched)
