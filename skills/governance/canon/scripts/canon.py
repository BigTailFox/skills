#!/usr/bin/env python3
"""Checker and helper CLI for the canon documentation system.

Single file, Python 3.8+ standard library only. Run `canon.py -h` for commands.
"""

import argparse
import contextlib
import datetime
import errno
import hashlib
import json
import os
import re
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

CANON_VERSION = "12"

TYPES = {
    "C": {"dir": "concepts", "active": ("draft",), "terminal": ("adopted", "dropped"),
          "sections": ("Motivation", "Ideas", "Open questions")},
    "D": {"dir": "designs", "active": ("draft", "accepted", "active"), "terminal": ("superseded", "retired"),
          "sections": ("Goals", "Spec", "Decisions")},
    "P": {"dir": "plans", "active": ("draft", "accepted", "in-progress"), "terminal": ("done", "abandoned"),
          "sections": ("Current state", "Slices", "Notes", "Log")},
    "R": {"dir": "reviews", "active": ("open",), "terminal": ("closed",),
          "sections": ("Scope", "Findings")},
    "E": {"dir": "experiments", "active": ("planned", "running"), "terminal": ("concluded",),
          "sections": ("Question", "Setup", "Results", "Conclusion")},
    "I": {"dir": "investigations", "active": ("open",), "terminal": ("resolved",),
          "sections": ("Symptom", "Reproduction", "Analysis", "Resolution")},
}
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
OPTIONAL_FIELDS = {"D": ("reviewed", "reviewers", "implemented"), "P": ("reviewed", "reviewers")}
LIST_FIELDS = {"modules", "refs", "owns", "paths", "based_on", "reviewers"}
INT_FIELDS = {"revision", "reviewed", "implemented"}
SEVERITIES = ("blocker", "major", "minor")
DISPOSITIONS = ("open", "fixed", "moved", "declined")
SLICE_STATUSES = ("todo", "in-progress", "done", "paused")
SETUP_LABELS = ("Commit", "Environment", "Command")
SOURCES_LABEL = "Sources"
RESOLUTION_LABELS = ("Root cause", "Fix", "Verification")

MAX_DOC_LINES = 500
MAX_AGENTS_LINES = 150
MAX_SUMMARY = 160

