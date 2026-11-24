"""Verify a review's archived scope and per-source input against the durable tree pair."""
import hashlib
import os
import re
import shlex
from pathlib import Path

from trace_records import UNKNOWN, canon, git_bytes, loc, snapshot_index
from trace_review_evidence import Archive, headings, scope_lines

HEX = re.compile(r"[0-9a-fA-F]{4,64}")



def archive_pin(archive, name):
    data = archive.read(name + ".txt")
    if data is None:
        return None
    pin = data.strip().decode("ascii", errors="replace")
    return pin.lower() if pin == "none" or canon.full_oid(pin) else UNKNOWN


def input_commit(case, trees, pin):
    if not pin or not HEX.fullmatch(pin):
        return None
    roots = [case.store, case.project / ".canon/canon/snapshots", case.project]
    resolved = {}
    for root in roots:
        oid = pin
        if not canon.full_oid(pin):
            value = git_bytes(root, "rev-parse", "--verify", "--quiet", pin + "^{commit}")
            if not value:
                continue
            oid = value.strip().decode("ascii")
            if not oid.startswith(pin.lower()):
                continue
        info = trees.commit(root, oid)
        if info:
            resolved[oid] = info
            if canon.full_oid(pin):
                break
    return next(iter(resolved.values())) if len(resolved) == 1 else None


def diff_scope(rows):
    """Parse only a literal Git diff and safe, reproducible options. Never execute prompt commands."""
    if any(label == "unverified scope" for label, _, _ in rows):
        return None
    candidates = []
    for label, value, _ in rows:
        if label not in {"target", "targets", "diff", "diff command"}:
            continue
        quoted = re.findall(r"\x60([^\x60]+)\x60", value)
        commands = [q for q in quoted if re.search(r"(?:^|\s)git\s+.*?\bdiff\b", q)]
        if not commands:
            inline = re.search(r"\bgit\s+(?:-C\s+\S+\s+)?diff\s+([^;(|]+)", value)
            commands = [inline[0].rstrip(" .")] if inline else []
        for command in commands:
            try:
                words = shlex.split(command)
            except ValueError:
                return None
            if not words or words[0] != "git" or "diff" not in words:
                return None
            args = words[words.index("diff") + 1:]
            limit = args.index("--") if "--" in args else len(args)
            flags, revisions = [], []
            for arg in args[:limit]:
                if arg in {"--binary", "--full-index", "--no-color", "--no-renames", "--find-renames",
                           "--minimal", "--patience", "--histogram", "--no-ext-diff", "--no-textconv"} or re.fullmatch(r"-U\d+", arg):
                    flags.append(arg)
                elif HEX.fullmatch(arg) or re.fullmatch(r"HEAD(?:~\d+)?", arg):
                    revisions.append(arg)
                elif re.fullmatch(r"[a-fA-F0-9]{4,64}\.\.[a-fA-F0-9]{4,64}", arg):
                    revisions.extend(arg.split(".."))
                else:
                    return None
            paths = args[limit + 1:]
            if len(revisions) not in {1, 2} or any("\0" in p for p in paths):
                return None
            candidates.append((revisions, flags, paths))
    if not candidates or not all(c == candidates[0] for c in candidates):
        return None
    revisions, flags, paths = candidates[0]
    declared = []
    for label, value, _ in rows:
        if label != "paths" or not value.strip():
            continue
        lexer = shlex.shlex(value, posix=True)
        lexer.quotes += chr(96)
        lexer.whitespace += ","
        lexer.whitespace_split = True
        lexer.commenters = ""
        try:
            declared.extend(lexer)
        except ValueError:
            return None
    if any(label == "paths" for label, _, _ in rows) and not declared:
        return None
    paths = sorted(set(paths))
    declared = sorted(set(declared))
    if paths and declared and paths != declared:
        return None
    return revisions, flags, paths or declared


