"""Delivered review contributions and the separately recorded confirmation rounds."""
from collections import Counter
import re

from trace_questions import by_comparison, case_ref, ratio
from trace_records import REVIEW, UNKNOWN
from trace_review_evidence import Archive, ReviewEvidence, VALID, recorded_reports
from trace_reviewer_cost import ReviewerCosts, group_costs


def confirmation(case, number, finding):
    history = case.history
    source = finding["by"][0]

    def recheck(event):
        fields = {k: event[k] for k in ("reviewer", "model", "snapshot", "result", "report", "order")}
        return dict(**fields, location=event["_location"], archive=history.report_status(event["report"]))

    checks = [recheck(e) for e in history.rechecks[source]]
    conflicts = [recheck(e) for e in history.conflicts[source]]
    ordered = sorted((r for r in checks if r["order"] is not None), key=lambda r: r["order"])
    unordered = [r for r in checks if r["order"] is None]
    first = finding.get("confirmed", UNKNOWN)
    latest = ordered[-1]["result"] if ordered else first
    if unordered or any(not ordered or r["order"] is None or r["order"] >= ordered[-1]["order"] for r in conflicts):
        latest = UNKNOWN
    return dict(raw_row=number, by=finding["by"], initial=first, individual=finding.get("confirmations", UNKNOWN),
                location=case.end["_location"], ordered=ordered, unordered=unordered, conflicting=conflicts,
                highest_verified=ordered[-1] if ordered else None, latest=latest)


def describe_review(case):
    end = case.end or {}
    dispositions = end.get("dispositions")
    coverage = case.data["outcome"]
    review = dict(coverage=coverage if coverage == "delivered" else "partial-" + coverage, groups=[],
                  raw_rows=UNKNOWN, raw_findings=[], raw_dispositions=UNKNOWN, confirmations=[], new_blockers=UNKNOWN,
                  valid_first_groups=UNKNOWN)
    if dispositions is not None:
        rows = [dict(raw_row=i, location=end["_location"], **f) for i, f in enumerate(dispositions["findings"], 1)]
        review.update(raw_rows=len(rows), raw_findings=rows, new_blockers=dispositions["new_blockers"],
                      raw_dispositions=dict(Counter(r["disposition"] for r in rows)))
        for i, f in enumerate(rows, 1):
            source = f["by"][0]
            if "confirmed" in f or case.history.rechecks[source] or case.history.conflicts[source]:
                review["confirmations"].append(confirmation(case, i, f))
    return review


def confirmation_question(delivered):
    groups = []
    for key, cases in by_comparison(delivered):
        confirmed, unresolved, rounds, unknown = [], [], [], []
        blockers = 0
        for c in cases:
            review = c.data["review"]
            if review["raw_rows"] == UNKNOWN:
                unknown.append(case_ref(c))
                continue
            for claim in review["confirmations"]:
                if claim["initial"] != UNKNOWN:
                    label = dict(case_ref(c, claim["location"]), raw_row=claim["raw_row"])
                    confirmed.append(label)
                    if claim["initial"] == "not-resolved":
                        unresolved.append(label)
            if (review["confirmation_reports"] or any(f["initial"] != UNKNOWN for f in review["confirmations"])
                or review["new_blockers"]):
                rounds.append(dict(case_ref(c, c.end["_location"], *review["confirmation_reports"]), new_blockers=review["new_blockers"]))
                blockers += review["new_blockers"]
        groups.append(dict(**key, cases=[case_ref(c, c.end["_location"]) for c in cases], unknown=unknown,
                           confirmed=confirmed, initial_not_resolved=ratio(len(unresolved), len(confirmed), unresolved, len(cases)),
                           new_blockers=ratio(blockers, len(rounds), rounds, len(cases))))
    return dict(title="Initial confirmation verdicts and new blockers per round", groups=groups)


def recorded_cross_only(review):
    roles = {r["key"]: r["role"] for r in review["reports"]}
    return [r for r in review["raw_findings"] if r["disposition"] in VALID and r["severity"] in {"blocker", "major"}
            and all(roles.get(claim.partition(":")[0]) == "cross-family" for claim in r["by"])]


def review_rate(items, cases, unknown):
    n = len(items)
    return dict(ratio(UNKNOWN if unknown and not n else n, len(cases), items, len(cases)),
                known_numerator=n, unknown_cases=unknown)


