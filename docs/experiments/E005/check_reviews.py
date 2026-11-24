"""Read-only check of the E005 pilot review evidence against named project archives."""

import argparse
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
REVIEW_KINDS = {"gate", "follow-up", "code-review"}
FINDING_HEADING = re.compile(r"(?:#{2,4}\s+|^\*\*)(F[1-9]\d*)\b")
CONFIRMATION_BLOCKER = re.compile(r"^\s*(?:- )?\*\*(?:New blocker — )?(F[1-9]\d*)\.")
DISPOSITIONS = {"accepted", "deferred", "declined", "escalated", "unknown"}


class EvidenceError(ValueError):
    """A safe diagnostic, containing no private evidence text."""


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read_table(path):
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream, delimiter="\t"))


def require(condition, message):
    if not condition:
        raise EvidenceError(message)


def group_units(rows):
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["project"], row["unit"]].append(row)
    return grouped


def contribution_counts(rows, reviewers, outcome):
    if outcome != "delivered":
        return {"coverage": "partial-" + outcome}
    groups = defaultdict(list)
    for row in rows:
        if row["phase"] == "first" and row["defect_group"] != "unknown":
            groups[row["defect_group"]].append(row)
    joint = dict.fromkeys(reviewers, 0)
    exclusive = joint.copy()
    valid = 0
    for claims in groups.values():
        dispositions = {r["disposition"] for r in claims}
        if dispositions not in ({"accepted"}, {"deferred"}):
            continue
        keys = {r["reviewer_key"] for r in claims}
        counts = joint if len(keys) > 1 else exclusive
        for key in keys:
            counts[key] += 1
        valid += 1
    return dict(coverage="delivered", valid_first_groups=valid, joint=joint, exclusive=exclusive)


def assignments(cell):
    entries = [pair.split("=") for pair in cell.split()]
    result = dict(entries)
    require(len(result) == len(entries), "repeated adjudicated finding")
    return result


def check_decision_record(archive, source, receipts):
    locator = source.get("decision_locator", "")
    if not locator:
        return
    match = re.fullmatch(r"(parent|[A-Za-z0-9_-]+\.md):L([1-9]\d*)", locator)
    require(match, "invalid decision locator")
    filename, number = match.groups()
    if filename == "parent":
        require(any(r["evidence"] in {"decision", "final"} and r["line"] == number and
                    r["sha256"] == source["decision_sha256"] for r in receipts), "unverified parent decision")
    else:
        line = (archive / filename).read_bytes().splitlines()[int(number)-1]
        require(digest(line) == source["decision_sha256"], "archived decision digest")


def verify_claims(archive, catalog, rows, recorded, registered, receipts):
    raw = {}
    for i, finding in enumerate(recorded, 1):
        for by in finding["by"]:
            require(by not in raw, "duplicate raw source")
            raw[by] = (str(i), finding["disposition"])
    table = {(r["report_stem"], r["finding_id"]): r for r in rows}
    require(len(table) == len(rows), "duplicate table source")
    covered = set()
    expected = set()
    for source in catalog:
        stem = source["report_stem"]
        require(re.fullmatch("[A-Za-z0-9_-]+", stem), "invalid report stem")
        blob = (archive / (stem + ".md")).read_bytes()
        require(digest(blob) == source["report_sha256"], "report digest")
        if source["phase"] == "pending":
            require(not source["groups"], "pending source has findings")
            continue
        heading = FINDING_HEADING if source["phase"] == "first" else CONFIRMATION_BLOCKER
        found = [(m[1], i) for i, line in enumerate(blob.decode().splitlines(), 1)
                 if (m := heading.search(line))]
        groups = assignments(source["groups"])
        decisions = assignments(source["decisions"])
        check_decision_record(archive, source, receipts)
        require(len(found) == len(groups) and {f for f, _ in found} == groups.keys(),
                "report findings differ from adjudication")
        require(decisions.keys() <= groups.keys(), "decision without a source")
        for fid, line in found:
            key = (stem, fid)
            require(key not in expected and key in table, "missing or duplicate report finding")
            expected.add(key)
            row = table[key]
            by = source["reviewer_key"] + ":" + fid
            raw_row, disposition = raw.get(by, ("", ""))
            if raw_row:
                require(by not in covered, "raw source used twice")
                covered.add(by)
                require(fid not in decisions or source.get("decision_locator"), "uncorroborated change of disposition")
            elif source["reviewer_key"] in registered:
                require(row["disposition"] == "unknown", "missing disposition evidence")
            require((row["raw_row"], row["raw_disposition"]) == (raw_row, disposition), "raw source reference")
            require(row["reviewer_key"] == source["reviewer_key"] and row["phase"] == source["phase"],
                    "report identity or phase")
            require(row["report_sha256"] == source["report_sha256"] and
                    row["source_locator"] == f"{stem}.md:L{line}", "source digest or locator")
            require(row["defect_group"] == groups[fid], "disputed defect grouping")
            require(row["disposition"] in DISPOSITIONS and
                    row["disposition"] == decisions.get(fid, disposition), "disposition differs from adjudication")
    require(expected == table.keys(), "unmatched table finding")
    require(covered == raw.keys(), "unmatched raw finding")


