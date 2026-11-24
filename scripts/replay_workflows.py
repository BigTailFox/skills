"""Prepare and compare paired historical runs of Canon workflows."""
import argparse
import os
from pathlib import Path
import sys
import tempfile

sys.dont_write_bytecode = True

import trace_report
from replay_case import load_case
from replay_run import run
from replay_score import score
from replay_summary import summarize
from replay_git import ReplayError, import_input, json_bytes, oid, save_fixtures, save_suite, sha256
from replay_task import criteria_for, plan_sections, review_delivery
from replay_roles import role_evidence
from replay_history import inventory
from trace_versions import valid_manifest


def operator_inputs(args):
    paths = [args.criteria] if args.criteria else []
    if args.review_evidence:
        paths.extend((args.review_evidence, args.review_evidence.with_name("review-adjudications.tsv"),
                      args.review_evidence.with_name("review-host.tsv")))
    return {str(p.resolve()): sha256(p.read_bytes()) if p.is_file() else None for p in paths}


def select_case(args):
    args.project = [args.project.resolve()]
    args.since = None
    args.codex_home = args.codex_home or [Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")]
    scopes = {}
    report, population, catalog = trace_report.read(args, scopes=scopes)
    matches = [c for c in population if c.history.unit == args.unit
               and (not args.store or c.store == args.store.resolve())]
    if len(matches) != 1:
        raise ReplayError("ambiguous unit across stores" if matches else "project, store and unit not found")
    case = matches[0]
    row = next((r for r in report["questions"]["9"]["units"] if r["case"] == case.id), None)
    if not row or not row["eligible"]:
        raise ReplayError("case ineligible: " + (", ".join(row["reasons"]) if row else "unit kind is not replayable"))
    version = case.data["version"]
    if version["status"] != "single":
        raise ReplayError("unit manifest is " + version["status"])
    manifest, = version["manifests"]
    if not valid_manifest(case, manifest):
        raise ReplayError("invalid recorded manifest")
    return case, row, scopes.get(case.id, {"form": "slice"}), manifest, population, catalog


def prepare(args):
    inputs = operator_inputs(args)
    case, row, scope, manifest, population, catalog = select_case(args)
    recorded = oid(case.store, "rev-parse", "--verify", "refs/skills/" + manifest + "^{commit}")
    candidate = oid(args.skills_repo, "rev-parse", "--verify", "--end-of-options", args.candidate + "^{commit}")
    out = args.out.absolute()
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".replay-", dir=out.parent) as name:
        private = Path(name) / "private"
        private.mkdir(mode=0o700)
        task_input, source = import_input(private / "input", case, row, scope)
        fixtures = save_fixtures(private / "fixtures", args.fixtures, private / "input", source)
        suites = dict(recorded=save_suite(private / "suites/recorded", case.store, recorded, recorded=True),
                      candidate=save_suite(private / "suites/candidate", args.skills_repo, candidate))
        if suites["recorded"]["manifest"] != manifest:
            raise ReplayError("recorded suite disagrees with its manifest")
        docs, sid = case.data["docs"], case.data["slice"]
        criteria, section = [], None
        if sid:
            plan, = [d for d in docs if d.startswith("P") and "@r" in d]
            section = plan_sections(private / "input", task_input["target"], plan).get(sid)
            if not section:
                raise ReplayError("slice or plan revision unavailable")
            task_input["paths"] = [section["path"]]
            criteria = criteria_for(section, args.criteria)
        elif args.criteria:
            raise ReplayError("criteria can only be supplied for a slice")
        delivery = review_delivery(case, private / "input", task_input["target"])
        roles, brief, conflicts = role_evidence(case, catalog)
        task = dict(docs=docs, slice=sid, tier=case.start.get("tier"), input=task_input,
                    delivery=delivery["text"] if delivery else None,
                    criteria=[{k: c[k] for k in ("id", "text")} for c in criteria])
        receipt = dict(schema=1, project=str(case.project), store=str(case.store), unit=case.history.unit,
                       kind=case.history.kind, host=case.data["host"], steered=row["steered"],
                       task=task, source=source, suites=suites, fixtures=fixtures, criteria=criteria,
                       slice_plan=section, delivery=delivery, roles=roles, historical_brief=brief,
                       incompatibilities=conflicts, history=inventory(case, row, scope, population))
        receipt["trace"] = dict(start=case.start["_sha256"], end=case.end["_sha256"] if case.end else None)
        if operator_inputs(args) != inputs:
            raise ReplayError("operator evidence changed during preparation")
        receipt["operator_inputs"] = inputs
        encoded = json_bytes(receipt)
        (private / "receipt.json").write_bytes(encoded)
        (private / "receipt.sha256").write_text(sha256(encoded) + "\n")
        load_case(Path(name))
        if out.is_symlink():
            raise ReplayError("output is a symlink")
        out.mkdir(mode=0o700, exist_ok=True)
        destination = out / "private"
        if not destination.exists() and any(out.iterdir()):
            raise ReplayError("different inputs require a fresh case directory")
        try:
            private.rename(destination)
        except OSError:
            if destination.is_symlink() or not (destination / "receipt.json").is_file():
                raise ReplayError("cannot publish prepared case")
            if (destination / "receipt.json").read_bytes() != encoded:
                raise ReplayError("different inputs require a fresh case directory")
            load_case(out)
        print(out / "private/receipt.json")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    p = commands.add_parser("prepare", help="freeze a verified historical unit")
    p.add_argument("--project", type=Path, required=True)
    p.add_argument("--unit", required=True)
    p.add_argument("--candidate", required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--skills-repo", type=Path, default=Path(__file__).resolve().parents[1])
    for name in ("store", "fixtures", "criteria", "review-evidence", "cursor-state-db"):
        p.add_argument("--" + name, type=Path)
    p.add_argument("--cursor-home", type=Path, default=Path.home() / ".cursor")
    p.add_argument("--codex-home", type=Path, action="append")
    p.set_defaults(operation=prepare)
    r = commands.add_parser("run", help="execute paired repetitions of a prepared case")
    r.add_argument("directory", type=Path)
    r.add_argument("--runner", type=Path, required=True)
    r.add_argument("--runner-config", type=Path, required=True)
    r.add_argument("--repetitions", type=int, default=3)
    r.set_defaults(operation=run)
    s = commands.add_parser("score", help="score one sealed case with its blinded judgments")
    s.add_argument("directory", type=Path)
    s.add_argument("--judgments", type=Path)
    s.set_defaults(operation=score)
    report = commands.add_parser("summarize", help="summarize paired differences across scored cases")
    report.add_argument("directories", type=Path, nargs="+", metavar="DIR")
    report.set_defaults(operation=summarize)
    args = parser.parse_args()
    try:
        args.operation(args)
    except (ReplayError, OSError, UnicodeError) as exc:
        parser.exit(1, f"replay: {exc}\n")


if __name__ == "__main__":
    main()