FILE_RE = re.compile(r"^([CDPREI])(\d{3,})([A-Z]?)-([a-z0-9]+(?:-[a-z0-9]+)*)\.md$")
FULL_ID_RE = re.compile(r"^([CDPREI])(\d{3,})([A-Z]?)$")
REF_ARG_RE = re.compile(r"^([CDPREI]\d{3,}[A-Z]?)(?:[#§](.+))?$")
REF_TEXT_RE = re.compile(r"^([CDPREI]\d{3,}[A-Z]?)(?:§([^:]+))?: \S")
BASED_ON_RE = re.compile(r"^(D\d{3,}[A-Z]?)@r(\d+)$")
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
LINK_RE = re.compile(r"(!?)\[([^\]]*)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
FENCE_RE = re.compile(r"^\s*(```|~~~)")
INLINE_CODE_RE = re.compile(r"`[^`]*`")
STATUS_LINE_RE = re.compile(r"^\s*(?:-\s+)?Status:\s*(.*?)\s*$")
MOVED_RE = re.compile(r"(?m)^(\s*\|\s*)([^|\s]+)(\s*\|.*\|\s*moved\s+)([CDPREI]\d{3,}[A-Z]?)(\s*\|\s*)$")
LABEL_RE = re.compile(r"^\s*(?:-\s+)?([A-Za-z ]+?):\s*(.*?)\s*$")
GUIDANCE = "<!-- canon:"
INDEX_START = "<!-- canon:index:start -->"
INDEX_END = "<!-- canon:index:end -->"
AGENTS_START = "<!-- canon:agents:start -->"
AGENTS_END = "<!-- canon:agents:end -->"
AGENTS_BLOCK = AGENTS_START + """
## Docs

This repo follows the canon documentation system (`canon` skill). Engineering docs live in `docs/` and in module `docs/` directories; start at [docs/README.md](docs/README.md).

- Tool: `python3 {script}` from the repo root (`-h` lists commands). Run `check --fix` before committing and after every merge or rebase.
- When a change may alter behavior or standards a design specifies, run `which <file>` and read the governing sections with `show D00X#slug` first.
- State each change's tier (L0, L1, L2) before starting. Designs and plans pass the review gate defined by the `canon` skill.
- Skip `docs/archived/` unless researching history.
""" + AGENTS_END
SUB_AGENTS = "Module docs: [docs/README.md](docs/README.md). The repo root `AGENTS.md` defines the docs rules.\n"
DOCS_README = """# Docs

Engineering docs managed with canon. Designs (D) are the source of truth; plans (P) record implementation; concepts (C), reviews (R), experiments (E) and investigations (I) cover the rest. Search from the repo root with `python3 {script} find <words>`.

## Index
"""
GITATTRIBUTES = ("**/docs/README.md merge=union", "**/docs/archived/README.md merge=union")
LOCAL_DIR = ".canon/"
DOCS_PATHSPEC = ":(glob)**/docs/**/*.md"

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

<!-- canon: One row per finding with IDs {id}-F1, {id}-F2, ... Severity: blocker, major, minor. Disposition: open, fixed <commit>, moved <doc ID>, declined <reason>. -->
""",
    "E": """
## Question

<!-- canon: The question or hypothesis, and what result would answer it. -->

## Setup

- Commit:
- Environment:
- Command:

<!-- canon: Fill Commit, Environment and Command for a run. For research, replace them with `- Sources:` and the primary sources consulted, one per indented line. -->

## Results

<!-- canon: Measurements or findings, each linked to its raw data or cited source. -->

## Conclusion

<!-- canon: The answer, and the design section or decision it was absorbed into. -->
""",
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


# ---------------------------------------------------------------- helpers

def today():
    return datetime.date.today().isoformat()


def posix_rel(path, start):
    return os.path.relpath(str(path), str(start)).replace(os.sep, "/")


def path_id(rel):
    """The id of a doc file, given its path from the repo root; None for any other file."""
    match = FILE_RE.match(rel.rsplit("/", 1)[-1])
    if match and (rel.startswith("docs/") or "/docs/" in rel):
        return match.group(1) + match.group(2) + match.group(3)
    return None


def git(cwd, *args):
    try:
        result = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True)
    except FileNotFoundError:
        return None
    return result.stdout if result.returncode == 0 else None


def parse_value(key, raw):
    if key in LIST_FIELDS and raw.startswith("[") and raw.endswith("]"):
        return [item.strip().strip("'\"") for item in raw[1:-1].split(",") if item.strip()]
    if key in INT_FIELDS and raw.isdigit():
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
    lines = text.split("\n")
    end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    rendered = "{}: {}".format(key, render_value(value))
    for i in range(1, end):
        if re.match(r"^{}:".format(re.escape(key)), lines[i]):
            lines[i] = rendered
            break
    else:
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
    for i in range(start, len(lines)):
        match = FENCE_RE.match(lines[i])
        if match:
            if fence is None:
                fence = match.group(1)
            elif fence == match.group(1):
                fence = None
            continue
        if fence is None:
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


def iter_links(lines, start=0):
    for i, line in code_mask(lines, start):
        masked = INLINE_CODE_RE.sub(lambda m: " " * len(m.group(0)), line)
        for match in LINK_RE.finditer(masked):
            yield i, match


def glob_regex(pattern):
    p = pattern.strip()
    while p.startswith("./"):
        p = p[2:]
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
    return re.compile(out + r"(?:/.*)?$")


def git_pathspec(project_rel, pattern):
    p = pattern.strip()
    while p.startswith("./"):
        p = p[2:]
    if p.endswith("/"):
        p += "**"

    def spec(*parts):
        return ":(glob)" + "/".join(x for x in parts if x)

    if any(c in p for c in "*?["):
        return [spec(project_rel, p)]
    return [spec(project_rel, p), spec(project_rel, p, "**")]


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


# ---------------------------------------------------------------- model

class Root:
    def __init__(self, repo, rel):
        self.rel = rel
        self.project = repo.root / rel if rel else repo.root
        self.docs = self.project / "docs"
        self.docs_rel = rel + "/docs" if rel else "docs"
        self.label = rel or "."


class Doc:
    def __init__(self, root, path, rel, match, archived):
        self.root, self.path, self.rel, self.archived = root, path, rel, archived
        self.type = match.group(1)
        self.digits, self.suffix, self.slug = match.group(2), match.group(3), match.group(4)
        self.number = int(self.digits)
        self.id = self.type + self.digits + self.suffix
        self.text = path.read_text(encoding="utf-8")
        self.lines = self.text.split("\n")
        self.fm, self.fm_end, self.fm_bad = parse_frontmatter(self.lines)
        self.headings = scan_headings(self.lines, self.fm_end + 1)
        h1 = next((h for h in self.headings if h.level == 1), None)
        prefix = self.id + ": "
        self.title = h1.text[len(prefix):].strip() if h1 and h1.text.startswith(prefix) else ""

    def get(self, key, default=None):
        return (self.fm or {}).get(key, default)

    @property
    def status(self):
        return self.get("status", "?")

    @property
    def revision(self):
        value = self.get("revision")
        return value if isinstance(value, int) else 0

    def as_list(self, key):
        value = self.get(key, [])
        return value if isinstance(value, list) else []

    def section(self, name):
        for idx, h in enumerate(self.headings):
            if h.level == 2 and h.text == name:
                end = next((x.line for x in self.headings[idx + 1:] if x.level <= 2), len(self.lines))
                return self.lines[h.line + 1:end]
        return None

    def labels(self, section_name):
        """Map `- Label: value` lines to their values; indented lines below a label extend its value."""
        out, last = {}, None
        for line in self.section(section_name) or []:
            indented = line[:1].isspace()
            match = LABEL_RE.match(line.replace("*", ""))
            if match and not (indented and last):
                last = match.group(1).strip()
                out[last] = match.group(2)
            elif last and indented and line.strip():
                out[last] = (out[last] + " " + line.strip()).strip()
            elif line.strip():
                last = None
        return out

    def sort_key(self):
        return (TYPE_ORDER.index(self.type), self.number, self.suffix)


class Repo:
    def __init__(self, start=None):
        start = Path(start or os.getcwd())
        top = git(start, "rev-parse", "--show-toplevel")
        self.is_git = top is not None
        self.root = Path(os.path.realpath(top.strip() if top else str(start)))
        self.has_head = self.is_git and git(self.root, "rev-parse", "--verify", "-q", "HEAD") is not None
        self.files = self._list_files()
        parents = [f.rsplit("/", 1)[0] if "/" in f else "" for f in self.files if f.rsplit("/", 1)[-1] == "AGENTS.md"]
        self.roots = [Root(self, rel) for rel in parents]
        self.docs, self.problems, self.attachments = [], [], []
        self.index_files, self.scope_md = [], []
        self.by_id, self.by_path = {}, {}
        self._slug_cache = {}
        self._scan()

    def _list_files(self):
        if self.is_git:
            out = git(self.root, "ls-files", "-z", "-co", "--exclude-standard") or ""
            return sorted({f for f in out.split("\0") if f and (self.root / f).is_file()})
        found = []
        for dirpath, dirnames, filenames in os.walk(str(self.root)):
            dirnames[:] = [d for d in dirnames if not d.startswith(".") and d not in ("node_modules", "venv")]
            for name in filenames:
                found.append(posix_rel(Path(dirpath) / name, self.root))
        return sorted(found)

    def problem(self, level, rel, msg, line=None, fix=None):
        self.problems.append((level, rel, line, msg, fix))

    def _scan(self):
        for root in self.roots:
            agents = root.project / "AGENTS.md"
            self.scope_md.append(agents)
            if not root.docs.is_dir():
                continue
            prefix = root.docs_rel + "/"
            reported = set()
            for rel in self.files:
                if not rel.startswith(prefix):
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
                    continue
                letter = CATEGORY_DIRS.get(parts[0])
                if letter is None:
                    key = (root.docs_rel, archived, parts[0])
                    if key not in reported:
                        reported.add(key)
                        where = root.docs_rel + ("/archived/" if archived else "/") + parts[0]
                        self.problem("ERROR", where, "unknown entry; allowed: README.md, archived/, guides/, assets/, "
                                     + ", ".join(i["dir"] + "/" for i in TYPES.values()))
                    continue
                id_match = FULL_ID_RE.match(parts[1]) if len(parts) >= 3 else None
                if id_match and id_match.group(1) == letter:
                    self.attachments.append((root, archived, parts[1], rel))
                    continue
                match = FILE_RE.match(parts[-1]) if len(parts) == 2 else None
                if not match or match.group(1) != letter or (match.group(3) and letter != "D") \
                        or str(int(match.group(2))).zfill(3) != match.group(2):
                    self.problem("ERROR", rel, "invalid doc path; expected {}/{}NNN-kebab-slug.md{}".format(
                        TYPES[letter]["dir"], letter, " (D may add one A-Z suffix)" if letter == "D" else ""))
                    continue
                doc = Doc(root, path, rel, match, archived)
                self.docs.append(doc)
                if doc.id in self.by_id:
                    self.problem("ERROR", rel, "duplicate id {}, also {}; run `canon.py renumber <path> --base <ref>` "
                                 "on the doc this branch added, with the branch it merged or rebased onto"
                                 .format(doc.id, self.by_id[doc.id].rel))
                else:
                    self.by_id[doc.id] = doc
                self.by_path[path] = doc
        self.docs.sort(key=Doc.sort_key)

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
            lines = path.read_text(encoding="utf-8").split("\n")
            self._slug_cache[path] = {h.slug for h in scan_headings(lines)}
        return self._slug_cache[path]

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
            sys.exit("canon: unknown ref " + ref)
        return {rel for rel in listing.split("\0") if rel}

    def tree_ids(self, ref):
        """Map id -> path for the doc files in a commit's tree."""
        ids = {}
        for rel in sorted(self.tree_files(ref)):
            doc_id = path_id(rel)
            if doc_id:
                ids.setdefault(doc_id, rel)
        return ids

    def deleted_docs(self, base=None):
        """Doc files deleted (not renamed) in uncommitted changes, and on this branch since `base`."""
        if not self.has_head:
            return []
        ranges = [["HEAD"]] + ([[base + "...HEAD"]] if base else [])
        deleted = set()
        for rng in ranges:
            out = git(self.root, "diff", "-z", "-M", "--name-status", "--diff-filter=D", *rng, "--", DOCS_PATHSPEC)
            if out is None:
                sys.exit("canon: cannot diff against " + rng[0])
            fields = out.split("\0")
            deleted |= {path for status, path in zip(fields[::2], fields[1::2]) if status.startswith("D")}
        return sorted(deleted)

    def project_files(self, root):
        prefix = root.rel + "/" if root.rel else ""
        return [f[len(prefix):] for f in self.files if f.startswith(prefix)]

    def changed_files(self, base=None):
        if not self.has_head:
            return list(self.files)
        outs = [git(self.root, "diff", "-z", "--name-only", "HEAD"),
                git(self.root, "ls-files", "-z", "-o", "--exclude-standard")]
        if base:
            outs.append(git(self.root, "diff", "-z", "--name-only", base + "...HEAD"))
            if outs[-1] is None:
                sys.exit("canon: cannot diff against {}".format(base))
        return sorted({f for out in outs for f in (out or "").split("\0") if f})

    def designs_for(self, abs_path):
        hits = []
        for doc in self.docs:
            if doc.type != "D" or doc.archived:
                continue
            rel = posix_rel(abs_path, doc.root.project)
            if rel.startswith(".."):
                continue
            if any(glob_regex(p).match(rel) for p in doc.as_list("paths")):
                hits.append(doc)
        return hits


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
            parts = ["- [{}: {}]({})".format(d.id, d.title or "?", posix_rel(d.path, base_dir)),
                     d.status, str(d.get("summary", "") or "?")]
            if d.as_list("owns"):
                parts.append("owns: " + ", ".join(d.as_list("owns")))
            if d.as_list("modules"):
                parts.append("modules: " + ", ".join(d.as_list("modules")))
            lines.append(" · ".join(parts))
        lines.append("")
    body = "\n".join(lines).strip() or "No documents."
    return INDEX_START + "\n\n" + body + "\n\n" + INDEX_END


def expected_indexes(repo):
    """Return {path: expected_text} for every docs root."""
    out = {}
    for root in repo.roots:
        if not root.docs.is_dir():
            continue
        readme = root.docs / "README.md"
        current = readme.read_text(encoding="utf-8") if readme.is_file() else None
        block = index_block(repo, root, False, root.docs)
        if current is None:
            out[readme] = "# Docs\n\n" + block + "\n"
        elif INDEX_START in current and INDEX_END in current:
            head, rest = current.split(INDEX_START, 1)
            out[readme] = head + block + rest.split(INDEX_END, 1)[1]
        else:
            out[readme] = current.rstrip("\n") + "\n\n" + block + "\n"
        archive_dir = root.docs / "archived"
        if any(d.root is root and d.archived for d in repo.docs) or (archive_dir / "README.md").is_file():
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
        if not dest.exists():
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
        if anchor and dest.suffix == ".md" and anchor not in repo.slugs(dest):
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


def terminal_problems(doc, status=None):
    """Conditions a doc must meet before it may take a terminal status."""
    out = []
    if doc.type == "P" and (status or doc.status) == "done":
        out += ["slice `{}` is {}, not done".format(name, state or "without status")
                for name, state in plan_slices(doc) if state != "done"]
    if doc.type == "R":
        for fid, _sev, disp in review_findings(doc)[0]:
            if disp.split(" ", 1)[0] == "open":
                out.append("finding {} is still open".format(fid))
    if doc.type == "E":
        labels = doc.labels("Setup")
        if not labels.get(SOURCES_LABEL):
            out += ["Setup: `{}` is empty (research lists `- {}:` instead)".format(k, SOURCES_LABEL)
                    for k in SETUP_LABELS if not labels.get(k)]
    if doc.type == "I":
        labels = doc.labels("Reproduction")
        out += ["Reproduction: `{}` is empty".format(k) for k in SETUP_LABELS if not labels.get(k)]
    if doc.type == "I":
        labels = doc.labels("Resolution")
        out += ["Resolution: `{}` is empty".format(k) for k in RESOLUTION_LABELS if not labels.get(k)]
    if doc.type == "E" and not "".join(doc.section("Conclusion") or []).strip():
        out.append("Conclusion is empty")
    return out


def review_findings(doc):
    findings, errors = [], []
    for line in doc.section("Findings") or []:
        if not line.strip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        first = cells[0]
        if first.lower() == "id" or (first and set(first) <= set("-: ")):
            continue
        if not re.match(r"^{}-F\d+$".format(re.escape(doc.id)), first) or len(cells) < 4:
            errors.append("finding row must be | {}-F<n> | severity | finding | disposition |".format(doc.id))
            continue
        findings.append((first, cells[1], cells[3]))
    return findings, errors


def plan_designs(doc):
    return {entry.split("@")[0] for entry in doc.as_list("based_on")}


def content_lines(lines):
    """Lines that count as a content change for `updated`; `implemented` tracks the code, not the doc."""
    return [line for line in lines if not line.startswith("implemented:")]


def check_doc(repo, doc, changed, strict=False):
    rel, fm, info = doc.rel, doc.fm, TYPES[doc.type]

    def err(msg, fix=None):
        repo.problem("ERROR", rel, msg, fix=fix)

    if fm is None:
        err("missing or unterminated `---` frontmatter")
        return
    old = git(repo.root, "show", "HEAD:" + rel) if rel in changed and repo.has_head else None
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
    unfinished_level = "WARN" if not strict and status in info["active"] and not past_gate else "ERROR"
    if status not in info["active"] + info["terminal"]:
        err("status `{}` invalid; use one of {}".format(status, ", ".join(info["active"] + info["terminal"])))
    elif (status in info["terminal"]) != doc.archived:
        err("status `{}` requires the doc to be {}; use `canon.py archive`".format(
            status, "in archived/" if status in info["terminal"] else "outside archived/"))
    elif status in info["terminal"]:
        for msg in terminal_problems(doc):
            err(msg)

    created, updated = parse_date(fm.get("created")), parse_date(fm.get("updated"))
    for key, value in (("created", created), ("updated", updated)):
        if key in fm and (value is None or not DATE_RE.match(str(fm[key]))):
            err("`{}` must be YYYY-MM-DD".format(key))
    if created and updated and updated < created:
        err("`updated` is earlier than `created`")
    if not isinstance(fm.get("revision"), int) or fm["revision"] < 1:
        err("`revision` must be a positive integer")
    summary = str(fm.get("summary", "")).strip()
    if not summary:
        repo.problem(unfinished_level, rel, "`summary` is empty")
    elif len(summary) > MAX_SUMMARY:
        repo.problem("WARN", rel, "`summary` is {} chars (max {})".format(len(summary), MAX_SUMMARY))

    h1 = [h for h in doc.headings if h.level == 1]
    if len(h1) != 1 or not doc.title:
        err("body must have exactly one H1 reading `# {}: <title>`".format(doc.id))
    names = [h.text for h in doc.headings if h.level == 2]
    for name in info["sections"]:
        if name not in names:
            err("missing section `## {}`".format(name))
    if GUIDANCE in doc.text:
        repo.problem(unfinished_level, rel, "template guidance `<!-- canon: ... -->` left in the doc")
    if len(doc.lines) > MAX_DOC_LINES:
        hint = "; split into sub-designs ({0}A, {0}B, ...)".format(doc.id) if doc.type == "D" else ""
        repo.problem("WARN", rel, "{} lines (max {}){}".format(len(doc.lines), MAX_DOC_LINES, hint))

    refs = doc.as_list("refs")
    for ref in refs:
        if ref not in repo.by_id:
            err("`refs` entry {} does not exist".format(ref))
    linked = check_links(repo, doc.path, doc.lines, doc.fm_end + 1, doc)
    missing = sorted(linked - set(refs) - {doc.id})
    if missing:
        err("linked docs missing from `refs`: " + ", ".join(missing), fix=(doc, "refs", refs + missing))

    reviewed = fm.get("reviewed")
    if reviewed is not None:
        if not isinstance(reviewed, int) or reviewed > doc.revision:
            err("`reviewed` must be an integer revision not above `revision`")
        if not doc.as_list("reviewers"):
            err("`reviewers` must list who reviewed revision {}".format(reviewed))
    if doc.type == "P" and status == "in-progress" and reviewed is None:
        err("plan in progress without `reviewed`")
    elif past_gate and reviewed != doc.revision:
        repo.problem("ERROR" if strict else "WARN", rel, "revision {} is not reviewed (reviewed: {}); pass the review "
                     "gate, then set `reviewed` and `reviewers`".format(doc.revision, reviewed))

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
        if doc.suffix and "D" + doc.digits not in repo.by_id:
            err("sub-design needs parent D{}".format(doc.digits))
        for topic in doc.as_list("owns"):
            if not SLUG_RE.match(topic):
                err("`owns` entry `{}` must be kebab-case".format(topic))
        files = None
        for pattern in doc.as_list("paths"):
            files = files if files is not None else repo.project_files(doc.root)
            rx = glob_regex(pattern)
            if not any(rx.match(f) for f in files):
                repo.problem("WARN", rel, "`paths` entry `{}` matches no file".format(pattern))
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
                             .format(entry, design.id, design.revision))
    if doc.type == "R":
        findings, errors = review_findings(doc)
        for msg in errors:
            err(msg)
        seen = set()
        for fid, severity, disposition in findings:
            if fid in seen:
                err("duplicate finding id " + fid)
            seen.add(fid)
            if severity not in SEVERITIES:
                err("{} severity must be one of {}".format(fid, ", ".join(SEVERITIES)))
            word, _, arg = disposition.partition(" ")
            if word not in DISPOSITIONS:
                err("{} disposition must start with one of {}".format(fid, ", ".join(DISPOSITIONS)))
            elif word == "moved" and arg.strip() not in repo.by_id:
                err("{} moved to unknown doc `{}`".format(fid, arg.strip()))

    if old_lines is not None and content_lines(old_lines) != content_lines(doc.lines) \
            and old_fm.get("updated") == fm.get("updated") != today():
        err("content changed but `updated` was not bumped", fix=(doc, "updated", today()))


