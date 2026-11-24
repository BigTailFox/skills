"""Interpret a sealed first-round report using the same finding headings as the trace reader."""
import re

from trace_review_evidence import headings


TERMINATOR = re.compile(r"^\s*(?:#{1,6}\s*)?(?:\*{1,2})?(?:questions?|verdict|assessment)\b\s*[:*]*", re.I)
VERDICT = re.compile(r"(?:verdict|assessment)\s*:\s*(approve|revise|sound)\s*[.!]?", re.I)
EMPTY = re.compile(r"(?:no (?:actionable |valid )?findings?(?: (?:found|identified))?|no issues(?: found)?)\s*[.!]?", re.I)


def report_claims(data, role):
    try:
        positions = list(headings(data).items())
        lines = data.decode().splitlines(keepends=True)
    except (UnicodeError, ValueError):
        return False, []
    nonblank = [line.strip().strip("#* ").strip() for line in lines if line.strip()]
    last = VERDICT.fullmatch(nonblank[-1].replace("**", "")) if nonblank else None
    if not positions:
        if len(nonblank) == 1 and EMPTY.fullmatch(nonblank[0]):
            return True, []
        explicit_empty = any(EMPTY.fullmatch(line) for line in nonblank)
        valid = bool(last and last[1].lower() in ("approve", "sound") and (explicit_empty or len(nonblank) == 1))
        return valid and not any(re.match(r"^\s*F\d+\b", line, re.I) for line in nonblank), []
    valid = bool(last)
    claims = []
    for i, (fid, (first, severity)) in enumerate(positions):
        stop = positions[i+1][1][0] - 1 if i+1 < len(positions) else len(lines)
        last_line = next((j for j in range(first, stop) if TERMINATOR.match(lines[j])), stop)
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
