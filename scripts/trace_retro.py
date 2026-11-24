"""Offline retro records, preserving note locations without their prose."""
from collections import Counter
import re

from trace_questions import case_ref, ratio
from trace_hosts import CursorSession, observed_lines
from trace_records import canon, git_bytes, loc, snapshot_index, stamp, UNKNOWN

STATE = r"(?:noted|raised|declined|later C\d{3,}|applied [0-9a-fA-F]{4,64})"
HEADING = re.compile(r"^## ([a-z0-9]+(?:-[a-z0-9]+)*): (" + STATE + r")\s*$")
ENTRY = re.compile(r"^- (\d{4}-\d\d-\d\d) (\S+): (.+)$")


def read_notes(project):
    path = project / ".canon/canon-retro/notes.md"
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        return []
    causes = []
    cause = None
    for n, line in enumerate(lines, 1):
        if line.startswith("## "):
            heading = HEADING.fullmatch(line)
            cause = None
            if heading:
                cause = dict(cause=heading[1], state=heading[2], location=loc(path, n), states=[], events=[])
                causes.append(cause)
            elif re.match(r"^## .+?:\s*applied\b", line, re.I):
                causes.append(dict(state="applied", location=loc(path, n), states=[]))
            continue
        entry = ENTRY.fullmatch(line)
        if not cause or not entry:
            continue
        state = re.fullmatch(r"set (" + STATE + ")", entry[3])
        if state:
            cause["states"].append(dict(state=state[1], location=loc(path, n)))
        else:
            cause["events"].append((entry[2], entry[3], loc(path, n)))
    return causes


def end_checks(cases, notes, all_cases):
    index = {(c.store, c.history.unit): c for c in all_cases}
    eligible = {c.id for c in cases if not c.start.get("parent") and c.end}
    outside = []
    roots = [case_ref(c, c.end["_location"]) for c in cases if not c.start.get("parent") and c.end]
    checks, raised, unknown = [], [], []
    for c in cases:
        if c.history.kind != "end-check":
            continue
        cost = c.data["parent_cost"]
        ref = case_ref(c, c.data["end_location"], *cost["locations"])
        checks.append(dict(ref, wall_seconds=c.data["wall_seconds"], tokens=cost["tokens"], outcome=c.data["outcome"]))
        if c.data["outcome"] == "raised":
            root, seen = c, set()
            while root and root.start.get("parent") and root.id not in seen:
                seen.add(root.id)
                root = index.get((root.store, root.start["parent"]))
            if root and root.id in eligible:
                raised.append(dict(ref, root=root.id))
            else:
                target = outside if root and not root.start.get("parent") else unknown
                target.append(dict(ref, root=root.id if target is outside else UNKNOWN))
        elif c.data["outcome"] != "quiet":
            unknown.append(ref)
    declined = []
    for project, causes in notes.items():
        for cause in causes:
            records = [s for s in cause["states"] if s["state"] == "declined"]
            for r in records or ([cause] if cause["state"] == "declined" else []):
                declined.append(dict(project=str(project), cause=cause["cause"], location=r["location"]))
    return dict(title="End-check cost and interruptions", checks=checks, declined=declined,
                interruptions=dict(ratio(len(raised), len(roots), raised, len(roots)),
                                   eligible_cases=roots, unknown_cases=unknown, outside_eligible_cases=outside))


def commit_patch(project, short):
    record = git_bytes(project, "show", "-s", "--no-notes", "--no-show-signature", "--format=%H %cI %P", short + "^{commit}")
    if not record:
        return short, None, None
    oid, when, *parents = record.decode("ascii").split()
    if not oid.startswith(short.lower()):
        return short, None, None
    patch = None
    if len(parents) <= 1:
        patch = git_bytes(project, "diff-tree", "--root", "--no-commit-id", "-p", "--binary", "--full-index",
                          "--no-renames", "--no-textconv", "--no-ext-diff", oid)
    return oid, stamp(when), patch


def patch_state(store, snapshot, patch):
    if not canon.full_oid(snapshot) or not patch:
        return UNKNOWN
    with snapshot_index(store, snapshot + "^{commit}") as env:
        if env is None:
            return UNKNOWN
        def applies(direction):
            return git_bytes(store, "apply", "--cached", "--check", *direction, "--whitespace=nowarn", "-",
                             data=patch, environment=env) is not None
        reverse, forward = applies(["-R"]), applies([])
        if reverse == forward:
            return UNKNOWN
        return "present" if reverse else "absent"