def revision_pin(case, token):
    if not token:
        return None
    if re.fullmatch(r"HEAD(?:~\d+)?", token):
        head = case.start.get("head")
        if not canon.full_oid(head):
            return None
        resolved = git_bytes(case.project, "rev-parse", "--verify", "--quiet", head + token[4:] + "^{commit}")
        return resolved.strip().decode("ascii") if resolved else None
    return token


def matches_pin(case, trees, token, original, tree):
    token = revision_pin(case, token)
    if not token:
        return False
    if original and canon.full_oid(original) and token.lower() == original:
        return True
    source = input_commit(case, trees, token)
    return bool(source and source["tree"] == tree)


def listed_untracked(scope, files):
    values = [value for label, value, _ in scope if label == "untracked" and value.strip()]
    if not values:
        if any(re.search(r"\bno untracked (?:new )?files\b", value, re.I) for _, value, _ in scope):
            return []
        return None
    if all(re.fullmatch(r"\s*[*\x60(]*(?:none|no untracked files)[*\x60)]*[.!]?\s*", v, re.I) for v in values):
        return []
    paths = []
    for value in values:
        lexer = shlex.shlex(value, posix=True)
        lexer.quotes += "\x60"
        lexer.whitespace += ","
        lexer.whitespace_split = True
        lexer.commenters = ""
        try:
            tokens = list(lexer)
        except ValueError:
            return None
        for token in tokens:
            path = token[2:] if token.startswith("./") else token
            if path == "and" and path not in files:
                continue
            if path not in files and path.endswith("."):
                path = path[:-1]
            if path not in files:
                return None
            paths.append(path)
    return sorted(set(paths))


def code_scope(case, trees, scope, target, base, pins):
    diff = diff_scope(scope)
    if not diff or not base:
        return None
    revisions, flags, paths = diff
    if not matches_pin(case, trees, revisions[0], pins[0], base["tree"]):
        return None
    if len(revisions) == 2 and not matches_pin(case, trees, revisions[1], pins[1], target["tree"]):
        return None
    for path in paths:
        name = path[2:] if path.startswith("./") else path
        name = name.rstrip("/")
        if any(name == "." or p == name or p.startswith(name + "/")
               for tree in (target, base) for p in trees.files(case.store, tree["tree"])):
            continue
        # Ask Git about a nonliteral pathspec in the same isolated indexes.
        if not any(c in path for c in "*?[:"):
            return None
        for tree in (target, base):
            with snapshot_index(case.store, tree["tree"]) as env:
                if env and git_bytes(case.store, "ls-files", "-z", "--error-unmatch", "--", path, environment=env):
                    break
        else:
            return None
    options = ["diff", "--no-ext-diff", "--no-textconv", *flags]
    untracked = []
    if len(revisions) == 2:
        patch = git_bytes(case.store, *options, base["tree"], target["tree"], "--", *paths)
    else:
        files = trees.files(case.store, target["tree"])
        names = listed_untracked(scope, files)
        if names is None:
            return None
        for name in names:
            mode, oid = files[name]
            untracked.append(dict(mode=mode, blob=oid, location=target["location"] + ":" + name))
        if names:
            with snapshot_index(case.store, target["tree"]) as env:
                if env is None or git_bytes(case.store, "-c", "core.splitIndex=false", "update-index",
                                            "--force-remove", "-z", "--stdin", environment=env,
                                            data=b"".join(os.fsencode(n) + b"\0" for n in names)) is None:
                    return None
                patch = git_bytes(case.store, *options, "--cached", base["tree"], "--", *paths, environment=env)
        else:
            patch = git_bytes(case.store, *options, base["tree"], target["tree"], "--", *paths)
    if patch is None:
        return None
    return dict(form="prepared diff" if len(revisions) == 2 else "live diff",
                paths=paths, options=flags, untracked_files=untracked, patch_sha256=hashlib.sha256(patch).hexdigest())


