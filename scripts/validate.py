#!/usr/bin/env python3
"""Validate every skill under the category directories.

Usage: python3 scripts/validate.py
Exits non-zero if any skill fails validation.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = ROOT / "skills"
CATEGORIES = ("execution", "governance")
NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
BRAND = "canon"
MAX_NAME = 64
MAX_DESCRIPTION = 1024
MAX_LINES = 500
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
FENCE_RE = re.compile(r"^\s*(```|~~~)")
INLINE_CODE_RE = re.compile(r"`[^`]*`")


def link_targets(text):
    """Yield link targets outside fenced code blocks and inline code."""
    fence = None
    for line in text.splitlines():
        match = FENCE_RE.match(line)
        if match:
            fence = match.group(1) if fence is None else (None if fence == match.group(1) else fence)
            continue
        if fence is None:
            yield from LINK_RE.findall(INLINE_CODE_RE.sub("", line))


def parse_frontmatter(text):
    """Parse the flat `key: value` frontmatter used by SKILL.md, including `>`/`|` block scalars."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    try:
        end = next(i for i, line in enumerate(lines[1:], 1) if line.strip() == "---")
    except StopIteration:
        return None

    fields = {}
    key = None
    block = None
    for line in lines[1:end]:
        if block is not None and (line.startswith((" ", "\t")) or not line.strip()):
            block.append(line.strip())
            continue
        if block is not None:
            fields[key] = " ".join(part for part in block if part)
            block = None
        match = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if not match:
            continue
        key, value = match.group(1), match.group(2).strip()
        if value in (">", ">-", "|", "|-"):
            block = []
        else:
            fields[key] = value.strip("'\"")
    if block is not None:
        fields[key] = " ".join(part for part in block if part)
    return fields


def validate_skill(skill_dir):
    errors = []
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        return ["missing SKILL.md"]

    text = skill_md.read_text(encoding="utf-8")
    fields = parse_frontmatter(text)
    if fields is None:
        return ["SKILL.md must start with a `---` delimited YAML frontmatter block"]

    name = fields.get("name", "")
    if not name:
        errors.append("frontmatter is missing `name`")
    else:
        if name != skill_dir.name:
            errors.append(f"`name` ({name}) does not match directory name ({skill_dir.name})")
        if not NAME_RE.match(name):
            errors.append("`name` must use lowercase letters, digits and single hyphens only")
        if name != BRAND and not name.startswith(BRAND + "-"):
            errors.append(f"`name` must be `{BRAND}` or start with `{BRAND}-`")
        if len(name) > MAX_NAME:
            errors.append(f"`name` exceeds {MAX_NAME} characters")

    description = fields.get("description", "")
    if not description:
        errors.append("frontmatter is missing `description`")
    elif len(description) > MAX_DESCRIPTION:
        errors.append(f"`description` is {len(description)} characters (max {MAX_DESCRIPTION})")

    line_count = len(text.splitlines())
    if line_count > MAX_LINES:
        errors.append(f"SKILL.md has {line_count} lines (max {MAX_LINES})")

    for target in link_targets(text):
        if re.match(r"^[a-z]+:", target) or target.startswith("#"):
            continue
        if not (skill_dir / target.split("#", 1)[0]).exists():
            errors.append(f"broken relative link: {target}")

    return errors


def main():
    seen = {}
    failures = 0
    count = 0

    if SKILLS_DIR.is_dir():
        for entry in sorted(SKILLS_DIR.iterdir()):
            if entry.name.startswith(".") or entry.name in CATEGORIES:
                continue
            failures += 1
            print(f"FAIL {entry.relative_to(ROOT)}")
            print(f"  - unknown category; skills must live under skills/{{{','.join(CATEGORIES)}}}/<name>/")

    for category in CATEGORIES:
        category_dir = SKILLS_DIR / category
        if not category_dir.is_dir():
            continue
        for skill_dir in sorted(p for p in category_dir.iterdir() if p.is_dir() and not p.name.startswith(".")):
            count += 1
            rel = skill_dir.relative_to(ROOT)
            errors = validate_skill(skill_dir)
            if skill_dir.name in seen:
                errors.append(f"duplicate skill name, also defined in {seen[skill_dir.name]}")
            seen.setdefault(skill_dir.name, rel)
            if errors:
                failures += 1
                print(f"FAIL {rel}")
                for error in errors:
                    print(f"  - {error}")
            else:
                print(f"ok   {rel}")

    print(f"\n{count} skill(s) checked, {failures} problem(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
