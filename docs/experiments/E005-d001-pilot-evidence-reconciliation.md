---
status: running
created: 2026-11-24
updated: 2026-11-24
revision: 1
modules: [canon]
summary: Reconcile review attribution, Cursor anchors and worker chronology for the frozen Canon and Silk pilot and two preselected Codex slices.
refs: [D001, E003, E004, P009, C001]
---

# E005: D001 pilot evidence reconciliation

## Question

Can independently corroborated evidence resolve attribution and host lookup on the frozen Canon and Silk sample, and do the two preselected worker runs meet the corrective exit condition? [D001§delivery-and-acceptance: pilot exit](../designs/D001-skill-telemetry.md#delivery-and-acceptance)

## Setup

- Commit: the approved D001 worker criterion is at `71a5edf`. P009@r1 at `d1454e9` selects its S1 and S2 in Canon on Codex before either starts.
- Environment: the two projects, ledger and cutoff from [E003: original pilot](E003-d001-trace-pilot.md). The original 20 roots contain 48 units with 20 review ends and 11 slices. The project archives, Cursor's named transcripts and optional local state database, and the Codex parent and worker rollouts are read locally. Publish record identifiers, evidence locations and digests.
- Command: recheck the original ledger, the [E004 clone fingerprints](E004/clone-checks.tsv), each correction against its sources, and the worker runs against their slice boundaries. Frozen and prospective denominators are separate.

## Results

All 20 archived ends were reconciled. Their 157 raw rows expand to 176 references. Two additional reports supply 20 omitted findings. Of these 196 references, 193 originated in the first round and three during confirmation. The 19 delivered reviews support 113 accepted or deferred defect groups. Of the 90 groups with one observed contributor, 64 have verified comparable reviewer scope and 26 have unknown exclusivity. The 36 source findings whose grouping is disputed remain outside those totals. Two compound findings have evidenced mixed decisions and no single overall disposition. [Per-review evidence and reproduction](E005/review-reconciliation.md)

The original exports locate 46/48 starts. Two uniquely matched terminal results in the named Cursor database bring the located total to 48/48. Nine of eleven frozen worker runs fit within their slices. Canon P007 S2 and S3 each returned after its closing commit. Their incomplete spans are excluded from full-worker duration, cost and contribution measures that require containment. [Host records, worker intervals and reproduction](E005/boundary-reconciliation.md)

### Prospective worker intervals

For the two preselected P009 slices, the checker enumerates the named parent's dispatches and resumes and the host's child sessions. It links each child to its task name, the matching dispatched brief, its own nonempty final report, the host completion carrying that report and its matching delivery to the parent before the slice commit. The Codex rollout stored each brief as a sealed payload. Its parent and child copies matched byte for byte. The inventory spans the selection commit through a pinned postcommit host observation at 09:01:24.461 UTC. It accounts for six parent dispatches or resumes and four linked child sessions. Two dispatches launched the selected workers. The other four calls launched or resumed the two reviewers, each independently bound to the code-review unit. Any unaccounted dispatch or child through that record fails the check, including one with an opaque brief or unrelated task name. [Observation and review-call receipts](E005/worker-observation.json) [Prospective dispatches](E005/prospective-dispatch.tsv) · [Read-only recheck](E005/check_prospective.py)

| P009 slice | Trace start (UTC) | Worker final / completion (UTC) | Git commit (UTC) | Verified attempts |
|---|---|---|---|---:|
| S1 | 08:00:42 | 08:19:07.273 / 08:19:07.347 | `631979f` at 08:19:55 | 1/1 contained |
| S2 | 08:20:01 | 08:40:21.385 / 08:40:21.443 | `6552499` at 08:41:38 | 1/1 contained |

```sh
python3 -B docs/experiments/E005/check_prospective.py --project "$CANON_PROJECT" --codex-home "$CODEX_PROFILE"
python3 -B docs/experiments/E005/test_prospective.py
```

### Small changes that can share a review

Silk's commit-title hook and CI check had two verified defects, both shared by Spec and Standards. Its Canon upgrade had two shared defects as well. An upgrade, removal of a superseded helper and migration notes can share one review when the same before-and-after checks exercise them. The Canon initialization case retained one exclusive finding on each axis. The Silk launcher's first round retained four Spec-only and three Standards-only findings. Keep both axes when reviewing changes to generated instructions, launchers or permissions. A reviewer-reduction threshold would need more than these four selected L0 cases. [E003§results: L0 cases](E003-d001-trace-pilot.md#results) · [Reconciled sources](E005/review-evidence.tsv)

The next small Canon batch suggested by these cases is the research form for `canon.py new E` and the matching `check` rules for Setup. The same three fixtures exercise both commands. One experiment cites sources, one reports a run and one does both. [C001§ideas: experiment forms](../concepts/C001-canon-backlog.md#ideas)

### Pilot exit

| D001 condition | Verified result |
|---|---|
| Root closure | 19/20 explicit ends met the threshold of 18. Eighteen delivered and one handed off. One root stayed open. |
| Review dispositions | All 20 submitted payloads matched the conversations. Reconciliation checked 39 first-round reports, the recorded decisions and the two recovered reviewers. The two mixed dispositions and 36 disputed first-round group assignments are identified in the linked evidence. The handoff stays outside completed-review totals. |
| Parent, tier and outcome | All 48 starts, 36 explicit ends, 11 implicit slice boundaries and the one open start agreed with their source records. The sample contained no tier escalation. |
| Inputs from independent clones | All 48 opening refs, 50 named document revisions and 11 slice headings matched. For reviews, 17/20 original openings matched the inputs. The three exceptions passed separately through the repaired capture and independent clone, as did a live code review. The cohort did not exercise an as-built gate. [Clone fingerprints](E004/clone-checks.tsv) |
| Hosts | Both hosts and both projects were represented. Exported starts covered 46/48. An opt-in database lookup verified the other two executions, including their exact printed IDs. |
| Workers | The original 9/11 result includes two identified late workers. The corrected check passed both preselected consecutive Codex slices. Each had one linked dispatch, one completed worker and a final report received before its commit. |
| Snapshot writes | All 48 sampled starts had snapshots. All 138 starts in the two projects through the cutoff also had snapshots. |

The E003 ledger regenerated byte for byte. The 53 Canon and 31 Silk start and end lines in the frozen cohort retained their pre-reconciliation SHA-256 digests, `43d181af3db1b68749d8b10749106e75d11afa31da80e3e5a7fd5ce83d28c4ee` and `4be11b453fcbbad6b677d042d717b9ef29ff993f1bb9669a20c3f736f5ce55cc` respectively.

The original digest receipt is in Codex parent session `01a20768-5de9-7313-89bc-736d971d3404`, line 17067 at 08:02:27 UTC, before either slice commit. To reproduce it, stream the selected start and end records in their original file order and hash their bytes including their original line endings.

```sh
python3 - "$CANON_PROJECT" "$SILK_PROJECT" <<'PYTHON'
import csv, hashlib, json, sys
from pathlib import Path
with open("docs/experiments/E003/cases.tsv") as stream:
    cases = list(csv.DictReader(stream, delimiter="\t"))
for label, root in zip(("Canon", "Silk"), sys.argv[1:]):
    ids = {row["unit"] for row in cases if row["project"] == label}
    with (Path(root) / ".canon/canon/trace/events.jsonl").open("rb") as stream:
        selected = [raw for raw in stream if (event := json.loads(raw)).get("id") in ids
                    and event["type"] in {"start", "end"}]
    print(label, len(selected), hashlib.sha256(b"".join(selected)).hexdigest())
PYTHON
```

## Conclusion

The pilot passes the corrective exit in D001@r18. This authorizes step 3, the offline report. The original worker result is 9/11 and the prospective result is 2/2. A report using these cases must retain the exclusions for disputed attribution and incomplete worker spans. [D001§delivery-and-acceptance: pilot exit](../designs/D001-skill-telemetry.md#delivery-and-acceptance)
