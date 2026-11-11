---
status: active
created: 2026-10-29
updated: 2026-11-11
revision: 4
modules: [canon]
summary: Project setup and upgrades with canon.py init, migration of existing docs with adopt, and the canon-init flows for setup, upgrade and new modules.
refs: [D000, D001, D002, D003, D005]
owns: [project-setup]
paths: [skills/governance/canon/scripts/canon.py, tests/test_canon.py, skills/governance/canon-init/SKILL.md, skills/governance/canon-sync/SKILL.md]
reviewed: 4
reviewers: [claude-opus-5.5]
implemented: 4
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

- The project is the repo root, or the module directory `--root` names. A `--root` that is not an existing directory inside the repository makes `init` change no file and exit with `canon: --root <dir> is not a directory inside the repository`. A run with nothing to change prints `canon init: nothing to do`; otherwise `init` prints one line per change, such as `created <path>`, `updated <path>` and `wrote <index>`.
- With unmerged entries in the Git index, `init` exits with `canon: resolve the merge conflicts first` before changing any file.
- **Copy.** The copy's path is `--script`; else the path the canon block of the repo root's `AGENTS.md` names: the rest of the first code span between its markers that starts with `python3 `, such as `scripts/canon.py` in `` `python3 scripts/canon.py` ``; else, without such a block or span, `scripts/canon.py`. This holds for a module run too. `init` changes no file and exits, checking in this order:
  - when the copy's path is absolute, holds whitespace or, with `.` and `..` resolved but not symbolic links, leads out of the repository, with ``canon: the copy's path <path> is not a relative path inside the repository without whitespace; pass `--script` with one``;
  - on a module run whose `--script` names another file than the block's path, with ``canon: the canon block of AGENTS.md names <block path>; move the copy with `init --script <path>` at the repo root first``.

  When the copy's path resolves to the running `canon.py`, `init` leaves it. Otherwise it reads the `CANON_VERSION = "<n>"` line of the file there:
  - no file, or an older version: writes the running `canon.py` there with mode 755 and prints `created <path>` or `updated <path>`;
  - a newer version: keeps the file and prints `warning: <path> is v<n>, newer than this canon.py (v<m>); kept it`;
  - the same version with other content: keeps the file and prints a warning that ends in `cp <running canon.py> <path>`, to run unless the copy has local edits to keep;
  - a file without that line, which is no copy of `canon.py`: changes no file and exits with ``canon: <path> is not a copy of canon.py; move it or pass `--script` with another path``.

  At the repo root, a `--script` that names another file than the block's path changes the copy's path: the new path follows the rules above, the block then names it, and a pre-commit hook holding exactly what `--hook` writes for the old path is rewritten for the new one. The old copy stays; when it is a copy of `canon.py` inside the repository, `init` prints ``warning: moved the copy from <old path>; remove it and replace its path where files still name it, such as each `docs/README.md` and CI``.
