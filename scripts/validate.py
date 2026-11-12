#!/usr/bin/env python3
"""Validate every skill under the category directories, that no SKILL.md lies elsewhere, the README skill list,
the canon.py version and D001's text budgets, then run the tests in tests/.

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
TRACE_CALL_RE = re.compile(r"`canon\.py trace (?:start|end) [^`]*`")
LIST_MARKER_RE = re.compile(r"^\s*(?:\d+\.|[-*])\s+")
SENTENCE_END_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\0(\[*_\"'])")
CALL_SITE_TOKENS = 40
PLACEHOLDERS = ("skills/governance/canon/SKILL.md", "In `trace` calls", 110)
TRACE_MD = ("skills/governance/canon/trace.md", 420)
UV_COMMAND = "uv run --no-project --with tiktoken python3 scripts/validate.py"


def git(*args):
    try:
        result = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
    except FileNotFoundError:
        return None
    return result.stdout if result.returncode == 0 else None


def prose_lines(text):
    """Yield (line number, line) for the lines outside fenced code blocks."""
    fence = None
    for number, line in enumerate(text.splitlines(), 1):
        match = FENCE_RE.match(line)
        if match:
            fence = match.group(1) if fence is None else (None if fence == match.group(1) else fence)
            continue
        if fence is None:
            yield number, line


def link_targets(text):
    """Yield link targets outside fenced code blocks and inline code."""
    for _number, line in prose_lines(text):
        yield from LINK_RE.findall(INLINE_CODE_RE.sub("", line))


def paragraph_lines(text):
    """Yield (first line number, text) for each paragraph, list item, heading or table row outside fenced code blocks,
    with its wrapped lines joined."""
    current, last, single = None, None, False
    for number, line in prose_lines(text):
        opens = LIST_MARKER_RE.match(line) or line.lstrip().startswith(("#", "|", ">"))
        if current and line.strip() and not opens and not single and number == last + 1:
            current[1] += " " + line.strip()
        else:
            if current:
                yield tuple(current)
            current = [number, line] if line.strip() else None
            single = line.lstrip().startswith(("#", "|"))
        last = number
    if current:
        yield tuple(current)


def trace_call_sites(text):
    """Yield (line number, sentence) for each sentence that holds a `canon.py trace start` or `end` call; a code span
    never ends a sentence."""
    for number, line in paragraph_lines(text):
        body = LIST_MARKER_RE.sub("", line)
        masked = INLINE_CODE_RE.sub(lambda m: "\0" * len(m.group(0)), body)
        start = 0
        for end in [m.start() for m in SENTENCE_END_RE.finditer(masked)] + [len(body)]:
            sentence = body[start:end].strip()
            if TRACE_CALL_RE.search(sentence):
                yield number, sentence
            start = end


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


def misplaced_skill_files(skill_files):
    """Every SKILL.md in the checkout, tracked, or untracked and not ignored, other than `skill_files`, those of the
    validated skills: the skills CLI would treat it as an installable skill."""
    listed = git("ls-files", "-z", "--cached", "--others", "--exclude-standard")
    if listed is None:
        return ["cannot list the checkout's files with git"]
    return [f"{rel} is not a skill's own skills/<category>/<name>/SKILL.md, yet the skills CLI would treat it as an "
            "installable skill"
            for rel in sorted(set(listed.split("\0")))
            if rel.rsplit("/", 1)[-1] == "SKILL.md" and ROOT / rel not in skill_files and (ROOT / rel).is_file()]


def check_canon_version():
    """Projects record in their canon block the CANON_VERSION they need, so every change to canon.py needs a new
    version."""
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


def text_budgets():
    """D001's budgets for the skill text tracing adds, in tiktoken's cl100k_base tokens: the errors, and why they were
    not measured when tiktoken is missing or cannot load the encoding."""
    try:
        import tiktoken
    except ImportError:
        return [], f"tiktoken is not installed; run `{UV_COMMAND}`"
    try:
        encoding = tiktoken.get_encoding("cl100k_base")
    except Exception as error:  # tiktoken downloads the encoding on first use
        return [], f"tiktoken cannot load cl100k_base ({error})"

    def tokens(text):
        return len(encoding.encode(text))

    errors = []
    for md in sorted(SKILLS_DIR.rglob("*.md")):
        for number, sentence in trace_call_sites(md.read_text(encoding="utf-8")):
            if (count := tokens(sentence)) > CALL_SITE_TOKENS:
                errors.append(f"{md.relative_to(ROOT).as_posix()}:{number}: a trace call site of {count} tokens "
                              f"(max {CALL_SITE_TOKENS})")
    rel, opening, limit = PLACEHOLDERS
    if (ROOT / rel).is_file():
        text = (ROOT / rel).read_text(encoding="utf-8")
        paragraph = next((p for p in text.split("\n\n") if p.startswith(opening)), None)
        if paragraph is None:
            errors.append(f"{rel}: no paragraph starts with {opening}")
        elif (count := tokens(paragraph)) > limit:
            errors.append(f"{rel}: the paragraph on trace placeholders is {count} tokens (max {limit})")
    rel, limit = TRACE_MD
    if (ROOT / rel).is_file() and (count := tokens((ROOT / rel).read_text(encoding="utf-8"))) > limit:
        errors.append(f"{rel}: {count} tokens (max {limit})")
    return errors, None


def run_tests():
    """The label of the suite's line, counting skipped tests, and its failures."""
    if not TESTS_DIR.is_dir():
        return "tests", []
    result = subprocess.run([sys.executable, "-B", "-m", "unittest", "discover", "-s", str(TESTS_DIR)],
                            cwd=ROOT, capture_output=True, text=True)
    skipped = re.search(r"skipped=(\d+)", result.stderr.rstrip().rsplit("\n", 1)[-1])
    label = f"tests ({skipped.group(1)} skipped)" if skipped else "tests"
    return label, [] if result.returncode == 0 else [result.stderr.rstrip()]


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
    skill_files = set()

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
            skill_files.add(skill_dir / "SKILL.md")
            failures += report(skill_dir.relative_to(ROOT), errors)
    failures += report("SKILL.md placement", misplaced_skill_files(skill_files))

    for md in sorted(ROOT.glob("*.md")):
        errors = broken_links(md, ROOT)
        if md.name == "README.md":
            errors += check_readme(skills)
        failures += report(md.name, errors)
    if (ROOT / CANON_SCRIPT).is_file():
        failures += report(CANON_SCRIPT + " version", check_canon_version())
    budget_errors, unmeasured = text_budgets()
    if unmeasured:
        print(f"skip D001 text budgets: {unmeasured}")
    else:
        failures += report("D001 text budgets", budget_errors)
    failures += report(*run_tests())
    print(f"\n{len(skills)} skill(s) checked, {failures} problem(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
