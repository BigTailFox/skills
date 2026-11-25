#!/usr/bin/env python3
"""Checker and helper CLI for the canon documentation system.

Single file, Python 3.8+ standard library only. Run `canon.py -h` for commands.
"""

import argparse
import collections
import contextlib
import datetime
import difflib
import errno
import hashlib
import json
import os
import posixpath
import re
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import urllib.parse
from pathlib import Path

try:
    import fcntl
except ImportError:  # Windows
    fcntl = None
    import msvcrt

CANON_VERSION = "83"

TYPES = {
    "C": {"dir": "concepts", "active": ("draft",), "terminal": ("adopted", "dropped"),
          "sections": ("Motivation", "Ideas", "Open questions")},
    "D": {"dir": "designs", "active": ("draft", "accepted", "active"), "terminal": ("superseded", "retired"),
          "sections": ("Goals", "Spec", "Decisions")},
    "P": {"dir": "plans", "active": ("draft", "accepted", "in-progress"), "terminal": ("done", "abandoned"),
          "sections": ("Current state", "Slices", "Notes", "Log")},
    "R": {"dir": "reviews", "active": ("open",), "terminal": ("closed",),
          "sections": ("Scope", "Findings")},
    "E": {"dir": "experiments", "active": ("planned", "running", "answered"),
          "terminal": ("concluded", "superseded", "overturned", "dropped"),
          "sections": ("Question", "Setup", "Results", "Conclusion")},
    "I": {"dir": "investigations", "active": ("open",), "terminal": ("resolved",),
          "sections": ("Symptom", "Reproduction", "Analysis", "Resolution")},
}
LIVE_TERMINAL = {"C": "adopted", "E": "concluded"}
TYPE_ORDER = "DPIREC"
CATEGORY_DIRS = {info["dir"]: letter for letter, info in TYPES.items()}
ALIASES = {}
for _letter, _info in TYPES.items():
    ALIASES[_letter.lower()] = _letter
    ALIASES[_info["dir"]] = _letter
    ALIASES[_info["dir"][:-1]] = _letter
EXTRA_DIRS = ("guides", "assets")

COMMON_FIELDS = ("status", "created", "updated", "revision", "modules", "summary", "refs")
TYPE_FIELDS = {"D": ("owns", "paths"), "P": ("based_on",)}
OPTIONAL_FIELDS = {"D": ("reviewed", "reviewers", "approved", "implemented", "as_built"),
                   "P": ("reviewed", "reviewers", "approved")}
LIST_FIELDS = {"modules", "refs", "owns", "paths", "based_on", "reviewers"}
INT_FIELDS = {"revision", "reviewed", "approved", "implemented"}
SEVERITIES = ("blocker", "major", "minor")
DISPOSITIONS = ("open", "fixed", "moved", "declined")
SLICE_STATUSES = ("todo", "in-progress", "done", "paused")
ISSUES_SECTION = "Known issues"
NEXT_STEPS = ("decide", "fix", "L1", "L2")
SETUP_LABELS = ("Commit", "Environment", "Command")
SOURCES_LABEL = "Sources"
RESOLUTION_LABELS = ("Root cause", "Fix", "Verification")

MAX_DOC_LINES = 500
MAX_AGENTS_LINES = 150
MAX_SUMMARY = 160
MAX_AREAS = 10
MAX_LINKS = 40
EMPTY_BLOBS = {hashlib.sha1(b"blob 0\0").hexdigest(), hashlib.sha256(b"blob 0\0").hexdigest()}

FILE_RE = re.compile(r"^([CDPREI])(\d{3,})([A-Z]?)-([a-z0-9]+(?:-[a-z0-9]+)*)\.md$")
FULL_ID_RE = re.compile(r"^([CDPREI])(\d{3,})([A-Z]?)$")
REF_ARG_RE = re.compile(r"^([CDPREI]\d{3,}[A-Z]?)(?:[#§](.+))?$")
REF_TEXT_RE = re.compile(r"^([CDPREI]\d{3,}[A-Z]?)(?:§([^:]+))?: \S")
BASED_ON_RE = re.compile(r"^(D\d{3,}[A-Z]?)@r(\d+)$")
FIXED_IN_DOC_RE = re.compile(r"^([CDPREI]\d{3,}[A-Z]?)@r\d+$")
HEX_NAME_RE = re.compile(r"^[0-9a-f]{7,64}$")
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
LINK_RE = re.compile(r"(!?)\[([^\]]*)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
FENCE_RE = re.compile(r"^\s*(?P<list>(?:(?:[-+*]|[0-9]{1,9}[.)]) {1,4})+)?(?P<fence>`{3,}|~{3,})")
INLINE_CODE_RE = re.compile(r"(?<!`)(`+)(?!`)(.*?)(?<!`)\1(?!`)")
LINK_UNSAFE_RE = re.compile(r"[\s%#?()]")
STATUS_LINE_RE = re.compile(r"^\s*(?:-\s+)?Status:\s*(.*?)\s*$")
DISPOSITION_ID_RE = re.compile(r"^\s*\|\s*(?P<finding>[^|\s]+)\s*\|.*\|\s*(?:moved\s+(?P<moved>[CDPREI]\d{3,}[A-Z]?)"
                               r"|fixed\s+(?P<fixed>[CDPREI]\d{3,}[A-Z]?)@r\d+)\s*\|\s*$")
CITATION_RE = re.compile(r"(?<![A-Za-z0-9_])([CDPREI][0-9]{3,}[A-Z]?)(?![A-Za-z0-9_])"
                         r"((?:@r[0-9]+|-[FK][0-9]+)(?![A-Za-z0-9_]))?(?:§([\w-]+))?")
LABEL_RE = re.compile(r"^\s*(?:-\s+)?([A-Za-z ]+?):\s*(.*?)\s*$")
GUIDANCE = "<!-- canon:"
GUIDANCE_RE = re.compile(re.escape(GUIDANCE) + r".*?-->", re.S)
INDEX_START = "<!-- canon:index:start -->"
INDEX_END = "<!-- canon:index:end -->"
AGENTS_START = "<!-- canon:agents:start -->"
AGENTS_END = "<!-- canon:agents:end -->"
INSTALL_DIR = ".agents/skills"
AGENTS_BLOCK = AGENTS_START + """
## Docs

This repo follows the canon documentation system, run from the `canon` skill installed in this project. Without that skill, or when its `canon.py` says it runs only from an install inside the project or that the project needs a newer canon version, ask the user whether to install canon here. At the repo root, `npx skills experimental_install` restores the release `skills-lock.json` records for `canon`; for the newest release, run `npx skills add BigTailFox/skills@<tag> -s '*' -a claude-code -a codex -a cursor -y`, where `<tag>` is the name after `refs/tags/` on the first line of `git ls-remote --tags --refs --sort=-v:refname https://github.com/BigTailFox/skills 'v*'`. Engineering docs live in `docs/` and in module `docs/` directories. Start at [D000: Project overview](docs/designs/D000-project-overview.md); [docs/README.md](docs/README.md) indexes every doc.

- Tool: `scripts/canon.py` of the `canon` skill installed in this project, `{install}/canon/scripts/canon.py` as `npx skills` installs it, canon version {version} or later, run from the repo root (`-h` lists commands). Run `check --fix` before committing and after every merge or rebase; in a checkout another session also uses, or to commit only part of a checkout's changes, follow the `canon` skill's Concurrent work instead.
- When a change may alter behavior or standards a design specifies, run `which <file>` and read the governing sections with `show D00X#slug` first.
- State each change's tier (L0, L1, L2) before starting, unless it touches only docs that no design's `paths` names and bumps no revision. Designs and plans pass the review gate defined by the `canon` skill.
- Skip `docs/archived/` unless researching history.
""" + AGENTS_END
STAGED_SINCE = 59  # the first CANON_VERSION whose `check` takes --staged; fixed as CANON_VERSION moves on
PRE_COMMIT_HOOK = """#!/bin/sh
c={install}/canon/scripts/canon.py
if [ ! -f "$c" ]; then
  echo "canon: no canon skill installed in this checkout; install it as the canon block of AGENTS.md says" >&2
  exit 1
fi
v=$(python3 "$c" --version) || exit 1
[ "${{v#canon }}" -ge {staged} ] 2>/dev/null && exec python3 "$c" check --staged
exec python3 "$c" check
""".format(install=INSTALL_DIR, staged=STAGED_SINCE)
CHECK_ONLY_HOOK = b"""#!/bin/sh
c=.agents/skills/canon/scripts/canon.py
[ -f "$c" ] && exec python3 "$c" check
echo "canon: no canon skill installed in this checkout; install it as the canon block of AGENTS.md says" >&2
exit 1
"""
OLD_HOOK_RE = re.compile(re.escape(CHECK_ONLY_HOOK) + rb"|#!/bin/sh\nexec python3 \S+ check\n?")
OLD_COPY_WARNING = ("the project no longer keeps a copy of canon.py; remove {0} and replace `python3 {0}` where files still name "
            "it, such as CI and each `docs/README.md`")
SUB_AGENTS = "Module docs: [docs/README.md](docs/README.md). The repo root `AGENTS.md` defines the docs rules.\n"
DOCS_README = """# Docs

Engineering docs managed with canon. Designs (D) are the source of truth; plans (P) record implementation; concepts (C), reviews (R), experiments (E) and investigations (I) cover the rest. Search from the repo root with `canon.py find <words>`.

## Index
"""
GITATTRIBUTES = ("**/docs/README.md merge=union", "**/docs/archived/README.md merge=union")
LOCAL_DIR = ".canon/"
WORKTREES_DIR = ".worktrees/"
DOCS_PATHSPEC = ":(glob)**/docs/**/*.md"
DOC_NAMES = ("README", "AGENTS", "CLAUDE", "CHANGELOG", "CONTRIBUTING", "LICENSE", "NOTICE", "SECURITY",
             "CODE_OF_CONDUCT", "COPYING")
DOC_SUFFIXES = (".md", ".markdown", ".rst", ".txt", ".adoc", ".org")

EXPERIMENT_TEMPLATE = """
## Question

<!-- canon: The question or hypothesis, and what result would answer it. -->

## Setup

{setup}

## Results

<!-- canon: Measurements or findings, each linked to its raw data or cited source. -->

## Conclusion

<!-- canon: The answer the Results give to the Question. -->
"""
TEMPLATES = {
    "C": """
## Motivation

<!-- canon: The problem or opportunity and why it matters. -->

## Ideas

<!-- canon: Candidate directions and their trade-offs. No implementation plan needed. -->

## Open questions

<!-- canon: What must be answered before a design can start. -->
""",
    "D": """
## Goals

<!-- canon: What this design must achieve, measurable where possible. -->

## Spec

<!-- canon: The authoritative spec for every topic in `owns`. Link to the owning design for anything else. -->

## Budgets

<!-- canon: Optional. Quantitative targets (latency, memory, size) and how they are measured. Delete the section if there are none. -->

## Decisions

<!-- canon: One line per key decision with its reason. Name a rejected alternative only if it is likely to be proposed again. -->
""",
    "P": """{implements}
## Current state

<!-- canon: Current slice, next action, paused slices with their reasons. Update at the end of every slice. -->

## Slices

<!-- canon: Ordered slices as `### S1: name`. Each starts with a `Status: todo` line (todo, in-progress, done, paused), then lists its changes and the test criteria that prove it done, naming the seam (public interface) each test exercises. -->

## Notes

<!-- canon: Risks and constraints the implementer must keep in mind. -->

## Log

<!-- canon: Append decisions, results, evidence and deviations as they happen. -->
""",
    "R": """
## Scope

<!-- canon: What was reviewed, at which commit, and from which angles. -->

## Findings

| ID | Severity | Finding | Disposition |
|----|----------|---------|-------------|

<!-- canon: One row per finding with IDs {id}-F1, {id}-F2, ... Severity: blocker, major, minor. Disposition: open, fixed <commit> (fixed <doc ID>@r<revision> for a fix made in a doc), moved <doc ID>, declined <reason>. -->
""",
    "E": EXPERIMENT_TEMPLATE.format(setup="""- Commit:
- Environment:
- Command:

<!-- canon: Fill Commit, Environment and Command for a run. For research, replace them with `- Sources:` and the primary sources consulted, one per indented line. -->"""),
    "E-research": EXPERIMENT_TEMPLATE.format(setup="""- Sources:

<!-- canon: List one primary source per indented line as a Markdown link. -->"""),
    "I": """
## Symptom

<!-- canon: Observed versus expected behavior, with error output or metrics. -->

## Reproduction

- Commit:
- Environment:
- Command:

## Analysis

<!-- canon: Hypotheses tested and their evidence, in order. -->

## Resolution

- Root cause:
- Fix:
- Verification:
""",
}
OVERVIEW_ID, OVERVIEW_SLUG, OVERVIEW_TITLE = "D000", "project-overview", "Project overview"
OVERVIEW_SPEC = (
    ("Glossary", "<!-- canon: Terms used across modules; a term one module uses belongs to the design that owns it. "
                 "It comes first, since the subsections after it use its terms. -->"),
    ("Capabilities", """<!-- canon: One row per capability the project offers its users or callers, at the grain of a feature list. -->

| Capability | Modules | Design |
|---|---|---|"""),
    ("Modules", """<!-- canon: One row per module. Path lists the module's directories relative to the project directory, comma-separated, each ending with `/`; `./` is the project directory. In a monorepo, each module's row links that module's designs. Adding a module is L2. -->

| Module | Path | Purpose | Entry points | Design |
|---|---|---|---|---|"""),
    ("Dependencies", """<!-- canon: The allowed dependency directions between modules. Changing them, or an interface between modules, is L2. -->

<!-- canon: Once a design owns a standard that applies across modules, such as error handling, add `### Standards` after Dependencies with one row per standard and the design that owns it: `| Standard | Design |`. Leave it out while no design owns one. -->"""),
)
OVERVIEW_TEMPLATE = """
## Goals

<!-- canon: What the project is for, who uses it and what is out of scope. -->

## Spec

<!-- canon: The four subsections below, in this order. Rows name modules, capabilities and standards, never single docs: designs reach their sub-topics through their own links, `docs/README.md` indexes every doc, and detail below the module level belongs to the module's designs. A Design cell links every top-level design that owns the capability or standard, or that governs the module's code, or reads `none`. The tables map the project, its planned modules included, each linking the designs that specify it; a module that a revision of a design with `implemented` specifies gets its row once its directory exists. A change that adds or removes a module, capability or standard, or creates, moves or archives a top-level design, updates their rows in the same commit; rows change no meaning, so they take no revision bump and no gate. Goals, Dependencies and Glossary are spec. `paths` lists only files that embody the architecture, such as dependency-boundary configuration and module wiring, and is usually empty. -->
""" + "".join("\n### {}\n\n{}\n".format(name, body) for name, body in OVERVIEW_SPEC) + """
## Decisions

<!-- canon: One line per key decision with its reason. Name a rejected alternative only if it is likely to be proposed again. -->
"""


# ---------------------------------------------------------------- helpers

def today():
    return datetime.date.today().isoformat()


def posix_rel(path, start):
    return os.path.relpath(str(path), str(start)).replace(os.sep, "/")


def well_formed_id(match):
    """Whether a FILE_RE or FULL_ID_RE match pads its number to three digits and gives only a design a suffix."""
    return str(int(match.group(2))).zfill(3) == match.group(2) and (not match.group(3) or match.group(1) == "D")


def path_id(rel):
    """The id of a doc file, given its path from the repo root; None for any other file."""
    match = FILE_RE.match(rel.rsplit("/", 1)[-1])
    if match and (rel.startswith("docs/") or "/docs/" in rel):
        return match.group(1) + match.group(2) + match.group(3)
    return None


def git_run(cwd, *args, env=None, data=None):
    """Run Git, preserving byte input and NUL-delimited path output. Return None when Git is not on PATH."""
    text_mode = data is None and "-z" not in args
    try:
        result = subprocess.run(["git", *args], cwd=str(cwd), env=env, input=data, capture_output=True,
                                text=text_mode)
    except FileNotFoundError:
        return None
    if not text_mode:
        result.stdout, result.stderr = result.stdout.decode(errors="surrogateescape"), result.stderr.decode(errors="replace")
    return result


def git(cwd, *args, env=None):
    result = git_run(cwd, *args, env=env)
    return result.stdout if result is not None and result.returncode == 0 else None


def git_failure(result, subcommand):
    """Why a `git <subcommand>` call `git_run` finished as `result` failed."""
    if result is None:
        return "git is not on PATH"
    return result.stderr.strip() or "git {} exited {}".format(subcommand, result.returncode)


def git_checked(cwd, *args, ok=(0,), data=None):
    """The finished `git <args>` run in `cwd`, for a call whose failure must not read as an empty result: an exit
    code outside `ok` ends the command with Git's reason."""
    result = git_run(cwd, *args, data=data)
    if result is None or result.returncode not in ok:
        sys.exit("canon: git {} failed in {}: {}".format(args[0], cwd, git_failure(result, args[0])))
    return result


def changed_path_status(root, command, *args):
    """Map changed paths to Git status letters, treating a rename as a deletion and an addition."""
    fields = git_checked(root, command, "-z", "--name-status", "--no-renames", "--ignore-submodules=none",
                         *args, "--").stdout.split("\0")
    return dict(zip(fields[1::2], fields[::2]))


def unreadable_checkout(start):
    """For a directory Git finds in no checkout: the nearest directory at or above it that holds `.git`, and why Git
    cannot read it; else None."""
    start = start.resolve()
    for path in (start, *start.parents):
        if (path / ".git").exists():
            return path, git_failure(git_run(start, "rev-parse", "--show-toplevel"), "rev-parse")
    return None


def parse_value(key, raw):
    if key in LIST_FIELDS and raw.startswith("[") and raw.endswith("]"):
        return [item.strip().strip("'\"") for item in raw[1:-1].split(",") if item.strip()]
    if key in INT_FIELDS and raw.isdigit():
        with contextlib.suppress(ValueError):
            return int(raw)
    return raw.strip("'\"")


def render_value(value):
    if isinstance(value, list):
        return "[" + ", ".join(value) + "]"
    return str(value)


def parse_frontmatter(lines):
    if not lines or lines[0].strip() != "---":
        return None, -1, []
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        return None, -1, []
    fields, bad = {}, []
    for line in lines[1:end]:
        if not line.strip():
            continue
        match = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*):\s*(.*?)\s*$", line)
        if not match:
            bad.append(line)
            continue
        fields[match.group(1)] = parse_value(match.group(1), match.group(2))
    return fields, end, bad


def set_field(text, key, value):
    """Set a frontmatter field, or delete its line when `value` is None."""
    lines = text.split("\n")
    end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    rendered = "{}: {}".format(key, render_value(value))
    for i in range(1, end):
        if re.match(r"^{}:".format(re.escape(key)), lines[i]):
            if value is None:
                del lines[i]
            else:
                lines[i] = rendered
            break
    else:
        if value is not None:
            lines.insert(end, rendered)
    return "\n".join(lines)


def gh_slug(text):
    text = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = text.replace("`", "").strip().lower()
    text = re.sub(r"[^\w\- ]", "", text)
    return text.replace(" ", "-")


def code_mask(lines, start=0):
    """Yield (index, line) outside fenced code blocks."""
    fence = None
    list_indent = 0
    for i in range(start, len(lines)):
        line = lines[i].expandtabs(4)
        if fence and list_indent and line.strip() and len(line) - len(line.lstrip()) < list_indent:
            fence = None  # Leaving the list item also closes its fence.
        match = FENCE_RE.match(line)
        if fence:
            if match and not match["list"] and match["fence"].startswith(fence) and not line[match.end():].strip():
                fence = None
            continue
        if match and (match["fence"][0] == "~" or "`" not in line[match.end():]):
            fence = match["fence"]
            list_indent = match.start("fence") if match["list"] else 0
            continue
        yield i, lines[i]


class Heading:
    def __init__(self, level, text, slug, line):
        self.level, self.text, self.slug, self.line = level, text, slug, line


def scan_headings(lines, start=0):
    headings, counts = [], {}
    for i, line in code_mask(lines, start):
        match = HEADING_RE.match(line)
        if not match:
            continue
        base = gh_slug(match.group(2))
        n = counts.get(base, 0)
        counts[base] = n + 1
        headings.append(Heading(len(match.group(1)), match.group(2), base if n == 0 else "{}-{}".format(base, n), i))
    return headings


def body_headings(text):
    lines = text.split("\n")
    return scan_headings(lines, parse_frontmatter(lines)[1] + 1)


def heading_anchors(old_text, new_text):
    """{old anchor: new anchor} for each heading whose anchor a command changes when it rewrites a doc from `old_text`
    to `new_text`. Headings pair in order, the H1 with the H1 and any other heading with one of the same level and
    text; a heading the command adds pairs with none."""
    def keyed(text):
        headings = body_headings(text)
        h1 = next((h for h in headings if h.level == 1), None)
        return headings, [(0, "") if h is h1 else (h.level, h.text) for h in headings]

    old, old_keys = keyed(old_text)
    new, new_keys = keyed(new_text)
    anchors = {}
    for a, b, size in difflib.SequenceMatcher(None, old_keys, new_keys, autojunk=False).get_matching_blocks():
        for k in range(size):
            if old[a + k].slug != new[b + k].slug:
                anchors[old[a + k].slug] = new[b + k].slug
    return anchors


def changed_anchors(old_text, new_text):
    """{old anchor: new anchor} for each heading whose anchor changes when a command rewrites headings of a doc in
    place, adding and removing none, so the headings of the two texts pair in order."""
    return {old.slug: new.slug for old, new in zip(body_headings(old_text), body_headings(new_text))
            if old.slug != new.slug}


def iter_links(lines, start=0):
    for i, line in code_mask(lines, start):
        masked = INLINE_CODE_RE.sub(lambda m: " " * len(m.group(0)), line)
        for match in LINK_RE.finditer(masked):
            yield i, match


def entry_path(pattern):
    """A `paths` entry relative to its project, without surrounding whitespace or leading `./`."""
    p = pattern.strip()
    while p.startswith("./"):
        p = p[2:]
    return p


def glob_regex(pattern):
    p = entry_path(pattern)
    if p.endswith("/"):
        p += "**"
    out, i = "", 0
    while i < len(p):
        if p.startswith("**/", i):
            out, i = out + "(?:.*/)?", i + 3
        elif p.startswith("**", i):
            out, i = out + ".*", i + 2
        elif p[i] == "*":
            out, i = out + "[^/]*", i + 1
        elif p[i] == "?":
            out, i = out + "[^/]", i + 1
        else:
            out, i = out + re.escape(p[i]), i + 1
    # Git permits newlines in names. Keep DOTALL scoped so composed design
    # patterns retain it, and require the real end of the path.
    return re.compile("(?s:" + out + r"(?:/.*)?)\Z")


def git_pathspec(project_rel, pattern):
    """A Git pathspec covering every file a `paths` entry of a design in the project at `project_rel` matches: the
    directory before its first wildcard, or the entry itself, taken literally, since Git's globs read `[`, `**`
    within a segment and `*` above a match otherwise than `glob_regex`; `governs` then decides. None for an absolute
    entry or one outside the repository, which Git refuses."""
    p = entry_path(pattern)
    if p.startswith("/") or posixpath.normpath(posixpath.join(project_rel, p)).split("/")[0] == "..":
        return None
    wildcard = next((i for i, c in enumerate(p) if c in "*?"), None)
    if wildcard is not None:
        p = p[:wildcard].rpartition("/")[0]
    return ":(literal)" + ("/".join(x for x in (project_rel, p.rstrip("/")) if x) or ".")


def code_pathspec(repo, root):
    """Pathspecs for a project's files outside its docs/ and outside nested projects."""
    specs = [":(glob)" + (root.rel + "/**" if root.rel else "**"), ":(glob,exclude)" + root.docs_rel + "/**"]
    for other in repo.roots:
        if other is not root and other.rel and (not root.rel or other.rel.startswith(root.rel + "/")):
            specs.append(":(glob,exclude)" + other.rel + "/**")
    return specs


def parse_date(value):
    try:
        return datetime.date.fromisoformat(value)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------- trees

def resolve_tree_path(tree, relative, aliases=None, walked=None, allow_missing=False):
    """Follow links before interpreting the next component. With allow_missing, retain absent target components."""
    if os.path.isabs(relative) or "\0" in relative:
        return None
    done, todo, links = [], collections.deque(relative.split("/")), 0
    while todo:
        part = todo.popleft()
        if part is None:
            aliases.append("/".join(done))  # Resolved endpoint of this link, before its caller's remaining components.
            continue
        if part in ("", "."):
            continue
        if part == "..":
            if not done:
                return None
            done.pop()
            continue
        rel = "/".join((*done, part))
        if walked is not None:
            walked.add(rel)
        kind, target = tree.entry(rel)
        if kind == "link":
            if aliases is not None:
                aliases.append(rel)
                todo.appendleft(None)
            links += 1
            if links > MAX_LINKS or os.path.isabs(target):
                return None
            todo.extendleft(reversed(target.split("/")))
        elif (kind == "dir" or (kind is None and allow_missing)
              or (kind == "file" and not any(p is not None for p in todo))):
            done.append(part)
        else:
            return None
    return "/".join(done)


class WorkTree:
    """The work tree, read from disk: the files Git tracks or would add that exist on disk, or outside Git the files
    a walk of the directory finds."""

    def __init__(self, root, is_git):
        self.root, self.is_git = root, is_git

    def files(self):
        if self.is_git:
            out = git_checked(self.root, "ls-files", "-z", "-co", "--exclude-standard").stdout
            return sorted({f for f in out.split("\0") if f and (self.root / f).is_file()})
        found = []
        for dirpath, dirnames, filenames in os.walk(str(self.root)):
            dirnames[:] = [d for d in dirnames if not d.startswith(".") and d not in ("node_modules", "venv")]
            for name in filenames:
                found.append(posix_rel(Path(dirpath) / name, self.root))
        return sorted(found)

    def tracked(self, name):
        """The paths Git tracks whose last component is `name`."""
        if not self.is_git:
            return []
        out = git_checked(self.root, "ls-files", "-z", "--", ":(glob)**/" + name).stdout
        return [rel for rel in out.split("\0") if rel]

    def entry(self, rel):
        path = self.root / rel
        try:
            mode = path.lstat().st_mode
            if stat.S_ISLNK(mode):
                return "link", os.readlink(path)
            if stat.S_ISDIR(mode):
                return "dir", None
            if stat.S_ISREG(mode):
                return "file", None
        except (FileNotFoundError, NotADirectoryError):
            pass
        return None, None

    def is_file(self, path):
        return path.is_file()

    def is_dir(self, path):
        return path.is_dir()

    def exists(self, path):
        return path.exists()

    def read_bytes(self, path):
        return path.read_bytes()

    def read_text(self, path, errors="strict"):
        return path.read_text(encoding="utf-8", errors=errors)

    def realpath(self, path):
        return Path(os.path.realpath(str(path)))


