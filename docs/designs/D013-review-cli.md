---
status: draft
created: 2026-11-25
updated: 2026-11-25
revision: 1
modules: [canon]
summary: CLI commands for review rounds, snapshots, required coverage checks, and worktree-local pending L2 approvals.
refs: [D001, D006, R003, R004]
owns: [review-snapshots, review-coverage, pending-l2-approvals]
paths: [skills/governance/canon/scripts/canon.py, tests/test_canon.py]
---

# D013: Review CLI

## Goals

1. Isolate each review round and pin its exact worktree snapshots in `.canon/` without touching the project's `.git` or writing to `.canon/canon/trace/` when tracing is off.
2. Mechanically verify that every required review role covered the exact target revisions (or code change) before crediting reviewers or closing a gate.
3. Track pending L2 approval targets per gate across follow-up rounds in a worktree-local record so nothing is dropped when asking the user for approval.

## Spec

This design specifies the CLI commands supporting blind reviews, review gates and L2 approvals (`canon.py review start`, `canon.py review check`, `canon.py snapshot`, `canon.py approvals`). Prose procedures for launching reviewers, prompts, tiers, merging findings and confirmation rounds live directly in the `canon` and `canon-blind-review` skills.

### Review snapshots

`canon.py review start TOPIC --kind gate|follow-up|code-review --tier TIER` (with `--target ID@rN` per initial design/plan revision, optional `--require KEY` for an additionally requested independent reviewer, `--base REF` or `none`, `--snapshot COMMIT`, and optional `--unit TRACE_ID`) creates a fresh worktree-local directory under `.canon/canon-blind-review/TOPIC/` (or `TOPIC/followup-N`) and prints its path:

- Writes declared kind, tier, targets, requested roles and optional trace unit to `round.json`.
- Pins the full commit behind each unambiguous baseline in the review store, including project objects; with `--snapshot COMMIT` uses the prepared target, otherwise takes a fresh snapshot. Reports any unavailable input so the caller falls back to full-document or no-diff review.
- Every new round gets a fresh directory so a late-finishing job writes only to its own round directory.

`canon.py snapshot` records the current work tree for a confirmation or follow-up diff and prints the snapshot commit's full id, whether tracing is on or off.

```text
.canon/canon/snapshots/.git            review snapshot repository: refs/snapshots/<id> per snapshot
.canon/canon/snapshots/snapshot.lock   held by each call
```

