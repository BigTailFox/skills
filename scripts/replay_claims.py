"""Interpret a sealed first-round report using the same finding headings as the trace reader."""
import re

from trace_review_evidence import headings
from trace_records import canon


SECTION = re.compile(r"(questions?|verdict|assessment)\s*(?:(:)\s*(.*))?", re.I)
EMPTY = re.compile(r"(?:no (?:actionable |valid )?findings?(?: (?:found|identified))?|no issues(?: found)?)\s*[.!]?", re.I)


def section(line):
    line = line.strip().replace("**", "").replace("__", "")
    heading = re.match(r"^#{1,6}\s+", line)
    match = SECTION.fullmatch(line[heading.end():] if heading else line)
    if match and (match[2] or heading):
        return match[1].lower(), (match[3] or "").strip(" *_.!")
    return None


def complete_empty(prose, fields, verdict, corroborated):
    if any(re.match(r"^\s*[#*_ -]*F\d+\b", line, re.I) for line in prose.values()):
        return False
    lines = [line.strip() for line in prose.values() if line.strip()]
    if not verdict:
        return bool(corroborated and len(lines) == 1 and EMPTY.fullmatch(lines[0]))
    if verdict not in ("approve", "sound"):
        return False
    questions = [n for n, (name, _) in fields.items() if name in ("question", "questions")]
    if questions:
        return len(questions) == 1 and all(
            EMPTY.fullmatch(line.strip()) or re.fullmatch(r"No (?:actionable )?findings? for\s+.+", line.strip(), re.I)
            for n, line in prose.items() if n < questions[0] and line.strip())
    return bool((len(lines) == 2 and EMPTY.fullmatch(lines[0])) or (corroborated and len(lines) == 1))


def report_claims(data, role, *, pinned=False, corroborated_empty=False):
    try:
        positions = list(headings(data, pinned=pinned).items())
        lines = data.decode().splitlines(keepends=True)
    except (UnicodeError, ValueError):
        return False, []
    prose = dict(canon.code_mask(lines))
    fields = {n: value for n, line in prose.items() if (value := section(line))}
    last = max((n for n, line in enumerate(lines) if line.strip()), default=-1)
    name, value = fields.get(last, (None, ""))
    verdict = value.lower() if name in ("verdict", "assessment") else None
    if not positions:
        shorthand = corroborated_empty and sum(bool(line.strip()) for line in lines) == 1
        return complete_empty(prose, fields, verdict, shorthand), []
    valid = verdict in ("approve", "revise", "sound")
    claims = []
    for i, (fid, (first, severity)) in enumerate(positions):
        stop = positions[i+1][1][0] - 1 if i+1 < len(positions) else len(lines)
        last_line = next((j for j in range(first, stop) if j in fields), stop)
        while last_line > first and not lines[last_line - 1].strip():
            last_line -= 1
        text = "".join(lines[first-1:last_line])
        description = re.sub(r"^(?:#{1,4}\s+|\*\*)F\d+\b[\s.:*—–-]*\[?(?:blocker|major|minor)\]?[\s.:*—–-]*",
                             "", text, flags=re.I)
        if severity not in ("blocker", "major", "minor") or not description.strip():
            valid = False
            continue
        claims.append(dict(role=role, finding=fid, severity=severity, first_line=first, last_line=last_line, text=text))
    return valid, claims
