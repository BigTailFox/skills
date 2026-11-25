---
status: open
created: 2026-11-25
updated: 2026-11-25
revision: 1
modules: [canon]
summary: Twelve open field findings on plan tiers, review completion, approvals, trace evidence, worktree records, CLI queries and verification coverage.
refs: [D001, D003, D006, D007, D010, C001, R005, R006]
---

# R007: Open Canon workflow feedback from Silk and Canon

## Scope

This review consolidates the unresolved items in the November 24–25, 2026 field-feedback inventory from Silk and Canon. It assesses workflow correctness, usability, evidence retention and verification coverage against Canon `29a9e4b` (v0.9.4, canon 82), with Silk checked at `a52cc21`. The nine Silk skill reports were recorded against canon 81. Proposed changes below remain proposals; recording a finding approves no change to a design or workflow.

The [captured field evidence](R007/field-evidence.json) preserves nine original Silk skill records, seven relevant retro-note sections and three read-only trace-history results. It includes the source paths, source-file digests and repository commits. Source record numbers below identify the original lines of Silk's `.canon/canon-retro/skills.jsonl`; note names identify sections of the named repository's `.canon/canon-retro/notes.md`. Document IDs prefixed with Silk refer to that repository, not this one's designs and plans.

An `open` disposition means that an upstream decision, fix or verification-policy follow-up remains. Local mitigations are stated separately. This inventory does not reopen the findings closed in [R005: Silk upgrade feedback](../archived/reviews/R005-silk-upgrade-090.md) or [R006: Review scope and commit checks](../archived/reviews/R006-silk-review-scope-and-commit-checks.md). Silk's applied external-compatibility testing rule and runner, and the machine-local guidance for interrupted Cursor tasks, are retained in the evidence only to explain their exclusion from the open findings.

## Findings

| ID | Severity | Finding | Disposition |
|----|----------|---------|-------------|
| R007-F1 | major | The first implementation plan for an unimplemented L2 design can be classified as L1. | open |
| R007-F2 | major | New blockers introduced by fixes can prolong confirmation without a timely escalation. | open |
| R007-F3 | minor | The approval instructions omit the required split between a plan and its follow-on design targets. | open |
| R007-F4 | major | A short baseline hash silently prevents retention of the review input. | open |
| R007-F5 | major | Restarting a gate in its existing directory can omit required evidence through the archive's modification-time filter. | open |
| R007-F6 | minor | Confirmation-introduced blockers have no supported identity for their later targeted rechecks. | open |
| R007-F7 | major | Retro records have no shared storage rule for linked worktrees. | open |
| R007-F8 | major | A missed background-review completion notification can leave a completed round waiting indefinitely. | open |
| R007-F9 | minor | Reading several design sections requires one `show` invocation per section. | open |
| R007-F10 | major | A completed Cursor report can fail local publication with EACCES. | open |
| R007-F11 | major | A Git marker in the default temporary root causes validation to skip outside-checkout tests. | open |
| R007-F12 | major | Verification using newer toolchain headers misses violations of the oldest supported versions. | open |

### R007-F1 First implementation plan tier

Silk skill record 33 and the `first-plan-tier-underestimated` note report that Silk `P002@r1`, the first implementation plan for accepted but unimplemented Silk `D003`, started as L1 because an earlier scaffold already supplied the module directory. The user changed the tier to L2. The retro attributes three unique blockers and nine unique majors to the subsequent cross-family pass; these counts are reported field evidence, not a new independent scoring of the reviewers.

