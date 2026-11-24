#!/usr/bin/env python3
"""Replay R006-F3 on the last 30 reachable non-merge commits at each pinned tip.

Run with Python 3.10+ and Git on a local filesystem supporting hard links:
    python3 refs-trial.py /path/to/skills /path/to/silk > results.tsv
    python3 refs-trial.py /path/to/skills /path/to/silk --explain 1a5d3e7 > results.tsv

The source repositories are read-only. Each run creates fresh clones under the
Canon repository's .canon/canon/refs-trailer-trial/. Only the TSV goes to stdout.
For a modified path, the commit tree supplies its owners. The runner also checks
the parent and reports any change in verdict from requiring both sets of owners.
"""

import argparse
import csv
import os
import re
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from contextlib import contextmanager
from pathlib import Path
from typing import NamedTuple


CANON = "19d59da60bbd0c119a3c594fd02ec710b96c48ec"
SILK = "c4440984c17507e3c8b3fd200f07478fa3547790"
TOOL = Path("skills/governance/canon/scripts/canon.py")
INSTALL = Path(".agents/skills/canon/scripts/canon.py")
DOC_ID = re.compile(r"\b[CDPREI][0-9]{3,}[A-Z]?\b")
DESIGN_ID = re.compile(r"D[0-9]{3,}[A-Z]?")
EXEMPT = {"doc", "skill", "no design"}


def run(root, *args):
    # Each subprocess enters its intended repository explicitly. canon is a
    # function so paths and arguments survive the shell unchanged.
    command = ('cd "$1" && shift && { canon() { "$TRIAL_PYTHON" '
               '.agents/skills/canon/scripts/canon.py "$@"; }; "$@"; }')
    env = dict(os.environ, TRIAL_PYTHON=sys.executable, GIT_OPTIONAL_LOCKS="0",
               GIT_NO_REPLACE_OBJECTS="1", PYTHONDONTWRITEBYTECODE="1", LC_ALL="C")
    result = subprocess.run(["sh", "-c", command, "trial", str(root), *args],
                            env=env, check=True, stdout=subprocess.PIPE)
    return os.fsdecode(result.stdout)


def git(root, *args):
    return run(root, "git", "-c", "core.hooksPath=/dev/null", *args)


def verify_root(root):
    found = Path(git(root, "rev-parse", "--show-toplevel").strip()).resolve()
    if found != root:
        raise ValueError(f"expected repository {root}, got {found}")


def clone(source, dest):
    git(source, "clone", "--quiet", "--template=", "--shared", "--no-checkout",
        "--", str(source), str(dest))
    verify_root(dest)
    return dest


@contextmanager
def project_tool(repo, pinned_tool):
    # A hard link keeps the installed filename inside this project's tree when
    # which follows symlinks. Silk's installed copy is restored before checkout.
    installed = repo / INSTALL
    saved = repo.parent / f"{repo.name}-saved-tool"
    installed.parent.mkdir(parents=True, exist_ok=True)
    had_tool = installed.exists() or installed.is_symlink()
    if had_tool:
        installed.rename(saved)
    try:
        os.link(pinned_tool, installed)
        try:
            yield
        finally:
            installed.unlink()
    finally:
        if had_tool:
            saved.rename(installed)


class Commit(NamedTuple):
    sha: str
    parent: str
    refs_lines: int
    cited: set
    changes: list


def read_commit(repo, sha):
    info = git(repo, "show", "-s", "--no-notes", "--no-show-signature",
               "--format=%P%x00%B", sha)
    parent, body = info.split("\0", 1)
    if " " in parent:
        raise ValueError(f"unexpected merge in sample: {sha}")
    lines = [line for line in body.splitlines() if line.lower().startswith("refs:")]
    cited = {doc for line in lines for doc in DOC_ID.findall(line[5:])}
    raw = git(repo, "diff-tree", "--root", "--no-commit-id", "-r",
              "--no-renames", "--name-status", "-z", sha)
    fields = raw.split("\0")[:-1]
    if len(fields) % 2 or any(code not in {"A", "D", "M", "T"} for code in fields[::2]):
        raise ValueError(f"unexpected diff-tree result for {sha}")
    return Commit(sha, parent, len(lines), cited, list(zip(fields[::2], fields[1::2])))


