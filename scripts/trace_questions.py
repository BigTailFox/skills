"""Comparable populations and coverage of offline trace measurements."""
from collections import defaultdict
from statistics import median
from pathlib import Path
import os
import re

from trace_records import UNKNOWN, canon, git_bytes


def comparison(case):
    d = case.data
    skill = (case.start.get("skill") or "").rstrip("/").rsplit("/", 1)[-1]
    manifest = case.manifests.get(case.start.get("manifest"), {})
    skill_digest = manifest.get("skills", {}).get(skill) or UNKNOWN
    d["skill_digest"] = skill_digest
    return (d["kind"], d["effective_tier"], d["host"], d["model"], skill_digest)


def by_comparison(cases):
    groups = defaultdict(list)
    for case in cases:
        fields = comparison(case)
        # Unknown model or version cannot establish comparability with a second case.
        groups[(fields, case.id if UNKNOWN in fields else None)].append(case)
    for (fields, _), members in groups.items():
        yield dict(zip(("kind", "tier", "host", "model", "skill_digest"), fields)), members


def measurement(rows):
    measured = [(c, v) for c, v in rows if isinstance(v, (int, float))]
    unknown = [c for c, v in rows if not isinstance(v, (int, float))]
    values = [v for _, v in measured]
    return dict(known=len(values), unknown=len(unknown), numerator=len(values), denominator=len(rows),
                total=sum(values) if values else UNKNOWN, median=median(values) if values else UNKNOWN,
                known_cases=[c for c, _ in measured], unknown_cases=unknown,
                sample="few units" if len(rows) < 20 else "20 or more units")


def token_components(rows):
    names = sorted({name for _, tokens in rows if isinstance(tokens, dict) for name in tokens})
    return {name: measurement([(case, tokens.get(name) if isinstance(tokens, dict) else None)
                               for case, tokens in rows]) for name in names}


def costs(cases):
    result = []
    for key, group in by_comparison(cases):
        rows = [c.data for c in group]
        parent_tokens = [(r["case"], r["parent_cost"]["tokens"]) for r in rows]
        attempts = [(r["case"] + " @ " + (a["dispatch_location"] if a["dispatch_location"] != UNKNOWN else
                     a.get("child_location", UNKNOWN)), a) for r in rows for a in r["worker_attempts"]]
        intervals, children = {}, defaultdict(list)
        for state in ("contained", "outside", UNKNOWN):
            matched = [label for label, a in attempts if a["containment"] == state]
            intervals[state] = dict(numerator=len(matched), denominator=len(attempts), cases=matched,
                                    sample="few units" if len(rows) < 20 else "20 or more units")
        for label, a in attempts:
            children[(a["session"], a.get("model", UNKNOWN))].append((label, a["child_cost"]))
        child_costs = [dict(session=session, model=model,
                            wall_seconds=measurement([(label, cost["wall_seconds"]) for label, cost in runs]),
                            tokens=token_components([(label, cost["tokens"]) for label, cost in runs]))
                       for (session, model), runs in children.items()]
        result.append(dict(**key, cases=[r["case"] for r in rows], count=len(rows),
                           wall_seconds=measurement([(r["case"], r["wall_seconds"]) for r in rows]),
                           fresh_subagents=measurement([(r["case"], r["fresh_subagents"]) for r in rows]),
                           tokens=measurement([(case, 1 if isinstance(tokens, dict) else None)
                                               for case, tokens in parent_tokens]),
                           token_components=token_components(parent_tokens),
                           worker_intervals=intervals, child_costs=child_costs))
    return dict(title="Wall time, subagents and tokens", groups=result)


