---
status: running
created: 2026-11-24
updated: 2026-11-24
revision: 1
modules: [canon]
summary: Reconcile review attribution, Cursor anchors and worker chronology for the frozen Canon and Silk pilot and two preselected Codex slices.
refs: [D001, E003, E004, P009]
---

# E005: D001 pilot evidence reconciliation

## Question

Can independently corroborated evidence resolve attribution and host lookup on the frozen Canon and Silk sample, and do the two preselected worker runs meet the corrective exit condition? [D001§delivery-and-acceptance: pilot exit](../designs/D001-skill-telemetry.md#delivery-and-acceptance)

## Setup

- Commit: the approved D001 worker criterion is at `71a5edf`. P009@r1 at `d1454e9` selects its S1 and S2 in Canon on Codex before either starts.
- Environment: the two projects, ledger and cutoff from [E003: original pilot](E003-d001-trace-pilot.md). The original 20 roots contain 48 units with 20 review ends and 11 slices. The project archives, Cursor's named transcripts and optional local state database, and the Codex parent and worker rollouts are read locally. Publish record identifiers, evidence locations and digests.
- Command: recheck the original ledger, the [E004 clone fingerprints](E004/clone-checks.tsv), each correction against its sources, and the worker runs against their slice boundaries. Frozen and prospective denominators are separate.

## Results

All 20 archived ends were reconciled. Their 157 raw rows expand to 176 references. Two additional reports supply 20 omitted findings. Of these 196 references, 193 originated in the first round and three during confirmation. The 19 delivered reviews support 113 accepted or deferred defect groups. The 36 source findings whose grouping is disputed remain outside those totals. Two compound findings have evidenced mixed decisions and no single overall disposition. [Per-review evidence and reproduction](E005/review-reconciliation.md)

The original exports locate 46/48 starts. Two uniquely matched terminal results in the named Cursor database bring the located total to 48/48. Nine of eleven frozen worker runs fit within their slices. Canon P007 S2 and S3 each returned after its closing commit. Their incomplete spans are excluded from full-worker duration, cost and contribution measures that require containment. [Host records, worker intervals and reproduction](E005/boundary-reconciliation.md)

## Conclusion

The readiness decision follows the seven exit checks after both observed slice commits.
