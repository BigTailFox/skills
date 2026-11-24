"""Read-only project evidence for the offline report. Locations are one-based."""
from collections import Counter
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import re

# The report ships with the source tree. Borrow the same store discovery, validation,
# history object and offline Git transition lookup as the capture tool.
_spec = importlib.util.spec_from_file_location(
    "canon_trace_source", Path(__file__).resolve().parents[1] / "skills/governance/canon/scripts/canon.py")
canon = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(canon)

UNKNOWN = "unknown"
CAVEAT = "Untraced work is unknown, not absent."
REVIEW = canon.REVIEW_ROLES


def stamp(value):
    return canon.event_time({"at": value})


def loc(path, number):
    return f"{path}#L{number}"


def git_bytes(root, *args):
    if not (root / ".git").exists():
        return None
    try:
        return canon.trace_git(root, canon.trace_env(GIT_NO_LAZY_FETCH="1", GIT_ALLOW_PROTOCOL=""), *args)
    except canon.SnapshotSkip:
        return None


def load_events(store, population):
    """Validate the trace schema before using a record. A bad finding preserves its end."""
    path = store / "events.jsonl"
    try:
        stream = path.open("rb")
    except FileNotFoundError:
        return
    except OSError:
        population["skipped"].append({"reason": "unreadable", "location": str(path)})
        return
    with stream:
        for line, raw in enumerate(stream, 1):
            address = loc(path, line)

            def skip(reason):
                population["skipped"].append({"reason": reason, "location": address})

            try:
                e = json.loads(raw)
                if not isinstance(e, dict) or type(e.get("v")) is not int:
                    raise ValueError()
                if e["v"] != 1 or e.get("type") not in {"start", "end", "manifest", "recheck"}:
                    skip("unsupported")
                    continue
                if e["type"] == "manifest":
                    if not isinstance(e.get("skills"), dict) or not isinstance(e.get("digest"), str):
                        raise ValueError()
                else:
                    if (not canon.UNIT_RE.fullmatch(e["id"]) or e["kind"] not in canon.TRACE_KINDS or
                        any(v is not None and not canon.UNIT_RE.fullmatch(v)
                            for v in (e.get("parent"), e.get("continues"))) or
                        not isinstance(e.get("docs", []), list) or
                        not all(isinstance(d, str) for d in e.get("docs", []))):
                        raise ValueError()
                    if e["kind"] == "slice" and (e["type"] != "start" or not e.get("parent") or
                                                  not canon.SLICE_RE.fullmatch(e.get("slice", ""))):
                        raise ValueError()
                    if e["type"] == "start":
                        if any(not re.fullmatch(r"[CDPREI]\d{3,}[A-Z]?(?:@r\d+)?", d) for d in e.get("docs", [])):
                            raise ValueError()
                        for key in ("skill", "conversation", "model", "head", "base", "snapshot", "manifest"):
                            if e.get(key) is not None and not isinstance(e[key], str):
                                raise ValueError()
                        if e.get("host") not in (None, "cursor", "codex", "claude-code", "other"):
                            e["host"] = None
                            skip("malformed host")
                        if e.get("tier") not in (None, "L0", "L1", "L2"):
                            e["tier"] = None
                            skip("malformed tier")
                    if e["type"] == "end":
                        if e.get("outcome") not in canon.KIND_OUTCOMES.get(e["kind"], canon.OUTCOMES):
                            e["outcome"] = None
                            skip("malformed outcome")
                        archive = e.get("archive")
                        if archive is not None and (not isinstance(archive, str) or not re.fullmatch(
                                r"ok|none|over-2MiB|copy: E[A-Z0-9_]+", archive)):
                            e["archive"] = None
                            skip("malformed archive")
                    if e["type"] == "recheck":
                        canon.check_recheck(e)
                    if e["type"] == "end" and e.get("dispositions") is not None:
                        try:
                            canon.check_dispositions(e["kind"], e["dispositions"], allow_repeated_sources=True)
                        except (canon.TraceError, KeyError, TypeError, ValueError):
                            e["dispositions"] = None
                            skip("malformed dispositions")
                e["_line"] = line
                e["_location"] = address
                e["_sha256"] = hashlib.sha256(raw.rstrip(b"\r\n")).hexdigest()
                yield e
            except (KeyError, ValueError, TypeError, RecursionError, canon.TraceError):
                skip("malformed")