def run_check(repo, base=None):
    changed = set(repo.changed_files()) if repo.has_head else set()
    for doc in repo.docs:
        check_doc(repo, doc, changed, strict=bool(base))

    owners = {}
    for doc in repo.docs:
        if doc.type == "D" and not doc.archived:
            for topic in doc.as_list("owns"):
                if topic in owners:
                    repo.problem("ERROR", doc.rel, "topic `{}` is already owned by {}".format(topic, owners[topic]))
                owners.setdefault(topic, doc.id)

    for root, archived, name, rel in repo.attachments:
        doc = repo.by_id.get(name)
        if not doc or doc.root is not root or doc.archived != archived:
            repo.problem("ERROR", rel, "attachment directory {} has no matching doc beside it".format(name))

    for path in repo.scope_md:
        if not path.is_file():
            continue
        lines = path.read_text(encoding="utf-8").split("\n")
        check_links(repo, path, lines, 0)
        if path.name == "AGENTS.md" and len(lines) > MAX_AGENTS_LINES:
            repo.problem("WARN", posix_rel(path, repo.root), "{} lines (max {}); move detail into docs".format(
                len(lines), MAX_AGENTS_LINES))

    for path, text in expected_indexes(repo).items():
        current = path.read_text(encoding="utf-8") if path.is_file() else None
        if current != text:
            repo.problem("ERROR", posix_rel(path, repo.root), "index out of date", fix=("index",))
        elif current:
            check_links(repo, path, current.split("\n"), 0)

    for rel in repo.deleted_docs(base):
        match = FILE_RE.match(rel.rsplit("/", 1)[-1])
        doc_id = match.group(1) + match.group(2) + match.group(3) if match else None
        if doc_id and doc_id not in repo.by_id:
            repo.problem("ERROR", rel, "{} was deleted; restore it and archive it instead".format(doc_id))

    if base:
        fork = git(repo.root, "merge-base", "HEAD", base)
        if fork is None:
            sys.exit("canon: no merge base with " + base)
        at_fork, theirs = repo.tree_ids(fork.strip()), repo.tree_ids(base)
        for doc in repo.docs:
            other = theirs.get(doc.id)
            if other and doc.id not in at_fork:
                repo.problem("ERROR", doc.rel, "{} was also added on {} as {}; run `canon.py renumber {} --base {}`"
                             .format(doc.id, base, other, doc.rel, base))


def apply_fixes(repo):
    done, index = [], False
    for level, rel, _line, msg, fix in repo.problems:
        if not fix:
            continue
        if fix[0] == "index":
            index = True
            continue
        doc, key, value = fix
        doc.text = set_field(doc.text, key, value)
        doc.path.write_text(doc.text, encoding="utf-8")
        done.append("{}: set {}".format(rel, key))
    return done, index


def print_problems(repo):
    errors = warnings = 0
    for level, rel, line, msg, _fix in sorted(repo.problems, key=lambda p: (p[1], p[2] or 0)):
        print("{} {}{}: {}".format(level, rel, ":" + str(line) if line else "", msg))
        if level == "ERROR":
            errors += 1
        else:
            warnings += 1
    return errors, warnings


