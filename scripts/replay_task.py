"""Resolve neutral requirements and explicit acceptance criteria from the frozen input."""
import os
from pathlib import Path
import re

from replay_git import ReplayError, git, oid, sha256
from replay_storage import decode
from trace_records import canon
from trace_review_evidence import Archive


def plan_sections(root, target, revision):
    name, rev = revision.split("@r")
    paths = [Path(os.fsdecode(raw)) for raw in git(root, "ls-tree", "-rz", "--name-only", target).split(b"\0") if raw]
    matches = [p for p in paths if p.name.startswith(name + "-") and canon.FILE_RE.fullmatch(p.name)
               and (p.parts[-3:-1] == ("docs", "plans") or p.parts[-4:-1] == ("docs", "archived", "plans"))]
    if len(matches) != 1:
        return {}
    path = matches[0].as_posix()
    blob = oid(root, "rev-parse", target + ":" + path)
    raw = git(root, "cat-file", "blob", blob).decode()
    doc = canon.Doc(None, root / path, path, canon.FILE_RE.fullmatch(matches[0].name), False, raw)
    span = doc.section_span("Slices")
    if not span or str(doc.revision) != rev:
        return {}
    first = doc.headings[span[0]].line
    markers = [h for h in doc.headings if first < h.line < span[1] and h.level == 3]
    lines = raw.splitlines(keepends=True)
    sections = {}
    for i, h in enumerate(markers):
        match = re.match(r"(S\d+)\b", h.text)
        if not match:
            continue
        sid = match[1]
        if sid in sections:
            return {}
        stop = markers[i + 1].line if i + 1 < len(markers) else min(span[1], len(lines))
        text = "".join(lines[h.line:stop])
        sections[sid] = dict(slice=sid, revision=revision, path=path, blob=blob, first_line=h.line + 1,
                             last_line=stop, text=text, sha256=sha256(text.encode()))
    return sections


STRUCTURAL = re.compile(r"^(?:[-*]\s+)?(?:\*\*)?(?:Status|Risk)(?:\*\*)?\s*:", re.I)


def acceptance_lines(section):
    lines = section["text"].splitlines(keepends=True)
    prose = {idx for idx, _ in canon.code_mask(lines)}
    return [(section["first_line"] + i, line) for i, line in enumerate(lines) if i and
            (i not in prose or not STRUCTURAL.match(line.strip()))]


SLICE_SELECTION = re.compile(r"(?<![a-z0-9])(S\d+)\b(?:\s*(?:through|to|[-–—]|\.\.)\s*(S\d+)\b)?", re.I)


def selected_sections(sections, phrase):
    if re.search(r"\b(?:except|excluding|exclude|skip|omit|without|not)\b", phrase, re.I):
        return []
    order = list(sections)
    selected = set()
    for match in SLICE_SELECTION.finditer(phrase.upper()):
        first, last = match.groups()
        if first not in sections or (last and (last not in sections or order.index(first) > order.index(last))):
            return []
        if not last and re.match(r"\s*(?:through\b|to\s*[.,;]?$|[-–—]|\.\.)", phrase[match.end():], re.I):
            return []
        selected.update(order[order.index(first):order.index(last or first) + 1])
    if re.search(r"\b(?:(?:whole|entire|full)[- ]plan|(?:all(?: the)? slices|every slice))\b", phrase, re.I):
        if selected and re.search(r"\b(?:only|limited to|solely)\b", phrase, re.I):
            return []
        return list(sections.values())
    return [section for sid, section in sections.items() if sid in selected]


