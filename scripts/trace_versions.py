"""Match captured skill content to reachable commits, including content reversions."""
from collections import defaultdict
import hashlib
import os
import re

from trace_records import UNKNOWN, canon, git_bytes

SHA256 = re.compile(r"[0-9a-f]{64}")
NAME = re.compile(r"canon(?:-[a-z0-9-]+)?")


def suite_entries(repo, tree, *, recorded=False):
    """Select exactly the trace manifest's regular files, grouped by installed name."""
    listing = git_bytes(repo, "ls-tree", "-rz", tree, *(("--", "skills") if not recorded else ()))
    if listing is None:
        return None
    dirs = defaultdict(dict)
    for record in listing.split(b"\0"):
        if not record:
            continue
        meta, path = record.split(b"\t", 1)
        mode, _, blob = meta.split()
        parts = os.fsdecode(path).split("/")
        # Also recognize the historical flat skills/<name>/ layout.
        indices = (0,) if recorded else (1, 2)
        index = next((i for i in indices if i < len(parts) - 1 and NAME.fullmatch(parts[i])), None)
        if index is None or mode not in (b"100644", b"100755"):
            continue
        rest = parts[index + 1:]
        if any(p.startswith(".") or p in ("LICENSE", "NOTICE", "__pycache__") or p.endswith(".pyc") for p in rest):
            continue
        dirs[tuple(parts[:index + 1])]["/".join(rest)] = (mode.decode("ascii"), blob.decode("ascii"))
    skills = {}
    for prefix, entries in sorted(dirs.items()):
        if "SKILL.md" in entries:
            skills.setdefault(prefix[-1], entries)
    return skills


def manifest_at(repo, tree):
    entries = suite_entries(repo, tree)
    if entries is None:
        return None
    manifest = {}
    for name, files in entries.items():
        digests = []
        for path, (_, oid) in sorted(files.items()):
            if len(oid) == 64:  # Capture always uses the SHA-1 Git blob identity.
                data = git_bytes(repo, "cat-file", "blob", oid)
                if data is None:
                    return None
                oid = hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()
            digests.append([path, oid])
        manifest[name] = canon.sha256_json(digests)
    return manifest


def valid_manifest(case, digest):
    rec = case.manifests.get(digest) or {}
    skills = rec.get("skills", {})
    if (not rec or not all(NAME.fullmatch(k) and isinstance(v, str) and SHA256.fullmatch(v)
                           for k, v in skills.items()) or canon.sha256_json(skills, sort_keys=True) != digest):
        return None
    return rec


def version_inventory(repo, selected, cases):
    repo = repo.resolve()
    units = {(c.store, c.history.unit): c for c in cases}
    observations = defaultdict(list)
    for c in cases:
        ends = [c.start]
        if c.end and (not c.start.get("parent") or "manifest" in c.end):
            ends.append(c.end)
        node, seen = c, set()
        while node and node.id not in seen:
            seen.add(node.id)
            observations[node.id].extend((e.get("manifest"), e["_location"]) for e in ends)
            node = units.get((node.store, node.start.get("parent")))
    manifests, skills = {}, {}
    for c in selected:
        evidence = observations[c.id]
        observed = {d for d, _ in evidence if isinstance(d, str) and SHA256.fullmatch(d)}
        status = "mixed" if len(observed) > 1 else (
            "single" if observed and all(isinstance(d, str) and d in observed for d, _ in evidence) else UNKNOWN)
        c.data["version"] = dict(status=status, manifests=sorted(observed), locations=[p for _, p in evidence])
        for digest in sorted(observed):
            entry = manifests.setdefault(digest, dict(digest=digest, commits=[], cases=[], locations=[]))
            entry["cases"].append(c.id)
            rec = valid_manifest(c, digest)
            if rec:
                if rec["_location"] not in entry["locations"]:
                    entry["locations"].append(rec["_location"])
                for name, value in rec["skills"].items():
                    skill = skills.setdefault((name, value), dict(skill=name, digest=value, commits=[], locations=[], cases=[]))
                    if c.id not in skill["cases"]:
                        skill["cases"].append(c.id)
                    if rec["_location"] not in skill["locations"]:
                        skill["locations"].append(rec["_location"])
    commits = git_bytes(repo, "log", "--all", "--no-show-signature", "--format=%H %T") if manifests else b""
    shallow = git_bytes(repo, "rev-parse", "--is-shallow-repository")
    complete = commits is not None and shallow == b"false\n"
    if commits:
        trees = defaultdict(list)
        for line in commits.decode("ascii").splitlines():
            commit, tree = line.split()
            trees[tree].append(commit)
        for tree, members in trees.items():
            content = manifest_at(repo, tree)
            if content is None:
                complete = False
                continue
            digest = canon.sha256_json(content, sort_keys=True)
            if digest in manifests:
                manifests[digest]["commits"].extend(members)
            for pair in content.items():
                if pair in skills:
                    skills[pair]["commits"].extend(members)
    for item in [*manifests.values(), *skills.values()]:
        item["status"] = "matched" if item["commits"] else ("local" if complete else UNKNOWN)
        item["commits"].sort()
    return dict(repository=str(repo), history="complete" if complete else UNKNOWN,
                manifests=list(manifests.values()), skills=list(skills.values()))
