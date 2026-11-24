"""Read the first-round reports retained by a review and its handoffs."""
from collections import Counter, defaultdict
import csv
from pathlib import Path
import re

from trace_records import UNKNOWN, canon, identifier, loc
from trace_review_receipts import EvidenceError, assignments, decision_record, digest, require, verified_dispatches

VALID = {"accepted", "deferred"}
HEADING = re.compile(r"^(?:#{1,4}\s+|\*\*)(F[1-9]\d*)\b", re.I)
FLATTENED_HEADING = re.compile(r"(?<!#)#{2,4}\s+(F[1-9]\d*)\b")
NEW_BLOCKER = re.compile(r"^\s*(?:- )?\*\*(?:New blocker — )?(F[1-9]\d*)\.", re.I)
ROLE_PREFIX = re.compile(r"^(?:same-model|spec|standards|cross-family)(?:-|$)")
STEM = re.compile(r"[A-Za-z0-9_-]{1,100}")
GROUP = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,99}")


LABEL = re.compile(r"^(targets?|follow-on targets|changes since|as-built|diff(?: command)?|"
                   r"untracked(?: [^:]{1,45})?|paths)(?:\s*:\s*(.*))?$", re.I)
LIST_FIELDS = {"target", "targets", "follow-on targets", "untracked", "paths"}
LIST_ITEM = re.compile(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)(.+)$")
CONCRETE_SCOPE = re.compile(r"\bgit\s+(?:-C\s+\S+\s+)?diff\b|\b[DP]\d{3,}[A-Z]?\b|"
                            r"(?:[\w.-]+/)+[\w.*-]+|[\w_-]+\.[A-Za-z][\w-]*|`[\w./*-]+`", re.I)


def scope_lines(archive, stem):
    name = stem + "-prompt.md"
    data = archive.read(name)
    if not data:
        return []
    rows, field, fence = [], None, None
    pending = None
    for n, raw in enumerate(data.decode("utf-8", errors="replace").splitlines(), 1):
        line = raw.strip()
        where = loc(archive.files[name], n)
        marker = re.match(r"^(`{3,}|~{3,})", line)
        if fence:
            if marker and marker[1][0] == fence[0] and len(marker[1]) >= len(fence):
                fence = None
                rows.append((field, "", where))
            elif field:
                rows.append((field, line, where))
                if line:
                    pending = None
            continue
        if marker and field:
            fence = marker[1]
            rows.append((field, "", where))
            continue
        header = re.sub(r"^#{1,6}\s+|\s+#+$", "", line)
        header = re.sub(r"^(?:[-*+]\s+)?(\*{1,3}|_{1,3})(.+?)\1(?=\s|:|$)", r"\2", header)
        if re.match(r"assess(?:\s*:|$)", header, re.I):
            break
        declaration = LABEL.fullmatch(header)
        if declaration:
            if pending:
                rows.append(("unverified scope", "", pending))
                pending = None
            label = declaration[1].lower()
            label = "untracked" if label.startswith("untracked") else label
            rows.append((label, declaration[2] or "", where))
            field = label if label in LIST_FIELDS else None
            value = declaration[2] or ""
            if field and (not value.strip() or re.search(r"\b(?:below|as follows|following (?:files|paths|targets))\b", value, re.I)):
                pending = where
        elif (re.search(r"\breview\b[^\n]*?\bagainst\b", line, re.I)
              and re.search(r"`git\s+(?:-C\s+\S+\s+)?diff\s+[^`]+`", line)):
            rows.append(("diff command", line, where))
            field = None
        elif field and line:
            item = LIST_ITEM.match(raw)
            if item or raw.startswith(("    ", "\t")) or re.fullmatch(r"[`\w./*-]+", line) and CONCRETE_SCOPE.search(line):
                rows.append((field, item[1] if item else line, where))
                pending = None
            elif line.startswith(">"):
                rows.append(("unverified scope", "", where))
                field = None
            else:
                field = None
    if pending or fence:
        rows.append(("unverified scope", "", pending or loc(archive.files[name], n)))
    return rows


