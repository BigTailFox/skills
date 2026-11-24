---
status: in-progress
created: 2026-11-24
updated: 2026-11-24
revision: 1
reviewed: 1
reviewers: [gpt-6.2-astra]
modules: [canon]
summary: Verify review attribution, partial Cursor exports and worker boundaries on the frozen D001 pilot and two preselected live slices.
refs: [D001, E005]
based_on: [D001@r18]
---

# P009: Reconcile the D001 pilot evidence

Implements [D001: Skill telemetry with canon trace](../designs/D001-skill-telemetry.md).

## Current state

Both slices are done. Verify the prospective pair at its two Git boundaries, then review the full batch.

## Slices

### S1: Reconcile the original review findings

Status: done

Risk: A duplicate claim credited as exclusive would change the conclusion about either review axis.

Work in the attachments of the experiment titled “D001 pilot evidence reconciliation”, created at implementation start. Reconcile all 20 review ends in the frozen E003 ledger with their original first-round reports in the named project's trace archive. Produce a redacted, reviewable mapping from raw disposition rows and independently numbered report findings to verified defect groups, contributors, dispositions and evidence locations. Include missing sources, disputed overlaps and partial coverage explicitly. Provide an experiment-local read-only check of the mapping against those archives. Accept project paths as inputs. Use temporary synthetic fixtures for negative tests. Keep private reports and host records local. The orchestrator supplies project and host paths in `.canon/canon-implement/P009/inputs.json`. The two omitted Silk reports also have original dispatch identifiers, explicit fixed-finding confirmation prompts and terminal reports; use those to corroborate dispositions where they support them. Publish the TSV in the design's `--review-evidence` format, including end/report digests and verifiable locators.

Tests at the evidence table and checker: each original row and delivered source is accounted for once, with a unit and a locator. In Silk's commit-title review, raw rows 1 and 3 (spec:F1 and standards:F1) describe the merge-amendment defect. Rows 2 and 4 (spec:F2 and standards:F2) describe the template-comment defect. The two groups give zero exclusive defects per axis. Test the crossed pairings too: reject them or withhold both joint and exclusive credit for the disputed groups. The four-report Silk gate preserves the two recorded identities and shows what the other two reports establish, including unknown dispositions where applicable. Exchanging a source, removing a report or giving incompatible rows the same group cannot silently grant exclusive credit. Only verified, appropriately scoped results enter a denominator.

### S2: Locate missing Cursor boundaries and verify the worker sequence

Status: done

Risk: An ambiguous local match could attach another unit's start or reveal private conversation content.

In the same experiment, reproduce the 46 exported start anchors from the E003 ledger and independently locate the other two in an explicitly supplied read-only Cursor state database. Provide a focused, runnable evidence check for the two gaps and redacted fixtures for a matching, missing and ambiguous candidate. Test the export-first route, the observed database record layout, other conversations and differently parameterized commands. Both original terminal results carry the printed trace ID. Verify the successful result alongside the executed command. Reject a contradictory or rejected result. Preserve the evidence location and limit printed results to safe metadata. An unavailable database or incomplete evidence yields unknown. Keep original traces and host records unchanged.

The preselected pair is Canon, P009@r1, S1 then S2 on Codex. Cite the reviewed plan commit as the selection record. The orchestrator runs them using the existing wait-before-commit rule. Wait for the terminal report before committing each slice's done transition. After S2 is committed, the orchestrator inventories the parent session's dispatches and resumes for both slices and all linked child sessions, including replacements. Verify each dispatch occurred at or after its own recorded slice start. Bind every attempt to its terminal event and verify it occurred before the earliest closing boundary. Account for timestamp precision using host event order where needed. A missing or extra attempt, unknown endpoint or new violation fails the preselected pair and keeps step 3 closed. A later repair trial would be reported separately.

Tests at the local evidence check and the host/Git records: 46 export starts plus two uniquely verified database starts cover the frozen 48 when the private inputs are present. Missing or ambiguous evidence stays unknown and contributes no inferred activity. Verify the eleven historical intervals at the available precision before the S2 commit. The prospective verdicts and seven-condition decision belong to the orchestrator's postcommit acceptance check.

## Notes

The experiment checkers validate the specific pilot evidence. They run outside the installed skills and do not implement the nine-question report. The two slices share one full code review. The orchestrator rechecks all seven exit conditions, records outstanding failures and starts the report only if all six other conditions pass and D001's corrective worker check passes. Link each observed historical exception to the affected measurements it excludes. Keep raw evidence and the original cohort denominator intact.

## Log

- Planned against D001@r18.
- Started at d1454e9b0dea2ee6139034f766e219ddd46ce7c8. The [E005: pilot evidence reconciliation](../experiments/E005-d001-pilot-evidence-reconciliation.md) records the frozen and prospective outcomes.
- S1 done. The 20 review ends contain 157 raw rows. The checker verified 39 first-round reports, including the two omitted reports, and separated three confirmation-only claims. The 19 delivered reviews support 113 valid groups. The two fully shared commit-title defects give neither axis exclusive credit. The evidence retains disputed groups and compound dispositions. Eighteen checker tests passed. The parent received the worker's final report and verified its terminal event before this commit.
- S2 done. Local inputs located 46 exported starts and two unique Cursor database executions. The eleven original worker intervals include nine contained and two outside. All 35 tests passed, including 17 start-evidence tests. The parent received the second worker's final report and verified its terminal event before this commit.