def slice_plan(case, root, tree, target):
    """Locate the slice by document ID and revision, including renamed and archived plans."""
    pid, revision = target.split("@r")
    if tree:
        if not canon.full_oid(tree):
            return None
        files = git_bytes(root, "ls-tree", "-r", "-z", "--name-only", tree)
    elif (root / ".git").exists():
        files = git_bytes(root, "ls-files", "-z", "--cached", "--others", "--exclude-standard")
    else:
        names = []
        for directory, subdirs, entries in os.walk(root):
            subdirs[:] = [d for d in subdirs if not d.startswith(".")]
            names.extend(os.fsencode((Path(directory) / name).relative_to(root)) for name in entries
                         if name.startswith(pid + "-") and name.endswith(".md"))
        files = b"\0".join(names)
    if files is None:
        return None
    paths = []
    for raw in files.split(b"\0"):
        p = Path(os.fsdecode(raw))
        if (p.name.startswith(pid + "-") and canon.FILE_RE.fullmatch(p.name) and
            (p.parts[-3:-1] == ("docs", "plans") or p.parts[-4:-1] == ("docs", "archived", "plans"))):
            paths.append(p)
    if len(paths) != 1:
        return None
    path = paths[0]
    try:
        data = git_bytes(root, "show", tree + ":" + path.as_posix()) if tree else (root / path).read_bytes()
        if data is None:
            return None
        doc = canon.Doc(None, root / path, path.as_posix(), canon.FILE_RE.fullmatch(path.name), False, data.decode())
    except (OSError, UnicodeError):
        return None
    if str(doc.revision) != revision:
        return None
    section = doc.section_span("Slices")
    if not section:
        return None
    heading = doc.headings[section[0]]
    markers = [h for h in doc.headings if heading.line < h.line < section[1] and h.level == 3]
    sid = case.start["slice"]
    matches = [h for h in markers if re.match(re.escape(sid) + r"\b", h.text)]
    if len(matches) != 1:
        return None
    opening = matches[0].line
    closing = next((h.line for h in markers if h.line > opening), section[1])
    address = f"{root}@{tree}:{path}" if tree else str(root / path)
    found = dict(status=UNKNOWN, risk="absent", location=f"{address}#L{opening + 1}")
    for idx, line in canon.code_mask(doc.lines[opening + 1:closing]):
        value = line.strip().strip("*")
        match = canon.STATUS_LINE_RE.match(value.replace("*", ""))
        if match and match[1] in canon.SLICE_STATUSES:
            found["status"] = match[1]
            found["status_location"] = f"{address}#L{opening + idx + 2}"
        if re.match(r"^(?:-\s+)?Risk:\s*\S", value, re.I):
            found["risk"] = "present"
            found["risk_location"] = f"{address}#L{opening + idx + 2}"
    log = doc.section_span("Log")
    if log:
        pos = doc.headings[log[0]].line + 1
        for offset, text in enumerate(doc.lines[pos:log[1]]):
            if re.search(r"\b" + re.escape(sid) + r"\b", text) and re.search(r"\bpaus(?:e|ed)\b", text, re.I):
                found["pause_log"] = f"{address}#L{pos + offset + 1}"
    return found


def pause_stash(case, plan):
    rows = git_bytes(case.project, "stash", "list", "--format=%H%x09%gs")
    if not rows:
        return []
    tag = re.escape(plan.partition("@")[0]) + r"\s+" + re.escape(case.start["slice"])
    found = []
    for line in rows.decode(errors="replace").splitlines():
        oid, _, subject = line.partition("\t")
        if re.search(r"^(?:On [^:]+:\s*)?" + tag + r"\b", subject):
            found.append(f"{case.project}@{oid}")
    return found