def verify_inventory(archive, catalog, recorded):
    require(len({s["report_stem"] for s in catalog}) == len(catalog) and
            all(s["phase"] in {"first", "confirmation", "pending"} for s in catalog), "ambiguous source inventory")
    first = {s["report_stem"]: s for s in catalog if s["phase"] == "first"}
    pending = {s["report_stem"] for s in catalog if s["phase"] == "pending"}
    delivered = set()
    prompts = set()
    for path in archive.glob("*.md"):
        stem = path.stem
        if re.search(r"-(?:confirm|recheck\d+)(?:-prompt)?$", stem):
            continue
        if stem.endswith("-prompt"):
            prompts.add(stem[:-7])
        elif stem.endswith("-pending") or re.match(r"^(spec|standards|cross-family|same-model)(-|$)", stem):
            delivered.add(stem)
    require(delivered == first.keys() | pending, "missing or unaccounted report")
    require(prompts == first.keys() | {s[:-8] for s in pending}, "unaccounted dispatch prompt")
    keys = {s["reviewer_key"] for s in first.values()}
    require(len(keys) == len(first) and recorded.keys() <= keys, "missing or ambiguous reviewer key")
    for stem, source in first.items():
        require((archive / (stem + "-id.txt")).read_text().strip() == source["reviewer_id"],
                "archived reviewer identity")
        if source["reviewer_key"] in recorded:
            r = recorded[source["reviewer_key"]]
            require((r["role"], r["model"], r["id"]) ==
                    (source["role"], source["model"], source["reviewer_id"]), "recorded reviewer identity")
    return first


def confirmed_fixed(prompt, terminal):
    fixed_line = next((line.partition("Fixed findings:")[2] for line in prompt.splitlines()
                       if "Fixed findings:" in line), "")
    fixed = set(re.findall(r"(?:^|;\s*)\s*(F[1-9]\d*)\s*\(", fixed_line))
    resolved = set()
    lines = terminal.splitlines()
    for i, line in enumerate(lines):
        bullet = re.match(r"^- \*\*(F[1-9]\d*)\*\*:\s*resolved(?=[.:]|\s*\(|\s*$)", line, re.I)
        heading = re.match(r"^### (F[1-9]\d*)\b", line)
        if bullet:
            resolved.add(bullet[1])
        elif heading and i + 1 < len(lines) and re.match(r"^Resolved(?=[.:]|\s*$)", lines[i+1]):
            resolved.add(heading[1])
    return fixed & resolved


def verify_supplements(archive, start, first, registered, receipts, cursor_home):
    extra = {stem for stem, s in first.items() if s["reviewer_key"] not in registered}
    require({r["report_stem"] for r in receipts} == extra, "supplemental host evidence inventory")
    if not extra:
        return
    conv = start.get("conversation", "")
    require(cursor_home and re.fullmatch(r"[0-9a-f-]{36}", conv), "Cursor conversation unavailable")
    matches = list(cursor_home.glob(f"projects/*/agent-transcripts/{conv}/{conv}.jsonl"))
    require(len(matches) == 1, "missing or ambiguous Cursor conversation")
    parent = matches[0]
    actions = ["dispatch", "first", "fixed", "terminal", "decision", "final"]
    for stem in extra:
        src = first[stem]
        sid = src["reviewer_id"]
        require(re.fullmatch(r"[0-9a-f-]{36}", sid), "supplemental dispatch identity")
        subset = [r for r in receipts if r["report_stem"] == stem]
        by_action = {r["evidence"]: r for r in subset}
        require(len(subset) == len(actions) and by_action.keys() == set(actions), "missing dispatch or verdict")
        child_lines = (parent.parent / "subagents" / (sid + ".jsonl")).read_bytes().splitlines()
        parent_lines = parent.read_bytes().splitlines()
        positions, records = [], {}
        for action in actions:
            receipt = by_action[action]
            child = action in actions[:4]
            require(receipt["conversation"] == conv and receipt["session"] == (sid if child else conv),
                    "host source identity")
            number = int(receipt["line"])
            require(number > 0, "host line number")
            data = (child_lines if child else parent_lines)[number-1]
            require(digest(data) == receipt["sha256"], "host record digest")
            event = json.loads(data)
            want = "user" if action in {"dispatch", "fixed"} else "assistant"
            require(event["role"] == want, "host message role")
            records[action] = "".join(c["text"] for c in event["message"]["content"] if c["type"] == "text")
            positions.append(number)
        require(positions[:4] == sorted(set(positions[:4])) and positions[4] < positions[5], "host record order")
        for action, suffix in [("dispatch", "-prompt"), ("first", ""), ("fixed", "-confirm-prompt"),
                               ("terminal", "-confirm")]:
            archived = (archive / (stem + suffix + ".md")).read_text().strip()
            host = records[action].strip()
            if action in {"dispatch", "fixed"} and "<user_query>" in host:
                host = host.split("<user_query>", 1)[1].split("</user_query>", 1)[0].strip()
            require(archived == host, "host and archive disagree")
        approved = {fid for fid, d in assignments(src["decisions"]).items() if d == "accepted"}
        require(approved <= confirmed_fixed(records["fixed"], records["terminal"]), "uncorroborated disposition")


