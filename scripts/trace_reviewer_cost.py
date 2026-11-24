"""Charge each participating reviewer session once across independently numbered reports."""
from trace_codex import Catalog
from trace_hosts import UUID
from trace_questions import measurement, token_components
from trace_records import UNKNOWN, loc, stamp


def reviewer_session(catalog, cases, identity):
    if identity == UNKNOWN:
        return None
    if UUID.fullmatch(identity):
        return catalog.session(identity)
    matches = {uid for c in cases for uid, path in catalog.children.get(c.data["conversation"], ()) if path == identity}
    return catalog.session(matches.pop()) if len(matches) == 1 else None


def command_turns(session, case):
    opened, closed = case.history.started, stamp(case.closing.get("at"))
    if not opened or not closed:
        return []
    turns = []
    for i, start in enumerate(session.starts):
        upper = session.starts[i+1].line if i + 1 < len(session.starts) else float("inf")
        terminals = [e.point for e in session.terminals if e.kind != "final" and start.line < e.point.line < upper]
        end = terminals[0] if len(terminals) == 1 else None
        if not start.at or start.at >= closed or (end and end.at and end.at < opened):
            continue
        locations = [loc(session.path, start.line)]
        row = dict(wall_seconds=UNKNOWN, tokens=UNKNOWN, locations=locations)
        if end:
            locations.append(loc(session.path, end.line))
        if end and end.at and opened <= start.at <= end.at < closed:
            cost = session.cost(start.line, end.line)
            locations.extend(cost["locations"])
            row.update(wall_seconds=(end.at - start.at).total_seconds(), tokens=cost["tokens"])
        turns.append(row)
    return turns


def sum_runs(runs):
    wall = [r["wall_seconds"] for r in runs]
    seconds = sum(wall) if wall and all(isinstance(v, (int, float)) for v in wall) else UNKNOWN
    tokens = [r["tokens"] for r in runs]
    totals = UNKNOWN
    if tokens and all(isinstance(v, dict) and v.keys() == tokens[0].keys() for v in tokens):
        totals = {k: sum(v[k] for v in tokens) for k in tokens[0]}
    return dict(wall_seconds=seconds, tokens=totals)


def report_origin(report, archives):
    """A handoff's copied files keep the parent that first registered those bytes and the author."""
    filename = report["stem"] + ".md"
    visible = [c for c in archives if str(c.store / c.history.unit / filename) in report["locations"]]
    if len(visible) != 1 or len(archives) == 1 or not report["session"].startswith("/root/"):
        return visible
    source = visible[0]
    try:
        original = (source.store / source.history.unit / filename).read_bytes()
        for c in reversed(archives):
            end = c.end or {}
            authors = (end.get("dispositions") or {}).get("reviewers", [])
            registered = any(r.get("key", r["role"]) == report["key"] and r["id"] == report["session"]
                             and r["model"] == report["model"] for r in authors)
            if not registered:
                continue
            directory = c.store / c.history.unit
            path, author = directory / filename, directory / (report["stem"] + "-id.txt")
            if end.get("archive") != "ok" or directory.is_symlink() or path.is_symlink() or author.is_symlink():
                return []
            if c is source:
                return [c]
            if not path.is_file() or not author.is_file():
                return []
            if path.read_bytes() == original and author.read_bytes().strip() == report["session"].encode():
                return [c]
    except OSError:
        return []
    return visible


class ReviewerCosts:
    def __init__(self, catalog, homes):
        self.catalog, self.homes = catalog, homes

    def sessions(self, reports, archives):
        sessions = {}
        rollouts = {}
        for r in reports:
            identity = r["session"]
            sources = report_origin(r, archives)
            owners = {c.data["conversation"] for c in sources}
            owner = next(iter(owners)) if len(owners) == 1 else UNKNOWN
            rollout = None
            if r["identity"] in ("recorded", "verified") and (UUID.fullmatch(identity) or identity.startswith("/root/")):
                if self.catalog is None:
                    self.catalog = Catalog(self.homes)
                rollout = reviewer_session(self.catalog, sources, identity)
            sid = rollout.session_id if rollout else identity
            parent = owner if sid.startswith("/root/") else None
            unresolved = sid == UNKNOWN or parent == UNKNOWN or r["identity"] not in {"recorded", "verified"}
            key = (sid, parent, r["stem"] if unresolved else None)
            item = sessions.setdefault(key, dict(session=UNKNOWN if unresolved else sid, parent_conversation=parent,
                                                 keys=[], locations=[]))
            item["keys"].append(r["key"])
            item["locations"].extend(r["locations"])
            for source in sources:
                item["locations"].extend([source.end["_location"], str(source.store / source.history.unit / (r["stem"] + ".md"))])
            if rollout:
                rollouts[key] = rollout
        for key, item in sessions.items():
            runs = []
            for c in archives:
                sid = item["session"]
                attempts = [a for a in c.data["worker_attempts"] if sid != UNKNOWN and a["session"] == sid]
                if attempts and key in rollouts:
                    for a in attempts:
                        cost = a["child_cost"]
                        runs.append(dict(cost, locations=[a["dispatch_location"], a["terminal_location"], *cost["locations"]]))
                elif key in rollouts:
                    runs.extend(command_turns(rollouts[key], c))
            item.update(sum_runs(runs), intervals=runs)
            item["locations"] = list(dict.fromkeys([*item["locations"], *(l for r in runs for l in r["locations"])]))
        return list(sessions.values())


def group_costs(cases, role=None):
    sessions = {}
    for c in cases:
        review = c.data["review"]
        roles = {r["key"]: r["role"] for r in review["reports"]}
        for session in review["session_costs"]:
            keys = [k for k in session["keys"] if role is None or roles.get(k) == role]
            if not keys:
                continue
            sid = session["session"]
            parent = session["parent_conversation"]
            if sid == UNKNOWN or (sid.startswith("/root/") and parent == UNKNOWN):
                key = (c.id, tuple(keys))
                sid = UNKNOWN
            else:
                key = (parent, sid) if sid.startswith("/root/") else sid
            item = sessions.setdefault(key, dict(session=sid, cases=[], intervals={}, missing=False))
            item["cases"].append(dict(case=c.id, keys=keys, locations=session["locations"]))
            item["missing"] |= not session["intervals"]
            for run in session["intervals"]:
                item["intervals"][tuple(run["locations"])] = run
    rows = []
    for key, item in sessions.items():
        costs = sum_runs([] if item["missing"] else list(item["intervals"].values()))
        rows.append(dict(session=item["session"], cases=item["cases"], **costs))
    units = len({ref["case"] for row in rows for ref in row["cases"]})
    return dict(sessions=rows, distinct_known_sessions=sum(r["session"] != UNKNOWN for r in rows),
                token_coverage=measurement([(r["cases"], 1 if isinstance(r["tokens"], dict) else None) for r in rows], units),
                wall_seconds=measurement([(r["cases"], r["wall_seconds"]) for r in rows], units),
                tokens=token_components([(r["cases"], r["tokens"]) for r in rows], units))
