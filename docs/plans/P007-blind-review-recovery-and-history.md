---
status: in-progress
created: 2026-11-23
updated: 2026-11-23
revision: 1
modules: [canon]
summary: Recover interrupted blind reviews, credit the reports each revision received and query the complete trace history of findings and rechecks.
refs: [D003, D007, D001, R004]
reviewed: 1
reviewers: [gpt-6.2-astra, gemini-4-neon-xhigh]
approved: 1
based_on: [D003@r11, D007@r9, D001@r15]
---

# P007: Blind review recovery and history

Deliver findings F4, F5, F6, F10 and F11 in [R004: field feedback](../reviews/R004-silk-canon-field-feedback.md). Read historical records first, then capture findings and rechecks. Select and recover external reviewers through the installed skills. Finally, link the trace of a handed-off review and finish the gate with the reports each target received.

## Current state

Next: S4

## Slices

### S1: Read the history of an existing trace

Status: done

Risk: A linked worktree can have records in two places. Missing boundaries can make a parent's and child's durations look like separate contributions to a single total.

Add `canon.py trace history [UNIT]` to the trace dispatcher and list it in the Tool table in `canon/SKILL.md`, where it can be found even when tracing is off. Link it from `trace.md` as well. Read existing logs and archives using the checkout relationship already recognized by `worktree_main`. Keep the write probe in `trace_holder` out of this read path. Start with v1 records produced by the existing CLI. [D001§commands: historical queries](../designs/D001-skill-telemetry.md#commands) and [D001§units: slice boundaries](../designs/D001-skill-telemetry.md#units)

- Through `trace history`, replay a portable fixture with 31 starts, 30 ends, a design open for over a day, a nested gate and a follow-up with `archive=none`. Check IDs, parent, chronological listing, per-kind counts and measured seconds, with no combined total. Verify all archive anomalies in the unfiltered output as well as a focused query. Use a separate fixture for bounded and unbounded slices. The first shows its upper bound, the second stays open, and neither contributes measured seconds. Check unknown or reversed times, orphan ends, bad lines and unsupported versions alongside valid events.
- Through `trace history UNIT`, test a non-review unit, an open review, legacy findings and first confirmations with unknown authorship or coverage. Exercise unrequested, failed, missing, diagnostic-only and surviving archives. An empty log yields an empty list and an unknown scoped ID yields a trace error.
- Run both queries with tracing on and off, also in a linked worktree with main and fallback logs, a duplicate unit ID and a missing trace directory. Each record uses its own store’s archives. Mark colliding rows with their originating store (main or worktree). A scoped collision is ambiguous. From the main checkout and a linked checkout outside `.worktrees/`, only the local log is visible. Compare the file tree and contents before and after. Observe attempted writes under the trace directories as well as final contents, so a transient probe would fail the test. The existing `trace status` keeps its 24-hour view.

### S2: Record and retrieve the evidence for one finding

Status: done

Risk: Concurrent retries through different source IDs or a late import can change the apparent verdict of a merged finding.

Extend `trace end --input` and both history views in `canon.py`. Add `trace recheck` using the existing event lock, bounded lines and trace switch. Put the caller’s field reference in the `canon` skill and link it from `SKILL.md` and `trace.md`. Update the `In trace calls` paragraph so a separately requested recheck can use a saved unit ID in a session that has started no unit. [D001§commands: CLI and output](../designs/D001-skill-telemetry.md#commands), [D001§call-sites: when to record](../designs/D001-skill-telemetry.md#call-sites), [D001§event-lines: event lines](../designs/D001-skill-telemetry.md#event-lines), [D001§review-dispositions: validation](../designs/D001-skill-telemetry.md#review-dispositions) and [D001§review-files: surviving reports](../designs/D001-skill-telemetry.md#review-files)

- Close a joint gate through `trace end --input -` with two cross-family report keys, different target subsets and F1 in each report. In an old-format fixture give two merged findings the same primary source and give just one a unique secondary alias. Show both in history. Refuse a recheck through either alias if its input or its stored canonical source would identify multiple findings.
- Close a code review with an axis and a delegated confirmation. `trace history UNIT` identifies the sources, targets and actual confirmers. Conflicting first confirmations retain both results and aggregate to `not-resolved`. Read old single-role inputs unchanged. Accept a sub-design such as `D003A@r1`. Preserve a valid upper-case confirmation snapshot exactly as supplied in the end payload. Reject duplicate references, invalid keys or targets, targets on a code review, unlisted or repeated confirmers, malformed snapshots, a missing `confirmed` aggregate and an inconsistent aggregate without changing the log.
- After closing the gate, run `trace recheck` on a merged finding through two source aliases. Concurrent identical calls both report success and append one canonical event. Reject rechecks of open, non-review and disposition-less units, conflicting reuse of a report stem or ordinal, unknown findings, changes in model identity and malformed input. Check the 16 KiB limit, the `trace off` result and preservation of the original end line. Exercise a previously unlisted reviewer, case-sensitive model matching and full SHA-1 and SHA-256 snapshot IDs after pruning.
- Import order 2 before order 1 and then an unordered report. `trace history UNIT` retains the first confirmation, both ordered results with author and snapshot, the highest verified ordinal and the uncertainty the unordered evidence introduces. Show whether each report survives in the archive. Count orphan rechecks, including those whose finding is missing. Recording a recheck leaves gate approvals and target coverage intact.
- Test a linked worktree across a change of writable store. Before appending a recheck, identify the origin among the eligible logs. S4 uses the same check when linking a handoff. If the ID is ambiguous or its sole origin differs from the store selected for writing, report a trace error and append to neither log.

### S3: Select and recover an external reviewer

Status: done

Risk: A buffered host can mistake a permission wait, polling timeout or heartbeat for progress and launch a duplicate job.

Update the Subagents section in the `canon` workflow, the reviewer setup in `canon-init`, and launch, progress and stopped-run instructions in `canon-blind-review`. The reviewer file describes each launcher, login prerequisite, approved destination, permitted inputs and tool scope. Credentials stay in the provider’s existing local credential store. Update parallel launch so the caller can monitor a background command while host reviewers run asynchronously. Keep per-attempt state bound to the output in a subdirectory of the round’s local review directory, outside reviewer input and the files directly archived at `end`. [D003§launch: parallel launch](../designs/D003-subagents.md#launch), [D003§reviewers: selection and setup](../designs/D003-subagents.md#reviewers), [D003§external-review-progress: progress and recovery](../designs/D003-subagents.md#external-review-progress) and [D003§resuming-and-replacing: retries](../designs/D003-subagents.md#resuming-and-replacing)

- From each installed entry point, walk an isolated example with two family lists, a shared launcher, a default, a host-specific `none`, an ineligible same-family reviewer and legacy inline and unheaded entries. Record the selected reviewer or manual route. A targeted setup normalizes the edited family’s legacy definition and preserves unrelated families, hosts and shared definitions. At the permission step, cite the configured destination, inputs, permitted tools and applicable prior authorization. The host makes its decision for the run. Demonstrate status and read-only resume before declaring either capability.
- Follow the launch instructions with a local stand-in that returns an ID, distinguishes tool activity from a heartbeat and exposes its status separately from its terminal report. Start the command first and a host reviewer asynchronously while the caller monitors it. Also exercise a lone foreground host reviewer. Verify pending permission, actual start, first activity, silence updates and exit with elapsed time.
- An active job survives polling timeouts. Resume a terminated progressing attempt with the same binding. A terminated attempt showing only heartbeats or polls spends a stopped attempt. An already-completed job may finish publishing its report. Check the two-recovery ceiling per attempt, a single stopped-run retry, partial output, terminal failure, cancellation, fallback and a legacy route whose activity or resume operation is unavailable. Also run both explicitly requested cross-family reviewers in one first round when the first succeeds. A fresh confirmation or an ID-less fallback preserves the first report’s identity as specified in [D001§review-files: report files](../designs/D001-skill-telemetry.md#review-files).

### S4: Resume a pending gate and credit each target

Status: todo

Risk: A handoff or supplemental review can otherwise lose completed work, duplicate a continuation or credit a revision the independent reviewer never saw.

Use S1–S3 in the gate, follow-up and code review workflows. Add `trace start --continues UNIT` and expose both directions of the link in history. Update the `canon` workflow, `canon-blind-review`, `canon-handoff` and `canon-code-review` at their normal entry points. Update `canon/trace.md` and S2’s field reference for `--continues` and closure with reused reports. Save the trace unit ID with the review evidence when tracing is on, including in `pending.md` for a pending gate. A handoff points to that record. For an older record, verify the historical unit by kind, targets or base, and round before using its ID. Preserve the first and per-source snapshots when resuming a pass.

For linking units and retaining reports, use [D001§commands: continuity](../designs/D001-skill-telemetry.md#commands), [D001§event-lines: wire fields](../designs/D001-skill-telemetry.md#event-lines), [D001§call-sites: trace ordering](../designs/D001-skill-telemetry.md#call-sites) and [D001§review-files: source files](../designs/D001-skill-telemetry.md#review-files). For prompting and attribution, use [D003§resuming-and-replacing: the actual reviewer](../designs/D003-subagents.md#resuming-and-replacing), [D007§review-gate: gate steps](../designs/D007-change-tiers.md#review-gate), [D007§unavailable-cross-family-review: pending gates](../designs/D007-change-tiers.md#unavailable-cross-family-review), [D007§target-coverage: target coverage](../designs/D007-change-tiers.md#target-coverage), [D007§confirmation-round: confirmation](../designs/D007-change-tiers.md#confirmation-round) and [D007§follow-up-round: later revisions](../designs/D007-change-tiers.md#follow-up-round).

- Through `trace start --continues`, continue a handed-off gate or follow-up of the same kind and primary revision, and a code review with the same recorded base and exact plan revision. Two plan-less reviews can match on their recorded base. A null base supplies no fixed point to verify. Reject that link, mismatched revisions or bases, non-review kinds and predecessors which are open or delivered. Test a second handoff and racing starts under the event lock. History shows the immutable partial end, its successor and actual completed evidence. An uncontinued handoff stays partial. Preserve `--parent` independently.
- After the writable store changes or tracing is turned off, resume the actual gate from `pending.md` and record any gap there. Check an ambiguous or unavailable origin leaves both logs intact and that tracing off prints `trace off`. Give a reused report a timestamp before the continuation. The final dispositions retain its source, its file stays in the predecessor archive, and loss of that archive leaves the recorded result intact.
- Walk a two-target L2 gate through a rate limit after seven same-model fixes. In a fresh session, `pending.md` identifies the missing role and separates first-round and post-fix snapshots. Check resume against matching and changed targets. Exercise a returned manual report and an explicit waiver as separate outcomes. Verify revision-specific frontmatter, separately pending approval and `pending.md` resolution. After a waiver, a later revision needs fresh independent coverage or another scoped decision. Exercise L1 withdrawal and the L2 code-review manual fallback at their own entry points.
- Walk a first round with two requested independent models, both assessing the same targets and returning F1. Verify each prompt, report, session ID, revision credit and distinct source reference using the saved files, frontmatter and `trace history UNIT`.
- Add a target during fixes and again in a follow-up after a manual pass. Give each missing role full criteria, a separate source key and its own input snapshot. Check per-target reviewer lists, delegated source IDs and the resulting `trace history UNIT`. Run a targeted recheck requested before closure and one after closure. The end retains the first confirmation and precedes either recheck event. Keep each report, prompt, session ID and snapshot under its own stem.

## Notes

- Use `tests/test_canon.py` and its `TraceCase` CLI harness for automated regression tests. Build histories, sessions and reviewer examples from synthetic data, with all required inputs described here or in the designs. Record the observed S3 and S4 walkthrough results in the implementation log. The implementation session can additionally compare historical output with the locally retained R004 evidence.
- Each commit touching `canon.py` includes its regression tests, increments `CANON_VERSION` and runs the working-tree `canon.py init` to refresh `AGENTS.md`. After skill changes, run `python3 scripts/validate.py` with the default `TMPDIR`, measure D001’s text budgets and check `npx skills add . --list`. Re-run any skipped outside-checkout tests from an eligible temp directory. Keep trace call sites within 40 tokens, the first-start paragraph within 110 and `trace.md` within 420 by linking detailed field rules.
- This delivers the capture and local query stage of [D001§delivery-and-acceptance: staged delivery](../designs/D001-skill-telemetry.md#delivery-and-acceptance). The later analysis and replay stages use the eligibility rules already in D001. At close, review the whole change once at L2, update the three `implemented` revisions and disposition the five R004 findings against the commits that deliver them.

## Log

- The three design revisions in `based_on` passed their joint review in `00320cf` and were approved in `78bc169`.
- Started at `6e69d74`.
- S1 added read-only `trace history [UNIT]`. The local field replay matched 31 starts, 30 ends, six per-kind duration totals, the unmatched design and the follow-up with `archive=none`. Both switch settings produced identical output and left the log checksum intact. Seven CLI tests also cover malformed records, slice bounds, missing archives and store collisions. All 411 repository tests passed across the default and outside-checkout runs. D001 text budgets passed and skill discovery found 19 skills. No plan deviation.
- S2 added per-report coverage, individual confirmation results and `trace recheck`. In an isolated copy of a historical gate, a recheck at its preserved snapshot, using a fixture reviewer identity, left the original unresolved finding intact and showed the later resolved result. Retrying succeeded once. A conflicting retry left the log byte-identical. CLI tests also cover concurrent aliases, unknown ordering, linked stores and pruned reports. All 421 tests passed across both temp environments, the D001 budgets passed, and discovery found 19 skills. No plan deviation.
- S3 tested ten reviewer selections through each of the three installed entry points. Named defaults, host-specific `none`, legacy entries and an explicit pair of reviewers produced the expected selections. A targeted setup preserved the other families and shared definitions. Local processes demonstrated permission and activity reporting, a polling timeout with the same job active, bounded same-ID recovery, the stopped-run retry, terminal publication, cancellation and an ID-less fallback. Both requested reviewers published separate reports. A fresh confirmation retained the original IDs. The local launcher also passed 42 offline cases. All 421 repository tests, D001 budgets and discovery of 19 skills passed. No plan deviation.
