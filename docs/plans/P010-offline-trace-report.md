---
status: accepted
created: 2026-11-24
updated: 2026-11-24
revision: 1
reviewed: 1
reviewers: [gpt-6.2-astra]
modules: [canon]
summary: Implement the read-only nine-question trace report with host evidence, verified reviewer contributions and replay eligibility.
refs: [D001, E005]
based_on: [D001@r18]
---

# P010: Report traced workflows offline

Implements [D001: Skill telemetry with canon trace](../designs/D001-skill-telemetry.md).

## Current state

Next: S1.

## Slices

### S1: Report unit boundaries, worker outcomes and measured cost

Status: todo

Risk: Pairing an incomplete host export or an overlapping worker with the wrong unit changes both cost and outcome comparisons.

Deliver the local `scripts/trace_report.py` command, its text and JSON output, and questions 4 and 6. Read D001's Sources, Units, Analysis, Reconciling pilot evidence and Privacy. Support the complete documented invocation, repeatable projects and Codex homes, an inclusive start-date filter and current-directory project default. Join the project's trace stores, Git slice status transitions, plan risk lines, parent/child and continuation relationships. Keep store identity, malformed/orphan records, open units, incomplete reviews, unknowns and source locations. Keep cases from different projects distinct and avoid counting the same physical store twice. Reuse the read-only history and Git logic from the working tree's canon implementation where appropriate. Keep all tooling outside the installable skills.

Read the named Cursor conversation exports and Codex rollouts in place. A qualifying Cursor database start requires an explicit path, one matching execution and unit, its successful result, and matching arguments, timing and conversation. Exported evidence takes priority. On Codex match a shell invocation to the result that prints the unit ID. Record unit wall time, host-recorded model/effort and cumulative token deltas only across identifiable boundaries. Retain cache, reasoning and other token components the host supplies separately. Link worker attempts using parent and child records, including resumed and replacement workers, stored dispatch IDs and native completion/termination. Compare each attempt against its slice's earliest closing boundary. Exclude incomplete worker intervals from full-worker measurements. Show separate parent and child costs, confirmed stops and unknown outcomes. Count a logical slice once across attempts and resumed units on its own plan revision. A missing commit, upper bound, user wait, same-second ambiguity or lost child cannot supply unobserved work or a precise completion.

Test the CLI with redacted real event shapes for both hosts and synthetic SQLite. Exercise fallback using a named export, missing, unique, ambiguous, rejected and other-conversation records, a missing Codex conversation ID with receipt-based lookup, time-zone offsets, a child that completes after a slice commit, multiple attempts, contradictory evidence, a paused or handed-off logical slice, and mismatched/torn token counters. Verify case IDs, source locations, counts with known and unknown coverage, grouped results, and no writes to the supplied projects, stores or host profiles. List the untraced-work caveat and the source population in both formats. For every kind, count fresh subagents launched inside the unit span and list resumes as attempts of the existing child. A CLI fixture includes an in-span reviewer launch and resume, a second launch outside the review, separate parent and child costs and their host locators. A Cursor unit with trace endpoints and a user wait retains its measured wall time. Keep private records and secrets out of source, fixtures and output.

### S2: Report reviewer contributions, confirmation and tier changes

Status: todo

Risk: Crossed report keys, stale corrections or a handoff counted twice can give an individual reviewer credit for someone else's finding.

Implement questions 1, 2, 3 and 5 at the same command. Read D001's Review dispositions, Analysis and Reconciling pilot evidence. Keep every independent report key and participating session, including zero-finding and supplemental reports. Count valid blocker/major cross-family-only groups per delivered review with an actual cross-family report, and show distinct-session cost with unknowns. Group code-review contributions by axis and tier and distinguish exclusive, shared and unverified credit. Expose raw disposition rows alongside verified groups. Use `--review-evidence` as the optional D001 table. Validate the selected project, unit, raw rows, actual reports, source locators, end/report digests and complete coverage before granting independent credit. Keep qualified partial decisions, unknown groups, rechecks, confirmation-only and disputed evidence separate. A report without adjudication retains its explicit recorded groupings and labels its attribution accordingly. Exclude incomplete handoffs from questions 1–3 and count a delivered continuation once.

Keep the original confirmation verdict, its individual evidence, new-blocker count and later ordered, conflicting or unordered rechecks separate. Infer effective tiers from descendant gates, respecting the starting tier, direct escalation targets and requests for a plan. Include each reached target once per original unit. Use compatible groups for comparisons, preserve unknown model and manifest evidence, list case IDs and locators behind each figure, and display numerator, denominator and the small-sample label where required.

