---
status: concluded
created: 2026-11-24
updated: 2026-11-24
revision: 1
modules: [canon]
summary: A 20-case Canon and Silk pilot found gaps in replay inputs, finding attribution, Cursor transcripts and worker boundaries before trace analysis.
refs: [D001, C001, R004]
---

# E003: D001 trace pilot on Canon and Silk

## Question

Do the records of 20 real workflows meet the seven exit conditions for building the trace report? What do their L0 code reviews tell us about batching small changes? [D001§delivery-and-acceptance: pilot exit](../designs/D001-skill-telemetry.md#delivery-and-acceptance)

## Setup

- Commit: `1b9d5cf` (Canon v0.9.1). The cutoff for both projects was the tag's commit time, 2026-11-24 13:29:08 +08:00. Capture was implemented before the earliest selected start. The sample spans subsequent capture fixes.
- Environment: Canon and Silk on Linux, with local Git history, trace and review snapshot stores, review archives, Cursor transcripts and Codex rollouts. The two main event logs contained 26 and 41 top-level starts respectively. The registered linked checkouts had no additional event logs. Untraced work is unknown.
- Command: From each project's trace store, run `git clone --mirror --no-local <project>/.canon/canon/trace/.git <scratch-mirror>`, then `git -C <scratch-mirror> fsck --connectivity-only --no-dangling`. For each ledger row, resolve `refs/trace/<unit>`, compare its first parent's tree with the recorded project base or HEAD, and read its target docs and plan from the clone. For reviews, resolve the archive's first-round `snapshot.txt`, role-specific pins and any `baseline.txt` in the originating checkout's separate review store. Compare tree IDs, file blobs and the base-to-target diff. Keep confirmations and later rechecks separate.

Freeze five roots for each project and host pair before examining outcomes in detail. Within each group, sort roots by unit ID. Keep every root containing an L0 code review, then add the earliest root with slices, the earliest handoff or blocked root and the earliest unclosed root, where available. Fill remaining slots at evenly spaced positions in the unselected roots, including both ends when there are at least two slots. Select the middle when there is one slot and round ties to even. Keep every descendant. This deliberately samples difficult cases and all four recorded L0 code reviews. Rates below describe these cases only.

The ledger identifies each root and child, the line numbers in the project's `.canon/canon/trace/events.jsonl`, and the start and end commands in the host conversation named by the start event. For slices, the end column names the commit that first marked the slice done. For Codex, match the command to its returned unit ID. For Cursor, match its arguments in order. Check reviewer files and worker runs against the conversations. `local-db` marks the two Cursor calls recovered separately by conversation, command arguments and timestamp. The checked-in evidence contains no transcript text or private source. [Case ledger](E003/cases.tsv)

## Results

The 20 roots contain 48 units, including 20 review units and 11 slices. The 20 review units comprise nine gates, two follow-ups and nine code reviews. One gate ended in handoff.

| D001 exit condition | Result | Observation |
|---|---|---|
| At least 18 top-level starts with an end or genuine interruption | Pass | 19/20 had an explicit end, with 18 delivered and one handoff. Silk `20261118T035910Z-24d017` had a start only. Its cause is unknown. |
| Every review's dispositions match its conversation | Fail | All 20 event payloads match the submitted JSON exactly, 11 inline and nine from archived inputs. The 157 recorded finding rows include duplicates across axes. One historical gate also omitted two reviewers whose first reports and confirmations survive. |
| Parent, tier and outcome agree with the host | Pass for the observed fields | All 48 starts were corroborated, including inherited slice fields, alongside all 36 explicit ends, 11 implicit slice ends and one open start. No tier escalation occurred in this sample. The worker timing test below compares actual runs with those implicit ends. |
| Clones reproduce actual inputs | Fail | All 48 event refs and their base or HEAD trees were recoverable. All 50 named document revisions and 11 slice headings matched. Only 17/20 first-round review trees equalled the trace tree. No sampled gate exercised an as-built second parent. |
| Every Cursor and Codex unit is found in its host record | Located 48/48. The specified JSONL lookup is incomplete | The exported records contain start anchors for 46/48. Both missing starts have ends in the named Cursor transcript and matching start commands in the local Cursor database. A reader limited to the documented files cannot locate the start of either span. |
| Every worker run falls inside one slice unit | Fail | Nine of 11 runs fit. Two workers returned their final reports after the slice commit. Each slice had one start and one worker. The sample contained no resumed or replacement runs. |
| No snapshot skipped because the sandbox could not write | Pass | Zero skips among the 48 selected starts and zero among all 138 starts in the two logs before the cutoff. Both hosts were represented. |

**Review inputs.** Three first-round target trees were absent from the independent trace clones. A separate empty bare repository fetched the three pinned targets and one explicit baseline from their original review stores, with no alternates. It passed `git fsck --full` and reproduced the reviewed inputs. This recovery depends on retaining the originating review stores. [Compared commits and trees](E003/review-inputs.tsv)

| Project and unit | Change between trace start and actual review input |
|---|---|
| Canon `20261123T144913Z-df1ef0` | The P008 summary and its generated index entry changed at the same document revision. Both first-round reviewers pinned the later tree. |
| Silk `20261117T043746Z-801537` | One experiment result gained a line. The reviewed design blob stayed identical. The full trees differ. |
| Silk `20261123T065931Z-916d26` | Both reviewer prompts used a separately prepared baseline and target. The trace's target tree was the reviewers' baseline. Its parent was a different tree. All three reviewed files then changed before the target snapshot. The recovered pair reproduces the three-file diff. |

**Finding attribution.** Silk gate `20261118T073105Z-459748` recorded two reviewers. Four delivered reports and confirmations appear in its conversation and archive. The older format omitted the two supplemental cross-family identities. The R004 fix added keyed sources for future records. At Silk code review `20261120T134358Z-d5efff`, both axes reported the same merge-amendment and template-comment defects. The closing event credited four separate findings. Canon `20261113T111039Z-248a5a` also counted the shared post-merge concurrency defect separately. Retain the original dispositions when interpreting these cases. [R004§review-history: review history](../archived/reviews/R004-silk-canon-field-feedback.md#review-history)

**Host and worker boundaries.** The Silk Cursor export contained the ends of `20261118T042829Z-09e0ed` and `20261118T073105Z-459748` at lines 195 and 187. The two corresponding terminal calls in Cursor's local `cursorDiskKV` recover the tier and parent. The earlier open design has its own start in another conversation. For the seven Cursor workers on Canon P006, each foreground task returned before the slice commit. For the four Codex workers on P007, the child rollout's final message and `task_complete` locate the actual return. S2 committed at 12:05:25 UTC and returned at 12:05:32, after S3 started at 12:05:29. S3 committed at 12:17:24 and returned at 12:17:28. Subsequent notification delivery in the parent was excluded.

**Boundary costs.** The event logs contain 48 accepted starts, 36 accepted ends and one later recheck for this cohort. At v0.9.1 on local ext4, an isolated clean checkout with 20,000 tracked files and 20 skill directories covering 1 MiB of content ran one cold start and 20 warm start/end pairs. Nearest-rank p95 was 231.812 ms for start and 70.869 ms for end, under the 300 ms budget. The cold start took 455.537 ms. These are command costs on this machine. [Raw timings](E003/latency.tsv)

**The four L0 code reviews.** The counts are descriptive, per case. The cases span different host, model and skill combinations. They include no controlled comparison with a reduced reviewer set.

| Project and unit | What the original review establishes |
|---|---|
| Canon `20261113T111039Z-248a5a`, generated initialization instructions | Six accepted rows, with overlap on concurrent editing. Spec also raised the design contract of generated instructions. Standards identified ambiguous trigger wording. Even a one-line instruction can change behavior in every downstream checkout. |
| Silk `20261120T134358Z-d5efff`, commit-title hook and CI | Four accepted rows describe two shared defects. Local-hook and CI changes can be reviewed together against the same commit-title rules and fixtures. |
| Silk `20261123T065931Z-916d26`, review launcher | The record contains 18 accepted rows, including three blocker rows. Its original diff required the separate recovery above. Exclude it from single-snapshot replay scoring. |
| Silk `20261124T041351Z-1320fa`, Canon upgrade | Both axes reported the same two gaps in the project rules. The event merged them into two findings. A dependency upgrade, retirement of a local helper and migration notes fit one compatibility review when the same before-and-after checks cover them. |

## Conclusion

The fixed sample fails the D001 pilot. The report implementation remains gated. First bind a review's actual baseline and first-round target to durable trace objects and test recovery after the separate review store is unavailable. Recheck the three recorded counterexamples. Preserve missing historical reviewer attribution and distinguish duplicate rows before using axis totals. Validate partial Cursor exports and await a worker's final report before committing its slice. A successful recheck needs evidence for each failed condition. [D001§known-issues: pilot blockers](../designs/D001-skill-telemetry.md#known-issues)

For small changes, group fixes that change one contract and share an acceptance test. The first capture batch can pair baseline retention, target retention and one clone-only diff regression. Cursor transcript recovery and worker completion have different evidence and tests. Another candidate from the backlog is the research form for `new E` and validation of its Setup fields. The same research-only, run-only and mixed documents can exercise both commands. Wording, examples and links under one existing rule can move together. Keep the required reviewers and confirmations when a batch changes a hook, launcher, permission or generated instruction. Four L0 cases, including two with duplicate rows and one with a mismatched replay input, cannot establish a threshold for reducing reviewers. [C001§ideas: experiment forms and code review scaled to risk](../concepts/C001-canon-backlog.md#ideas)
