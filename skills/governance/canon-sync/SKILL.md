---
name: canon-sync
description: Brings a project's canon docs in line with its code. Runs the docs step after a change (update governing designs, archive finished plans, reviews, investigations and experiments, fix stale READMEs, prepare the commit trailer), reconciles docs after merges, and audits doc health (stale designs, idle docs, due reviews, outdated canon.py). Use when the user asks to sync, update, reconcile or audit docs, before committing finished work, or after merging branches.
disable-model-invocation: true
---

# Canon sync

Read the `canon` skill first. `canon.py` means the project copy named in `AGENTS.md`.

## After a change

1. Scope the change: uncommitted work by default, or a branch with `--base <ref>`. Run `canon.py affected [--base <ref>]`.
2. For each listed design, compare the diff with the governing sections (`show D00X#slug`):
   - The change implements an accepted spec or plan: update the spec wherever the code now says more, and set the design `active` once its implementation has landed.
   - The code contradicts the spec: report it to the user instead of rewriting the spec.
   - The user decided to change the spec's meaning: bump `revision` and pass the review gate (L1, A1).
3. For changed files where `which` prints `no design`, add them to the `paths` of the design that owns the area. If no design owns it, tell the user; a new design is L2.
4. For each listed plan, update slice statuses, Current state and Log. Archive the plan as `done` when every slice is `done`; report paused slices to the user.
5. Set the dispositions of review findings this change fixed. Archive reviews with no open finding, resolved investigations, and experiments whose conclusion is absorbed into a design.
6. Search READMEs, guides and `AGENTS.md` for names the change renamed or removed (commands, flags, config keys, paths) and fix them.
7. Run `canon.py check --fix` until it is clean.
8. Propose the commit message: Conventional Commits, plus a `Refs: <ids>` trailer for L1 and L2 work.

## After a merge or rebase

Run `canon.py check --fix --base <target>`. For an id collision, renumber the doc your branch added: `renumber <path> --base <target>` before rebasing, `renumber <path>` after.

## Audit

1. Compare `python3 scripts/canon.py --version` with the `canon` skill's `scripts/canon.py --version`. If the project copy is older, upgrade it as the `canon-init` skill describes.
2. Run `canon.py audit`.
3. For each stale design, inspect `git log --since=<updated> -- <paths>` and reconcile it as in step 2 above.
4. For each idle doc, finish it, archive it (`dropped`, `retired`, `abandoned`), or ask the user.
5. When a review is due, propose its scope (modules and angles) to the user.
6. Report what changed and what needs the user's decision.