def review_delivery(case, root, target):
    if case.history.kind != "code-review":
        return None
    archive = Archive(case, {})
    requirements = {}
    for report in case.data["review"]["reports"]:
        name = report["stem"] + "-prompt.md"
        body = archive.read(name)
        if body is None:
            return None
        for i, line in canon.code_mask(body.decode().splitlines()):
            match = re.match(r"^\s*(?:[-*]\s+)?(?:\*\*)?Requested delivery\s*:\s*(?:\*\*)?\s*(.+?)\s*$", line, re.I)
            if match:
                requirements.setdefault(match[1], []).append(f"{archive.files[name]}#L{i+1}")
    if len(requirements) > 1:
        return None
    phrase = next(iter(requirements), "")
    if re.fullmatch(r"(?:(?:task |delivery )?scope (?:is )?)?(?:unknown|unavailable|not provided|unspecified)[.!]?",
                    phrase, re.I):
        return None
    plans = [r for r in case.data["docs"] if re.fullmatch(r"P\d+[A-Z]?@r\d+", r)]
    if not plans:
        return dict(text=phrase, source=requirements[phrase], sha256=sha256(phrase.encode())) if phrase else None
    if len(plans) != 1:
        return None
    plan, revision = plans[0].split("@r")
    named = re.findall(r"(?<![a-z0-9])(P\d{3,}[A-Z]?)(?:@r(\d+))?\b", phrase, re.I)
    if any(pid.upper() != plan or (rev and rev != revision) for pid, rev in named):
        return None
    sections = plan_sections(root, target, plans[0])
    selected = selected_sections(sections, phrase)
    if not selected:
        return None
    paragraphs, sources = [], []
    for section in selected:
        body = "".join(line for _, line in acceptance_lines(section)).strip()
        if not body:
            return None
        paragraphs.append(section["text"].splitlines()[0] + "\n\n" + body)
        sources.append({k: section[k] for k in ("slice", "revision", "path", "blob", "first_line", "last_line")})
    text = "\n\n".join(paragraphs)
    return dict(text=text, source=sources, sha256=sha256(text.encode()))


def criteria_for(section, mapping):
    keys = ("first_line", "last_line", "text")
    if mapping is None:
        return [dict(id=section["slice"], argv=None, **{k: section[k] for k in keys})]
    try:
        spec = decode(mapping.read_bytes(), "criteria mapping")
    except OSError as exc:
        raise ReplayError(f"unreadable criteria mapping: {exc}") from exc
    if (not isinstance(spec, dict) or type(spec.get("schema")) is not int or spec["schema"] != 1 or
            spec.get("slice") != section["slice"] or spec.get("plan_blob") != section["blob"] or
            not isinstance(spec.get("criteria"), list)):
        raise ReplayError("criteria mapping does not match the frozen plan blob and slice")
    items, ids, covered = [], set(), set()
    first = section["first_line"]
    lines = section["text"].splitlines(keepends=True)
    for entry in spec["criteria"]:
        if not isinstance(entry, dict):
            raise ReplayError("invalid criteria entry")
        name, lo, hi, argv = (entry.get(k) for k in ("id", "first_line", "last_line", "argv"))
        if (not isinstance(name, str) or not name.strip() or name in ids or
                type(lo) is not int or type(hi) is not int or not first <= lo <= hi <= section["last_line"] or
                "argv" not in entry or (argv is not None and (not isinstance(argv, list) or not argv or
                    not all(isinstance(a, str) and "\0" not in a for a in argv) or not argv[0]))):
            raise ReplayError("invalid criteria ID, range or argv")
        ids.add(name)
        covered.update(range(lo, hi + 1))
        items.append(dict(id=name, first_line=lo, last_line=hi, argv=argv, text="".join(lines[lo-first:hi-first+1])))
    remaining = [n for n, line in acceptance_lines(section) if line.strip() and n not in covered]
    while remaining:
        lo = hi = remaining.pop(0)
        while remaining and remaining[0] == hi + 1:
            hi = remaining.pop(0)
        name = f"unmapped-{lo}"
        while name in ids:
            name += "-"
        ids.add(name)
        items.append(dict(id=name, first_line=lo, last_line=hi, argv=None, text="".join(lines[lo-first:hi-first+1])))
    return sorted(items, key=lambda c: c["first_line"])
