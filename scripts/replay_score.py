"""Score the sealed first-round observations of one paired case."""
from contextlib import contextmanager

from replay_git import ReplayError, sha256
from replay_judgments import blinded_judgments, decided_counts, index_rows, later_decisions, review_metrics
from replay_protocol import COMPONENTS, require
from replay_run import fcntl
from replay_scoring_inputs import ScoreInputs, reference_key
from replay_storage import decode, publish, publish_json
from trace_review_evidence import VALID


@contextmanager
def sealed_run(directory):
    private = directory / "private"
    lock_path = private / "run.lock"
    require(not private.is_symlink() and not lock_path.is_symlink(), "invalid private run lock")
    with lock_path.open("rb") as lock:
        if fcntl:
            fcntl.flock(lock, fcntl.LOCK_SH)
        try:
            inputs = ScoreInputs(directory)
        except (KeyError, TypeError, IndexError, AttributeError) as exc:
            raise ReplayError("invalid sealed replay inputs") from exc
        yield inputs


def token_components(measured):
    values = {k: measured.get(k) for k in COMPONENTS}
    for key, value in values.items():
        if type(value) is not int or value < 0:
            values[key] = None
    for total, subset in (("input", "cached_input"), ("output", "reasoning_output")):
        if values[subset] is not None and values[total] is not None and values[subset] > values[total]:
            values[total] = values[subset] = None
    return values


def seconds(value):
    return value if type(value) in (float, int) and value >= 0 else None


def costs(attempt, roles):
    metrics = {"cost.wall_seconds": seconds(attempt["wall_seconds"])}
    for key in roles:
        values = token_components(attempt["roles"].get(key, {}).get("tokens", {}))
        metrics.update({f"cost.tokens.{key}.{component}": value for component, value in values.items()})
    return metrics


def boundary_cost(inputs, violation):
    if violation is None:
        return None
    ref = violation["evidence"]
    return dict(wall_seconds=seconds(violation["wall_seconds"]),
                tokens={k: token_components(v) for k, v in violation["tokens"].items()},
                reason_sha256=sha256(violation["reason"].encode()),
                evidence_sha256=ref["sha256"] if reference_key(ref) in inputs.private_files else None)


def compare(observed, candidate, complete=True):
    a = observed["rate"] if isinstance(observed, dict) else observed
    b = candidate["rate"] if isinstance(candidate, dict) else candidate
    return dict(recorded=observed, candidate=candidate, difference=b - a if complete and None not in (a, b) else None)


def common_decisions(recorded, candidate, field, positive, negative):
    old, new = recorded[field], candidate[field]
    decided = {positive, negative}
    common = sorted(k for k in old.keys() & new.keys() if old[k] in decided and new[k] in decided)
    prefix = "slice." + field
    a, b = (decided_counts({k: side[k] for k in common}, prefix, positive, negative) for side in (old, new))
    return common, {k: compare(v, b[k], bool(common)) for k, v in a.items()}


def paired(attempts, repetitions):
    slots = {(a["pair"], a["arm"]): a for a in attempts if a["outcome"] == "completed"}
    pairs = []
    for pair in range(1, repetitions + 1):
        recorded, candidate = (slots.get((pair, arm)) for arm in ("recorded", "candidate"))
        if recorded is None or candidate is None:
            continue
        partial = set(recorded["unknown_metrics"] + candidate["unknown_metrics"])
        metrics = {key: compare(value, candidate["metrics"][key], key not in partial)
                   for key, value in recorded["metrics"].items()}
        row = dict(pair=pair, recorded=recorded["id"], candidate=candidate["id"], metrics=metrics)
        if "criteria" in recorded:
            row["common"] = {}
            for field, yes, no in (("criteria", "pass", "fail"), ("later", "present", "absent")):
                row["common"][field], decided = common_decisions(recorded, candidate, field, yes, no)
                metrics.update(decided)
            # Undecided criteria and matches remain visible in the per-arm observations.
            for key in ("slice.criteria.unavailable", "slice.later.unknown"):
                metrics.pop(key)
        pairs.append(row)
    return pairs


def judgment_rows(inputs, judgment_bytes):
    if judgment_bytes is None:
        if inputs.receipt["kind"] != "slice" or any(g["disposition"] in VALID for g in inputs.packet["history"]["groups"]):
            raise ReplayError("blinded judgments are required")
        return None, {}, []
    judgments = decode(judgment_bytes, "blinded judgments")
    require(type(judgments.get("schema")) is int and judgments["schema"] == 1 and
            isinstance(judgments.get("attempts"), list), "invalid v1 judgments")
    judgment_issues = []
    rows = index_rows(judgments["attempts"], "id")
    if set(rows) - inputs.rows.keys() or sum(map(len, rows.values())) != len(judgments["attempts"]):
        judgment_issues.append("judgments contain an unrecognized attempt")
    if judgments.get("packet_sha256") != inputs.packet_sha256:
        rows.clear()
        judgment_issues.append("judgments bound to a different packet")
    return judgments, rows, judgment_issues