def fix_events(cause, oid, units, eligible):
    observed, outside, unmatched = [], [], []
    for session, detail, location in cause["events"]:
        flags = re.findall(r"\bfix=(present|absent|unverified)\b", detail)
        refs = re.findall(r"(?<![\w-])([0-9a-fA-F]{4,64})(?![\w-])", detail)
        if flags != ["present"] or not any(oid.lower().startswith(ref.lower()) for ref in refs):
            continue
        if re.fullmatch(r"\d{8}-\d{4}", session):
            anchors = [c for c in units if c.history.kind in {"retro", "end-check"} and c.history.started and
                       c.history.started.strftime("%Y%m%d-%H%M") == session]
            # A minute shared by different conversations cannot identify one session.
            identities = {c.data["conversation"] if c.data["conversation"] != UNKNOWN else c.id for c in anchors}
            if len(identities) != 1:
                anchors = []
        else:
            anchors = [c for c in units if session != UNKNOWN and c.data["conversation"] == session]
        sessions = {c.data["conversation"] for c in anchors} - {UNKNOWN}
        exposed = [c for c in eligible if c in anchors or c.data["conversation"] in sessions]
        row = dict(location=location, anchors=[case_ref(c) for c in anchors], eligible_cases=[case_ref(c) for c in exposed])
        (observed if exposed else outside if anchors else unmatched).append(row)
    return observed, outside, unmatched


def repeated_commands(case):
    session = case.host_session
    calls = session.shells if isinstance(session, CursorSession) else getattr(session, "commands", [])
    lines, complete = observed_lines(case, [n for n, _ in calls])
    gaps, gaps_covered = observed_lines(case, getattr(session, "undecoded", []))
    selected = set(lines)
    entries = [(n, command) for n, command in calls if n in selected]
    counts = Counter(command for _, command in entries)
    places = [loc(session.path, n) for n, command in entries if counts[command] > 1]
    return dict(case=case.id, count=sum(n - 1 for n in counts.values()) if complete and gaps_covered and not gaps else UNKNOWN,
                observed_repetitions=sum(n - 1 for n in counts.values()), undecoded_locations=[loc(session.path, n) for n in gaps],
                locations=places, boundaries=[case.data["host_start"]["location"], case.data["host_end"]["location"]])


def retro_fixes(cases, notes):
    fixes, unknown_fixes = [], []
    states = {}
    for project, causes in notes.items():
        units = [c for c in cases if c.project == project]
        for cause in causes:
            if cause["state"] == "applied":
                unknown_fixes.append(dict(reason="applied fix has no commit", location=cause["location"]))
                continue
            by_fix = {}
            for r in [*cause["states"], cause]:
                if r["state"].startswith("applied "):
                    short = r["state"].split()[1]
                    oid, when, patch = commit_patch(project, short)
                    if oid not in by_fix:
                        by_fix[oid] = (when, patch, [])
                    by_fix[oid][2].append(r["location"])
            for oid, (when, patch, locations) in by_fix.items():
                eligible, unknown, absent, before, after = [], [], [], [], []
                for c in units:
                    ref = case_ref(c)
                    if not when or not c.history.started or c.history.started == when:
                        unknown.append(ref)
                    elif c.history.started < when:
                        before.append(c)
                    else:
                        snapshot = c.start.get("snapshot")
                        key = (project, oid, c.store, snapshot)
                        if key not in states:
                            states[key] = patch_state(c.store, snapshot, patch)
                        ref = case_ref(c, f"{c.store}@{snapshot}") if canon.full_oid(snapshot) else ref
                        {"present": eligible, "absent": absent, UNKNOWN: unknown}[states[key]].append(ref)
                        if states[key] == "present":
                            after.append(c)
                events, outside, unmatched = fix_events(cause, oid, units, after)
                fixes.append(dict(project=str(project), cause=cause["cause"], commit=oid,
                                  locations=[*locations, f"{project}@{oid}"], absent_cases=absent,
                                  recurrences=dict(ratio(len(events), len(eligible), events, len(eligible)),
                                                   eligible_cases=eligible, unknown_cases=unknown),
                                  repeated_commands=dict(before=[repeated_commands(c) for c in before],
                                                         after=[repeated_commands(c) for c in after]),
                                  outside_eligible_events=outside, unmatched_events=unmatched))
    return dict(title="Retro fix recurrences", fixes=fixes, unknown_fixes=unknown_fixes)