def read_events(trace):
    lines = (trace / "events.jsonl").read_bytes().splitlines()
    boundaries = defaultdict(list)
    for i, line in enumerate(lines, 1):
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if isinstance(event, dict) and isinstance(event.get("id"), str) and event.get("type") in ("start", "end"):
            boundaries[event["id"], event["type"]].append(i)
    return lines, boundaries


def check_unit(case, trace, events, rows, catalog, receipts, cursor_home):
    lines, boundaries = events
    for kind in ("start", "end"):
        require(boundaries.get((case["unit"], kind)) == [int(case[kind + "_event"])],
                "missing or ambiguous event boundary")
    start = json.loads(lines[int(case["start_event"])-1])
    end_line = lines[int(case["end_event"])-1]
    end = json.loads(end_line)
    require(start["id"] == end["id"] == case["unit"], "unit identity")
    require(start["type"] == "start" and end["type"] == "end" and
            start["kind"] == end["kind"] == case["kind"], "event boundary")
    require(case["outcome"] == end["outcome"] and end["archive"] == "ok", "outcome or archive")
    recorded = end["dispositions"]["findings"]
    require(len(recorded) == int(case["findings"]), "raw finding count")
    reviewers = end["dispositions"]["reviewers"]
    registered = {r.get("key", r["role"]): r for r in reviewers}
    require(len(registered) == len(reviewers), "duplicate recorded reviewer key")
    archive = trace / case["unit"]
    first = verify_inventory(archive, catalog, registered)
    verify_supplements(archive, start, first, registered, receipts, cursor_home)
    verify_claims(archive, catalog, rows, recorded, registered, receipts)
    require(all(r["end_sha256"] == digest(end_line) for r in rows), "end digest")
    first_rows = [r for r in rows if r["phase"] == "first"]
    return dict(raw_rows=len(recorded), reports=len(first), source_rows=len(rows),
                first_findings=len(first_rows), confirmation_only=len(rows) - len(first_rows),
                omitted=sum(not r["raw_row"] for r in rows),
                pending=[s["reviewer_key"] for s in catalog if s["phase"] == "pending"],
                disputed_first_sources=sum(r["defect_group"] == "unknown" for r in first_rows),
                first_dispositions=dict(Counter(r["disposition"] for r in first_rows)),
                raw_dispositions=dict(Counter(f["disposition"] for f in recorded)),
                **contribution_counts(rows, [s["reviewer_key"] for s in first.values()], end["outcome"]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", action="append", required=True, metavar="NAME=DIR")
    parser.add_argument("--ledger", type=Path, default=HERE.parent / "E003/cases.tsv")
    parser.add_argument("--review-evidence", type=Path, default=HERE / "review-evidence.tsv")
    parser.add_argument("--adjudications", type=Path, default=HERE / "review-adjudications.tsv")
    parser.add_argument("--host-receipts", type=Path, default=HERE / "review-host.tsv")
    parser.add_argument("--cursor-home", type=Path)
    args = parser.parse_args()
    projects = {}
    for value in args.project:
        label, sep, directory = value.partition("=")
        if not sep or not label or not directory or label in projects:
            parser.error("--project needs a distinct NAME=DIR")
        projects[label] = Path(directory)
    if len({p.resolve() for p in projects.values()}) != len(projects):
        parser.error("each project needs its own directory")
    cases = [r for r in read_table(args.ledger) if r["kind"] in REVIEW_KINDS and r["project"] in projects]
    tables = group_units(read_table(args.review_evidence))
    catalogs = group_units(read_table(args.adjudications))
    receipts = group_units(read_table(args.host_receipts))
    keys = {(r["project"], r["unit"]) for r in cases}
    if len(keys) != len(cases) or set(projects) != {key[0] for key in keys}:
        parser.error("missing or ambiguous review cohort")
    if any(key[0] in projects and key not in keys for key in tables.keys() | catalogs.keys() | receipts.keys()):
        parser.error("evidence outside the selected cohort")
    reviews = []
    for name, directory in projects.items():
        trace = directory / ".canon/canon/trace"
        try:
            events = read_events(trace)
        except OSError:
            events = ([], {})
        for case in cases:
            if case["project"] != name:
                continue
            key = (name, case["unit"])
            review = dict(project=name, unit=case["unit"], kind=case["kind"], outcome=case["outcome"])
            try:
                review.update(check_unit(case, trace, events, tables[key], catalogs[key], receipts[key], args.cursor_home))
                review["status"] = "verified"
            except (ValueError, KeyError, IndexError, OSError, TypeError) as error:
                review.update(status="unknown", reason=str(error) if isinstance(error, EvidenceError) else type(error).__name__)
            reviews.append(review)
    print(json.dumps({"reviews": reviews}, indent=2))
    return int(any(r["status"] == "unknown" for r in reviews))


if __name__ == "__main__":
    raise SystemExit(main())
