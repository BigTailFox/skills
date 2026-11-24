---
status: concluded
created: 2026-11-24
updated: 2026-11-24
revision: 1
modules: [canon]
summary: All three recovered review inputs survived an independent trace clone. Three other pilot criteria still fail on the frozen Canon and Silk cohort.
refs: [D001, E003]
---

# E004: D001 review input revalidation

## Question

Can canon retain the inputs behind E003's three discrepancies after the originating checkout and its review store disappear? Does the original 20-workflow cohort now meet the conditions for building the report? [D001§delivery-and-acceptance: pilot exit](../designs/D001-skill-telemetry.md#delivery-and-acceptance)

## Setup

- Commit: `9cbb516`, canon version 80. E003 fixed the cohort and cutoff at `1b9d5cf`.
- Environment: Linux, local Git, Canon and Silk's original trace archives, review objects and host records. Keep the 20 roots and all 48 units in the original ledger. Reconcile each start, boundary, document revision and submitted disposition against its recorded location. [Original ledger](E003/cases.tsv)
- Command: In an isolated checkout, issue a fresh `trace start` and `trace end UNIT delivered --dir ROUND` for each counterexample. Copy the archived first-round target into the round and supply the actual baseline from the prompt or the archived pin. Move the resulting trace store aside and take the checkout and its review store offline **before** running `git clone --mirror --no-local` from the isolated trace store. Check that both stores lack alternates and run `git fsck --strict --no-dangling` in each.

For the full-document case, compare the tree ID, recursive NUL-delimited tree listing and reviewed file bytes. For each patch, verify both tree IDs and compare `git diff --binary --full-index` byte for byte, both across the whole tree and with the prompt's path scope. Record SHA-256 digests of the matching bytes. Separately clone the trace from the live K3 code review and check its recorded end against both first-round prompts. [Pins, capture IDs and fingerprints](E004/clone-checks.tsv)

## Results

| Review input | Evidence for the baseline and target | Independent clone |
|---|---|---|
| Canon P008 plan | Both prompts requested the whole plan. The fresh capture used `none` and the archived target after the summary edit. | The target tree and the complete plan matched. The retained commit had no parent. |
| Silk D003 design | The prompt named project commit `e391747`. The archived target included an intervening experiment-log edit. | Both the full patch and the design-scoped patch matched. |
| Silk launcher | Both prompts and the archive named the separately prepared baseline `a3a6876` and target `258f962`. | The reviewed three-file patch matched byte for byte. |
| Canon K3 code review | Both live reviewers used `3f6f0f0` and initial target `bb04d21`. Their confirmation used a later target. | The retained pair reproduced the initial patch. The opening ref and later confirmation remained separately identifiable. |

All three recovered pairs passed when submitted through the repaired capture path. The fourth row is this batch’s live code review, closed by the repaired capture path. The original 48 ledger rows still matched E003 byte for byte. In those historical captures, 17/20 review targets matched their opening trees and three differed. The fresh captures and the live review are outside that historical denominator. The frozen cohort contains no as-built gate. A command-level regression covers an as-built commit that changes before dispatch. [Original discrepancies](E003/review-inputs.tsv)

| D001 pilot condition | Frozen-cohort recheck |
|---|---|
| Top-level closure | 19/20 had explicit ends, including one handoff. One remained open. |
| Finding attribution | In Silk's commit-title review the two reports describe the same two defects in four recorded rows. A separate gate recorded two of four delivered reviewers. D001-K4 remains open. |
| Parent, tier and outcome | The recorded fields agreed for all 48 observed units. The sample contained no escalation. |
| Input recovery | All 48 opening refs were readable. The three historical discrepancies and their fresh captures are accounted for above. |
| Host lookup | Exported records contained 46/48 start anchors. Cursor's local database supplied the remaining two. D001-K5 remains open. |
| Worker boundaries | Nine of 11 fit. The P007 S2 and S3 terminal reports followed commits `81c92e6` and `30596c4` by 7 and 4 seconds, respectively, at whole-second resolution. D001-K6 remains open. |
| Sandbox writes | None of the 48 selected starts skipped a snapshot. |

The latency check used the E003 fixture with 20,000 tracked files and 20 skill directories. Each code review used a fixed project baseline. One tracked file changed between start and dispatch in every round. Across 20 warm rounds, nearest-rank p95 was 329.306 ms for start and 117.496 ms for end with retention. A separate interleaved comparison exercised the earlier and current start implementations on the same fixture. Their clean-start p95 values were 327.189 and 328.066 ms, and their dirty-start values were 326.255 and 326.217 ms. Both versions exceeded the 300 ms start budget in this code-review workload. E003 timed clean implementation units. [Per-round timings](E004/latency.tsv)

## Conclusion

D001-K3 passes the three recovered cases and one live review. D001's report gate remains closed on attribution, host lookup and worker boundaries. Counts of independent reviewer contributions and timings based on complete host spans still need those repairs. [D001§delivery-and-acceptance: pilot criteria](../designs/D001-skill-telemetry.md#delivery-and-acceptance)