- Lives at `.canon/canon/snapshots/` under the checkout root (found as [D001§switch-and-storage: switch and storage](D001-skill-telemetry.md#switch-and-storage) finds that root), so every linked worktree has its own, `.worktrees/` included. Built on first use and writes `.canon/canon/.gitignore` when missing. Writes nothing to `.canon/canon/trace/`.
- Takes an orphan snapshot commit (as [D001§snapshots: snapshots](D001-skill-telemetry.md#snapshots) does) at `refs/snapshots/<id>` (UTC timestamp + 6 random hex digits), holding what `git add -A` would record while leaving the project work tree and index untouched.
- Borrows project objects by writing the absolute path from `git rev-parse --git-path objects` into `objects/info/alternates`, so snapshots store only objects the project lacks instead of copying the full tree.
- Holding `snapshot.lock`, best-effort prunes refs older than 30 days and interrupted index copies or `.init-<id>` directories older than 1 hour, then relies on `gc --auto`.
- On failure (outside Git, untracked + unstaged files over 10 MiB, 5 s lock timeout, or failed Git/alternates/gitignore step), prints `snapshot error: <reason>` (with Git's message on stderr if present) and exits 1.

### Checking required review coverage

`canon.py review check ROUND --input FILE` (or `-` for stdin) validates a round's [D001§review-dispositions: disposition record](D001-skill-telemetry.md#review-dispositions) before crediting `reviewed`/`reviewers` or completing a code review, even with tracing off:

- Accepts `--target ID@rN` for targets added in a supplemental pass. Verifies each design or plan's current revision against completed first-round or supplemental reports in this round using each report's source key, recorded role and assessed targets.
- Required roles: a design or plan gate requires the same-model role plus cross-family at L2; a code review requires Spec and Standards plus cross-family at L2. Each `--require KEY` pass needs independent evidence. A finding-only confirmation covers its claims alone, never full target coverage.
- Optional `--coverage FILE` supports:
  - `assignments`: maps additional supplemental source keys to one requested pass, verifying matching role, same actual model between original and supplemental reports, and single-pass use.
  - `delegations`: list of `{pass, target, source, prior_round, prior_source, prior_target}` for delegated follow-up on a previously covered target, verifying an actual full prior report in the prior round's `dispositions.json` (including verified legacy evidence) for an earlier revision of the same doc and the delegate's current report; waived or newly added targets require full coverage.
- Exceptions: `--waive KEY=ID@rN` discharges a named L2 cross-family requirement after recording the user's decision in the round; `--withdraw KEY` discharges an additionally requested L1 cross-family pass after recording `withdrawal.md`. Neither grants reviewer credit or approval.
- Missing coverage exits nonzero naming the role and affected revision or code change. A missing expected replay input with established coverage warns without failing. Runs locally, modifies no doc, and never treats a trace outcome as proof of a review.

### Pending L2 approvals

Each L2 gate keeps a worktree-local record at `.canon/canon-design/<gate>/approvals.json`, keyed by the original review topic (e.g. `D001-r15`, `P002-r1`), mapping each target ID to `{revision, path}` (the docs' `approved` frontmatter fields in [D006§frontmatter: frontmatter](D006-doc-model.md#frontmatter) remain the record of consent):

- `canon.py approvals GATE --start ID@rN ...`: initializes a new record (refusing to overwrite an existing one) requiring the primary ID at the gate key's revision. Design gates take designs (including sub-designs and D000); plan gates take their plan alone.
- `canon.py approvals GATE --update [ID@rN ...] [--retire ID@rN ...]`: updates an existing record, adding new targets, advancing revisions (never lowering), dropping targets already approved at or above their recorded revision, and preserving unaffected entries under concurrent updates. `--retire ID@rN` removes an exact saved pair whose file moved, was archived, disappeared, or passed a later reviewed revision; an unchanged pending revision cannot be retired. An empty record remains on disk so later follow-ups reuse the gate key.
- `canon.py approvals GATE --recover [ID@rN ...]`: reconstructs a missing record (or an emptied plan-gate record whose file identity was lost) from verified pending targets, omitting already-approved ones after verification.
- `canon.py approvals [GATE]`: read-only query; with `GATE`, prints `<gate>: <sorted ID@rN ...>` or `<gate>: none` (nonzero if missing); without arguments, lists outstanding gates in key order.
- Validation: resolves every saved ID uniquely and verifies its recorded path before dropping approved targets; every remaining target must be live with `revision` and `reviewed` equal to its recorded number. Any stale, missing, ambiguous or invalid target/update exits nonzero without partial writes.

## Decisions

- **Review snapshots live outside `.canon/canon/trace/` and borrow project objects via `alternates`**: confirmation diffs must work when tracing is off, must not write into the project's `.git` (read-only in Codex's sandbox), and must not copy a 20,000-file repository tree on first review ([D001§snapshots: snapshots](D001-skill-telemetry.md#snapshots)).
- **Subagents start fresh (never forks) and reviewers read the live work tree while it stays frozen**: a fork unblinds reviewers; checking out a snapshot per reviewer loses Git history `check` reads, whereas freezing edits while readers run prevents post-review edits from slipping under an approval ([R003§r003-f5-reviewers-read-the-live-work-tree: R003-F5](../archived/reviews/R003-silk-design-phase.md#r003-f5-reviewers-read-the-live-work-tree)).
- **Machine-local reviewer config (`$XDG_CONFIG_HOME/canon/reviewer.md`)**: tools, logins and command grants vary per machine, not per checkout; checkout-local files broke linked worktrees and clones.
- **Mechanical coverage checks (`review check`) and per-gate approval records (`approvals`)**: Silk gates dropped a pending target across follow-ups (`R004-F1`) and credited reviewers who had not read a newly added target ([R004: Silk feedback](../archived/reviews/R004-silk-canon-field-feedback.md)).
