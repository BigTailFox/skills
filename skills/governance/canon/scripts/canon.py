#!/usr/bin/env python3
"""Checker and helper CLI for the canon documentation system.

Single file, Python 3.8+ standard library only. Run `canon.py -h` for commands.
"""

import argparse
import contextlib
import datetime
import os
import re
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path

CANON_VERSION = "4"

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
                    self.problem("ERROR", rel, "duplicate id {}, also {}; run `canon.py renumber <path>` on the doc "
                                 "this branch added".format(doc.id, self.by_id[doc.id].rel))
                else:
                    self.by_id[doc.id] = doc
                self.by_path[path] = doc
        self.docs.sort(key=Doc.sort_key)

    def get(self, doc_id):
        doc = self.by_id.get(doc_id)
        if doc is None:
            sys.exit("canon: unknown document {}".format(doc_id))
        return doc

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

    def tree_ids(self, ref):
        """Map id -> path for the doc files in a commit's tree."""
        listing = git(self.root, "ls-tree", "-r", "-z", "--name-only", ref)
        if listing is None:
            sys.exit("canon: unknown ref " + ref)
        ids = {}
        for rel in listing.split("\0"):
            match = FILE_RE.match(rel.rsplit("/", 1)[-1])
            if match and (rel.startswith("docs/") or "/docs/" in rel):
                ids.setdefault(match.group(1) + match.group(2) + match.group(3), rel)
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
    gate = (doc.type == "D" and status in ("accepted", "active")) or (doc.type == "P" and status == "accepted")
    if gate and reviewed != doc.revision:
        repo.problem("ERROR" if strict else "WARN", rel, "revision {} is not reviewed (reviewed: {}); pass the review "
                     "gate, then set `reviewed` and `reviewers`".format(doc.revision, reviewed))
    if doc.type == "P" and status == "in-progress" and reviewed is None:
        err("plan in progress without `reviewed`")

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
            landed = old_fm.get("reviewed", reviewed)
            planned = any(p.type == "P" and not p.archived and doc.id in plan_designs(p) for p in repo.docs)
            fix = (doc, "implemented", landed) if isinstance(landed, int) and not planned else None
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
    Returns the files whose link texts changed.
    """
    renamed, adopted = renamed or {}, adopted or {}
    touched = set()

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
                touched.add(path)
            if dest in adopted and not ref and not match.group(1):
                label = adopted[dest] + ("§" + anchor if anchor else "") + ": " + (match.group(2) or adopted[dest])
                edits.setdefault(i, []).append((match.start(2), match.end(2), label))
                touched.add(path)
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
    return touched


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
def id_lock(repo):
    """Serialise id allocation between canon commands running in this checkout."""
    path = repo.root / LOCAL_DIR / "id.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.time() + 60
    while True:
        try:
            os.close(os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY))
            break
        except FileExistsError:
            try:
                if time.time() - path.stat().st_mtime > 30:
                    path.unlink()
                    continue
            except FileNotFoundError:
                continue
            if time.time() > deadline:
                sys.exit("canon: {} is held by another canon command; delete it if none is running"
                         .format(posix_rel(path, repo.root)))
            time.sleep(0.05)
    try:
        yield
    finally:
        with contextlib.suppress(FileNotFoundError):
            path.unlink()


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
    if doc.suffix:
        sys.exit("canon: renumber the parent design; sub-designs follow it")
    used = used_numbers(repo, doc.type)
    if args.base:
        used |= {int(FULL_ID_RE.match(i).group(2)) for i in repo.tree_ids(args.base) if i[0] == doc.type}
    if args.new:
        match = FULL_ID_RE.match(args.new)
        if not match or match.group(1) != doc.type or match.group(3):
            sys.exit("canon: new id must be a top-level {} id".format(doc.type))
        number = int(match.group(2))
        if number in used:
            sys.exit("canon: {} is already used".format(args.new))
    else:
        number = max(used) + 1
    digits = str(number).zfill(3)
    group = [doc] + [d for d in repo.docs if d.type == "D" and d.suffix and d.number == doc.number
                     and d.root is doc.root and doc.type == "D"]
    renamed, moves = {}, {}
    for d in group:
        new_id = d.type + digits + d.suffix
        renamed[d.path] = (d.id, new_id)
        moves[d.path] = d.path.with_name("{}-{}.md".format(new_id, d.slug))
        attachment = d.path.parent / d.id
        if attachment.is_dir():
            moves[attachment] = d.path.parent / new_id
    touched = rewrite_for_moves(repo, moves, renamed)
    id_map = dict(renamed.values())
    # An id another doc still has (a collision after rebase) changes only where a link shows which doc is meant.
    shared = {old for old in id_map if any(d.id == old and d.path not in renamed for d in repo.docs)}
    unshared = {old: new for old, new in id_map.items() if old not in shared}
    kept = []
    for d in repo.docs:
        mapping = id_map if d.path in renamed or d.path in touched else unshared
        text = d.path.read_text(encoding="utf-8")
        new_text = remap_ids(d, text, mapping, renamed.get(d.path))
        if new_text != text:
            d.path.write_text(new_text, encoding="utf-8")
        if mapping is unshared and shared & referenced_ids(d):
            kept.append(d.rel)
    move_paths(repo, moves)
    write_indexes(Repo())
    for old, new in id_map.items():
        print("{} -> {}".format(old, new))
    if kept:
        print("kept {} in {}: another doc still has that id; change the entries that meant this doc"
              .format(", ".join(sorted(shared)), ", ".join(kept)))
    print("run `canon.py check --fix` to finish")
    return 0


def referenced_ids(doc):
    """Ids a doc names in `refs`, `based_on` and `moved` dispositions."""
    ids = set(doc.as_list("refs")) | plan_designs(doc)
    if doc.type == "R":
        ids |= {disp.split(" ", 1)[1].strip() for _f, _s, disp in review_findings(doc)[0] if disp.startswith("moved ")}
    return ids


def remap_ids(doc, text, id_map, own=None):
    """Rewrite ids in `refs`, `based_on` and `moved` dispositions; when the doc itself is renumbered
    (`own` = (old, new)), also its H1 and its finding ids."""
    fm = parse_frontmatter(text.split("\n"))[0] or {}
    for key in ("refs", "based_on"):
        values = fm.get(key)
        if isinstance(values, list):
            mapped = []
            for value in values:
                head, sep, tail = value.partition("@")
                mapped.append(id_map.get(head, head) + sep + tail)
            if mapped != values:
                text = set_field(text, key, mapped)
    if doc.type == "R" and id_map:
        alt = "|".join(re.escape(i) for i in sorted(id_map, key=len, reverse=True))
        text = re.sub(r"(?m)^(\s*\|.*\|\s*moved\s+)(" + alt + r")(\s*\|\s*)$",
                      lambda m: m.group(1) + id_map[m.group(2)] + m.group(3), text)
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

    p = sub.add_parser("renumber", help="give a doc a new id and rewrite every link to it")
    p.add_argument("target", help="doc id, or its path when the id is duplicated")
    p.add_argument("new", nargs="?", help="new id (default: next free)")
    p.add_argument("--base", help="also avoid ids present on this ref, e.g. origin/main")
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

    args = parser.parse_args(argv)
    return args.func(Repo(), args)


if __name__ == "__main__":
    sys.exit(main())