class Archive:
    """Reused first-round files may survive only in the predecessor's one-time archive."""
    def __init__(self, case, units):
        self.files = {}
        self.cases = []
        self.rechecks = set()
        seen = set()
        while case and case.id not in seen:
            seen.add(case.id)
            self.cases.append(case)
            for evidence in (case.history.rechecks, case.history.conflicts):
                self.rechecks.update(r["report"] for events in evidence.values() for r in events)
            directory = case.store / case.history.unit
            if (case.end or {}).get("archive") == "ok" and not directory.is_symlink():
                try:
                    for p in directory.iterdir():
                        if not p.is_symlink() and p.is_file():
                            self.files.setdefault(p.name, p)
                except OSError:
                    pass
            prior = units.get((case.store, case.start.get("continues")))
            if not prior or prior.history.kind != case.history.kind or prior.data["outcome"] != "handoff":
                break
            case = prior
        self.later_confirmations = {name[:-10] for name in self.files if name.endswith("-prompt.md")
                                    and self.later_verdict(name[:-10])}

    def later_verdict(self, stem):
        """Some follow-on confirmations have an arbitrary stem. Require both sides of the same named check."""
        prompt = (self.read(stem + "-prompt.md") or b"").lstrip()
        instruction = re.match(rb"The author revised [^\n.]{0,250} after your (?:confirmation|recheck)\.\s+"
                               rb"Confirm (?:the new blocker )?([NF][1-9]\d*)\b", prompt, re.I)
        if not instruction:
            return False
        pin = self.read(stem + "-snapshot.txt") or b""
        report = (self.read(stem + ".md") or b"").decode(errors="replace")
        if not re.fullmatch(rb"[0-9a-fA-F]{40}(?:[0-9a-fA-F]{24})?", pin.strip()):
            return False
        headings = [s.strip("*# -\t") for s in report.splitlines()
                    if re.match(r"^\s*[*# -]*[NF][1-9]\d*\b", s, re.I)]
        verdict = re.compile(instruction[1].decode() + r"\s*[:—–-]?\s*(?:not[- ]resolved|resolved)\b", re.I)
        return bool(headings) and all(verdict.match(s) for s in headings)

    def read(self, name):
        path = self.files.get(name)
        if path:
            try:
                return path.read_bytes()
            except OSError:
                pass
        return None

    def first_stems(self):
        return {Path(name).stem for name in self.files if name.endswith(".md") and STEM.fullmatch(Path(name).stem) and
                (ROLE_PREFIX.match(Path(name).stem) or name[:-3] + "-prompt.md" in self.files)
                and not re.search(r"-(?:confirm|recheck\d*)(?:[-.]|$)|-(?:prompt|pending)\.md$", name)
                and Path(name).stem not in self.rechecks | self.later_confirmations}

    def prompt_stems(self):
        return {name[:-10] for name in self.files if name.endswith("-prompt.md")
                and not re.search(r"-(?:confirm|recheck\d*)(?:[-.]|$)", name)} - self.rechecks - self.later_confirmations


def headings(blob, phase="first", pinned=False):
    pattern = HEADING if phase == "first" else NEW_BLOCKER
    found = {}
    for index, line in canon.code_mask(blob.decode().splitlines()):
        number = index + 1
        match = pattern.match(line)
        if not match and pinned and phase == "first" and number == 1:
            # Some exports joined the host preamble to the first Markdown heading.
            # Accept that marker only when the table also pins its bytes and line.
            matches = list(FLATTENED_HEADING.finditer(line))
            match = matches[0] if len(matches) == 1 else None
        if match:
            fid = match[1].upper()
            if fid in found:
                raise ValueError("duplicate report finding")
            severity = re.search(r"\b(blocker|major|minor)\b", line[match.end():], re.I)
            found[fid] = (number, severity[1].lower() if severity else UNKNOWN)
    return found


