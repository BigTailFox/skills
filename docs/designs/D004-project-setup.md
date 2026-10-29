---
status: active
created: 2026-10-29
updated: 2026-10-29
revision: 1
modules: [canon]
summary: Project setup and upgrades with canon.py init, migration of existing docs with adopt, and the canon-init flows for setup, upgrade and new modules.
refs: [D000, D001, D002, D003]
owns: [project-setup]
paths: [skills/governance/canon/scripts/canon.py, tests/test_canon.py, skills/governance/canon-init/SKILL.md, skills/governance/canon-sync/SKILL.md]
reviewed: 1
reviewers: [claude-opus-5.5]
implemented: 1
---

# D004: Project setup

## Goals

1. One idempotent command, `canon.py init`, sets a repository or a monorepo module up for canon, and the same command upgrades the project's copy of `canon.py`.
2. `canon.py adopt` turns an existing markdown file into a canon doc, keeping its Git history and every inline link to it.
3. The `canon-init` skill takes the user through setting a project up, upgrading it and adding a module.

Out of scope: what `init` does with D000, and the D000 and as-built steps of setup and upgrade ([D002§project-overview-d000: D000](D002-overview-and-as-built.md#project-overview-d000), [D002§setup: setup](D002-overview-and-as-built.md#setup)); the reviewer file `canon-init` writes ([D003§reviewers: reviewers](D003-subagents.md#reviewers)); tracing, which `init` never turns on ([D001§switch-and-storage: switch](D001-skill-telemetry.md#switch-and-storage)).

## Spec

`--script` and the paths in the output are relative to the repo root, the top of the Git work tree or, outside Git, the directory the command runs in; `--root` and FILE are relative to the directory the command runs in.

### init

```text
canon.py init [--root DIR] [--script PATH] [--hook]
```

- The project is the repo root, or the module directory `--root` names. A run with nothing to change prints `canon init: nothing to do`; otherwise `init` prints one line per change, such as `created <path>`, `updated <path>` and `wrote <index>`.
- With unmerged entries in the Git index, `init` exits with `canon: resolve the merge conflicts first` before changing any file.
- **Copy.** The copy's path is `--script`, else `scripts/canon.py`, for a module too. When that path resolves to the running `canon.py`, `init` leaves it. Otherwise it reads the `CANON_VERSION = "<n>"` line of the file there:
  - no file, or an older version: writes the running `canon.py` there with mode 755 and prints `created <path>` or `updated <path>`;
  - a newer version: keeps the file and prints `warning: <path> is v<n>, newer than this canon.py (v<m>); kept it`;
  - the same version with other content: keeps the file and prints a warning that ends in `cp <running canon.py> <path>`, to run unless the copy has local edits to keep;
  - a file without that line, which is no copy of `canon.py`: changes no file and exits with ``canon: <path> is not a copy of canon.py; move it or pass `--script` with another path`` (D004-K1).
- **Repository files.** `.gitattributes` gets each missing line of `**/docs/README.md merge=union` and `**/docs/archived/README.md merge=union`, and `.gitignore` gets `.canon/` unless a line already names `.canon`, with or without slashes. Both are at the repo root and are created when missing.
- **`AGENTS.md`.** A run without `--root` writes the canon block into the repo root's `AGENTS.md`: the `## Docs` section of the template in `canon.py`, between a start and an end marker, the HTML comments `canon:agents:start` and `canon:agents:end`. The section names D000 and the index ([D002§project-overview-d000: D000](D002-overview-and-as-built.md#project-overview-d000)), and its Tool line reads ``- Tool: `python3 <copy>` from the repo root (`-h` lists commands). …``. Without `AGENTS.md`, `init` creates one holding `# AGENTS.md` and the block. Without a start marker, it appends the block; otherwise it replaces the text from the first start marker to the first end marker after it. A start marker with no end marker after it makes `init` change no file and exit with ``canon: AGENTS.md has a canon block start marker with no end marker after it; fix the markers and rerun `init` `` (D004-K3).
- A module run leaves the repo root's `AGENTS.md` alone. A module without an `AGENTS.md` gets one holding `# AGENTS.md` and a line that links the module's `docs/README.md` and says the repo root's `AGENTS.md` defines the docs rules; a module's existing `AGENTS.md` stays as it is.
- **Docs index.** When the project's `docs/README.md` is missing, `init` creates it with an intro that names `python3 <copy> find <words>` and an `## Index` heading. Each run then regenerates every index.
- **D000.** At the repo root only, as [D002§project-overview-d000: D000](D002-overview-and-as-built.md#project-overview-d000) states.
- **`--hook`.** In a Git checkout, `init` writes the pre-commit hook at the path `git rev-parse --git-path hooks/pre-commit` prints, holding `#!/bin/sh` and `exec python3 <copy> check`, with mode 755. An existing hook stays, and `init` prints ``kept the existing pre-commit hook; add `python3 <copy> check` to it``. Outside Git, `--hook` does nothing.

### adopt

```text
canon.py adopt FILE TYPE [--slug SLUG] [--title TITLE] [--root DIR]
```

- TYPE is a letter of C, D, P, R, E and I in either case, or a type's directory name, plural or singular, such as `designs` or `design`.
- The project is `--root`, a project directory or its `docs/`, else the nearest directory above FILE that holds an `AGENTS.md`, up to the repo root. The doc gets the next free id of its type, which history keeps taken as [D002§project-overview-d000: D000](D002-overview-and-as-built.md#project-overview-d000) states, allocated under the lock `.canon/id.lock`, and moves to `<project>/docs/<type directory>/<id>-<slug>.md`. SLUG defaults to FILE's name without `.md`, lowercased, each run of characters other than `a-z` and `0-9` replaced by one `-`, trimmed of `-`, and `doc` when nothing is left.
- Every relative inline link, `[text](target)` outside code, that points at FILE, or into it with an anchor, follows the move, in each `.md` file Git tracks or would add, or outside Git in each `.md` file outside directories named `node_modules`, `venv` or starting with `.`, and FILE's own inline links are rewritten for its new directory; a root-absolute link (`/path`) stays root-absolute. A rewritten target is percent-encoded where the original was, such as a space as `%20` (D004-K4). Reference-style definitions, HTML links and other file extensions are not rewritten; `check` reads only these inline links too. A link to FILE, not an image, whose text is not a reference gets the text `<id>: <text>`, or `<id>§<anchor>: <text>` when it has an anchor, the text defaulting to the id when empty.
- FILE's frontmatter is dropped, printing `dropped frontmatter fields: <names>`, and replaced with a new doc's frontmatter for the type: its first status, `created` and `updated` today, `revision: 1`, empty `modules`, `summary` and `refs`, and empty `owns` and `paths` for a design or `based_on` for a plan. FILE's first H1 becomes `# <id>: <title>`, where TITLE defaults to that H1's text, else to the slug with each `-` replaced by a space and the first letter capitalized; without an H1, that line is prepended. Each section the type requires that FILE lacks is appended as `## <name>` with a guidance comment asking for the matching adopted content.
- In a Git checkout the move is a `git mv`, so history follows the file; outside Git, or when Git refuses the move, as for an untracked FILE, it is a plain rename. `adopt` then regenerates the indexes and prints `<old path> -> <new path>`.
- `adopt` exits without changing a file when FILE is not an existing `.md` file (`canon: <file> is not a markdown file`) or is already a canon doc (`canon: <file> is already a canon doc`), when SLUG is not kebab-case (`canon: slug must be kebab-case`), TYPE is unknown (`canon: unknown type <type>; use one of C D P R E I`) or the project has no `AGENTS.md` (``canon: no AGENTS.md at <absolute path>; set the project up with `canon.py init` first``), when the Git index has unmerged entries, and when another command holds the id lock for 60 s.

### The canon-init skill

- Until the project has its own copy, the skill runs `scripts/canon.py` from the `canon` skill's directory. In a project already set up, `<copy>` is the path the root canon block names, and every `init` gets `--script <copy>`.
- **Setup**, in order:
  1. Survey the existing docs, skipping generated and vendored files and leaving docs by their name and each docs root's `README.md` in place ([D002§setup: setup](D002-overview-and-as-built.md#setup)). In a monorepo, find the modules that get a docs root: independently built or released packages and services.
  2. Propose one line per file, naming its type, `guides/`, the doc it folds into or that it stays in place, and the modules that get a docs root; wait for the user's approval.
  3. Run `init` at the repo root, with `--hook` when the user wants a pre-commit hook, then `init --root <module>` for each module. When `init` exits because `scripts/canon.py` is no copy of `canon.py`, ask the user for another path and rerun with `--script <path>`.
  4. `adopt` each mapped file and move guides into `docs/guides/` with `git mv`. Commit before restructuring, so Git still pairs the renames.
  5. Restructure: move content into the required sections, state each standard only in the design that owns it, fill `summary`, `modules`, `owns` and `paths`, fold each ADR into its design as a Decision line, removing the ADR, fold docs about the whole project into D000 as [D002§setup: setup](D002-overview-and-as-built.md#setup) states, and archive docs about finished or obsolete work.
  6. Write D000 as [D002§setup: setup](D002-overview-and-as-built.md#setup) states.
  7. In `AGENTS.md`, leave the canon block as `init` wrote it (D004-K2), move spec-like content from the rest into designs and remove instructions that conflict with canon, such as old doc conventions. A project that uses Claude Code and has no `CLAUDE.md` gets one holding `@AGENTS.md`.
  8. Set up the reviewer file ([D003§reviewers: reviewers](D003-subagents.md#reviewers)).
  9. In a project with CI, add `python3 scripts/canon.py check --base origin/<default branch>`, with a fetch depth that reaches the merge base.
  10. Pass D000 and the adopted designs that describe existing code through their gates ([D002§setup: setup](D002-overview-and-as-built.md#setup)).
  11. Run `check --fix` until it reports no error, and commit as `docs: adopt canon` with a `Refs:` trailer naming D000 and those designs.
- **Upgrade**: from the repo root, run `python3 <canon>/scripts/canon.py init --script <copy>`, where `<canon>` is the `canon` skill's directory, then `check --fix`, and fix what the new version still reports apart from D000's guidance. `--fix` gives `implemented: 1` only to an active design never revised and without an open plan; every other active design gets the revision its code fully implements, found by comparing the code with each revision of its spec in the Git history, or the open plan's `based_on`. A plan in progress whose `reviewed` is below its `revision` passes the review gate before its slices continue. When `init` moved the design owning `architecture` to D000, commit its output as it is before anything else, so Git keeps the rename, with `--no-verify` when a pre-commit hook runs `check`, since the guidance `init` appended fails `check` until the D000 work replaces it. A project that had no D000 then continues as [D002§setup: setup](D002-overview-and-as-built.md#setup) states.
- **Add a module**: run `python3 <copy> init --root <module> --script <copy>`, then add or update the module's row in D000's Modules table, linking the designs in the module's docs root.
- `canon-sync`'s audit compares the copy's `--version` with that of the `canon` skill's `scripts/canon.py`. An older copy is upgraded as above; a copy of the same version with other content is shown to the user as a diff before it is replaced, since it may hold local edits.

## Known issues

| ID | Severity | Issue | Source | Since | Next |
|----|----------|-------|--------|-------|------|
| D004-K1 | major | `init` overwrites a file at the copy's path that has no `CANON_VERSION` line and prints `created <path>` | as-built 3cbb2b6 | 2026-10-29 | fix |
| D004-K2 | minor | `canon-init`'s setup step 7 asks to keep the canon block short and in the project's language, though the next `init` at the repo root rewrites the block from its template | as-built 3cbb2b6 | 2026-10-29 | fix |
| D004-K3 | major | With a start marker and no end marker after it, `init` either fails with an `IndexError` after writing the copy, `.gitattributes` and `.gitignore`, when an end marker comes earlier, or appends the block, after which the next run deletes the text between the stray start marker and the block | as-built 3cbb2b6 | 2026-10-29 | fix |
| D004-K4 | minor | `adopt` writes a rewritten target decoded, so `other%20doc.md` becomes `other doc.md`, which is no link | as-built 3cbb2b6 | 2026-10-29 | fix |

## Decisions

- The canon block keeps the template's words, also in a project documented in another language, since `init` rewrites it on every run at the repo root (the user's decision).
- Upgrade commits `init`'s move of the design owning `architecture` on its own, with `--no-verify` under a hook running `check`, so Git keeps the rename (the user's decision; f767510, P002's Log).
- `adopt` replaces FILE's frontmatter instead of merging it, printing the fields it dropped (`adopt_doc` in `canon.py`; reason unknown, kept as found).