# ---------------------------------------------------------------- moves

def rewrite_for_moves(repo, moves, renamed=None, adopted=None):
    """Rewrite relative links in every markdown file so they survive `moves` (old path -> new path).

    `renamed` maps a moved doc's old path to (old id, new id); link texts naming it are rewritten too.
    `adopted` maps a file becoming a canon doc to its id; link texts to it get the reference format.
    """
    renamed, adopted = renamed or {}, adopted or {}

    def mapped(p):
        for src, dst in moves.items():
            if p == src:
                return dst
            try:
                return dst / p.relative_to(src)
            except ValueError:
                continue
        return p

    for rel in repo.files:
        if not rel.endswith(".md"):
            continue
        path = repo.root / rel
        lines = path.read_text(encoding="utf-8").split("\n")
        new_dir = mapped(path).parent
        edits = {}
        for i, match in iter_links(lines):
            target = match.group(3)
            resolved = repo.resolve(path.parent, target)
            if resolved is None or resolved[0] == "self":
                continue
            dest, anchor = resolved
            ids = renamed.get(dest)
            ref = REF_TEXT_RE.match(match.group(2))
            if ids and ref and ref.group(1) == ids[0]:
                edits.setdefault(i, []).append((match.start(2), match.start(2) + len(ids[0]), ids[1]))
            if dest in adopted and not ref and not match.group(1):
                label = adopted[dest] + ("§" + anchor if anchor else "") + ": " + (match.group(2) or adopted[dest])
                edits.setdefault(i, []).append((match.start(2), match.end(2), label))
            new_dest = mapped(dest)
            if new_dest == dest and new_dir == path.parent:
                continue
            new_target = "/" + posix_rel(new_dest, repo.root) if target.startswith("/") else posix_rel(new_dest, new_dir)
            if anchor:
                new_target += "#" + anchor
            if new_target != target:
                edits.setdefault(i, []).append((match.start(3), match.end(3), new_target))
        if edits:
            for i, spans in edits.items():
                line = lines[i]
                for start, end, value in sorted(spans, reverse=True):
                    line = line[:start] + value + line[end:]
                lines[i] = line
            path.write_text("\n".join(lines), encoding="utf-8")


def move_paths(repo, moves):
    for src, dst in moves.items():
        dst.parent.mkdir(parents=True, exist_ok=True)
        if not (repo.is_git and git(repo.root, "mv", str(src), str(dst)) is not None):
            os.rename(str(src), str(dst))


def require_clean_merge(repo):
    if repo.is_git and (git(repo.root, "ls-files", "-u") or "").strip():
        sys.exit("canon: resolve the merge conflicts first")


def used_numbers(repo, letter):
    return {d.number for d in repo.docs if d.type == letter}


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

def find_root(repo, root_arg):
    if root_arg:
        path = Path(os.path.realpath(root_arg))
        if path.name == "docs":
            path = path.parent
    else:
        path = Path(os.path.realpath(os.getcwd()))
        while not (path / "AGENTS.md").is_file() and path != repo.root and path.parent != path:
            path = path.parent
    if not (path / "AGENTS.md").is_file():
        sys.exit("canon: no AGENTS.md at {}; set the project up with `canon.py init` first".format(path))
    rel = posix_rel(path, repo.root)
    rel = "" if rel == "." else rel
    for root in repo.roots:
        if root.rel == rel:
            return root
    return Root(repo, rel)


def cmd_check(repo, args):
    run_check(repo, args.base)
    if args.fix:
        done, index = apply_fixes(repo)
        repo = Repo()
        if index or done:
            done += ["wrote " + p for p in write_indexes(repo)]
            repo = Repo()
        for line in done:
            print("fixed " + line)
        run_check(repo, args.base)
    errors, warnings = print_problems(repo)
    fixable = sum(1 for p in repo.problems if p[4])
    tail = "; {} fixable with --fix".format(fixable) if fixable and not args.fix else ""
    print("canon check: {} docs, {} errors, {} warnings{}".format(len(repo.docs), errors, warnings, tail))
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