def recorded_reports(case, archive):
    dispositions = (case.end or {}).get("dispositions") or {}
    registered = {r.get("key", r["role"]): r for r in dispositions.get("reviewers", [])}
    reports = []
    for stem in sorted(registered.keys() | archive.first_stems()):
        author = registered.get(stem, {})
        role = author.get("role", UNKNOWN)
        blob = archive.read(stem + ".md")
        state = UNKNOWN
        count = UNKNOWN
        locations = []
        if author:
            locations.append(case.end["_location"])
        if blob is not None:
            locations.append(str(archive.files[stem + ".md"]))
            try:
                count = len(headings(blob))
            except (UnicodeError, ValueError):
                pass
            if author:
                identity = archive.read(stem + "-id.txt")
                if identity is None or identity.strip() == (author.get("id") or "").encode():
                    state = "recorded"
                else:
                    state = "disputed"
        reports.append(dict(key=stem if author else UNKNOWN, stem=stem, role=role, model=author.get("model", UNKNOWN),
                            session=author.get("id") or UNKNOWN, targets=author.get("targets", UNKNOWN),
                            first_findings=count, identity=state, locations=locations))
    return reports


def read_table(path):
    result = defaultdict(list)
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream, delimiter="\t", strict=True)
        require(reader.fieldnames and {"project", "unit"} <= set(reader.fieldnames)
                and len(set(reader.fieldnames)) == len(reader.fieldnames), "invalid table header")
        for row in reader:
            require(None not in row and None not in row.values(), "incomplete table row")
            row["_location"] = loc(path, reader.line_num)
            result[row["project"], row["unit"]].append(row)
    return result


class ReviewEvidence:
    """Bind symbolic project labels by the selected path or unambiguous original end receipts."""
    def __init__(self, path, cases, database):
        self.rows, self.sources, self.receipts = {}, {}, {}
        self.keys = defaultdict(list)
        self.error = None
        self.has_catalog = False
        self.database = database
        if path is None:
            return
        try:
            self.rows = read_table(path)
            catalog = path.with_name("review-adjudications.tsv")
            self.has_catalog = catalog.is_file()
            if self.has_catalog:
                self.sources = read_table(catalog)
            host = path.with_name("review-host.tsv")
            if host.is_file():
                self.receipts = read_table(host)
        except (OSError, UnicodeError, csv.Error, EvidenceError):
            self.error = "unreadable or invalid review evidence"
            return
        projects = {c.project for c in cases}
        by_unit = defaultdict(list)
        for c in cases:
            by_unit[c.history.unit].append(c)
        labels = defaultdict(set)
        for label, uid in self.rows.keys() | self.sources.keys() | self.receipts.keys():
            labels[label].add(uid)
        for label, ids in labels.items():
            owners = {p for p in projects if str(p) == label or p.name.casefold() == label.casefold()}
            if not owners and "/" not in label:
                for uid in ids:
                    receipts = {r.get("end_sha256") for r in self.rows.get((label, uid), [])}
                    owners.update(c.project for c in by_unit[uid] if c.end and c.end["_sha256"] in receipts)
            for uid in ids:
                matches = [c for c in by_unit[uid] if c.project in owners]
                for c in matches:
                    self.keys[c.id].append((label, uid) if len(owners) == len(matches) == 1 else None)

    def apply(self, case, archive, review):
        keys = self.keys.get(case.id)
        if self.error:
            review.update(attribution=UNKNOWN, evidence_issue=self.error)
        elif keys:
            try:
                require(len(keys) == 1 and keys[0] and not case.ambiguous, "ambiguous project or review identity")
                key = keys[0]
                rows = self.rows.get(key, [])
                by_group = defaultdict(set)
                for r in rows:
                    name = r.get("defect_group", "")
                    if r.get("phase", "first") == "first" and GROUP.fullmatch(name) and name != UNKNOWN:
                        by_group[name].add(r.get("disposition"))
                review.update(evidence_mode="with report adjudications" if self.has_catalog else "standalone table",
                              adjudicated_valid_groups=sum(len(ds) == 1 and ds <= VALID for ds in by_group.values()),
                              evidence_locations=[r["_location"] for r in rows])
                result = adjudicate(case, archive, rows, self.sources.get(key, []),
                                    self.receipts.get(key, []), self.has_catalog, self.database)
                review.update(result)
            except (KeyError, ValueError, OSError, IndexError, TypeError, AttributeError) as e:
                review.update(attribution=UNKNOWN, evidence_issue=str(e) if isinstance(e, EvidenceError) else
                              "incomplete or invalid review evidence")


