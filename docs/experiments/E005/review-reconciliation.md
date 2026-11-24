# Review findings in the frozen cohort

All 20 review ends in the [E003 ledger](../E003/cases.tsv) have identifiable source evidence. Their 157 raw rows record 147 accepted, nine declined and one deferred disposition. Expanding their `by` arrays gives 176 references. The two omitted Silk reports add 20 findings. Three of the resulting 196 entries first appeared during confirmation. The 193 first-round findings came from 39 delivered reports, including one report with zero findings. [Evidence table](review-evidence.tsv)

| Population | Ends | First-round reports | First-round findings | Accepted | Deferred | Declined | Unknown disposition |
|---|---:|---:|---:|---:|---:|---:|---:|
| All frozen ends | 20 | 39 | 193 | 180 | 1 | 10 | 2 |
| Delivered ends | 19 | 38 | 183 | 170 | 1 | 10 | 2 |
| Handoff | 1 | 1 | 10 | 10 | 0 | 0 | 0 |

Of the 183 source findings in delivered reviews, 36 have disputed group membership. The other 147 map to 123 distinct unit-local groups. Of those groups, 112 have an accepted disposition, one deferred, nine declined and one unknown. The 113 accepted or deferred groups include 23 with multiple contributing reports and 90 with a single contributing report. For 64 of the 90 single-source groups, every participating first-round prompt names a common scope. The remaining 26 retain single-source observations with unknown exclusivity. Eleven delivered reviews have comparable scope. The scope receipts pin the complete prompts and their target lines, including follow-on targets when present. [Source identities and adjudicated groups](review-adjudications.tsv)

## Cases that change interpretation

- **Silk `20261120T134358Z-d5efff`.** The spec and standards reports each independently numbered two findings. Rows 1 and 3 identify the same merge-amendment defect. Rows 2 and 4 identify the same template-comment defect. Both groups were accepted. Each axis has two joint and zero exclusive contributions across the two defects. The local archive's `verification.md:L5` and `verification.md:L6` independently identify the two paired checks.
- **Silk `20261118T073105Z-459748`.** The raw end contains 19 rows citing 20 source findings from two recorded reviewers. All four first-round reports together contain 40 findings. The two identifiers recorded at close stay bound to their original `same-model` and `cross-family` reports. The recovered Grok and Gemini dispatches use `cross-family-2` and `cross-family-3` respectively in this table, following their order after those two reviewers in the final reviewed document. Each dispatch's own archive identity, initial prompt, first report, fixed-finding prompt and terminal confirmation match its child conversation. All four first-round prompts name the same four target documents. The parent decision identifies the models and exceptions. Two completed Cursor task records independently bind the original prompts and returned child IDs to the requested Gemini and Grok models. Child and parent line numbers, database keys and digests are in the [host receipts](review-host.tsv).
- The Gemini confirmation resolves each of its 11 enumerated first-round findings. The parent explicitly declined part of F4, leaving that compound finding's overall disposition unknown. Grok resolved each of its nine enumerated findings, then raised a new blocker, N1, during confirmation. The parent accepted its repair. N1 belongs outside the first-round count. Of the 20 omitted first-round findings, 19 therefore have a corroborated accepted disposition and one is unknown. The parent also explicitly declined the original cross-family reviewer's remaining F11 request. Raw row 2 had attributed one accepted disposition to both that reviewer and `same-model:F2`. The evidence table retains the raw accepted value and the separate final declined decision for `cross-family:F11`. The competing source groupings remain unknown. The two parent records can be checked at lines 183 and 197 in the named conversation. [Host receipts](review-host.tsv)
- **Silk `20261116T042358Z-20c8a5`.** This was an explicitly requested cross-family pass following earlier same-model gates. Its archive states in `merge-notes.md:L13` that part of F7 was fixed and the remainder declined. The raw accepted disposition survives. A single adjudicated outcome for that finding is unknown.
- **Silk `20261123T065931Z-916d26`.** The two first reports contain eight and seven findings. Raw rows 9, 10 and 18 refer to new blockers in the two confirmation reports. Rows 9 and 18 corroborate the same later defect. These three accepted rows retain their confirmation file locations and hashes. First-round counts exclude all three.
- **Silk `20261120T134507Z-9a9e00`.** The same-model report accounts for all ten accepted rows. The other requested report was pending at handoff, as its archived pending notice records. The inventory includes the notice and its digest. Contribution denominators exclude this review.
- **Canon `20261113T101311Z-9f81b7`.** The cross-family reviewer delivered an approving report with zero numbered findings. Its file, digest and identity remain in the report inventory.

