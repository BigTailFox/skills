---
status: active
created: 2026-10-30
updated: 2026-10-30
revision: 1
modules: [canon]
summary: The generated doc index in each docs root's README.md and archived/README.md, its markers and format, the commands that regenerate it and check's index errors.
refs: [D004]
owns: [docs-index]
paths: [skills/governance/canon/scripts/canon.py, tests/test_canon.py]
reviewed: 1
reviewers: [claude-opus-5.5]
implemented: 1
---

# D005: Docs index

## Goals

1. Each docs root lists every numbered doc it holds, with its id, title, status, known issue count, summary, owned topics and modules, in a generated index that the `AGENTS.md` block points agents to.
2. Nobody edits an index by hand: the commands that create, move or archive docs regenerate it, `check` fails while it is out of date and `check --fix` regenerates it. The hand-written text around the index in `docs/README.md` stays as it is.

Out of scope: what `init` writes into a new `docs/README.md` and the union-merge lines it adds to `.gitattributes` ([D004§init: init](D004-project-setup.md#init)); the frontmatter and Known issues tables the entries read (the `canon` skill).

## Spec

### Index files

Each docs root (the `canon` skill's Layout) whose `docs/` directory exists has two index files:

- `docs/README.md` holds the index of the root's docs outside `archived/`, from a start marker through an end marker, the HTML comments `canon:index:start` and `canon:index:end`. The text before and after them is hand-written.
- `docs/archived/README.md` holds the index of the root's archived docs and nothing else: `# Archived docs`, a blank line, the index and a newline. It is written once the root has an archived doc, and kept up to date while the file exists.

### Format

An index is the start marker, a blank line, its groups, a blank line and the end marker, such as these groups:

```markdown
### Designs

- [D001: Auth](designs/D001-auth.md) · active · 2 known issues · Token issuing and refresh. · owns: auth-token, session · modules: auth
- [D001A: Sessions](designs/D001A-sessions.md) · draft · ?

### Plans

- [P001: Refresh rotation](plans/P001-refresh-rotation.md) · in-progress · Rotate refresh tokens. · modules: auth
```

- There is one group per type that has docs, in the order Designs, Plans, Investigations, Reviews, Experiments, Concepts. A group is a `### ` heading naming the type's directory, capitalized, a blank line and one line per doc; a blank line separates groups. Within a group, docs follow their numbers, each design's sub-designs after it in letter order.
- A doc's line is `- ` and these parts joined by ` · `: the link `[<id>: <title>](<path>)`, its path relative to the index file's directory; the status; for a design that lists known issues, `1 known issue` or `<n> known issues`; the summary; `owns: <topics>` and `modules: <modules>`, comma-separated and left out when empty. A missing title, an absent `status` field and an empty or absent summary show as `?`; a title is missing when the doc's H1 does not start with `<id>: `.
- An index with no doc to list holds `No documents.` between its markers, with a blank line on each side.

### Regeneration

- `index`, `new`, `adopt`, `archive`, `rename`, `renumber` and `init` regenerate the index files of every docs root after their other changes, and write only the files whose text changes. `index` prints `wrote <path>` for each file it writes, `<path>` being relative to the repo root; `init` lists them as [D004§init: init](D004-project-setup.md#init) states; the others print nothing for them. `check --fix` regenerates them after its other fixes when it applied a fix or found an index out of date, printing `fixed wrote <path>` for each.
- `docs/README.md` is regenerated thus:
  - A missing file becomes `# Docs`, a blank line, the index and a newline.
  - The index spans from the first start marker through the first end marker after it; regeneration replaces that span and keeps the text around it as it is.
  - Without a start marker, the index is appended: the text without its trailing newlines, a blank line, the index and a newline.
  - When the first start marker in the `docs/README.md` of any docs root, or of the project `init` sets up, has no end marker after it, `check --fix`, `index`, `new`, `adopt`, `archive`, `rename`, `renumber` and `init` change no file and exit with `canon: <path> has an index start marker with no end marker after it; fix the markers and rerun`, `<path>` being relative to the repo root.
- `docs/archived/README.md` is rewritten whole.

### Check

- `check` reports `ERROR <path>: index out of date`, fixable with `--fix`, for each index file whose text differs from what regeneration would write: a missing `docs/README.md`, and a missing `docs/archived/README.md` once the root has an archived doc, included.
- For a `docs/README.md` whose first start marker has no end marker after it, `check` reports `ERROR <path>: index start marker with no end marker after it; fix the markers` in place of comparing it; `check --fix` exits as [Regeneration](#regeneration) states.
- `check` checks the links of an index file, hand-written ones included, only while the file is up to date.

## Decisions

- The index of live docs shares `docs/README.md` with a hand-written intro, between markers, while the archived index has a file of its own, generated whole (`DOCS_README` and `expected_indexes` in `canon.py`; reason unknown, kept as found).
- Index files merge with Git's union driver, so branches never conflict on them, and `check --fix` after a merge or rebase regenerates them (the `canon` skill's Rules; the `.gitattributes` lines in [D004§init: init](D004-project-setup.md#init)).
- A first start marker with no end marker after it is refused rather than repaired, as the canon block's is ([D004§init: init](D004-project-setup.md#init)): no repair can tell where the hand-written text after it resumes (the user's decision).