def write_doc(root, letter, doc_id, slug, title, fields, implements=""):
    path = root.docs / TYPES[letter]["dir"] / "{}-{}.md".format(doc_id, slug)
    body = TEMPLATES[letter].replace("{implements}", implements).replace("{id}", doc_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8") as f:
            f.write(render_frontmatter(fields) + "\n# {}: {}\n{}".format(doc_id, title, body))
    except FileExistsError:
        sys.exit("canon: {} already exists".format(path))
    return path


def cmd_new(repo, args):
    with id_lock(repo):
        return new_doc(Repo(), args)


def new_doc(repo, args):
    letter = parse_type(args.type)
    if not SLUG_RE.match(args.slug):
        sys.exit("canon: slug must be kebab-case")
    root = find_root(repo, args.root)
    if args.parent:
        parent = repo.get(args.parent)
        if letter != "D" or parent.type != "D" or parent.suffix:
            sys.exit("canon: --parent takes a top-level design and only applies to designs")
        taken = {i for i in repo.by_id if i[:-1] == parent.id}
        letters = [c for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" if parent.id + c not in taken]
        if not letters:
            sys.exit("canon: {} has no free sub-design letter; create a new top-level design".format(parent.id))
        doc_id, root = parent.id + letters[0], parent.root
    else:
        doc_id = next_id(repo, letter)
    title = args.title or args.slug.replace("-", " ").capitalize()
    fields = default_fields(letter)
    implements = ""
    if letter == "P" and args.design:
        design = repo.get(args.design)
        if design.type != "D" or design.status not in ("accepted", "active"):
            sys.exit("canon: --from takes an accepted or active design")
        fields.update(modules=design.as_list("modules"), refs=[design.id],
                      based_on=["{}@r{}".format(design.id, design.revision)])
        plan_dir = root.docs / TYPES["P"]["dir"]
        implements = "\nImplements [{}: {}]({}).\n".format(design.id, design.title, posix_rel(design.path, plan_dir))
    path = write_doc(root, letter, doc_id, args.slug, title, fields, implements)
    write_indexes(Repo())
    print(posix_rel(path, repo.root))
    return 0


def cmd_archive(repo, args):
    require_clean_merge(repo)
    doc = repo.get(args.id)
    info = TYPES[doc.type]
    if doc.archived:
        sys.exit("canon: {} is already archived".format(doc.id))
    if args.status not in info["terminal"]:
        sys.exit("canon: {} can be archived as {}".format(doc.id, " or ".join(info["terminal"])))
    problems = terminal_problems(doc, args.status)
    if problems:
        print("\n".join("ERROR {}: {}".format(doc.rel, p) for p in problems))
        return 1
    text = set_field(set_field(doc.text, "status", args.status), "updated", today())
    doc.path.write_text(text, encoding="utf-8")
    archive_dir = doc.root.docs / "archived" / info["dir"]
    moves = {doc.path: archive_dir / doc.path.name}
    attachment = doc.root.docs / info["dir"] / doc.id
    if attachment.is_dir():
        moves[attachment] = archive_dir / doc.id
    rewrite_for_moves(repo, moves)
    move_paths(repo, moves)
    write_indexes(Repo())
    print("{} -> {}".format(doc.rel, posix_rel(moves[doc.path], repo.root)))
    return 0


def cmd_rename(repo, args):
    require_clean_merge(repo)
    doc = repo.get(args.id)
    if not SLUG_RE.match(args.slug):
        sys.exit("canon: slug must be kebab-case")
    moves = {doc.path: doc.path.with_name("{}-{}.md".format(doc.id, args.slug))}
    rewrite_for_moves(repo, moves)
    move_paths(repo, moves)
    write_indexes(Repo())
    print("{} -> {}".format(doc.rel, posix_rel(moves[doc.path], repo.root)))
    return 0


def script_version(path):
    match = re.search(r'^CANON_VERSION = "(\d+)"', path.read_text(encoding="utf-8"), re.M) if path.is_file() else None
    return int(match.group(1)) if match else None


def cmd_init(repo, args):
    require_clean_merge(repo)
    actions = []

    def note(verb, path):
        actions.append("{} {}".format(verb, posix_rel(path, repo.root)))

    script = repo.root / (args.script or "scripts/canon.py")
    script_rel = posix_rel(script, repo.root)
    me = Path(os.path.realpath(__file__))
    if Path(os.path.realpath(str(script))) != me:
        current = script_version(script)
        if current is None or current < int(CANON_VERSION):
            script.parent.mkdir(parents=True, exist_ok=True)
            script.write_text(me.read_text(encoding="utf-8"), encoding="utf-8")
            os.chmod(str(script), 0o755)
            note("updated" if current else "created", script)
        elif current > int(CANON_VERSION):
            print("warning: {} is v{}, newer than this canon.py (v{}); kept it".format(script_rel, current, CANON_VERSION))
        elif script.read_text(encoding="utf-8") != me.read_text(encoding="utf-8"):
            print("warning: {0} differs from this canon.py though both are v{1}; kept it. Unless it has local edits "
                  "to keep, replace it: cp {2} {0}".format(script_rel, current, me))

    attributes = repo.root / ".gitattributes"
    lines = attributes.read_text(encoding="utf-8").splitlines() if attributes.is_file() else []
    missing = [line for line in GITATTRIBUTES if line not in lines]
    if missing:
        attributes.write_text("\n".join(lines + missing) + "\n", encoding="utf-8")
        note("updated" if lines else "created", attributes)

    ignore = repo.root / ".gitignore"
    lines = ignore.read_text(encoding="utf-8").splitlines() if ignore.is_file() else []
    if not any(line.strip().strip("/") == LOCAL_DIR.strip("/") for line in lines):
        ignore.write_text("\n".join(lines + [LOCAL_DIR]) + "\n", encoding="utf-8")
        note("updated" if lines else "created", ignore)

    project = Path(os.path.realpath(args.root)) if args.root else repo.root
    top = project == repo.root
    agents = project / "AGENTS.md"
    block = AGENTS_BLOCK.format(script=script_rel)
    if not agents.is_file():
        project.mkdir(parents=True, exist_ok=True)
        agents.write_text("# AGENTS.md\n\n" + (block if top else SUB_AGENTS) + "\n", encoding="utf-8")
        note("created", agents)
    elif top:
        text = agents.read_text(encoding="utf-8")
        if AGENTS_START in text and AGENTS_END in text:
            head, rest = text.split(AGENTS_START, 1)
            new = head + block + rest.split(AGENTS_END, 1)[1]
        else:
            new = text.rstrip("\n") + "\n\n" + block + "\n"
        if new != text:
            agents.write_text(new, encoding="utf-8")
            note("updated", agents)

    readme = project / "docs" / "README.md"
    if not readme.is_file():
        readme.parent.mkdir(parents=True, exist_ok=True)
        readme.write_text(DOCS_README.format(script=script_rel), encoding="utf-8")
        note("created", readme)

    fresh = Repo()
    if top and not args.no_architecture and not any("architecture" in d.as_list("owns") for d in fresh.docs):
        fields = default_fields("D")
        fields["owns"] = ["architecture"]
        note("created", write_doc(find_root(fresh, str(project)), "D", next_id(fresh, "D"), "architecture",
                                  "Architecture", fields))

    if args.hook and repo.is_git:
        hook = repo.root / git(repo.root, "rev-parse", "--git-path", "hooks/pre-commit").strip()
        if hook.exists():
            print("kept the existing pre-commit hook; add `python3 {} check` to it".format(script_rel))
        else:
            hook.parent.mkdir(parents=True, exist_ok=True)
            hook.write_text("#!/bin/sh\nexec python3 {} check\n".format(script_rel), encoding="utf-8")
            os.chmod(str(hook), 0o755)
            note("created", hook)

    actions += ["wrote " + rel for rel in write_indexes(Repo())]
    print("\n".join(actions) if actions else "canon init: nothing to do")
    return 0


def slugify(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "doc"


def cmd_adopt(repo, args):
    require_clean_merge(repo)
    with id_lock(repo):
        return adopt_doc(Repo(), args)


def adopt_doc(repo, args):
    letter = parse_type(args.type)
    src = Path(os.path.realpath(args.file))
    if not src.is_file() or src.suffix != ".md":
        sys.exit("canon: {} is not a markdown file".format(args.file))
    if src in repo.by_path:
        sys.exit("canon: {} is already a canon doc".format(args.file))
    if args.root:
        root = find_root(repo, args.root)
    else:
        project = src.parent
        while not (project / "AGENTS.md").is_file() and project != repo.root and project.parent != project:
            project = project.parent
        root = find_root(repo, str(project))
    slug = args.slug or slugify(src.stem)
    if not SLUG_RE.match(slug):
        sys.exit("canon: slug must be kebab-case")
    doc_id = next_id(repo, letter)
    dest = root.docs / TYPES[letter]["dir"] / "{}-{}.md".format(doc_id, slug)
    rewrite_for_moves(repo, {src: dest}, adopted={src: doc_id})

    lines = src.read_text(encoding="utf-8").split("\n")
    fm, end, _bad = parse_frontmatter(lines)
    body = lines[end + 1:] if fm is not None else lines
    if fm:
        print("dropped frontmatter fields: " + ", ".join(fm))
    h1 = next((h for h in scan_headings(body) if h.level == 1), None)
    title = args.title or (h1.text if h1 else slug.replace("-", " ").capitalize())
    if h1:
        body[h1.line] = "# {}: {}".format(doc_id, title)
    else:
        body = ["# {}: {}".format(doc_id, title), ""] + body
    names = {h.text for h in scan_headings(body) if h.level == 2}
    text = "\n".join(body).strip("\n") + "\n"
    for name in TYPES[letter]["sections"]:
        if name not in names:
            text += "\n## {}\n\n<!-- canon: Move the matching adopted content here. -->\n".format(name)
    src.write_text(render_frontmatter(default_fields(letter)) + "\n" + text, encoding="utf-8")
    move_paths(repo, {src: dest})
    write_indexes(Repo())
    print("{} -> {}".format(posix_rel(src, repo.root), posix_rel(dest, repo.root)))
    return 0


def cmd_renumber(repo, args):
    require_clean_merge(repo)
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
    on_base = repo.tree_files(args.base) if args.base else None
    new_id = renumbered_id(repo, doc, args.new, on_base)
    links = {}

    def linked(src, path):
        if src.path not in links:
            links[src.path] = doc_links(repo, src)
        return path in links[src.path]

    def side(ours, theirs, there, ours_linked, theirs_linked):
        """Whose a sub-design, attachment or reference is when `ours` shares its id with `theirs`: 'ours',
        'theirs', or None when nothing tells or the evidence conflicts. It belongs to the doc on its side of the
        base (`there`: it exists on the base), when only one of them exists there, and to the doc links alone reach.
        """
        votes = set()
        if on_base is not None and all((t.rel in on_base) != (ours.rel in on_base) for t in theirs):
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
        owner = side(doc, rivals, on_base is not None and child.rel in on_base,
                     linked(child, doc.path) or linked(doc, child.path),
                     any(linked(child, r.path) or linked(r, child.path) for r in rivals)) if rivals else "ours"
        if owner == "ours":
            group.append(child)
        elif owner is None:
            unclear.append(child.rel)
    if unclear:
        sys.exit("canon: cannot tell which {} owns {}; link each sub-design from its parent design{}, then rerun"
                 .format(doc.id, ", ".join(unclear), "" if args.base else " or pass --base <ref>"))
    if len({d.id for d in group}) < len(group):
        sys.exit("canon: sub-designs of {} share an id; renumber the one this branch added first".format(doc.id))

    renamed, moves, notes = {}, {}, []
    for d in group:
        new = new_id if d is doc else new_id + d.suffix
        renamed[d.path] = (d.id, new)
        moves[d.path] = d.path.with_name("{}-{}.md".format(new, d.slug))
        attachment = d.path.parent / d.id
        if not attachment.is_dir():
            continue
        others = [x for x in repo.docs if x.id == d.id and x is not d and x.path.parent == d.path.parent]
        owners = {side(d, others, on_base is not None and posix_rel(f, repo.root) in on_base, linked(d, f),
                       any(linked(x, f) for x in others)) for f in attachment.rglob("*") if f.is_file()} \
            if others else {"ours"}
        if owners <= {"ours"}:
            moves[attachment] = d.path.parent / new
        elif owners != {"theirs"}:
            notes.append("kept {}: it also holds attachments of another {}; move this doc's files to {} and fix "
                         "their links".format(posix_rel(attachment, repo.root), d.id,
                                              posix_rel(d.path.parent / new, repo.root)))
    rewrite_for_moves(repo, moves, renamed)

    id_map = dict(renamed.values())
    holder = {old: repo.by_path[path] for path, (old, _new) in renamed.items()}
    others = {old: [d for d in repo.docs if d.id == old and d.path not in renamed] for old in id_map}
    kept = {}
    for d in repo.docs:
        before = set()
        if on_base is not None and d.rel in on_base:
            before = id_entries(d.type, git(repo.root, "show", "{}:{}".format(args.base, d.rel)) or "")

        def pick(field, key, old, d=d, before=before):
            if old not in id_map or not others[old]:
                return id_map.get(old)
            owner = side(holder[old], others[old], (field, key, old) in before, linked(d, holder[old].path),
                         any(linked(d, x.path) for x in others[old]))
            if owner is None:
                kept.setdefault(old, set()).add(d.rel)
            return id_map[old] if owner == "ours" else None

        text = d.path.read_text(encoding="utf-8")
        new_text = remap_ids(d, text, pick, renamed.get(d.path))
        if new_text != text:
            d.path.write_text(new_text, encoding="utf-8")
    move_paths(repo, moves)
    write_indexes(Repo())
    for old, new in id_map.items():
        print("{} -> {}".format(old, new))
    for old, rels in sorted(kept.items()):
        print("kept {} in {}: another doc still has that id; change the entries there that mean {}"
              .format(old, ", ".join(sorted(rels)), id_map[old]))
    print("\n".join(notes + ["run `canon.py check --fix` to finish"]))
    return 0


def renumbered_id(repo, doc, wanted, on_base):
    """`wanted`, once checked and normalized, or the next free id; a sub-design keeps its parent and takes a free
    letter. Ids in the base's files (`on_base`) stay taken."""
    taken = {d.id for d in repo.docs} | {i for i in map(path_id, on_base or ()) if i}
    if doc.suffix:
        parent = doc.type + doc.digits
        letters = [parent + c for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"]
        free = [i for i in letters if i not in taken]
        if wanted and wanted not in letters:
            sys.exit("canon: new id must be a sub-design of {}".format(parent))
        if wanted and wanted not in free:
            sys.exit("canon: {} is already used".format(wanted))
        if not free:
            sys.exit("canon: {} has no free sub-design letter".format(parent))
        return wanted or free[0]
    used = {int(FULL_ID_RE.match(i).group(2)) for i in taken if i[0] == doc.type}
    if not wanted:
        return doc.type + str(max(used) + 1).zfill(3)
    match = FULL_ID_RE.match(wanted)
    if not match or match.group(1) != doc.type or match.group(3):
        sys.exit("canon: new id must be a top-level {} id".format(doc.type))
    number = int(match.group(2))
    if number in used:
        sys.exit("canon: {} is already used".format(wanted))
    return doc.type + str(number).zfill(3)


def doc_links(repo, doc):
    """Paths of the files a doc's body links to."""
    paths = set()
    for _i, match in iter_links(doc.lines, doc.fm_end + 1):
        resolved = repo.resolve(doc.path.parent, match.group(3))
        if resolved and resolved[0] != "self":
            paths.add(resolved[0])
    return paths


def id_entries(doc_type, text):
    """(field, key, id) for each id a doc's text names in `refs`, `based_on` and `moved` dispositions; the key is
    the entry, or for `moved` the finding id."""
    fm = parse_frontmatter(text.split("\n"))[0] or {}
    entries = {(field, value, value.partition("@")[0]) for field in ("refs", "based_on")
               for value in (fm.get(field) if isinstance(fm.get(field), list) else [])}
    if doc_type == "R":
        entries |= {("moved", m.group(2), m.group(4)) for m in MOVED_RE.finditer(text)}
    return entries


def remap_ids(doc, text, pick, own=None):
    """Rewrite each id in `refs`, `based_on` and `moved` dispositions for which `pick(field, key, id)` returns a new
    id (keys as in `id_entries`); when the doc itself is renumbered (`own` = (old, new)), also its H1 and its
    finding ids."""
    fm = parse_frontmatter(text.split("\n"))[0] or {}
    for field in ("refs", "based_on"):
        values = fm.get(field)
        if isinstance(values, list):
            mapped = []
            for value in values:
                head, sep, tail = value.partition("@")
                mapped.append((pick(field, value, head) or head) + sep + tail)
            if mapped != values:
                text = set_field(text, field, mapped)

    def moved(m):
        return m.group(1) + m.group(2) + m.group(3) + (pick("moved", m.group(2), m.group(4)) or m.group(4)) \
            + m.group(5)

    if doc.type == "R":
        text = MOVED_RE.sub(moved, text)
    if own:
        old, new = own
        text = re.sub(r"^# {}:".format(re.escape(old)), "# {}:".format(new), text, count=1, flags=re.M)
        text = re.sub(r"\b{}-F(\d+)\b".format(re.escape(old)), new + r"-F\1", text)
    return text


def cmd_index(repo, args):
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
        sys.exit("canon: {} has no section #{}".format(doc.id, anchor))
    print(doc.rel)
    print("\n".join(doc.lines[1:doc.fm_end]))
    print("# {}: {}".format(doc.id, doc.title))
    for h in doc.headings:
        if h.level >= 2:
            print("{}{}  #{}".format("  " * (h.level - 2), h.text, h.slug))
    return 0


def lead_note(doc):
    implemented = doc.get("implemented")
    if doc.type == "D" and isinstance(implemented, int) and implemented < doc.revision:
        return " [spec r{} leads code r{}]".format(doc.revision, implemented)
    return ""


def doc_line(doc):
    return "{} {} {} - {}{}".format(doc.id, doc.status, doc.rel, doc.get("summary", ""), lead_note(doc))


def cmd_find(repo, args):
    words = [w.lower() for w in args.words]
    found = 0
    for doc in repo.docs:
        if doc.archived and not args.archived:
            continue
        meta = " ".join([doc.id, doc.title, str(doc.get("summary", ""))] + doc.as_list("owns")
                        + doc.as_list("modules")).lower()
        hits = [h for h in doc.headings if h.level >= 2 and all(w in meta + " " + h.text.lower() for w in words)]
        if all(w in meta for w in words) or hits:
            found += 1
            print(doc_line(doc))
            for h in hits if not all(w in meta for w in words) else []:
                print("  {}#{} {}".format(doc.id, h.slug, h.text))
    if not found:
        print("no match")
    return 0


def cmd_which(repo, args):
    for name in args.files:
        path = Path(os.path.realpath(name))
        hits = repo.designs_for(path)
        rel = posix_rel(path, repo.root)
        if not hits:
            print("{}: no design".format(rel))
        for doc in hits:
            print("{}: {} {} - {}{}".format(rel, doc.id, doc.rel, doc.get("summary", ""), lead_note(doc)))
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


def unchecked_commits(repo, doc):
    """The last commit that changed a design's file, and the later commits touching its `paths` whose
    `Refs:` trailers do not name it."""
    base = (git(repo.root, "log", "-1", "--format=%H", "--", doc.rel) or "").strip()
    if not base:
        return None, []
    specs = []
    for pattern in doc.as_list("paths"):
        specs += git_pathspec(doc.root.rel, pattern)
    out = git(repo.root, "log", "--format=%H%x00%B%x01", base + "..HEAD", "--", *specs) or ""
    commits = []
    for entry in out.split("\x01"):
        sha, _, message = entry.strip("\n").partition("\0")
        named = set()
        for line in message.splitlines():
            if line.lower().startswith("refs:"):
                named |= set(re.findall(r"\b[CDPREI]\d{3,}[A-Z]?\b", line))
        if sha and doc.id not in named:
            commits.append(sha)
    return base, commits


def cmd_audit(repo, args):
    now = datetime.date.today()
    report = []
    stale = []
    for doc in repo.docs:
        if doc.type == "D" and not doc.archived and doc.as_list("paths") and repo.has_head:
            base, commits = unchecked_commits(repo, doc)
            if commits:
                stale.append((len(commits), base, doc))
    if stale:
        report.append("Designs with code commits since the design last changed that no `Refs:` trailer names "
                      "(most first; review `git log <since>..HEAD` on its paths):")
        for count, base, doc in sorted(stale, key=lambda x: -x[0]):
            report.append("  {} commits since {}  {}".format(count, base[:12], doc_line(doc)))
    idle = []
    for doc in repo.docs:
        updated = parse_date(doc.get("updated"))
        in_work = not doc.archived and doc.type != "C" and not (doc.type == "D" and doc.status == "active")
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
            out = git(repo.root, "log", *since, "--format=%H", "--", *code_pathspec(repo, root)) or ""
            commits = len(set(out.split()))
        if len(done) >= args.review_after or commits >= args.review_commits:
            report.append("{}: {} plans finished and {} code commits since the last review; consider a review (R)"
                          .format(root.label, len(done), commits))
    print("\n".join(report) if report else "canon audit: nothing to report")
    return 0


# ---------------------------------------------------------------- trace

TRACE_DIR = LOCAL_DIR + "canon/trace"
TRACE_KINDS = ("design", "plan", "implement", "investigate", "canon-review", "retro", "code-review", "gate", "slice",
               "end-check")
TOP_LEVEL_KINDS = TRACE_KINDS[:6]
OUTCOMES = ("delivered", "blocked", "handoff", "cancelled")
KIND_OUTCOMES = {"implement": OUTCOMES + ("partial", "escalated"), "end-check": ("quiet", "raised")}
REVIEW_ROLES = {"gate": ("same-model", "cross-family"), "code-review": ("spec", "standards", "cross-family")}
REVIEW_DISPOSITIONS = {"gate": ("accepted", "declined", "escalated"),
                       "code-review": ("accepted", "declined", "escalated", "deferred")}
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


def trace_switch_path():
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "canon" / "trace"


def trace_state(root):
    """Whether tracing is on in the checkout at `root`, and the status line that says why."""
    switch, off = trace_switch_path(), TRACE_DIR + "/off"
    if not switch.exists():
        return False, "trace off: no machine switch {}; `canon.py trace on` creates it".format(switch)
    if (root / off).exists():
        return False, "trace off: this checkout opted out with {}; `canon.py trace on --here` deletes it".format(off)
    return True, "trace on: the machine switch {} exists and this checkout has no {}".format(switch, off)


def trace_docs(root, is_git, names):
    """Each doc id as `<id>@r<revision>`, from the doc in docs/ or docs/archived/ at `root`, else in any docs/
    directory Git lists; a name that finds no doc stays as given."""
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
    revisions = {name: doc_revision(path) for name, path in paths.items()}
    return ["{}@r{}".format(name, revisions[name]) if revisions.get(name) else name for name in names]


def doc_revision(path):
    """The `revision` in a doc file's frontmatter; None when it has none or the file cannot be read."""
    try:
        revision = (parse_frontmatter(path.read_text(encoding="utf-8").split("\n"))[0] or {}).get("revision")
    except (OSError, ValueError):
        return None
    return revision if isinstance(revision, int) else None


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


def read_events(trace_dir, *needles):
    """The lines of events.jsonl holding one of the byte strings `needles`, parsed; lines that do not parse or carry
    another `v` are skipped."""
    try:
        data = (trace_dir / "events.jsonl").read_bytes()
    except FileNotFoundError:
        return []
    events = []
    for raw in data.split(b"\n"):
        if any(needle in raw for needle in needles):
            try:
                event = json.loads(raw.decode("utf-8"))
            except ValueError:
                continue
            if isinstance(event, dict) and type(event.get("v")) is int and event["v"] == 1:
                events.append(event)
    return events


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


def append_event(trace_dir, line, check, manifest=None, store=None):
    """Append `line` to events.jsonl in one write, under events.lock and once `check` passes there again, preceded by
    the `manifest` line of its digest when the file holds none. `store`, run there once `check` passes and before
    `line` is serialized, stores what the line records and completes it, so that a call rejected there stores
    nothing."""
    entry = event_bytes(manifest) if manifest else b""
    trace_dir.mkdir(parents=True, exist_ok=True)
    with file_lock(trace_dir / "events.lock", TRACE_LOCK_WAIT, TraceError("timed out waiting for events.lock")):
        check()
        if store:
            store()
        data = event_bytes(line)
        if entry and not any(event.get("type") == "manifest" and event.get("digest") == manifest["digest"]
                             for event in read_events(trace_dir, manifest["digest"].encode())):
            data = entry + data
        fd = os.open(str(trace_dir / "events.jsonl"),
                     os.O_WRONLY | os.O_APPEND | os.O_CREAT | getattr(os, "O_BINARY", 0), 0o666)
        try:
            written = os.write(fd, data)
        finally:
            os.close(fd)
    if written != len(data):
        raise TraceError("wrote {} of the {} bytes to append to events.jsonl".format(written, len(data)))


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


def take_snapshot(root, trace_dir, unit, parent):
    """Record the work tree at refs/trace/<unit> in the snapshot repository, as a commit whose parent holds the tree
    of commit `parent`, or that has no parent when `parent` is None (D001#snapshots); return the snapshot commit."""
    env = trace_env(**SNAPSHOT_IDENTITY)
    status = trace_git(root, env, "status", "--porcelain", "-z", "--untracked-files=all")
    if changes_size(root, status) > MAX_CHANGES:
        raise SnapshotSkip("changes-over-10MiB")
    lines = trace_git(root, env, "rev-parse", "--git-path", "index", "--git-path", "objects",
                      "--show-object-format").splitlines()
    index, objects = (os.path.abspath(os.path.join(str(root), os.fsdecode(path))) for path in lines[:2])
    git_dir = snapshot_repo(trace_dir, unit, env, sha256=lines[2:] == [b"sha256"])
    copy = git_dir / ("index-" + unit)
    try:
        copy_index(index, copy)
        steps = dict(env, GIT_INDEX_FILE=str(copy), GIT_OBJECT_DIRECTORY=str(git_dir / "objects"),
                     GIT_ALTERNATE_OBJECT_DIRECTORIES=objects)
        trace_git(root, steps, "add", "-A")
        tree = trace_git(root, steps, "write-tree").decode().strip()
        parents = []
        if parent:
            base = trace_git(root, steps, "commit-tree", parent + "^{tree}", "-m", "trace {} base".format(unit))
            parents = ["-p", base.decode().strip()]
        commit = trace_git(root, steps, "commit-tree", tree, *parents, "-m", "trace " + unit).decode().strip()
        copy_borrowed(root, steps, trace_dir, env, commit)
        snapshot_git(trace_dir, env, "update-ref", "refs/trace/" + unit, commit)
    finally:
        with contextlib.suppress(OSError):
            copy.unlink()
    with contextlib.suppress(SnapshotSkip):
        snapshot_git(trace_dir, env, "-c", "gc.autoDetach=false", "gc", "--auto", "--quiet")
    return commit


def copy_borrowed(root, steps, trace_dir, env, commit):
    """Copy into the snapshot repository the objects `commit` reaches that it lacks, which the snapshot steps
    borrowed from the project, so the snapshot repository depends on nothing outside it."""
    listing = trace_git(root, steps, "rev-list", "--objects", commit)
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


def record_snapshot(root, is_git, trace_dir, unit, parent, manifest, files):
    """Under snapshot.lock, take the unit's snapshot, then store the skill files of `manifest` when the snapshot
    repository exists; return the snapshot commit and the reason none was recorded, one of them None. A start that
    cannot take the lock records and stores nothing."""
    if not is_git:
        return None, "no-git"
    snapshot = skip = None
    try:
        with snapshot_lock(trace_dir):
            try:
                snapshot = take_snapshot(root, trace_dir, unit, parent)
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


def trace_start(args):
    root, is_git = trace_root()
    if not trace_state(root)[0]:
        print("trace off")
        return 0
    if (args.kind == "slice") != bool(args.slice) or (args.slice and not SLICE_RE.fullmatch(args.slice)):
        raise TraceError("--slice S<n> comes with the slice kind only, which requires it")
    invalid = [doc for doc in args.docs if not FULL_ID_RE.fullmatch(doc)]
    if invalid:
        raise TraceError("DOC arguments are doc ids such as D001, not {}".format(", ".join(map(repr, invalid))))
    if args.model is not None and not short_field(args.model):
        raise TraceError("--model must be a single-line string of 1 to {} characters".format(MAX_REVIEWER_FIELD))
    trace_dir = root / TRACE_DIR
    parent = start_parent(trace_dir, args)
    host, conversation = trace_host()
    now = datetime.datetime.now(datetime.timezone.utc)
    unit = now.strftime(UNIT_TIME_FORMAT) + "-" + os.urandom(3).hex()
    line = {"v": 1, "type": "start", "id": unit, "kind": args.kind,
            "at": now.astimezone().isoformat(timespec="seconds"), "parent": args.parent,
            "docs": trace_docs(root, is_git, args.docs)}
    if args.slice:
        line["slice"] = args.slice
    head = trace_head(root, is_git)
    base = resolve_base(root, args.base, head)
    if args.kind == "slice":
        model, skill = parent.get("model"), parent.get("skill")
    else:
        model = args.model.lower() if args.model else None
        skill = os.path.abspath(args.skill) if args.skill else None
    manifest, files = skill_manifest(skill) if skill else (None, [])
    ignore_trace_dir(root)
    snapshot, skipped = record_snapshot(root, is_git, trace_dir, unit, base or head, manifest, files)
    line.update(tier=args.tier or (parent or {}).get("tier"), base=base, head=head, snapshot=snapshot,
                skipped=skipped, host=host, conversation=conversation, model=model, skill=skill,
                manifest=manifest["digest"] if manifest else None)
    append_event(trace_dir, line, lambda: start_parent(trace_dir, args), manifest)
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
        raise TraceError("--input comes with gate and code-review units only")
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


def check_dispositions(kind, dispositions):
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
        entry(reviewer, where, ("role", "model", "id"))
        expect(reviewer["role"] in roles and reviewer["role"] not in listed, where + ".role",
               "one of {}, each listed once".format(", ".join(roles)))
        listed.append(reviewer["role"])
        expect(short_field(reviewer["model"]), where + ".model", "a single-line string of at most 200 characters")
        expect(reviewer["id"] is None or short_field(reviewer["id"]), where + ".id",
               "null or a single-line string of at most 200 characters")
    expect(isinstance(dispositions["findings"], list), ".findings", "a list")
    for n, finding in enumerate(dispositions["findings"]):
        where = ".findings[{}]".format(n)
        entry(finding, where, ("by", "severity", "disposition") + (("axis",) if review else ()), ("confirmed",))
        by = finding["by"]
        expect(isinstance(by, list) and by and all(isinstance(ref, str) and ref.partition(":")[0] in listed
                                                   and FINDING_ID_RE.fullmatch(ref.partition(":")[2]) for ref in by),
               where + ".by", "a non-empty list of <role>:F<n>, each naming a listed reviewer")
        expect(finding["severity"] in SEVERITIES, where + ".severity", " or ".join(SEVERITIES))
        expect(finding["disposition"] in REVIEW_DISPOSITIONS[kind], where + ".disposition",
               " or ".join(REVIEW_DISPOSITIONS[kind]))
        if review:
            expect(finding["axis"] in ("spec", "standards"), where + ".axis", "spec or standards")
        if "confirmed" in finding:
            expect(finding["confirmed"] in ("resolved", "not-resolved"), where + ".confirmed",
                   "resolved or not-resolved")
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


def archive_files(source, target, since):
    """Copy the regular files directly in `source` modified at second `since` or later into `target` when they total
    at most 2 MiB; return the end line's `archive`."""
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_BINARY", 0)
    written = []
    try:
        with os.scandir(str(source)) as entries:
            names = sorted(entry.name for entry in entries if entry.is_file(follow_symlinks=False)
                           and entry.stat(follow_symlinks=False).st_mtime_ns >= since * 10 ** 9)
        files, total = {}, 0
        for name in names:
            with open(os.open(os.path.join(str(source), name), flags), "rb") as file:
                if not stat.S_ISREG(os.fstat(file.fileno()).st_mode):
                    continue
                files[name] = file.read(MAX_ARCHIVE + 1 - total)
            total += len(files[name])
            if total > MAX_ARCHIVE:
                return "over-2MiB"
        if not files:
            return "none"
        target.mkdir(parents=True, exist_ok=True)
        for name, data in files.items():
            written.append(target / name)
            written[-1].write_bytes(data)
    except OSError as error:
        for path in written:
            with contextlib.suppress(OSError):
                path.unlink()
        return "copy: " + errno_name(error)
    return "ok"


def trace_end(args):
    root, is_git = trace_root()
    if not trace_state(root)[0]:
        print("trace off")
        return 0
    trace_dir = root / TRACE_DIR
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

    def archive():
        if source:
            line["archive"] = archive_files(source, trace_dir / args.unit, unit_started(args.unit))

    append_event(trace_dir, line, lambda: end_unit(trace_dir, args), manifest, archive)
    print("trace {} ended".format(args.unit))
    return 0


def trace_status(args):
    root, _is_git = trace_root()
    print(trace_state(root)[1])
    now = datetime.datetime.now(datetime.timezone.utc)
    since = (now - datetime.timedelta(hours=24)).strftime(UNIT_TIME_FORMAT)
    events = read_events(root / TRACE_DIR,
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
    print("\n".join(snapshot_summary(root / TRACE_DIR)))
    return 0


def trace_switch(args):
    root, _is_git = trace_root()
    if args.here:
        off = root / TRACE_DIR / "off"
        if args.action == "off":
            ignore_trace_dir(root)
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
    print(trace_state(root)[1])
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


def prune_snapshots(trace_dir, cutoff):
    """Delete the snapshot refs of the units started before `cutoff`; return how many went."""
    refs = prune_git(trace_dir, "for-each-ref", "--format=%(refname)", "refs/trace/").decode().split()
    old = [ref for ref in refs if stale(ref, "refs/trace/", cutoff)]
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
    root, _is_git = trace_root()
    trace_dir = root / TRACE_DIR
    now = datetime.datetime.now(datetime.timezone.utc)
    cutoff = (now - datetime.timedelta(days=args.days)).strftime(UNIT_TIME_FORMAT)
    hour_ago = (now - datetime.timedelta(hours=1)).strftime(UNIT_TIME_FORMAT)
    repo = (trace_dir / ".git").is_dir()
    held = file_lock(trace_dir / "snapshot.lock", TRACE_LOCK_WAIT, TraceError("timed out waiting for snapshot.lock")) \
        if repo else contextlib.nullcontext()
    with held:
        snapshots = prune_snapshots(trace_dir, cutoff) if repo else 0
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


def main(argv=None):
    parser = argparse.ArgumentParser(prog="canon.py", description="canon documentation system tool")
    parser.add_argument("--version", action="version", version="canon " + CANON_VERSION)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("check", help="validate all docs; exit 1 on errors")
    p.add_argument("--fix", action="store_true", help="apply mechanical fixes (refs, updated, implemented, indexes)")
    p.add_argument("--base", help="also check this branch against a ref, e.g. origin/main: deleted docs, id "
                                  "collisions, revisions pending review and unfinished docs fail")
    p.set_defaults(func=cmd_check)

    p = sub.add_parser("new", help="create a doc from its template with the next free id")
    p.add_argument("type", help="C D P R E I (or concept, design, plan, ...)")
    p.add_argument("slug", help="kebab-case file slug")
    p.add_argument("--title")
    p.add_argument("--root", help="project directory (with AGENTS.md); default: nearest to cwd")
    p.add_argument("--parent", help="top-level design to split, creates D00XA, D00XB, ...")
    p.add_argument("--from", dest="design", help="design a plan implements; fills based_on")
    p.set_defaults(func=cmd_new)

    p = sub.add_parser("archive", help="set a terminal status, move to archived/, rewrite links")
    p.add_argument("id")
    p.add_argument("status")
    p.set_defaults(func=cmd_archive)

    p = sub.add_parser("init", help="set up canon in a repo or module (idempotent; also upgrades the script copy)")
    p.add_argument("--root", help="module directory to set up (default: repo root)")
    p.add_argument("--script", help="where to copy canon.py, relative to the repo root (default: scripts/canon.py)")
    p.add_argument("--hook", action="store_true", help="install a git pre-commit hook running `check`")
    p.add_argument("--no-architecture", action="store_true",
                   help="skip the architecture design skeleton (an adopted doc will own `architecture`)")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("adopt", help="turn an existing markdown file into a canon doc, keeping history and links")
    p.add_argument("file")
    p.add_argument("type", help="C D P R E I (or concept, design, plan, ...)")
    p.add_argument("--slug", help="kebab-case slug (default: from the file name)")
    p.add_argument("--title", help="title (default: the file's H1)")
    p.add_argument("--root", help="project directory (default: nearest AGENTS.md above the file)")
    p.set_defaults(func=cmd_adopt)

    p = sub.add_parser("rename", help="change a doc's file slug and rewrite every link to it")
    p.add_argument("id")
    p.add_argument("slug")
    p.set_defaults(func=cmd_rename)

    p = sub.add_parser("renumber", help="give a doc a new id, or a sub-design a new letter, and rewrite the links "
                                        "and references to it")
    p.add_argument("target", help="doc id, or its path when the id is duplicated")
    p.add_argument("new", nargs="?", help="new id (default: next free)")
    p.add_argument("--base", help="the branch merged or rebased onto, e.g. origin/main: its ids stay taken, and "
                                  "what exists there belongs to the doc that exists there")
    p.set_defaults(func=cmd_renumber)

    p = sub.add_parser("index", help="regenerate docs/README.md and docs/archived/README.md indexes")
    p.set_defaults(func=cmd_index)

    p = sub.add_parser("show", help="print a doc's outline, or one section with ID#slug")
    p.add_argument("ref")
    p.set_defaults(func=cmd_show)

    p = sub.add_parser("find", help="search ids, titles, summaries, owns, modules and headings")
    p.add_argument("words", nargs="+")
    p.add_argument("--archived", action="store_true", help="include archived docs")
    p.set_defaults(func=cmd_find)

    p = sub.add_parser("which", help="list the designs whose `paths` govern the given files")
    p.add_argument("files", nargs="+")
    p.set_defaults(func=cmd_which)

    p = sub.add_parser("affected", help="designs and plans governing changed files (default: uncommitted)")
    p.add_argument("files", nargs="*")
    p.add_argument("--base", help="include changes since the merge base with this ref")
    p.set_defaults(func=cmd_affected)

    p = sub.add_parser("audit", help="report designs with unchecked code commits, idle open docs, and due reviews")
    p.add_argument("--days", type=int, default=30, help="idle threshold (default 30)")
    p.add_argument("--review-after", type=int, default=5, help="finished plans before a review is due (default 5)")
    p.add_argument("--review-commits", type=int, default=50,
                   help="code commits before a review is due (default 50)")
    p.set_defaults(func=cmd_audit)

    p = sub.add_parser("trace", help="record canon workflow units for skill telemetry; off unless `trace on` ran")
    actions = p.add_subparsers(dest="action", required=True)
    t = actions.add_parser("start", help="start a unit and print `trace <id>`")
    t.add_argument("kind", choices=TRACE_KINDS)
    t.add_argument("docs", nargs="*", metavar="DOC", help="ids of the docs the unit works on")
    t.add_argument("--parent", metavar="UNIT", help="id of the open unit this one runs inside")
    t.add_argument("--tier", choices=("L0", "L1", "L2"))
    t.add_argument("--slice", metavar="S<n>", help="the plan slice a slice unit builds")
    t.add_argument("--base", metavar="REF", help="the commit the unit's change starts from; the snapshot's parent "
                                                 "holds the tree of its merge base with HEAD")
    t.add_argument("--skill", metavar="DIR", help="directory of the SKILL.md being followed")
    t.add_argument("--model", metavar="ID", help="the session's model id")
    t.set_defaults(func=trace_start)
    t = actions.add_parser("end", help="end an open unit")
    t.add_argument("unit")
    t.add_argument("outcome")
    t.add_argument("--to", choices=("L1", "L2", "plan"), help="the tier or plan an escalated unit needs")
    t.add_argument("--dir", metavar="DIR", help="directory under .canon/ whose files changed since the unit started "
                                                "are archived with it")
    t.add_argument("--input", metavar="FILE|-", help="a gate's or code review's dispositions as JSON, from FILE or "
                                                     "from stdin for -")
    t.set_defaults(func=trace_end)
    t = actions.add_parser("status", help="say whether tracing is on and why, and list the open units")
    t.set_defaults(func=trace_status)
    t = actions.add_parser("on", help="turn tracing on for this machine; --here deletes this checkout's off file")
    t.add_argument("--here", action="store_true")
    t.set_defaults(func=trace_switch)
    t = actions.add_parser("off", help="turn tracing off for this machine; --here opts this checkout out")
    t.add_argument("--here", action="store_true")
    t.set_defaults(func=trace_switch)
    t = actions.add_parser("prune", help="delete the snapshots and archives of units started more than N days ago, "
                                         "tracing on or off")
    t.add_argument("--days", type=day_count, required=True, metavar="N")
    t.set_defaults(func=trace_prune)

    args = parser.parse_args(argv)
    if args.command == "trace":
        return cmd_trace(args)
    return args.func(Repo(), args)


if __name__ == "__main__":
    sys.exit(main())
