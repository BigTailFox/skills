"""Report evidence from local canon traces without changing the projects or host profiles."""
import argparse
from datetime import date
import json
import os
from pathlib import Path
import sys

sys.dont_write_bytecode = True
from trace_records import collect, select
from trace_hosts import attach_hosts
from trace_workers import codex_workers, cursor_workers
from trace_questions import apply_tiers, costs, slice_outcomes, tier_changes
from trace_reviews import review_questions
from trace_retro import end_checks, read_notes, retro_fixes
from trace_replay import replay_units
from trace_versions import version_inventory


def build(args):
    population, cases = collect(args.project or [Path.cwd()])
    apply_tiers(cases)
    catalog = attach_hosts(cases, args)
    codex_workers(cases, catalog)
    cursor_workers(cases)
    selected = select(cases, args.since, population)
    population.update(units=len(selected), since=args.since.isoformat() if args.since else None,
                      cursor_home=str(args.cursor_home), cursor_state_db=str(args.cursor_state_db) if args.cursor_state_db else None,
                      codex_homes=[str(path) for path in args.codex_home])
    population["host_starts"] = {}
    for source in ("export", "cursor-db", "unknown"):
        members = [c.id for c in selected if c.data["host_start"]["source"] == source]
        population["host_starts"][source] = {
            "numerator": len(members), "denominator": len(selected), "cases": members,
            "sample": "few units" if len(selected) < 20 else "20 or more units"}
    notes = {Path(p): read_notes(Path(p)) for p in dict.fromkeys([*population["projects"], *(str(c.project) for c in selected)])}
    versions = version_inventory(args.skills_repo, selected, cases)
    return dict(population=population, cases=[c.data for c in selected], skill_versions=versions,
                questions={**review_questions(selected, cases, args, catalog), "4": slice_outcomes(selected), "5": tier_changes(selected),
                           "6": costs(selected), "7": retro_fixes(selected, notes), "8": end_checks(selected, notes, cases),
                           "9": replay_units(selected, cases)})


def text_value(label, value, depth=0):
    prefix = "  " * depth
    if isinstance(value, dict):
        props = dict(value)
        ratio = ""
        if "numerator" in props and "denominator" in props:
            ratio = f" {props.pop('numerator')}/{props.pop('denominator')}"
        print(prefix + label + ratio)
        for key, member in props.items():
            text_value(key.replace("_", " "), member, depth + 1)
    elif isinstance(value, list):
        if not value or all(not isinstance(x, (list, dict)) for x in value):
            print(prefix + label + "  " + (", ".join(str(x) for x in value) or "none"))
        else:
            print(prefix + label)
            for item in value:
                text_value("•", item, depth + 1)
    else:
        print(prefix + label + "  " + ("none" if value is None else str(value)))


def text_report(report):
    text_value("Source population", report["population"])
    text_value("Skill versions", report["skill_versions"])
    for number, question in report["questions"].items():
        print()
        text_value("Q" + str(number) + "  " + question["title"],
                   {k: v for k, v in question.items() if k != "title"})
    print()
    text_value("Cases and record locations", report["cases"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, action="append", metavar="PATH")
    parser.add_argument("--since", type=date.fromisoformat, metavar="YYYY-MM-DD", help="inclusive UTC start date")
    parser.add_argument("--skills-repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--cursor-home", type=Path, default=Path.home() / ".cursor")
    parser.add_argument("--cursor-state-db", type=Path)
    parser.add_argument("--codex-home", type=Path, action="append")
    parser.add_argument("--review-evidence", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    args.codex_home = args.codex_home or [Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")]
    report = build(args)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        text_report(report)


if __name__ == "__main__":
    main()
