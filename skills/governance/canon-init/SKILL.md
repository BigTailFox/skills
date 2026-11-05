---
name: canon-init
description: Sets up canon in a repository or monorepo module, migrates existing docs into it, sets up the cross-family reviewer, and upgrades a project's canon.py.
disable-model-invocation: true
---

# Canon init

Read the `canon` skill first; it defines the system. Until the project has its own copy, run `scripts/canon.py` from the `canon` skill directory, written below as `<canon>/scripts/canon.py`. `<copy>` is the project's copy, at the path the canon block of the repo root's `AGENTS.md` names, where `init` keeps it.

## Pick the flow

Run the flow the user names; resume a setup or upgrade that stopped before its end only then. Otherwise, when the repo root's `AGENTS.md` has no canon block, set up the project. In a project set up, run each of these that applies, in order, and when neither does, ask the user which flow to run:

1. **Upgrade** when `<copy>` is missing, or `python3 <copy> --version` prints a lower version than `python3 <canon>/scripts/canon.py --version`.
2. **Set up the cross-family reviewer** when that section's first line says to run it alone.

## Set up a project

1. **Survey.** List existing docs: `docs/`, ADRs, RFCs, design notes, plans, postmortems, benchmark reports. Skip generated and vendored files. Docs by their name outside every docs root, such as READMEs, changelogs and licenses (the `canon` skill's Layout lists the names), and a docs root's own `README.md` stay where they are: they are neither adopted nor folded into D000. Every other file under a docs root is surveyed, whatever its name. In a monorepo, find the modules that deserve their own docs root: independently built or released packages and services.
2. **Propose a mapping** and wait for the user's approval. One line per file: target type (C, D, P, R, E, I), `guides/`, fold into another doc, or leave in place. A doc that describes the whole project, such as an architecture overview, folds into D000. Also name the modules that get a docs root.
3. **Initialize** at the repo root: `python3 <canon>/scripts/canon.py init`. Then run `python3 <copy> init --root <module>` for each module. `init` is idempotent. It copies the script to `<copy>`; when `init` exits because of the copy's path, ask the user for one and rerun with `--script <path>`. It also adds the canon block to `AGENTS.md`, adds union-merge rules for the indexes to `.gitattributes`, adds `.canon/` to `.gitignore`, and creates `docs/README.md` and, at the repo root only, D000, the project overview, from its template.
4. **Adopt** each mapped file: `python3 <copy> adopt <file> <type> [--slug <slug>]`. It keeps git history, assigns the id, prepends frontmatter, appends missing sections and rewrites every link to the file. Move guides into `docs/guides/` with `git mv`. Commit before restructuring so git still recognizes the renames.
5. **Restructure** the adopted docs:
   - Move content into the required sections and replace the guidance comments.
   - Merge standards stated in several docs into the one design that owns them; link from elsewhere.
   - Fill `summary`, `modules`, `owns` and `paths`; only D000 owns `architecture`.
   - Fold each ADR into the owning design as a Decision line, and each doc that describes the whole project into D000, then remove the folded file.
   - Archive docs about finished or obsolete work, e.g. `archive P001 done`, `archive D004 superseded`.
6. **D000.** Fill it from the code, as an as-built revision of HEAD (the `canon` skill's `as-built.md`) that follows D000's rules in the `canon` skill's doc types: Goals; every capability, and every module with its Path, each row linking its designs or reading `none`; the standards designs own across modules; the dependency directions; and the glossary. In a project without code, D000 is the project's first L2 design instead: skip it here and in the Review step, and end setup by giving the user `/canon-design D000`.
7. **AGENTS.md.** Leave the canon block as `init` wrote it, since every `init` at the repo root rewrites it from its template. Move spec-like content from the rest of `AGENTS.md` into designs, and remove instructions that conflict with canon, such as old doc conventions. If the project uses Claude Code, make sure its `CLAUDE.md` imports `AGENTS.md`: create it containing `@AGENTS.md`, or add that line to an existing one that lacks it, unless `CLAUDE.md` and `AGENTS.md` are the same file. Remove the instructions in `CLAUDE.md` that conflict with canon too.
8. **Cross-family reviewer.** Set it up as described below.
9. **CI.** If the project has CI, add `python3 <copy> check --base origin/<default branch>`, with a fetch depth that includes the merge base.
10. **Review.** D000 and every adopted design that describes existing code are as-built revisions of HEAD, each with its `as_built` set: pass each through the review gate at L1, whose status step makes it `active` with `implemented` equal to its revision. Setup ends once they have passed. Write no other as-built design: the first change that alters behavior no design states records what it needs. Show the user D000.
11. Run `python3 <copy> check --fix` until it reports no errors, and commit as `docs: adopt canon`, with a `Refs:` trailer naming D000 and the adopted designs that describe existing code.
12. **Hook.** If the user wants a pre-commit hook, run `python3 <copy> init --hook` now, not earlier: its `check` would reject step 4's commit. When it warns that it cannot write the hook, give the user the command the warning names.

## Set up the cross-family reviewer

Run this alone when the project is set up but this machine has no `.canon/canon-blind-review/reviewer.md`, e.g. after a fresh clone, or when sessions start running on a model family the file has no reviewer of another family for.

1. Ask the user which model families their sessions run on. Each needs a reviewer of another family, so sessions on both Claude and GPT need a GPT reviewer and a Claude reviewer.
2. For each reviewer, ask which tool runs it: an agent CLI such as codex, claude, gemini or Cursor's agent, which works from every host, or a subagent of their host with a named model. Ask for its model, suggesting the family's flagship (a smaller model of another family adds little), and its reasoning effort.
3. Build each command from the tool's `--help`: a new read-only session at that model and effort, the prompt read from `<prompt>`, the final message left in `<out>`. Run it once on a one-line prompt and fix it until it works, noting what the host needed, such as running outside its sandbox.
4. Write the reviewer file as the `canon` skill's workflow describes (Subagents), the user's preferred reviewer first.

Without another family, skip this; reviews then use the manual fallback.

## Upgrade

From the repo root run `python3 <canon>/scripts/canon.py init`; when it exits because of the copy's path, ask the user for one and rerun with `--script <path>`. It replaces an older `<copy>` (by `CANON_VERSION`), refreshes the `AGENTS.md` block between its markers and gives a project without D000 one, as below; everything else is kept. Then run `check --fix` and fix what the new version still reports, apart from D000's guidance, which the D000 work below replaces. `--fix` gives `implemented: 1` only to an active design never revised and without an open plan; give any other active design the revision its code fully implements, found by comparing the code with each revision of the spec in the git history, and the open plan's `based_on` when there is one. A plan in progress whose `reviewed` is below its `revision` passes the review gate before its slices continue.

When the project had no D000, `init` prints how it got one:

- **Moved** the design that owns `architecture` to D000, with its sub-designs, attachments, known issues and every reference to it, and appended the subsections D000 lacks at the end of `## Spec`: commit `init`'s output as it is, so Git keeps the rename, with `--no-verify` when a pre-commit hook runs `check`, since the guidance `init` appended fails `check` until the rewrite below replaces it. Then bump D000's `revision` and make that revision an as-built revision of HEAD (the `canon` skill's `as-built.md`). Rewrite Goals as D000's, fold the old sections of its Spec into the four subsections, fill what is still missing as setup's D000 step says, and narrow `paths` to the files that embody the architecture, dropping every directory and glob; the code those entries covered shows in `audit`'s coverage until designs cover it. Then pass the review gate at L1.
- **Created** D000 from its template, since no design owns `architecture`: fill it and pass its gate as setup's D000 and Review steps say.
- **Refused**, because the design owning `architecture` is a sub-design or lies under a module's docs root, or several designs own it: take `architecture` out of the `owns` the message names and rerun `init`. When no design owns it any more, `init` creates D000: fill it as above, folding in what the designs that dropped `architecture` state about the whole project.

## Add a module

Run `python3 <copy> init --root <module> --script <copy>`, then add the module's row to D000's Modules table, or update the row it has, linking the designs in the module's docs root.
