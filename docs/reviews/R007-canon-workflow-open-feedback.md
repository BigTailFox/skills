---
status: open
created: 2026-11-25
updated: 2026-11-25
revision: 1
modules: [canon]
summary: Nine findings fixed. Six open on review decisions and documentation, worktree retro records, multi-section queries and verification coverage.
refs: [D001, D003, D006, D007, D009, D010, C001, R004, R005, R006, P012]
---

# R007: Open Canon workflow feedback from Silk and Canon

## Scope

This review consolidates the unresolved items in the November 24–25, 2026 field-feedback inventory from Silk and Canon. The initial inventory assessed workflow correctness, usability, evidence retention and verification coverage against Canon `29a9e4b` (v0.9.4, canon 82), with Silk checked at `a52cc21`. Its nine Silk skill reports were recorded against canon 81. The finding descriptions preserve the original reports. The table records their current dispositions.

The [captured field evidence](R007/field-evidence.json) preserves nine original Silk skill records, seven relevant retro-note sections and three read-only trace-history results. It includes the source paths, source-file digests and repository commits. Source record numbers below identify the original lines of Silk's `.canon/canon-retro/skills.jsonl`; note names identify sections of the named repository's `.canon/canon-retro/notes.md`. Document IDs prefixed with Silk refer to that repository, not this one's designs and plans.

Silk's subsequent joint design gate, led by Silk `D005@r4`, produced skill records 36–38 on canon 82 and five new retro sections. The November 25 supplement compares those reports at Silk `2bc5aef` with the upstream instructions at Canon `0311d34` (canon 86). It records three upstream proposals as R007-F13–F15 and two local remedies under [Local follow-ups](#local-follow-ups-from-the-same-silk-gate). [D005@r4 field evidence](R007/silk-d005-r4-feedback.json)

An `open` disposition means that an upstream decision, fix or verification-policy follow-up remains. Local mitigations are stated separately. This inventory does not reopen the findings closed in [R005: Silk upgrade feedback](../archived/reviews/R005-silk-upgrade-090.md) or [R006: Review scope and commit checks](../archived/reviews/R006-silk-review-scope-and-commit-checks.md). Silk's applied external-compatibility testing rule and runner, and the machine-local guidance for interrupted Cursor tasks, are retained in the evidence only to explain their exclusion from the open findings.

## Findings

| ID | Severity | Finding | Disposition |
|----|----------|---------|-------------|
| R007-F1 | major | The first implementation plan for an unimplemented L2 design can be classified as L1. | fixed b1cffbb |
| R007-F2 | major | New blockers introduced by fixes can prolong confirmation without a timely escalation. | fixed 821583c |
| R007-F3 | minor | The approval instructions omit the required split between a plan and its follow-on design targets. | fixed b1cffbb |
| R007-F4 | major | A short baseline hash silently prevents retention of the review input. | fixed d8b223a |
| R007-F5 | major | Restarting a gate in its existing directory can omit required evidence through the archive's modification-time filter. | fixed 9594d9a |
| R007-F6 | minor | Confirmation-introduced blockers have no supported identity for their later targeted rechecks. | fixed 9594d9a |
| R007-F7 | major | Retro records have no shared storage rule for linked worktrees. | open |
| R007-F8 | major | A missed background-review completion notification can leave a completed round waiting indefinitely. | fixed 0fefb31 |
| R007-F9 | minor | Reading several design sections requires one `show` invocation per section. | open |
| R007-F10 | major | A completed Cursor report can fail local publication with EACCES. | fixed 9594d9a |
| R007-F11 | major | A Git marker in the default temporary root causes validation to skip outside-checkout tests. | fixed 4de7e23 |
| R007-F12 | major | Verification using newer toolchain headers misses violations of the oldest supported versions. | open |
| R007-F13 | major | During blind-review triage, an agent can treat a user's follow-up questions and counterproposals as decisions. | open |
| R007-F14 | major | The targeted recheck instructions leave implicit when to return a still-unresolved blocker to the user. | open |
| R007-F15 | major | A revised design guarantee can remain stale in the public overview and in diagram labels through multiple review passes. | open |

The eight fixed findings went through a single implementation plan and combined code review. [P012: Reliable review rounds and evidence](../archived/plans/P012-review-workflow-reliability.md)

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