def slice_evidence(case, plan):
    commit = case.data["commit"]
    closed = slice_plan(case, case.project, commit, plan) if commit else None
    opening = None
    for root, oid in ((case.store, case.start.get("snapshot")), (case.project, case.start.get("head"))):
        if oid:
            opening = slice_plan(case, root, oid, plan)
            if opening:
                break
    current = None if closed else slice_plan(case, case.project, None, plan)
    document = opening or closed or current or {}
    evidence = [case.data["start_location"]]
    for item in (opening, closed, current):
        if item:
            evidence.extend(item[k] for k in ("location", "risk_location", "status_location") if k in item)
    status = (closed or {}).get("status", UNKNOWN)
    if not closed and current and current["status"] == "paused" and current.get("pause_log"):
        stash = pause_stash(case, plan)
        evidence.append(current["pause_log"])
        evidence.extend(stash)
        if stash:
            status = "paused"
    return document.get("risk", UNKNOWN), status, list(dict.fromkeys(evidence))


def slice_outcomes(cases):
    grouped = defaultdict(list)
    for case in cases:
        if case.history.kind != "slice":
            continue
        plans = [d for d in case.data["docs"] if re.fullmatch(r"P\d{3,}@r\d+", d)]
        plan = plans[0] if len(plans) == 1 else UNKNOWN
        key = (str(canon.main_trace_root(case.project)), plan, case.start["slice"], case.id if plan == UNKNOWN else None)
        grouped[key].append(case)
    slices = []
    for (project, plan, sid, _), units in grouped.items():
        ordered = sorted(units, key=lambda c: (c.history.started is None, c.history.started, c.id))
        risks, reasons, locations, statuses = set(), set(), [], []
        all_done = True
        for case in ordered:
            risk, status, evidence = slice_evidence(case, plan) if plan != UNKNOWN else (UNKNOWN, UNKNOWN, [])
            risks.add(risk)
            statuses.append(status)
            locations.extend(evidence)
            if status == "paused":
                reasons.add("plan paused")
            attempts = case.data["worker_attempts"]
            if not attempts or case.data["fresh_subagents"] == UNKNOWN:
                all_done = False
            for a in attempts:
                locations.extend([a["dispatch_location"], a["terminal_location"]])
                if a["containment"] != "contained":
                    all_done = False
                    continue
                if a["terminal"] == "stopped":
                    reasons.add("host stopped")
                elif a["report_status"] in {"paused", "blocked", "stuck"}:
                    reasons.add("worker " + a["report_status"])
                if a["report_status"] != "done":
                    all_done = False
        stop = "confirmed" if reasons else ("no observed stop" if all_done and statuses[-1] == "done" else UNKNOWN)
        case_ids = [c.id for c in ordered]
        comparables = {comparison(c) for c in ordered}
        kind, tier, host, model, skill_digest = (comparables.pop() if len(comparables) == 1 else
                                                ("slice", UNKNOWN, UNKNOWN, UNKNOWN, UNKNOWN))
        slices.append(dict(project=project, plan=plan, slice=sid, cases=case_ids, risk=risks.pop() if len(risks) == 1 else UNKNOWN,
                           outcome=statuses[-1], stop=stop, reasons=sorted(reasons), tier=tier, host=host,
                           model=model, skill_digest=skill_digest, locations=list(dict.fromkeys(s for s in locations if s != UNKNOWN))))
    cohorts = defaultdict(list)
    for s in slices:
        dims = tuple(s[k] for k in ("risk", "tier", "host", "model", "skill_digest"))
        cohorts[(dims, s["cases"][0] if UNKNOWN in dims else None)].append(s)
    groups = []
    for (dims, _), rows in cohorts.items():
        by_stop = {k: [r["cases"] for r in rows if r["stop"] == k] for k in ("confirmed", "no observed stop", UNKNOWN)}
        groups.append(dict(zip(("risk", "tier", "host", "model", "skill_digest"), dims),
                           stopped=dict(numerator=len(by_stop["confirmed"]), denominator=len(rows),
                                        known=len(rows) - len(by_stop[UNKNOWN]), unknown=len(by_stop[UNKNOWN]),
                                        sample="few units" if len(rows) < 20 else "20 or more units", cases=by_stop)))
    return dict(title="Slice outcomes and recorded risks", denominator=len(slices), slices=slices, groups=groups)
