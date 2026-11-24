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


class ReviewerCosts:
    def __init__(self, catalog, homes):
        self.catalog, self.homes = catalog, homes

    def sessions(self, reports, archives):
        sessions = {}
        rollouts = {}
        for r in reports:
            identity = r["session"]
            rollout = None
            if r["identity"] in ("recorded", "verified") and (UUID.fullmatch(identity) or identity.startswith("/root/")):
                if self.catalog is None:
                    self.catalog = Catalog(self.homes)
                rollout = reviewer_session(self.catalog, archives, identity)
            sid = rollout.session_id if rollout else identity
            key = (sid, r["stem"] if sid == UNKNOWN else None)
            item = sessions.setdefault(key, dict(session=sid, keys=[], locations=[]))
            item["keys"].append(r["key"])
            item["locations"].extend(r["locations"])
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


def group_costs(cases):
    sessions = {}
    for c in cases:
        for session in c.data["review"]["session_costs"]:
            sid = session["session"]
            key = sid if sid != UNKNOWN else (c.id, tuple(session["keys"]))
            item = sessions.setdefault(key, dict(cases=[], intervals={}, missing=False))
            item["cases"].append(dict(case=c.id, keys=session["keys"], locations=session["locations"]))
            item["missing"] |= not session["intervals"]
            for run in session["intervals"]:
                item["intervals"][tuple(run["locations"])] = run
    rows = []
    for key, item in sessions.items():
        costs = sum_runs([] if item["missing"] else list(item["intervals"].values()))
        rows.append(dict(session=key if isinstance(key, str) else UNKNOWN, cases=item["cases"], **costs))
    return dict(sessions=rows, distinct_known_sessions=sum(r["session"] != UNKNOWN for r in rows),
                token_coverage=measurement([(r["cases"], 1 if isinstance(r["tokens"], dict) else None) for r in rows]),
                wall_seconds=measurement([(r["cases"], r["wall_seconds"]) for r in rows]),
                tokens=token_components([(r["cases"], r["tokens"]) for r in rows]))
