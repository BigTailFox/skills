---
status: active
created: 2026-10-30
updated: 2026-11-13
revision: 3
modules: [canon]
summary: The generated doc index of each docs root in README.md and archived/README.md, its markers and format, regenerating or staging it, and check's index errors.
refs: [D004, D006, R003]
owns: [docs-index]
paths: [skills/governance/canon/scripts/canon.py, tests/test_canon.py]
reviewed: 3
reviewers: [claude-opus-5.5, gpt-5.6-sol-high]
approved: 3
implemented: 2
---

# D005: Docs index

## Goals

1. Each docs root lists every numbered doc it holds, with its id, title, status, known issue count, summary, owned topics and modules, in a generated index that the `AGENTS.md` block points agents to.
2. Nobody edits an index by hand: the commands that create, move or archive docs or set their status regenerate it, `check --fix` regenerates it, and `index --staged` stages the index of the staged docs for a commit that holds only part of a checkout's changes. The hand-written text around the index in `docs/README.md` stays as it is.
3. Every commit's index matches its docs: `check --staged`, which the pre-commit hook runs, `check --rev` and `check --base` fail while an index is out of date, and `check` on the work tree, whose index may list another session's uncommitted docs, warns.

Out of scope: what `init` writes into a new `docs/README.md` and the union-merge lines it adds to `.gitattributes` ([D004§init: init](D004-project-setup.md#init)); the frontmatter and Known issues tables the entries read (the `canon` skill); how `check` and `index --staged` read the staged tree or a commit ([D006§check: check](D006-doc-model.md#check)).

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

- `index`, `new`, `adopt`, `archive`, `status`, `rename`, `renumber` and `init` regenerate the index files of every docs root after their other changes, and write only the files whose text changes. `index` prints `wrote <path>` for each file it writes, `<path>` being relative to the repo root; `init` lists them as [D004§init: init](D004-project-setup.md#init) states; the others print nothing for them. `check --fix` without doc arguments regenerates them after its other fixes when it applied a fix or found an index out of date, printing `fixed wrote <path>` for each.
- `docs/README.md` is regenerated thus:
  - A missing file becomes `# Docs`, a blank line, the index and a newline.
  - The index spans from the first start marker through the first end marker after it; regeneration replaces that span and keeps the text around it as it is.
  - Without a start marker, the index is appended: the text without its trailing newlines, a blank line, the index and a newline.
  - When the first start marker in the `docs/README.md` of any docs root, or of the project `init` sets up, has no end marker after it, `check --fix` without doc arguments, `index`, `new`, `adopt`, `archive`, `status`, `rename`, `renumber` and `init` change no file and exit with `canon: <path> has an index start marker with no end marker after it; fix the markers and rerun`, `<path>` being relative to the repo root.
- `docs/archived/README.md` is rewritten whole.

```text
canon.py index [--staged]
```

`index --staged` regenerates the index files of the staged tree, which it reads as `check --staged` does ([D006§check: check](D006-doc-model.md#check)), and stages them, so a commit that holds only some of the work tree's docs gets the index of those docs:

- It computes each index file's text by the rules above from the staged docs and the staged copy of each `docs/README.md`, a copy the staged tree lacks counting as a missing file.
- For each index file whose staged entry is missing or holds other text, it writes the text as a blob with `git hash-object -w --stdin` and stages it with `git update-index --add --cacheinfo <mode>,<blob>,<path>`, keeping the staged entry's mode when it is `100644` or `100755`, else using `100644`, and prints `staged <path>`. It stages nothing else.
- It then writes the work tree's index files whose text changes, as `index` does, printing `wrote <path>` for each, so the work tree's index lists every doc there, those left out of the commit included.
- It ends before changing any file or staging anything, with `canon: index --staged needs a Git checkout` outside Git, `canon: resolve the merge conflicts first` when the Git index has unmerged entries, `canon: the staged <path> has an index start marker with no end marker after it; fix the markers, stage the file and rerun` when the staged copy of a `docs/README.md` has a first start marker with no end marker after it, and the message above when the work tree's copy has one.

### Check

- `check` reports `<LEVEL> <path>: index out of date` for each index file of the tree it checks ([D006§check: check](D006-doc-model.md#check)) whose text differs from what regeneration would write: a missing `docs/README.md`, and a missing `docs/archived/README.md` once the root has an archived doc, included. It is an `ERROR` under `--staged`, `--rev` and `--base`, the message adding `; stage the commit's files, run canon.py index --staged and commit with no paths` under `--staged`, and otherwise a `WARN`; on the work tree `--fix` fixes it.
- For a `docs/README.md` whose first start marker has no end marker after it, `check` reports `ERROR <path>: index start marker with no end marker after it; fix the markers` in place of comparing it; `check --fix` exits as [Regeneration](#regeneration) states.
- `check` checks the links of an index file, hand-written ones included, only while the file is up to date.

## Decisions

- The index of live docs shares `docs/README.md` with a hand-written intro, between markers, while the archived index has a file of its own, generated whole (`DOCS_README` and `expected_indexes` in `canon.py`; reason unknown, kept as found).
- Index files merge with Git's union driver, so branches never conflict on them, and `check --fix` after a merge or rebase regenerates them (the `canon` skill's Rules; the `.gitattributes` lines in [D004§init: init](D004-project-setup.md#init)).
- A first start marker with no end marker after it is refused rather than repaired, as the canon block's is ([D004§init: init](D004-project-setup.md#init)): no repair can tell where the hand-written text after it resumes (the user's decision).
- A stale index fails `check --staged`, `--rev` and `--base`, which check what a commit or a branch holds, and only warns on the work tree: a subagent allowed to edit only its own files cannot regenerate the shared index, and another session's uncommitted docs make the work tree's differ, while what must hold is that each commit's index matches its docs, which the hook and CI check ([R003§r003-f39-stale-index-as-an-error: R003-F39](../archived/reviews/R003-silk-design-phase.md#r003-f39-stale-index-as-an-error); the user's decision, 2026-11-12).
- `index --staged` builds a commit's index from the staged docs rather than staging the work tree's file, whose lines list docs the commit leaves out: staging only one's own lines took sessions a hand-built blob at each commit ([R003§r003-f14-sessions-sharing-one-checkout: R003-F14](../archived/reviews/R003-silk-design-phase.md#r003-f14-sessions-sharing-one-checkout); the user's decision, 2026-11-12). The `--staged` error also asks to stage the commit's files and commit with no paths: under `git commit <paths>` the hook checks a temporary index that `index --staged`, run afterwards, never reaches, and that leaves the files out of the Git index, so the same commit would fail again (gate of D006 r17).
