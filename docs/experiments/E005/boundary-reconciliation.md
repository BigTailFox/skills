# Frozen host starts and worker intervals

The 48 starts in the [E003 case ledger](../E003/cases.tsv) have 46 exported anchors and two database anchors. All 23 Codex starts have a shell call and an output from the same call ID that prints the unit ID. Of the 25 Cursor starts, 23 have a matching shell invocation in the named transcript. The other two have a matching terminal execution in Cursor’s local database. The [start receipts](start-anchors.tsv) identify the conversation, source and record for every unit.

## The two missing Cursor starts

Both units belong to Silk conversation `0ae54eb5-dd3c-4138-a7b8-f2fc87075602`. The export retains their closing commands. Each database record contains a completed terminal call, its executed command and a result with `rejected=false` that prints the expected unit ID on its own line. The gate’s command also ran a snapshot. All times below are UTC on 2026-11-18.

| Unit | Trace start | Terminal execution | Exported end |
|---|---|---|---|
| `20261118T042829Z-09e0ed`, design | 04:28:29 | 04:28:26.684–04:28:34.436 | L195 |
| `20261118T073105Z-459748`, gate | 07:31:05 | 07:31:02.441–07:31:10.306 | L187 |

The [start checker](check_starts.py) reads shell calls from each named export first. At either gap it checks the recorded end and queries only tool-call keys from that conversation in the supplied `cursorDiskKV` table. It requires agreement between the key, call ID, raw and parsed command, targets, options, execution interval and printed result. The trace second must overlap the execution and the surrounding trace boundaries must permit it. A missing, rejected, contradictory, unsupported or ambiguous execution leaves that start unknown. The two database hits contribute two boundaries. Token usage and intermediate calls remain unmeasured by this check.

## Historical worker intervals

The [worker receipts](frozen-workers.tsv) retain all eleven attempts in the frozen sample, including the two outside their slices. Each slice has a single trace start. Seven P006 and two P007 runs are contained. The other two P007 workers reported and completed after their closing commits.

| Codex slice and unit | Commit and UTC time on 2026-11-23 | Worker final report | Worker completion |
|---|---|---|---|
| P007 S2, `20261123T115135Z-5be685` | `81c92e6`, 12:05:25 | 12:05:32.350 | 12:05:32.413 |
| P007 S3, `20261123T120529Z-96078e` | `30596c4`, 12:17:24 | 12:17:28.278 | 12:17:28.342 |

S3 had already started at 12:05:29 UTC when S2 returned. S3 returned before S4’s 12:17:30 UTC start. Exclude both incomplete worker spans from full-duration comparisons and from cost or contribution measures that need the worker contained in its slice. Both still count in the frozen containment verdict of 9/11.

The [worker checker](check_frozen_workers.py) checks each commit’s parent and tree for the slice’s transition to done. In all eleven cases the commit precedes the next sibling trace start and the enclosing end. For P006 it matches each foreground task’s prompt to its child, verifies the successful terminal record and locates the commit command after the task in the parent export. Cursor supplies event order at these boundaries. For P007 it inventories the parent’s dispatches and resumes and the linked child sessions, verifies one turn per worker, and compares the parent dispatch and the child’s final report and completion with the opening trace second and closing Git second. The parent dispatch time and child creation time are separate observations. The original eleven runs had no resumes or replacements.

## Reproduce

Supply the two project roots, both host profile directories and the local Cursor database. The start receipts hash the exact UTF-8 JSONL record bytes excluding the line ending, or the stored SQLite value bytes. A Codex start has a separate result-record digest. A Cursor database value contains both command and result. The scripts print record locations or verdicts and leave the original evidence in place.

```sh
python3 docs/experiments/E005/check_starts.py \
  --project "Canon=$CANON_PROJECT" --project "Silk=$SILK_PROJECT" \
  --cursor-home "$CURSOR_PROFILE" --codex-home "$CODEX_PROFILE" \
  --cursor-db "$CURSOR_STATE_DB" --receipts docs/experiments/E005/start-anchors.tsv
python3 docs/experiments/E005/check_frozen_workers.py \
  --canon-project "$CANON_PROJECT" --cursor-home "$CURSOR_PROFILE" --codex-home "$CODEX_PROFILE"
python3 docs/experiments/E005/test_start_evidence.py
```

Omitting `--cursor-db` reproduces the export-only result of 46/48 and returns exit 1. A successful full recheck returns exit 0. The [redacted fixtures](test_start_evidence.py) create temporary SQLite databases and transcripts under `.canon/`, including unique, missing, duplicate and other-conversation candidates.
