---
name: canon-init
description: Sets up the canon documentation system in a repository or monorepo module, migrates existing docs (design notes, ADRs, RFCs, plans, postmortems, benchmarks) into it, and upgrades a project's canon.py copy. Use when the user asks to initialize, install, adopt, migrate to or upgrade canon docs, or to add a docs root for a new module.
disable-model-invocation: true
---

# Canon init

Read the `canon` skill first; it defines the system. Until the project has its own copy, run `scripts/canon.py` from the `canon` skill directory, written below as `<canon>/scripts/canon.py`.

## Set up a project

1. **Survey.** List existing docs: `docs/`, ADRs, RFCs, design notes, plans, postmortems, benchmark reports. Skip READMEs, changelogs, licenses, generated and vendored files. In a monorepo, find the modules that deserve their own docs root: independently built or released packages and services.
2. **Propose a mapping** and wait for the user's approval. One line per file: target type (C, D, P, R, E, I), `guides/`, fold into another doc, or leave in place. Also name the doc that becomes the architecture design, if any, and the modules that get a docs root.
3. **Initialize** at the repo root: `python3 <canon>/scripts/canon.py init`. Add `--no-architecture` when an existing doc becomes the architecture design, and `--hook` when the user wants a pre-commit hook. Then run `python3 scripts/canon.py init --root <module>` for each module. `init` is idempotent. It copies the script to `scripts/canon.py`, adds the canon block to `AGENTS.md`, adds union-merge rules for the indexes to `.gitattributes`, and creates `docs/README.md` and an architecture design skeleton.
4. **Adopt** each mapped file: `python3 scripts/canon.py adopt <file> <type> [--slug <slug>]`. It keeps git history, assigns the id, prepends frontmatter, appends missing sections and rewrites every link to the file. Move guides into `docs/guides/` with `git mv`. Commit before restructuring so git still recognizes the renames.
5. **Restructure** the adopted docs:
   - Move content into the required sections and replace the guidance comments.
   - Merge standards stated in several docs into the one design that owns them; link from elsewhere.
   - Fill `summary`, `modules`, `owns` and `paths`; the architecture design owns `architecture`.
   - Fold each ADR into the owning design as a Decision line and remove the ADR file.
   - Archive docs about finished or obsolete work, e.g. `archive P001 done`, `archive D004 superseded`.
6. **Architecture design.** Fill it from the code: module map (module, path, purpose, owning design), allowed dependency directions, and a glossary of cross-module terms. Make the designs' `paths` cover the main source directories so `which` answers for most files.
7. **AGENTS.md.** Keep the canon block short and in the project's language. Move spec-like content from the rest of `AGENTS.md` into designs, and remove instructions that conflict with canon, such as old doc conventions. If the project uses Claude Code and has no `CLAUDE.md`, create one containing `@AGENTS.md`.
8. **CI.** If the project has CI, add `python3 scripts/canon.py check --base origin/<default branch>`, with a fetch depth that includes the merge base.
9. **Review.** Pass every design that describes existing code through the review gate at L1, so A1 checks it against the code, then set it `active`. Show the user the architecture design.
10. Run `python3 scripts/canon.py check --fix` until clean, and commit as `docs: adopt canon`.

## Upgrade

From the repo root run `python3 <canon>/scripts/canon.py init`. It replaces an older `scripts/canon.py` (by `CANON_VERSION`) and refreshes the `AGENTS.md` block between its markers; everything else is kept. Then run `check` and fix what the new version reports.

## Add a module

Run `python3 scripts/canon.py init --root <module>`, then add the module to the architecture design's module map.