class GitTree:
    """A tree read through Git and never from disk: `entries` maps the path of each of its entries from the repo root
    to their mode and object name, and its blobs are read through one `git cat-file --batch` process. Paths are
    absolute under the repo root, as on disk."""

    def __init__(self, root, entries):
        self.root, self.entries, self.dirs = root, entries, set()
        for rel in entries:
            self.dirs.update(rel[:i] for i, c in enumerate(rel) if c == "/")
        self.batch, self.blobs = None, {}

    @classmethod
    def of_commit(cls, root, commit):
        """The tree of `commit`, its entries listed once with `git ls-tree`."""
        entries = {}
        for item in git_checked(root, "ls-tree", "-r", "-z", "--full-tree", commit).stdout.split("\0"):
            if item:
                meta, _, rel = item.partition("\t")
                mode, _kind, name = meta.split(" ")
                entries[rel] = mode, name
        return cls(root, entries)

    @classmethod
    def staged(cls, root, changes, has_head):
        """The staged tree: the stage-0 entries of the Git index, the file `GIT_INDEX_FILE` names when it is set,
        listed once with `git ls-files -s`, other than intent-to-add entries, which no commit records. `git ls-files`
        lists such an entry as the empty blob, and `changes`, the `git diff --cached` status of each path the staged
        tree changes against HEAD, or against the empty tree without HEAD, lists it as deleted over a path HEAD holds
        and leaves it out elsewhere: an empty blob `changes` leaves out is a file only where HEAD holds the path."""
        entries, unlisted = {}, []
        for item in git_checked(root, "ls-files", "-s", "-z").stdout.split("\0"):
            if not item:
                continue
            meta, _, rel = item.partition("\t")
            mode, name, stage = meta.split(" ")
            if stage != "0" or name in EMPTY_BLOBS and changes.get(rel) == "D":
                continue
            if name in EMPTY_BLOBS and rel not in changes:
                unlisted.append(rel)
            entries[rel] = mode, name
        if unlisted:
            held = git_checked(root, "ls-tree", "-r", "-z", "--name-only", "--full-tree", "HEAD").stdout.split("\0") \
                if has_head else []
            for rel in set(unlisted) - set(held):
                del entries[rel]
        return cls(root, entries)

    def blob(self, name):
        """The content of the blob with object name `name`; a failure, a `missing` reply included, ends the command."""
        if name not in self.blobs:
            if self.batch is None:
                self.batch = subprocess.Popen(["git", "cat-file", "--batch"], cwd=str(self.root),
                                              stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            with contextlib.suppress(OSError):
                self.batch.stdin.write(name.encode() + b"\n")
                self.batch.stdin.flush()
            reply = self.batch.stdout.readline().decode().split()
            size = int(reply[2]) if reply[1:2] == ["blob"] else None
            data = self.batch.stdout.read(size + 1)[:-1] if size is not None else None
            if data is None or len(data) != size:
                reason = " ".join(reply) if reply and size is None else self.stopped()
                sys.exit("canon: git cat-file failed in {}: {}".format(self.root, reason))
            self.blobs[name] = data
        return self.blobs[name]

    def stopped(self):
        """Why the `git cat-file --batch` process stopped answering, once it has exited."""
        err = self.batch.communicate()[1].decode().strip()
        return err or "git cat-file exited {}".format(self.batch.returncode)

    def entry(self, rel):
        mode, name = self.entries.get(rel, ("", None))
        if mode == "120000":
            return "link", self.blob(name).decode("utf-8", "surrogateescape")
        if mode.startswith("100"):
            return "file", None
        return ("dir" if rel in self.dirs else None), None

    def resolve(self, path, allow_missing=False):
        try:
            relative = path.relative_to(self.root).as_posix()
        except ValueError:
            return None
        return resolve_tree_path(self, relative, allow_missing=allow_missing)

    def files(self):
        return sorted(rel for rel, (mode, _name) in self.entries.items()
                      if mode.startswith("100") or mode == "120000" and self.is_file(self.root / rel))

    def tracked(self, name):
        """The paths of the tree whose last component is `name`."""
        return [rel for rel in self.entries if rel.rsplit("/", 1)[-1] == name]

    def is_file(self, path):
        entry = self.entries.get(self.resolve(path))
        return entry is not None and entry[0].startswith("100")

    def is_dir(self, path):
        rel = self.resolve(path)
        return rel == "" or rel in self.dirs

    def exists(self, path):
        return self.is_file(path) or self.is_dir(path)

    def read_bytes(self, path):
        if not self.is_file(path):
            raise FileNotFoundError(errno.ENOENT, "no file in the tree", str(path))
        return self.blob(self.entries[self.resolve(path)][1])

    def read_text(self, path, errors="strict"):
        """The blob's text with `\\r\\n` and `\\r` read as `\\n`, as Python's text mode reads the work tree and `git` reads
        the commit compared."""
        return self.read_bytes(path).decode("utf-8", errors).replace("\r\n", "\n").replace("\r", "\n")

    def realpath(self, path):
        rel = self.resolve(path, allow_missing=True)
        return None if rel is None else self.root / rel


# ---------------------------------------------------------------- model

class Root:
    def __init__(self, repo, rel):
        self.rel = rel
        self.project = repo.root / rel if rel else repo.root
        self.docs = self.project / "docs"
        self.docs_rel = rel + "/docs" if rel else "docs"
        self.label = rel or "."


class Doc:
    def __init__(self, root, path, rel, match, archived, text):
        self.root, self.path, self.rel, self.archived = root, path, rel, archived
        self.type = match.group(1)
        self.digits, self.suffix, self.slug = match.group(2), match.group(3), match.group(4)
        self.number = int(self.digits)
        self.id = self.type + self.digits + self.suffix
        self.text = text
        self.lines = self.text.split("\n")
        self.fm, self.fm_end, self.fm_bad = parse_frontmatter(self.lines)
        self.headings = scan_headings(self.lines, self.fm_end + 1)
        h1 = next((h for h in self.headings if h.level == 1), None)
        prefix = self.id + ": "
        self.title = h1.text[len(prefix):].strip() if h1 and h1.text.startswith(prefix) else ""
        self._paths = None

    def get(self, key, default=None):
        return (self.fm or {}).get(key, default)

    @property
    def status(self):
        return self.get("status", "?")

    @property
    def revision(self):
        value = self.get("revision")
        return value if isinstance(value, int) else 0

    @property
    def reviewed(self):
        value = self.get("reviewed")
        return value if isinstance(value, int) else 0

    @property
    def implemented(self):
        value = self.get("implemented")
        return value if isinstance(value, int) else 0

    def as_list(self, key):
        value = self.get(key, [])
        return value if isinstance(value, list) else []

    def section_span(self, name):
        """The index in `headings` of the `## name` heading and the line its section ends before; None without it."""
        for idx, h in enumerate(self.headings):
            if h.level == 2 and h.text == name:
                return idx, next((x.line for x in self.headings[idx + 1:] if x.level <= 2), len(self.lines))
        return None

    def section(self, name):
        span = self.section_span(name)
        return self.lines[self.headings[span[0]].line + 1:span[1]] if span else None

    def spec_subsections(self):
        """The `### ` headings in `## Spec`, as indexes into `headings`."""
        span = self.section_span("Spec")
        if span is None:
            return []
        return [i for i in range(span[0] + 1, len(self.headings))
                if self.headings[i].line < span[1] and self.headings[i].level == 3]

    def module_rows(self):
        """The rows of D000's Modules table, the first table under `### Modules` in `## Spec`, as (entries, design):
        the Path cell split at commas, each entry stripped of whitespace and backticks, and the Design cell, each
        column found by its header in any case."""
        heads = self.headings
        found = next((i for i in self.spec_subsections() if heads[i].text == "Modules"), None)
        if found is None:
            return []
        end = next((h.line for h in heads[found + 1:] if h.level <= 3), len(self.lines))
        rows = []
        for _i, line in code_mask(self.lines[:end], heads[found].line + 1):
            if line.strip().startswith("|"):
                rows.append([cell.strip() for cell in line.strip().strip("|").split("|")])
            elif rows:
                break
        header = [cell.lower() for cell in rows[0]] if rows else []
        path_col = header.index("path") if "path" in header else None
        design_col = header.index("design") if "design" in header else None
        out = []
        for row in rows[1:] if path_col is not None else []:
            if all(set(cell) <= set("-: ") for cell in row):
                continue
            entries = [e.strip(" \t`") for e in (row[path_col] if path_col < len(row) else "").split(",")]
            design_cell = row[design_col] if design_col is not None and design_col < len(row) else ""
            out.append(([e for e in entries if e], design_cell))
        return out

    def module_entries(self):
        """The entries of the Path cells of D000's Modules table."""
        return [entry for entries, _design_cell in self.module_rows() for entry in entries]

    def governs(self, rel, exact=False):
        """Whether this design's `paths` match a repo-relative file; under `exact`, for a file that is no code
        (`Repo.is_code`), only an entry equal to its path does."""
        prefix = self.root.rel + "/" if self.root.rel else ""
        if not rel.startswith(prefix):
            return False
        if self._paths is None:
            entries = self.as_list("paths")
            pattern = "|".join("(?:{})".format(glob_regex(p).pattern) for p in entries)
            self._paths = {entry_path(p) for p in entries}, re.compile(pattern) if entries else None
        listed, matcher = self._paths
        rel = rel[len(prefix):]
        return rel in listed if exact else bool(matcher and matcher.match(rel))

    def label_items(self, section_name, *, ignore_fenced_labels=False):
        """Read label/value pairs in order, keeping repeated fields and their indented continuations."""
        fields = []
        current = None
        lines = self.section(section_name) or []
        label_lines = {i for i, _ in code_mask(lines)} if ignore_fenced_labels else range(len(lines))
        for i, line in enumerate(lines):
            indented = line[:1].isspace()
            match = LABEL_RE.match(line.replace("*", "")) if i in label_lines else None
            if match and not (indented and current):
                current = [match.group(1).strip(), match.group(2)]
                fields.append(current)
            elif current and indented and line.strip():
                current[1] = (current[1] + " " + line.strip()).strip()
            elif line.strip():
                current = None
        return fields

    def labels(self, section_name):
        return dict(self.label_items(section_name))

    def sort_key(self):
        return (TYPE_ORDER.index(self.type), self.number, self.suffix)


Problem = collections.namedtuple("Problem", "level rel line msg fix also tree_hint")


class Repo:
    def __init__(self, start=None, rev=None, tip="HEAD", staged=False):
        """The repository around `start`, read from the work tree, from the tree of commit `rev`, a full object name,
        when given, or from the staged tree when `staged`; `tip` names the branch's tip, HEAD or `rev`, in messages."""
        start = Path(start or os.getcwd())
        top = git(start, "rev-parse", "--show-toplevel")
        self.is_git = top is not None
        self.unreadable = None if self.is_git else unreadable_checkout(start)
        self.root = Path(os.path.realpath(top.strip() if top else str(start)))
        self.has_head = self.is_git and git_checked(self.root, "rev-parse", "--verify", "-q", "HEAD",
                                                    ok=(0, 1)).returncode == 0
        self.rev, self.staged, self.tip, self.head = rev, staged, tip, rev or "HEAD"
        self.reads_work_tree = not (rev or staged)
        self.compared, self.days = "HEAD" if self.has_head else None, {today()}
        if rev:
            self.tree = GitTree.of_commit(self.root, rev)
            out = git_checked(self.root, "log", "-1", "--no-notes", "--no-show-signature",
                              "--format=%P%n%ad%n%cd", "--date=short", rev).stdout
            parents, *days = out.split("\n")[:3]
            self.compared = parents if len(parents.split()) == 1 else None
            self.diff_args, self.days = (self.compared, rev), set(days)
        elif staged:
            self.staged_changes = changed_path_status(self.root, "diff", "--cached")
            self.tree = GitTree.staged(self.root, self.staged_changes, self.has_head)
            self.diff_args = ("--cached", "HEAD")
        else:
            self.tree = WorkTree(self.root, self.is_git)
            self.diff_args = ("HEAD",)
        self.files = self.tree.files()
        parents = [f.rsplit("/", 1)[0] if "/" in f else "" for f in self.files
                   if f.rsplit("/", 1)[-1] == "AGENTS.md" and not self.is_installed_skill(f)]
        self.roots = [Root(self, rel) for rel in parents]
        self.docs, self.problems, self.attachments = [], [], []
        self.index_files, self.scope_md = [], []
        self.live_markdown = {}
        self.by_id, self.by_path = {}, {}
        self._slug_cache, self._design_linked, self._citations = {}, None, None
        self._scan()

    def require_readable(self):
        """End the command when Git finds no checkout around a directory that `.git` puts in one (`unreadable`)."""
        if self.unreadable:
            sys.exit("canon: cannot read the history of HEAD in {}: {}".format(*self.unreadable))

    def problem(self, level, rel, msg, line=None, fix=None, also=(), tree_hint=""):
        """Record a problem on the file at `rel`; `also` holds the paths of the other docs a problem between docs
        involves."""
        self.problems.append(Problem(level, rel, line, msg, fix, also, tree_hint))

    def _scan(self):
        aliases = {}
        for root in self.roots:
            agents = root.project / "AGENTS.md"
            self.scope_md.append(agents)
            if not self.tree.is_dir(root.docs):
                continue
            prefix = root.docs_rel + "/"
            nested = tuple(other.rel + "/" for other in self.roots if other.rel.startswith(prefix))
            reported = set()
            for rel in self.files:
                if not rel.startswith(prefix) or rel.startswith(nested):
                    continue
                parts = rel[len(prefix):].split("/")
                path = self.root / rel
                if parts == ["README.md"]:
                    self.index_files.append((root, False, path))
                    continue
                archived = parts[0] == "archived"
                if archived:
                    parts = parts[1:]
                    if parts == ["README.md"]:
                        self.index_files.append((root, True, path))
                        continue
                if not parts:
                    continue
                if parts[0] in EXTRA_DIRS and not archived:
                    if rel.endswith(".md"):
                        self.scope_md.append(path)
                        self.live_markdown[path] = root
                    continue
                letter = CATEGORY_DIRS.get(parts[0])
                if letter is None:
                    key = (root.docs_rel, archived, parts[0])
                    if key not in reported:
                        reported.add(key)
                        where = root.docs_rel + ("/archived/" if archived else "/") + parts[0]
                        self.problem("ERROR", where, "unknown entry; allowed: README.md, "
                                     + ("" if archived else "archived/, guides/, assets/, ")
                                     + ", ".join(i["dir"] + "/" for i in TYPES.values()),
                                     tree_hint="; " + self.unknown_entry_step(where, len(parts) > 1, archived))
                    continue
                id_match = FULL_ID_RE.match(parts[1]) if len(parts) >= 3 else None
                if id_match and id_match.group(1) == letter:
                    self.attachments.append((root, archived, parts[1], rel))
                    if rel.endswith(".md"):
                        self.scope_md.append(path)
                    continue
                match = FILE_RE.match(parts[-1]) if len(parts) == 2 else None
                if not match or match.group(1) != letter or not well_formed_id(match):
                    self.problem("ERROR", rel, "invalid doc path; expected {}/{}NNN-kebab-slug.md{}".format(
                        TYPES[letter]["dir"], letter, " (D may add one A-Z suffix)" if letter == "D" else ""))
                    continue
                real = self.tree.realpath(path)
                if real is None or self.root not in real.parents:
                    continue
                if real != path:
                    aliases[path] = real
                try:
                    doc = Doc(root, path, rel, match, archived, self.tree.read_text(path))
                except UnicodeDecodeError:
                    self.problem("ERROR", rel, "document is not UTF-8")
                    continue
                self.by_path[path] = doc
                if not archived and doc.fm is not None:
                    self.live_markdown[path] = root
        for path, target in aliases.items():
            alias, canonical = self.by_path.get(path), self.by_path.get(target)
            if alias and canonical and alias.id == canonical.id:
                del self.by_path[path]
        self.docs = list(self.by_path.values())
        for doc in self.docs:
            if doc.id in self.by_id:
                first = self.by_id[doc.id].rel
                self.problem("ERROR", doc.rel, "duplicate id {}, also {}; run `canon.py renumber <path> --base <ref>` "
                             "on the doc this branch added, with the branch it merged or rebased onto"
                             .format(doc.id, first), also=(first,))
            else:
                self.by_id[doc.id] = doc
        self.docs.sort(key=Doc.sort_key)
        self.live_areas = {root.docs / name: root for root in self.roots for name in EXTRA_DIRS}
        self.live_areas.update({doc.path.parent / doc.id: doc.root for doc in self.docs
                                if not doc.archived and doc.fm is not None})
        for root, archived, name, rel in self.attachments:
            area = root.docs / TYPES[name[0]]["dir"] / name
            if not archived and area in self.live_areas and rel.endswith(".md"):
                self.live_markdown[self.root / rel] = root

    def unknown_entry_step(self, where, is_dir, archived):
        """The next step for an unknown entry of a docs root, the file or directory at repo-relative `where`."""
        match = (FULL_ID_RE if is_dir else FILE_RE).match(where.rsplit("/", 1)[-1])
        if match and well_formed_id(match):
            return "move it into {}{}/".format("archived/" if archived else "", TYPES[match.group(1)]["dir"])
        if archived:
            return "move it out of archived/"
        if not is_dir and where.endswith(".md"):
            return "adopt it with `canon.py adopt {} TYPE` or move it into guides/".format(where)
        if is_dir and any(f.startswith(where + "/") and f.endswith(".md") for f in self.files):
            return "adopt its .md files with `canon.py adopt FILE TYPE` or move it into guides/"
        return "move it into guides/ or assets/"

    def get(self, doc_id):
        docs = [d for d in self.docs if d.id == doc_id]
        if not docs:
            sys.exit("canon: unknown document {}".format(doc_id))
        if len(docs) > 1:
            sys.exit("canon: {} is the id of {}; renumber one of them first".format(
                doc_id, " and ".join(d.rel for d in docs)))
        return docs[0]

    def slugs(self, path):
        doc = self.by_path.get(path)
        if doc:
            return {h.slug for h in doc.headings}
        if path not in self._slug_cache:
            try:
                lines = self.tree.read_text(path).split("\n")
            except UnicodeDecodeError:
                self._slug_cache[path] = None
            else:
                self._slug_cache[path] = {h.slug for h in scan_headings(lines)}
        return self._slug_cache[path]

    def design_linked(self):
        """Paths of the files the body of a design, live or archived, links to."""
        if self._design_linked is None:
            self._design_linked = set().union(*(doc_links(self, d) for d in self.docs if d.type == "D"))
        return self._design_linked

    def citations(self):
        """For each file of an experiment, live or archived as `concluded`, that a live doc cites, the docs whose links
        count, sorted as `docs` is: the body of any doc outside archived/ other than the experiment, a concluded
        experiment's only while it is cited itself."""
        if self._citations is None:
            experiments = {d.path: d for d in self.docs
                           if d.type == "E" and (not d.archived or d.status == "concluded")}
            citing = [d for d in self.docs if not d.archived and not (d.type == "E" and d.status == "concluded")]
            seen, citers = {d.path for d in citing}, {}
            while citing:
                reached = []
                for d in citing:
                    for path in doc_links(self, d):
                        if path in experiments and path != d.path:
                            citers.setdefault(path, set()).add(d)
                            if path not in seen:
                                seen.add(path)
                                reached.append(experiments[path])
                citing = [d for d in reached if not d.archived]
            self._citations = {path: sorted(docs, key=Doc.sort_key) for path, docs in citers.items()}
        return self._citations

    def resolve(self, src_dir, target):
        if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", target) or target.startswith("//"):
            return None
        path, _, anchor = target.partition("#")
        path = urllib.parse.unquote(path)
        if not path:
            return "self", anchor
        if path.startswith("/"):
            return Path(os.path.normpath(str(self.root / path.lstrip("/")))), anchor
        return Path(os.path.normpath(str(src_dir / path))), anchor

    def tree_files(self, ref):
        """Paths of the files in a commit's tree."""
        listing = git(self.root, "ls-tree", "-r", "-z", "--name-only", ref)
        if listing is None:
            sys.exit(unknown_ref(ref))
        return {rel for rel in listing.split("\0") if rel}

    def tree_ids(self, ref):
        """Map id -> path for the doc files in a commit's tree."""
        ids = {}
        for rel in sorted(self.tree_files(ref)):
            doc_id = path_id(rel)
            if doc_id:
                ids.setdefault(doc_id, rel)
        return ids

    def history_ids(self):
        """Ids of the doc files in the history of HEAD, those since deleted or renamed away included.
        `--full-history` walks the side branches whose docs a merge discarded, and `-m` lists the docs that only a
        merge's resolution added."""
        self.require_readable()
        if not self.has_head:
            return set()
        out = git(self.root, "log", "-z", "--format=", "--name-only", "--no-renames", "--full-history", "-m",
                  "HEAD", "--", DOCS_PATHSPEC)
        if out is None:
            sys.exit("canon: cannot read the history of HEAD")
        return {i for i in map(path_id, out.split("\0")) if i}

    def taken_ids(self):
        """Ids no new doc may get: those of the docs in the work tree and those of `history_ids`."""
        return {d.id for d in self.docs} | self.history_ids()

    def deleted_docs(self, base=None):
        """(path, commit) for each doc file deleted, not renamed: between the commit compared and the tree checked,
        where the commit is the one compared, and on this branch since `base` up to its tip, where it is the merge
        base with `base`."""
        ranges = []
        if self.compared:
            ranges.append((self.diff_args, self.compared))
        if base and (self.rev or self.has_head):
            ranges.append(((base.commit + "..." + self.head,), None))
        deleted = []
        for revs, commit in ranges:
            args = ("diff", "-z", "-M", "--name-status", "--diff-filter=D", *revs, "--", DOCS_PATHSPEC)
            if commit:
                out = git_checked(self.root, *args).stdout
            else:
                result = git_run(self.root, *args)
                if result is None or result.returncode != 0:
                    sys.exit(diff_failure(self, base.ref, result, "diff"))
                out = result.stdout
            fields = out.split("\0")
            paths = sorted(path for status, path in zip(fields[::2], fields[1::2]) if status.startswith("D"))
            if paths:
                commit = commit or base.fork
                deleted += [(path, commit) for path in paths]
        return deleted

    def checked_changes(self):
        """The files the tree checked changes against the commit compared: for the work tree its changes against
        HEAD, under `staged` the staged tree's, under `rev` the files `rev` changes against its only parent; none
        without that commit."""
        if self.compared is None:
            return set()
        if self.reads_work_tree:
            return set(self.changed_files())
        if self.staged:
            return set(self.staged_changes)
        out = git_checked(self.root, "diff", "-z", "--name-only", "--no-renames", *self.diff_args).stdout
        return {f for f in out.split("\0") if f}

    def project_files(self, root):
        prefix = root.rel + "/" if root.rel else ""
        return [f[len(prefix):] for f in self.files if f.startswith(prefix)]

    def changed_files(self, base=None):
        if not self.has_head:
            return list(self.files)
        outs = [git_checked(self.root, "diff", "-z", "--name-only", "--no-renames", "HEAD").stdout,
                git_checked(self.root, "ls-files", "-z", "-o", "--exclude-standard").stdout]
        if base:
            branch_base(self, base)
            result = git_run(self.root, "diff", "-z", "--name-only", "--no-renames", base + "..." + self.head)
            if result is None or result.returncode != 0:
                sys.exit(diff_failure(self, base, result, "diff"))
            outs.append(result.stdout)
        return sorted({f for out in outs for f in (out or "").split("\0") if f})

    def is_doc(self, rel):
        """Whether a repo-relative file is a doc by its name, such as a README, or lies under a docs root, and is no
        installed skill file."""
        name = rel.rsplit("/", 1)[-1]
        stem = name.split(".", 1)[0].upper()
        named = (stem in DOC_NAMES or stem.startswith("LICENSE-")) \
            and ("." not in name or name.lower().endswith(DOC_SUFFIXES))
        return (named or any(rel.startswith(root.docs_rel + "/") for root in self.roots)) \
            and not self.is_installed_skill(rel)

    def is_code(self, rel):
        """Whether a repo-relative file is neither a doc nor an installed skill file, the files a design's `paths`
        govern only through an entry equal to their path and coverage never counts."""
        return not (self.is_doc(rel) or self.is_installed_skill(rel))

    def is_installed_skill(self, rel):
        """Whether a repo-relative path is an installed skill file: the repo root's `skills-lock.json`, INSTALL_DIR or
        a path under it, or a link whose real path in the tree read is INSTALL_DIR or lies under it. INSTALL_DIR stays
        unresolved, so that when it is itself a link, the files it points to keep their own kind."""
        if rel in ("skills-lock.json", INSTALL_DIR) or rel.startswith(INSTALL_DIR + "/"):
            return True
        skills = self.root / INSTALL_DIR
        real = self.tree.realpath(self.root / rel)
        return real is not None and (real == skills or skills in real.parents)

    def designs_for(self, abs_path):
        """The non-archived designs whose `paths` govern a file."""
        rel = posix_rel(abs_path, self.root)
        if rel == ".." or rel.startswith("../"):
            return []
        exact = not self.is_code(rel)
        return [doc for doc in self.docs if doc.type == "D" and not doc.archived and doc.governs(rel, exact)]


# ---------------------------------------------------------------- embedded source

EMBED_OPEN = re.compile(r"<!-- embed: ([^\s]+) -->")
EMBED_CLOSE = "<!-- /embed -->"
REGION_NAME = re.compile(r"[a-zA-Z0-9_-]+")
REGION_LINE = re.compile(r"^[ \t]*(?:#|//)[ \t]*(region|endregion)(?=[ \t]|$)(.*)$")
SOURCE_LANG = {".py": "python", ".h": "cpp", ".hpp": "cpp", ".cpp": "cpp", ".capnp": "capnp"}
EmbedBlock = collections.namedtuple("EmbedBlock", "start end operand")


def embed_blocks(lines, start):
    """Disjoint, closed pairs and syntax problems, with zero-based marker lines in the Markdown body."""
    pairs, errors, stack = [], [], []
    invalid = False
    for i, line in code_mask(lines, start):
        line = line.rstrip("\r\n")
        if line.startswith("<!-- embed:"):
            match = EMBED_OPEN.fullmatch(line)
            if stack:
                errors.append((i, "nested embed marker"))
                invalid = True
            if not match:
                errors.append((i, "malformed opening embed marker"))
                invalid = True
            stack.append((i, match[1] if match else ""))
        elif line.startswith("<!-- /embed"):
            if line != EMBED_CLOSE:
                errors.append((i, "malformed closing embed marker"))
                invalid = bool(stack)
            elif not stack:
                errors.append((i, "closing embed marker has no opening marker"))
            else:
                opened, operand = stack.pop()
                if not stack:
                    if not invalid:
                        pairs.append(EmbedBlock(opened, i, operand))
                    invalid = False
    errors.extend((i, "unclosed embed marker") for i, _ in stack)
    return pairs, errors


def marked_lines(blocks):
    return {i for block in blocks for i in range(block.start, block.end + 1)}


def physical_lines(text):
    return re.findall(r"[^\r\n]*(?:\r\n|\r|\n)|[^\r\n]+$", text)


def write_markdown(path, text, numbered=True):
    """Preserve line endings across in-place edits and in paired source spans when a command adds headings or fields."""
    before = path.read_bytes().decode("utf-8")
    if "\r" in before:
        old, new = physical_lines(before), physical_lines(text)

        def blocks(lines):
            return embed_blocks(lines, parse_frontmatter(lines)[1] + 1 if numbered else 0)[0]

        if len(old) == len(new):
            spans = [(range(len(old)), range(len(new)))]
        else:
            ending = re.search(r"\r\n|\r|\n", before)[0]
            new = [line.rstrip("\r\n") + ending if line.endswith(("\r", "\n")) else line for line in new]
            spans = [(range(a.start, a.end + 1), range(b.start, b.end + 1)) for a, b in zip(blocks(old), blocks(new))]
        for original, edited in spans:
            for i, j in zip(original, edited):
                ending = old[i][len(old[i].rstrip("\r\n")):]
                if ending or j == len(new) - 1:
                    new[j] = new[j].rstrip("\r\n") + ending
        text = "".join(new)
    path.write_bytes(text.encode("utf-8"))


def source_operand(operand):
    raw, separator, region = operand.partition("#")
    if not raw or re.search(r"%(?![a-fA-F0-9]{2})", raw) or separator and not REGION_NAME.fullmatch(region):
        raise ValueError("invalid embed operand: " + operand)
    path = urllib.parse.unquote(raw, errors="strict")
    if os.path.isabs(path) or "\0" in path:
        raise ValueError("embed source needs a relative repository path: " + operand)
    return path, region


def source_fence(source, text, region):
    """Validate every delimiter, then format the selected region or the whole source without its delimiters."""
    if "\0" in text:
        raise ValueError("NUL byte in embed source " + source.name)
    body, regions, active = [], {}, None
    for i, line in enumerate(re.split(r"\r\n|\r|\n", text), 1):
        marker = REGION_LINE.match(line)
        if not marker:
            body.append(line)
            continue
        keyword, tail = marker.groups()
        name = tail.strip(" \t")
        if name and not REGION_NAME.fullmatch(name) or keyword == "region" and not name:
            raise ValueError("invalid region delimiter in {}:{}".format(source.name, i))
        if keyword == "region":
            if active is not None or name in regions:
                raise ValueError("nested or duplicate region {} in {}:{}".format(name, source.name, i))
            active = name, len(body)
        else:
            if active is None or name and name != active[0]:
                raise ValueError("unmatched endregion in {}:{}".format(source.name, i))
            regions[active[0]] = active[1], len(body)
            active = None
    if active is not None:
        raise ValueError("unclosed region {} in {}".format(active[0], source.name))
    if region:
        if region not in regions:
            raise ValueError("no region {} in {}".format(region, source.name))
        start, end = regions[region]
        body = body[start:end]
    nonblank = [i for i, line in enumerate(body) if line.strip()]
    if nonblank:
        indent = os.path.commonprefix([re.match(r"[ \t]*", body[i])[0] for i in nonblank])
        body = [line[len(indent):] if line.startswith(indent) else line for line in body[nonblank[0]:nonblank[-1]+1]]
    else:
        body = []
    longest = max((len(run) for line in body for run in re.findall(r"`+", line)), default=0)
    fence = "`" * max(3, longest + 1)
    return [fence + SOURCE_LANG.get(source.suffix, "")] + body + [fence]


class SourceEmbeds:
    """Live consumers and their source files in one repository tree."""

    def __init__(self, repo):
        self.repo = repo
        self.inventory = set(repo.files)
        self.projects = {root.project for root in repo.roots}
        self.starts = {}
        for path in repo.live_markdown:
            rel = path.relative_to(repo.root).as_posix()
            if resolve_tree_path(repo.tree, rel) == rel:
                self.starts[path] = repo.by_path[path].fm_end + 1 if path in repo.by_path else 0

    def alias_area(self, rel):
        """The live root that owns this file or directory hop, stopping at nested projects."""
        path = self.repo.root / rel
        if rel in self.inventory and path.suffix != ".md":
            return None
        if path in self.repo.live_markdown:
            return self.repo.live_markdown[path]
        for parent in (path, *path.parents):
            if parent in self.repo.live_areas:
                return self.repo.live_areas[parent]
            if parent in self.projects:
                break
        return None

    def consumer(self, path):
        if path.suffix != ".md":
            return None
        try:
            relative = path.relative_to(self.repo.root).as_posix()
        except ValueError:
            return None
        aliases = []
        resolved = resolve_tree_path(self.repo.tree, relative, aliases)
        real = self.repo.root / resolved if resolved is not None else None
        if real not in self.starts:
            return None
        if any(self.alias_area(hop) is not self.repo.live_markdown[real] for hop in aliases):
            return None
        return real

    def selected(self, names):
        selected, errors = set(), []
        for name in names:
            if FULL_ID_RE.fullmatch(name):
                try:
                    doc = self.repo.get(name)
                except SystemExit as error:
                    errors.append(str(error))
                    continue
                path = self.consumer(doc.path)
                if path:
                    attached = path.parent / doc.id
                    selected.update(p for p in self.starts if attached in p.parents)
            else:
                path = self.consumer(Path.cwd() / name)
            if path is None:
                errors.append("canon: {} is not a live embed consumer".format(name))
            else:
                selected.add(path)
        return sorted(selected if names else self.starts), errors

    def source_file(self, relative, label, walked=None):
        rel = resolve_tree_path(self.repo.tree, relative, walked=walked)
        if rel not in self.inventory:
            raise ValueError("source is not a repository file: " + label)
        return self.repo.root / rel

    def source(self, path, operand, walked=None):
        parent = path.parent.relative_to(self.repo.root).as_posix()
        relative, region = source_operand(operand)
        return self.source_file(parent + "/" + relative, operand, walked), region

    def resolved_blocks(self, path, blocks):
        """The pairs with resolvable source paths, independent of whether their blocks can be rendered."""
        for block in blocks:
            walked = set()
            try:
                source, region = self.source(path, block.operand, walked)
            except (OSError, ValueError):
                continue
            yield block, source, region, walked

    def consumers_of(self, name):
        """Find live documents by the resolved source of their markers, without rendering their blocks."""
        # Keep the last component literal: "file/" and "file/." both require a directory.
        directory, filename = os.path.split(name)
        parent = Path.cwd() / directory
        if parent == self.repo.root or self.repo.root in parent.parents:
            parent = parent.relative_to(self.repo.root)
        try:
            target = self.source_file(parent.as_posix() + "/" + filename, name)
        except (OSError, ValueError) as error:
            sys.exit("canon: " + str(error))
        matches = []
        for consumer, start in self.starts.items():
            try:
                text = self.repo.tree.read_text(consumer)
            except (OSError, UnicodeError) as error:
                sys.exit("canon: cannot read {}: {}".format(posix_rel(consumer, self.repo.root), error))
            if "<!-- embed:" in text:
                pairs, _ = embed_blocks(text.split("\n"), start)
                if any(source == target for _, source, _, _ in self.resolved_blocks(consumer, pairs)):
                    matches.append(consumer)
        return sorted(matches, key=lambda p: p.as_posix())

    def move_editor(self, moves, adopted, destination):
        """For this move set, find protected lines and edits to marker operands in each original Markdown file."""
        repo = self.repo
        moved_entries = {posix_rel(path, repo.root) for path in moves}
        new_attachments = {moves[src].parent / doc_id for src, doc_id in adopted.items()}
        archive_dirs = {root.docs / "archived" for root in repo.roots}
        starts = dict(self.starts)
        starts.update((d.path, d.fm_end + 1) for d in repo.docs if d.archived and d.fm is not None)
        starts.update((repo.root / rel, 0) for _root, archived, _id, rel in repo.attachments
                      if archived and rel.endswith(".md"))

        def edit(path, lines):
            start = starts.get(path)
            if path in adopted:
                start = parse_frontmatter(lines)[1] + 1
            elif not new_attachments.isdisjoint(path.parents):
                start = 0
            blocks = embed_blocks(lines, start)[0] if start is not None else ()
            new_path = destination(path)
            edits = {}
            if blocks and archive_dirs.isdisjoint(new_path.parents):
                for block, source, region, walked in self.resolved_blocks(path, blocks):
                    if source != path and (new_path != path or not moved_entries.isdisjoint(walked)):
                        relative = posix_rel(destination(source), new_path.parent)
                        relative = re.sub(r"[%#\s]", lambda m: urllib.parse.quote(m[0], safe=""), relative)
                        marker = EMBED_OPEN.match(lines[block.start])
                        edits[block.start] = [(*marker.span(1), relative + ("#" + region if region else ""))]
            return marked_lines(blocks), edits

        return edit

    def update(self, path, problems, check=False):
        try:
            text = self.repo.tree.read_bytes(path).decode("utf-8")
        except (OSError, UnicodeError) as error:
            problems.append((path, 1, str(error)))
            return None
        if "<!-- embed:" not in text and "<!-- /embed" not in text:
            return None
        lines = physical_lines(text)
        blocks, errors = embed_blocks(lines, self.starts[path])
        problems.extend((path, i + 1, error) for i, error in errors)
        for start, end, operand in reversed(blocks):
            try:
                source, region = self.source(path, operand)
                if source == path:
                    raise ValueError("embed source is the consumer itself: " + operand)
                source_text = self.repo.tree.read_text(source)
                if source in self.starts and any(embed_blocks(source_text.split("\n"), self.starts[source])):
                    raise ValueError("embed source contains an active embed: " + operand)
                block = source_fence(source, source_text, region)
            except (OSError, ValueError) as error:
                problems.append((path, start + 1, str(error)))
                continue
            if block == [line.rstrip("\r\n") for line in lines[start + 1:end]]:
                continue
            if check:
                problems.append((path, start + 1, "stale embed"))
                continue
            eol = lines[start][len(lines[start].rstrip("\r\n")):]
            lines[start + 1:end] = [line + eol for line in block]
        result = "".join(lines)
        return result if result != text else None

    def diagnostic_hint(self, path, reason):
        if self.repo.staged:
            return "; generate against the source intended for the commit and stage the matching block"
        if self.repo.rev:
            return " in commit " + self.repo.rev
        if reason == "stale embed":
            return "; run `canon.py embed {}`".format(shlex.quote(posix_rel(path, Path.cwd())))
        return ""


def cmd_embed(repo, args):
    if args.list_only and args.source is None:
        sys.exit("canon: --list requires --source FILE")
    return process_embeds(repo, args.docs, args.check, source=args.source, list_only=args.list_only)


def process_embeds(repo, names, check, source=None, list_only=False):
    """Check the selected live consumers or regenerate them together once every input is valid."""
    embeds = SourceEmbeds(repo)
    updates, problems = {}, []
    if source is None:
        selected, errors = embeds.selected(names)
    else:
        selected, errors = embeds.consumers_of(source), []
        if list_only:
            for path in selected:
                name = posix_rel(path, repo.root)
                print(name.replace("\\", "\\\\").replace("\r", "\\r").replace("\n", "\\n"))
            return 0
    for path in selected:
        updated = embeds.update(path, problems, check=check)
        if updated is not None:
            updates[path] = updated
    if errors or problems:
        for error in errors:
            print(error, file=sys.stderr)
        for path, line, reason in sorted(problems):
            print("ERROR {}:{}: {}{}".format(posix_rel(path, repo.root), line, reason,
                                             embeds.diagnostic_hint(path, reason)))
        return 1
    for path, text in updates.items():
        # Replacing this directory entry leaves even an unselected hard link untouched.
        with tempfile.TemporaryDirectory(dir=path.parent) as directory:
            updated = Path(directory) / path.name
            updated.write_bytes(text.encode("utf-8"))
            shutil.copymode(path, updated)
            updated.replace(path)
        print("updated " + posix_rel(path, repo.root))
    return 0


# ---------------------------------------------------------------- index

def index_block(repo, root, archived, base_dir):
    lines = []
    docs = [d for d in repo.docs if d.root is root and d.archived == archived]
    for letter in TYPE_ORDER:
        group = [d for d in docs if d.type == letter]
        if not group:
            continue
        lines += ["### " + TYPES[letter]["dir"].capitalize(), ""]
        for d in group:
            label = issue_label(d)
            parts = ["- [{}: {}]({})".format(d.id, d.title or "?", posix_rel(d.path, base_dir)), d.status]
            parts += [label] if label else []
            parts.append(str(d.get("summary", "") or "?"))
            if d.as_list("owns"):
                parts.append("owns: " + ", ".join(d.as_list("owns")))
            if d.as_list("modules"):
                parts.append("modules: " + ", ".join(d.as_list("modules")))
            lines.append(" · ".join(parts))
        lines.append("")
    body = "\n".join(lines).strip() or "No documents."
    return INDEX_START + "\n\n" + body + "\n\n" + INDEX_END


def marker_span(text, start_marker, end_marker):
    """The span of a marked block in `text`, from its first start marker through the first end marker after it; None
    without a start marker, and an end of None when no end marker follows the start marker."""
    start = text.find(start_marker)
    if start < 0:
        return None
    end = text.find(end_marker, start)
    return start, end + len(end_marker) if end >= 0 else None


def broken_indexes(repo, project=None):
    """The `docs/README.md` files whose first index start marker has no end marker after it, in every docs root and in
    `project`, which `init` is about to make one."""
    readmes = [root.docs / "README.md" for root in repo.roots] + ([project / "docs/README.md"] if project else [])
    broken = []
    for readme in readmes:
        span = marker_span(repo.tree.read_text(readme), INDEX_START, INDEX_END) if repo.tree.is_file(readme) else None
        if span and span[1] is None:
            broken.append(readme)
    return broken


def require_intact_indexes(repo, project=None):
    """Exit before a command changes any file when regenerating an index would lose the text after a start marker
    with no end marker."""
    broken = broken_indexes(repo, project)
    if broken:
        sys.exit("canon: {} has an index start marker with no end marker after it; fix the markers and rerun"
                 .format(posix_rel(broken[0], repo.root)))


def expected_indexes(repo):
    """Return {path: expected_text} for every docs root, leaving out each `broken_indexes` file."""
    out = {}
    for root in repo.roots:
        if not repo.tree.is_dir(root.docs):
            continue
        readme = root.docs / "README.md"
        current = repo.tree.read_text(readme) if repo.tree.is_file(readme) else None
        span = marker_span(current, INDEX_START, INDEX_END) if current is not None else None
        block = index_block(repo, root, False, root.docs)
        if current is None:
            out[readme] = "# Docs\n\n" + block + "\n"
        elif span is None:
            out[readme] = current.rstrip("\n") + "\n\n" + block + "\n"
        elif span[1] is not None:
            out[readme] = current[:span[0]] + block + current[span[1]:]
        archive_dir = root.docs / "archived"
        if any(d.root is root and d.archived for d in repo.docs) or repo.tree.is_file(archive_dir / "README.md"):
            out[archive_dir / "README.md"] = "# Archived docs\n\n" + index_block(repo, root, True, archive_dir) + "\n"
    return out


def write_indexes(repo):
    written = []
    for path, text in expected_indexes(repo).items():
        if not path.is_file() or path.read_text(encoding="utf-8") != text:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
            written.append(posix_rel(path, repo.root))
    return written


def stage_indexes(repo):
    """Stage each index file of the staged tree `repo` whose staged entry is missing or holds other text, keeping a
    staged mode of 100644 or 100755; the paths staged."""
    staged = []
    for path, text in expected_indexes(repo).items():
        if repo.tree.is_file(path) and repo.tree.read_text(path) == text:
            continue
        rel = posix_rel(path, repo.root)
        mode = repo.tree.entries.get(rel, ("100644",))[0]
        blob = git_checked(repo.root, "hash-object", "-w", "--stdin", data=text.encode("utf-8")).stdout.strip()
        git_checked(repo.root, "update-index", "--add", "--cacheinfo", "{},{},{}".format(
            mode if mode in ("100644", "100755") else "100644", blob, rel))
        staged.append(rel)
    return staged


# ---------------------------------------------------------------- check

def check_links(repo, path, lines, start, doc=None):
    rel = posix_rel(path, repo.root)
    linked = set()
    own = {h.slug for h in scan_headings(lines, start)}
    for i, match in iter_links(lines, start):
        image, text, target = match.group(1), match.group(2), match.group(3)
        resolved = repo.resolve(path.parent, target)
        if resolved is None:
            continue
        dest, anchor = resolved
        if dest == "self":
            if anchor and anchor not in own:
                repo.problem("ERROR", rel, "missing anchor #" + anchor, i + 1)
            continue
        if not repo.tree.exists(dest):
            repo.problem("ERROR", rel, "broken link " + target, i + 1)
            continue
        target_doc = repo.by_path.get(dest)
        if target_doc and not image:
            linked.add(target_doc.id)
            ref = REF_TEXT_RE.match(text)
            want = "[{0}: ...] or [{0}§slug: ...] with #slug".format(target_doc.id)
            if not ref or ref.group(1) != target_doc.id:
                repo.problem("ERROR", rel, "link to {} must read {}".format(target_doc.id, want), i + 1)
            elif (ref.group(2) or "") != anchor:
                repo.problem("ERROR", rel, "link text section and #anchor differ; use " + want, i + 1)
        if anchor and dest.suffix == ".md":
            slugs = repo.slugs(dest)
            if slugs is None:
                repo.problem("ERROR", rel, "anchor target is not UTF-8: " + target, i + 1)
            elif anchor not in slugs:
                repo.problem("ERROR", rel, "missing anchor #{} in {}".format(anchor, posix_rel(dest, repo.root)), i + 1)
    return linked


def plan_slices(doc):
    """List [name, status] for each `### ` slice in a plan's Slices section."""
    slices = []
    for _i, line in code_mask(doc.section("Slices") or []):
        heading = HEADING_RE.match(line)
        if heading and len(heading.group(1)) == 3:
            slices.append([heading.group(2), None])
        elif slices and slices[-1][1] is None:
            match = STATUS_LINE_RE.match(line.replace("*", ""))
            if match:
                slices[-1][1] = match.group(1)
    return slices


def experiment_setup_problems(doc):
    sources = []
    runs = []
    for label, value in doc.label_items("Setup", ignore_fenced_labels=True):
        if label == SOURCES_LABEL:
            sources.append(value)
        elif label in SETUP_LABELS:
            if not runs or label in runs[-1]:
                runs.append({})
            runs[-1][label] = value
    problems = ["Setup: `Sources` is empty" for source in sources if not source]
    if not runs and not sources:
        runs.append({})
    for number, run in enumerate(runs, 1):
        hint = "" if sources else " (research lists `- Sources:` instead)"
        if len(runs) > 1:
            hint = " (run {})".format(number)
        problems.extend("Setup: `{}` is empty{}".format(label, hint)
                        for label in SETUP_LABELS if not run.get(label))
    return problems


def terminal_problems(doc, status=None):
    """Conditions a doc must meet before it may take a terminal status."""
    out = []
    if doc.type == "P" and (status or doc.status) == "done":
        slices = plan_slices(doc)
        if not slices:
            out.append("plan has no slices")
        out += ["slice `{}` is {}, not done".format(name, state or "without status")
                for name, state in slices if state != "done"]
    if doc.type == "R":
        for fid, _sev, disp in review_findings(doc)[0]:
            if disp.split(" ", 1)[0] == "open":
                out.append("finding {} is still open".format(fid))
    if doc.type == "D":
        out += ["known issue {} is still listed; move it to the design that takes over, or remove it".format(row[0])
                for row in known_issues(doc)[0]]
    if doc.type == "E" and (status or doc.status) != "dropped":
        out += experiment_setup_problems(doc)
    if doc.type == "I":
        labels = doc.labels("Reproduction")
        out += ["Reproduction: `{}` is empty".format(k) for k in SETUP_LABELS if not labels.get(k)]
    if doc.type == "I":
        labels = doc.labels("Resolution")
        out += ["Resolution: `{}` is empty".format(k) for k in RESOLUTION_LABELS if not labels.get(k)]
    if doc.type == "E" and not GUIDANCE_RE.sub("", "\n".join(doc.section("Conclusion") or [])).strip():
        out.append("Conclusion is empty")
    return out


def id_table(doc, section, name, letter, columns):
    """The rows of the table under `section` whose first cell is an id `<doc id>-<letter><n>`, followed by
    `columns`, each as its list of cells; cells beyond those are ignored. Also an error for each row that does not
    fit."""
    rows, errors = [], []
    for _i, line in code_mask(doc.section(section) or []):
        if not line.strip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        first = cells[0]
        if first.lower() == "id" or (first and set(first) <= set("-: ")):
            continue
        if not re.match(r"^{}-{}\d+$".format(re.escape(doc.id), letter), first) or len(cells) <= len(columns):
            errors.append("{} row must be | {}-{}<n> | {} |".format(name, doc.id, letter, " | ".join(columns)))
            continue
        rows.append(cells[:len(columns) + 1])
    return rows, errors


def id_row_problems(rows, name):
    """Duplicate ids and unknown severities among rows that start with an id and a severity."""
    out, seen = [], set()
    for row in rows:
        if row[0] in seen:
            out.append("duplicate {} id {}".format(name, row[0]))
        seen.add(row[0])
        if row[1] not in SEVERITIES:
            out.append("{} severity must be one of {}".format(row[0], ", ".join(SEVERITIES)))
    return out


def review_findings(doc):
    rows, errors = id_table(doc, "Findings", "finding", "F", ("severity", "finding", "disposition"))
    return [(row[0], row[1], row[3]) for row in rows], errors


def known_issues(doc):
    """(id, severity, issue, source, since, next) for each row of a design's Known issues table, and the problems
    of the rows that do not fit it."""
    return id_table(doc, ISSUES_SECTION, "known issue", "K", ("severity", "issue", "source", "since", "next"))


def issue_label(doc):
    """How many known issues a design lists, as `2 known issues`; empty when it lists none."""
    count = len(known_issues(doc)[0]) if doc.type == "D" else 0
    return counted(count, "known issue", "known issues") if count else ""


def issue_rows_only(old, new):
    """Whether a design's change from text `old` to `new` lies in its Known issues table alone, blank lines,
    `updated` and `refs` aside: such a change does not check the design against its code."""
    def split(text):
        lines = text.split("\n")
        heads = scan_headings(lines)
        start = next((h for h in heads if h.level == 2 and h.text == ISSUES_SECTION), None)
        end = next((h.line for h in heads if start and h.line > start.line and h.level <= 2), len(lines))
        table = lines[start.line:end] if start else []
        rest = lines[:start.line] + lines[end:] if start else lines
        return [line for line in rest if line.strip() and not line.startswith(("updated:", "refs:"))], table

    old_rest, old_table = split(old)
    new_rest, new_table = split(new)
    return old_rest == new_rest and old_table != new_table


def plan_designs(doc):
    return {entry.split("@")[0] for entry in doc.as_list("based_on")}


def content_lines(lines):
    """Lines that count as a content change for `updated`; `implemented` tracks the code and `as_built` the
    pending gate, not the doc."""
    return [line for line in lines if not line.startswith(("implemented:", "as_built:"))]


def line_count(lines):
    """How many lines a text split at newlines holds: as `wc -l` counts them, plus a last line without a newline."""
    return len(lines) - 1 if lines and lines[-1] == "" else len(lines)


def unfinished_problems(doc):
    """An empty `summary` and leftover template guidance, which only an unfinished doc may have."""
    out = []
    if not str(doc.get("summary", "")).strip():
        out.append("`summary` is empty")
    if any(GUIDANCE in INLINE_CODE_RE.sub("", line) for _i, line in code_mask(doc.lines)):
        out.append("template guidance `<!-- canon: ... -->` left in the doc")
    return out


def check_doc(repo, doc, changed, embeds, strict=False):
    rel, fm, info = doc.rel, doc.fm, TYPES[doc.type]

    def err(msg, fix=None):
        repo.problem("ERROR", rel, msg, fix=fix)

    if fm is None:
        err("missing or unterminated `---` frontmatter")
        return
    old = git(repo.root, "show", "{}:{}".format(repo.compared, rel)) if rel in changed else None
    old_lines = old.split("\n") if old is not None else None
    old_fm = (parse_frontmatter(old_lines)[0] or {}) if old_lines else {}
    for line in doc.fm_bad:
        err("unparseable frontmatter line: " + line)
    allowed = COMMON_FIELDS + TYPE_FIELDS.get(doc.type, ()) + OPTIONAL_FIELDS.get(doc.type, ())
    for key in fm:
        if key not in allowed:
            err("unknown frontmatter field `{}`".format(key))
    for key in COMMON_FIELDS + TYPE_FIELDS.get(doc.type, ()):
        if key not in fm:
            err("missing frontmatter field `{}`".format(key))
    for key in LIST_FIELDS & set(fm):
        if not isinstance(fm[key], list):
            err("`{}` must be a list like [a, b]".format(key))

    status = fm.get("status")
    past_gate = (doc.type == "D" and status in ("accepted", "active")) or \
        (doc.type == "P" and status in ("accepted", "in-progress"))
    answered = doc.type == "E" and status == "answered"
    unfinished_level = "WARN" if not (strict or past_gate or answered) and status in info["active"] else "ERROR"
    if status is None:
        pass
    elif status not in info["active"] + info["terminal"]:
        err("status `{}` invalid; use one of {}".format(status, ", ".join(info["active"] + info["terminal"])))
    elif status in info["terminal"] and not doc.archived and LIVE_TERMINAL.get(doc.type) != status:
        err("status `{}` requires the doc to be in archived/; use `canon.py archive`".format(status))
    elif status not in info["terminal"] and doc.archived:
        err("status `{}` requires the doc to be outside archived/; set one of {}".format(
            status, ", ".join(info["terminal"])))
    elif status in info["terminal"]:
        for msg in terminal_problems(doc):
            err(msg)
        if doc.type == "C" and not doc.archived and doc.path not in repo.design_linked():
            repo.problem("WARN", rel, "adopted, but no design links it")
        if doc.type == "E" and status == "concluded":
            citers = repo.citations().get(doc.path)
            if not doc.archived and not citers:
                repo.problem("WARN", rel, "concluded, but no live doc cites it; link it or archive it as concluded")
            elif doc.archived and citers:
                repo.problem("WARN", rel, "concluded, but linked by {}; a cited concluded experiment stays live, so "
                                          "move it and its attachment directory out of archived/ and fix the links, or "
                                          "remove the links that do not rest on its result"
                             .format(", ".join(d.id for d in citers)), also=tuple(d.rel for d in citers))
    elif answered:
        for msg in terminal_problems(doc, "concluded"):
            err(msg)

    created, updated = parse_date(fm.get("created")), parse_date(fm.get("updated"))
    for key, value in (("created", created), ("updated", updated)):
        if key in fm and (value is None or not DATE_RE.match(str(fm[key]))):
            err("`{}` must be YYYY-MM-DD".format(key))
    if created and updated and updated < created:
        err("`updated` is earlier than `created`")
    if not isinstance(fm.get("revision"), int) or fm["revision"] < 1:
        err("`revision` must be a positive integer")
    for msg in unfinished_problems(doc):
        repo.problem(unfinished_level, rel, msg)
    summary = str(fm.get("summary", "")).strip()
    if len(summary) > MAX_SUMMARY:
        repo.problem("WARN", rel, "`summary` is {} chars (max {})".format(len(summary), MAX_SUMMARY))

    h1 = [h for h in doc.headings if h.level == 1]
    if len(h1) != 1 or not doc.title:
        err("body must have exactly one H1 reading `# {}: <title>`".format(doc.id))
    names = [h.text for h in doc.headings if h.level == 2]
    for name in info["sections"]:
        if name not in names:
            err("missing section `## {}`".format(name))
    count = line_count(doc.lines)
    if count > MAX_DOC_LINES and doc.path in embeds.starts:
        blocks, _errors = embed_blocks(doc.lines, doc.fm_end + 1)
        count -= sum(block.end - block.start - 1 for block in blocks)
    if not doc.archived and count > MAX_DOC_LINES:
        if doc.type == "D":
            hint = "; make it a new top-level design" if doc.suffix \
                else "; split into sub-designs ({0}A, {0}B, ...)".format(doc.id)
        elif doc.type == "C":
            hint = "; split it into several concepts"
        else:
            hint = "; move detail into {}/".format(posix_rel(doc.path.parent / doc.id, repo.root))
        repo.problem("WARN", rel, "{} lines (max {}){}".format(count, MAX_DOC_LINES, hint))

    refs = doc.as_list("refs")
    for ref in refs:
        if ref not in repo.by_id:
            err("`refs` entry {} does not exist".format(ref))
    linked = check_links(repo, doc.path, doc.lines, doc.fm_end + 1, doc)
    missing = sorted(linked - set(refs) - {doc.id})
    if missing:
        err("linked docs missing from `refs`: " + ", ".join(missing), fix=(doc, "refs", refs + missing))

    reviewed = fm.get("reviewed")
    if reviewed is not None and "reviewed" in OPTIONAL_FIELDS.get(doc.type, ()):
        if not isinstance(reviewed, int) or reviewed > doc.revision:
            err("`reviewed` must be an integer revision not above `revision`")
        if not doc.as_list("reviewers"):
            err("`reviewers` must list who reviewed revision {}".format(reviewed))
    if doc.type == "P" and status == "in-progress" and reviewed is None:
        err("plan in progress without `reviewed`")
    elif past_gate and reviewed != doc.revision:
        repo.problem("ERROR" if strict else "WARN", rel, "revision {} is not reviewed (reviewed: {}); pass the review "
                     "gate, then set `reviewed` and `reviewers`".format(doc.revision, "none" if reviewed is None else reviewed))
    approved = fm.get("approved")
    if approved is not None and "approved" in OPTIONAL_FIELDS.get(doc.type, ()):
        if not isinstance(approved, int) or not 1 <= approved <= doc.reviewed:
            err("`approved` must be an integer revision from 1 to `reviewed`")

    if doc.type == "D":
        implemented = fm.get("implemented")
        if implemented is not None:
            if not isinstance(implemented, int) or not 1 <= implemented <= doc.revision:
                err("`implemented` must be an integer revision from 1 to `revision`")
            elif isinstance(reviewed, int) and implemented > reviewed:
                err("`implemented` r{} is above `reviewed` r{}; implement only reviewed revisions"
                    .format(implemented, reviewed))
            if status in ("draft", "accepted"):
                err("`implemented` is set but status is `{}`; a design whose code has landed is `active`"
                    .format(status))
        elif status == "active":
            # A design became active once its code landed, so one never revised implements r1; for a revised
            # design only the code and the history can tell.
            planned = any(p.type == "P" and not p.archived and doc.id in plan_designs(p) for p in repo.docs)
            fix = (doc, "implemented", 1) if old_fm.get("revision", doc.revision) == 1 and not planned else None
            err("active design needs `implemented`: the revision its code fully implements", fix=fix)
        as_built = fm.get("as_built")
        if as_built is not None:
            if reviewed is not None and reviewed == fm.get("revision"):
                err("`as_built` remains on revision {}, which is reviewed; the gate deletes it when it sets "
                    "`reviewed`".format(reviewed), fix=(doc, "as_built", None))
            elif not names_commit(repo, as_built) and not (as_built == "worktree" and not repo.has_head):
                err("`as_built` `{}` names no commit; give the hex name, at least 7 digits, of the commit the "
                    "revision records, or `worktree` outside Git or before the first commit".format(as_built))
        if doc.suffix and "D" + doc.digits not in repo.by_id:
            err("sub-design needs parent D{}".format(doc.digits))
        for topic in doc.as_list("owns"):
            if not SLUG_RE.match(topic):
                err("`owns` entry `{}` must be kebab-case".format(topic))
        files = None
        for pattern in [] if doc.archived or not doc.implemented else doc.as_list("paths"):
            files = files if files is not None else repo.project_files(doc.root)
            rx = glob_regex(pattern)
            if not any(rx.match(f) for f in files):
                repo.problem("WARN", rel, "`paths` entry `{}` matches no file".format(pattern))
        issues, errors = known_issues(doc)
        for msg in errors + id_row_problems(issues, "known issue"):
            err(msg)
        if not issues and not errors and doc.section(ISSUES_SECTION) is not None:
            repo.problem("WARN", rel, "`## {}` lists no issue; delete the section".format(ISSUES_SECTION))
        for kid, _severity, issue, source, since, next_step in issues:
            if not issue or not source:
                err("{} needs the issue and its source".format(kid))
            recorded = parse_date(since) if DATE_RE.match(since) else None
            if recorded is None:
                err("{} since must be the date it was recorded, YYYY-MM-DD".format(kid))
            elif recorded > datetime.date.today():
                err("{} since {} is later than today".format(kid, since))
            if next_step not in NEXT_STEPS:
                err("{} next must be one of {}".format(kid, ", ".join(NEXT_STEPS)))
    if doc.type == "P":
        for name, state in plan_slices(doc):
            if state not in SLICE_STATUSES:
                err("slice `{}` needs a `Status:` line with one of {}".format(name, ", ".join(SLICE_STATUSES)))
        for entry in doc.as_list("based_on"):
            match = BASED_ON_RE.match(entry)
            if not match:
                err("`based_on` entry `{}` must look like D003@r4".format(entry))
                continue
            design = repo.by_id.get(match.group(1))
            if design is None:
                err("`based_on` design {} does not exist".format(match.group(1)))
            elif status in info["active"] and design.revision > int(match.group(2)):
                repo.problem("WARN", rel, "based on {} but {} is at r{}; re-check the plan and update `based_on`"
                             .format(entry, design.id, design.revision), also=(design.rel,))
    if doc.type == "R":
        findings, errors = review_findings(doc)
        for msg in errors + id_row_problems(findings, "finding"):
            err(msg)
        for fid, _severity, disposition in findings:
            word, _, arg = disposition.partition(" ")
            if word not in DISPOSITIONS:
                err("{} disposition must start with one of {}".format(fid, ", ".join(DISPOSITIONS)))
            elif word == "moved" and arg.strip() not in repo.by_id:
                err("{} moved to unknown doc `{}`".format(fid, arg.strip()))
            elif word == "fixed":
                match = FIXED_IN_DOC_RE.match(arg.strip())
                if match and match.group(1) not in repo.by_id:
                    err("{} fixed in unknown doc `{}`".format(fid, match.group(1)))

    if old_lines is not None and content_lines(old_lines) != content_lines(doc.lines) \
            and old_fm.get("updated") == fm.get("updated") not in repo.days:
        err("content changed but `updated` was not bumped", fix=(doc, "updated", today()))


def commit_name(root, value, env=None):
    """The full name of the commit that `value` names when it is the hex object name of exactly one commit, full or
    of at least 7 digits; else None. A ref such as HEAD or a branch names none, even one named like a hash, since it
    moves once the change commits."""
    if not isinstance(value, str) or not HEX_NAME_RE.match(value):
        return None
    objects = (git(root, "rev-parse", "--disambiguate=" + value, env=env) or "").split()
    commits = [name for name in objects if (git(root, "cat-file", "-t", name, env=env) or "").strip() == "commit"]
    return commits[0] if len(commits) == 1 else None


def names_commit(repo, value):
    return commit_name(repo.root, value) is not None


def owned_architecture(repo, commit, rel):
    """Whether the doc at `rel` in `commit` was a non-archived design owning `architecture`, which `init` moves to
    D000: once D000 is filled out, Git no longer pairs the two as a rename."""
    if (path_id(rel) or "")[:1] != "D" or "/docs/archived/" in "/" + rel:
        return False
    owns = (parse_frontmatter((git(repo.root, "show", "{}:{}".format(commit, rel)) or "").split("\n"))[0] or {}) \
        .get("owns")
    return isinstance(owns, list) and "architecture" in owns


def check_overview(repo):
    """The rules for D000: the repo root's docs/ holds it, live, and no other docs root holds one; its Spec holds
    the four subsections; its `paths` list only files; its Modules Paths are directories of the project, unless their
    row links designs and none of them has `implemented`."""
    overview = root_overview(repo)
    if overview is None:
        archived = root_overview(repo, archived=True)
        if archived:
            repo.problem("ERROR", archived.rel, "D000 is archived, but every project keeps its project overview; move "
                         "it back to docs/designs/ with a live status")
        else:
            repo.problem("ERROR", "docs", "no D000, the project overview every project keeps; run `canon.py init` "
                         "at the repo root")
    for doc in repo.docs:
        if doc.id == OVERVIEW_ID and doc.root.rel:
            repo.problem("ERROR", doc.rel, "D000 belongs only in the repo root's docs/; give this doc another id with "
                         "`canon.py renumber {}`".format(doc.rel))
    if overview is None:
        return
    present = {overview.headings[i].text for i in overview.spec_subsections()}
    missing = ["`### {}`".format(name) for name, _body in OVERVIEW_SPEC if name not in present]
    if missing and overview.section("Spec") is not None:
        names = [name for name, _body in OVERVIEW_SPEC]
        repo.problem("ERROR", overview.rel, "`## Spec` lacks {}; D000's Spec holds the subsections {} and {}".format(
            ", ".join(missing), ", ".join(names[:-1]), names[-1]))
    for pattern in overview.as_list("paths"):
        entry = entry_path(pattern)
        if any(c in entry for c in "*?[") or entry.endswith("/") or repo.tree.is_dir(overview.root.project / entry):
            repo.problem("ERROR", overview.rel, "`paths` entry `{}` names a glob or directory; D000's `paths` list "
                         "only files, since a glob or directory makes every file under it look governed"
                         .format(pattern))
    for entries, design_cell in overview.module_rows():
        linked = linked_designs(repo, overview, design_cell)
        if linked and not any(d.implemented for d in linked):
            continue
        for entry in entries:
            if module_dir(repo, overview, entry) is None:
                repo.problem("WARN", overview.rel, "Modules Path `{}` is not a directory of the project".format(entry))


def linked_designs(repo, doc, text):
    """The designs that the links in `text`, a line of `doc`, point to; images and other targets count for none."""
    found = []
    for match, dest in link_targets(repo, doc.path, [text]):
        target = None if match.group(1) else repo.by_path.get(dest)
        if target and target.type == "D":
            found.append(target)
    return found


def unknown_ref(ref):
    return "canon: unknown ref {}; fetch it first or correct the name".format(ref)


def require_commit(repo, ref):
    """Resolve a --base value to its commit, or end the command."""
    commit = None if ref.startswith("-") else git(repo.root, "rev-parse", "--verify", "-q", ref + "^{commit}")
    if commit is None:
        sys.exit(unknown_ref(ref))
    return commit.strip()


def diff_failure(repo, base, result, subcommand):
    return "canon: cannot diff against {}...{}: {}".format(base, repo.tip, git_failure(result, subcommand))


BranchBase = collections.namedtuple("BranchBase", "ref commit fork")


def branch_base(repo, base):
    """Resolve the named base and its merge base with the selected tip once for the branch comparison."""
    if not (repo.rev or repo.has_head):
        sys.exit("canon: no merge base with " + base)
    commit = require_commit(repo, base)
    result = git_run(repo.root, "merge-base", repo.head, commit)
    if result is not None and result.returncode == 0:
        return BranchBase(base, commit, result.stdout.strip())
    if result is not None and result.returncode == 1:
        if (git(repo.root, "rev-parse", "--is-shallow-repository") or "").strip() == "true":
            sys.exit("canon: no merge base with {} in this shallow clone; fetch the full history with "
                     "`git fetch --unshallow`".format(base))
        sys.exit("canon: no merge base with " + base)
    sys.exit(diff_failure(repo, base, result, "merge-base"))


def named_docs(repo, names):
    """The docs `check`'s ID or PATH arguments name, each once: an id names the doc `get` resolves, as for `archive`,
    and any other argument the doc whose file it is, relative to the working directory."""
    docs = []
    for name in names:
        match = FULL_ID_RE.match(name)
        doc = repo.get(name) if match and well_formed_id(match) else repo.by_path.get(Path(os.path.realpath(name)))
        if doc is None:
            sys.exit("canon: {} names no doc; give a doc id or the path of a doc file".format(name))
        if doc not in docs:
            docs.append(doc)
    return docs


def attachment_dirs(repo, docs):
    """The repo-relative paths of the attachment directories of `docs`, each ending with `/`."""
    return tuple(posix_rel(doc.path.parent / doc.id, repo.root) + "/" for doc in docs)


def run_check(repo, base=None, named=None, strict=False):
    """Record the problems `check` finds in `repo`; with `named`, the docs the command names, only those on their
    files, those between docs that involve one of them, and those on the `.md` files in their attachment directories,
    leaving `AGENTS.md`, guides, indexes, old copies and deleted docs unchecked. Every doc is checked either way, since
    a problem recorded on one doc may involve a named one."""
    strict = strict or base is not None
    changed = repo.checked_changes()
    embeds = SourceEmbeds(repo)
    for doc in repo.docs:
        check_doc(repo, doc, changed, embeds, strict=strict)

    owners = {}
    for doc in repo.docs:
        if doc.type == "D" and not doc.archived:
            for topic in doc.as_list("owns"):
                if topic in owners:
                    repo.problem("ERROR", doc.rel, "topic `{}` is already owned by {}".format(topic, owners[topic].id),
                                 also=(owners[topic].rel,))
                owners.setdefault(topic, doc)

    for root, archived, name, rel in repo.attachments:
        doc = repo.by_id.get(name)
        if not doc or doc.root is not root or doc.archived != archived:
            repo.problem("ERROR", rel, "attachment directory {} has no matching doc beside it".format(name))

    attached = attachment_dirs(repo, named or [])
    problems = []
    named_paths = {doc.path for doc in named or []}
    for path in embeds.starts:
        if named is None or path in named_paths or posix_rel(path, repo.root).startswith(attached):
            embeds.update(path, problems, check=True)
    for path, line, reason in problems:
        repo.problem("ERROR", posix_rel(path, repo.root), reason, line, tree_hint=embeds.diagnostic_hint(path, reason))
    scope = repo.scope_md if named is None else \
        [path for path in repo.scope_md if posix_rel(path, repo.root).startswith(attached)]
    for path in scope:
        if path in repo.live_markdown and path not in embeds.starts:
            continue
        if not repo.tree.is_file(path):
            continue
        try:
            lines = repo.tree.read_text(path).split("\n")
        except UnicodeDecodeError:
            if path not in embeds.starts:
                repo.problem("ERROR", posix_rel(path, repo.root), "document is not UTF-8")
            continue
        check_links(repo, path, lines, 0)
        if path.name == "AGENTS.md" and line_count(lines) > MAX_AGENTS_LINES:
            repo.problem("WARN", posix_rel(path, repo.root), "{} lines (max {}); move detail into docs".format(
                line_count(lines), MAX_AGENTS_LINES))

    check_overview(repo)
    if named is not None:
        rels = {doc.rel for doc in named}
        repo.problems = [p for p in repo.problems if p.rel in rels or rels.intersection(p.also)
                         or (p.rel.endswith(".md") and p.rel.startswith(attached))]
        return

    for path in broken_indexes(repo):
        repo.problem("ERROR", posix_rel(path, repo.root),
                     "index start marker with no end marker after it; fix the markers")
    index_hint = ("; stage the commit's files, run canon.py index --staged and commit with no paths"
                  if repo.staged else "")
    for path, text in expected_indexes(repo).items():
        current = repo.tree.read_text(path) if repo.tree.is_file(path) else None
        if current != text:
            repo.problem("ERROR" if strict or not repo.reads_work_tree else "WARN", posix_rel(path, repo.root),
                         "index out of date", fix=("index",), tree_hint=index_hint)
        elif current:
            check_links(repo, path, current.split("\n"), 0)

    for rel in old_copies(repo):
        repo.problem("WARN", rel, OLD_COPY_WARNING.format(rel))

    overview_kept = root_overview(repo) is not None
    for rel, commit in repo.deleted_docs(base):
        match = FILE_RE.match(rel.rsplit("/", 1)[-1])
        doc_id = match.group(1) + match.group(2) + match.group(3) if match else None
        if doc_id and doc_id not in repo.by_id and not (overview_kept and owned_architecture(repo, commit, rel)):
            repo.problem("ERROR", rel, "{} was deleted; restore it and archive it instead".format(doc_id))

    if base:
        at_fork, theirs = repo.tree_ids(base.fork), repo.tree_ids(base.commit)
        for doc in repo.docs:
            other = theirs.get(doc.id)
            if other and doc.id not in at_fork:
                repo.problem("ERROR", doc.rel, "{} was also added on {} as {}; run `canon.py renumber {} --base {}`"
                             .format(doc.id, base.ref, other, doc.rel, base.ref))


def apply_fixes(repo):
    done, index = [], False
    for problem in repo.problems:
        if not problem.fix:
            continue
        if problem.fix[0] == "index":
            index = True
            continue
        doc, key, value = problem.fix
        doc.text = set_field(doc.text, key, value)
        write_markdown(doc.path, doc.text)
        done.append("{}: {} {}".format(problem.rel, "set" if value is not None else "deleted", key))
    return done, index


def diagnostic_key(problem):
    return problem.level, problem.rel, problem.line, problem.msg


def base_diagnostics(repo, base):
    """Count the matches available on the named base without losing the selected tree's results."""
    if base and repo.problems:
        try:
            baseline = Repo(repo.root, rev=base.commit)
            run_check(baseline, strict=True)
            return collections.Counter(diagnostic_key(problem) for problem in baseline.problems)
        except (OSError, UnicodeError, SystemExit) as error:
            print("canon: cannot compare diagnostics with {}: {}".format(base.ref, error), file=sys.stderr)
    return collections.Counter()


def print_problems(repo, on_base):
    errors = warnings = 0
    for problem in sorted(repo.problems, key=lambda p: (p.rel, p.line or 0)):
        key = diagnostic_key(problem)
        marker = ""
        if on_base[key]:
            on_base[key] -= 1
            marker = " [also on base]"
        print("{} {}{}: {}{}".format(problem.level, problem.rel, ":" + str(problem.line) if problem.line else "",
                                     problem.msg + problem.tree_hint, marker))
        if problem.level == "ERROR":
            errors += 1
        else:
            warnings += 1
    return errors, warnings


# ---------------------------------------------------------------- moves

def apply_edits(lines, edits):
    """`lines`, changed in place, with the (start, end, value) spans that `edits` maps each line index to replaced."""
    for i, spans in edits.items():
        for start, end, value in sorted(spans, reverse=True):
            lines[i] = lines[i][:start] + value + lines[i][end:]
    return lines


def rewrite_for_moves(repo, moves, renamed=None, adopted=None, anchors=None, retitled=None, citations=False,
                      renumber_text=None, revised=None):
    """Rewrite relative links in every markdown file so they survive `moves` (old path -> new path).

    `renamed` maps a moved doc's old path, and the old path of an attachment directory that moves with it, to
    (old id, new id); in files other than docs, the citations of the old id in the texts of links to them become
    the new id. For numbered docs, `renumber_text(doc, anchors)` rewrites references against the same headings as
    the link pass, from the original document in every round.
    `adopted` maps a file becoming a canon doc to its id; link texts to it get the reference format.
    `anchors` maps a file's old path to {old anchor: new anchor} for the headings the command changed before this
    rewrite; links into the file, its own `#<anchor>` links included, and a reference's `§<anchor>` follow.
    `retitled` maps a doc's path to (old link text, new link text); the texts of links to it that read the old one
    become the new one.
    With `citations`, the `§<slug>` after each citation in a doc (`id_citations`) follows the anchors of what it
    names (`slug_follower`) instead.
    The anchors settle: links and citations follow the headings this rewrite changes too.
    """
    renamed, adopted, anchors, retitled = renamed or {}, adopted or {}, anchors or {}, retitled or {}
    owner, follow = doc_owner(repo, {}), slug_follower(repo)

    def mapped(p):
        for src, dst in moves.items():
            if p == src:
                return dst
            try:
                return dst / p.relative_to(src)
            except ValueError:
                continue
        return p

    marker_edits = SourceEmbeds(repo).move_editor(moves, adopted, mapped)

    def rewrite(path, lines, shifted):
        """The edits to `lines`, the text of the file at `path`, with `shifted` as the anchors."""
        new_path = mapped(path)
        new_dir = new_path.parent
        doc = repo.by_path.get(path)
        protected, edits = marker_edits(path, lines)
        for i, match in iter_links(lines):
            if i in protected:
                continue
            target = match.group(3)
            resolved = repo.resolve(path.parent, target)
            if resolved is None:
                continue
            dest, anchor = resolved
            is_self = dest == "self"
            dest = path if is_self else dest
            new_anchor = shifted.get(dest, {}).get(anchor, anchor) if anchor else anchor
            ids = None if doc else \
                renamed.get(dest) or next((renamed[p] for p in dest.parents if p in renamed), None)
            for cited in CITATION_RE.finditer(match.group(2)) if ids else ():
                if cited.group(1) == ids[0]:
                    start = match.start(2) + cited.start(1)
                    edits.setdefault(i, []).append((start, start + len(ids[0]), ids[1]))
            link_texts = retitled.get(dest)
            if link_texts and lines[i][match.start(2):match.end(2)] == link_texts[0]:
                edits.setdefault(i, []).append((match.start(2), match.end(2), link_texts[1]))
            ref = REF_TEXT_RE.match(match.group(2))
            if ref and anchor and ref.group(2) == anchor and new_anchor != anchor and not (citations and doc):
                start = match.start(2) + ref.start(2)
                edits.setdefault(i, []).append((start, start + len(anchor), new_anchor))
            if dest in adopted and not is_self and not ref and not match.group(1):
                label = adopted[dest] + ("§" + new_anchor if new_anchor else "") + ": " \
                    + (match.group(2) or adopted[dest])
                edits.setdefault(i, []).append((match.start(2), match.end(2), label))
            new_dest = mapped(dest)
            if is_self or (new_dest == dest and new_dir == path.parent):
                new_target = target if new_anchor == anchor else target.partition("#")[0] + "#" + new_anchor
            else:
                new_target = "/" + posix_rel(new_dest, repo.root) if target.startswith("/") \
                    else posix_rel(new_dest, new_dir)
                new_target = LINK_UNSAFE_RE.sub(lambda m: urllib.parse.quote(m.group(0), safe=""), new_target)
                if anchor:
                    new_target += "#" + new_anchor
            if new_target != target:
                edits.setdefault(i, []).append((match.start(3), match.end(3), new_target))
        for citation in id_citations(repo, doc, owner, "\n".join(lines)) if citations and doc and shifted else ():
            slug = follow(doc, citation, citation.id, shifted)
            if slug:
                edits.setdefault(citation.line, []).append((citation.slug.start, citation.slug.end, slug))
        return edits

    paths = {repo.root / rel for rel in repo.files if rel.endswith(".md")} | set(adopted)
    originals = {}
    for path in sorted(paths):
        if repo.tree.realpath(path) != path:
            continue
        try:
            originals[path] = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            sys.exit("canon: {} is not UTF-8".format(posix_rel(path, repo.root)))
    revised = revised or {}
    for path in revised.keys() - originals.keys():
        sys.exit("canon: cannot rewrite through an alias: " + posix_rel(path, repo.root))
    texts = {**originals, **revised}

    def step(shifted):
        rewritten = {}
        for path, text in texts.items():
            if renumber_text and path in repo.by_path:
                text = renumber_text(repo.by_path[path], shifted)
            lines = text.split("\n")
            rewritten[path] = "\n".join(apply_edits(lines, rewrite(path, lines, shifted)))
        settled = dict(anchors)
        for path, text in rewritten.items():
            changed = changed_anchors(texts[path], text)
            if changed:
                first = anchors.get(path, {})
                both = {a: changed.get(first.get(a, a), first.get(a, a))
                        for a in set(first) | (set(changed) - set(first.values()))}
                settled[path] = {a: b for a, b in both.items() if a != b}
        return rewritten, settled

    rewritten = settle(step, anchors, sum(len(body_headings(text)) for text in texts.values()) + 1)[0]
    for path, text in rewritten.items():
        if text != originals[path]:
            write_markdown(path, text, numbered=path in repo.by_path or path in adopted)


def move_paths(repo, moves):
    for src, dst in moves.items():
        dst.parent.mkdir(parents=True, exist_ok=True)
        if not (repo.is_git and git(repo.root, "mv", str(src), str(dst)) is not None):
            os.rename(str(src), str(dst))


def require_clean_merge(root, is_git=True):
    """End the command when the Git index of the checkout at `root` has unmerged entries; outside Git it has none."""
    if is_git and git_checked(root, "ls-files", "-u").stdout.strip():
        sys.exit("canon: resolve the merge conflicts first")


def used_numbers(repo, letter):
    return {int(FULL_ID_RE.match(i).group(2)) for i in repo.taken_ids() if i[0] == letter}


@contextlib.contextmanager
def file_lock(path, timeout, error):
    """Hold an exclusive lock on `path`, raising `error` once `timeout` seconds pass without it. The lock belongs to
    the process holding it, so the OS releases it however that process ends; nothing ever breaks it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(path), os.O_RDWR | os.O_CREAT)
    deadline, locked = time.time() + timeout, False
    try:
        while not locked:
            try:
                if fcntl:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                else:
                    msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                locked = True
            except (BlockingIOError, PermissionError):
                if time.time() > deadline:
                    raise error
                time.sleep(0.05)
        yield
    finally:
        if locked and not fcntl:
            msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
        os.close(fd)


def id_lock(repo):
    """Serialise id allocation between canon commands in this checkout."""
    path = repo.root / LOCAL_DIR / "id.lock"
    return file_lock(path, 60, SystemExit("canon: another canon command has held {} for a minute; let it finish"
                                          .format(posix_rel(path, repo.root))))


# ---------------------------------------------------------------- commands

def project_dir(repo, path):
    """The nearest directory from `path` up to the repo root that holds an AGENTS.md other than an installed skill
    file, else the last directory looked at."""
    def holds_project(path):
        agents = path / "AGENTS.md"
        return agents.is_file() and not repo.is_installed_skill(posix_rel(agents, repo.root))

    while not holds_project(path) and path != repo.root and path.parent != path:
        path = path.parent
    return path


def find_root(repo, root_arg):
    if root_arg:
        path = Path(os.path.realpath(root_arg))
        if path.name == "docs":
            path = path.parent
    else:
        path = project_dir(repo, Path(os.path.realpath(os.getcwd())))
    if not (path / "AGENTS.md").is_file():
        sys.exit("canon: no AGENTS.md at {}; set the project up with `canon.py init` first".format(path))
    rel = posix_rel(path, repo.root)
    rel = "" if rel == "." else rel
    for root in repo.roots:
        if root.rel == rel:
            return root
    return Root(repo, rel)


def check_repo(args):
    """The repository `check` reads, the work tree, the staged tree under `--staged` or commit REV's tree under
    `--rev`, once its flags and doc arguments pass: an error ends the command before any doc is read."""
    if args.staged and args.rev is not None:
        sys.exit("canon: --staged and --rev check different trees; give one of them")
    if args.fix and (args.staged or args.rev is not None):
        sys.exit("canon: --fix edits the work tree, which --staged and --rev do not check; drop one of them")
    if args.docs and (args.base is not None or args.staged or args.rev is not None):
        sys.exit("canon: check with doc arguments checks only those docs in the work tree; drop --base, --staged and "
                 "--rev")
    if not args.staged and args.rev is None:
        return Repo()
    top = git(os.getcwd(), "rev-parse", "--show-toplevel")
    if top is None:
        sys.exit("canon: --staged and --rev read Git; run check in a Git checkout")
    root = Path(os.path.realpath(top.strip()))
    if args.staged:
        require_clean_merge(root)
        return Repo(staged=True)
    commit = None if args.rev.startswith("-") else git(root, "rev-parse", "--verify", "-q", args.rev + "^{commit}")
    if commit is None:
        sys.exit(unknown_ref(args.rev))
    commit = commit.strip()
    shallow = root / git_checked(root, "rev-parse", "--git-path", "shallow").stdout.strip()
    if shallow.is_file() and commit in shallow.read_text().split():
        sys.exit("canon: {} is a shallow commit, whose parents this clone lacks; fetch them with "
                 "`git fetch --deepen=1`".format(args.rev))
    return Repo(rev=commit, tip=args.rev)


def cmd_check(repo, args):
    named = named_docs(repo, args.docs) if args.docs else None
    if args.fix and named is None:
        require_intact_indexes(repo)
    base = branch_base(repo, args.base) if args.base else None
    missing_refs = list(missing_commit_refs(repo, base)) if base else []
    run_check(repo, base, named)
    if args.fix:
        done, index = apply_fixes(repo)
        repo = Repo()
        if named is None and (index or done):
            done += ["wrote " + p for p in write_indexes(repo)]
            repo = Repo()
        for line in done:
            print("fixed " + line)
        named = named_docs(repo, args.docs) if args.docs else None
        run_check(repo, base, named)
    on_base = base_diagnostics(repo, base)
    for sha, design, path in missing_refs:
        repo.problem("ERROR", "commit " + sha, "missing {} in Refs: for {!r}".format(design, path))
    if args.version_notice:
        repo.problem("WARN", "AGENTS.md", args.version_notice)
    errors, warnings = print_problems(repo, on_base)
    fixable = sum(1 for p in repo.problems if p.fix)
    tail = "; {} fixable with --fix".format(fixable) if fixable and repo.reads_work_tree and not args.fix else ""
    print("canon check: {} docs, {} errors, {} warnings{}".format(len(repo.docs if named is None else named), errors,
                                                                  warnings, tail))
    return 1 if errors else 0


def parse_type(name):
    letter = ALIASES.get(name.lower())
    if not letter:
        sys.exit("canon: unknown type {}; use one of C D P R E I".format(name))
    return letter


def next_id(repo, letter):
    return letter + str(max(used_numbers(repo, letter) | {0}) + 1).zfill(3)


def default_fields(letter):
    fields = {"status": TYPES[letter]["active"][0], "created": today(), "updated": today(), "revision": 1,
              "modules": [], "summary": "", "refs": []}
    if letter == "D":
        fields.update(owns=[], paths=[])
    if letter == "P":
        fields["based_on"] = []
    return fields


def render_frontmatter(fields):
    return "---\n" + "\n".join("{}: {}".format(k, render_value(v)) for k, v in fields.items()) + "\n---\n"


def write_doc(root, letter, doc_id, slug, title, fields, implements="", template=None):
    path = root.docs / TYPES[letter]["dir"] / "{}-{}.md".format(doc_id, slug)
    body = (template or TEMPLATES[letter]).replace("{implements}", implements).replace("{id}", doc_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8") as f:
            f.write(render_frontmatter(fields) + "\n# {}: {}\n{}".format(doc_id, title, body))
    except FileExistsError:
        sys.exit("canon: {} already exists".format(path))
    return path


def cmd_new(repo, args):
    require_intact_indexes(repo)
    with id_lock(repo):
        return new_doc(Repo(), args)


def new_doc(repo, args):
    letter = parse_type(args.type)
    require_slug(args.slug)
    if args.research and letter != "E":
        sys.exit("canon: --research only applies to experiments")
    if args.design and letter != "P":
        sys.exit("canon: --from only applies to plans")
    if letter == "P" and not args.design:
        sys.exit("canon: a plan comes from an accepted or active design; pass its id with `--from`")
    if args.parent:
        if args.root:
            sys.exit("canon: --parent puts the sub-design beside its parent; drop --root")
        parent = repo.get(args.parent) if letter == "D" else None
        if parent is None or parent.type != "D" or parent.suffix:
            sys.exit("canon: --parent takes a top-level design and only applies to designs")
        taken = repo.taken_ids()
        letters = [c for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" if parent.id + c not in taken]
        if not letters:
            sys.exit("canon: {} has no free sub-design letter; create a new top-level design".format(parent.id))
        doc_id, root = parent.id + letters[0], parent.root
    else:
        root = find_root(repo, args.root)
        doc_id = next_id(repo, letter)
    title = args.title or args.slug.replace("-", " ").capitalize()
    fields = default_fields(letter)
    implements = ""
    if args.design:
        design = repo.get(args.design)
        if design.type != "D":
            sys.exit("canon: --from takes an accepted or active design; {} is not a design".format(design.id))
        if design.status not in ("accepted", "active"):
            sys.exit("canon: --from takes an accepted or active design; {} is {}".format(design.id, design.status))
        fields.update(modules=design.as_list("modules"), refs=[design.id],
                      based_on=["{}@r{}".format(design.id, design.revision)])
        plan_dir = root.docs / TYPES["P"]["dir"]
        implements = "\nImplements [{}: {}]({}).\n".format(design.id, design.title, posix_rel(design.path, plan_dir))
    template = TEMPLATES["E-research"] if args.research else None
    path = write_doc(root, letter, doc_id, args.slug, title, fields, implements, template=template)
    write_indexes(Repo())
    print(posix_rel(path, repo.root))
    return 0


def report_unmet_terminal(doc, status):
    """Print `ERROR <path>: <problem>` for each terminal condition of `status` that `doc` fails; whether any did."""
    problems = unfinished_problems(doc) + terminal_problems(doc, status)
    if problems:
        print("\n".join("ERROR {}: {}".format(doc.rel, p) for p in problems))
    return bool(problems)


def cmd_archive(repo, args):
    require_clean_merge(repo.root, repo.is_git)
    require_intact_indexes(repo)
    doc = repo.get(args.id)
    info = TYPES[doc.type]
    if doc.id == OVERVIEW_ID:
        sys.exit("canon: {} is the project overview every project keeps; revise it instead of archiving it"
                 .format(doc.id))
    if doc.archived:
        sys.exit("canon: {} is already archived".format(doc.id))
    if args.status not in info["terminal"]:
        sys.exit("canon: {} can be archived as {}".format(doc.id, " or ".join(info["terminal"])))
    if doc.type == "E" and args.status == "concluded":
        if doc.status != "concluded":
            sys.exit("canon: {} is {}, not concluded; archive an experiment nothing absorbed as dropped"
                     .format(doc.id, doc.status))
        citers = repo.citations().get(doc.path)
        if citers:
            sys.exit("canon: {} is linked by {}; it stays live while a live doc cites it"
                     .format(doc.id, ", ".join(d.id for d in citers)))
    live = [d.id for d in repo.docs if d.type == "D" and d.suffix and "D" + d.digits == doc.id and not d.archived]
    if live:
        sys.exit("canon: {} has live sub-designs {}; archive them first".format(doc.id, ", ".join(live)))
    if report_unmet_terminal(doc, args.status) or process_embeds(repo, [doc.id], check=True):
        return 1
    text = set_field(set_field(doc.text, "status", args.status), "updated", today())
    archive_dir = doc.root.docs / "archived" / info["dir"]
    moves = {doc.path: archive_dir / doc.path.name}
    attachment = doc.root.docs / info["dir"] / doc.id
    if attachment.is_dir():
        moves[attachment] = archive_dir / doc.id
    rewrite_for_moves(repo, moves, revised={doc.path: text})
    move_paths(repo, moves)
    write_indexes(Repo())
    print("{} -> {}".format(doc.rel, posix_rel(moves[doc.path], repo.root)))
    return 0


def status_moves(letter):
    """The statuses `status` moves a doc of type `letter` along, in order: the non-terminal ones, then a concept's live
    `adopted` or an experiment's live `concluded`."""
    return TYPES[letter]["active"] + ((LIVE_TERMINAL[letter],) if letter in LIVE_TERMINAL else ())


def cmd_status(repo, args):
    require_intact_indexes(repo)
    doc = repo.get(args.id)
    if doc.archived:
        sys.exit("canon: {} is archived".format(doc.id))
    info, moves = TYPES[doc.type], status_moves(doc.type)
    if args.status not in info["active"] + info["terminal"]:
        sys.exit("canon: {} is not a status of {}; use one of {}".format(args.status, doc.id, ", ".join(moves)))
    if args.status not in moves:
        sys.exit("canon: {} is terminal for {}; use `canon.py archive`".format(args.status, doc.id))
    later = moves[moves.index(doc.status) + 1:] if doc.status in moves else moves
    back = "running" if doc.type == "E" and doc.status == "answered" else None
    if args.status not in later and args.status != back:
        sys.exit("canon: {} is {}; status moves only forward{}{}".format(
            doc.id, doc.status, ", to " + ", ".join(later) if later else "", ", or back to " + back if back else ""))
    passed = later[:later.index(args.status) + 1] if args.status in later else []
    implemented = doc.get("implemented")
    citers = repo.citations().get(doc.path, []) if doc.type == "E" else []
    condition = None
    if {"accepted", "in-progress"} & set(passed) and not 1 <= doc.reviewed == doc.revision:
        condition = "`reviewed` equal to `revision`"
    elif args.status == "active" and not (isinstance(implemented, int) and 1 <= implemented <= doc.reviewed):
        condition = "`implemented` not above `reviewed`"
    elif doc.type == "E" and args.status == "concluded" and not any(d.type in ("D", "P") for d in citers):
        condition = "a live design or plan that links it"
    if condition:
        sys.exit("canon: {} needs {} to become {}".format(doc.id, condition, args.status))
    if args.status == back and citers:
        sys.exit("canon: {} is linked by {}; a later run gets a new experiment that links it"
                 .format(doc.id, ", ".join(d.id for d in citers)))
    if doc.type == "E" and args.status in ("answered", "concluded"):
        if report_unmet_terminal(doc, "concluded"):
            return 1
    text = set_field(set_field(doc.text, "status", args.status), "updated", today())
    doc.path.write_text(text, encoding="utf-8")
    write_indexes(Repo())
    print("{}: {} -> {}".format(doc.id, doc.status, args.status))
    return 0


def target_reference(text, separator):
    """Split a canonical design or plan ID and positive revision, or return None."""
    if not isinstance(text, str):
        return None
    doc_id, _, number = text.partition(separator)
    match = FULL_ID_RE.fullmatch(doc_id)
    if match and doc_id[0] in "DP" and well_formed_id(match) and re.fullmatch(r"[1-9][0-9]*", number):
        return doc_id, number
    return None


def approval_ref(text, separator, gate=None):
    """The canonical design or plan ID and positive revision in a gate key or target reference."""
    target = target_reference(text, separator)
    if not target:
        sys.exit("canon: invalid approval {} {}{}".format("gate" if separator == "-r" else "target", text,
                                                         " in " + gate if gate else ""))
    doc_id, number = target
    revision = int(number)
    if gate:
        primary, first_revision = approval_ref(gate, "-r")
        if doc_id[0] != primary[0] or (doc_id == primary and revision < first_revision):
            sys.exit("canon: {} does not belong to gate {}".format(text, gate))
    return doc_id, revision


def read_approval_record(path):
    def unique_keys(pairs):
        result = dict(pairs)
        if len(result) != len(pairs):
            raise ValueError("duplicate key")
        return result

    gate = path.parent.name
    try:
        targets = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_keys)
        if not isinstance(targets, dict) or (gate[0] == "P" and len(targets) > 1):
            raise ValueError("expected a mapping of gate targets")
        for doc_id, item in targets.items():
            if not (isinstance(item, dict) and set(item) == {"path", "revision"} and type(item["revision"]) is int):
                raise ValueError("invalid target " + doc_id)
            approval_ref("{}@r{}".format(doc_id, item["revision"]), "@r", gate)
            rel = item["path"]
            if not (isinstance(rel, str) and path_id(rel) == doc_id and not Path(rel).is_absolute()
                    and ".." not in Path(rel).parts and Path(rel).as_posix() == rel):
                raise ValueError("invalid document path for " + doc_id)
        return targets
    except FileNotFoundError:
        sys.exit("canon: no approval record for " + gate)
    except (OSError, ValueError) as error:
        sys.exit("canon: invalid approval record for {}: {}".format(gate, error))