def revision_documents(revisions, files, read):
    """Resolve named revisions uniquely in one tree and read their frozen frontmatter."""
    docs = {}
    for name in revisions:
        ref = re.fullmatch(r"([DP]\d{3,}[A-Z]?)@r([1-9]\d*)", name)
        if not ref:
            return None
        doc, revision = ref.groups()
        paths = [p for p in files if Path(p).name.startswith(doc + "-") and canon.FILE_RE.fullmatch(Path(p).name)
                 and re.search(r"(?:^|/)docs/(?:archived/)?(?:designs|plans)/[^/]+$", p)]
        if len(paths) != 1:
            return None
        data = read(paths[0])
        if data is None:
            return None
        fields = canon.parse_frontmatter(data.decode(errors="replace").splitlines())[0] or {}
        if str(fields.get("revision")) != revision:
            return None
        docs[paths[0]] = fields
    return docs


def target_documents(case, trees, target):
    files = trees.files(case.store, target["tree"])
    docs = revision_documents(case.start.get("docs", []), files,
                              lambda p: git_bytes(case.store, "cat-file", "blob", files[p][1]))
    return [(p, f.get("as_built")) for p, f in docs.items()] if docs is not None else None


def gate_scope(case, trees, scope, opening, target, base, pins, docs, reasons):
    named = set()
    for label, value, _ in scope:
        if label in {"target", "targets", "follow-on targets"}:
            named.update(re.findall(r"(?:[\w./-]+/)?docs/(?:archived/)?(?:designs|plans)/[DP]\d{3,}[A-Z]?-[a-z0-9-]+\.md", value))
    if not docs or len(named) != len(docs) or not all(any(n == p or n.endswith("/" + p) for n in named) for p, _ in docs):
        reasons.append("review targets or revisions unverified")
        return None
    changes = [v for label, v, _ in scope if label == "changes since"]
    if base or changes:
        token = re.match(r"\s*\x60?([a-fA-F0-9]{4,64})\b", changes[0]) if len(changes) == 1 else None
        if not base or not token or not matches_pin(case, trees, token[1], pins[0], base["tree"]):
            reasons.append("archived review baseline unverified")
            return None
    as_built = docs[0][1]
    claims = [value for label, value, _ in scope if label == "as-built"]
    checked = dict(form="document diff" if base else "full document", paths=[p for p, _ in docs])
    if as_built or claims or len(opening["parents"]) == 2:
        source = input_commit(case, trees, as_built) if isinstance(as_built, str) else None
        tokens = re.findall(r"(?<!\w)([0-9a-fA-F]{4,64})(?!\w)", claims[0]) if len(claims) == 1 else []
        code = trees.commit(case.store, opening["parents"][1]) if len(opening["parents"]) == 2 else None
        if not source or not code or not tokens or not all(source["commit"].startswith(t.lower()) for t in tokens):
            reasons.append("as-built code unverified")
            return None
        if code["tree"] != source["tree"]:
            reasons.append("as-built code tree differs")
            return None
        checked.update(as_built_tree=code["tree"], as_built_commit=source["commit"])
    return checked


def round_pair(case, trees, opening, archive, reports, reasons):
    target_pin = archive_pin(archive, "snapshot")
    base_pin = archive_pin(archive, "baseline")
    original = input_commit(case, trees, target_pin)
    if "review_input" not in case.end:
        if not original:
            reasons.append("legacy first-round target unverified")
            return None
        if original["tree"] != opening["tree"]:
            reasons.append("different opening and first-round targets")
            return None
        if base_pin is None:
            scopes = [scope_lines(archive, r["stem"]) for r in reports]
            named = []
            for scope in scopes:
                diff = diff_scope(scope)
                changes = [re.match(r"\s*\x60?([a-fA-F0-9]{4,64})\b", v) for k, v, _ in scope if k == "changes since"]
                named.append(revision_pin(case, diff[0][0]) if diff else changes[0][1] if len(changes) == 1 and changes[0]
                             else "none" if case.history.kind == "gate" and not changes else None)
            if named and all(p == named[0] for p in named):
                base_pin = named[0]
        actual_base = input_commit(case, trees, base_pin)
        base = None
        if actual_base and opening["parents"]:
            base = trees.commit(case.store, opening["parents"][0])
        if not (base_pin == "none" and case.history.kind == "gate") and (
                not base or not actual_base or base["tree"] != actual_base["tree"]):
            reasons.append("legacy first-round baseline unverified")
            return None
        return "independently verified opening", opening, base, actual_base["commit"] if actual_base else base_pin, target_pin
    target = trees.published(case, "review-input", case.end.get("review_input"))
    if not target or not canon.full_oid(target_pin):
        reasons.append("first-round target unverified")
        return None
    parents = target["parents"]
    base = trees.commit(case.store, parents[0]) if len(parents) == 1 else None
    if not ((base_pin == "none" and not parents and case.history.kind == "gate") or
            (canon.full_oid(base_pin) and base and not base["parents"])):
        reasons.append("first-round baseline unverified")
        return None
    for pin, info in ((target_pin, target), (base_pin, base)):
        source = input_commit(case, trees, pin)
        if source and (not info or source["tree"] != info["tree"]):
            reasons.append("archived pins disagree with retained trees")
            return None
    return "retained first round", target, base, base_pin, target_pin