class Case:
    def __init__(self, project, store, start, manifests):
        self.project = project
        self.store = store
        self.start = start
        self.manifests = manifests
        self.history = canon.HistoryUnit(start, store, None)
        self.id = f"{store}::{start['id']}"
        self.data = {}
        self.ambiguous = False
        self.host_session = None
        self.host_span = (None, None)

    @property
    def end(self):
        return self.history.end

    @property
    def closing(self):
        return self.end or self.history.boundary or {}

    def describe(self):
        h, start = self.history, self.start
        ended = self.closing
        measured = bool(h.end or "commit" in ended)
        seconds = h.seconds()
        self.data.update(
            case=self.id, unit=h.unit, project=str(self.project), store=str(self.store), kind=h.kind,
            docs=start.get("docs", []), tier=start.get("tier") or UNKNOWN,
            effective_tier=start.get("tier") or UNKNOWN, parent=start.get("parent"),
            continues=start.get("continues"), continuation=h.continuation,
            host=start.get("host") or UNKNOWN, conversation=start.get("conversation") or UNKNOWN,
            model=start.get("model") or UNKNOWN, effort=UNKNOWN, manifest=start.get("manifest") or UNKNOWN,
            recorded_model=start.get("model") or UNKNOWN, host_model=UNKNOWN,
            model_locations=[start["_location"]] if start.get("model") else [],
            started=start.get("at") if h.started else UNKNOWN,
            ended=ended.get("at") if canon.event_time(ended) else UNKNOWN,
            start_location=start["_location"], end_location=ended.get("_location", UNKNOWN),
            outcome=(h.end.get("outcome") or UNKNOWN) if h.end else (
                "committed" if "commit" in ended else "upper bound" if ended else "open"),
            wall_seconds=seconds if measured and seconds is not None else UNKNOWN,
            upper_bound_seconds=seconds if ended and not measured and seconds is not None else UNKNOWN,
            archive=h.archive_status(), slice=start.get("slice"), commit=ended.get("commit"),
        )


def read_store(project, store, population):
    cases, manifests, slices = {}, {}, {}
    checks = []
    for event in load_events(store, population):
        action = event["type"]
        if action == "manifest":
            manifests[event["digest"]] = event
            continue
        uid = event["id"]
        case = cases.get(uid)
        if action == "recheck":
            checks.append(event)
            continue
        if action == "start" or event["kind"] == "implement":
            sibling = slices.pop(event.get("parent") if action == "start" else uid, None)
            if sibling:
                sibling.history.boundary = event
        if action == "start" and case is None:
            case = cases[uid] = Case(project, store, event, manifests)
            if event["kind"] == "slice":
                slices[event["parent"]] = case
        elif action == "end" and case and case.history.kind == event["kind"] and not case.end:
            case.history.end = event
        else:
            if case and action in ("start", "end"):
                case.ambiguous = True
            population["orphans"].append(dict(unit=uid, type=action, location=event["_location"]))
    for e in checks:
        case = cases.get(e["id"])
        try:
            if not case or e["kind"] != case.history.kind or not (case.end or {}).get("dispositions"):
                raise ValueError()
            source = canon.finding_source(case.end["dispositions"], e["finding"])
            case.history.rechecks[source].append(e)
        except (ValueError, canon.TraceError):
            population["orphans"].append(dict(unit=e["id"], type="recheck", location=e["_location"]))
    for case in cases.values():
        h = case.history
        if h.kind == "slice" and (project / ".git").exists():
            try:
                transition = canon.slice_commit(project, h)
            except (canon.SnapshotSkip, OSError, ValueError, KeyError):
                transition = None
            if transition:
                h.boundary = dict(transition, _location=f"{project}@{transition['commit']}")
        for field in ("parent", "continues"):
            related = case.start.get(field)
            if related and related not in cases:
                population["orphans"].append(dict(unit=h.unit, type=field, related=related,
                                                  location=case.start["_location"]))
        predecessor = cases.get(case.start.get("continues"))
        if predecessor:
            predecessor.history.continuation = h.unit
        issues = Counter()
        h.verify_rechecks(issues)
        for conflicts in h.conflicts.values():
            population["skipped"].extend(dict(reason="conflicting recheck", location=e["_location"]) for e in conflicts)
    for case in cases.values():
        case.describe()
    return list(cases.values())


def collect(projects):
    projects = list(dict.fromkeys(p.resolve() for p in projects))
    population = dict(projects=[str(p) for p in projects], stores=[], skipped=[], orphans=[], open=[], incomplete=[],
                      caveat=CAVEAT)
    stores = set()
    cases = []
    for p in projects:
        for name, trace_dir in canon.history_stores(p):
            store = trace_dir.resolve()
            if store in stores:
                continue
            stores.add(store)
            population["stores"].append(str(store))
            owner = canon.main_trace_root(p) if name == "main" else p
            cases.extend(read_store(owner, store, population))
    return population, cases


def select(cases, since, population):
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    selected = []
    for case in cases:
        h = case.history
        if since and h.started and h.started.astimezone(timezone.utc).date() < since:
            continue
        selected.append(case)
        if not case.closing:
            population["open"].append(case.id)
        if ((not case.closing and h.kind != "slice" and (not h.started or h.started < cutoff))
                or (h.kind in REVIEW and (not case.end or case.end.get("outcome") == "handoff"))):
            population["incomplete"].append(case.id)
    return selected
