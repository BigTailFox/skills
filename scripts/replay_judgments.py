"""Adjudicate claim groups and count only the evidence a blinded comparison establishes."""
from collections import Counter, defaultdict
import re

from replay_packet import opaque
from replay_scoring_inputs import evidence_in, reference_key
from trace_review_evidence import VALID


def rate(numerator, denominator, complete=True):
    return dict(numerator=numerator, denominator=denominator,
                rate=numerator / denominator if denominator and complete else None)


def decided_counts(decisions, prefix, positive, negative):
    yes = sum(v == positive for v in decisions.values())
    no = sum(v == negative for v in decisions.values())
    return {f"{prefix}.{positive}": yes, f"{prefix}.{negative}": no,
            f"{prefix}.{positive}_rate": rate(yes, yes + no)}


def index_rows(rows, key):
    indexed = defaultdict(list)
    for row in rows:
        if isinstance(row, dict) and isinstance(row.get(key), str) and row[key]:
            indexed[row[key]].append(row)
    return indexed


def identifiers(value):
    return isinstance(value, list) and all(isinstance(v, str) and v for v in value)


def blinded_judgments(inputs, judgments):
    if judgments is None:
        return None

    def identifier(value):
        if value is None:
            return None
        if isinstance(value, str) and re.fullmatch("[0-9a-f]{32}", value):
            return value
        return opaque(inputs.journal, "operator identifier", value)

    paths = {ref["path"] for g in inputs.packet["history"]["groups"] for ref in g["evidence"]}
    for attempt in inputs.rows.values():
        paths.update(c["evidence"]["path"] for c in attempt["claims"] + attempt["tests"])
        if attempt["artifact"]:
            paths.add(attempt["artifact"]["path"])

    def evidence(refs):
        result = []
        for ref in refs if isinstance(refs, list) else []:
            key = reference_key(ref)
            if key and key[0] in paths and re.fullmatch("[0-9a-f]{64}", key[1]):
                result.append(dict(path=key[0], sha256=key[1]))
        return result

    def rows(value):
        return [r for r in value if isinstance(r, dict)] if isinstance(value, list) else []

    attempts = []
    for row in rows(judgments.get("attempts")):
        groups = [dict(id=identifier(g.get("id")), historical=identifier(g.get("historical")),
                       claims=[identifier(c) for c in g["claims"]] if isinstance(g.get("claims"), list) else [],
                       verdict=g["verdict"] if g.get("verdict") in ("valid", "false_positive") else "unknown",
                       scope=g["scope"] if g.get("scope") in ("in", "out") else "unknown",
                       evidence=evidence(g.get("evidence"))) for g in rows(row.get("groups"))]
        later = [dict(historical=identifier(g.get("historical")), evidence=evidence(g.get("evidence")),
                      match=g["match"] if g.get("match") in ("present", "absent") else "unknown")
                 for g in rows(row.get("later"))]
        attempts.append(dict(id=identifier(row.get("id")), groups=groups, later=later))
    digest = judgments.get("packet_sha256")
    return dict(schema=1, packet_sha256=digest if isinstance(digest, str) and re.fullmatch("[0-9a-f]{64}", digest) else None,
                attempts=attempts)


def later_decisions(inputs, judgment, attempt_evidence):
    historical = {g["id"] for g in inputs.packet["history"]["groups"] if g["disposition"] in VALID}
    decisions = dict.fromkeys(sorted(historical), "unknown")
    issues = []
    if inputs.history["unknown"]:
        issues.append("historical inventory incomplete")
    if not judgment or judgment.get("groups") != [] or not isinstance(judgment.get("later"), list):
        if historical or judgment:
            issues.append("later-review judgment missing, repeated or malformed")
        return decisions, issues
    rows = index_rows(judgment["later"], "historical")
    if rows.keys() != historical or sum(map(len, rows.values())) != len(judgment["later"]):
        issues.append("missing or foreign later-review group")
    known = {g["id"] for g in inputs.history["groups"]}
    allowed = attempt_evidence | inputs.history_refs
    for gid in decisions:
        if len(rows[gid]) != 1 or gid not in known:
            issues.append("later-review reference missing, repeated or unverified")
            continue
        row = rows[gid][0]
        match = row.get("match")
        refs = row.get("evidence")
        if (match not in ("present", "absent", "unknown") or not evidence_in(refs, allowed) or
                match != "unknown" and not any(reference_key(ref) in attempt_evidence for ref in refs)):
            issues.append("later-review match or evidence unavailable")
            continue
        decisions[gid] = match
    return decisions, sorted(set(issues))


