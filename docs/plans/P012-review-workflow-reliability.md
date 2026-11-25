---
status: in-progress
created: 2026-11-25
updated: 2026-11-25
revision: 1
modules: [canon]
summary: Eight review workflow corrections covering round ownership, evidence and waivers, confirmation findings and host recovery.
refs: [D007, D003, D001, R007]
based_on: [D007@r12, D003@r14, D001@r19]
reviewed: 1
reviewers: [gpt-6.2-astra]
---

# P012: Reliable review rounds and evidence

Implements [D007: Change tiers and the review gate](../designs/D007-change-tiers.md).

## Current state

Next: S4.

## Slices

### S1: Pin a fresh round and retain its review inputs

Status: done

Risk: A cancelled reviewer can finish after its replacement starts. Git can resolve an abbreviation differently in another store.

Implement `review start` and unit-bound archival in the installed Canon CLI. Reuse the review snapshot machinery, archive limits and trace locks. Update the CLI reference and blind-review file instructions. Carry verified legacy short baseline bindings into the offline review input checker. Bump the tool version and run project initialization in the same commit.

Test at the CLI and offline replay seams. Start an L1 gate, cancel and restart the same topic at L2. A verified older baseline and prompt copied into the replacement round are retained. A report arriving late in the old round is absent. Test prepared and live inputs, tracing off, SHA formats, and archive ownership mismatches. A verified abbreviated legacy baseline reproduces the actual diff in a mirror without the original commit. An unavailable or ambiguous input emits a material-specific warning and an idempotent retro record while allowing the review to proceed. Compare a mixed follow-up that never requested a shared baseline with a round that lost its requested pin. Only the latter warns and records a gap. Preserve normal full-document gates, linked handoffs and legacy archive filters. [D003§review-snapshots: round start](../designs/D003-subagents.md#review-snapshots) · [D001§first-round-review-input: archival](../designs/D001-skill-telemetry.md#first-round-review-input)

### S2: Check review coverage before crediting revisions

Status: done

Risk: Treating a confirmation, a stale report or a partial waiver as full coverage can mark an unreviewed target as reviewed.

Implement `review check` on S1's round metadata. Wire the start and check into design and plan gates, follow-ups and both axes of code review. Make the first plan's L2 default visible at plan entry. Explain plan and design approval records in the workflow and `approvals -h`. Follow the current versioning and initialization procedure for the CLI change.

Through the CLI with telemetry off, check a gate with complete reports, a missing role, a supplemental target covered by only one required role, a changed revision, and a code review missing an axis. Exercise a separately requested reviewer and its supplemental assignments, including a wrong model and reuse for two passes. For a delegated follow-up, verify actual prior full same-document evidence at an earlier revision, the current delegate report and its actual model, and reject a previously waived target. The previous report must have served the very independent pass now delegated, including a supplemental source assigned to it. Substitute a prior same-model report in the same case and require rejection. Hand off a partially reviewed same-revision gate after its same-model pass, resume into a fresh round and dispatch only its missing cross-family pass. Bring forward the verified same-model report, its actual author and its predecessor provenance. Check both readers, an unrelated predecessor, and resumption with tracing off using the saved pending record. Check a documented L1 withdrawal. A waiver must apply to the exact allowed role and revision and contributes no review credit. Verify that a missing replay baseline alone warns and logs the gap while established coverage passes. Exercise an L2 first core implementation over an existing scaffold and a local follow-up to an implemented design against the published plan instructions. Check the documented approval commands with one plan and a separately reviewed design. [D007§checking-required-review-coverage: coverage](../designs/D007-change-tiers.md#checking-required-review-coverage) · [D007§choosing-a-tier: first implementation](../designs/D007-change-tiers.md#choosing-a-tier) · [D007§pending-l2-approvals: approval grouping](../designs/D007-change-tiers.md#pending-l2-approvals)

### S3: Link confirmation blockers to their own rechecks

Status: done

Risk: A confirmation report may reuse a first-round finding label. Incorrect attribution changes historical reviewer metrics.

Implement `trace blocker`, rechecks of its namespaced identities, history and the offline readers. Update the confirmation, retro and evidence instructions. Make the one scheduled confirmation's stop point explicit. Preserve old event shapes and initial attribution. Bump the CLI version and initialize the project in the same commit.

Through the CLI and offline readers, record a first-round F12 and a confirmation F12, recheck each independently, and introduce a blocker in a separately authorized recheck. Verify correct origins and report availability, idempotent retries, rejected conflicting or unknown provenance, later ordering, unknown first-confirmation snapshots, visibility of old count-only data and unchanged first-round scores. A confirmation introducing a blocker routes to the user before any new fix or recheck. If the user authorizes a recheck before closure, obtain its result, close with the first verdict intact, then register the blocker before appending its saved recheck. Verify that ordering through the public commands. [D001§review-dispositions: source identity](../designs/D001-skill-telemetry.md#review-dispositions) · [D007§confirmation-round: escalation](../designs/D007-change-tiers.md#confirmation-round)

### S4: Recover a completed review from its original run

Status: todo

Update the portable launch and completion instructions for hosts that can await foreground jobs together and hosts with asynchronous reviewers. Exercise a completed host job with a lost completion notice, a still-running job and the machine's installed Cursor launcher. At the machine’s installed launcher entry point, reproduce the denied cleanup and a distinct denied final report replacement. Identify the exact operations. Check that a completed run publishes its bound report and run ID through cleanup denial and that the launcher’s resume automatically publishes the original report and ID after a replacement failure, with the second provider call forbidden. Retain the runnable offline regression and exact results. Record the verified machine-local outcome and reproduction in a short R007 verification receipt, distinguishing what the historical logs identify from what the reproducer establishes. [D003§external-review-progress: command recovery](../designs/D003-subagents.md#external-review-progress) · [R007: field feedback](../reviews/R007-canon-workflow-open-feedback.md)

## Notes

The batch covers R007-F1 through F6, F8 and F10. Each has a separate acceptance case. S1 delivers the producer and replay binding, S2 the consumer, S3 the post-review record, and S4 the host instructions. A tool change carries regression coverage in tests/test_canon.py, an incremented CANON_VERSION and this checkout’s refreshed AGENTS.md. Use the existing trace budget and the D001 evidence reference for details. Evidence that a required review occurred and optional material for replay have different effects on gate completion. Use the existing user waiver limits. The other field findings remain open.

## Log

The plan covers one combined implementation and final code review.

Started at bd5c4a937e1af59a68585f9feb53ed3e9ed7b13d.

S1 — Canon 83 creates distinct round directories, binds prepared/live input and preserves verified short baselines for replay after the source disappears. Seven new CLI and replay cases and a real ambiguous-prefix fixture passed. Recovery keeps its original round and source identity. The coverage check in S2 can use the existing round declaration, pass list, pin and material-warning helpers, including in a checkout with tracing off. A numbered key identifies a separately requested pass when its ordinary role is already required.

S2 — Canon 84 checks actual readers by target and role, separate approval groups, partial handoffs, delegation and scoped user exceptions. Fourteen public CLI regressions and an installed-CLI trial passed. In S3 the same report-local F-number may occur in both the original and confirmation reports. Exercise the offline evidence and first-round replay joins as well as live history.

S3 — Canon 85 registers confirmation and later recheck blockers with their own identities. Equal F12 labels remained distinct in history and replay; independent CLI checks and legacy replay cases passed. S4 can reproduce the field investigation from .canon/canon-investigate/review-publication/f10.YIZ7/replay.py and its three observation files. The machine regressions use the installed test-review-live.py; .canon/canon/review-workflow-batch/host-fallback.json records a completed and an active host job checked without a completion notice. Keep the durable verification with R007, then update finding dispositions in the docs step.