def merge_approval_round(repo, gate, original, args):
    """Merge only the targets reviewed in this round, keeping other pending revisions and their file identities."""
    primary, first_revision = approval_ref(gate, "-r")
    targets = original.copy()
    moved = set()
    for ref in args.retire or ():
        doc_id, revision = approval_ref(ref, "@r")
        item = targets.get(doc_id)
        if not item or item["revision"] != revision:
            sys.exit("canon: {} is not recorded in {}".format(ref, gate))
        path = repo.root / item["path"]
        doc = repo.by_path.get(path)
        if doc is None:
            if os.path.lexists(str(path)):
                sys.exit("canon: {} still exists but cannot be read as a document; cannot retire {}".format(
                    item["path"], ref))
            moved.add(doc_id)
        elif not doc.archived and not (revision < doc.reviewed <= doc.revision and doc.as_list("reviewers")):
            sys.exit("canon: {} is still at {} without a later review; cannot retire it".format(ref, doc.rel))
        del targets[doc_id]
    supplied = {}
    for ref in args.start or args.update or args.recover or ():
        doc_id, revision = approval_ref(ref, "@r", gate)
        if doc_id in supplied and supplied[doc_id] != revision:
            sys.exit("canon: conflicting revisions for {} in {}".format(doc_id, gate))
        supplied[doc_id] = revision
        if doc_id in original and revision < original[doc_id]["revision"]:
            sys.exit("canon: {} would lower a recorded revision in {}".format(ref, gate))
        rel = targets[doc_id]["path"] if doc_id in targets else repo.get(doc_id).rel
        targets[doc_id] = {"revision": revision, "path": rel}
    if args.start is not None and supplied.get(primary) != first_revision:
        sys.exit("canon: start gate {} with its primary {}@r{}".format(gate, primary, first_revision))
    if primary[0] == "P":
        if args.update and not original:
            sys.exit("canon: verify the settled plan in the reviewed commits and use --recover for " + gate)
        if len(targets) > 1 or (args.update and supplied.keys() - original.keys() and not moved):
            sys.exit("canon: a plan gate takes only its own plan: " + gate)
    return targets


