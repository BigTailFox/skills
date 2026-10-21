---
name: canon-sync
description: Runs the canon docs step, reconciles docs after a merge or rebase, and audits doc health.
disable-model-invocation: true
---

# Canon sync

Read the `canon` skill first. `canon.py` means the project copy named in `AGENTS.md`.

## After a change

Run the docs step defined by the `canon` skill, on uncommitted work by default or on a branch with `--base <ref>`. Instead of committing, propose the commit message with its `Refs:` trailer.

## After a merge or rebase

Run `canon.py check --fix --base <target>`. For an id collision, renumber the doc your branch added with `renumber <path> --base <target>`, then fix the references it reports as kept.

## Audit

1. Compare `python3 scripts/canon.py --version` with the `canon` skill's `scripts/canon.py --version`. If the project copy is older, upgrade it as the `canon-init` skill describes. If the versions match but the files differ, show the user the diff before replacing it: the project may have local edits.
2. Run `canon.py audit`.
3. For each design with unchecked commits, inspect `git log <since>..HEAD -- <paths>` (audit prints the commit it counts from) and reconcile it as the docs step reconciles a listed design. Commit the design, bumping only `updated` when nothing else changed, so audit counts from there.
4. For each known issue, check that it still holds against the design and the code. Delete the rows a change has already resolved, then run `canon.py check --fix` and commit.
5. For each idle doc, finish it, archive it (`dropped`, `retired`, `abandoned`), or ask the user.
6. When a review is due, propose its scope (modules and angles) and the `canon-review` skill to run it.
7. Report what changed and what needs the user's decision, including the known issues whose next step is `decide`, oldest first.