## Disputed group membership

One independently numbered finding can request several corrections. When another report covers only part of it, a single group assignment would credit the whole finding to the narrower source. The following claims retain their individual dispositions with an unknown group. The table includes exact report lines for each. [Evidence table](review-evidence.tsv)

| Project and unit | Sources | Reason |
|---|---|---|
| Canon `20261113T111039Z-248a5a` | spec F3, standards F3 | Both requested a separate commit. The spec finding also requested a wording change. Raw rows 2 and 4 separately establish the shared post-merge concurrency defect. |
| Canon `20261113T131039Z-043b4f` | spec F1 and F3, standards F1–F3 | Two spec findings combine dispatch-site and qualifier changes that the standards findings divide differently. |
| Canon `20261123T083937Z-951359` | spec F1 and F2, standards F1 | The standards finding combines a missed path and a spurious match. Each has a separately numbered spec finding. |
| Canon `20261123T144913Z-df1ef0` | same-model F3, F5, F6 and F7, cross-family F4, F6, F9 and F5 respectively | Four recorded merges combine narrower checks with additional guide updates, acceptance cases or routing rules. |
| Silk `20261118T073105Z-459748` | same-model F2, cross-family F11, Gemini F9 | The accounts differ over which contract changes were required and accepted. |
| Same Silk gate | same-model F4 and F8, cross-family F3, F4 and F12, Gemini F3, F4 and F10, Grok F1, F4 and F9 | Ownership, location, typing and example corrections span several independently numbered claims. Part of Gemini F4 was explicitly declined. |
| Silk `20261124T041326Z-7a4fbc` | same-model F1, cross-family F1 | A shared implementation suggestion addresses two different concerns about tracking and retaining an earlier event. Equivalence of the required fixes is uncertain. |
| Silk `20261123T065931Z-916d26` | spec F4, standards F2 | The spec finding includes two terminal-outcome windows. The standards finding addresses the publication window. |

## Reproduce the check

Set the variables below to the two project roots, the directory containing Cursor's `projects/` directory and its local state database. The program reads the original event logs, archives and named child conversations and model-dispatch records in place. It prints JSON containing unit IDs, counts and diagnostic categories. A missing archive or ambiguous boundary returns exit 1 and withholds the affected unit's contribution counts. A handoff retains its observed counts with `coverage=partial-handoff`. A verified row means the checked files support the published mapping, including its explicit unknowns.

```sh
python3 docs/experiments/E005/check_reviews.py \
  --project "Canon=$CANON_PROJECT" --project "Silk=$SILK_PROJECT" \
  --cursor-home "$CURSOR_PROFILE" --cursor-state-db "$CURSOR_STATE_DB"
python3 docs/experiments/E005/test_review_evidence.py
```

The [adjudications](review-adjudications.tsv) are the human comparison of defects and requested corrections, keyed by project, unit, actual report stem and independently numbered finding. They pin each full report, including the report with zero findings. The `scope_lines` and `prompt_sha256` fields locate the compared target blocks in the two or more participating prompts. A verified common block supports exclusive credit. Differing or unavailable blocks leave exclusivity unknown. The [checker](check_reviews.py) verifies the selected project's unique start and end against the frozen ledger, checks the delivered reports and their identities, and resolves each locator to its numbered finding. For an omitted reviewer it checks the separate dispatch, first report, fixed-finding prompt and terminal record before accepting that source's disposition. The synthetic [regressions](test_review_evidence.py) exercise the same command.

Use [review-evidence.tsv](review-evidence.tsv) as D001's `--review-evidence` input. `raw_row` is one-based within the end's findings array and empty for an omitted source. Within the named project, `source_locator` is relative to `.canon/canon/trace/<unit>/` and gives the one-based line in the actual report. `end_sha256` hashes the exact end line without its newline. `report_sha256` hashes the original file bytes. `phase` distinguishes first-round and confirmation-only sources. `reviewer_key` keeps independent contributors identifiable across the two phases.