def pending_approvals(repo, gate, targets):
    """The saved revisions still awaiting consent, checked against the work tree before they can be offered."""
    pending = {}
    for doc in sorted((repo.get(doc_id) for doc_id in targets), key=Doc.sort_key):
        doc_id = doc.id
        item = targets[doc_id]
        revision = item["revision"]
        if doc.rel != item["path"]:
            sys.exit("canon: {} was reviewed at {}; reconcile {} with the reviewed commit".format(
                doc_id, item["path"], gate))
        approved = doc.get("approved")
        if approved is not None:
            if not (type(approved) is int and 1 <= approved <= doc.reviewed <= doc.revision):
                sys.exit("canon: invalid approved revision on " + doc_id)
            if approved >= revision:
                continue
        if doc.archived or not revision == doc.revision == doc.reviewed or not doc.as_list("reviewers"):
            sys.exit("canon: {}@r{} no longer matches a live, currently reviewed revision in {}".format(
                doc_id, revision, gate))
        pending[doc_id] = item
    return pending


def gate_approvals(repo, path, args, write=False):
    gate = path.parent.name
    approval_ref(gate, "-r")
    if args.start is not None or args.recover is not None:
        targets = {}
        if path.exists():
            if args.start is not None or gate[0] != "P" or len(args.recover) != 1 or read_approval_record(path):
                sys.exit("canon: approval record already exists for " + gate)
    else:
        targets = read_approval_record(path)
    if write:
        targets = merge_approval_round(repo, gate, targets, args)
    pending = pending_approvals(repo, gate, targets)
    if write:
        with tempfile.TemporaryDirectory(dir=path.parent) as tmp:
            staged = Path(tmp) / path.name
            staged.write_text(json.dumps(pending, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            staged.replace(path)
    if pending or args.gate:
        refs = ["{}@r{}".format(doc_id, item["revision"]) for doc_id, item in pending.items()]
        print("{}: {}".format(gate, " ".join(refs) or "none"))


def cmd_approvals(repo, args):
    repo.require_readable()
    directory = repo.root / LOCAL_DIR / "canon-design"
    writing = any(mode is not None for mode in (args.start, args.update, args.recover))
    if args.retire and args.update is None:
        sys.exit("canon: --retire requires --update")
    if args.gate:
        approval_ref(args.gate, "-r")
        path = directory / args.gate / "approvals.json"
        if writing:
            timeout = SystemExit("canon: another command is updating approval gate " + args.gate)
            try:
                with file_lock(path.with_suffix(".lock"), 60, timeout):
                    gate_approvals(Repo(repo.root), path, args, write=True)
            except OSError as error:
                sys.exit("canon: cannot update approval gate {}: {}".format(args.gate, error))
        else:
            gate_approvals(repo, path, args)
    elif writing:
        sys.exit("canon: name the approval gate to update")
    else:
        status = 0
        for path in sorted(directory.glob("*/approvals.json")):
            try:
                gate_approvals(repo, path, args)
            except SystemExit as error:
                print("{} ({})".format(error, path.parent.name), file=sys.stderr)
                status = 1
        return status
    return 0


def cmd_rename(repo, args):
    require_clean_merge(repo.root, repo.is_git)
    require_intact_indexes(repo)
    doc = repo.get(args.id)
    if doc.id == OVERVIEW_ID:
        sys.exit("canon: D000 keeps its file name, which the AGENTS.md block links")
    require_slug(args.slug)
    title = None if args.title is None else args.title.strip()
    if title is not None and (not title or re.search(r"[\r\n\[\]]", title)):
        sys.exit("canon: title must be one line of text without [ or ]")
    moves = {}
    if args.slug != doc.slug:
        moves[doc.path] = doc.path.with_name("{}-{}.md".format(doc.id, args.slug))
        attachment = doc.path.parent / doc.id
        for path in sorted(attachment.rglob("*")) if attachment.is_dir() else ():
            if path.is_file() and path.name.split(".", 1)[0] == doc.slug:
                moves[path] = path.with_name(args.slug + path.name[len(doc.slug):])
    for dest in moves.values():
        if os.path.lexists(str(dest)):
            sys.exit("canon: {} already exists".format(posix_rel(dest, repo.root)))
    anchors, retitled, revised = {}, {}, {}
    if title is not None:
        h1 = next((h for h in doc.headings if h.level == 1), None)
        if h1 is None:
            sys.exit("canon: {} has no H1".format(doc.id))
        lines = list(doc.lines)
        lines[h1.line] = "# {}: {}".format(doc.id, title)
        text = "\n".join(lines)
        anchors[doc.path] = changed_anchors(doc.text, text)
        if doc.title:
            retitled[doc.path] = ("{}: {}".format(doc.id, doc.title), "{}: {}".format(doc.id, title))
        revised[doc.path] = text
    rewrite_for_moves(repo, moves, anchors=anchors, retitled=retitled, citations=True, revised=revised)
    move_paths(repo, moves)
    write_indexes(Repo())
    print("{} -> {}".format(doc.rel, posix_rel(moves.get(doc.path, doc.path), repo.root)))
    for src, dest in moves.items():
        if src != doc.path:
            print("{} -> {}".format(posix_rel(src, repo.root), posix_rel(dest, repo.root)))
    return 0


def canon_block_span(text):
    """The span of the canon block in an `AGENTS.md` text, from its first start marker through the first end marker
    after it; None without a start marker. Exits when no end marker follows the start marker."""
    span = marker_span(text, AGENTS_START, AGENTS_END)
    if span and span[1] is None:
        sys.exit("canon: the repo root's AGENTS.md has a canon block start marker with no end marker after it; fix "
                 "the markers and rerun `init`")
    return span


def old_copies(repo):
    """The tracked files named canon.py that hold a `CANON_VERSION` line, copies kept from when projects held one,
    other than installed skill files and the `<dir>/scripts/canon.py` whose `<dir>/SKILL.md` names the `canon` skill."""
    found = []
    for rel in repo.tree.tracked("canon.py"):
        path = repo.root / rel
        if not repo.tree.is_file(path) or repo.is_installed_skill(rel):
            continue
        skill = path.parent.parent / "SKILL.md"
        if rel.split("/")[-2:-1] == ["scripts"] and repo.tree.is_file(skill):
            fields = parse_frontmatter(repo.tree.read_text(skill, errors="replace").split("\n"))[0]
            if fields and fields.get("name") == "canon":
                continue
        with contextlib.suppress(OSError):
            if re.search(rb'^CANON_VERSION = "\d+"', repo.tree.read_bytes(path), re.M):
                found.append(rel)
    return found


def cmd_init(repo, args):
    require_clean_merge(repo.root, repo.is_git)
    project = Path(os.path.realpath(args.root)) if args.root else repo.root
    if not project.is_dir() or (project != repo.root and repo.root not in project.parents):
        sys.exit("canon: --root {} is not a directory inside the repository".format(args.root))
    require_intact_indexes(repo, project)
    top = project == repo.root
    if args.version_notice and not top:
        print("canon: " + args.version_notice, file=sys.stderr)
    if top and not has_overview(repo):
        architecture_design(repo)  # refuses before any file changes
    root_agents = repo.root / "AGENTS.md"
    root_text = root_agents.read_text(encoding="utf-8") if root_agents.is_file() else ""
    span = canon_block_span(root_text)
    actions = []

    def note(verb, path):
        actions.append("{} {}".format(verb, posix_rel(path, repo.root)))

    for rel in old_copies(repo) if top else []:
        print("warning: " + OLD_COPY_WARNING.format(rel))

    attributes = repo.root / ".gitattributes"
    lines = attributes.read_text(encoding="utf-8").splitlines() if attributes.is_file() else []
    missing = [line for line in GITATTRIBUTES if line not in lines]
    if missing:
        attributes.write_text("\n".join(lines + missing) + "\n", encoding="utf-8")
        note("updated" if lines else "created", attributes)

    ignore = repo.root / ".gitignore"
    lines = ignore.read_text(encoding="utf-8").splitlines() if ignore.is_file() else []
    named = {line.strip().strip("/") for line in lines}
    missing = [entry for entry in (LOCAL_DIR, WORKTREES_DIR) if entry.strip("/") not in named]
    if missing:
        ignore.write_text("\n".join(lines + missing) + "\n", encoding="utf-8")
        note("updated" if lines else "created", ignore)

    agents = project / "AGENTS.md"
    block = AGENTS_BLOCK.format(install=INSTALL_DIR, version=CANON_VERSION)
    if not agents.is_file():
        agents.write_text("# AGENTS.md\n\n" + (block if top else SUB_AGENTS) + "\n", encoding="utf-8")
        note("created", agents)
    elif top:
        text = root_text
        if span:
            new = text[:span[0]] + block + text[span[1]:]
        else:
            new = text.rstrip("\n") + "\n\n" + block + "\n"
        if new != text:
            agents.write_text(new, encoding="utf-8")
            note("updated", agents)

    readme = project / "docs" / "README.md"
    if not readme.is_file():
        readme.parent.mkdir(parents=True, exist_ok=True)
        readme.write_text(DOCS_README, encoding="utf-8")
        note("created", readme)

    fresh = Repo()
    if top and not has_overview(fresh):
        source = architecture_design(fresh)
        if source:
            _id_map, moves, notes = move_doc(fresh, source, OVERVIEW_ID, slug=OVERVIEW_SLUG, title=OVERVIEW_TITLE)
            actions += ["moved {} -> {}".format(posix_rel(src, repo.root), posix_rel(dst, repo.root))
                        for src, dst in moves.items()] + notes
            path = moves[source.path]
            overview = Doc(source.root, path, posix_rel(path, repo.root), FILE_RE.match(path.name), False,
                           path.read_text(encoding="utf-8"))
            added = add_overview_sections(overview)
            shifted = heading_anchors(overview.text, path.read_text(encoding="utf-8"))
            if shifted:
                rewrite_for_moves(Repo(), {}, anchors={path: shifted})
            if added:
                actions.append("added {} to {}".format(", ".join(added), overview.rel))
        else:
            fields = default_fields("D")
            fields["owns"] = ["architecture"]
            note("created", write_doc(find_root(fresh, str(project)), "D", OVERVIEW_ID, OVERVIEW_SLUG,
                                      OVERVIEW_TITLE, fields, template=OVERVIEW_TEMPLATE))

    if (top or args.hook) and repo.is_git:
        found = git(repo.root, "rev-parse", "--git-path", "hooks/pre-commit")
        hook = repo.root / found.strip() if found else None
        old = current = False
        try:
            if hook is None:
                raise OSError("git rev-parse --git-path hooks/pre-commit failed")
            with contextlib.suppress(OSError):
                if hook.is_file():
                    data = hook.read_bytes()
                    old = top and OLD_HOOK_RE.fullmatch(data) is not None
                    current = data == PRE_COMMIT_HOOK.encode("utf-8")
            if old:
                hook.write_bytes(PRE_COMMIT_HOOK.encode("utf-8"))
                os.chmod(str(hook), 0o755)
                note("updated", hook)
            elif args.hook and os.path.lexists(str(hook)):
                if not current:
                    print("kept the existing pre-commit hook; add `canon.py check --staged` to it")
            elif args.hook:
                hook.parent.mkdir(parents=True, exist_ok=True)
                hook.write_bytes(PRE_COMMIT_HOOK.encode("utf-8"))
                os.chmod(str(hook), 0o755)
                note("created", hook)
        except OSError as error:
            if args.hook or old:
                print("warning: cannot write the pre-commit hook: {}; rerun `canon.py init --hook` where .git is "
                      "writable".format(error))

    actions += ["wrote " + rel for rel in write_indexes(Repo())]
    print("\n".join(actions) if actions else "canon init: nothing to do")
    return 0


def has_overview(repo):
    """Whether the repo root's docs/ holds a D000, archived or not; `init` then neither creates nor moves one."""
    return root_overview(repo, archived=True) is not None


def add_overview_sections(doc):
    """Append at the end of the design's `## Spec` each of D000's subsections it lacks, with its template guidance;
    return the headings added."""
    span = doc.section_span("Spec")
    if span is None:
        return []
    present = {doc.headings[i].text for i in doc.spec_subsections()}
    lines, end = list(doc.lines), span[1]
    while not lines[end - 1].strip():
        end -= 1
    added, block = [], []
    for name, body in OVERVIEW_SPEC:
        if name not in present:
            added.append("### " + name)
            block += ["", "### " + name, ""] + body.split("\n")
    lines[end:end] = block
    write_markdown(doc.path, "\n".join(lines))
    return added


def architecture_design(repo):
    """The non-archived design owning `architecture`, which `init` moves to D000; None when no design owns it.
    Exits when more than one does, or when it is a sub-design or a module's, which cannot become the repo root's D000.
    """
    owners = [d for d in repo.docs if d.type == "D" and not d.archived and "architecture" in d.as_list("owns")]
    named = " and ".join("{} ({})".format(d.id, d.rel) for d in owners)
    if len(owners) > 1:
        sys.exit("canon: {} all own `architecture`; take it out of the `owns` of all but one and rerun `init`"
                 .format(named))
    if owners and (owners[0].suffix or owners[0].root.rel):
        where = "a sub-design" if owners[0].suffix else "under the module docs root " + owners[0].root.docs_rel
        sys.exit("canon: {} owns `architecture` but is {}, so it cannot become the repo root's D000; take "
                 "`architecture` out of its `owns` and rerun `init`, which then creates a fresh D000 for its content "
                 "to fold into".format(named, where))
    return owners[0] if owners else None


def slugify(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "doc"


def require_slug(slug):
    if not SLUG_RE.match(slug):
        sys.exit("canon: slug `{}` must be kebab-case, such as `{}`".format(slug, slugify(slug)))


def cmd_adopt(repo, args):
    require_clean_merge(repo.root, repo.is_git)
    require_intact_indexes(repo)
    with id_lock(repo):
        return adopt_doc(Repo(), args)


def adopt_doc(repo, args):
    letter = parse_type(args.type)
    src = Path(os.path.realpath(args.file))
    if not os.path.lexists(args.file):
        sys.exit("canon: {} does not exist".format(args.file))
    if not src.is_file() or src.suffix != ".md":
        sys.exit("canon: {} is not a markdown file".format(args.file))
    if src in repo.by_path:
        sys.exit("canon: {} is already a canon doc".format(args.file))
    if args.root:
        root = find_root(repo, args.root)
    else:
        root = find_root(repo, str(project_dir(repo, src.parent)))
    slug = args.slug or slugify(src.stem)
    require_slug(slug)
    doc_id = next_id(repo, letter)
    dest = root.docs / TYPES[letter]["dir"] / "{}-{}.md".format(doc_id, slug)
    old = src.read_text(encoding="utf-8")
    rewrite_for_moves(repo, {src: dest}, adopted={src: doc_id},
                      anchors={src: heading_anchors(old, adopted_text(old, letter, doc_id, slug, args.title)[0])})
    text, dropped = adopted_text(src.read_text(encoding="utf-8"), letter, doc_id, slug, args.title)
    if dropped:
        print("dropped frontmatter fields: " + ", ".join(dropped))
    write_markdown(src, text)
    move_paths(repo, {src: dest})
    write_indexes(Repo())
    print("{} -> {}".format(posix_rel(src, repo.root), posix_rel(dest, repo.root)))
    return 0


def adopted_text(text, letter, doc_id, slug, title=None):
    """The text `adopt` gives a file becoming doc `doc_id`, and the frontmatter fields it drops: canon's frontmatter,
    the H1 read as `# <id>: <title>` and the type's missing sections."""
    lines = text.split("\n")
    fm, end, _bad = parse_frontmatter(lines)
    body = lines[end + 1:] if fm is not None else lines
    protected = marked_lines(embed_blocks(body, 0)[0])
    headings = [h for h in scan_headings(body) if h.line not in protected]
    h1 = next((h for h in headings if h.level == 1), None)
    title = title or (h1.text if h1 else slug.replace("-", " ").capitalize())
    if h1:
        body[h1.line] = "# {}: {}".format(doc_id, title)
    else:
        body = ["# {}: {}".format(doc_id, title), ""] + body
    names = {h.text for h in headings if h.level == 2}
    text = "\n".join(body).strip("\n") + "\n"
    for name in TYPES[letter]["sections"]:
        if name not in names:
            text += "\n## {}\n\n<!-- canon: Move the matching adopted content here. -->\n".format(name)
    return render_frontmatter(default_fields(letter)) + "\n" + text, list(fm or ())


def cmd_renumber(repo, args):
    require_clean_merge(repo.root, repo.is_git)
    require_intact_indexes(repo)
    with id_lock(repo):
        return renumber_doc(Repo(), args)


def renumber_doc(repo, args):
    if FULL_ID_RE.match(args.target):
        matches = [d for d in repo.docs if d.id == args.target]
        if not matches:
            sys.exit("canon: unknown document " + args.target)
        if len(matches) > 1:
            sys.exit("canon: {} is ambiguous; pass the file path of the doc to renumber".format(args.target))
        doc = matches[0]
    else:
        doc = repo.by_path.get(Path(os.path.realpath(args.target)))
        if doc is None:
            sys.exit("canon: {} is not a canon doc".format(args.target))
    if doc.id == OVERVIEW_ID and not doc.root.rel:
        sys.exit("canon: D000 is the project overview every project keeps; renumber only a D000 in a module's docs")
    repo.require_readable()
    if args.base:
        require_commit(repo, args.base)
    on_base = repo.tree_files(args.base) if args.base else None
    new_id = renumbered_id(repo, doc, args.new, on_base)
    id_map, moves, notes = move_doc(repo, doc, new_id, args.base, on_base, offer_base=True)
    write_indexes(Repo())
    notes.extend(moved_attachment_notes(repo, doc, moves))
    for old, new in id_map.items():
        print("{} -> {}".format(old, new))
    print("\n".join(notes + ["run `canon.py check --fix` to finish"]))
    return 0


def moved_attachment_notes(repo, doc, moves):
    """Locate literal old paths still present in the renumbered experiment, after Markdown links were rewritten."""
    old_dir = doc.path.parent / doc.id
    if doc.type != "E" or old_dir not in moves:
        return
    destination = moves[doc.path]
    text = destination.read_text(encoding="utf-8")
    if doc.id + "/" not in text:
        return
    new_dir = moves[old_dir]
    paths = {}
    for file in new_dir.rglob("*"):
        if file.is_file():
            old = old_dir / file.relative_to(new_dir)
            move = posix_rel(old, repo.root), posix_rel(file, repo.root)
            for base in (repo.root, doc.root.project, doc.root.docs, doc.path.parent):
                paths[posix_rel(old, base)] = move
    if not paths:
        return
    spellings = "|".join(re.escape(path) for path in sorted(paths, key=len, reverse=True))
    quoted = r"""(?P<quoted>"(?:\\.|[^"\\])*"|(?<!\w)'(?:\\.|[^'\\])*')"""
    pattern = re.compile(quoted + r"|(?P<bare>(?:\./)?(?:" + spellings + "))")
    # Check both ends of the whole token, including its quotes. A shell word may continue on either side of them.
    start = re.compile(r"""(?<![^\s`=(\[{,:<>|&;])""")
    end = re.compile(r"""(?=$|[\s`)\]}<>|&;]|[.,:!?](?=\s|$|['"]))""")
    lines = text.split("\n")
    first = parse_frontmatter(lines)[1] + 1
    rel = posix_rel(destination, repo.root)
    for index in range(first, len(lines)):
        seen = set()
        line = lines[index]
        for match in pattern.finditer(line):
            if not start.match(line, match.start()) or not end.match(line, match.end()):
                continue
            spelling = match.group("bare") or match.group("quoted")[1:-1]
            move = paths.get(spelling[2:] if spelling.startswith("./") else spelling)
            if move and move not in seen:
                old, new = move
                yield "{}:{}: moved attachment {} -> {}".format(rel, index + 1, old, new)
                seen.add(move)


def move_doc(repo, doc, new_id, base=None, on_base=None, slug=None, title=None, offer_base=False):
    """Give `doc` the id `new_id`, and its sub-designs that id with their letters: move their files and attachment
    directories, and rewrite the links, entries, dispositions and citations naming them. `slug` and `title` replace
    the doc's own. `base` is the branch merged or rebased onto, and `on_base` the files of its tree; `offer_base`
    suggests `--base` when it is missing, for a command that has one. Returns the id map, the moves and notes for the
    user."""
    links = {}

    def linked(src, path):
        if src.path not in links:
            links[src.path] = doc_links(repo, src)
        return path in links[src.path]

    embeds, embedded_files = SourceEmbeds(repo), {}

    def links_attachment(d, path):
        if d not in embedded_files:
            blocks = embed_blocks(d.lines, embeds.starts[d.path])[0] if d.path in embeds.starts else ()
            embedded_files[d] = {source for _block, source, _region, _walk in embeds.resolved_blocks(d.path, blocks)}
        return linked(d, path) or path in embedded_files[d]

    def side(ours, theirs, there, ours_linked, theirs_linked):
        """Whose a sub-design, attachment or reference is when `ours` shares its id with `theirs`: 'ours',
        'theirs', or None when nothing tells or the evidence conflicts. It belongs to the doc on its side of the
        base (`there`: it exists on the base, None when the base holds it only in part), when only one of them exists
        there, and to the doc links alone reach.
        """
        votes = set()
        if on_base is not None and all((t.rel in on_base) != (ours.rel in on_base) for t in theirs):
            if there is None:
                return None
            votes.add("ours" if there == (ours.rel in on_base) else "theirs")
        if ours_linked != theirs_linked:
            votes.add("ours" if ours_linked else "theirs")
        return votes.pop() if len(votes) == 1 else None

    group, unclear = [doc], []
    rivals = [d for d in repo.docs if d.id == doc.id and d is not doc and d.root is doc.root]
    for child in repo.docs:
        if doc.type != "D" or doc.suffix or child.type != "D" or not child.suffix or child.number != doc.number \
                or child.root is not doc.root:
            continue
        whose = side(doc, rivals, on_base is not None and child.rel in on_base,
                     linked(child, doc.path) or linked(doc, child.path),
                     any(linked(child, r.path) or linked(r, child.path) for r in rivals)) if rivals else "ours"
        if whose == "ours":
            group.append(child)
        elif whose is None:
            unclear.append(child.rel)
    if unclear:
        sys.exit("canon: cannot tell which {} owns {}; link each sub-design from its parent design{}, then rerun"
                 .format(doc.id, ", ".join(unclear), " or pass --base <ref>" if offer_base and not base else ""))
    if len({d.id for d in group}) < len(group):
        sys.exit("canon: sub-designs of {} share an id; renumber the one this branch added first".format(doc.id))

    renamed, moves, notes, keepers = {}, {}, [], {}
    for d in group:
        new = new_id if d is doc else new_id + d.suffix
        renamed[d.path] = (d.id, new)
        moves[d.path] = d.path.with_name("{}-{}.md".format(new, slug if d is doc and slug else d.slug))
        attachment = d.path.parent / d.id
        if not attachment.is_dir():
            continue
        others = [x for x in repo.docs if x.id == d.id and x is not d and x.path.parent == d.path.parent]
        owners = {side(d, others, on_base is not None and posix_rel(f, repo.root) in on_base, links_attachment(d, f),
                       any(links_attachment(x, f) for x in others)) for f in attachment.rglob("*") if f.is_file()} \
            if others else {"ours"}
        if owners <= {"ours"}:
            moves[attachment] = d.path.parent / new
            keepers[attachment] = d
            continue
        keepers[attachment] = others[0]
        if owners != {"theirs"}:
            notes.append("kept {}: it also holds attachments of another {}; move this doc's files to {} and fix "
                         "their links".format(posix_rel(attachment, repo.root), d.id,
                                              posix_rel(d.path.parent / new, repo.root)))

    id_map = dict(renamed.values())
    holder = {old: repo.by_path[path] for path, (old, _new) in renamed.items()}
    others = {old: [d for d in repo.docs if d.id == old and d.path not in renamed] for old in id_map}
    owner, follow = doc_owner(repo, keepers), slug_follower(repo, renamed)
    kept = {}

    def picker(d):
        """`pick(field, key, old id)` for the references `d` makes: the new id, or None to keep the old one."""
        counts = None

        def entry_counts():
            """How many times `d` names each entry (`id_entries`), now and on the base."""
            nonlocal counts
            if counts is None:
                before = collections.Counter()
                if on_base is not None and d.rel in on_base:
                    before = id_entries(repo, d, owner, git(repo.root, "show", "{}:{}".format(base, d.rel)) or "")
                counts = id_entries(repo, d, owner), before
            return counts

        def pick(field, key, old):
            if old not in id_map:
                return None
            if field == "cite" and old == d.id:
                return id_map[old] if d.path in renamed else None
            if not others[old]:
                return id_map[old]
            now, before = entry_counts()
            entry = (field, key, old)
            there = None if field == "cite" and 0 < before[entry] < now[entry] else before[entry] > 0
            whose = side(holder[old], others[old], there, linked(d, holder[old].path),
                         any(linked(d, x.path) for x in others[old]))
            if whose is None:
                kept.setdefault(old, set()).add(d.rel)
            return id_map[old] if whose == "ours" else None
        return pick

    def remap(d, pick, shifted):
        """`d`'s text with the references to moved ids rewritten as `pick` chooses, a link text's citation of the doc
        the link points at following that doc, and the `§<slug>` after a citation following the anchors `shifted` of
        what it names (`slug_follower`)."""
        edits = {}
        for cited in id_citations(repo, d, owner):
            if cited.field == "link":
                new = id_map[cited.id] if owner(cited.dest).path in renamed else None
            else:
                new = pick(cited.field, cited.key, cited.id)
            if new:
                edits.setdefault(cited.line, []).append((cited.start, cited.end, new))
            slug = follow(d, cited, new or cited.id, shifted)
            if slug:
                edits.setdefault(cited.line, []).append((cited.slug.start, cited.slug.end, slug))
        lines = apply_edits(list(d.lines), edits)
        if d.path in renamed:
            lines = rename_finding_ids(lines, d.fm_end, *renamed[d.path])
        if d is doc and title:
            h1 = next((h for h in d.headings if h.level == 1), None)
            if h1:
                lines[h1.line] = "# {}: {}".format(new_id, title)
        text = "\n".join(lines)
        for field in ("refs", "based_on"):
            values = d.get(field)
            if isinstance(values, list):
                mapped = []
                for value in values:
                    head, sep, tail = value.partition("@")
                    mapped.append((pick(field, value, head) or head) + sep + tail)
                if mapped != values:
                    text = set_field(text, field, mapped)
        return text

    picks = {d: picker(d) for d in repo.docs if "§" in d.text or any(old in d.text for old in id_map)}

    def renumber_text(d, shifted):
        return remap(d, picks[d], shifted) if d in picks else d.text

    renamed_paths = dict(renamed)
    renamed_paths.update((d.path.parent / d.id, renamed[d.path]) for d in group if d.path.parent / d.id in moves)
    rewrite_for_moves(repo, moves, renamed_paths, renumber_text=renumber_text)
    move_paths(repo, moves)
    notes = ["kept {} in {}: another doc still has that id; change the references there that mean {}"
             .format(old, ", ".join(sorted(rels)), id_map[old]) for old, rels in sorted(kept.items())] + notes
    return id_map, moves, notes


def renumbered_id(repo, doc, wanted, on_base):
    """`wanted`, once checked and normalized, or the next free id; a sub-design keeps its parent and takes a free
    letter. Ids in the base's files (`on_base`) and in the history of HEAD stay taken."""
    taken = repo.taken_ids() | {i for i in map(path_id, on_base or ()) if i}
    match = FULL_ID_RE.match(wanted or "")
    normalized = match.group(1) + str(int(match.group(2))).zfill(3) + match.group(3) if match else None
    if doc.suffix:
        parent = doc.type + doc.digits
        letters = [parent + c for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"]
        free = [i for i in letters if i not in taken]
        if wanted and normalized not in letters:
            sys.exit("canon: new id must be a sub-design of {}".format(parent))
        if wanted and normalized not in free:
            sys.exit("canon: {} is already used".format(wanted))
        if not free:
            sys.exit("canon: {} has no free sub-design letter".format(parent))
        return normalized or free[0]
    used = {int(FULL_ID_RE.match(i).group(2)) for i in taken if i[0] == doc.type}
    if not wanted:
        return doc.type + str(max(used) + 1).zfill(3)
    if not match or match.group(1) != doc.type or match.group(3):
        sys.exit("canon: new id must be a top-level {} id".format(doc.type))
    if int(match.group(2)) in used:
        sys.exit("canon: {} is already used".format(wanted))
    return normalized


def link_targets(repo, path, lines, start=0):
    """(match, path) for each link in `lines` of the file at `path` that points to a file; URLs and anchors within
    the file aside."""
    for _i, match in iter_links(lines, start):
        resolved = repo.resolve(path.parent, match.group(3))
        if resolved and resolved[0] != "self":
            yield match, resolved[0]


def doc_links(repo, doc):
    """Paths of the files a doc's body links to."""
    return {dest for _match, dest in link_targets(repo, doc.path, doc.lines, doc.fm_end + 1)}


def doc_owner(repo, keepers):
    """A function giving the doc whose file a path is or whose attachment directory holds it: for a directory several
    docs have, the doc `keepers` maps it to; None when no doc has the directory or `keepers` names none for it."""
    holders = {}
    for doc in repo.docs:
        holders.setdefault(doc.path.parent / doc.id, []).append(doc)

    def owner(path):
        if path in repo.by_path:
            return repo.by_path[path]
        directory = next((p for p in (path, *path.parents) if p in holders), None)
        if directory is None:
            return None
        return holders[directory][0] if len(holders[directory]) == 1 else keepers.get(directory)
    return owner


def slug_follower(repo, renamed=None):
    """A function giving the slug the `§<slug>` after a Citation in a doc becomes, or None when it keeps its own: the
    slug follows `anchors` ({path: {old anchor: new anchor}}) of what the citation names once `renamed` (old path ->
    (old id, new id)) has given docs their new ids, `cited_id` being the id it reads then: the linked file for a
    citation, in a link's text, of the doc the link points at; else the doc it is in for that doc's own id, or the
    one doc with the id."""
    renamed = renamed or {}
    ids = {d.path: renamed[d.path][1] if d.path in renamed else d.id for d in repo.docs}
    holders = collections.Counter(ids.values())
    sole = {i: path for path, i in ids.items() if holders[i] == 1}

    def follow(doc, cited, cited_id, anchors):
        if not cited.slug:
            return None
        path = cited.dest if cited.field == "link" else doc.path if cited_id == ids[doc.path] else sole.get(cited_id)
        return anchors.get(path, {}).get(cited.slug.text)
    return follow


def settle(step, anchors, rounds):
    """Apply `step`, which maps anchors ({path: {old anchor: new anchor}}) to (result, anchors after it), from
    `anchors` until they stop changing, at most `rounds` times; returns the last (result, anchors)."""
    for _ in range(rounds):
        result, settled = step(anchors)
        if settled == anchors:
            break
        anchors = settled
    return result, settled


Citation = collections.namedtuple("Citation", "line start end field key id slug dest")
Span = collections.namedtuple("Span", "start end text")


def id_citations(repo, doc, owner, text=None):
    """Each id cited in `summary` and, outside code, in the body of `doc`, or of `text` read as its text, as a
    Citation: `field` is `moved` or `fixed` for a review's disposition, keyed by its finding id; `link` for a citation,
    in a link's text, of the doc the link points at (`dest`), which `owner` gives; and `cite` for any other, keyed as
    written. `start` and `end` span the id, and `slug` is the Span of a `§<slug>` after it."""
    lines = doc.lines if text is None else text.split("\n")
    fm_end = doc.fm_end if text is None else parse_frontmatter(lines)[1]
    protected = marked_lines(embed_blocks(lines, fm_end + 1)[0]) if fm_end >= 0 else set()
    summary = [(i, lines[i]) for i in range(1, fm_end) if lines[i].startswith("summary:")]
    for i, line in summary + list(code_mask(lines, fm_end + 1)):
        if i in protected:
            continue
        masked = INLINE_CODE_RE.sub(lambda m: " " * len(m.group(0)), line)
        texts, skipped = [], []
        for match in LINK_RE.finditer(masked):
            resolved = repo.resolve(doc.path.parent, match.group(3))
            dest = None if resolved is None else doc.path if resolved[0] == "self" else resolved[0]
            texts.append((match.start(2), match.end(2), dest))
            skipped += [(match.start(), match.start(2)), (match.end(2), match.end())]
        disposition = DISPOSITION_ID_RE.match(masked) if doc.type == "R" else None
        if disposition:
            field = "moved" if disposition.group("moved") else "fixed"
            yield Citation(i, disposition.start(field), disposition.end(field), field, disposition.group("finding"),
                           disposition.group(field), None, None)
            skipped.append(disposition.span(field))
        for match in CITATION_RE.finditer(masked):
            if any(start <= match.start() < end for start, end in skipped):
                continue
            dest = next((d for start, end, d in texts if start <= match.start() < end), None)
            target = owner(dest) if dest else None
            yield Citation(i, match.start(1), match.end(1),
                           "link" if target is not None and target.id == match.group(1) else "cite",
                           match.group(1) + (match.group(2) or ""), match.group(1),
                           Span(*match.span(3), match.group(3)) if match.group(3) else None, dest)


def id_entries(repo, doc, owner, text=None):
    """How many times `doc`, or `text` read as its text, names each (field, key, id): its `refs` and `based_on`
    entries, keyed by the entry, and its citations other than links, as `id_citations` keys them."""
    fm = parse_frontmatter((doc.text if text is None else text).split("\n"))[0] or {}
    entries = collections.Counter((field, value, value.partition("@")[0]) for field in ("refs", "based_on")
                                  for value in (fm[field] if isinstance(fm.get(field), list) else []))
    entries.update((cited.field, cited.key, cited.id) for cited in id_citations(repo, doc, owner, text)
                   if cited.field != "link")
    return entries


def rename_finding_ids(lines, fm_end, old, new):
    """`lines` with doc `old`'s finding and known-issue ids (`<old>-F<n>`, `<old>-K<n>`) renamed to doc `new`'s in
    the code of the body after `fm_end`, its fenced blocks and inline code spans."""
    def rename(code):
        return CITATION_RE.sub(lambda m: new + m.group(0)[len(old):] if m.group(1) == old
                               and (m.group(2) or "").startswith("-") else m.group(0), code)

    prose = dict(code_mask(lines, fm_end + 1))
    protected = marked_lines(embed_blocks(lines, fm_end + 1)[0]) if fm_end >= 0 else set()
    for i in range(fm_end + 1, len(lines)):
        if i not in protected:
            lines[i] = INLINE_CODE_RE.sub(lambda m: rename(m.group(0)), lines[i]) if i in prose else rename(lines[i])
    return lines


def staged_index_repo(repo):
    """The staged tree whose indexes `index --staged` stages, once its refusals pass, from the work tree's `repo`: each
    ends the command before it changes any file or stages anything."""
    if not repo.is_git:
        sys.exit("canon: index --staged needs a Git checkout")
    require_clean_merge(repo.root, repo.is_git)
    staged = Repo(staged=True)
    broken = broken_indexes(staged)
    if broken:
        sys.exit("canon: the staged {} has an index start marker with no end marker after it; fix the markers, stage "
                 "the file and rerun".format(posix_rel(broken[0], staged.root)))
    return staged


def cmd_index(repo, args):
    staged = staged_index_repo(repo) if args.staged else None
    require_intact_indexes(repo)
    for rel in stage_indexes(staged) if staged else ():
        print("staged " + rel)
    for rel in write_indexes(repo):
        print("wrote " + rel)
    return 0


def cmd_show(repo, args):
    match = REF_ARG_RE.match(args.ref)
    if not match:
        sys.exit("canon: expected an id like D003 or D003#slug")
    doc = repo.get(match.group(1))
    anchor = match.group(2)
    if anchor:
        for idx, h in enumerate(doc.headings):
            if h.slug == anchor:
                end = next((x.line for x in doc.headings[idx + 1:] if x.level <= h.level), len(doc.lines))
                print("{}#{}".format(doc.rel, anchor))
                print("\n".join(doc.lines[h.line:end]).rstrip())
                return 0
        if doc.type == "D" and anchor == "known-issues":
            print("{} has no known issues".format(doc.id))
            return 0
        slugs = [h.slug for h in doc.headings if h.level >= 2]
        sys.exit("canon: {} has no section #{}{}".format(doc.id, anchor,
                                                          "; sections: " + ", ".join(slugs) if slugs else ""))
    print(doc.rel)
    for line in doc.lines[1:max(doc.fm_end, 1)]:
        print(line)
    print("# {}: {}".format(doc.id, doc.title))
    for h in doc.headings:
        if h.level >= 2:
            print("{}{}  #{}".format("  " * (h.level - 2), h.text, h.slug))
    return 0


def design_notes(doc):
    """Notes on a design that whoever works from it needs first: a spec that leads the code, known issues."""
    if doc.type != "D":
        return ""
    notes, implemented, label = "", doc.get("implemented"), issue_label(doc)
    if isinstance(implemented, int) and implemented < doc.revision:
        notes += " [spec r{} leads code r{}]".format(doc.revision, implemented)
    if label:
        notes += " [{}]".format(label)
    return notes


def doc_line(doc):
    return "{} {} {} - {}{}".format(doc.id, doc.status, doc.rel, doc.get("summary", ""), design_notes(doc))


def find_match(doc, words):
    """Whether `doc` matches the lowercased `words`, and its matching headings unless its metadata holds them all."""
    meta = " ".join([doc.id, doc.title, str(doc.get("summary", ""))] + doc.as_list("owns")
                    + doc.as_list("modules")).lower()
    if all(w in meta for w in words):
        return True, []
    hits = [h for h in doc.headings if h.level >= 2 and all(w in meta + " " + h.text.lower() for w in words)]
    return bool(hits), hits


def cmd_find(repo, args):
    words = [w.lower() for w in args.words]
    found = 0
    for doc in repo.docs:
        if doc.archived and not args.archived:
            continue
        matched, hits = find_match(doc, words)
        if matched:
            found += 1
            print(doc_line(doc))
            for h in hits:
                print("  {}#{} {}".format(doc.id, h.slug, h.text))
    if found:
        return 0
    archived = 0 if args.archived else sum(1 for d in repo.docs if d.archived and find_match(d, words)[0])
    if archived == 1:
        print("no match; 1 archived doc matches with `--archived`")
    elif archived:
        print("no match; {} archived docs match with `--archived`".format(archived))
    else:
        print("no match")
    return 0


def is_missing(repo, path, rel):
    """Whether nothing exists at `path`, repo-relative `rel`, and neither HEAD's tree nor the Git index holds it or a
    file below it."""
    if path.exists():
        return False
    if not repo.is_git:
        return True
    listings = [["ls-files", "-z", "--cached"]] + ([["ls-tree", "-r", "-z", "--name-only", "HEAD"]]
                                                  if repo.has_head else [])
    return not any(git(repo.root, "--literal-pathspecs", *listing, "--", rel) for listing in listings)


def cmd_which(repo, args):
    for name in args.files:
        path = Path(os.path.realpath(name))
        hits = repo.designs_for(path)
        rel = posix_rel(path, repo.root)
        label = rel + " (missing)" if is_missing(repo, path, rel) else rel
        if not hits:
            kind = "skill" if repo.is_installed_skill(rel) else "doc" if repo.is_doc(rel) else "no design"
            print("{}: {}".format(label, kind))
        for doc in hits:
            print("{}: {} {} - {}{}".format(label, doc.id, doc.rel, doc.get("summary", ""), design_notes(doc)))
    return 0


def cmd_affected(repo, args):
    files = [posix_rel(Path(os.path.realpath(f)), repo.root) for f in args.files] or repo.changed_files(args.base)
    designs = {}
    for rel in files:
        for doc in repo.designs_for(repo.root / rel):
            designs.setdefault(doc.id, (doc, []))[1].append(rel)
    if not designs:
        print("no design governs the changed files")
        return 0
    for doc, rels in designs.values():
        print(doc_line(doc))
        for rel in rels:
            print("  " + rel)
    for doc in repo.docs:
        if doc.type == "P" and not doc.archived and plan_designs(doc) & set(designs):
            print("plan " + doc_line(doc))
    return 0


def trailer_ids(message, key):
    """The doc ids named in the lines of a commit message that start with `<key>:`, in any case."""
    named = set()
    for line in message.splitlines():
        if line.lower().startswith(key + ":"):
            named |= set(re.findall(r"\b[CDPREI]\d{3,}[A-Z]?\b", line))
    return named


@contextlib.contextmanager
def historical_repo(root, commit):
    """Close this tree's batch reader before opening the next commit in a long range."""
    view = Repo(root, rev=commit)
    try:
        yield view
    finally:
        batch = view.tree.batch
        if batch is not None and batch.poll() is None:
            batch.communicate()


def required_refs(view, changes, parent):
    """One witness path per design, from the tree that records that path."""
    owners = {}

    def collect(tree, paths):
        for path in paths:
            for doc in tree.designs_for(tree.root / path):
                owners.setdefault(doc.id, (doc, path))

    collect(view, (path for path in changes if changes[path] != "D"))
    deleted = [path for path in changes if changes[path] == "D"]
    if deleted:
        with historical_repo(view.root, parent) as previous:
            collect(previous, deleted)
    return sorted(owners.values(), key=lambda item: item[0].sort_key())


def cmd_commit_template(args):
    if args.subject and args.subject.splitlines() != [args.subject]:
        sys.exit("canon: --subject must be one line")
    top = git(os.getcwd(), "rev-parse", "--show-toplevel")
    if top is None:
        sys.exit("canon: commit-template needs a Git checkout")
    root = Path(top.strip())
    require_clean_merge(root)
    staged = Repo(root, staged=True)
    owners = required_refs(staged, staged.staged_changes, staged.compared)
    print(args.subject)
    if owners:
        print("\nRefs: " + ", ".join(doc.id for doc, _ in owners))
    return 0


def require_range_history(root, base, commits):
    """A missing parent at the base can hide an apparent new commit. Prove all
    new commits descend from that boundary by testing the roots of the range."""
    shallow = root / git_checked(root, "rev-parse", "--git-path", "shallow").stdout.strip()
    if not shallow.is_file():
        return
    frontier = [sha for sha, parents in commits.items() if not any(p in commits for p in parents)]

    def ancestor(older, newer):
        return git_checked(root, "merge-base", "--is-ancestor", older, newer, ok=(0, 1)).returncode == 0

    for boundary in shallow.read_text().splitlines():
        if boundary in commits or (ancestor(boundary, base) and not all(ancestor(boundary, c) for c in frontier)):
            sys.exit("canon: shallow history cannot establish the commit range at {}; fetch the full history "
                     "with `git fetch --unshallow`".format(boundary))


def missing_commit_refs(repo, base):
    tip = repo.rev or require_commit(repo, "HEAD")
    history = git_checked(repo.root, "log", "-z", "--no-notes", "--no-show-signature", "--encoding=UTF-8",
                          "--format=%H%x00%P%x00%B", base.commit + ".." + tip, "--").stdout
    if not history:
        return
    fields = history.split("\0")
    records = [fields[i:i + 3] for i in range(0, len(fields) - 1, 3)]
    parents = {sha: lineage.split() for sha, lineage, _ in records}
    require_range_history(repo.root, base.commit, parents)
    for sha, _, message in records:
        lineage = parents[sha]
        if len(lineage) > 1:
            continue
        paths = changed_path_status(repo.root, "diff-tree", "--root", "-r", "--no-commit-id", sha)
        if not paths:
            continue
        cited = trailer_ids(message, "refs")
        with historical_repo(repo.root, sha) as view:
            for doc, path in required_refs(view, paths, lineage[0] if lineage else None):
                if doc.id not in cited:
                    yield sha, doc.id, path


def unchecked_commits(repo, doc):
    """The commit a design's count runs from, its newest reconciliation or else its last change beyond its Known
    issues table, and the commits since its last change and every reconciliation after it that touch files its
    `paths` govern and whose `Refs:` trailers do not name it. A merge touches the files its resolution changed against
    every parent, or for a clean merge, which changed none, the files it changed against any parent."""
    last = None
    for sha in git_checked(repo.root, "log", "--format=%H", "--", doc.rel).stdout.split():
        old = git(repo.root, "show", "{}^:{}".format(sha, doc.rel))
        new = git(repo.root, "show", "{}:{}".format(sha, doc.rel))
        if old is None or new is None or not issue_rows_only(old, new):
            last = sha
            break
    if not last:
        return None, []
    specs = [s for s in (git_pathspec(doc.root.rel, p) for p in doc.as_list("paths")) if s]
    if not specs:
        return last, []
    out = git_checked(repo.root, "log", "-z", "--format=%x01%H%x00%B%x02", last + "..HEAD").stdout
    reconciled = [header.partition("\0")[0] for header, _files in log_entries(out)
                  if doc.id in trailer_ids(header.partition("\0")[2], "reconciled")]
    out = git_checked(repo.root, "log", "-z", "-c", "--name-only", "--no-renames", "--full-history",
                      "--format=%x01%H %P%x00%B%x02", "HEAD", "--not", last, *reconciled, "--", *specs).stdout
    commits = []
    for header, files in log_entries(out):
        shas, _, message = header.partition("\0")
        sha, _, parents = shas.partition(" ")
        if not files and len(parents.split()) > 1:
            merged = git_checked(repo.root, "diff-tree", "-z", "-r", "-m", "--no-commit-id", "--name-only",
                                 "--no-renames", sha, "--", *specs).stdout
            files = [f for f in merged.split("\0") if f]
        if files and not any(doc.governs(f, not repo.is_code(f)) for f in files):
            continue
        if sha and doc.id not in trailer_ids(message, "refs"):
            commits.append(sha)
    return (reconciled[0] if reconciled else last), commits


def log_entries(out):
    """(header, files) for each commit `git log -z --name-only` lists with a format of `%x01<header>%x02`."""
    for entry in out.split("\x01")[1:]:
        header, _, names = entry.partition("\x02")
        yield header, [f for f in names.lstrip("\0").lstrip("\n").split("\0") if f]


def root_overview(repo, archived=False):
    """The D000 in the repo root's docs/, outside archived/ unless `archived`; None without one."""
    return next((d for d in repo.docs if d.id == OVERVIEW_ID and not d.root.rel and (archived or not d.archived)),
                None)


def module_dir(repo, overview, entry):
    """The directory an entry of a Path cell of D000's Modules table names, read with or without its trailing `/`,
    relative to the project directory with "" for `./`; None when it is no existing directory of the project in the
    tree read, which then holds no file."""
    project = str(overview.root.project)
    target = os.path.normpath(os.path.join(project, entry))
    if not ((target == project or target.startswith(project + os.sep)) and repo.tree.is_dir(Path(target))):
        return None
    rel = posix_rel(target, project)
    return "" if rel == "." else rel


def coverage_report(repo, overview):
    """`audit`'s source areas: the tracked files under D000's module Paths, docs and installed skill files aside, that
    no design's `paths` match, grouped by directory within their module and ranked by the commits of the last 90
    days."""
    modules = sorted({module_dir(repo, overview, entry) for entry in overview.module_entries()} - {None}, key=len,
                     reverse=True)
    designs = [doc for doc in repo.docs if doc.type == "D" and not doc.archived and doc.as_list("paths")]
    uncovered, covered_dirs, files_directly_in = {}, set(), {}
    tracked = git_checked(repo.root, "ls-files", "-z").stdout if modules else ""
    for rel in tracked.split("\0"):
        module = next((m for m in modules if not m or rel.startswith(m + "/")), None) if rel else None
        if module is None or not repo.is_code(rel):
            continue
        folder = posixpath.dirname(rel)
        files_directly_in[folder] = files_directly_in.get(folder, 0) + 1
        if any(doc.governs(rel) for doc in designs):
            while (module, folder) not in covered_dirs:
                covered_dirs.add((module, folder))
                if folder == module:
                    break
                folder = posixpath.dirname(folder)
        else:
            uncovered[rel] = module
    areas, area_of = {}, {}
    for rel, module in uncovered.items():
        area = posixpath.dirname(rel)
        while area != module and (module, posixpath.dirname(area)) not in covered_dirs:
            area = posixpath.dirname(area)
        area_of[rel] = area
        areas.setdefault(area, (module, []))[1].append(rel)
    commits = dict.fromkeys(areas, 0)
    if areas and repo.has_head:
        out = git_checked(repo.root, "log", "-z", "--since=90.days.ago", "--format=%x01%x02", "--name-only",
                          "--no-renames", "HEAD").stdout
        for _header, files in log_entries(out):
            for area in {area_of[f] for f in files if f in area_of}:
                commits[area] += 1

    def label(area):
        return area + "/" if area else "./"

    ranked = sorted(areas, key=lambda a: (-commits[a], -len(areas[a][1]), label(a)))
    if not ranked:
        return []
    width = len(str(max(commits[a] for a in ranked[:MAX_AREAS])))
    report = ["Source areas no design covers (commits in the last 90 days, most first):"]
    for area in ranked[:MAX_AREAS]:
        module, files = areas[area]
        size = "{} files".format(len(files)) if (module, area) not in covered_dirs \
            else "{} of {} files".format(len(files), files_directly_in[area])
        report.append("  {:>{}} commits  {}  {}".format(commits[area], width, label(area), size))
    if len(ranked) > MAX_AREAS:
        report.append("  and {} more areas".format(len(ranked) - MAX_AREAS))
    return report


def unreached_designs(repo, overview):
    """The non-archived designs D000 does not reach: it reaches itself and every design named in the `refs` of a
    design it reaches."""
    reached, todo = set(), [overview]
    while todo:
        doc = todo.pop()
        if doc.id not in reached:
            reached.add(doc.id)
            todo += [repo.by_id[r] for r in doc.as_list("refs") if r in repo.by_id and repo.by_id[r].type == "D"]
    return [d for d in repo.docs if d.type == "D" and not d.archived and d.id not in reached]


def cmd_audit(repo, args):
    repo.require_readable()
    now = datetime.date.today()
    report = []
    stale = []
    for doc in repo.docs:
        if doc.type == "D" and not doc.archived and doc.as_list("paths") and repo.has_head:
            base, commits = unchecked_commits(repo, doc)
            if commits:
                stale.append((len(commits), base, doc))
    if stale:
        report.append("Designs with code commits since the design last changed or was reconciled that no `Refs:` "
                      "trailer names (most first; review `git log <since>..HEAD` on its paths):")
        for count, base, doc in sorted(stale, key=lambda x: -x[0]):
            report.append("  {} commits since {}  {}".format(count, base[:12], doc_line(doc)))
    issues = []
    for doc in repo.docs:
        if doc.type == "D" and not doc.archived:
            for kid, severity, issue, _source, since, next_step in known_issues(doc)[0]:
                key = (parse_date(since) or datetime.date.max, doc.sort_key(), int(kid.rsplit("K", 1)[1]))
                issues.append((key, kid, severity, issue, next_step))
    if issues:
        report.append("Known issues, oldest first (`show <design>#known-issues` has their sources):")
        for key, kid, severity, issue, next_step in sorted(issues):
            age = "?" if key[0] == datetime.date.max else (now - key[0]).days
            report.append("  {} {}, {} days, next {}: {}".format(kid, severity, age, next_step, issue))
    idle = []
    for doc in repo.docs:
        updated = parse_date(doc.get("updated"))
        exempt = doc.type == "C" or (doc.type, doc.status) in (("D", "active"), ("E", "concluded"))
        in_work = not doc.archived and not exempt
        if in_work and updated and (now - updated).days > args.days:
            idle.append(doc)
    if idle:
        report.append("Open docs untouched for over {} days:".format(args.days))
        report += ["  " + doc_line(d) for d in idle]
    for root in repo.roots:
        reviews = [parse_date(d.get("created")) for d in repo.docs if d.root is root and d.type == "R"]
        last = max([r for r in reviews if r] or [datetime.date.min])
        done = [d for d in repo.docs if d.root is root and d.type == "P" and d.status == "done"
                and (parse_date(d.get("updated")) or datetime.date.min) > last]
        commits = 0
        if repo.has_head:
            since = [] if last == datetime.date.min else ["--since=" + (last + datetime.timedelta(days=1)).isoformat()]
            out = git_checked(repo.root, "log", *since, "--format=%H", "--", *code_pathspec(repo, root)).stdout
            commits = len(set(out.split()))
        if len(done) >= args.review_after or commits >= args.review_commits:
            report.append("{}: {} plans finished and {} code commits since the last review; consider a review (R)"
                          .format(root.label, len(done), commits))
    overview = root_overview(repo)
    if overview and repo.is_git:
        report += coverage_report(repo, overview)
    unreached = unreached_designs(repo, overview) if overview else []
    if unreached:
        report.append("Designs D000 does not reach (link each from D000's rows or from a design D000 reaches):")
        report += ["  " + doc_line(d) for d in unreached]
    print("\n".join(report) if report else "canon audit: nothing to report")
    return 0


# ---------------------------------------------------------------- trace

TRACE_DIR = LOCAL_DIR + "canon/trace"
REVIEW_SNAPSHOT_DIR = LOCAL_DIR + "canon/snapshots"
REVIEW_ROUND_DIR = LOCAL_DIR + "canon-blind-review"
REVIEW_SNAPSHOT_DAYS = 30
TRACE_KINDS = ("design", "plan", "implement", "investigate", "canon-review", "retro", "code-review", "gate",
               "follow-up", "slice", "end-check")
TOP_LEVEL_KINDS = TRACE_KINDS[:6]
OUTCOMES = ("delivered", "blocked", "handoff", "cancelled")
KIND_OUTCOMES = {"implement": OUTCOMES + ("partial", "escalated"), "end-check": ("quiet", "raised")}
GATE_ROLES = ("same-model", "cross-family")
REVIEW_ROLES = {"gate": GATE_ROLES, "follow-up": GATE_ROLES, "code-review": ("spec", "standards", "cross-family")}
REVIEW_DISPOSITIONS = ("accepted", "declined", "escalated", "deferred")
CONFIRMATION_RESULTS = ("resolved", "not-resolved")
FINDING_ID_RE = re.compile(r"F[1-9][0-9]*")
UNIT_RE = re.compile(r"^\d{8}T\d{6}Z-[0-9a-f]{6}$")
UNIT_TIME_FORMAT = "%Y%m%dT%H%M%SZ"
SLICE_RE = re.compile(r"^S\d+$")
TRACE_LOCK_WAIT = 5
MAX_EVENT = 16 * 1024
MAX_CHANGES = 10 * 1024 * 1024
MAX_SNAPSHOT_ERROR = 64 * 1024
MAX_ARCHIVE = 2 * 1024 * 1024
MAX_REVIEWER_FIELD = 200
REPO_ENV = ("GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY",
            "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_NAMESPACE")
SNAPSHOT_IDENTITY = {"GIT_AUTHOR_NAME": "canon-trace", "GIT_AUTHOR_EMAIL": "trace@canon.invalid",
                     "GIT_COMMITTER_NAME": "canon-trace", "GIT_COMMITTER_EMAIL": "trace@canon.invalid"}
TRACE_NOTICE = ("Tracing keeps, in each checkout's {}/, an event line at each canon unit boundary and a snapshot of the "
                "work tree at each unit start, untracked files that are not ignored included. No commit or push reaches "
                "that directory, but packaging that does not read .gitignore, such as a Docker build context, must "
                "exclude .canon/.").format(TRACE_DIR)


class TraceError(Exception):
    """Invalid input or an events file that cannot be written; `trace` prints it and exits 0."""


class SnapshotSkip(Exception):
    """A snapshot that was not recorded: `reason` goes in the start line's `skipped`, Git's `message` in the unit's
    snapshot-error.txt."""

    def __init__(self, reason, message=b""):
        super().__init__(reason)
        self.reason, self.message = reason, message


def trace_root():
    """The checkout holding the working directory, found without running Git: the nearest directory holding `.git`,
    else `AGENTS.md`, else the working directory; and whether it holds `.git`."""
    cwd = Path(os.getcwd())
    for marker in (".git", "AGENTS.md"):
        for path in (cwd, *cwd.parents):
            if (path / marker).exists():
                return path, marker == ".git"
    return cwd, False


def named_git_dir(top):
    """The Git directory that the gitdir: line of the .git file of the checkout at `top` names, a relative path
    resolved from `top`, with symbolic links resolved; None when `top`'s .git is no such file."""
    try:
        with open(str(top / ".git"), "rb") as git_file:
            line = git_file.readline()
    except OSError:
        return None
    if not line.startswith(b"gitdir: "):
        return None
    return Path(os.path.realpath(os.path.join(str(top), os.fsdecode(line[len(b"gitdir: "):].rstrip(b"\r\n")))))


def common_git_dir(top):
    """The common Git directory of the checkout at `top`, read without running Git: top/.git when that is a directory,
    else the directory its .git file names, or for a linked worktree, whose named directory lies directly inside one
    named worktrees, the directory two levels above it; None when top/.git is neither."""
    if (top / ".git").is_dir():
        return top / ".git"
    git_dir = named_git_dir(top)
    return git_dir.parent.parent if git_dir is not None and git_dir.parent.name == "worktrees" else git_dir


def worktree_main(root):
    """The checkout whose trace directory the checkout at `root` shares as a worktree in .worktrees/, read without
    running Git: the nearest <R> with `root` under <R>/.worktrees/ whose common Git directory's worktrees directory
    directly holds the directory `root`'s .git file names, one of <R>'s linked worktrees; else None."""
    git_dir = named_git_dir(root)
    if git_dir is None:
        return None
    for path in root.parents:
        common = common_git_dir(path.parent) if path.name == ".worktrees" else None
        if common is not None and str(git_dir.parent) == os.path.realpath(str(common / "worktrees")):
            return path.parent
    return None


def can_create_file(directory):
    """Whether a file can be created in `directory`, created first when missing: a uniquely named file is created
    there and deleted."""
    probe = directory / ".write-test-{}-{}".format(os.getpid(), os.urandom(4).hex())
    try:
        directory.mkdir(parents=True, exist_ok=True)
        os.close(os.open(str(probe), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600))
    except OSError:
        return False
    with contextlib.suppress(OSError):
        probe.unlink()
    return True


def main_trace_root(root):
    """The main checkout this worktree shares, or the checkout itself, found without Git or writes."""
    main, shared = root, worktree_main(root)
    while shared:
        main, shared = shared, worktree_main(shared)
    return main


def trace_holder(root):
    """The checkout whose trace directory accepts writes, falling back to the worktree's own (D001#switch-and-storage)."""
    main = main_trace_root(root)
    if main != root and trace_state(main, root)[0] and not can_create_file(main / TRACE_DIR):
        return root
    return main


def history_stores(root):
    """Eligible event logs and their archives, independent of the trace switch and current write access."""
    main = main_trace_root(root)
    if main == root:
        return [(None, root / TRACE_DIR)]
    return [("main", main / TRACE_DIR), ("worktree", root / TRACE_DIR)]


def trace_switch_path():
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "canon" / "trace"


def trace_state(holder, root):
    """Whether tracing is on in the checkout at `root`, whose calls use the trace directory of the checkout `holder`,
    and the status line that says why."""
    switch, off = trace_switch_path(), holder / TRACE_DIR / "off"
    shown = TRACE_DIR + "/off" if holder == root else str(off)
    if not switch.exists():
        return False, "trace off: no machine switch {}; `canon.py trace on` creates it".format(switch)
    if off.exists():
        return False, "trace off: this checkout opted out with {}; `canon.py trace on --here` deletes it".format(shown)
    return True, "trace on: the machine switch {} exists and this checkout has no {}".format(switch, shown)


def trace_doc_paths(root, is_git, names):
    """The file of each doc id that finds one: the doc in docs/ or docs/archived/ at `root`, else in any docs/
    directory Git lists."""
    paths, missing = {}, []
    for name in dict.fromkeys(names):
        category = TYPES[name[0]]["dir"]
        found = sorted(root.glob("docs/{}/{}-*.md".format(category, name))) \
            or sorted(root.glob("docs/archived/{}/{}-*.md".format(category, name)))
        if found:
            paths[name] = found[0]
        else:
            missing.append(name)
    if missing and is_git:
        try:
            out = trace_git(root, trace_env(), "ls-files", "-z", "-co", "--exclude-standard", "--",
                            *(":(glob)**/docs/**/{}-*.md".format(name) for name in missing))
        except SnapshotSkip:
            out = b""
        for rel in sorted(os.fsdecode(out).split("\0")):
            doc_id = path_id(rel)
            if doc_id in missing and doc_id not in paths and rel.split("/")[-2] == TYPES[doc_id[0]]["dir"]:
                paths[doc_id] = root / rel
    return paths


def trace_docs(names, paths):
    """Each doc id as `<id>@r<revision>`, from its file in `paths`; a name without a file or revision stays as
    given."""
    revisions = {name: doc_revision(path) for name, path in paths.items()}
    return ["{}@r{}".format(name, revisions[name]) if revisions.get(name) else name for name in names]


def doc_field(path, key):
    """Field `key` of a doc file's frontmatter; None when it has none or the file cannot be read."""
    try:
        return (parse_frontmatter(path.read_text(encoding="utf-8").split("\n"))[0] or {}).get(key)
    except (OSError, ValueError):
        return None


def doc_revision(path):
    """The `revision` in a doc file's frontmatter; None when it has none or the file cannot be read."""
    revision = doc_field(path, "revision")
    return revision if isinstance(revision, int) else None


def as_built_commit(root, path):
    """The full name of the commit that the `as_built` field of the doc at `path` names; None when the field names
    none, as `worktree` does (D002#as-built-revisions)."""
    return commit_name(root, doc_field(path, "as_built"), env=trace_env())


def trace_host():
    """The agent host and the conversation the environment names."""
    env = os.environ
    if env.get("CURSOR_AGENT") == "1":
        host = "cursor"
    elif env.get("CODEX_THREAD_ID"):
        host = "codex"
    elif env.get("CLAUDECODE") == "1":
        host = "claude-code"
    else:
        host = "other"
    return host, env.get("CURSOR_CONVERSATION_ID") or env.get("CODEX_THREAD_ID") or None


def event_lines(trace_dir, *needles):
    """Yield (v1 event, None) or (None, reason) for each matching line; no needles selects every line."""
    try:
        events = (trace_dir / "events.jsonl").open("rb")
    except FileNotFoundError:
        return
    with events:
        for raw in events:
            if needles and not any(needle in raw for needle in needles):
                continue
            try:
                event = json.loads(raw.decode("utf-8"))
            except (ValueError, RecursionError):
                event = None
            if not isinstance(event, dict) or type(event.get("v")) is not int:
                yield None, "malformed"
            elif event["v"] != 1:
                yield None, "unsupported"
            else:
                yield event, None


def read_events(trace_dir, *needles):
    """The parseable v1 events matching the given byte strings."""
    return [event for event, problem in event_lines(trace_dir, *needles) if not problem]


def unit_events(trace_dir, unit):
    """The start and end lines of `unit`, each None when the events file holds none."""
    start = end = None
    if UNIT_RE.match(unit):
        for event in read_events(trace_dir, unit.encode()):
            if event.get("id") == unit and event.get("type") == "start":
                start = start or event
            elif event.get("id") == unit and event.get("type") == "end":
                end = end or event
    return start, end


def unit_in_writable_store(root, trace_dir, unit):
    """Find the sole origin of a saved unit ID before appending related evidence under the writer's lock."""
    origins = []
    for store, directory in history_stores(root):
        start, end = unit_events(directory, unit)
        if start:
            origins.append((store, directory, start, end))
    if not origins:
        raise TraceError("{} names no unit".format(unit))
    if len(origins) > 1:
        raise TraceError("{} is ambiguous (main and worktree stores)".format(unit))
    store, directory, start, end = origins[0]
    if directory != trace_dir:
        raise TraceError("{} belongs to the {} store, which is not the current writable store".format(unit, store))
    return start, end


def start_parent(trace_dir, args):
    """The start line of the open unit `--parent` names, once checked that it may hold a unit of this kind."""
    if args.kind in TOP_LEVEL_KINDS and args.parent:
        raise TraceError("{} units are top-level and take no --parent".format(args.kind))
    if not args.parent:
        if args.kind == "slice":
            raise TraceError("a slice needs --parent naming its implement unit")
        return None
    start, end = unit_events(trace_dir, args.parent)
    if start is None:
        raise TraceError("--parent {} names no unit".format(args.parent))
    kind = start.get("kind")
    if kind in ("slice", "end-check"):
        raise TraceError("{} units cannot be parents".format(kind))
    if end is not None:
        raise TraceError("--parent {} has ended".format(args.parent))
    if args.kind == "slice" and kind != "implement":
        raise TraceError("slice parents are implement units, not {} units".format(kind))
    return start


def review_fixed_point(start):
    """The revision or (base, plan revision) that identifies the work a review can continue."""
    docs = start.get("docs") or []
    if start["kind"] == "code-review":
        plans = [doc for doc in docs if doc.startswith("P")]
        if not start.get("base") or len(plans) > 1 or (plans and not target_reference(plans[0], "@r")):
            raise TraceError("--continues needs a recorded base and an exact revision of any plan")
        return start["base"], plans
    if not docs or not target_reference(docs[0], "@r"):
        raise TraceError("--continues needs the primary target at an exact revision")
    return docs[0]


def check_review_continuation(root, trace_dir, line):
    """Check the handoff's identity before snapshotting and again under the append lock."""
    kind = line["kind"]
    if kind not in REVIEW_ROLES:
        raise TraceError("--continues comes with gate, follow-up and code-review units only")
    previous, end = unit_in_writable_store(root, trace_dir, line["continues"])
    if previous.get("kind") != kind or not end or end.get("kind") != kind or end.get("outcome") != "handoff":
        raise TraceError("--continues needs a handoff end of the same review kind")
    if review_fixed_point(previous) != review_fixed_point(line):
        raise TraceError("--continues needs the same primary revision, or the same base and plan for a code review")
    predecessor = line["continues"]
    if any(event.get("type") == "start" and event.get("continues") == predecessor
           for event in read_events(trace_dir, predecessor.encode())):
        raise TraceError("{} already has a continuation".format(predecessor))


def ignore_trace_dir(root):
    """Write .canon/canon/.gitignore when missing, so no commit holds the trace directory even when the project's own
    .gitignore lacks .canon/."""
    path = root / LOCAL_DIR / "canon" / ".gitignore"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        with contextlib.suppress(FileExistsError), path.open("xb") as ignore:
            ignore.write(b"*\n")


def event_bytes(line):
    """`line` as one compact UTF-8 JSON line of at most 16 KiB."""
    data = json.dumps(line, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(data) > MAX_EVENT:
        raise TraceError("the event line would be {} bytes, over the 16 KiB limit".format(len(data)))
    return data + b"\n"


def events_lock(trace_dir):
    return file_lock(trace_dir / "events.lock", TRACE_LOCK_WAIT, TraceError("timed out waiting for events.lock"))


def write_event_bytes(trace_dir, data):
    """Append the serialized lines in one write while the caller holds events.lock."""
    fd = os.open(str(trace_dir / "events.jsonl"),
                 os.O_WRONLY | os.O_APPEND | os.O_CREAT | getattr(os, "O_BINARY", 0), 0o666)
    try:
        written = os.write(fd, data)
    finally:
        os.close(fd)
    if written != len(data):
        raise TraceError("wrote {} of the {} bytes to append to events.jsonl".format(written, len(data)))


def append_event(trace_dir, line, check, manifest=None, store=None):
    """Append `line` to events.jsonl in one write, under events.lock and once `check` passes there again, preceded by
    the `manifest` line of its digest when the file holds none. `store`, run there once `check` passes and before
    `line` is serialized, stores what the line records and completes it, so that a call rejected there stores
    nothing."""
    entry = event_bytes(manifest) if manifest else b""
    with events_lock(trace_dir):
        check()
        with store() if store else contextlib.nullcontext():
            data = event_bytes(line)
            if entry and not any(event.get("type") == "manifest" and event.get("digest") == manifest["digest"]
                                 for event in read_events(trace_dir, manifest["digest"].encode())):
                data = entry + data
            write_event_bytes(trace_dir, data)


def trace_env(**extra):
    """The environment of trace's Git commands: the caller's, without the variables that point Git at another
    repository, index or object store, and with GIT_OPTIONAL_LOCKS=0 so that no command rewrites the project's index."""
    env = {key: value for key, value in os.environ.items() if key not in REPO_ENV}
    env.update(GIT_OPTIONAL_LOCKS="0", **extra)
    return env


def errno_name(error):
    return errno.errorcode.get(error.errno, "OSError")


def remove_tree(path):
    """Remove the directory `path` and what it holds, as far as possible. Windows refuses to delete a read-only file,
    and Git makes loose objects read-only, so an entry whose removal fails is made writable and removed again; a
    symlink is never followed. Python 3.12 deprecates rmtree's onerror in favour of onexc."""
    def retry(function, failed, _error):
        with contextlib.suppress(OSError):
            mode = os.lstat(failed).st_mode
            if function in (os.unlink, os.rmdir) and not stat.S_ISLNK(mode):
                os.chmod(failed, stat.S_IMODE(mode) | stat.S_IWRITE)
                function(failed)

    if sys.version_info >= (3, 12):
        shutil.rmtree(str(path), onexc=retry)
    else:
        shutil.rmtree(str(path), onerror=retry)


def trace_git(cwd, env, *args, data=None, stdin=None, stdout=subprocess.PIPE):
    """Run `git *args` and return its output; raise SnapshotSkip naming the Git command and how it failed."""
    command = "git " + next(arg for arg in args if not arg.startswith("-"))
    try:
        result = subprocess.run(["git", *args], cwd=str(cwd), env=env, input=data, stdin=stdin, stdout=stdout,
                                stderr=subprocess.PIPE)
    except OSError as error:
        raise SnapshotSkip("{}: {}".format(command, errno_name(error)))
    if result.returncode:
        raise SnapshotSkip("{}: exit {}".format(command, result.returncode), result.stderr)
    return result.stdout


def snapshot_git(trace_dir, env, *args, **options):
    """Run `git *args` in the snapshot repository, as trace_git does."""
    return trace_git(trace_dir, env, "--git-dir=" + str(trace_dir / ".git"), *args, **options)


def trace_head(root, is_git):
    """The commit HEAD names; None on an unborn branch or outside Git."""
    if not is_git:
        return None
    try:
        return trace_git(root, trace_env(), "rev-parse", "--verify", "-q", "HEAD^{commit}").decode().strip()
    except SnapshotSkip:
        return None


def resolve_base(root, ref, head):
    """The merge base of commit `ref` and HEAD; None without `ref`, on an unborn branch, outside Git (`head` is None
    in both) and without a merge base. A `ref` that names no commit is invalid input."""
    if ref is None or head is None:
        return None
    env, invalid = trace_env(), TraceError("--base {} names no commit".format(ref))
    if ref.startswith("-"):
        raise invalid
    try:
        commit = trace_git(root, env, "rev-parse", "--verify", "-q", ref + "^{commit}").decode().strip()
    except SnapshotSkip:
        raise invalid
    try:
        return trace_git(root, env, "merge-base", commit, head).decode().strip()
    except SnapshotSkip:
        return None


def snapshot_repo(trace_dir, unit, env, sha256):
    """The snapshot repository's Git directory, created on first use."""
    git_dir = trace_dir / ".git"
    if not git_dir.is_dir():
        build_snapshot_repo(trace_dir, unit, env, sha256)
    return git_dir


def build_snapshot_repo(trace_dir, unit, env, sha256):
    """Create the snapshot repository in the project's object format, whatever default object format Git is
    configured with: non-bare, its HEAD on an empty commit. It is built aside and renamed into place, so a .git in the
    trace directory is always complete."""
    build = trace_dir / (".init-" + unit)
    built = "--git-dir=" + str(build / ".git")
    try:
        if sha256:
            trace_git(trace_dir, env, "init", "-q", "--template=", "--object-format=sha256", str(build))
        else:
            trace_git(trace_dir, dict(env, GIT_DEFAULT_HASH="sha1"), "init", "-q", "--template=", str(build))
        tree = trace_git(trace_dir, env, built, "mktree", data=b"").decode().strip()
        commit = trace_git(trace_dir, env, built, "commit-tree", tree, "-m", "canon trace").decode().strip()
        trace_git(trace_dir, env, built, "update-ref", "HEAD", commit)
        try:
            os.rename(str(build / ".git"), str(trace_dir / ".git"))
        except OSError as error:
            raise SnapshotSkip("git init: " + errno_name(error))
    finally:
        remove_tree(build)


def copy_index(source, target):
    """Copy the index at `source` to `target` with its modification time, which Git compares entries against to
    find racily clean ones; copy nothing when there is no index."""
    if not os.path.exists(source):
        return
    try:
        with open(source, "rb") as src, open(str(target), "wb") as dst:
            info = os.fstat(src.fileno())
            shutil.copyfileobj(src, dst)
        os.utime(str(target), ns=(info.st_atime_ns, info.st_mtime_ns))
    except OSError as error:
        raise SnapshotSkip("index copy: " + errno_name(error))


def changes_size(root, status):
    """The total size of the untracked files and of the files with unstaged changes in the output of
    `git status --porcelain -z`."""
    total, records = 0, iter(status.split(b"\0"))
    for record in records:
        if len(record) < 4:
            continue
        if record[0:1] in b"RC" or record[1:2] in b"RC":
            next(records, None)
        if record[1:2] != b" ":
            with contextlib.suppress(OSError):
                info = os.lstat(os.path.join(str(root), os.fsdecode(record[3:])))
                total += info.st_size if stat.S_ISREG(info.st_mode) else 0
    return total


def take_snapshot(root, trace_dir, unit, parent, namespace="trace", borrow=False, as_built=None):
    """Record the work tree at refs/<namespace>/<unit> in the snapshot repository, as a commit whose parent holds the
    tree of commit `parent`, or that has no parent when `parent` is None (D001#snapshots); with a `parent`, the tree
    of commit `as_built` is its second parent. Return the snapshot commit. With `borrow`, the repository reads the
    project's objects through its alternates instead of copying them (D003#review-snapshots)."""
    env = trace_env(**SNAPSHOT_IDENTITY)
    status = trace_git(root, env, "status", "--porcelain", "-z", "--untracked-files=all")
    if changes_size(root, status) > MAX_CHANGES:
        raise SnapshotSkip("changes-over-10MiB")
    lines = trace_git(root, env, "rev-parse", "--git-path", "index", "--git-path", "objects",
                      "--show-object-format").splitlines()
    index, objects = (os.path.abspath(os.path.join(str(root), os.fsdecode(path))) for path in lines[:2])
    git_dir = snapshot_repo(trace_dir, unit, env, sha256=lines[2:] == [b"sha256"])
    if borrow:
        borrow_objects(git_dir, objects)
    copy = git_dir / ("index-" + unit)
    try:
        copy_index(index, copy)
        steps = dict(env, GIT_INDEX_FILE=str(copy), GIT_OBJECT_DIRECTORY=str(git_dir / "objects"),
                     GIT_ALTERNATE_OBJECT_DIRECTORIES=objects)
        trace_git(root, steps, "add", "-A")
        tree = trace_git(root, steps, "write-tree").decode().strip()
        sources = [(parent, "base"), (as_built, "as-built")] if parent else []
        parents = []
        for source, role in sources:
            if source:
                tree_commit = trace_git(root, steps, "commit-tree", source + "^{tree}", "-m",
                                        "{} {} {}".format(namespace, unit, role))
                parents += ["-p", tree_commit.decode().strip()]
        commit = trace_git(root, steps, "commit-tree", tree, *parents, "-m",
                           "{} {}".format(namespace, unit)).decode().strip()
        if not borrow:
            copy_borrowed(root, steps, trace_dir, env, commit)
        snapshot_git(trace_dir, env, "update-ref", "refs/{}/{}".format(namespace, unit), commit)
    finally:
        with contextlib.suppress(OSError):
            copy.unlink()
    with contextlib.suppress(SnapshotSkip):
        snapshot_git(trace_dir, env, "-c", "gc.autoDetach=false", "gc", "--auto", "--quiet")
    return commit


def borrow_objects(git_dir, objects):
    """Name the project's object directory, the absolute path `objects`, in the snapshot repository's alternates."""
    path = git_dir / "objects" / "info" / "alternates"
    data = os.fsencode(objects) + b"\n"
    try:
        if not path.is_file() or path.read_bytes() != data:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
    except OSError as error:
        raise SnapshotSkip("alternates: " + errno_name(error))


def copy_borrowed(root, steps, trace_dir, env, *tips):
    """Copy the missing objects reachable from these commits or trees into the independent snapshot repository."""
    listing = trace_git(root, steps, "rev-list", "--objects", *tips)
    found = snapshot_git(trace_dir, env, "cat-file", "--batch-check",
                         data=b"".join(line.split(b" ", 1)[0] + b"\n" for line in listing.splitlines()))
    missing = b"".join(line.split(b" ", 1)[0] + b"\n" for line in found.splitlines() if line.endswith(b" missing"))
    if missing:
        try:
            with tempfile.TemporaryFile(dir=str(trace_dir / ".git")) as pack:
                trace_git(root, steps, "pack-objects", "--stdout", "-q", data=missing, stdout=pack)
                pack.seek(0)
                snapshot_git(trace_dir, env, "index-pack", "--stdin", stdin=pack)
        except OSError as error:
            raise SnapshotSkip("git pack-objects: " + errno_name(error))


@contextlib.contextmanager
def snapshot_lock(trace_dir):
    """Hold snapshot.lock, which keeps each start's snapshot and skill storage apart from the others' and from prune;
    raise SnapshotSkip when it cannot be taken."""
    with contextlib.ExitStack() as held:
        try:
            held.enter_context(file_lock(trace_dir / "snapshot.lock", TRACE_LOCK_WAIT,
                                         SnapshotSkip("snapshot lock: timeout")))
        except OSError as error:
            raise SnapshotSkip("snapshot lock: " + errno_name(error))
        yield


def record_snapshot(root, is_git, trace_dir, unit, parent, manifest, files, as_built):
    """Under snapshot.lock, take the unit's snapshot as take_snapshot does, then store the skill files of `manifest`
    when the snapshot repository exists; return the snapshot commit and the reason none was recorded, one of them
    None. A start that cannot take the lock records and stores nothing."""
    if not is_git:
        return None, "no-git"
    snapshot = skip = None
    try:
        with snapshot_lock(trace_dir):
            try:
                snapshot = take_snapshot(root, trace_dir, unit, parent, as_built=as_built)
            except SnapshotSkip as failed:
                skip = failed
            if manifest and (trace_dir / ".git").is_dir():
                store_skills(trace_dir, manifest, files)
    except SnapshotSkip as failed:
        skip = failed
    if skip and skip.message:
        with contextlib.suppress(OSError):
            (trace_dir / unit).mkdir(parents=True, exist_ok=True)
            (trace_dir / unit / "snapshot-error.txt").write_bytes(skip.message[-MAX_SNAPSHOT_ERROR:])
    return snapshot, skip.reason if skip else None


def human_size(size):
    for unit in ("KiB", "MiB", "GiB"):
        size /= 1024
        if size < 1024 or unit == "GiB":
            return "{:.1f} {}".format(size, unit)


def snapshot_line(trace_dir):
    """The line saying how many snapshots the snapshot repository holds and its size on disk."""
    git_dir, count, size = trace_dir / ".git", 0, 0
    if git_dir.is_dir():
        with contextlib.suppress(SnapshotSkip):
            count = len(snapshot_git(trace_dir, trace_env(), "for-each-ref", "--format=%(refname)",
                                     "refs/trace/").splitlines())
        for path, _dirs, names in os.walk(str(git_dir)):
            for name in names:
                with contextlib.suppress(OSError):
                    size += os.lstat(os.path.join(path, name)).st_size
    return "snapshots: {}, {} on disk".format(count, human_size(size))


def snapshot_summary(trace_dir):
    """The status lines on snapshots: the snapshot line, and the starts that recorded none, by reason."""
    reasons = {}
    for event in read_events(trace_dir, b'"skipped":"'):
        if event.get("type") == "start" and isinstance(event.get("skipped"), str):
            reasons[event["skipped"]] = reasons.get(event["skipped"], 0) + 1
    skipped = "; ".join("{} {}".format(n, reason) for reason, n in sorted(reasons.items(), key=lambda r: (-r[1], r[0])))
    return [snapshot_line(trace_dir), "skipped starts: " + (skipped or "none")]


def skill_dirs(skill):
    """The directories named canon or canon-* that hold a SKILL.md beside the directory `skill`, or in every category
    directory when `skill` sits in the skills repository's skills/<category>/<name>/ layout, by name."""
    skill = Path(skill)
    tops = [skill.parent]
    if skill.parent.parent.name == "skills":
        with contextlib.suppress(OSError):
            tops = sorted(path for path in skill.parent.parent.iterdir() if path.is_dir())
    found = {}
    for top in tops:
        with contextlib.suppress(OSError):
            for path in sorted(top.iterdir()):
                if (path.name == "canon" or path.name.startswith("canon-")) and (path / "SKILL.md").is_file():
                    found.setdefault(path.name, path)
    return found


def covered_files(directory, prefix=""):
    """The files a skill's digest covers, as (path from the skill directory, executable, content): every regular file
    under `directory` but LICENSE, NOTICE and *.pyc, and none under __pycache__/ or named with a leading dot."""
    files = []
    with os.scandir(str(directory)) as entries:
        for entry in entries:
            if entry.name.startswith(".") or entry.name in ("LICENSE", "NOTICE", "__pycache__") \
                    or entry.name.endswith(".pyc"):
                continue
            if entry.is_dir(follow_symlinks=False):
                files += covered_files(entry.path, prefix + entry.name + "/")
            elif entry.is_file(follow_symlinks=False):
                with open(entry.path, "rb") as file:
                    executable = bool(os.fstat(file.fileno()).st_mode & stat.S_IXUSR)
                    files.append((prefix + entry.name, executable, file.read()))
    return files


def sha256_json(value, **options):
    """The SHA-256 of `value` as compact UTF-8 JSON."""
    text = json.dumps(value, ensure_ascii=False, separators=(",", ":"), **options)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def skill_manifest(skill):
    """The `manifest` line of the skills found from the directory `skill`, and the files its digests cover as (tree
    path, executable, content), each skill directory under its name. A skill's digest is the SHA-256 of its covered
    files' sorted [path, Git blob id] pairs, and the manifest's that of its skills (D001#skill-digests)."""
    skills, files = {}, []
    for name, directory in sorted(skill_dirs(skill).items()):
        covered = covered_files(directory)
        skills[name] = sha256_json(sorted([path, hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()]
                                          for path, _executable, data in covered))
        files += [(name + "/" + path, executable, data) for path, executable, data in covered]
    return {"v": 1, "type": "manifest", "digest": sha256_json(skills, sort_keys=True), "skills": skills}, files


def quoted(path):
    """`path` as a C-style quoted string, the form in which git fast-import takes a path holding any byte."""
    return b'"' + b"".join(b"\\%03o" % byte if byte < 32 or byte in b'"\\\x7f' else bytes([byte])
                           for byte in os.fsencode(path)) + b'"'


def store_skills(trace_dir, manifest, files):
    """Store the files of a manifest the snapshot repository lacks there, as a parentless commit at
    refs/skills/<manifest digest>; best-effort, since the next start with that manifest stores it."""
    ref, env = "refs/skills/" + manifest["digest"], trace_env()
    with contextlib.suppress(SnapshotSkip):
        if snapshot_git(trace_dir, env, "for-each-ref", ref):
            return
        committer = "{GIT_COMMITTER_NAME} <{GIT_COMMITTER_EMAIL}> {when} +0000".format(when=int(time.time()),
                                                                                    **SNAPSHOT_IDENTITY)
        message = "skills " + manifest["digest"]
        stream = [b"commit %s\ncommitter %s\ndata %d\n%s\n" % (ref.encode(), committer.encode(), len(message),
                                                                message.encode())]
        for path, executable, data in files:
            mode = b"100755" if executable else b"100644"
            stream.append(b"M %s inline %s\ndata %d\n%s\n" % (mode, quoted(path), len(data), data))
        snapshot_git(trace_dir, env, "fast-import", "--quiet", data=b"".join(stream))


def short_field(value):
    """Whether `value` is a non-empty single-line string of at most 200 characters, as model and reviewer ids are."""
    return isinstance(value, str) and len(value) <= MAX_REVIEWER_FIELD and value.splitlines() == [value]


def new_id(now):
    """The id of a unit or review snapshot that starts at the UTC time `now`: that time and 6 random hex digits."""
    return now.strftime(UNIT_TIME_FORMAT) + "-" + os.urandom(3).hex()


def trace_start(args):
    root, is_git = trace_root()
    holder = trace_holder(root)
    if not trace_state(holder, root)[0]:
        print("trace off")
        return 0
    if (args.kind == "slice") != bool(args.slice) or (args.slice and not SLICE_RE.fullmatch(args.slice)):
        raise TraceError("--slice S<n> comes with the slice kind only, which requires it")
    invalid = [doc for doc in args.docs if not FULL_ID_RE.fullmatch(doc)]
    if invalid:
        raise TraceError("DOC arguments are doc ids such as D001, not {}".format(", ".join(map(repr, invalid))))
    if args.model is not None and not short_field(args.model):
        raise TraceError("--model must be a single-line string of 1 to {} characters".format(MAX_REVIEWER_FIELD))
    trace_dir = holder / TRACE_DIR
    parent = start_parent(trace_dir, args)
    host, conversation = trace_host()
    started_ns = time.time_ns()
    now = datetime.datetime.fromtimestamp(started_ns // 10 ** 9, datetime.timezone.utc)
    unit = new_id(now)
    paths = trace_doc_paths(root, is_git, args.docs)
    line = {"v": 1, "type": "start", "id": unit, "kind": args.kind,
            "at": now.astimezone().isoformat(timespec="seconds"), "parent": args.parent,
            "docs": trace_docs(args.docs, paths)}
    if args.slice:
        line["slice"] = args.slice
    head = trace_head(root, is_git)
    base = resolve_base(root, args.base, head)
    line["base"] = base
    if args.continues is not None:
        line["continues"] = args.continues
        line["archive_since_ns"] = started_ns
        check_review_continuation(root, trace_dir, line)

    def check_start():
        start_parent(trace_dir, args)
        if args.continues is not None:
            check_review_continuation(root, trace_dir, line)

    if args.kind == "slice":
        model, skill = parent.get("model"), parent.get("skill")
    else:
        model = args.model.lower() if args.model else None
        skill = os.path.abspath(args.skill) if args.skill else None
    manifest, files = skill_manifest(skill) if skill else (None, [])
    ignore_trace_dir(holder)
    gate_doc = paths.get(args.docs[0]) if args.kind == "gate" and args.docs and is_git else None
    as_built = as_built_commit(root, gate_doc) if gate_doc else None
    snapshot, skipped = record_snapshot(root, is_git, trace_dir, unit, base or head, manifest, files, as_built)
    line.update(tier=args.tier or (parent or {}).get("tier"), head=head, snapshot=snapshot,
                skipped=skipped, host=host, conversation=conversation, model=model, skill=skill,
                manifest=manifest["digest"] if manifest else None)
    append_event(trace_dir, line, check_start, manifest)
    print("trace " + line["id"])
    return 0


def end_unit(trace_dir, args):
    """The start line of the unit `end` closes, once checked that it is open and its kind allows the outcome."""
    start, end = unit_events(trace_dir, args.unit)
    if start is None:
        raise TraceError("{} names no unit".format(args.unit))
    kind = start.get("kind")
    if kind == "slice":
        raise TraceError("a slice ends with its commit or the next start under its implement unit, not with end")
    if end is not None:
        raise TraceError("{} has already ended".format(args.unit))
    outcomes = KIND_OUTCOMES.get(kind, OUTCOMES)
    if args.outcome not in outcomes:
        raise TraceError("{} units end {} or {}".format(kind, ", ".join(outcomes[:-1]), outcomes[-1]))
    if (args.outcome == "escalated") != bool(args.to):
        raise TraceError("--to L1|L2|plan comes with escalated only, which requires it")
    return start


def read_dispositions(kind, source):
    """The dispositions `--input` reads, from file `source` or from stdin for `-`, once checked against
    D001#review-dispositions for a `kind` unit."""
    if kind not in REVIEW_ROLES:
        raise TraceError("--input comes with gate, follow-up and code-review units only")
    try:
        data = sys.stdin.buffer.read() if source == "-" else Path(source).read_bytes()
    except OSError as error:
        raise TraceError("cannot read --input {}: {}".format(source, errno_name(error)))
    try:
        dispositions = json.loads(data)
    except ValueError as error:
        raise TraceError("--input is not JSON: {}".format(error))
    check_dispositions(kind, dispositions)
    return dispositions


def reviewer_key(role, key):
    return isinstance(key, str) and (key == role or re.fullmatch(role + r"-(?:[2-9]|[1-9][0-9]+)", key))


def full_oid(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-fA-F]{40}(?:[0-9a-fA-F]{24})?", value)


def check_dispositions(kind, dispositions, allow_repeated_sources=False):
    """Raise TraceError unless `dispositions` holds what D001#review-dispositions defines for a `kind` unit and
    nothing else, so that no free text reaches the line."""
    def expect(ok, where, what):
        if not ok:
            raise TraceError("dispositions{} must be {}".format(where, what))

    def entry(value, where, keys, optional=()):
        expect(isinstance(value, dict), where, "an object")
        unknown = [key for key in value if key not in keys + optional]
        if unknown:
            raise TraceError("dispositions{} has keys a {} does not take: {}".format(where, kind, ", ".join(unknown)))
        missing = [key for key in keys if key not in value]
        if missing:
            raise TraceError("dispositions{} lacks {}".format(where, ", ".join(missing)))

    roles, review = REVIEW_ROLES[kind], kind == "code-review"
    entry(dispositions, "", ("reviewers", "findings", "new_blockers"))
    expect(isinstance(dispositions["reviewers"], list), ".reviewers", "a list")
    listed = []
    for n, reviewer in enumerate(dispositions["reviewers"]):
        where = ".reviewers[{}]".format(n)
        entry(reviewer, where, ("role", "model", "id"), ("key",) if review else ("key", "targets"))
        role = reviewer["role"]
        key = reviewer.get("key", role)
        expect(role in roles, where + ".role", "one of " + ", ".join(roles))
        expect(reviewer_key(role, key) and key not in listed, where + ".key", "a unique key for " + role)
        listed.append(key)
        if "targets" in reviewer:
            targets = reviewer["targets"]
            refs = [target_reference(t, "@r") for t in targets] if isinstance(targets, list) else []
            expect(refs and all(refs) and len({ref[0] for ref in refs}) == len(refs), where + ".targets",
                   "a non-empty list of distinct design or plan IDs at positive exact revisions")
        expect(short_field(reviewer["model"]), where + ".model", "a single-line string of at most 200 characters")
        expect(reviewer["id"] is None or short_field(reviewer["id"]), where + ".id",
               "null or a single-line string of at most 200 characters")
    expect(isinstance(dispositions["findings"], list), ".findings", "a list")
    sources = set()
    for n, finding in enumerate(dispositions["findings"]):
        where = ".findings[{}]".format(n)
        entry(finding, where, ("by", "severity", "disposition") + (("axis",) if review else ()),
              ("confirmed", "confirmations"))
        by = finding["by"]
        expect(isinstance(by, list) and by and all(isinstance(ref, str) and ref.partition(":")[0] in listed
                                                   and FINDING_ID_RE.fullmatch(ref.partition(":")[2]) for ref in by),
               where + ".by", "a non-empty list of <key>:F<n>, each naming a listed reviewer")
        if not allow_repeated_sources:
            expect(len(set(by)) == len(by) and sources.isdisjoint(by), where + ".by", "source references used only once")
            sources.update(by)
        expect(finding["severity"] in SEVERITIES, where + ".severity", " or ".join(SEVERITIES))
        expect(finding["disposition"] in REVIEW_DISPOSITIONS, where + ".disposition", " or ".join(REVIEW_DISPOSITIONS))
        if review:
            expect(finding["axis"] in ("spec", "standards"), where + ".axis", "spec or standards")
        if "confirmed" in finding:
            expect(finding["confirmed"] in CONFIRMATION_RESULTS, where + ".confirmed", "resolved or not-resolved")
        if "confirmations" in finding:
            confirmations = finding["confirmations"]
            expect(isinstance(confirmations, list) and confirmations, where + ".confirmations", "a non-empty list")
            confirmers = set()
            for i, item in enumerate(confirmations):
                field = "{}.confirmations[{}]".format(where, i)
                entry(item, field, ("reviewer", "result", "snapshot"))
                key = item["reviewer"]
                expect(key in listed and key not in confirmers, field + ".reviewer", "a distinct listed reviewer key")
                confirmers.add(key)
                expect(item["result"] in CONFIRMATION_RESULTS, field + ".result", "resolved or not-resolved")
                expect(item["snapshot"] is None or full_oid(item["snapshot"]), field + ".snapshot",
                       "null or a full 40- or 64-hex object ID")
            aggregate = "not-resolved" if any(c["result"] == "not-resolved" for c in confirmations) else "resolved"
            expect(finding.get("confirmed") == aggregate, where + ".confirmed", aggregate + " for these confirmations")
    blockers = dispositions["new_blockers"]
    expect(type(blockers) is int and blockers >= 0, ".new_blockers", "a non-negative integer")


def archive_source(root, path):
    """`--dir`, taken from the checkout `root` when relative, with symlinks resolved, once checked that it lies under
    the checkout's .canon/."""
    source = Path(os.path.realpath(os.path.join(str(root), path)))
    if Path(os.path.realpath(str(root / LOCAL_DIR))) not in source.parents:
        raise TraceError("--dir {} lies outside {} once symlinks are resolved".format(path, LOCAL_DIR))
    return source


def unit_started(unit):
    """The start time in the id of `unit`, in seconds since the epoch."""
    when = datetime.datetime.strptime(unit[:16], UNIT_TIME_FORMAT).replace(tzinfo=datetime.timezone.utc)
    return int(when.timestamp())


def regular_bytes(path, limit):
    """Read at most limit bytes from a regular file without following a final symlink."""
    if not stat.S_ISREG(path.lstat().st_mode):
        raise OSError(errno.EINVAL, "not a regular file", str(path))
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_BINARY", 0)
    with open(os.open(str(path), flags), "rb") as file:
        if not stat.S_ISREG(os.fstat(file.fileno()).st_mode):
            raise OSError(errno.EINVAL, "not a regular file", str(path))
        return file.read(limit)


def check_round_declaration(info):
    fields = {"kind", "tier", "targets", "require", "unit", "base", "baseline", "snapshot"}
    if not isinstance(info, dict) or not fields.issubset(info):
        raise TraceError("incomplete round declaration")
    kind, targets, required = info["kind"], info["targets"], info["require"]
    if not isinstance(kind, str) or kind not in REVIEW_ROLES or info["tier"] not in ("L0", "L1", "L2"):
        raise TraceError("invalid review kind or tier")
    if (not isinstance(targets, list) or (kind != "code-review" and not targets) or
        any(not target_reference(t, "@r") for t in targets) or
        len({t.partition("@")[0] for t in targets}) != len(targets)):
        raise TraceError("use --target ID@rN for each distinct initial design or plan")
    if (not isinstance(required, list) or
        any(not any(reviewer_key(role, key) for role in REVIEW_ROLES[kind]) for key in required) or
        len(set(required)) != len(required)):
        raise TraceError("--require needs distinct reviewer keys for this review kind")
    unit = info["unit"]
    if unit is not None and (not isinstance(unit, str) or not UNIT_RE.fullmatch(unit)):
        raise TraceError("--unit needs a trace unit ID")
    if (info["base"] is not None and not isinstance(info["base"], str) or
        info["snapshot"] is not None and not full_oid(info["snapshot"]) or
        info["baseline"] not in (None, "none") and not full_oid(info["baseline"])):
        raise TraceError("invalid first-round pins")


def read_review_round(root, directory):
    """Read a round's ownership record; a missing marker is allowed only at a legacy path."""
    try:
        data = regular_bytes(directory / "round.json", MAX_ARCHIVE + 1)
        if len(data) <= MAX_ARCHIVE:
            info = json.loads(data)
            check_round_declaration(info)
            return info
    except FileNotFoundError:
        if root / REVIEW_ROUND_DIR not in directory.parents or not directory.name.startswith("round-"):
            return None
    except (OSError, ValueError, TraceError):
        pass
    raise TraceError("missing or invalid round.json")


def archive_files(source, target, since_ns, info):
    """Copy up to 2 MiB of direct regular files. A matching round has no age cutoff; legacy files use since_ns."""
    written = []
    try:
        with os.scandir(str(source)) as entries:
            names = sorted(entry.name for entry in entries if entry.is_file(follow_symlinks=False)
                           and (since_ns is None or entry.stat(follow_symlinks=False).st_mtime_ns >= since_ns))
        files, total = {}, 0
        for name in names:
            files[name] = regular_bytes(source / name, MAX_ARCHIVE + 1 - total)
            total += len(files[name])
            if total > MAX_ARCHIVE:
                return "over-2MiB", {}
        if info is not None:
            try:
                if json.loads(files.get("round.json", b"")) != info:
                    raise ValueError()
            except ValueError:
                raise TraceError("round.json changed during archival")
        if not files:
            return "none", {}
        target.mkdir(parents=True, exist_ok=True)
        for name, data in files.items():
            written.append(target / name)
            written[-1].write_bytes(data)
    except OSError as error:
        for path in written:
            with contextlib.suppress(OSError):
                path.unlink()
        return "copy: " + errno_name(error), {}
    return "ok", files


def review_pins(review_dir, env, kind, info, files, gaps):
    """Resolve the expected pins in the supplied evidence. A mixed follow-up deliberately omits its shared base."""
    pins = {}
    for material in ("snapshot", "baseline"):
        name = material + ".txt"
        literal = files.get(name, b"").strip().decode("ascii", "replace")
        if material == "baseline" and kind == "follow-up" and (info.get("base") is None if info else not literal):
            continue
        try:
            if not literal:
                raise SnapshotSkip("missing or unreadable")
            if material == "baseline" and literal == "none" and kind != "code-review":
                commit = "none"
            else:
                if material == "snapshot" and not full_oid(literal):
                    raise SnapshotSkip("expected a full commit ID")
                commit = review_commit(review_dir, env, literal)
                if material == "snapshot" and literal.lower() != commit:
                    raise SnapshotSkip("expected a full commit ID")
            if info is not None and commit != info.get(material):
                raise SnapshotSkip("does not match the pinned round input")
            pins[material] = commit
        except (OSError, SnapshotSkip) as error:
            gaps[name] = str(error)
    return pins


def retain_review_input(root, trace_dir, line, info, files, gaps):
    """Bind the archived first-round pins to independent trees before publishing the accepted review end."""
    review_dir, unit = root / REVIEW_SNAPSHOT_DIR, line["id"]
    env = trace_env(**SNAPSHOT_IDENTITY)
    try:
        # A missing store still allows per-material diagnostics, without creating another store to inspect it.
        lock = snapshot_lock(review_dir) if (review_dir / ".git").is_dir() else contextlib.nullcontext()
        with lock:
            pins = review_pins(review_dir, env, line["kind"], info, files, gaps)
            if len(pins) != 2:
                return
            base, target = pins["baseline"], pins["snapshot"]
            binding = {}
            if base != files["baseline.txt"].strip().decode("ascii").lower():
                binding["review_baseline"] = base
            # An optional pin must not displace a valid end near the 16 KiB limit.
            event_bytes(dict(line, review_input=target, **binding))
            commits = [target] if base == "none" else [base, target]
            trees = snapshot_git(review_dir, env, "rev-parse", *(c + "^{tree}" for c in commits)).decode().split()
            with snapshot_lock(trace_dir):
                snapshot_repo(trace_dir, unit, env, sha256=len(target) == 64)
                copy_borrowed(review_dir, dict(env, GIT_DIR=str(review_dir / ".git")), trace_dir, env, *trees)
                parents = []
                if len(trees) == 2:
                    parent = snapshot_git(trace_dir, env, "commit-tree", trees[0], "-m", "review baseline " + unit)
                    parents = ["-p", parent.decode().strip()]
                commit = snapshot_git(trace_dir, env, "commit-tree", trees[-1], *parents, "-m", "review input " + unit)
                oid = commit.decode().strip()
                snapshot_git(trace_dir, env, "update-ref", "refs/review-input/" + unit, oid)
                line.update(review_input=oid, **binding)
    except (OSError, SnapshotSkip, TraceError) as error:
        gaps["review_input"] = "could not retain the first-round trees: " + str(error)


def required_review_passes(info):
    roles = list(REVIEW_ROLES[info["kind"]])
    if info["tier"] != "L2":
        roles.remove("cross-family")
    return list(dict.fromkeys(roles + info["require"]))


def review_prompt_gaps(files, keys, gaps):
    for key in keys:
        name = key + "-prompt.md"
        if not files.get(name, b"").strip():
            gaps[name] = "missing, unreadable or empty"


def warn_review_gaps(root, directory, unit, gaps, model=None):
    """Recording friction is best-effort. Deduplicate a round's material across start, check, close and retries."""
    if not gaps:
        return
    address = posix_rel(directory, root) if directory else unit
    for material, reason in gaps.items():
        print("review warning: {}: {}: {}".format(address, material, reason), file=sys.stderr)
    ledger = root / LOCAL_DIR / "canon-retro" / "skills.jsonl"
    host, conversation = trace_host()
    now = datetime.datetime.now().astimezone()
    skill_hash = "unknown"
    try:
        lock = json.loads((root / "skills-lock.json").read_bytes())
        skill_hash = lock["skills"]["canon"]["computedHash"]
    except (OSError, ValueError, KeyError, TypeError):
        pass
    try:
        with file_lock(ledger.with_suffix(".lock"), TRACE_LOCK_WAIT, TraceError("retro lock timeout")), ledger.open("a+b") as log:
            log.seek(0)
            seen = set()
            for raw in log:
                with contextlib.suppress(ValueError, TypeError, AttributeError):
                    row = json.loads(raw)
                    if row.get("round") == address and row.get("unit") == unit:
                        seen.add(row.get("material"))
            for material, reason in gaps.items():
                if material in seen:
                    continue
                record = dict(date=now.date().isoformat(), session=conversation or now.strftime("%Y%m%d-%H%M"),
                              host=host, model=model or "unknown", skill="canon", skill_hash=skill_hash,
                              canon="canon " + CANON_VERSION, step="review input", round=address, unit=unit,
                              material=material, event=material + ": " + reason,
                              suggestion="Verify the requested review material in the round before closing it.")
                log.write(json.dumps(record).encode("utf-8") + b"\n")
    except (OSError, TraceError) as error:
        print("review warning: could not record the retro entry: " + str(error), file=sys.stderr)


def trace_end(args):
    root, is_git = trace_root()
    holder = trace_holder(root)
    if not trace_state(holder, root)[0]:
        print("trace off")
        return 0
    trace_dir = holder / TRACE_DIR
    start = end_unit(trace_dir, args)
    kind = start.get("kind")
    dispositions = read_dispositions(kind, args.input) if args.input is not None else None
    source = archive_source(root, args.dir) if args.dir is not None else None
    now = datetime.datetime.now(datetime.timezone.utc)
    line = {"v": 1, "type": "end", "id": args.unit, "kind": kind,
            "at": now.astimezone().isoformat(timespec="seconds"), "outcome": args.outcome}
    if args.to:
        line["to"] = args.to
    line["head"] = trace_head(root, is_git)
    manifest = None
    if start.get("parent") is None:
        manifest = skill_manifest(start["skill"])[0] if start.get("skill") else None
        line["manifest"] = manifest["digest"] if manifest else None
    if kind in REVIEW_ROLES:
        line["dispositions"] = dispositions
    line["archive"] = None
    gaps = {}

    @contextlib.contextmanager
    def archive():
        files = {}
        info = None
        if source:
            cutoff = start.get("archive_since_ns", unit_started(args.unit) * 10 ** 9)
            try:
                info = read_review_round(root, source)
                if info is not None:
                    if (info["unit"], info["kind"]) != (args.unit, kind):
                        raise TraceError("round unit or review kind mismatch")
                    cutoff = None
                line["archive"], files = archive_files(source, trace_dir / args.unit, cutoff, info)
            except TraceError as error:
                line["archive"] = "copy: EINVAL"
                gaps["archive"] = str(error)
        if kind not in REVIEW_ROLES:
            yield
            return
        ref = "refs/review-input/" + args.unit
        if line["archive"] == "ok":
            if dispositions is not None:
                keys = [r.get("key", r["role"]) for r in dispositions["reviewers"]]
            elif info and args.outcome == "delivered":
                keys = required_review_passes(info)
            else:
                keys = []
            review_prompt_gaps(files, keys, gaps)
            retain_review_input(root, trace_dir, line, info, files, gaps)
        elif source or args.outcome == "delivered" and dispositions is not None:
            gaps.setdefault("archive", line["archive"] or "no round directory supplied")
        oid = line.get("review_input")
        if not oid:
            # An interrupted end may already have published this unit's ref.
            with contextlib.suppress(SnapshotSkip):
                snapshot_git(trace_dir, trace_env(), "update-ref", "-d", ref)
        try:
            yield
        except BaseException:
            if oid:
                with contextlib.suppress(SnapshotSkip):
                    snapshot_git(trace_dir, trace_env(), "update-ref", "-d", ref, oid)
            raise

    append_event(trace_dir, line, lambda: end_unit(trace_dir, args), manifest, archive)
    warn_review_gaps(root, source, args.unit, gaps, start.get("model"))
    print("trace {} ended".format(args.unit))
    return 0


def finding_source(dispositions, reference):
    """Resolve the caller's alias and the stored primary source, both unambiguous even in a legacy end."""
    matches = [f for f in dispositions["findings"] if reference in f["by"]]
    if not matches:
        raise TraceError("unknown finding " + reference)
    if len(matches) != 1:
        raise TraceError("ambiguous finding " + reference)
    source = matches[0]["by"][0]
    if source != reference and any(f is not matches[0] and source in f["by"] for f in dispositions["findings"]):
        raise TraceError("ambiguous primary source " + source)
    return source


def check_recheck(record):
    """Validate a recheck's evidence before appending it or using its report stem to inspect an archive."""
    roles = REVIEW_ROLES.get(record["kind"], ())
    key, source = record.get("reviewer"), record.get("finding")
    if not any(reviewer_key(role, key) for role in roles):
        raise TraceError("invalid reviewer key for " + record["kind"])
    source_key, _, finding_id = source.partition(":") if isinstance(source, str) else ("", "", "")
    if not (any(reviewer_key(role, source_key) for role in roles) and FINDING_ID_RE.fullmatch(finding_id)):
        raise TraceError("finding must be <key>:F<n>")
    if not short_field(record.get("model")):
        raise TraceError("a new reviewer key requires a single-line model ID of 1 to 200 characters")
    if not full_oid(record.get("snapshot")):
        raise TraceError("snapshot must be a full 40- or 64-hex object ID")
    if record.get("result") not in CONFIRMATION_RESULTS:
        raise TraceError("result must be resolved or not-resolved")
    stem = record.get("report")
    if not isinstance(stem, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", stem):
        raise TraceError("report must be 1 to 100 ASCII letters, digits, hyphens or underscores")
    order = record.get("order")
    if "order" not in record or (order is not None and (type(order) is not int or order < 1)):
        raise TraceError("order must be a positive integer or unknown")


def recheck_model(key, supplied, models):
    if len(models) > 1 or (models and supplied is not None and supplied not in models):
        raise TraceError("model does not match the recorded identity of " + key)
    return next(iter(models), supplied)


def recheck_claim(event):
    return (event["reviewer"], event["model"], event["snapshot"].lower(), event["result"], event["order"])


def new_recheck(args, kind, dispositions, previous):
    """Build the canonical event, or return None for an identical retry of a recorded report."""
    source = finding_source(dispositions, args.finding)
    models = {r["model"] for r in dispositions["reviewers"] if r.get("key", r["role"]) == args.reviewer}
    models.update(e["model"] for e in previous if e["reviewer"] == args.reviewer)
    model = recheck_model(args.reviewer, args.model, models)
    if args.order != "unknown" and not re.fullmatch(r"[0-9]+", args.order):
        raise TraceError("order must be a positive integer or unknown")
    record = {"v": 1, "type": "recheck", "id": args.unit, "kind": kind, "finding": source,
              "reviewer": args.reviewer, "model": model, "snapshot": args.snapshot.lower(),
              "result": args.result, "report": args.report,
              "order": None if args.order == "unknown" else int(args.order)}
    check_recheck(record)
    for old in previous:
        if old["finding"] != source:
            continue
        if old["report"] == record["report"]:
            if recheck_claim(old) == recheck_claim(record):
                return None
            raise TraceError("conflicting recheck for report " + record["report"])
        if record["order"] is not None and old["order"] == record["order"]:
            raise TraceError("recheck order {} already belongs to {}".format(record["order"], old["report"]))
    record["at"] = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    return record


def closed_review(root, trace_dir, unit):
    start, end = unit_in_writable_store(root, trace_dir, unit)
    if (not end or start["kind"] not in REVIEW_ROLES or end.get("kind") != start["kind"]
            or not end.get("dispositions")):
        raise TraceError("recheck requires a closed review with recorded dispositions")
    check_dispositions(start["kind"], end["dispositions"], allow_repeated_sources=True)
    return start["kind"], end["dispositions"]


def trace_recheck(args):
    root, _is_git = trace_root()
    holder = trace_holder(root)
    if not trace_state(holder, root)[0]:
        print("trace off")
        return 0
    trace_dir = holder / TRACE_DIR
    closed_review(root, trace_dir, args.unit)
    ignore_trace_dir(holder)
    with events_lock(trace_dir):
        kind, dispositions = closed_review(root, trace_dir, args.unit)
        previous = [e for e in read_events(trace_dir, args.unit.encode()) if e.get("id") == args.unit
                    and e.get("kind") == kind and e.get("type") == "recheck"]
        for event in previous:
            check_recheck(event)
        record = new_recheck(args, kind, dispositions, previous)
        if record:
            write_event_bytes(trace_dir, event_bytes(record))
    print("trace {} rechecked".format(args.unit))
    return 0


def event_time(event):
    """The recorded wall time, comparable across UTC offsets, or None when unknown."""
    value = event.get("at")
    if isinstance(value, str):
        with contextlib.suppress(ValueError):
            when = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
            if when.tzinfo is not None:
                return when
    return None


def committed_slice_status(root, commit, plan, revision, name, env):
    """Read the traced plan by ID in this commit, including after a rename or move between docs roots."""
    listing = os.fsdecode(trace_git(root, env, "ls-tree", "-r", "-z", "--name-only", commit))
    paths = [Path(p) for p in listing.split("\0") if p.rsplit("/", 1)[-1].startswith(plan + "-")]
    matches = [p for p in paths if FILE_RE.fullmatch(p.name) and
               (p.parts[-3:-1] == ("docs", "plans") or p.parts[-4:-1] == ("docs", "archived", "plans"))]
    if len(matches) != 1:
        return None
    path = matches[0]
    try:
        text = trace_git(root, env, "show", commit + ":" + path.as_posix()).decode("utf-8")
    except UnicodeDecodeError:
        return None
    doc = Doc(None, root / path, path.as_posix(), FILE_RE.fullmatch(path.name), False, text)
    if str(doc.revision) != revision:
        return None
    states = [state for heading, state in plan_slices(doc) if re.match(re.escape(name) + r"\b", heading)]
    return states[0] if len(states) == 1 else None


def slice_commit(root, unit):
    """Find an unambiguous status transition on the recorded plan revision after the slice's starting HEAD."""
    base = unit.start.get("head")
    plans = [target_reference(doc, "@r") for doc in unit.start.get("docs", []) if doc.startswith("P")]
    if not full_oid(base) or not unit.started or len(plans) != 1 or not plans[0]:
        return None
    plan, revision = plans[0]
    env = trace_env(GIT_NO_LAZY_FETCH="1", GIT_ALLOW_PROTOCOL="")
    boundary = unit.boundary or {}
    last = boundary.get("head")
    tips = [last] if full_oid(last) else ["--all", "HEAD"]
    since = trace_git(root, env, "log", "--no-patch", "--no-show-signature", "--no-notes", "--full-history",
                      "--reverse", "--topo-order", "--ancestry-path", "^" + base, *tips, "--format=%H %P %cI",
                      "--", ":(glob)**/docs/**/plans/" + plan + "-*.md").decode("ascii")
    states = {}

    def status(commit):
        if commit not in states:
            states[commit] = committed_slice_status(root, commit, plan, revision, unit.start["slice"], env)
        return states[commit]

    first = None
    limit = event_time(boundary)
    for line in since.splitlines():
        commit, *parents, at = line.split()
        when = event_time({"at": at})
        if not when or when < unit.started or (limit and when > limit):
            continue
        current = status(commit)
        if current not in ("done", "paused") or not parents:
            continue
        prior = [status(parent) for parent in parents]
        if any(old not in ("todo", "in-progress", "paused") or old == current for old in prior):
            continue
        if first is None:
            first = {"commit": commit, "at": at}
        elif git(root, "merge-base", "--is-ancestor", first["commit"], commit, env=env) is None:
            return None  # Independent branches completed the same slice.
    return first


class HistoryUnit:
    """A start paired with its own store's end and archives."""

    def __init__(self, start, trace_dir, store):
        self.start, self.trace_dir, self.store = start, trace_dir, store
        self.unit, self.kind = start["id"], start["kind"]
        self.started = event_time(start)
        self.end = self.boundary = None
        self.continuation = None
        self.rechecks = collections.defaultdict(list)
        self.conflicts = collections.defaultdict(list)

    def verify_rechecks(self, issues):
        """Bind imported reports to their authors and exclude contested ordinals regardless of import order."""
        if not self.rechecks:
            return
        reviewers = self.end["dispositions"]["reviewers"]
        models = {r.get("key", r["role"]): {r["model"]} for r in reviewers}
        unlisted = collections.defaultdict(set)
        for checks in self.rechecks.values():
            for event in checks:
                if event["reviewer"] not in models:
                    unlisted[event["reviewer"]].add(event["model"])
        models.update(unlisted)
        for source, checks in self.rechecks.items():
            reports, ordinals = collections.defaultdict(set), collections.defaultdict(set)
            trusted = []
            for event in checks:
                key = event["reviewer"]
                try:
                    recheck_model(key, event["model"], models[key])
                except TraceError:
                    issues["malformed"] += 1
                    continue
                trusted.append(event)
                reports[event["report"]].add(recheck_claim(event))
                if event["order"] is not None:
                    ordinals[event["order"]].add(event["report"])
            verified = {}
            for event in trusted:
                stem, order = event["report"], event["order"]
                if len(reports[stem]) > 1 or len(ordinals.get(order, ())) > 1:
                    issues["malformed"] += 1
                    self.conflicts[source].append(event)
                else:
                    verified.setdefault(stem, event)
            self.rechecks[source] = list(verified.values())

    def seconds(self):
        ended = event_time(self.end or self.boundary or {})
        if self.started and ended and ended >= self.started:
            return int((ended - self.started).total_seconds())
        return None

    def archive_status(self):
        if self.kind == "slice":
            return "unrequested"
        if not self.end:
            return "pending"
        if "archive" not in self.end:
            return "unknown"
        recorded = self.end["archive"]
        if recorded is None:
            return "unrequested"
        if recorded != "ok":
            return "none" if recorded == "none" else "failed ({})".format(recorded)
        directory = self.trace_dir / self.unit
        diagnostic = False
        try:
            if not directory.is_symlink():
                with os.scandir(str(directory)) as entries:
                    for entry in entries:
                        if entry.is_file(follow_symlinks=False):
                            if entry.name != "snapshot-error.txt":
                                return "ok (files present)"
                            diagnostic = True
        except (FileNotFoundError, NotADirectoryError):
            pass
        except OSError as error:
            return "ok (files unknown, {})".format(errno_name(error))
        return "ok (files missing, snapshot diagnostic only)" if diagnostic else "ok (files missing)"

    def report_status(self, stem):
        """Check only the exact regular report file in this unit's own archive."""
        directory = self.trace_dir / self.unit
        try:
            if not directory.is_symlink() and stat.S_ISREG((directory / (stem + ".md")).lstat().st_mode):
                return "present"
        except (FileNotFoundError, NotADirectoryError):
            pass
        except OSError as error:
            return "unknown ({})".format(errno_name(error))
        return "missing"

    def row(self):
        end = self.end or {}
        seconds = self.seconds()
        wall = "{}s".format(seconds) if seconds is not None else "unknown"
        ended = end["at"] if event_time(end) else "unknown"
        outcome = (end.get("outcome") or "unknown") if self.end else "open (missing end)"
        detail = " store=" + self.store if self.store else ""
        if self.kind == "code-review":
            base = self.start.get("base")
            detail += " base=" + (base if full_oid(base) else "unknown")
        if self.start.get("continues"):
            detail += " continues=" + self.start["continues"]
        if self.kind in REVIEW_ROLES and outcome == "handoff":
            detail += " coverage=partial continuation=" + (self.continuation or "none")
        if self.kind == "slice":
            detail += " slice=" + (self.start.get("slice") or "unknown")
            outcome = "implicit" if self.boundary else "open"
            if self.boundary:
                if "commit" in self.boundary:
                    outcome, ended = "committed", self.boundary["at"]
                    detail += " commit=" + self.boundary["commit"]
                else:
                    ended = "by " + self.boundary["at"] if event_time(self.boundary) else "unknown"
                    if seconds is not None:
                        wall = "<={}s (upper bound)".format(seconds)
        return ("{} {} parent={} docs={} started={} ended={} outcome={} wall={} archive={}{}"
                .format(self.unit, self.kind, self.start.get("parent") or "none",
                        " ".join(self.start.get("docs") or []) or "none", self.start["at"] if self.started else "unknown",
                        ended, outcome, wall, self.archive_status(), detail))

    def print_rechecks(self, source, first):
        checks = self.rechecks[source]
        ordered = sorted((e for e in checks if e["order"] is not None), key=lambda e: e["order"])
        unordered = [e for e in checks if e["order"] is None]
        latest = first
        for heading, group in (("", ordered), ("    unordered rechecks:", unordered)):
            if heading and group:
                print(heading)
            for event in group:
                verdict = "{result} reviewer={reviewer} snapshot={snapshot} model={model}".format(**event)
                print("      recheck order={} result={} report={} archive={}".format(
                    event["order"] or "unknown", verdict, event["report"], self.report_status(event["report"])))
        if ordered:
            last = ordered[-1]
            latest = "{result} reviewer={reviewer} snapshot={snapshot} model={model}".format(**last)
            print("    highest verified order={} result={}".format(last["order"], latest))
        if unordered:
            latest = "unknown (unordered evidence)"
        for event in self.conflicts[source]:
            print("    conflicting recheck report={} order={}".format(event["report"], event["order"] or "unknown"))
            if not ordered or event["order"] is None or event["order"] >= ordered[-1]["order"]:
                latest = "unknown (conflicting evidence)"
        print("    latest=" + latest)

    def print_review(self):
        """Report the evidence this review recorded; a legacy aggregate does not identify any confirmer."""
        oid = (self.end or {}).get("review_input")
        print("  review_input=" + (oid if full_oid(oid) else "unknown"))
        if not self.end:
            print("  dispositions=pending")
            return
        dispositions = self.end.get("dispositions")
        if not dispositions:
            print("  dispositions=unknown")
            return
        for reviewer in dispositions["reviewers"]:
            print("  reviewer {} model={} id={} targets={}".format(
                reviewer.get("key", reviewer["role"]), reviewer["model"], reviewer["id"] or "unknown",
                ", ".join(reviewer.get("targets", [])) or "unknown"))
        for finding in dispositions["findings"]:
            axis = " axis=" + finding["axis"] if "axis" in finding else ""
            print("  finding {} severity={} disposition={}{}".format(", ".join(finding["by"]), finding["severity"],
                                                                     finding["disposition"], axis))
            verdict = finding.get("confirmed", "unknown")
            confirmations = finding.get("confirmations", [])
            if confirmations:
                print("    first confirmation=" + verdict)
                for item in confirmations:
                    print("      confirmation={} reviewer={} snapshot={}".format(
                        item["result"], item["reviewer"], item["snapshot"] or "unknown"))
                authors = ", ".join("reviewer={} snapshot={}".format(c["reviewer"], c["snapshot"] or "unknown")
                                    for c in confirmations if c["result"] == verdict)
            else:
                authors = "reviewer=unknown snapshot=unknown"
                print("    first confirmation={} {}".format(verdict, authors))
            self.print_rechecks(finding["by"][0], "{} {}".format(verdict, authors))
        print("  new blockers={}".format(dispositions["new_blockers"]))


def history_events(trace_dir, issues):
    """Yield usable unit records, counting bad lines. A damaged disposition still leaves the end boundary usable."""
    for event, problem in event_lines(trace_dir):
        if problem:
            issues[problem] += 1
            continue
        action = event.get("type")
        if action == "manifest":
            continue
        if action not in ("start", "end", "recheck"):
            issues["unsupported"] += 1
            continue
        unit = event.get("id")
        docs = event.get("docs") or []
        parent, continues, slice_name = event.get("parent"), event.get("continues"), event.get("slice")
        if (not isinstance(unit, str) or not UNIT_RE.fullmatch(unit) or event.get("kind") not in TRACE_KINDS
                or any(link is not None and (not isinstance(link, str) or not UNIT_RE.fullmatch(link))
                       for link in (parent, continues))
                or (continues is not None and (action != "start" or event["kind"] not in REVIEW_ROLES))
                or (slice_name is not None and (not isinstance(slice_name, str) or not SLICE_RE.fullmatch(slice_name)))
                or (event["kind"] == "slice" and (action != "start" or parent is None or slice_name is None))
                or not isinstance(docs, list) or not all(isinstance(doc, str) for doc in docs)):
            issues["malformed"] += 1
            continue
        if action == "recheck":
            try:
                check_recheck(event)
            except TraceError:
                issues["malformed"] += 1
                continue
        if action == "end" and event.get("dispositions") is not None:
            try:
                if event["kind"] not in REVIEW_ROLES:
                    raise TraceError("dispositions on a non-review unit")
                check_dispositions(event["kind"], event["dispositions"], allow_repeated_sources=True)
            except TraceError:
                issues["malformed"] += 1
                event["dispositions"] = None
        yield event


def history_units(trace_dir, store):
    units, ends, open_slices = {}, {}, {}
    rechecks = []
    issues = collections.Counter()
    for event in history_events(trace_dir, issues):
        action, unit = event["type"], event["id"]
        if action == "recheck":
            rechecks.append(event)
            continue
        parent = event.get("parent") if action == "start" else unit
        previous = open_slices.pop(parent, None) if action == "start" or event["kind"] == "implement" else None
        if previous:
            previous.boundary = event
        if action == "start":
            units[unit] = HistoryUnit(event, trace_dir, store)
            if event["kind"] == "slice":
                open_slices[parent] = units[unit]
        else:
            ends[unit, event["kind"]] = event
    for unit in units.values():
        unit.end = ends.pop((unit.unit, unit.kind), None)
        predecessor = units.get(unit.start.get("continues"))
        if predecessor:
            predecessor.continuation = unit.unit
    orphans = list(ends.values())
    for event in rechecks:
        unit = units.get(event["id"])
        if unit and unit.kind == event["kind"] and unit.end and unit.end.get("dispositions"):
            with contextlib.suppress(TraceError):
                source = finding_source(unit.end["dispositions"], event["finding"])
                unit.rechecks[source].append(event)
                continue
        orphans.append(event)
    for unit in units.values():
        unit.verify_rechecks(issues)
    return list(units.values()), orphans, issues


def trace_history(args):
    root, is_git = trace_root()
    units, orphans, skipped = [], [], collections.Counter()
    for store, trace_dir in history_stores(root):
        found, unmatched, bad = history_units(trace_dir, store)
        units.extend(found)
        orphans.extend((store, event) for event in unmatched)
        skipped.update(bad)
    if args.unit:
        units = [unit for unit in units if unit.unit == args.unit]
        if not units:
            raise TraceError("{} names no unit".format(args.unit))
        if len(units) > 1:
            raise TraceError("{} is ambiguous (main and worktree stores)".format(args.unit))
    if not units:
        print("no traced units")
    counts, wall = collections.Counter(), collections.Counter()
    for unit in sorted(units, key=lambda u: (u.started is None, u.started, u.unit)):
        if is_git and unit.kind == "slice":
            with contextlib.suppress(SnapshotSkip):  # An unavailable Git object leaves only the event boundary.
                unit.boundary = slice_commit(root, unit) or unit.boundary
        print(unit.row())
        if args.unit and unit.kind in REVIEW_ROLES:
            unit.print_review()
        counts[unit.kind] += 1
        if unit.end or (unit.boundary and "commit" in unit.boundary):
            wall[unit.kind] += unit.seconds() or 0
    if units and not args.unit:
        print("By kind (a parent's wall time includes its children):")
        for kind in sorted(counts):
            print("  {}: {}, {} measured wall seconds".format(kind, counted(counts[kind], "unit", "units"), wall[kind]))
    if not args.unit:
        orphan_rechecks = 0
        for store, event in orphans:
            finding = ""
            if event["type"] == "recheck":
                finding = " finding={}".format(event.get("finding", "unknown"))
                orphan_rechecks += 1
            print("orphan {} {} {}{}{}".format(event["type"], event["id"], event["kind"], finding,
                                              " store=" + store if store else ""))
        if orphan_rechecks:
            print(counted(orphan_rechecks, "orphan recheck", "orphan rechecks"))
    if skipped:
        print("event line issues: {} malformed, {} unsupported".format(skipped["malformed"], skipped["unsupported"]))
    return 0


def trace_status(args):
    root, _is_git = trace_root()
    holder = trace_holder(root)
    print(trace_state(holder, root)[1])
    now = datetime.datetime.now(datetime.timezone.utc)
    since = (now - datetime.timedelta(hours=24)).strftime(UNIT_TIME_FORMAT)
    events = read_events(holder / TRACE_DIR,
                         *{prefix.encode() for prefix in (since[:9], now.strftime(UNIT_TIME_FORMAT)[:9])})
    ended = {event.get("id") for event in events if event.get("type") == "end"}
    units = [event for event in events if event.get("type") == "start" and event.get("kind") != "slice"
             and UNIT_RE.match(event.get("id", "")) and event["id"] >= since and event["id"] not in ended]
    units.sort(key=lambda event: event["id"], reverse=True)
    conversation = trace_host()[1]
    print("open units started in the last 24 hours, newest first:" if units
          else "no open units started in the last 24 hours")
    for event in units:
        docs = "".join(" " + doc for doc in event.get("docs") or [])
        mine = " (this conversation)" if conversation and event.get("conversation") == conversation else ""
        print("  {} {}{} started {}{}".format(event["id"], event.get("kind"), docs, event.get("at"), mine))
    print("\n".join(snapshot_summary(holder / TRACE_DIR)))
    return 0


def trace_switch(args):
    root, _is_git = trace_root()
    if args.here:
        holder = trace_holder(root)
        off = holder / TRACE_DIR / "off"
        if args.action == "off":
            ignore_trace_dir(holder)
            off.parent.mkdir(parents=True, exist_ok=True)
            off.touch()
        else:
            off.unlink(missing_ok=True)
    else:
        switch = trace_switch_path()
        if args.action == "on":
            switch.parent.mkdir(parents=True, exist_ok=True)
            switch.touch()
            print(TRACE_NOTICE)
        else:
            switch.unlink(missing_ok=True)
    print(trace_state(trace_holder(root), root)[1])
    return 0


def counted(n, one, many):
    return "{} {}".format(n, one if n == 1 else many)


def day_count(text):
    """`--days N`, a whole number of days, 0 or more."""
    try:
        days = int(text)
    except ValueError:
        days = -1
    if days < 0:
        raise argparse.ArgumentTypeError("N is a whole number of days, 0 or more, not {}".format(text))
    return days


def stale(name, prefix, cutoff):
    """Whether `name` is `prefix` followed by the id of a unit started before `cutoff`, a time in the form ids begin
    with; ids sort by their start time."""
    unit = name[len(prefix):]
    return name.startswith(prefix) and bool(UNIT_RE.match(unit)) and unit[:16] < cutoff


def prune_git(trace_dir, *args, data=None):
    """Run `git *args` in the snapshot repository and return its output; a failure is a trace error naming the Git
    command and how it failed."""
    try:
        return snapshot_git(trace_dir, trace_env(), *args, data=data)
    except SnapshotSkip as failed:
        raise TraceError(failed.reason)


def prune_snapshots(trace_dir, cutoff, prefix="refs/trace/"):
    """Delete the snapshot refs under `prefix` whose ids were made before `cutoff`; return how many went."""
    refs = prune_git(trace_dir, "for-each-ref", "--format=%(refname)", prefix).decode().split()
    old = [ref for ref in refs if stale(ref, prefix, cutoff)]
    if old:
        prune_git(trace_dir, "update-ref", "--stdin", data="".join("delete {}\n".format(ref) for ref in old).encode())
    return len(old)


def remove_stale(directory, prefix, cutoff):
    """Remove the entries of `directory` named `prefix` and the id of a unit started before `cutoff`, a directory with
    what it holds and a symlink without its target; return how many went."""
    try:
        with os.scandir(str(directory)) as entries:
            found = [entry for entry in entries if stale(entry.name, prefix, cutoff)]
    except FileNotFoundError:
        return 0
    for entry in found:
        if entry.is_dir(follow_symlinks=False):
            remove_tree(entry.path)
        else:
            with contextlib.suppress(OSError):
                os.unlink(entry.path)
    return sum(not os.path.lexists(entry.path) for entry in found)


def trace_prune(args):
    """Prune under snapshot.lock whenever the snapshot repository exists, so that no start's snapshot can reuse an
    object while the deletions and gc run."""
    trace_dir = trace_holder(trace_root()[0]) / TRACE_DIR
    now = datetime.datetime.now(datetime.timezone.utc)
    cutoff = (now - datetime.timedelta(days=args.days)).strftime(UNIT_TIME_FORMAT)
    hour_ago = (now - datetime.timedelta(hours=1)).strftime(UNIT_TIME_FORMAT)
    with contextlib.ExitStack() as held:
        # A review end holds events.lock from archive selection through its ref and event publication.
        if (trace_dir / "events.lock").exists():
            held.enter_context(events_lock(trace_dir))
        repo = (trace_dir / ".git").is_dir()
        if repo:
            held.enter_context(file_lock(trace_dir / "snapshot.lock", TRACE_LOCK_WAIT,
                                         TraceError("timed out waiting for snapshot.lock")))
        snapshots = prune_snapshots(trace_dir, cutoff) if repo else 0
        if repo:
            prune_snapshots(trace_dir, cutoff, "refs/review-input/")
        archives = remove_stale(trace_dir, "", cutoff)
        copies = remove_stale(trace_dir / ".git", "index-", hour_ago) if repo else 0
        builds = remove_stale(trace_dir, ".init-", hour_ago)
        print("removed {} and {} of units started more than {} ago".format(
            counted(snapshots, "snapshot", "snapshots"), counted(archives, "archive", "archives"),
            counted(args.days, "day", "days")))
        print("removed {} and {} left by interrupted starts".format(
            counted(copies, "index copy", "index copies"), counted(builds, "build directory", "build directories")))
        if repo:
            prune_git(trace_dir, "gc", "--prune=1.hour.ago", "--quiet")
    print(snapshot_line(trace_dir))
    return 0


def cmd_trace(args):
    try:
        return args.func(args)
    except TraceError as error:
        print("trace error: {}".format(error))
    except Exception as error:  # a failed call never stops the work
        print("trace error: {}: {}".format(type(error).__name__, error))
    return 0


# ---------------------------------------------------------------- review snapshots

def expire_review_snapshots(snapshot_dir, now):
    """Delete, best-effort, the review snapshots taken more than REVIEW_SNAPSHOT_DAYS ago and what interrupted calls
    left more than an hour ago."""
    hour_ago = (now - datetime.timedelta(hours=1)).strftime(UNIT_TIME_FORMAT)
    if (snapshot_dir / ".git").is_dir():
        with contextlib.suppress(TraceError):
            prune_snapshots(snapshot_dir, (now - datetime.timedelta(days=REVIEW_SNAPSHOT_DAYS))
                            .strftime(UNIT_TIME_FORMAT), "refs/snapshots/")
    with contextlib.suppress(OSError):
        remove_stale(snapshot_dir / ".git", "index-", hour_ago)
    with contextlib.suppress(OSError):
        remove_stale(snapshot_dir, ".init-", hour_ago)


@contextlib.contextmanager
def review_snapshot_store(root, is_git):
    if not is_git:
        raise SnapshotSkip("no-git")
    try:
        ignore_trace_dir(root)
    except OSError as error:
        raise SnapshotSkip("gitignore: " + errno_name(error))
    directory = root / REVIEW_SNAPSHOT_DIR
    with snapshot_lock(directory):
        now = datetime.datetime.now(datetime.timezone.utc)
        expire_review_snapshots(directory, now)
        yield directory, now


def cmd_snapshot(_args):
    """Record the work tree in the review snapshot repository and print the snapshot commit (D003#review-snapshots);
    exit 1 when no snapshot was recorded."""
    root, is_git = trace_root()
    try:
        with review_snapshot_store(root, is_git) as (directory, now):
            commit = take_snapshot(root, directory, new_id(now), None, "snapshots", borrow=True)
    except SnapshotSkip as failed:
        print("snapshot error: " + failed.reason)
        sys.stdout.flush()
        if failed.message:
            sys.stderr.write(failed.message.decode("utf-8", "replace"))
        return 1
    print(commit)
    return 0


def review_commit(directory, env, pin):
    """Resolve a literal hex object name in the review store, including its alternates. Reject any ambiguity
    before testing its object type, so Git's commit disambiguation cannot hide a colliding tree or blob."""
    if not isinstance(pin, str) or not re.fullmatch(r"[A-Fa-f0-9]{4,64}", pin):
        raise SnapshotSkip("expected a hexadecimal commit ID")
    matches = snapshot_git(directory, env, "rev-parse", "--disambiguate=" + pin.lower()).decode().split()
    if len(matches) != 1 or not matches[0].startswith(pin.lower()):
        raise SnapshotSkip("ambiguous or unavailable commit")
    if snapshot_git(directory, env, "cat-file", "-t", matches[0]).strip() != b"commit":
        raise SnapshotSkip("not a commit")
    return matches[0]


def pin_review_ref(root, directory, env, ref, now):
    if re.fullmatch(r"[0-9a-fA-F]+", ref):
        commit = review_commit(directory, env, ref)
    else:
        if not ref or ref.startswith("-") or "\n" in ref:
            raise SnapshotSkip("invalid commit reference")
        repo = directory if ref.startswith("refs/snapshots/") else root
        commit = trace_git(repo, env, "rev-parse", "--verify", ref + "^{commit}").decode().strip()
    snapshot_git(directory, env, "update-ref", "refs/snapshots/" + new_id(now), commit)
    return commit


def prepare_round_inputs(root, is_git, info, prepared):
    """Pin target and baseline independently, preserving each available input if the other cannot be recorded."""
    env, gaps = trace_env(**SNAPSHOT_IDENTITY), {}
    base = info["base"]
    if base == "none" and info["kind"] != "code-review":
        info["baseline"] = "none"
    needs_base = info["baseline"] is None and (base is not None or info["kind"] == "code-review")
    try:
        with review_snapshot_store(root, is_git) as (directory, now):
            objects, fmt = trace_git(root, env, "rev-parse", "--git-path", "objects", "--show-object-format").splitlines()
            git_dir = snapshot_repo(directory, new_id(now), env, sha256=fmt == b"sha256")
            borrow_objects(git_dir, os.path.abspath(root / os.fsdecode(objects)))
            try:
                if prepared is None:
                    info["snapshot"] = take_snapshot(root, directory, new_id(now), None, "snapshots", borrow=True)
                else:
                    info["snapshot"] = pin_review_ref(root, directory, env, prepared, now)
            except (SnapshotSkip, OSError) as error:
                gaps["snapshot.txt"] = str(error)
            if needs_base:
                if base in (None, "none"):
                    raise SnapshotSkip("code review requires a diff baseline")
                info["baseline"] = pin_review_ref(root, directory, env, base, now)
    except (SnapshotSkip, OSError) as error:
        if not info["snapshot"]:
            gaps.setdefault("snapshot.txt", str(error))
        if needs_base:
            gaps["baseline.txt"] = str(error)
    return gaps


def review_start(args):
    root, is_git = trace_root()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*(?:/followup-[1-9][0-9]*)?", args.topic):
        raise TraceError("invalid review topic")
    parent = root / REVIEW_ROUND_DIR / args.topic
    if parent.resolve() != parent:
        raise TraceError("review topic must lie in this checkout's review directory")
    base = "none" if args.kind == "gate" and args.base is None else args.base
    info = dict(kind=args.kind, tier=args.tier, targets=args.target, require=args.require, unit=args.unit,
                base=base, baseline=None, snapshot=None)
    check_round_declaration(info)
    gaps = prepare_round_inputs(root, is_git, info, args.snapshot)
    parent.mkdir(parents=True, exist_ok=True)
    path = Path(tempfile.mkdtemp(prefix="round-", dir=str(parent)))
    (path / "round.json").write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")
    for material in ("snapshot", "baseline"):
        if info[material] is not None:
            (path / (material + ".txt")).write_text(info[material] + "\n", encoding="ascii")
    warn_review_gaps(root, path, args.unit, gaps)
    print(path)
    return 0


def require_project_install():
    """End the command unless this canon.py was started by a path inside the project, found without running Git: the
    path passes through a directory that is the nearest at or above the working directory holding `.git`; outside
    Git, the working directory or a directory above it holding `AGENTS.md`. Links on the path stay unresolved, so a
    user install refuses and a project's link to it runs. Return the first of those directories, whose `AGENTS.md`
    records the project's version."""
    start = os.path.abspath(__file__)
    cwd = Path(os.getcwd())
    tops = [path for path in (cwd, *cwd.parents) if (path / ".git").exists()][:1] \
        or [cwd] + [path for path in cwd.parents if (path / "AGENTS.md").exists()]
    for path in Path(start).parents:
        for top in tops:
            with contextlib.suppress(OSError):
                if os.path.samefile(str(path), str(top)):
                    return tops[0]
    sys.exit("canon: canon runs only from an install inside the project, and this canon.py is {}; install canon in "
             "the project as https://github.com/BigTailFox/skills#install says, and remove a user install of canon "
             "with `npx skills remove -g`".format(start))


def require_project_version(top):
    """Compare CANON_VERSION with the version the canon block of `top`'s AGENTS.md records in its first `- Tool:`
    line: exit when the project needs a newer canon.py, and return the reminder to upgrade the project when it is set
    up for an older one or records none. None when they are equal, or without the file or a start marker with an end
    marker after it, where no check runs."""
    try:
        text = (top / "AGENTS.md").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    span = marker_span(text, AGENTS_START, AGENTS_END)
    if not span or span[1] is None:
        return None
    tool = next((line for line in text[span[0]:span[1]].split("\n") if line.startswith("- Tool:")), "")
    match = re.search(r"canon version (\d+) or later", tool)
    if not match:
        return "this project records no canon version; run `/canon-init` to upgrade it to version " + CANON_VERSION
    recorded = int(match.group(1))
    if int(CANON_VERSION) < recorded:
        sys.exit("canon: this project needs canon version {} or later, and this canon.py is version {}; install a "
                 "newer canon release as the canon block of AGENTS.md says".format(recorded, CANON_VERSION))
    if int(CANON_VERSION) > recorded:
        return "this project is set up for canon version {}; run `/canon-init` to upgrade it to version {}".format(
            recorded, CANON_VERSION)
    return None


def main(argv=None):
    parser = argparse.ArgumentParser(prog="canon.py", description="canon documentation system tool")
    parser.add_argument("--version", action="version", version="canon " + CANON_VERSION)
    sub = parser.add_subparsers(dest="command", required=True)

    def command(actions, name, help):
        return actions.add_parser(name, help=help, description=help)

    p = command(sub, "check", help="validate all docs; exit 1 on errors")
    p.add_argument("docs", nargs="*", metavar="ID|PATH",
                   help="report only the problems on these docs, each given by its id or the path of its file")
    p.add_argument("--fix", action="store_true",
                   help="apply mechanical fixes (refs, updated, implemented, as_built, indexes)")
    p.add_argument("--base", help="check all governing design IDs in new non-merge commits' Refs: lines. Also check "
                                  "this branch against a ref, e.g. origin/main: deleted docs, id "
                                  "collisions, revisions pending review and unfinished docs fail. Mark problems also "
                                  "present on that ref")
    p.add_argument("--staged", action="store_true",
                   help="check the staged tree, what `git commit` records, instead of the work tree")
    p.add_argument("--rev", metavar="REV", help="check the tree of commit REV instead of the work tree")
    p.set_defaults(func=cmd_check)

    p = command(sub, "commit-template", help="print a Git commit message with the staged change's design references")
    p.add_argument("--subject", default="", metavar="TEXT", help="one-line subject, left blank by default")

    p = command(sub, "embed", help="generate source blocks in live Markdown documents")
    select = p.add_mutually_exclusive_group()
    select.add_argument("docs", nargs="*", default=[], metavar="ID|PATH", help="a live document ID or Markdown path")
    select.add_argument("--source", metavar="FILE", help="select live documents embedding this source file")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="report stale or invalid source blocks without writing")
    mode.add_argument("--list", dest="list_only", action="store_true",
                      help="with --source, list matching documents without writing")
    p.set_defaults(func=cmd_embed)

    p = command(sub, "new", help="create a doc from its template with the next free id")
    p.add_argument("type", help="C D P R E I (or concept, design, plan, ...)")
    p.add_argument("slug", help="kebab-case file slug")
    p.add_argument("--title", help="title (default: the slug with spaces, capitalized)")
    p.add_argument("--root", "--r", help="project directory (with AGENTS.md); default: nearest to cwd")
    p.add_argument("--parent", help="top-level design to split, creates D00XA, D00XB, ...")
    p.add_argument("--from", dest="design", help="design a plan implements, required for plans; fills based_on")
    p.add_argument("--research", action="store_true", help="start an experiment with a Sources field for primary-source research")
    p.set_defaults(func=cmd_new)

    p = command(sub, "archive", help="set a terminal status, move to archived/, rewrite links")
    p.add_argument("id")
    p.add_argument("status", help="; ".join("{}: {}".format(letter, ", ".join(info["terminal"]))
                                            for letter, info in TYPES.items()))
    p.set_defaults(func=cmd_archive)

    p = command(sub, "status",
                help="move a doc's status forward, or an answered experiment back to running, and check the move")
    p.add_argument("id")
    p.add_argument("status", help="; ".join("{}: {}".format(letter, ", ".join(status_moves(letter)))
                                            for letter in TYPES))
    p.set_defaults(func=cmd_status)

    p = command(sub, "approvals", help="list pending L2 approvals or record a reviewed round")
    p.add_argument("gate", nargs="?", metavar="GATE", help="original gate topic, e.g. D001-r15 or P002-r1")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--start", nargs="+", metavar="ID@rN", help="record the initial round, including the gate's primary")
    mode.add_argument("--update", nargs="*", metavar="ID@rN", help="merge a follow-up or clear approved entries")
    mode.add_argument("--recover", nargs="*", metavar="ID@rN", help="rebuild from verified gate and follow-up history")
    p.add_argument("--retire", nargs="+", metavar="ID@rN", help="with --update, retire a superseded or moved target")
    p.set_defaults(func=cmd_approvals)

    p = command(sub, "init", help="set up canon in a repo or module (idempotent)")
    p.add_argument("--root", help="module directory to set up (default: repo root)")
    p.add_argument("--hook", action="store_true", help="install a git pre-commit hook running `check --staged`")
    p.set_defaults(func=cmd_init)

    p = command(sub, "adopt", help="turn an existing markdown file into a canon doc, keeping history and links")
    p.add_argument("file")
    p.add_argument("type", help="C D P R E I (or concept, design, plan, ...)")
    p.add_argument("--slug", help="kebab-case slug (default: from the file name)")
    p.add_argument("--title", help="title (default: the file's H1)")
    p.add_argument("--root", help="project directory (default: nearest AGENTS.md above the file)")
    p.set_defaults(func=cmd_adopt)

    p = command(sub, "rename", help="change a doc's file slug, the attachments named after it and, with --title, its "
                                    "title, and rewrite every link to it")
    p.add_argument("id")
    p.add_argument("slug", help="new kebab-case file slug")
    p.add_argument("--title", help="new title for the H1 and for link texts reading `<id>: <old title>`")
    p.set_defaults(func=cmd_rename)

    p = command(sub, "renumber", help="give a doc a new id, which its sub-designs follow, or a sub-design a new "
                                      "letter, and rewrite the links and references to them; only when `check` asks "
                                      "for it, for an id collision or a D000 in a module's docs")
    p.add_argument("target", help="doc id, or its path when the id is duplicated")
    p.add_argument("new", nargs="?", help="new id (default: next free)")
    p.add_argument("--base", help="the branch merged or rebased onto, e.g. origin/main: its ids stay taken, and "
                                  "what exists there belongs to the doc that exists there")
    p.set_defaults(func=cmd_renumber)

    p = command(sub, "index", help="regenerate docs/README.md and docs/archived/README.md indexes")
    p.add_argument("--staged", action="store_true",
                   help="first regenerate the staged tree's indexes from the staged docs and stage them")
    p.set_defaults(func=cmd_index)

    p = command(sub, "show", help="print a doc's outline, or one section with ID#slug")
    p.add_argument("ref", help="a doc id such as D003, or D003#slug for the section whose heading has that slug")
    p.set_defaults(func=cmd_show)

    p = command(sub, "find", help="search ids, titles, summaries, owns, modules and headings")
    p.add_argument("words", nargs="+")
    p.add_argument("--archived", action="store_true", help="include archived docs")
    p.set_defaults(func=cmd_find)

    p = command(sub, "which", help="list the designs whose `paths` govern the given files; `skill` for an installed "
                                   "skill file and `doc` for a project doc that no `paths` entry names exactly, "
                                   "`no design` for other files; `(missing)` after a file neither on disk nor in Git")
    p.add_argument("files", nargs="+")
    p.set_defaults(func=cmd_which)

    p = command(sub, "affected", help="designs and plans governing changed files (default: uncommitted)")
    p.add_argument("files", nargs="*", help="files to check instead of the changed ones")
    p.add_argument("--base", help="include changes since the merge base with this ref; ignored with files")
    p.set_defaults(func=cmd_affected)

    p = command(sub, "audit", help="report designs with unchecked code commits, known issues, idle open docs, due "
                                   "reviews, source areas no design covers, and designs D000 does not reach")
    p.add_argument("--days", type=int, default=30,
                   help="days without an update before an open doc other than a concept, active design or concluded "
                        "experiment is idle (default 30)")
    p.add_argument("--review-after", type=int, default=5, help="finished plans before a review is due (default 5)")
    p.add_argument("--review-commits", type=int, default=50,
                   help="code commits before a review is due (default 50)")
    p.set_defaults(func=cmd_audit)

    p = command(sub, "review", help="prepare and check a review round in this checkout")
    actions = p.add_subparsers(dest="action", required=True)
    t = command(actions, "start", help="pin initial inputs and print a fresh directory for all dispatches and reports")
    t.add_argument("topic", metavar="TOPIC", help="the gate or code review topic, optionally ending in /followup-N")
    t.add_argument("--kind", required=True, choices=tuple(REVIEW_ROLES))
    t.add_argument("--tier", required=True, choices=("L0", "L1", "L2"))
    t.add_argument("--target", action="append", default=[], metavar="ID@rN", help="initial design or plan revision")
    t.add_argument("--require", action="append", default=[], metavar="KEY", help="additional independent reviewer")
    t.add_argument("--base", metavar="REF", help="diff baseline, or none for a full-document gate; omit for mixed follow-ups")
    t.add_argument("--snapshot", metavar="COMMIT", help="prepared target commit (default: snapshot the current work tree)")
    t.add_argument("--unit", metavar="TRACE_ID", help="bind the new round's files to this trace unit and review kind")
    t.set_defaults(func=review_start)

    p = command(sub, "trace", help="record canon workflow units for skill telemetry; off unless `trace on` ran")
    actions = p.add_subparsers(dest="action", required=True)
    t = command(actions, "start", help="start a unit and print `trace <id>`")
    t.add_argument("kind", choices=TRACE_KINDS)
    t.add_argument("docs", nargs="*", metavar="DOC", help="ids of the docs the unit works on")
    t.add_argument("--parent", metavar="UNIT", help="id of the open unit this one runs inside")
    t.add_argument("--continues", metavar="UNIT", help="id of the handed-off review this one resumes")
    t.add_argument("--tier", choices=("L0", "L1", "L2"))
    t.add_argument("--slice", metavar="S<n>", help="the plan slice a slice unit builds")
    t.add_argument("--base", metavar="REF", help="the commit the unit's change starts from; the snapshot's parent "
                                                 "holds the tree of its merge base with HEAD")
    t.add_argument("--skill", metavar="DIR", help="directory of the SKILL.md being followed")
    t.add_argument("--model", metavar="ID", help="the session's model id")
    t.set_defaults(func=trace_start)
    t = command(actions, "end", help="end an open unit; a slice ends with its commit or the next start under its "
                                     "implement unit instead")
    t.add_argument("unit")
    t.add_argument("outcome", help="; ".join("{}: {}".format(kinds, ", ".join(outcomes)) for kinds, outcomes in
                                             [("other kinds", OUTCOMES)] + list(KIND_OUTCOMES.items())))
    t.add_argument("--to", choices=("L1", "L2", "plan"), help="the tier or plan an escalated unit needs")
    t.add_argument("--dir", metavar="DIR", help="archive this unit-bound round's direct regular files under .canon/; "
                                                "a legacy directory uses the unit's start time as its cutoff")
    t.add_argument("--input", metavar="FILE|-", help="a gate's, follow-up's or code review's dispositions as JSON, "
                                                     "from FILE or from stdin for -")
    t.set_defaults(func=trace_end)
    t = command(actions, "status", help="say whether tracing is on and why, and list the open units")
    t.set_defaults(func=trace_status)
    t = command(actions, "history", help="read the recorded history of all units or one unit, tracing on or off")
    t.add_argument("unit", nargs="?", metavar="UNIT")
    t.set_defaults(func=trace_history)
    t = command(actions, "recheck", help="record a targeted recheck of a closed review finding")
    t.add_argument("unit", metavar="UNIT")
    t.add_argument("finding", metavar="FINDING")
    t.add_argument("--reviewer", required=True, metavar="KEY")
    t.add_argument("--snapshot", required=True, metavar="OID")
    t.add_argument("--result", required=True, metavar="resolved|not-resolved")
    t.add_argument("--report", required=True, metavar="STEM")
    t.add_argument("--order", required=True, metavar="N|unknown")
    t.add_argument("--model", metavar="MODEL")
    t.set_defaults(func=trace_recheck)
    t = command(actions, "on", help="turn tracing on for this machine; --here deletes this checkout's off file")
    t.add_argument("--here", action="store_true",
                   help="only delete this checkout's off file; the machine switch stays as it is")
    t.set_defaults(func=trace_switch)
    t = command(actions, "off", help="turn tracing off for this machine; --here opts this checkout out")
    t.add_argument("--here", action="store_true",
                   help="only write this checkout's off file, opting it out; the machine switch stays as it is")
    t.set_defaults(func=trace_switch)
    t = command(actions, "prune", help="delete the snapshots and archives of units started more than N days ago, "
                                       "tracing on or off")
    t.add_argument("--days", type=day_count, required=True, metavar="N")
    t.set_defaults(func=trace_prune)

    command(sub, "snapshot", help="record the work tree, untracked files included, for a review's confirmation diff "
                                  "and print the snapshot commit; exit 1 when none was recorded")

    args = parser.parse_args(argv)
    args.version_notice = require_project_version(require_project_install())
    if args.version_notice and args.command not in ("check", "init"):
        print("canon: " + args.version_notice, file=sys.stderr)
    if args.command == "trace":
        return cmd_trace(args)
    if args.command == "review":
        try:
            return args.func(args)
        except (TraceError, SnapshotSkip, OSError) as error:
            print("review error: " + str(error), file=sys.stderr)
            return 1
    if args.command == "snapshot":
        return cmd_snapshot(args)
    if args.command == "commit-template":
        return cmd_commit_template(args)
    return args.func(check_repo(args) if args.command == "check" else Repo(), args)


if __name__ == "__main__":
    sys.exit(main())