def prompt_scope(archive, stem, source):
    prompt = archive.read(stem + "-prompt.md")
    receipt, span = source.get("prompt_sha256"), source.get("scope_lines")
    if receipt:
        require(prompt is not None and digest(prompt) == receipt, "stale prompt digest")
    if not span:
        return None
    require(receipt and re.fullmatch(r"[1-9]\d*-[1-9]\d*", span), "invalid prompt scope")
    lo, hi = map(int, span.split("-"))
    lines = prompt.splitlines()
    require(lo <= hi <= len(lines), "invalid prompt scope")
    target = b"\n".join(lines[lo-1:hi]).strip()
    require(target, "empty prompt scope")
    declarations = scope_lines(archive, stem)
    if any(label == "unverified scope" for label, _, _ in declarations):
        return None
    if not any(label in {"target", "targets", "diff", "diff command"} and CONCRETE_SCOPE.search(value)
               for label, value, _ in declarations):
        return None
    if not all(lo <= int(place.rsplit("#L", 1)[1]) <= hi for _, _, place in declarations):
        return None
    return target


def source_inventory(case, archive, catalog, registered):
    first = {}
    all_stems = set()
    pending = []
    for src in catalog:
        stem, phase = src["report_stem"], src["phase"]
        require(STEM.fullmatch(stem) and stem not in all_stems and phase in {"first", "confirmation", "pending"},
                "ambiguous report inventory")
        all_stems.add(stem)
        blob = archive.read(stem + ".md")
        require(blob is not None and digest(blob) == src["report_sha256"], "missing or stale source report")
        key = src["reviewer_key"]
        require(src["role"] in canon.REVIEW_ROLES[case.history.kind] and canon.reviewer_key(src["role"], key),
                "invalid reviewer key or role")
        if phase == "pending":
            require(not src.get("groups"), "pending source has findings")
            pending.append(key)
        elif phase == "first":
            require(key not in first, "ambiguous independent report key")
            require(identifier(src["model"]) and (not src["reviewer_id"] or identifier(src["reviewer_id"])),
                    "invalid report identity")
            identity = archive.read(stem + "-id.txt")
            require(identity is not None and identity.decode().strip() == (src["reviewer_id"] or ""),
                    "archived reviewer identity mismatch")
            if key in registered:
                author = registered[key]
                require(stem == key and (src["role"], src["model"], src["reviewer_id"] or None) ==
                        (author["role"], author["model"], author["id"]), "recorded reviewer identity mismatch")
            first[key] = src
    require(registered.keys() <= first.keys() and archive.first_stems() ==
            {s["report_stem"] for s in first.values()}, "missing or unaccounted first-round report")
    pending_stems = {s["report_stem"] for s in catalog if s["phase"] == "pending"}
    require(pending_stems == {name[:-3] for name in archive.files if name.endswith("-pending.md")} and
            archive.prompt_stems() == {s["report_stem"] for s in first.values()} | {s.removesuffix("-pending") for s in pending_stems},
            "missing or unaccounted dispatch prompt")
    return first, pending


def standalone_inventory(case, archive, rows, registered):
    by_stem = defaultdict(list)
    for row in rows:
        by_stem[row["report_stem"]].append(row)
    sources = []
    for stem in sorted(by_stem.keys() | archive.first_stems() | registered.keys()):
        members = by_stem[stem]
        header = members[0] if members else {}
        phase = header.get("phase") or ("confirmation" if stem.endswith("-confirm") else "first")
        key = header.get("reviewer_key") or stem.removesuffix("-confirm")
        author = registered.get(key, {})
        role = next((r for r in canon.REVIEW_ROLES[case.history.kind] if canon.reviewer_key(r, key)), UNKNOWN)
        blob = archive.read(stem + ".md")
        require(STEM.fullmatch(stem) and blob is not None, "missing source report")
        identity = archive.read(stem + "-id.txt") or b""
        sources.append(dict(report_stem=stem, role=role, reviewer_key=key, model=author.get("model", UNKNOWN),
                            reviewer_id=identity.decode().strip(), phase=phase,
                            groups=" ".join(r["finding_id"] + "=" + r["defect_group"] for r in members),
                            decisions=" ".join(r["finding_id"] + "=" + r["disposition"] for r in members),
                            report_sha256=header.get("report_sha256", digest(blob)), scope_lines=header.get("scope_lines", ""),
                            prompt_sha256=header.get("prompt_sha256", ""),
                            _location=header.get("_location", str(archive.files[stem + ".md"]))))
    return sources