- **Repository files.** `.gitattributes` gets each missing line of `**/docs/README.md merge=union` and `**/docs/archived/README.md merge=union`, and `.gitignore` gets `.canon/` unless a line already names `.canon`, with or without slashes. Both are at the repo root and are created when missing.
- **`AGENTS.md`.** A run without `--root` writes the canon block into the repo root's `AGENTS.md`: the `## Docs` section of the template in `canon.py`, between a start and an end marker, the HTML comments `canon:agents:start` and `canon:agents:end`. The section tells an agent without the skills to ask the user to install them with `npx skills add BigTailFox/skills -g -s '*'`, which prompts for the agents to install to; it names D000 and the index ([D002§project-overview-d000: D000](D002-overview-and-as-built.md#project-overview-d000)), and its Tool line reads ``- Tool: `python3 <copy>` from the repo root (`-h` lists commands). …``. Without `AGENTS.md`, `init` creates one holding `# AGENTS.md` and the block. Without a start marker, it appends the block; otherwise it replaces the text from the first start marker to the first end marker after it. A start marker in the repo root's `AGENTS.md` with no end marker after it makes every run, a module's included, change no file and exit with ``canon: the repo root's AGENTS.md has a canon block start marker with no end marker after it; fix the markers and rerun `init` ``.
- A module run leaves the repo root's `AGENTS.md` alone. A module without an `AGENTS.md` gets one holding `# AGENTS.md` and a line that links the module's `docs/README.md` and says the repo root's `AGENTS.md` defines the docs rules; a module's existing `AGENTS.md` stays as it is.
- **Docs index.** When the project's `docs/README.md` is missing, `init` creates it with an intro that names `python3 <copy> find <words>` and an `## Index` heading. Each run then regenerates every index ([D005§regeneration: regeneration](D005-docs-index.md#regeneration)).
- **D000.** At the repo root only, as [D002§project-overview-d000: D000](D002-overview-and-as-built.md#project-overview-d000) states.
- **`--hook`.** In a Git checkout, `init` writes the pre-commit hook at the path `git rev-parse --git-path hooks/pre-commit` prints, holding `#!/bin/sh` and `exec python3 <copy> check`, with mode 755. An existing hook stays, and `init` prints ``kept the existing pre-commit hook; add `python3 <copy> check` to it``. Outside Git, `--hook` does nothing.
- When `init` cannot write the hook or rewrite it for a moved copy, such as where `.git` is read-only, it still finishes every other step and prints `warning: cannot write the pre-commit hook: <reason>; ` followed by ``rerun `python3 <copy> init --hook` where .git is writable`` for a new hook, or ``replace <old path> with <copy> in it where .git is writable, before removing <old path>`` for a rewrite.

### adopt

```text
canon.py adopt FILE TYPE [--slug SLUG] [--title TITLE] [--root DIR]
```

- TYPE is a letter of C, D, P, R, E and I in either case, or a type's directory name, plural or singular, such as `designs` or `design`.
- The project is `--root`, a project directory or its `docs/`, else the nearest directory above FILE that holds an `AGENTS.md`, up to the repo root. The doc gets the next free id of its type, which history keeps taken as [D002§project-overview-d000: D000](D002-overview-and-as-built.md#project-overview-d000) states, allocated under the lock `.canon/id.lock`, and moves to `<project>/docs/<type directory>/<id>-<slug>.md`. SLUG defaults to FILE's name without `.md`, lowercased, each run of characters other than `a-z` and `0-9` replaced by one `-`, trimmed of `-`, and `doc` when nothing is left.
- Every relative inline link, `[text](target)` outside code, that points at FILE, or into it with an anchor, follows the move, in each `.md` file Git tracks or would add, or outside Git in each `.md` file outside directories named `node_modules`, `venv` or starting with `.`, and FILE's own inline links are rewritten for its new directory; a root-absolute link (`/path`) stays root-absolute. A rewritten target percent-encodes whitespace, `%`, `#`, `?`, `(` and `)` in its path, such as a space as `%20`, and keeps every other character as it is, so it stays a link. Reference-style definitions, HTML links and other file extensions are not rewritten; `check` reads only these inline links too. A link to FILE, not an image, whose text is not a reference gets the text `<id>: <text>`, or `<id>§<anchor>: <text>` when it has an anchor, the text defaulting to the id when empty.
- FILE's frontmatter is dropped, printing `dropped frontmatter fields: <names>`, and replaced with a new doc's frontmatter for the type: its first status, `created` and `updated` today, `revision: 1`, empty `modules`, `summary` and `refs`, and empty `owns` and `paths` for a design or `based_on` for a plan. FILE's first H1 becomes `# <id>: <title>`, where TITLE defaults to that H1's text, else to the slug with each `-` replaced by a space and the first letter capitalized; without an H1, that line is prepended. Each section the type requires that FILE lacks is appended as `## <name>` with a guidance comment asking for the matching adopted content.
- In a Git checkout the move is a `git mv`, so history follows the file; outside Git, or when Git refuses the move, as for an untracked FILE, it is a plain rename. `adopt` then regenerates the indexes ([D005§regeneration: regeneration](D005-docs-index.md#regeneration)) and prints `<old path> -> <new path>`.
- `adopt` exits without changing a file when FILE is not an existing `.md` file (`canon: <file> is not a markdown file`) or is already a canon doc (`canon: <file> is already a canon doc`), when SLUG is not kebab-case (`canon: slug must be kebab-case`), TYPE is unknown (`canon: unknown type <type>; use one of C D P R E I`) or the project has no `AGENTS.md` (``canon: no AGENTS.md at <absolute path>; set the project up with `canon.py init` first``), when the Git index has unmerged entries, and when another command holds the id lock for 60 s.

### The canon-init skill

- Until the project has its own copy, the skill runs `scripts/canon.py` from the `canon` skill's directory. In a project already set up, `<copy>` is the path the root canon block names, where `init` keeps the copy.
- The skill runs the flow the user names. Otherwise it runs Setup when the repo root's `AGENTS.md` has no canon block. In a project set up, it runs, in this order, Upgrade when the copy is missing or its `--version` is below that of the `canon` skill's `canon.py`, then the reviewer setup when [D003§reviewers: reviewers](D003-subagents.md#reviewers) says to run it alone; when neither holds, it asks the user which flow to run. A Setup or Upgrade that stopped before its end resumes only when the user names it.
- **Setup**, in order:
  1. Survey the existing docs, skipping generated and vendored files and leaving docs by their name and each docs root's `README.md` in place ([D002§setup: setup](D002-overview-and-as-built.md#setup)). In a monorepo, find the modules that get a docs root: independently built or released packages and services.
  2. Propose one line per file, naming its type, `guides/`, the doc it folds into or that it stays in place, and the modules that get a docs root; wait for the user's approval.
  3. Run `init` at the repo root, then `init --root <module>` for each module. When `init` exits because of the copy's path, ask the user for one and rerun with `--script <path>`.
  4. `adopt` each mapped file and move guides into `docs/guides/` with `git mv`. Commit before restructuring, so Git still pairs the renames.
  5. Restructure: move content into the required sections, state each standard only in the design that owns it, fill `summary`, `modules`, `owns` and `paths`, fold each ADR into its design as a Decision line, removing the ADR, fold docs about the whole project into D000 as [D002§setup: setup](D002-overview-and-as-built.md#setup) states, and archive docs about finished or obsolete work.
  6. Write D000 as [D002§setup: setup](D002-overview-and-as-built.md#setup) states.
  7. In `AGENTS.md`, leave the canon block as `init` wrote it, move spec-like content from the rest into designs and remove instructions that conflict with canon, such as old doc conventions. A project that uses Claude Code gets the line `@AGENTS.md` in its `CLAUDE.md`, created when missing, unless `CLAUDE.md` already imports it or is the same file as `AGENTS.md`, and loses the instructions there that conflict with canon too.
  8. Set up the reviewer file ([D003§reviewers: reviewers](D003-subagents.md#reviewers)).
  9. In a project with CI, add `python3 <copy> check --base origin/<default branch>`, with a fetch depth that reaches the merge base.
  10. Pass D000 and the adopted designs that describe existing code through their gates ([D002§setup: setup](D002-overview-and-as-built.md#setup)).
  11. Run `check --fix` until it reports no error, and commit as `docs: adopt canon` with a `Refs:` trailer naming D000 and those designs.
  12. When the user wants a pre-commit hook, run `python3 <copy> init --hook`, and give the user its warning's command when it cannot write the hook.
- **Upgrade**: from the repo root, run `python3 <canon>/scripts/canon.py init`, where `<canon>` is the `canon` skill's directory; when it exits because of the copy's path, ask the user for one and rerun with `--script <path>`. Then run `check --fix`, and fix what the new version still reports apart from D000's guidance. `--fix` gives `implemented: 1` only to an active design never revised and without an open plan; every other active design gets the revision its code fully implements, found by comparing the code with each revision of its spec in the Git history, or the open plan's `based_on`. A plan in progress whose `reviewed` is below its `revision` passes the review gate before its slices continue. When `init` moved the design owning `architecture` to D000, commit its output as it is before anything else, so Git keeps the rename, with `--no-verify` when a pre-commit hook runs `check`, since the guidance `init` appended fails `check` until the D000 work replaces it. A project that had no D000 then continues as [D002§setup: setup](D002-overview-and-as-built.md#setup) states.
- **Add a module**: run `python3 <copy> init --root <module> --script <copy>`, then add or update the module's row in D000's Modules table, linking the designs in the module's docs root.
- `canon-sync`'s audit compares the copy's `--version` with that of the `canon` skill's `scripts/canon.py`. An older copy is upgraded as above; a copy of the same version with other content is shown to the user as a diff before it is replaced, since it may hold local edits.

## Known issues

| ID | Severity | Issue | Source | Since | Next |
|----|----------|-------|--------|-------|------|
| D004-K1 | major | Nothing checks that a project's `canon.py` copy is new enough for the installed skills, so an older copy's errors contradict them; a version 18 copy reports the `as_built` field as unknown | R001-F2 | 2026-11-05 | L2 |
| D004-K2 | minor | `adopt` rewrites the H1, which changes its anchor, and leaves links to the old anchor broken until `check` fails on them | R001-F29 | 2026-11-05 | L1 |
| D004-K3 | minor | D004§adopt restates the link-rewriting rule, and D004§decisions says the commands sharing it have no design, while D006§statuses-and-archiving now owns it with `archive` | D006 gate | 2026-11-11 | L1 |

## Decisions

- The canon block keeps the template's words, also in a project documented in another language, since `init` rewrites it on every run at the repo root (the user's decision).
- `init` without `--script` keeps the copy where the root canon block names it, and refuses rather than move it, so a project set up with `--script` keeps its copy through upgrades and new modules (the user's decision). Add a module still passes `--script <copy>`, since a copy older than `CANON_VERSION` 23 ignores the block.
- Setup installs the pre-commit hook last: the hook's `check` fails on every file step 5 has yet to restructure, so it would reject step 4's commit, which comes first to keep Git's rename pairing (R001-F14).
- Upgrade commits `init`'s move of the design owning `architecture` on its own, with `--no-verify` under a hook running `check`, so Git keeps the rename (the user's decision; f767510, P002's Log).
- `adopt` shares its link rewriting with `archive`, `rename`, `renumber` and `init`'s move of a design to D000, so they encode targets alike; those commands have no design ([D000§capabilities: Capabilities](D000-project-overview.md#capabilities)), and the design that takes them on will own the rule (the user's decision).
- `adopt` replaces FILE's frontmatter instead of merging it, printing the fields it dropped (`adopt_doc` in `canon.py`; reason unknown, kept as found).