def historical_owners(repo, commits, pinned_tool):
    requests = defaultdict(set)
    for commit in commits:
        for status, path in commit.changes:
            if status != "D":
                requests[commit.sha].add(path)
            if status != "A":
                requests[commit.parent].add(path)
    answers = {}
    for revision, paths in requests.items():
        git(repo, "checkout", "--quiet", "--detach", revision)
        with project_tool(repo, pinned_tool):
            output = run(repo, "canon", "which", "--", *sorted(paths))
            by_path = defaultdict(set)
            for line in output.splitlines():
                label, answer = line.split(": ", 1)
                if label.endswith(" (missing)"):
                    raise ValueError(f"missing path at {revision}: {label}")
                first = answer.split(" ", 1)[0]
                if answer in EXEMPT:
                    by_path[label].add(answer)
                elif DESIGN_ID.fullmatch(first):
                    by_path[label].add(first)
                else:
                    raise ValueError(f"unrecognized which output: {line}")
            for path in paths:
                resolved = str((repo / path).resolve().relative_to(repo))
                matches = by_path.get(resolved)
                if not matches or (len(matches) > 1 and matches & EXEMPT):
                    raise ValueError(f"bad which result for {revision}:{path}: {matches}")
                answers[revision, path] = matches
    return answers


def classify(required, commit):
    if not required:
        return "no governed files"
    if not commit.refs_lines:
        return "no Refs line"
    if required - commit.cited:
        return "missing governing IDs"
    return "complete"


def ids(items):
    return ",".join(sorted(items)) or "-"


def rows(name, repo, tip, pinned_tool, explain):
    revisions = git(repo, "rev-list", "--no-merges", "-n", "30", tip).splitlines()
    if len(revisions) != 30:
        raise ValueError(f"{name} history does not contain the 30 required commits")
    commits = [read_commit(repo, revision) for revision in revisions]
    owners = historical_owners(repo, commits, pinned_tool)
    for commit in commits:
        counts = Counter()
        required, previous = set(), set()
        for status, path in commit.changes:
            revision = commit.parent if status == "D" else commit.sha
            matches = owners[revision, path]
            if matches & EXEMPT:
                counts[next(iter(matches))] += 1
            else:
                counts["governed"] += 1
                required.update(matches)
            if status in {"M", "T"}:
                previous.update(owners[commit.parent, path] - EXEMPT)
            if any(commit.sha.startswith(prefix) for prefix in explain):
                print(f"{name} {commit.sha[:12]} {status} {path}  {ids(matches)}", file=sys.stderr)
        verdict = classify(required, commit)
        if (required | previous) != required:
            both = classify(required | previous, commit)
            print(f"{name} {commit.sha[:12]} union of both trees adds {ids(previous - required)};"
                  f" verdict changes from {verdict!r} to {both!r}", file=sys.stderr)
        yield [name, commit.sha, verdict, len(commit.changes), counts["governed"], counts["doc"],
               counts["skill"], counts["no design"], commit.refs_lines, ids(required),
               ids(commit.cited), ids(required - commit.cited)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("canon_repo", type=Path)
    parser.add_argument("silk_repo", type=Path)
    parser.add_argument("--explain", action="append", default=[], metavar="COMMIT_PREFIX")
    args = parser.parse_args()
    canon_source = args.canon_repo.resolve()
    silk_source = args.silk_repo.resolve()
    for root in (canon_source, silk_source):
        verify_root(root)
    scratch = canon_source / ".canon/canon/refs-trailer-trial"
    scratch.mkdir(parents=True, exist_ok=True)
    workspace = Path(tempfile.mkdtemp(prefix="replay-", dir=scratch))
    driver = clone(canon_source, workspace / "driver")
    git(driver, "checkout", "--quiet", "--detach", CANON)
    writer = csv.writer(sys.stdout, delimiter="\t", lineterminator="\n")
    writer.writerow("repo commit verdict paths governed doc skill unowned refs_lines "
                    "required cited missing".split())
    for name, source, tip in (("Canon", canon_source, CANON), ("Silk", silk_source, SILK)):
        repo = clone(source, workspace / name)
        writer.writerows(rows(name, repo, tip, driver / TOOL, args.explain))


if __name__ == "__main__":
    main()