def cross_family_question(delivered):
    groups = []
    for key, cases in by_comparison(delivered):
        actual, uncertain, raw, adjudicated, verified, participating = [], [], [], [], [], []
        unknown_groups, unknown_credit = [], []
        for c in cases:
            review = c.data["review"]
            reports = [r for r in review["reports"] if r["role"] == "cross-family" and r["identity"] in {"recorded", "verified"}]
            if not reports:
                if review["raw_rows"] == UNKNOWN or any(r["role"] in ("cross-family", UNKNOWN) for r in review["reports"]):
                    uncertain.append(case_ref(c, c.end["_location"]))
                continue
            label = case_ref(c, c.end["_location"], *(p for r in reports for p in r["locations"]))
            actual.append(label)
            participating.append(c)
            raw.extend(dict(case_ref(c, r["location"]), raw_row=r["raw_row"]) for r in recorded_cross_only(review))
            if review["valid_first_groups"] == UNKNOWN:
                unknown_groups.append(label)
            uncertain_credit = review["valid_first_groups"] == UNKNOWN or any(
                s["role"] == "cross-family" and s["phase"] == "first" and s["group"] == UNKNOWN and
                s["disposition"] in VALID | {UNKNOWN} for s in review.get("source_findings", []))
            for g in review["groups"]:
                if g["roles"] != ["cross-family"] or g["blocker_or_major"] is False or g["disposition"] not in VALID | {UNKNOWN}:
                    continue
                if g["disposition"] in VALID and g["blocker_or_major"] is True:
                    ref = dict(case_ref(c, *g["locations"]), group=g["group"])
                    adjudicated.append(ref)
                    if g["attribution"] in {"joint", "exclusive"} and review["comparable_scope"]:
                        verified.append(ref)
                        continue
                uncertain_credit = True
            if uncertain_credit:
                unknown_credit.append(label)
        groups.append(dict(**key, cases=actual, unknown_reviews=uncertain,
                           reviewer_cost=group_costs(participating),
                           recorded=ratio(len(raw), len(actual), raw, len(actual)),
                           adjudicated=review_rate(adjudicated, actual, unknown_groups),
                           verified=review_rate(verified, actual, unknown_credit)))
    return dict(title="Cross-family-only valid blocker and major findings per delivered review", groups=groups)


def axis_question(delivered):
    groups = []
    for key, cases in by_comparison([c for c in delivered if c.history.kind == "code-review"]):
        axes = {}
        unknown = [case_ref(c, c.end["_location"]) for c in cases if c.data["review"]["valid_first_groups"] == UNKNOWN]
        raw_unknown = [case_ref(c, c.end["_location"]) for c in cases if c.data["review"]["raw_rows"] == UNKNOWN]
        for axis in ("spec", "standards"):
            buckets = {k: [] for k in ("recorded", "adjudicated", "verified", "joint", "exclusive", "single_source_unknown", "unverified")}
            contested = []
            for c in cases:
                review = c.data["review"]
                for r in review["raw_findings"]:
                    if r["axis"] == axis and r["disposition"] in VALID:
                        buckets["recorded"].append(dict(case_ref(c, r["location"]), raw_row=r["raw_row"]))
                for g in review["groups"]:
                    if axis in g["axes"] and g["disposition"] in VALID:
                        ref = dict(case_ref(c, *g["locations"]), group=g["group"])
                        buckets["adjudicated"].append(ref)
                        category = g["attribution"]
                        buckets[category].append(ref)
                        if category == "unverified":
                            contested.append(ref)
                        else:
                            buckets["verified"].append(ref)
            axes[axis] = {}
            for name, items in buckets.items():
                missing = raw_unknown if name == "recorded" else unknown
                if name in ("verified", "joint", "exclusive", "single_source_unknown"):
                    missing = [*missing, *contested]
                axes[axis][name] = review_rate(items, cases, missing)
        groups.append(dict(**key, cases=[case_ref(c, c.end["_location"]) for c in cases], axes=axes,
                           unknown_attribution=unknown))
    return dict(title="Valid code-review contributions per axis and tier", groups=groups)


def review_questions(cases, all_cases, args, catalog):
    units = {(c.store, c.history.unit): c for c in all_cases}
    evidence = ReviewEvidence(args.review_evidence, all_cases, args.cursor_state_db)
    costs = ReviewerCosts(catalog, args.codex_home)
    reviews = [c for c in cases if c.history.kind in REVIEW]
    for c in reviews:
        review = c.data["review"] = describe_review(c)
        archive = Archive(c, units)
        review.update(attribution="recorded", reports=recorded_reports(c, archive))
        review["confirmation_reports"] = [str(p) for name, p in archive.files.items()
                                          if re.fullmatch(r"[A-Za-z0-9_-]+-confirm(?:-(?:spec|standards)(?:-[0-9]+)?)?\.md", name)]
        review["later_confirmation_reports"] = [str(archive.files[stem + ".md"]) for stem in sorted(archive.later_confirmations)]
        evidence.apply(c, archive, review)
        review["session_costs"] = costs.sessions(review["reports"], archive.cases)
    delivered = [c for c in reviews if c.data["outcome"] == "delivered"]
    return {"1": cross_family_question(delivered), "2": confirmation_question(delivered), "3": axis_question(delivered)}
