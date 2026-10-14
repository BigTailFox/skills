---
name: canon-init
description: Sets up canon in a repository or monorepo module, migrates existing docs into it, sets up the cross-family reviewer, and upgrades a project's canon.py.
disable-model-invocation: true
---

# Canon init

Read the `canon` skill first; it defines the system. Until the project has its own copy, run `scripts/canon.py` from the `canon` skill directory, written below as `<canon>/scripts/canon.py`.

## Set up a project

1. **Survey.** List existing docs: `docs/`, ADRs, RFCs, design notes, plans, postmortems, benchmark reports. Skip READMEs, changelogs, licenses, generated and vendored files. In a monorepo, find the modules that deserve their own docs root: independently built or released packages and services.
2. **Propose a mapping** and wait for the user's approval. One line per file: target type (C, D, P, R, E, I), `guides/`, fold into another doc, or leave in place. Also name the doc that becomes the architecture design, if any, and the modules that get a docs root.
3. **Initialize** at the repo root: `python3 <canon>/scripts/canon.py init`. Add `--no-architecture` when an existing doc becomes the architecture design, and `--hook` when the user wants a pre-commit hook. Then run `python3 scripts/canon.py init --root <module>` for each module. `init` is idempotent. It copies the script to `scripts/canon.py`, adds the canon block to `AGENTS.md`, adds union-merge rules for the indexes to `.gitattributes`, adds `.canon/` to `.gitignore`, and creates `docs/README.md` and an architecture design skeleton.
4. **Adopt** each mapped file: `python3 scripts/canon.py adopt <file> <type> [--slug <slug>]`. It keeps git history, assigns the id, prepends frontmatter, appends missing sections and rewrites every link to the file. Move guides into `docs/guides/` with `git mv`. Commit before restructuring so git still recognizes the renames.
5. **Restructure** the adopted docs:
   - Move content into the required sections and replace the guidance comments.
   - Merge standards stated in several docs into the one design that owns them; link from elsewhere.
   - Fill `summary`, `modules`, `owns` and `paths`; the architecture design owns `architecture`.
   - Fold each ADR into the owning design as a Decision line and remove the ADR file.
   - Archive docs about finished or obsolete work, e.g. `archive P001 done`, `archive D004 superseded`.
6. **Architecture design.** Fill it from the code: module map (module, path, purpose, owning design), allowed dependency directions, and a glossary of cross-module terms. Make the designs' `paths` cover the main source directories so `which` answers for most files.
7. **AGENTS.md.** Keep the canon block short and in the project's language. Move spec-like content from the rest of `AGENTS.md` into designs, and remove instructions that conflict with canon, such as old doc conventions. If the project uses Claude Code and has no `CLAUDE.md`, create one containing `@AGENTS.md`.
8. **Cross-family reviewer.** Set it up as described below.
9. **CI.** If the project has CI, add `python3 scripts/canon.py check --base origin/<default branch>`, with a fetch depth that includes the merge base.
10. **Review.** Pass every design that describes existing code through the review gate at L1, so the same-model reviewer checks it against the code, then set it `active` with `implemented` equal to its revision. Show the user the architecture design.
11. Run `python3 scripts/canon.py check --fix` until it reports no errors, and commit as `docs: adopt canon`.

## Set up the cross-family reviewer

Run this alone when the project is set up but this machine has no `.canon/canon-blind-review/reviewer.md`, e.g. after a fresh clone, or when sessions start running on a model family the file has no reviewer of another family for.

1. Ask the user which model families their sessions run on. Each needs a reviewer of another family, so sessions on both Claude and GPT need a GPT reviewer and a Claude reviewer.
2. For each reviewer, ask which tool runs it: an agent CLI such as codex, claude, gemini or Cursor's agent, which works from every host, or a subagent of their host with a named model. Ask for its model, suggesting the family's flagship (a smaller model of another family adds little), and its reasoning effort.
3. Build each command from the tool's `--help`: a new read-only session at that model and effort, the prompt read from `<prompt>`, the final message left in `<out>`. Run it once on a one-line prompt and fix it until it works, noting what the host needed, such as running outside its sandbox.
4. Write the reviewer file as the `canon` skill's workflow describes (Subagents), the user's preferred reviewer first.

Without another family, skip this; reviews then use the manual fallback.

## Upgrade

From the repo root run `python3 <canon>/scripts/canon.py init`. It replaces an older `scripts/canon.py` (by `CANON_VERSION`) and refreshes the `AGENTS.md` block between its markers; everything else is kept. Then run `check --fix` and fix what the new version still reports. `--fix` gives `implemented: 1` only to an active design never revised and without an open plan; give any other active design the revision its code fully implements, found by comparing the code with each revision of the spec in the git history, and the open plan's `based_on` when there is one. A plan in progress whose `reviewed` is below its `revision` passes the review gate before its slices continue.

## Add a module

Run `python3 scripts/canon.py init --root <module>`, then add the module to the architecture design's module map.