def adjudicate(case, archive, rows, catalog, receipts, has_catalog, database):
    disp = (case.end or {}).get("dispositions")
    require(disp and case.end.get("archive") == "ok", "missing review end or archive")
    registered = {r.get("key", r["role"]): r for r in disp["reviewers"]}
    raw = {}
    for number, f in enumerate(disp["findings"], 1):
        for ref in f["by"]:
            require(ref not in raw, "ambiguous raw source")
            raw[ref] = number, f
    if not has_catalog:
        catalog = standalone_inventory(case, archive, rows, registered)
    first, pending = source_inventory(case, archive, catalog, registered)
    dispatches, parent_decisions = (verified_dispatches(case, archive, first, registered, receipts, database, has_catalog)
                                   if has_catalog or receipts else ({}, {}))
    known = registered.keys() | dispatches.keys()
    scopes = [prompt_scope(archive, s["report_stem"], s) for s in first.values()]
    comparable = len(scopes) >= 2 and None not in scopes and len(set(scopes)) == 1 and first.keys() <= known
    indexed = {(r["report_stem"], r["finding_id"]): r for r in rows}
    require(len(indexed) == len(rows), "duplicate table finding")
    claims, reports, covered = [], [], set()
    pins = {}
    for src in catalog:
        stem, key, phase = src["report_stem"], src["reviewer_key"], src["phase"]
        if phase == "pending":
            continue
        path = archive.files[stem + ".md"]
        found = headings(archive.read(path.name), phase, pinned=True)
        groups, decisions = assignments(src["groups"]), assignments(src.get("decisions", ""))
        decision_location = decision_record(archive, src, parent_decisions) if has_catalog else None
        require(found.keys() == groups.keys() and decisions.keys() <= groups.keys(), "incomplete source coverage")
        if phase == "first":
            reports.append(dict(key=key, stem=stem, role=src["role"], model=src["model"],
                                session=src["reviewer_id"] or UNKNOWN, targets=registered.get(key, {}).get("targets", UNKNOWN),
                                first_findings=len(found), identity="verified" if key in known else UNKNOWN,
                                locations=[str(path), src["_location"], *dispatches.get(key, [])]))
        for fid, (line, severity) in found.items():
            row = indexed.pop((stem, fid), None)
            require(row and row["end_sha256"] == case.end["_sha256"] and row["report_sha256"] == src["report_sha256"],
                    "missing evidence or stale digest")
            ref = key + ":" + fid
            number, original = raw.get(ref, (None, {}))
            raw_disposition = original.get("disposition", "")
            require((not number or ref not in covered) and row["raw_row"] == (str(number) if number else "") and
                    row.get("raw_disposition", raw_disposition) == raw_disposition, "raw disposition reference mismatch")
            if number:
                covered.add(ref)
            require(row["source_locator"] == f"{stem}.md:L{line}" and row.get("reviewer_key", key) == key and
                    row.get("phase", phase) == phase, "claim locator or identity mismatch")
            require(all(k not in row or row[k] == src.get(k, "") for k in ("prompt_sha256", "scope_lines")),
                    "scope receipt mismatch")
            require(GROUP.fullmatch(row["defect_group"]) and GROUP.fullmatch(groups[fid]), "invalid defect group")
            decision = row["disposition"]
            if has_catalog and number and decision != raw_disposition:
                require(decision_location, "uncorroborated change of disposition")
            if has_catalog and not number and decision != UNKNOWN and (key in registered or decision != "accepted"):
                require(decision_location, "uncorroborated disposition of omitted finding")
            require(decision in (*canon.REVIEW_DISPOSITIONS, UNKNOWN) and decision == decisions.get(fid, raw_disposition or UNKNOWN),
                    "disposition disagrees with source")
            claims.append(dict(source=ref, key=key, role=src["role"], phase=phase, raw_row=number,
                               severity=severity, raw_severity=original.get("severity"), raw_sources=original.get("by", []),
                               axis=original.get("axis"), disposition=decision,
                               group=row["defect_group"], independent_group=groups[fid],
                               raw_disposition=raw_disposition or None, decision_location=decision_location,
                               locations=[loc(path, line), row["_location"], src["_location"], case.end["_location"],
                                          *([decision_location] if decision_location else []), *dispatches.get(key, [])]))
            pins[phase, ref] = dict(report_sha256=src["report_sha256"], decision_sha256=src.get("decision_sha256") or None,
                                    decision_location=decision_location)
    require(not indexed and covered == raw.keys(), "unmatched table or raw finding")
    if not has_catalog:
        grouped = defaultdict(set)
        for c in claims:
            if c["phase"] == "first":
                grouped[c["group"]].add(c["source"])
        for c in claims:
            f = raw.get(c["source"], (None, {}))[1]
            if (c["key"] not in registered or c["disposition"] != f.get("disposition") or
                set(f.get("by", [])) != grouped[c["group"]]):
                c["independent_group"] = UNKNOWN
    case.adjudication_pins = pins
    return summarize(claims, reports, pending, comparable, case.data["outcome"])