def first_round_score(case, archive, review):
    """Resolve each source in the original dispositions to a first-round finding."""
    sources, later, unknown = {}, {}, []
    if "source_findings" in review:
        identified = {r["key"] for r in review["reports"] if r["identity"] in {"recorded", "verified"}}
        for claim in review["source_findings"]:
            store = sources if claim["phase"] == "first" else later
            store[claim["source"]] = claim
            if claim["phase"] == "first" and (claim["key"] not in identified or claim["disposition"] == UNKNOWN):
                unknown.append(dict(source=claim["source"], locations=claim["locations"]))
    else:
        for r in review["reports"]:
            name = r["stem"] + ".md"
            blob = archive.read(name)
            if r["identity"] != "recorded" or blob is None:
                unknown.append(dict(key=r["key"], locations=r["locations"]))
                continue
            def collect(blob, phase, target, name):
                try:
                    found = headings(blob, phase)
                except (ValueError, UnicodeError):
                    unknown.append(dict(key=r["key"], locations=[str(archive.files[name])]))
                    return
                for fid, (line, severity) in found.items():
                    ref = r["key"] + ":" + fid
                    target[ref] = dict(source=ref, severity=severity, locations=[loc(archive.files[name], line)])
            collect(blob, "first", sources, name)
            name = r["stem"] + "-confirm.md"
            confirmed = archive.read(name)
            if confirmed is not None:
                collect(confirmed, "confirmation", later, name)
    scored, seen, confirmation = [], set(), []
    for raw in review["raw_findings"]:
        by_decision = {}
        for ref in raw["by"]:
            if ref in later and ref not in sources:
                confirmation.append(dict(raw_row=raw["raw_row"], source=ref, locations=later[ref]["locations"]))
                continue
            if ref in seen or ref not in sources or ref in later:
                unknown.append(dict(source=ref, locations=[raw["location"]]))
                continue
            seen.add(ref)
            claim = sources[ref]
            decision = claim.get("disposition", raw["disposition"])
            if (review.get("evidence_mode") == "standalone table" and decision != raw["disposition"]
                and not claim.get("decision_location")):
                unknown.append(dict(source=ref, locations=claim["locations"], recorded=raw["disposition"]))
                decision = raw["disposition"]
            if decision != UNKNOWN:
                by_decision.setdefault(decision, []).append(ref)
        for decision, refs in by_decision.items():
            scoped = {k: raw[k] for k in ("raw_row", "location", "axis") if k in raw}
            severity = raw["severity"] if refs == raw["by"] else UNKNOWN
            if len(refs) == 1:
                severity = sources[refs[0]].get("severity", severity)
            scored.append(dict(scoped, by=refs, severity=severity, disposition=decision,
                               source_locations=[p for ref in refs for p in sources[ref]["locations"]]))
    for ref, claim in sources.items():
        if ref in seen:
            continue
        verified_decision = review.get("evidence_mode") != "standalone table" or claim.get("decision_location")
        if verified_decision and claim.get("raw_row") is None and claim.get("disposition") not in {None, UNKNOWN}:
            scored.append(dict(raw_row=None, by=[ref], severity=claim["severity"], disposition=claim["disposition"],
                               source_locations=claim["locations"]))
        else:
            unknown.append(dict(source=ref, locations=claim["locations"]))
    return dict(dispositions=scored, confirmation_only=confirmation, unverified_sources=unknown)