The machine reviewer file now describes a parallel foreground tool batch on Cursor and checking the actual subagent result before yielding with a background reviewer outstanding. At intake, the portable instruction in `canon-blind-review` asked for asynchronous host reviewers. Carry the host-capability distinction and a completion-recovery check into the shared workflow, consistent with [D003§external-review-progress: external review progress](../designs/D003-subagents.md#external-review-progress). The shared fix and its verification are recorded [below](#r007-f8-and-r007-f10-recovery-verification).

### R007-F9 Batch section reads

Silk skill record 35 reports that supplying eight `ID#slug` arguments to `canon.py show` exited with unrecognized arguments, forcing separate commands or offset-based reads of a large design. [D010§show: show](../designs/D010-doc-queries-and-renames.md#show) specifies one argument, so this is an interface improvement request. Accept several selectors in one invocation and keep a distinct path-and-section header for each result.

### R007-F10 Completed report publication failure

At intake, Canon's `cursor-completed-report-publication` note was `raised`. It records completed Cursor design and plan reviews on November 23, followed by two code-review confirmations on November 24, whose local launcher failed to publish the report with `EACCES` or errno 13. Each complete report was recovered from the original provider session and verified binding without another provider call.

Keep this as a machine-launcher investigation under [D003§external-review-progress: external review progress](../designs/D003-subagents.md#external-review-progress). Establish which local write fails, fix publication through the installed entry point, and retain a regression case that recovers an already completed report without rerunning the reviewer. Manual recovery mitigated each incident. The [verification below](#r007-f8-and-r007-f10-recovery-verification) records which failures the installed launcher now recovers and what the original logs established.

### R007-F11 Skipped outside-checkout tests

Canon's `default-test-temp-inside-checkout` note remains `raised`. A Git marker in the default temporary root repeatedly caused `scripts/validate.py` to skip tests that need a directory outside any checkout: 14 in earlier runs and 15 in the canon 82 run. Separate runs in a clean temporary root passed; the canon 82 record also reports nine Bubblewrap cases passing on the capable host.

The gap is repeatable coverage in the normal validation command. Have the validator identify this skip cause and run that group under a verified clean temporary root, reporting the result. It should preserve unrelated capability skips. The already passing manual runs are evidence for the tests, not a fix to the validator's coverage gap.

### R007-F12 Oldest supported toolchain verification

Silk's `floor-header-drift` note remains `noted`. Its cross-family code review caught use of Linux 6.7+ futex spellings where the supported floor was Linux 5.16, and a CUDA 12.3+ attribute name where headers had to support CUDA 12.0. Local and CI builds used newer headers. Silk commit `10867b9` fixed both implementation defects.

The remaining item is the verification-policy decision: add an explicit compile check against the oldest supported headers and toolchain to Silk's compatibility matrix, and decide whether `canon-plan` and `canon-tdd` should prompt for that case when a design promises version floors. Silk owns the concrete versions and environment. This finding tracks the prevention gap, with the two code fixes already complete.

### R007-F13 Questions in replies to escalated findings

Silk record 36 and the `askquestion-custom-reply-unanswered` note describe a three-item review question. The user entered questions and alternatives for two items in the form's free-text “Other” field. The agent edited the designs and launched confirmation before answering. The user interrupted, the GPU indexing rule was reworked, and confirmation restarted.

Silk added a local rule in `49551fb`. R004-F9 supplied the mixed-reply example in `canon-grill`. Silk now asks `canon-blind-review` Merge to point to it. Record choices the user settled, answer their questions in chat, and wait for their decision on the open points before editing the affected material or launching its reviewers. [R004§fixing-findings-and-recording-decisions: earlier fix](../archived/reviews/R004-silk-canon-field-feedback.md#fixing-findings-and-recording-decisions) · [D007§merging-findings: merging findings](../designs/D007-change-tiers.md#merging-findings) · [D009§record: recording decisions](../designs/D009-settling-decisions.md#record)

### R007-F14 An unresolved blocker after a targeted recheck

Silk record 37 and the `review-recheck-self-loop` note concern the first targeted recheck. Cross-family F2 (blocker) and F5 (major) remained open. Silk reports that the agent drafted a private-API solution and launched a second recheck before returning the design choice to the user. That report raised two new blockers. The speculative changes were discarded. The fourth targeted report approved the revised design.

Silk added a local stop rule in `390c2e7`. R007-F2 addressed the scheduled confirmation. Canon 86 also requires a separate request for a targeted recheck and explicitly returns a newly introduced blocker to the user. The remaining suggestion is to say what happens when that recheck leaves the **same blocker** unresolved. Present the blocker and options to the user before further edits or another recheck. [D007§confirmation-round: confirmation round](../designs/D007-change-tiers.md#confirmation-round) · [D003§resuming-and-replacing: targeted rechecks](../designs/D003-subagents.md#resuming-and-replacing)

### R007-F15 Stale guarantees in public overviews and diagrams

Silk record 38 and the `guarantee-sweep-misses-diagrams-and-sketches` note follow cross-family F8. The authors qualified a GPU Mirror guarantee in the design prose, but Silk's public overview and three Mermaid labels in Silk C001 and D005 still promised one copy per visible GPU island. Some labels split the phrase with `<br/>`. Confirmation and the first two targeted rechecks kept F8 open. The third confirmed that all three labels now said “per selected GPU placement.” A related guarantee in the Python API sketch took one more pass.

Silk added its project-specific pointers in `78ed009`. The confirmation step already names affected designs and sketches following R004-F7. Silk proposes including the project's designated public overview and checking diagram and table labels, including wording split across lines, alongside the attached sketches before taking the confirmation snapshot. [R004§fixing-findings-and-recording-decisions: earlier fix](../archived/reviews/R004-silk-canon-field-feedback.md#fixing-findings-and-recording-decisions) · [D007§confirmation-round: confirmation round](../designs/D007-change-tiers.md#confirmation-round)

### Local follow-ups from the same Silk gate

- **Failed review status.** The machine launcher erased its status record after a provider exited with an error. When the user asked whether the reviewer was running, the status command could no longer answer. The local fix keeps the failed state, exit code, error summary and original session ID available after the status socket closes. Silk recorded 50 passing offline cases. The installed launcher, test file and reviewer configuration matched the three digests in the `review-live-erases-failure-state` note when this supplement was collected. [Field evidence](R007/silk-d005-r4-feedback.json)
- **Cached PyTorch interpreter.** Silk reports two probes that searched for a working PyTorch installation although its compatibility runner had already provisioned one. Silk `2bc5aef` put the existing `.cache/python-compat/optional-py3.12/bin/python` path in its testing instructions. The `cached-torch-venv-undocumented` note records the local fix. R007-F12 continues to track compilation against the oldest supported headers. [Field evidence](R007/silk-d005-r4-feedback.json)

## Verification

At intake, the inventory was checked against the captured source records, Canon v0.9.4's skill text and governing sections, the closed dispositions in R005/R006, and three live read-only `trace history` queries. The severity reflects the workflow impact at intake. The reviewer counts and elapsed times come from the original records.

For the D005 supplement, the first 35 lines of Silk's skill ledger and the first 167 lines of its retro notes matched the original intake digests. The supplement preserves the added records and sections, the four local-instruction commits, and the relevant history from Silk gate `20261125T065524Z-2a7ee8`. Its cross-family confirmation and four targeted reports were checked against the finding sequence above. The account of the user's intervention and discarded work comes from Silk's retro. [D005@r4 field evidence](R007/silk-d005-r4-feedback.json)

### R007-F8 and R007-F10 recovery verification

On 2026-11-25 at 08:49:45 UTC, a check of the original Codex transcripts matched both child IDs and their common parent without consulting completion notices. The confirmation turn of `01a211b3-da4b-7dc1-8b41-cc6306644651` yielded the saved 1,698-byte terminal text (SHA-256 `67958cc72ee08e169e5d64fb95b27e652ef485b3a3f82d85bbe072a6f63f0d0c`, excluding the file’s trailing newline). The open turn of `01a211e2-a5e9-7111-8a31-5fada943aacd` was still running on its original handle.

The four historical Cursor jobs reported provider success and launcher exit 1. Their diagnostics end in `failed (CLI exit 1): external review: [Errno 13] Permission denied`. They locate the failure in the supervised command before publication. The denied operation and its target are unknown for those jobs.

| Offline case on this Linux host | Initial exit | Cleanup warnings | Result |
|---|---:|---:|---|
| Saved pre-fix launcher, injected `os.kill(helper_pid, SIGKILL)` denial | 1 | 0 | Historical diagnostic reproduced. Previous report preserved. |
| Installed launcher, same injected denial | 0 | 1 | Complete report and original session ID published. |
| Installed launcher, kernel denied the supervisor’s `SIGKILL` to `cursorsandbox --help` under `cursor_sandbox_agent_cli (enforce)` | 0 | 1 | Complete report and original session ID published. |
| Installed launcher, injected `os.replace(.canon-review-<key>/result, cross-family.md)` denial | 1 | 0 | Previous report preserved. `resume cross-family.md` exited 0 and published the bound result with the provider disabled. |

Each case made one call to a local stand-in. Each successful publication produced 262,169 exact bytes (SHA-256 `9dab0b87d7a39ab90d03bf9f0cfc7631e10dbdccb970dda8790298488c2b8c83`) and printed `session id: fixture-cursor`. The regression exercises the caller’s ID-file step as well. A denied replacement leaves the previous report and ID together. After successful publication or resume, the caller records the returned ID alongside the verified report. The installed `~/.config/canon/review-live.py` had SHA-256 `d336ff49a7edaa462215445ad4d1bdd81b08303f30236db6fb3a91be1dbfce37`. Its companion suite passed all 50 offline cases.

Run the [offline regression](R007/check_cursor_publication.py) from the checkout on Linux. The default runs both injected cases. For the kernel-denial case, also pass `--cursor-helper` with the path to the installed `cursorsandbox` beside the resolved Cursor `agent` executable.

```sh
python3 docs/reviews/R007/check_cursor_publication.py .canon/canon-implement/P012/S4
```