def summarize(claims, reports, pending, comparable, outcome):
    first = [c for c in claims if c["phase"] == "first"]
    members = defaultdict(list)
    for c in first:
        if c["group"] != UNKNOWN:
            members[c["group"]].append(c)
    groups = []
    keys = [r["key"] for r in reports]
    joint, exclusive, single = (dict.fromkeys(keys, 0) for _ in range(3))
    supplied = verified = 0
    for name, rows in members.items():
        decisions = {r["disposition"] for r in rows}
        decision = next(iter(decisions)) if len(decisions) == 1 else UNKNOWN
        corroborated = (all(c["independent_group"] == name for c in rows) and
                        all(c["group"] == name for c in first if c["independent_group"] == name))
        contributors = sorted({r["key"] for r in rows})
        category = "joint" if len(contributors) > 1 else "exclusive" if comparable else "single_source_unknown"
        sources = {r["source"] for r in rows}
        # A merged row records the maximum over all its sources. Splitting it
        # cannot assign that maximum to either subgroup independently.
        severities = {r["raw_severity"] if r["raw_sources"] and sources.issuperset(r["raw_sources"]) else r["severity"]
                      for r in rows}
        severity = next((s for s in ("blocker", UNKNOWN, "major", "minor") if s in severities), UNKNOWN)
        high = True if severities & {"major", "blocker"} else (UNKNOWN if UNKNOWN in severities else False)
        axes = sorted({r["role"] if r["role"] in {"spec", "standards"} else r["axis"] for r in rows} - {None})
        group = dict(group=name, sources=[r["source"] for r in rows], keys=contributors, roles=sorted({r["role"] for r in rows}),
                     axes=axes, disposition=decision, severity=severity, blocker_or_major=high,
                     attribution=category if corroborated else "unverified",
                     locations=list(dict.fromkeys(l for r in rows for l in r["locations"])))
        groups.append(group)
        if decision in VALID:
            supplied += 1
            if corroborated:
                verified += 1
                counts = {"joint": joint, "exclusive": exclusive, "single_source_unknown": single}[category]
                for k in contributors:
                    counts[k] += 1
    complete = (all(g["attribution"] != "unverified" and g["disposition"] != UNKNOWN for g in groups)
                and all(c["group"] != UNKNOWN and c["disposition"] != UNKNOWN for c in first))
    return dict(attribution="verified" if complete else "partial",
                reports=reports, pending=pending, comparable_scope=comparable, first_findings=len(first),
                omitted=sum(c["raw_row"] is None for c in first), confirmation_only=len(claims) - len(first),
                first_dispositions=dict(Counter(c["disposition"] for c in first)), source_findings=claims, groups=groups,
                disputed_first_sources=sum(c["group"] == UNKNOWN for c in first),
                adjudicated_valid_groups=supplied, valid_first_groups=verified if outcome == "delivered" else UNKNOWN,
                joint=joint, exclusive=exclusive, single_source_unknown=single)
