"""Report paired differences within cases, then give each historical case equal weight."""
from collections import defaultdict
from statistics import mean
import sys

from replay_git import ReplayError, json_bytes, sha256
from replay_protocol import evidence_bytes, require
from replay_score import case_result, sealed_run
from replay_storage import decode


ARMS = ("recorded", "candidate")


def verified_result(directory):
    """Reproduce the published score from its sealed inputs, including the exact adjudication bytes."""
    try:
        directory = directory.resolve(strict=True)
        with sealed_run(directory) as inputs:
            path = directory / "result.json"
            require(not path.is_symlink(), "invalid result path")
            encoded = path.read_bytes()
            result = decode(encoded, "scored result")
            require(result.get("run_sha256") == inputs.run_sha256, "run changed after scoring")
            digest = result.get("judgments_sha256")
            raw = None
            if digest is not None:
                raw = evidence_bytes(inputs.private, dict(path=f"judgments/{digest}", sha256=digest))
            require(encoded == json_bytes(case_result(inputs, raw)), "result differs from its sealed evidence")
            return result, sha256(encoded)
    except (OSError, ReplayError) as exc:
        raise ReplayError(f"cannot verify scored case {directory}: {exc}") from exc


def total(values):
    known = [value for value in values if value is not None]
    return sum(known) if known else None


def observations(values, is_rate, partial=()):
    known = [v for v in values if v is not None]
    if is_rate:
        return dict(measurements=len(known), numerator=total(v["numerator"] for v in known),
                    denominator=total(v["denominator"] for v in known), known_rates=sum(v["rate"] is not None for v in known))
    return dict(measurements=len(known), total=total(known),
                partial_measurements=len(partial), lower_bound=total(partial))


def case_metric(key, attempts, pairs):
    observed = {arm: [] for arm in ARMS}
    partial = {arm: [] for arm in ARMS}
    for attempt in attempts:
        value = attempt["metrics"].get(key)
        if value is not None:
            target = partial if key in attempt["unknown_metrics"] and not isinstance(value, dict) else observed
            target[attempt["arm"]].append(value)
    is_rate = any(isinstance(v, dict) for values in observed.values() for v in values)
    comparable, missing = [], []
    for pair in pairs:
        comparison = pair["metrics"].get(key)
        if comparison is None or comparison["difference"] is None:
            missing.append(pair["pair"])
        else:
            comparable.append(comparison)
    metric = dict(pair_count=len(comparable), unavailable_pairs=missing,
                  mean_difference=mean(v["difference"] for v in comparable) if comparable else None,
                  observed={arm: observations(values, is_rate, partial[arm]) for arm, values in observed.items()})
    if is_rate:
        # A slice's common decided criteria (or later groups) can differ from either arm's overall denominator.
        metric["paired_observed"] = {arm: observations([v[arm] for v in comparable], True) for arm in ARMS}
    return metric


def case_row(result):
    pairs, attempts = result["pairs"], result["attempts"]
    names = {key for attempt in attempts for key in attempt["metrics"]}
    paired_ids = {pair[arm] for pair in pairs for arm in ARMS}
    return dict(case=result["case"], identity=result["identity"], cohort=result["cohort"], steered=result["steered"],
                complete_pairs=[p["pair"] for p in pairs], incomplete_pairs=result["incomplete_pairs"],
                unpaired_attempts=[{k: a[k] for k in ("id", "pair", "arm", "outcome", "boundary_violation")}
                                   for a in attempts if a["id"] not in paired_ids],
                sparse_pairs=result["sparse_pairs"], metrics={k: case_metric(k, attempts, pairs) for k in sorted(names)})


def combine_observations(rows, field):
    combined = {}
    for arm in ARMS:
        samples = [row[field][arm] for row in rows]
        combined[arm] = {key: total(s[key] for s in samples) for key in samples[0]}
    return combined


def cohort_row(cohort, cases, scope, projects):
    metrics = {}
    for key in sorted({key for case in cases for key in case["metrics"]}):
        rows = [c["metrics"][key] for c in cases if key in c["metrics"]]
        means = [m["mean_difference"] for m in rows if m["pair_count"]]
        metric = dict(case_count=len(means), pair_count=sum(m["pair_count"] for m in rows),
                      excluded_cases=[c["case"] for c in cases if not c["metrics"].get(key, {}).get("pair_count")],
                      mean_difference=mean(means) if means else None, observed=combine_observations(rows, "observed"))
        if "paired_observed" in rows[0]:
            metric["paired_observed"] = combine_observations(rows, "paired_observed")
        metrics[key] = metric
    return dict(scope=scope, cohort=cohort, projects=projects, case_count=len(cases),
                complete_pair_count=sum(len(c["complete_pairs"]) for c in cases),
                cases=[c["case"] for c in cases], sparse_cases=[c["case"] for c in cases if c["sparse_pairs"]],
                metrics=metrics)


def independent_cases(directories):
    comparisons = defaultdict(dict)
    for directory in sorted({d.resolve() for d in directories}):
        result, digest = verified_result(directory)
        key = json_bytes([result["identity"], result["cohort"]["suites"]])
        _, sources = comparisons[key].setdefault(digest, (result, []))
        sources.append(str(directory))
    cases, conflicts = [], []
    fields = ("receipt_sha256", "run_sha256", "packet_sha256", "judgments_sha256")
    for _, variants in sorted(comparisons.items()):
        first, directories = next(iter(variants.values()))
        if len(variants) == 1:
            cases.append(dict(case_row(first), directories=directories))
        else:
            seen = []
            for digest, (result, sources) in sorted(variants.items()):
                seen.append(dict(directories=sources, result_sha256=digest, **{f: result[f] for f in fields}))
            differing = [f for f in fields if len({v[f] for v in seen}) > 1]
            conflicts.append(dict(identity=first["identity"], suites=first["cohort"]["suites"],
                                  differing=differing, variants=seen))
    return cases, conflicts


def summarize(args):
    cases, conflicts = independent_cases(args.directories)
    projects, combined = defaultdict(list), defaultdict(list)
    for case in cases:
        cohort = case["cohort"]
        key = json_bytes({k: v for k, v in cohort.items() if k != "project"})
        projects[cohort["project"], key].append(case)
        combined[key].append(case)
    cohorts = [cohort_row(group[0]["cohort"], group, "project", [project])
               for (project, _), group in sorted(projects.items())]
    for key, group in sorted(combined.items()):
        names = sorted({c["cohort"]["project"] for c in group})
        if len(names) > 1:
            cohorts.append(cohort_row(decode(key, "cohort"), group, "combined", names))
    sys.stdout.buffer.write(json_bytes(dict(schema=1, cases=cases, cohorts=cohorts, conflicts=conflicts)))