def score_slice(inputs, attempt, packet_row, judgment):
    status = attempt["worker_status"] if "worker" in inputs.verified_reports[attempt["id"]] else None
    completed = attempt["outcome"] == "completed" and status in ("done", "blocked", "stuck")
    metrics = {"slice.worker." + s: int(s == status) if completed else None for s in ("done", "blocked", "stuck")}
    refs = inputs.verified_refs[attempt["id"]]
    criteria = {c["id"]: "unavailable" for c in inputs.receipt["criteria"]}
    for test in packet_row["tests"]:
        if reference_key(test["evidence"]) in refs:
            criteria[inputs.criteria[test["id"]]] = test["outcome"]
    metrics.update(decided_counts(criteria, "slice.criteria", "pass", "fail"))
    metrics["slice.criteria.unavailable"] = sum(v == "unavailable" for v in criteria.values())
    attempt_evidence = {reference_key(t["evidence"]) for t in packet_row["tests"]
                        if criteria[inputs.criteria[t["id"]]] != "unavailable"}
    if reference_key(packet_row["artifact"]) in refs:
        attempt_evidence.add(reference_key(packet_row["artifact"]))
    later, issues = later_decisions(inputs, judgment, attempt_evidence)
    if attempt.get("status_issue"):
        issues.append(attempt["status_issue"])
    metrics.update(decided_counts(later, "slice.later", "present", "absent"))
    metrics["slice.later.unknown"] = sum(v == "unknown" for v in later.values())
    brief = attempt.get("brief_comparison", {})
    comparison = dict(status=brief.get("status", "unavailable"), dispatched_sha256=brief.get("dispatched_sha256"),
                      historical_sha256=inputs.receipt["historical_brief"]["sha256"])
    dispatched = attempt["roles"].get("worker", {}).get("brief")
    if reference_key(dispatched) not in inputs.private_files:
        comparison.update(status="unavailable", dispatched_sha256=None)
    return dict(metrics=metrics, unknowns=issues, unknown_metrics=[], worker_status=status, criteria=criteria,
                later=later, brief_comparison=comparison)


def score_review(inputs, attempt, packet_row, judgment):
    ident = attempt["id"]
    expected = inputs.journal["roles"].keys() - {"parent"}
    complete_reports = attempt["outcome"] == "completed" and inputs.verified_reports[ident] == expected
    delivery_missing = inputs.receipt["kind"] == "code-review" and inputs.receipt["delivery"] is None
    allowed = inputs.history_refs | inputs.verified_refs[ident]
    if inputs.review_input and inputs.review_input_available:
        allowed.add(inputs.review_input)
    if not inputs.review_input_available:
        judgment = None
    metrics, unknowns, partial = review_metrics(judgment, packet_row, inputs.history, complete_reports,
                                               delivery_missing, allowed)
    return dict(metrics=metrics, unknowns=unknowns, unknown_metrics=partial)


def case_result(inputs, judgment_bytes):
    journal, receipt = inputs.journal, inputs.receipt
    judgments, rows, judgment_issues = judgment_rows(inputs, judgment_bytes)
    attempts = []
    evaluate = score_slice if receipt["kind"] == "slice" else score_review
    for attempt in inputs.attempts:
        ident = attempt["id"]
        matches = rows.get(ident, [])
        judgment = matches[0] if len(matches) == 1 else None
        scored = evaluate(inputs, attempt, inputs.rows[ident], judgment)
        scored["metrics"].update(costs(attempt, journal["roles"]))
        attempts.append(dict(id=ident, arm=attempt["arm"], pair=attempt["pair"], outcome=attempt["outcome"], **scored,
                             boundary_violation=boundary_cost(inputs, attempt["boundary_violation"])))
    pairs = paired(attempts, journal["repetitions"])
    completed = {p["pair"] for p in pairs}
    identity = {k: receipt[k] for k in ("project", "store", "unit")}
    suites = {k: {f: s[f] for f in ("manifest", "tree")} for k, s in receipt["suites"].items()}
    cohort = dict(project=receipt["project"], kind=receipt["kind"], tier=receipt["task"]["tier"], host=receipt["host"],
                  suites=suites, roles=journal["roles"], config_sha256=journal["config_sha256"],
                  runner_sha256=journal["runner_sha256"])
    history = dict(inputs.history, review=receipt["history"]["review"], raw_count=receipt["history"]["raw_count"])
    incomplete = sorted(set(range(1, journal["repetitions"] + 1)) - completed)
    evidence = {"unavailable_evidence_sha256": inputs.unavailable_evidence} if inputs.unavailable_evidence else {}
    return dict(schema=1, case=journal["case"], identity=identity, cohort=cohort, trace=receipt["trace"], **evidence,
                steered=receipt["steered"], receipt_sha256=inputs.receipt_sha256, run_sha256=inputs.run_sha256,
                packet_sha256=inputs.packet_sha256, judgments_sha256=sha256(judgment_bytes) if judgment_bytes else None,
                judgments=blinded_judgments(inputs, judgments), history=history,
                judgment_issues=judgment_issues, attempts=attempts, pairs=pairs, comparable_pairs=len(pairs),
                incomplete_pairs=incomplete, sparse_pairs=len(pairs) < 3)


def score(args):
    directory = args.directory.resolve(strict=True)
    raw = args.judgments.read_bytes() if args.judgments else None
    path = directory / "result.json"
    with sealed_run(directory) as inputs:
        result = case_result(inputs, raw)
        if raw is not None:
            store = inputs.private / "judgments"
            require(not store.is_symlink(), "invalid private judgments directory")
            publish(store / result["judgments_sha256"], raw)
        publish_json(path, result)
    print(path)