Test through the CLI with different roles, repeated sessions, handoff with and without continuation, accepted and deferred severities, a nested gate, an explicit escalation, initial non-resolution followed by a resolved recheck, mismatched claim IDs and digests, and an incomplete or ambiguous correction table. Verify the E005-style four-to-two shared defect example and the two recovered supplemental roles, including a partially accepted finding. A stale source or a grouping incompatible with its adjudication must withhold affected contribution claims. Use any co-located review-adjudications.tsv and review-host.tsv companions supplied with the table to check the independently adjudicated group keys and source/model dispatches. Bind them to the same selected project, review, receipts, archive and host. The E005 table and companions support this path without a project-specific rule. Exercise both a crossed pairing and a missing supplemental dispatch. With a standalone table, distinguish the supplied human grouping from claims independently corroborated against available evidence. Preserve its raw and adjudicated counts and withhold independent credit where completeness, group membership or a recovered contributor cannot be corroborated. The pilot table's target lines and full prompt hashes support comparable-scope checks. Record single-source observations with unknown exclusivity when independent scope evidence is absent. No tests depend on either private project.

### S3: Report retro causes and cost, version mapping and replay eligibility

Status: todo

Risk: Project history, stored snapshots and reviewer input can diverge even when the document revision stays the same.

Complete questions 7, 8 and 9 and the report's skill-version inventory. Read D001's Skill digests, Analysis, Replay and Privacy. Read retro sections, applied commits, state transitions, fix-presence evidence, end-check and retro session/minute anchors. For all Git reads prohibit automatic network/lazy object fetches and optional repository writes. Test a missing partial-clone object with a fetch sentinel, unchanged object inventory and an unknown result. Compare a candidate fix's actual patch with the unit snapshot in reverse and forward using an isolated check. Keep uncertain applicability, missing snapshots and missing timing out of measured denominators. Report repeated identical commands without printing their text, before and after each fix. Report end-check wall time, tokens, raised interruptions over ended top-level units, and documented declined items. Preserve numerator, eligible cases and unknown cases even for zero matches.

For question 9 list eligible slices and first-round gate/code-review inputs, their parameters, manifests, dispositions, and steering evidence. Verify snapshot objects, base, target, first-round role pins, supplemental input equality and any as-built second-parent tree. For a prepared review, the durable synthetic target and its synthetic baseline parent may have different commit IDs from the original first-round pins. Test eligibility from their verified trees and archived prompt scope after removing the originating review store and its pin objects. Pair this case with an unverified distinct supplemental input and assert its exclusion reason. Apply the recovery rule for independently evidenced legacy inputs. Exclude handoffs, continuations, different or unknown common inputs and unverifiable as-built code with a reason. Keep later rechecks out of the original score. Report eligibility and what could be replayed. Running a replay belongs to D001's later step. Map skill file and manifest digests to matching commits in `--skills-repo`, including mixed and local versions. Group comparisons only within the same kind, effective tier, host, model and skill digest. Complete the text and JSON presentations for all nine questions so both surface coverage and allow a reader to trace a figure to its cases.

Test at the CLI with redacted host records, small isolated Git projects and trace snapshot refs. Exercise present, absent and ambiguous retro patches, session/minute matching, a declined state, repeated commands, a change and a reversion of skill content, eligible snapshots, a handoff/continuation, mismatched supplemental inputs, a changed as-built second parent, missing targets, and steering unknown when no host evidence survives. Assert that both selected project trees, Git refs/indexes, host databases and profiles remain unchanged. Then run the complete CLI on the two real projects with E005 evidence in a local output stream and verify the four frozen L0 cases against E005. The orchestrator also selects the published case IDs from the production report: assert 46/48 exported starts and 48/48 with the supplied database, 9/11 contained historical worker runs, exclusion of both known late intervals from full-worker metrics, and a separate 2/2 contained prospective sample. The CLI analyzes arbitrary projects. These fixed cohorts belong only to the acceptance check. None of the private records or full machine reports belong in the repository.

## Notes

Implement [D001§analysis: offline report](../designs/D001-skill-telemetry.md#analysis) after [E005: pilot evidence reconciliation](../experiments/E005-d001-pilot-evidence-reconciliation.md). The report may share narrowly scoped internal modules in `scripts/` and checked-in redacted fixtures under `tests/`. Its normal entry point is `python3 scripts/trace_report.py`; the installed skills and trace schema require no change. Limit output to identifiers, counts, digests, record locations and documented categories. The private paths used in the experiment are available to the orchestrator for acceptance. Use the default Python standard library and Git. Verify the whole change in one code review. The docs step adds `scripts/trace_report.py` and its owned implementation/test files to D001 paths, updates the capability and usage entry, and verifies that `canon.py which scripts/trace_report.py` names D001. Record the tests and real-project checks alongside step 3 delivery.

## Log

- Planned against D001@r18.
