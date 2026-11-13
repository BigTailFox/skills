---
name: canon-init
description: Sets up canon in a repository or monorepo module, migrates existing docs into it, sets up the cross-family reviewer, and upgrades the project's canon install.
disable-model-invocation: true
---

# Canon init

Read the `canon` skill first; it defines the system. `canon.py` means the `canon` skill's `scripts/canon.py`, as its Tool section says; run it from the repo root. On a first run from a user install, with canon installed for every project but not in this one, `canon.py` refuses to run: install canon in the project first, as the `canon` skill's Tool section says.

## Pick the flow

Run the flow the user names; resume a setup or upgrade that stopped before its end only then. Otherwise, when the repo root's `AGENTS.md` has no canon block, set up the project. In a project set up, run each of these that applies, in order, and when neither does, ask the user which flow to run:

1. **Upgrade** when the project's canon version, the `canon version <n> or later` in the Tool line of the canon block, is below `canon.py --version`, or the block records none.
2. **Set up the cross-family reviewer** when that section says to run it alone.

## Set up a project

1. **Survey.** List existing docs: `docs/`, ADRs, RFCs, design notes, plans, postmortems, benchmark reports. Skip generated and vendored files. Docs by their name outside every docs root, such as READMEs, changelogs and licenses (the `canon` skill's Layout lists the names), and a docs root's own `README.md` stay where they are: they are neither adopted nor folded into D000. Every other file under a docs root is surveyed, whatever its name. In a monorepo, find the modules that deserve their own docs root: independently built or released packages and services.
2. **Propose a mapping** and wait for the user's approval. One line per file: target type (C, D, P, R, E, I), `guides/`, fold into another doc, or leave in place. A doc that describes the whole project, such as an architecture overview, folds into D000. Also name the modules that get a docs root, and ask whether to commit the installed skills, `.agents/skills/` and the agents' links to it such as `.claude/skills/`, which canon recommends so that every clone, worktree and CI job runs the pinned release with nothing to install, or only `skills-lock.json`, from which `npx skills experimental_install` restores them.
3. **Initialize** at the repo root: `canon.py init`. Then run `canon.py init --root <module>` for each module. `init` is idempotent. It adds the canon block to `AGENTS.md`, recording the project's canon version, adds union-merge rules for the indexes to `.gitattributes`, adds `.canon/` to `.gitignore`, and creates `docs/README.md` and, at the repo root only, D000, the project overview, from its template.
4. **Adopt** each mapped file: `canon.py adopt <file> <type> [--slug <slug>]`. It keeps git history, assigns the id, prepends frontmatter, appends missing sections and rewrites every link to the file. Move guides into `docs/guides/` with `git mv`. Commit before restructuring so git still recognizes the renames, with the installed skills, or with `skills-lock.json` alone and the installed skills' paths in `.gitignore`, as step 2 settled.
5. **Restructure** the adopted docs:
   - Move content into the required sections and replace the guidance comments.
   - Merge standards stated in several docs into the one design that owns them; link from elsewhere.
   - Fill `summary`, `modules`, `owns` and `paths`; only D000 owns `architecture`.
   - Fold each ADR into the owning design as a Decision line, and each doc that describes the whole project into D000, then remove the folded file.
   - Archive docs about finished or obsolete work, e.g. `archive P001 done`, `archive D004 superseded`.
6. **D000.** Fill it from the code, as an as-built revision of HEAD (the `canon` skill's `as-built.md`) that follows D000's rules in the `canon` skill's doc types: Goals; every capability, and every module with its Path, each row linking its designs or reading `none`; the standards designs own across modules; the dependency directions; and the glossary. In a project without code, D000 is the project's first L2 design instead: skip it here and in the Review step, and end setup by giving the user `/canon-design D000`.
7. **AGENTS.md.** Leave the canon block as `init` wrote it, since every `init` at the repo root rewrites it from its template. Move spec-like content from the rest of `AGENTS.md` into designs, and remove instructions that conflict with canon, such as old doc conventions. If the project uses Claude Code, make sure its `CLAUDE.md` imports `AGENTS.md`: create it containing `@AGENTS.md`, or add that line to an existing one that lacks it, unless `CLAUDE.md` and `AGENTS.md` are the same file. Remove the instructions in `CLAUDE.md` that conflict with canon too.
8. **Cross-family reviewer.** Set it up as described below.
9. **CI.** If the project has CI, add a job that runs `python3 .agents/skills/canon/scripts/canon.py check --base origin/<default branch>`, with a fetch depth that includes the merge base, after `npx skills experimental_install` when the project commits only `skills-lock.json`.
10. **Review.** D000 and every adopted design that describes existing code are as-built revisions of HEAD, each with its `as_built` set: pass each through the review gate at L1, whose status step makes it `active` with `implemented` equal to its revision. Setup ends once they have passed. Write no other as-built design: the first change that alters behavior no design states records what it needs. Show the user D000.
11. Run `canon.py check --fix` until it reports no errors, and commit as `docs: adopt canon`, with a `Refs:` trailer naming D000 and the adopted designs that describe existing code.
12. **Hook.** If the user wants a pre-commit hook, run `canon.py init --hook` now, not earlier: its `check` would reject step 4's commit. When it warns that it cannot write the hook, give the user the command the warning names.

## Set up the cross-family reviewer

Follow the reviewer setup in the `canon` skill's workflow (Subagents), covering every model family the user's sessions run on, after copying an earlier setup's reviewer file as that section says. Run it, as setup step 8 or alone, only when the reviewer file gives this session's family neither a reviewer this host can run nor a `none` that covers this host, e.g. on a new machine; run it alone whenever the user names this flow.

## Upgrade

A project whose canon block records no canon version kept a copy of `canon.py` and needs canon installed: unless it is, install it as the `canon` skill's Tool section says. Either way, ask whether to commit the installed skills or only `skills-lock.json`, as setup step 2 does, and commit them with the upgrade, as setup step 4 does. Otherwise, when a newer release than the one `skills-lock.json` records for `canon` exists, found as the `canon` skill's Tool section finds the newest, offer to install it; on a yes, install it, read this skill and the `canon` skill again from the new install and run its `canon.py` from here on.

From the repo root run `canon.py init`. It rewrites the canon block of `AGENTS.md` with the running canon version, replaces a pre-commit hook that ran a copy, and gives a project without D000 one, as below; everything else is kept. When it warns that the project no longer keeps a copy, ask the user whether to remove the copy, then replace `python3 <path>` where files still name it, `<path>` being the copy the warning names: in CI with the job of setup step 9, elsewhere, such as in each `docs/README.md`, with `canon.py`. Then run `check --fix` and fix what the new version still reports, apart from D000's guidance, which the D000 work below replaces. `--fix` gives `implemented: 1` only to an active design never revised and without an open plan; give any other active design the revision its code fully implements, found by comparing the code with each revision of the spec in the git history, and the open plan's `based_on` when there is one. A plan in progress whose `reviewed` is below its `revision` passes the review gate before its slices continue.

When the project had no D000, `init` prints how it got one:

- **Moved** the design that owns `architecture` to D000, with its sub-designs, attachments, known issues and every reference to it, and appended the subsections D000 lacks at the end of `## Spec`: commit `init`'s output as it is, so Git keeps the rename, with `--no-verify` when a pre-commit hook runs `check`, since the guidance `init` appended fails `check` until the rewrite below replaces it. Then bump D000's `revision` and make that revision an as-built revision of HEAD (the `canon` skill's `as-built.md`). Rewrite Goals as D000's, fold the old sections of its Spec into the four subsections, in their order, fill what is still missing as setup's D000 step says, and narrow `paths` to the files that embody the architecture, dropping every directory and glob; the code those entries covered shows in `audit`'s coverage until designs cover it. Then pass the review gate at L1.
- **Created** D000 from its template, since no design owns `architecture`: fill it and pass its gate as setup's D000 and Review steps say.
- **Refused**, because the design owning `architecture` is a sub-design or lies under a module's docs root, or several designs own it: take `architecture` out of the `owns` the message names and rerun `init`. When no design owns it any more, `init` creates D000: fill it as above, folding in what the designs that dropped `architecture` state about the whole project.

## Add a module

Run `canon.py init --root <module>`, then add the module's row to D000's Modules table, or update the row it has, linking the designs in the module's docs root.
