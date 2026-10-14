#!/usr/bin/env python3
"""Validate every skill under the category directories, the README skill list and the canon.py version,
then run the tests in tests/.

Usage: python3 scripts/validate.py
Exits non-zero if any check or test fails.
"""

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = ROOT / "skills"
TESTS_DIR = ROOT / "tests"
CATEGORIES = ("execution", "governance")
NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
BRAND = "canon"
MAX_NAME = 64
MAX_DESCRIPTION = 1024
MAX_LINES = 500
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
FENCE_RE = re.compile(r"^\s*(```|~~~)")
INLINE_CODE_RE = re.compile(r"`[^`]*`")
SKILL_LIST = "## Skills"
SKILL_ROW_RE = re.compile(r"^\|\s*`([a-z0-9-]+)`\s*\|.*\|\s*([^|]+?)\s*\|\s*$")
TRIGGER = {False: "Auto", True: "Manual"}
IMPLICIT_RE = re.compile(r"^\s*allow_implicit_invocation:\s*['\"]?(\w+)", re.M)
CANON_SCRIPT = "skills/governance/canon/scripts/canon.py"
VERSION_RE = re.compile(r'^CANON_VERSION = "\d+"', re.M)


def git(*args):
    try:
        result = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
    except FileNotFoundError:
        return None
    return result.stdout if result.returncode == 0 else None


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


def broken_links(md, base):
    errors = []
    for target in link_targets(md.read_text(encoding="utf-8")):
        if re.match(r"^[a-z]+:", target) or target.startswith("#"):
            continue
        if not (md.parent / target.split("#", 1)[0]).exists():
            errors.append(f"broken relative link in {md.relative_to(base).as_posix()}: {target}")
    return errors


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
    """Return the skill's errors and whether it is user-invoked (None when SKILL.md is unreadable)."""
    errors = []
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        return ["missing SKILL.md"], None

    text = skill_md.read_text(encoding="utf-8")
    fields = parse_frontmatter(text)
    if fields is None:
        return ["SKILL.md must start with a `---` delimited YAML frontmatter block"], None

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
    if ": " in description:
        errors.append("`description` contains `: `, which breaks YAML parsing of a plain scalar")

    line_count = len(text.splitlines())
    if line_count > MAX_LINES:
        errors.append(f"SKILL.md has {line_count} lines (max {MAX_LINES})")

    for md in sorted(skill_dir.rglob("*.md")):
        errors += broken_links(md, skill_dir)

    manual = fields.get("disable-model-invocation", "").lower() == "true"
    policy = skill_dir / "agents" / "openai.yaml"
    implicit = IMPLICIT_RE.search(policy.read_text(encoding="utf-8")) if policy.is_file() else None
    implicit_off = implicit is not None and implicit.group(1).lower() == "false"
    if manual and not implicit_off:
        errors.append("`disable-model-invocation: true` needs agents/openai.yaml with "
                      "`policy: allow_implicit_invocation: false` so Codex keeps it manual too")
    if implicit_off and not manual:
        errors.append("agents/openai.yaml disables implicit invocation; set `disable-model-invocation: true` too")

    return errors, manual


def check_readme(skills):
    """The README skill list must name every skill once, under its category, with its trigger mode."""
    readme = ROOT / "README.md"
    errors = []
    rows = {}
    in_list, category = False, None
    for line in readme.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            in_list = line.strip() == SKILL_LIST
        elif in_list and line.startswith("### "):
            category = line[4:].strip()
        elif in_list and (match := SKILL_ROW_RE.match(line)):
            name, trigger = match.groups()
            if name in rows:
                errors.append(f"skill list names `{name}` twice")
            rows[name] = (category, trigger)
    for name, (expected_category, manual) in sorted(skills.items()):
        if name not in rows:
            errors.append(f"skill list is missing `{name}`")
            continue
        listed_category, trigger = rows[name]
        if listed_category != expected_category:
            errors.append(f"`{name}` is listed under {listed_category} but lives in {expected_category}")
        if manual is not None and trigger != TRIGGER[manual]:
            errors.append(f"`{name}` is listed as {trigger}; its frontmatter makes it {TRIGGER[manual]}")
    for name in sorted(set(rows) - set(skills)):
        errors.append(f"skill list names `{name}`, which is not a skill")
    return errors


def check_canon_version():
    """Projects upgrade their canon.py copy by CANON_VERSION, so every change to canon.py needs a new version."""
    text = (ROOT / CANON_SCRIPT).read_text(encoding="utf-8")
    match = VERSION_RE.search(text)
    if not match:
        return ["no `CANON_VERSION = \"<n>\"` line"]
    head = git("show", "HEAD:" + CANON_SCRIPT)
    head_match = VERSION_RE.search(head) if head is not None else None
    if head_match is None or head_match.group(0) != match.group(0):
        return []
    since = (git("log", "-1", "--format=%H", "-S" + match.group(0), "--", CANON_SCRIPT) or "").strip()
    released = git("show", since + ":" + CANON_SCRIPT) if since else None
    if released is not None and released != text:
        return [f"changed since commit {since[:12]} set {match.group(0)}; bump CANON_VERSION"]
    return []


def run_tests():
    if not TESTS_DIR.is_dir():
        return []
    result = subprocess.run([sys.executable, "-B", "-m", "unittest", "discover", "-s", str(TESTS_DIR)],
                            cwd=ROOT, capture_output=True, text=True)
    return [] if result.returncode == 0 else [result.stderr.rstrip()]


def report(label, errors):
    if not errors:
        print(f"ok   {label}")
        return 0
    print(f"FAIL {label}")
    for error in errors:
        print(f"  - {error}")
    return 1


def main():
    failures = 0
    skills = {}

    if SKILLS_DIR.is_dir():
        for entry in sorted(SKILLS_DIR.iterdir()):
            if entry.name.startswith(".") or entry.name in CATEGORIES:
                continue
            failures += report(entry.relative_to(ROOT), [
                f"unknown category; skills must live under skills/{{{','.join(CATEGORIES)}}}/<name>/"])

    for category in CATEGORIES:
        category_dir = SKILLS_DIR / category
        if not category_dir.is_dir():
            continue
        for skill_dir in sorted(p for p in category_dir.iterdir() if p.is_dir() and not p.name.startswith(".")):
            errors, manual = validate_skill(skill_dir)
            if skill_dir.name in skills:
                errors.append(f"duplicate skill name, also defined in skills/{skills[skill_dir.name][0]}")
            skills.setdefault(skill_dir.name, (category, manual))
            failures += report(skill_dir.relative_to(ROOT), errors)

    for md in sorted(ROOT.glob("*.md")):
        errors = broken_links(md, ROOT)
        if md.name == "README.md":
            errors += check_readme(skills)
        failures += report(md.name, errors)
    if (ROOT / CANON_SCRIPT).is_file():
        failures += report(CANON_SCRIPT + " version", check_canon_version())
    failures += report("tests", run_tests())
    print(f"\n{len(skills)} skill(s) checked, {failures} problem(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
