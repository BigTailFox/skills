---
name: canon-sync
description: Brings a project's canon docs in line with its code. Runs the docs step after a change (update governing designs, archive finished plans, reviews, investigations and experiments, fix stale READMEs, prepare the commit trailer), reconciles docs after merges, and audits doc health (stale designs, idle docs, due reviews, outdated canon.py). Use when the user asks to sync, update, reconcile or audit docs, before committing finished work, or after merging branches.
disable-model-invocation: true
---

# Canon sync

Read the `canon` skill first. `canon.py` means the project copy named in `AGENTS.md`.

## After a change

Run the docs step defined by the `canon` skill, on uncommitted work by default or on a branch with `--base <ref>`. Instead of committing, propose the commit message with its `Refs:` trailer.

## After a merge or rebase

Run `canon.py check --fix --base <target>`. For an id collision, renumber the doc your branch added: `renumber <path> --base <target>` before rebasing, `renumber <path>` after.

## Audit

1. Compare `python3 scripts/canon.py --version` with the `canon` skill's `scripts/canon.py --version`. If the project copy is older, upgrade it as the `canon-init` skill describes.
2. Run `canon.py audit`.
3. For each stale design, inspect `git log --since=<updated> -- <paths>` and reconcile it as the docs step reconciles a listed design.
4. For each idle doc, finish it, archive it (`dropped`, `retired`, `abandoned`), or ask the user.
5. When a review is due, propose its scope (modules and angles) and the `canon-review` skill to run it.
6. Report what changed and what needs the user's decision.