def partition(judgment, packet_row, allowed, issues):
    claims = {c["id"] for c in packet_row["claims"]}
    unavailable = {c["id"] for c in packet_row["claims"] if reference_key(c["evidence"]) not in allowed}
    if not judgment or judgment.get("later") != [] or not isinstance(judgment.get("groups"), list):
        issues.append("review judgment missing, repeated or malformed")
        return []
    raw = judgment["groups"]
    by_id = index_rows(raw, "id")
    membership = Counter(c for g in raw if isinstance(g, dict) and identifiers(g.get("claims")) for c in g["claims"])
    if set(membership) != claims:
        issues.append("missing or foreign claim in partition")
    groups = []
    for g in raw:
        if (not isinstance(g, dict) or not isinstance(g.get("id"), str) or len(by_id[g["id"]]) != 1
                or not identifiers(g.get("claims")) or not g["claims"]
                or any(c not in claims or membership[c] != 1 for c in g["claims"])):
            issues.append("ambiguous claim group membership")
            continue
        if unavailable.intersection(g["claims"]) or not evidence_in(g.get("evidence"), allowed):
            issues.append("claim or judgment evidence unavailable")
            continue
        groups.append(g)
    return groups


def adjudicate(raw, dispositions, missing_delivery, issues):
    groups = {}
    for g in raw:
        ref = g.get("historical")
        verdict, scope = g.get("verdict"), g.get("scope")
        if "historical" not in g or ref is not None and (not isinstance(ref, str) or ref not in dispositions):
            issues.append("unresolved historical reference")
            ref, verdict = None, "unknown"
        if verdict not in ("valid", "false_positive", "unknown") or (ref is not None and verdict != "unknown"
                and (verdict == "valid") != (dispositions[ref] in VALID)):
            issues.append("unresolved or contradictory verdict")
            verdict = "unknown"
        if scope not in ("in", "out", "unknown"):
            issues.append("unresolved scope judgment")
            scope = "unknown"
        if missing_delivery and scope != "in":
            scope, verdict = "unknown", "unknown"
            issues.append("delivery unavailable for scope-dependent claim")
        key = ("historical", ref) if ref is not None else ("judged", g["id"])
        if key in groups:
            # Multiple claims mapped to the same verified defect can only establish one finding.
            previous = groups[key]
            if previous["verdict"] != verdict or previous["scope"] != scope:
                issues.append("conflicting judgments for one historical defect")
            if previous["verdict"] != verdict:
                verdict = "unknown"
            if previous["scope"] != scope:
                scope = "unknown"
        groups[key] = dict(historical=ref, verdict=verdict, scope=scope)
    return groups.values()


def review_metrics(judgment, packet_row, historical, complete_reports, delivery_missing, allowed):
    issues = []
    raw = partition(judgment, packet_row, allowed, issues)
    if not complete_reports:
        issues.append("first-round reports incomplete")
    whole_partition = not issues
    dispositions = {g["id"]: g["disposition"] for g in historical["groups"]}
    eligible = {gid for gid, disposition in dispositions.items() if disposition in VALID}
    groups = adjudicate(raw, dispositions, delivery_missing, issues)
    recovered = {g["historical"] for g in groups if g["verdict"] == "valid"} & eligible
    unresolved = [g["historical"] for g in groups if g["verdict"] == "unknown"]
    could_match = any(ref is None or ref in eligible - recovered for ref in unresolved)
    complete = (not historical["unknown"] and complete_reports and
                (recovered == eligible or whole_partition and not could_match))
    partial = set()
    if not whole_partition:
        partial.update(("review.unknown_verdict", "review.unknown_scope"))
    if not whole_partition or unresolved:
        partial.update(("review.false_positive", "review.novel_valid"))
    possible_novel = sum(g["verdict"] == "valid" and g["historical"] is None for g in groups)
    if historical["unknown"]:
        issues.append("historical inventory incomplete")
        if possible_novel:
            partial.add("review.novel_valid")
    metrics = {
        "review.recall": rate(len(recovered), len(eligible), complete),
        "review.novel_valid": possible_novel if not historical["unknown"] else 0,
        "review.false_positive": sum(g["verdict"] == "false_positive" for g in groups),
        "review.unknown_verdict": sum(g["verdict"] == "unknown" for g in groups),
        "review.unknown_scope": sum(g["scope"] == "unknown" for g in groups),
        "review.scope": rate(sum(g["scope"] == "out" for g in groups), sum(g["scope"] != "unknown" for g in groups),
                             whole_partition),
    }
    return metrics, sorted(set(issues)), sorted(partial)