Silk commit `bc895d8` adds a project rule defaulting first implementation plans and core protocol or architecture milestones to L2. The upstream request remains to settle how a plan inherits risk from an unimplemented design and make the rule explicit in `canon-plan` and [D007§choosing-a-tier: choosing a tier](../designs/D007-change-tiers.md#choosing-a-tier). An existing scaffold alone should not settle that decision.

### R007-F2 Confirmation rounds and new blockers

Silk skill record 30 describes six cross-family and five same-model confirmation passes around Silk `P001@r1`, seven confirmation-introduced blockers and about 50 minutes before escalation at the fourth cross-family confirmation. The captured history of `20261124T143253Z-5cd962` records `new blockers=7`.

[D007§confirmation-round: confirmation round](../designs/D007-change-tiers.md#confirmation-round) already schedules one confirmation and sends remaining blockers to the user. The requested clarification is that this includes blockers introduced by the fixes. A subsequent targeted recheck needs its own authorization and evidence. The record does not establish that every later pass lacked authorization; it shows that the existing instruction did not produce a timely first escalation. Findings introduced during confirmation also need the tracking addressed by R007-F6.

### R007-F3 Mixed plan and design approvals

Silk skill record 27 reports that a trace gate accepted Silk `P001@r1` and `D000@r21` together, but `canon.py approvals P001-r1 --start P001@r1 D000@r21` failed with `D000@r21 does not belong to gate P001-r1`. The agent inspected the implementation to discover the grouping restriction.

[D007§pending-l2-approvals: pending L2 approvals](../designs/D007-change-tiers.md#pending-l2-approvals) expressly limits a plan approval record to its own plan. The workflow's instruction to record the full first round, and `approvals -h`, omit that distinction. The default follow-up is to document separate plan and design approval records at those entry points. Supporting mixed records would instead require a design revision.

### R007-F4 Abbreviated baseline hashes

Silk skill record 28 reports that `baseline.txt` held the seven-character hash `fff71d4` for the Silk `P001-r1` and `D002-r9` reviews. `trace end` returned success without a warning, while review-input retention stayed unknown. The captured histories of `20261124T143253Z-5cd962` and `20261124T154711Z-52babc` still show `review_input=unknown`.

[D001§first-round-review-input: first-round review input](../designs/D001-skill-telemetry.md#first-round-review-input) requires full object IDs and permits an unknown retained input when pins are malformed. This is a request to improve input handling and diagnostics, not evidence that retention violates that spec. Resolve an unambiguous abbreviated commit before retention and report when a supplied pin cannot be retained, so a successful trace close does not hide the loss of replay evidence.

### R007-F5 Evidence omitted when a gate restarts

Silk skill record 32 reports that cancelled L1 gate `20261125T030511Z-c78316` and replacement L2 gate `20261125T030845Z-82bb16` reused the `P002-r1` directory. Its baseline and same-model prompt predated the replacement gate. The archive's modification-time filter omitted them. The captured replacement history shows both `archive=ok (files present)` and `review_input=unknown`.

The follow-up should identify the files belonging to the restarted round explicitly, preserve its verified baseline and required prompts regardless of their age, and report incomplete evidence. Reusing a directory must not accidentally associate stale reports with the replacement review. [D001§review-files: review files](../designs/D001-skill-telemetry.md#review-files) and [D001§first-round-review-input: retained input](../designs/D001-skill-telemetry.md#first-round-review-input) govern the change.

### R007-F6 Rechecking confirmation-introduced blockers

Silk skill record 34 reports later targeted rechecks of blockers introduced during the Silk `D003@r32` and `P002@r1` confirmations. `trace recheck` accepts a source key belonging to an original merged finding, so these later claims cannot be linked through the same interface. A `new_blockers` count preserves their number but not their identities and subsequent verdicts.

Extend [D001§review-dispositions: review dispositions](../designs/D001-skill-telemetry.md#review-dispositions) with an identity and report provenance for each confirmation-introduced blocker, then let its separately authorized rechecks refer to that identity. Preserve the original finding list and first-confirmation outcome.

### R007-F7 Retro storage across worktrees

Silk skill record 31 reports an empty retro history in `.worktrees/plan-d003-ring-protocol` while the main checkout held 26 recorded causes and 30 skill-friction entries. `canon-retro` names checkout-relative paths, so a linked worktree can start a separate history and lose it when that worktree is removed.

The proposed follow-up is a shared main-checkout ledger, with an explicit fallback when that location cannot be written. This extends the existing idea **Collecting canon's records across projects** in [C001§ideas: backlog](../concepts/C001-canon-backlog.md#ideas). Resolve the storage rule with [D001§switch-and-storage: trace storage](../designs/D001-skill-telemetry.md#switch-and-storage) and [D006§concurrent-work: concurrent work](../designs/D006-doc-model.md#concurrent-work), including how simultaneous appenders preserve one another's entries.

### R007-F8 Completed background reviews without a notification

Silk skill record 29 and `cursor-parallel-review-launch-stall` report that a blocking command reviewer ran alongside a background Cursor Task. After the command returned, the parent waited for a completion notification that never arrived. The subagent's transcript already contained its finished report, but the chat remained silent for 16 minutes until the user intervened.

The machine reviewer file now describes a parallel foreground tool batch on Cursor and checking the actual subagent result before yielding with a background reviewer outstanding. The portable instruction in `canon-blind-review` still asks for asynchronous host reviewers. Carry the host-capability distinction and a completion-recovery check into the shared workflow, consistent with [D003§external-review-progress: external review progress](../designs/D003-subagents.md#external-review-progress). The local mitigation has not closed that upstream request.

### R007-F9 Batch section reads

Silk skill record 35 reports that supplying eight `ID#slug` arguments to `canon.py show` exited with unrecognized arguments, forcing separate commands or offset-based reads of a large design. [D010§show: show](../designs/D010-doc-queries-and-renames.md#show) specifies one argument, so this is an interface improvement request. Accept several selectors in one invocation and keep a distinct path-and-section header for each result.

### R007-F10 Completed report publication failure

Canon's `cursor-completed-report-publication` note remains `raised`. It records completed Cursor design and plan reviews on November 23, followed by two code-review confirmations on November 24, whose local launcher failed to publish the report with `EACCES` or errno 13. Each complete report was recovered from the original provider session and verified binding without another provider call.

Keep this as a machine-launcher investigation under [D003§external-review-progress: external review progress](../designs/D003-subagents.md#external-review-progress). Establish which local write fails, fix publication through the installed entry point, and retain a regression case that recovers an already completed report without rerunning the reviewer. Manual recovery mitigates the incidents; the record contains no verified root-cause fix.

### R007-F11 Skipped outside-checkout tests

Canon's `default-test-temp-inside-checkout` note remains `raised`. A Git marker in the default temporary root repeatedly caused `scripts/validate.py` to skip tests that need a directory outside any checkout: 14 in earlier runs and 15 in the canon 82 run. Separate runs in a clean temporary root passed; the canon 82 record also reports nine Bubblewrap cases passing on the capable host.

The gap is repeatable coverage in the normal validation command. Have the validator identify this skip cause and run that group under a verified clean temporary root, reporting the result. It should preserve unrelated capability skips. The already passing manual runs are evidence for the tests, not a fix to the validator's coverage gap.

### R007-F12 Oldest supported toolchain verification

Silk's `floor-header-drift` note remains `noted`. Its cross-family code review caught use of Linux 6.7+ futex spellings where the supported floor was Linux 5.16, and a CUDA 12.3+ attribute name where headers had to support CUDA 12.0. Local and CI builds used newer headers. Silk commit `10867b9` fixed both implementation defects.

The remaining item is the verification-policy decision: add an explicit compile check against the oldest supported headers and toolchain to Silk's compatibility matrix, and decide whether `canon-plan` and `canon-tdd` should prompt for that case when a design promises version floors. Silk owns the concrete versions and environment. This finding tracks the prevention gap, with the two code fixes already complete.

## Verification

The inventory was checked against the captured source records, Canon v0.9.4's skill text and governing sections, the closed dispositions in R005/R006, and three live read-only `trace history` queries. It does not claim to reproduce the launcher failures, rerun the historical reviews or repeat the compatibility tests. Suggested severity reflects the remaining workflow impact; reported reviewer counts and elapsed times retain their source attribution.

### R007-F8 and R007-F10 recovery verification

On 2026-11-25 at 08:49:45 UTC, a check of the original Codex transcripts matched both child IDs and their common parent without consulting completion notices. The confirmation turn of `01a211b3-da4b-7dc1-8b41-cc6306644651` yielded the saved 1,698-byte terminal text (SHA-256 `67958cc72ee08e169e5d64fb95b27e652ef485b3a3f82d85bbe072a6f63f0d0c`, excluding the file’s trailing newline). The open turn of `01a211e2-a5e9-7111-8a31-5fada943aacd` was still running on its original handle.

The four historical Cursor jobs reported provider success and launcher exit 1. Their diagnostics end in `failed (CLI exit 1): external review: [Errno 13] Permission denied`. They locate the failure in the supervised command before publication. The denied operation and its target are unknown for those jobs.

| Offline case on this Linux host | Initial exit | Cleanup warnings | Result |
|---|---:|---:|---|
| Saved pre-fix launcher, injected `os.kill(helper_pid, SIGKILL)` denial | 1 | 0 | Historical diagnostic reproduced. Previous report preserved. |
| Installed launcher, same injected denial | 0 | 1 | Complete report and original session ID published. |
| Installed launcher, kernel denied the supervisor’s `SIGKILL` to `cursorsandbox --help` under `cursor_sandbox_agent_cli (enforce)` | 0 | 1 | Complete report and original session ID published. |
| Installed launcher, injected `os.replace(.canon-review-<key>/result, cross-family.md)` denial | 1 | 0 | Previous report preserved. `resume cross-family.md` exited 0 and published the bound result with the provider disabled. |

Each case made one call to a local stand-in. Each successful publication produced 262,169 exact bytes (SHA-256 `9dab0b87d7a39ab90d03bf9f0cfc7631e10dbdccb970dda8790298488c2b8c83`) and printed `session id: fixture-cursor`. The installed `~/.config/canon/review-live.py` had SHA-256 `d336ff49a7edaa462215445ad4d1bdd81b08303f30236db6fb3a91be1dbfce37`. Its companion suite passed all 50 offline cases.

Run the [offline regression](R007/check_cursor_publication.py) from the checkout on Linux. The default runs both injected cases. For the kernel-denial case, also pass `--cursor-helper` with the path to the installed `cursorsandbox` beside the resolved Cursor `agent` executable.

```sh
python3 docs/reviews/R007/check_cursor_publication.py .canon/canon-implement/P012/S4
```