def review_input(case, trees, opening, row):
    reasons = row["reasons"]
    archive = Archive(case, {})
    review = case.data["review"]
    row["parameters"]["reviewers"] = [{k: r[k] for k in ("key", "role", "model", "session", "targets")} for r in review["reports"]]
    row["score"] = first_round_score(case, archive, review)
    if case.start.get("continues"):
        reasons.append("continuation")
    if case.history.kind == "follow-up":
        reasons.append("follow-up requires prior context")
    if case.data["outcome"] != "delivered":
        reasons.append("handoff" if case.data["outcome"] == "handoff" else "review not delivered")
    if not case.end or case.end.get("dispositions") is None:
        reasons.append("original dispositions unavailable")
    no_input = bool(reasons)
    if row["score"]["unverified_sources"]:
        reasons.append("first-round scoring sources unverified")
    if no_input:
        return
    reports = review["reports"]
    result = round_pair(case, trees, opening, archive, reports, reasons)
    if not result:
        return
    source, target, base, base_pin, target_pin = result
    pair = row["review_input"] = dict(source=source, target=target["commit"], target_tree=target["tree"],
                                      baseline=base["commit"] if base else "none", baseline_tree=base["tree"] if base else "none",
                                      target_pin=target_pin, baseline_pin=base_pin, roles=[],
                                      locations=[target["location"], *[str(archive.files[n]) for n in ("snapshot.txt", "baseline.txt")
                                                                      if n in archive.files]])
    scopes = []
    docs = target_documents(case, trees, target)
    if case.history.kind == "code-review" and case.start.get("docs") and not docs:
        reasons.append("review targets or revisions unverified")
    if not reports:
        reasons.append("first-round reports unavailable")
    for r in reports:
        stem = r["stem"]
        pin = archive_pin(archive, stem + "-snapshot")
        addresses = list(r["locations"])
        if pin:
            addresses.append(str(archive.files[stem + "-snapshot.txt"]))
        elif source == "independently verified opening" and r["key"] == r["role"] and r["key"] != UNKNOWN:
            # Early first rounds archived one pin for the initial dispatch.
            # A late or supplemental report needs its own evidence.
            pin = target_pin
            addresses.append(str(archive.files["snapshot.txt"]))
        scope = scope_lines(archive, stem)
        addresses.extend(line for _, _, line in scope)
        role = dict(key=r["key"], pin=pin or UNKNOWN, locations=addresses)
        pair["roles"].append(role)
        if r["identity"] not in {"recorded", "verified"} or stem not in archive.first_stems():
            reasons.append("first-round report unverified")
        if not matches_pin(case, trees, pin, target_pin, target["tree"]):
            reasons.append("supplemental input unverified" if r["key"] != r["role"] or r["key"] == UNKNOWN
                           else "first-round role input unverified")
            continue
        if case.history.kind == "gate":
            if r["targets"] != UNKNOWN and set(r["targets"]) != set(case.start["docs"]):
                reasons.append("different first-round targets")
            verified = gate_scope(case, trees, scope, opening, target, base, (base_pin, target_pin), docs, reasons)
        else:
            verified = code_scope(case, trees, scope, target, base, (base_pin, target_pin))
        if verified is None:
            reasons.append("archived prompt scope unverified")
            continue
        scopes.append(verified)
        role.update(form=verified["form"], scope_sha256=canon.sha256_json(verified, sort_keys=True))
    if scopes and not all(s == scopes[0] for s in scopes):
        reasons.append("different first-round scopes")
    if scopes:
        pair["form"] = scopes[0]["form"]
        pair.update({k: v for k, v in scopes[0].items() if k in {"patch_sha256", "untracked_files", "as_built_tree", "as_built_commit"}})
        return scopes[0]
