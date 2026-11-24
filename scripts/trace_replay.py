"""Verify the original inputs that an offline replay could restore."""
import os
import re

from trace_hosts import observed_lines
from trace_questions import case_ref, ratio, slice_plan
from trace_records import canon, git_bytes, loc, UNKNOWN
from trace_review_inputs import review_input


class Trees:
    """Read immutable commits and verify the blobs a replay checkout needs, once per tree."""
    def __init__(self):
        self.commits = {}
        self.trees = {}

    def commit(self, root, oid):
        if not canon.full_oid(oid):
            return None
        key = (root, oid)
        if key not in self.commits:
            value = None
            if git_bytes(root, "cat-file", "-t", oid) == b"commit\n":
                meta = git_bytes(root, "show", "-s", "--format=%T %P", "--no-show-signature", "--no-notes", oid)
                if meta:
                    tree, *parents = meta.decode("ascii").split()
                    if self.files(root, tree) is not None:
                        value = dict(commit=oid, tree=tree, parents=parents, location=f"{root}@{oid}")
            self.commits[key] = value
        return self.commits[key]

    def files(self, root, tree):
        key = (root, tree)
        if key in self.trees:
            return self.trees[key]
        listing = git_bytes(root, "ls-tree", "-rz", tree)
        files = None
        if listing is not None:
            files = {}
            blobs = set()
            for row in listing.split(b"\0"):
                if not row:
                    continue
                meta, name = row.split(b"\t", 1)
                mode, kind, oid = meta.split()
                files[os.fsdecode(name)] = (mode.decode(), oid.decode())
                if kind == b"blob":
                    blobs.add(oid)
            if blobs:
                checked = git_bytes(root, "cat-file", "--batch-check=%(objecttype)", data=b"\n".join(blobs) + b"\n")
                if checked is None or checked.splitlines() != [b"blob"] * len(blobs):
                    files = None
        self.trees[key] = files
        return files

    def published(self, case, namespace, oid):
        if not canon.full_oid(oid):
            return None
        ref = "refs/" + namespace + "/" + case.history.unit
        tip = git_bytes(case.store, "rev-parse", "--verify", "--quiet", ref)
        if not tip or tip.strip().decode("ascii") != oid:
            return None
        return self.commit(case.store, oid)


def steering(case):
    session = case.host_session
    lines, complete = observed_lines(case, getattr(session, "users", []))
    locations = [loc(session.path, n) for n in lines]
    if complete:
        locations.extend([case.data["host_start"]["location"], case.data["host_end"]["location"]])
    return (True if lines else False if complete else UNKNOWN), locations


def replay_units(cases):
    trees = Trees()
    rows, eligible = [], []
    for c in cases:
        kind = c.history.kind
        if kind not in {"slice", "gate", "code-review", "follow-up"}:
            continue
        opening = trees.published(c, "trace", c.start.get("snapshot"))
        steered, locations = steering(c)
        row = dict(case_ref(c, c.data["end_location"]), unit=c.history.unit, kind=kind, reasons=[],
                   parameters={k: c.data[k] for k in ("docs", "slice", "tier", "host", "model", "effort")},
                   manifests=c.data["version"], opening=opening or UNKNOWN, steered=steered,
                   steering_locations=locations, score={})
        reasons = row["reasons"]
        if c.ambiguous:
            reasons.append("ambiguous unit identity")
        if not opening or not all(trees.commit(c.store, p) for p in opening["parents"]):
            reasons.append("opening snapshot unavailable")
            skipped = c.start.get("skipped")
            if isinstance(skipped, str) and re.fullmatch(r"no-git|changes-over-10MiB|(?:git [a-z-]+|index copy|alternates|"
                                                         r"snapshot lock): (?:E[A-Z0-9]+|exit -?\d+|timeout)", skipped):
                row["snapshot_issue"] = skipped
            else:
                row["snapshot_issue"] = "recorded snapshot unavailable" if c.start.get("snapshot") else UNKNOWN
        if kind == "slice":
            plans = [d for d in c.data["docs"] if d.startswith("P") and "@r" in d]
            match = slice_plan(c, c.store, opening["commit"], plans[0]) if opening and len(plans) == 1 else None
            if not match:
                reasons.append("slice or plan revision unavailable")
            row["score"] = dict(test_criteria=match["location"] if match else UNKNOWN,
                                worker_outcomes=[{k: a[k] for k in ("terminal", "report_status", "containment",
                                                                     "terminal_location")} for a in c.data["worker_attempts"]])
        else:
            review_input(c, trees, opening, row)
        row["reasons"] = list(dict.fromkeys(reasons))
        row["eligible"] = not reasons
        if row["eligible"]:
            eligible.append(case_ref(c, opening["location"]))
        rows.append(row)
    return dict(title="Replay eligibility and original scoring evidence", units=rows,
                eligible=ratio(len(eligible), len(rows), eligible, len(rows)))
