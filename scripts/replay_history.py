"""Freeze the successfully joined, case-local historical groups separately from new attempts."""
from collections import Counter, defaultdict

from replay_git import sha256
from replay_claims import report_claims
from trace_records import UNKNOWN
from trace_review_evidence import Archive
from trace_review_inputs import first_round_score


def inventory(case, row, scope, population):
    if case.history.kind == "slice":
        case = next((c for c in population if c.id == scope.get("following_case")), None)
        if case is None:
            return dict(review=None, raw_count=None, raw=[], groups=[], unknown=[], confirmation_only=[], evidence_issue=None)
        archive = Archive(case, {})
        score = first_round_score(case, archive, case.data["review"])
    else:
        archive = Archive(case, {})
        score = row["score"]
    review = case.data["review"]
    refs = defaultdict(list)
    evidence = {}
    unknown = []
    closing = (case.end or {}).get("dispositions") or {}
    reviewers = {r.get("key", r["role"]) for r in closing.get("reviewers", [])}
    contributors = {ref.split(":")[0] for d in review["raw_findings"] for ref in d["by"]}
    closed_empty = reviewers - contributors if case.data["outcome"] == "delivered" and type(review["raw_rows"]) is int else set()
    for report in review["reports"]:
        name = report["stem"] + ".md"
        blob = archive.read(name)
        if report["identity"] not in {"recorded", "verified"} or blob is None:
            unknown.append(dict(sources=[report["key"]], reason="first-round report unavailable"))
            continue
        complete, claims = report_claims(blob, report["key"], pinned=bool(review.get("source_findings")),
                                         corroborated_empty=report["key"] in closed_empty)
        if not claims and not complete:
            unknown.append(dict(sources=[report["key"]], reason="unverified empty report"))
        file_digest = sha256(blob)
        for claim in claims:
            ref = report["key"] + ":" + claim["finding"]
            refs[ref].append(name)
            text = claim["text"]
            pins = getattr(case, "adjudication_pins", {}).get(("first", ref), {})
            if file_digest == pins.get("report_sha256"):
                evidence[ref] = dict(source=ref, text=text, sha256=sha256(text.encode()), severity=claim["severity"],
                                     report=name, first_line=claim["first_line"], last_line=claim["last_line"], **pins)
    raw = review["raw_rows"]
    if not review["reports"] or raw == UNKNOWN:
        unknown.append(dict(sources=[], reason="first-round inventory unavailable"))
    for item in score["unverified_sources"]:
        ref = item.get("source") or item.get("key")
        unknown.append(dict(sources=[ref] if ref else [], reason="unverified first-round source"))
    uncertain = {ref for item in unknown for ref in item["sources"]}
    decisions = defaultdict(list)
    for disposition in score["dispositions"]:
        for ref in disposition["by"]:
            decisions[ref].append(disposition["disposition"])
    memberships = Counter(ref for g in review["groups"] for ref in g["sources"])
    groups, known = [], set()
    for g in review["groups"]:
        sources = sorted(g["sources"])
        if (g["disposition"] not in ("accepted", "deferred", "declined") or g["attribution"] == "unverified"
                or not sources or any(s in uncertain or len(refs[s]) != 1 or memberships[s] != 1
                    or decisions[s] != [g["disposition"]] or s not in evidence for s in sources)):
            continue
        groups.append(dict(id=g["group"], disposition=g["disposition"], sources=sources,
                           evidence=[evidence[s] for s in sources]))
        known.update(sources)
    for d in score["dispositions"]:
        remaining = [s for s in d["by"] if s not in known and s not in uncertain]
        if remaining:
            unknown.append(dict(sources=remaining, raw_row=d["raw_row"], disposition=d["disposition"],
                                reason="uncorroborated historical group or disposition"))
    return dict(review=case.history.unit, raw_count=None if raw == UNKNOWN else raw, raw=review["raw_findings"],
                groups=groups, unknown=unknown, confirmation_only=score["confirmation_only"],
                evidence_issue=review.get("evidence_issue"))
