# Review evidence

## First-round review input

Run `review start` with the topic, kind, tier, initial target revisions and additional requested reviewers. Pass the printed trace ID as `--unit` when available. Use `--base REF` for the prompt's diff, `--base none` for a full document, and omit `--base` for a mixed follow-up whose prompts record each path's inputs. A code review needs a baseline. Supply `--snapshot COMMIT` for a prepared target. Otherwise the command snapshots the live checkout. Read the verified commits from the returned directory's `snapshot.txt` and `baseline.txt` and use them in the prompts. When an input is unavailable use the full-document or revised-section fallback where applicable. Keep the pins through confirmation.

Close from the same checkout with the returned directory as `--dir`. Its `round.json` binds its files to this unit and review kind, even when a verified input predates the unit. Legacy directories keep their modification-time cutoff. A legacy abbreviated baseline is verified against the snapshot store and its project objects at close. Its archived spelling and the end record's full `review_baseline` identify that literal during offline replay. Each missing expected material produces a warning and one local retro record for the round. Continue the review on the available evidence.

Scoped `trace history UNIT` shows the retained commit at close, or `unknown`. In a mirror clone of the trace store, `refs/review-input/UNIT` holds the target tree. Its single parent holds the diff baseline when one was used. Apply the prompt's path scope and diff options. For a live diff in that bare clone, set `GIT_WORK_TREE` to an empty scratch directory and `GIT_INDEX_FILE` to a new file path for the following commands. Load the target with `git read-tree <review_input>`. Feed the prompt's untracked paths, NUL-delimited, to `git update-index --force-remove -z --stdin` in that index. Compare `git diff --cached <review_input>^ -- <scope>` using the original options. This preserves staged deletions whose files remain on disk. Read the listed files and modes from the complete target tree.

## Handed-off reviews

Append each printed review unit ID to `trace-unit.txt` in the round's directory. Keep the latest ID and its predecessors with `pending.md`. On handoff, run the coverage check with the completed reports and their dispositions. It saves the partial record and names the outstanding passes. End any open trace unit with that evidence and point the handoff to the pending record.

On resume, use `trace history UNIT` to verify the handoff. For an older record without an ID, find a candidate in `trace history` and verify its kind, exact targets or recorded code-review base and plan, and round against the saved prompts, reports or archive. Use only an unambiguous match. If a continuation already exists, check its status. An open one belongs to the session resuming it. A delivered one holds the completed evidence. A further handoff is continued by its own ID.

Add `--continues UNIT` to the trace start with the same primary revision, or the same recorded base and exact plan revision for a code review. Two plan-less code reviews can match on their recorded base. Keep `--parent` for the current enclosing workflow. When the origin is uncertain, unavailable in the writable store, or tracing is off, note the gap in `pending.md` and resume from its saved state.

Start a fresh round for the same topic. Compare the targets with the latest pending snapshot, verify the reports and confirmations against the changes they cover, and dispatch only the missing work. For each reused source, copy its original report, prompt, ID and applicable snapshots and confirmations with timestamps preserved. Include its original author, key, assessed targets, findings and confirmations in the current dispositions. In the coverage file set `"handoff": {"prior_round": "<predecessor round path>", "sources": ["same-model"]}` with the actual source keys. The check compares each report and its authorship with the predecessor. Keep its pending record and use the fresh directory for the final archive.

## Checking coverage

Run `canon.py review check ROUND --input FILE` before setting review fields or completing code review, including with tracing off. Use the [end dispositions](#end-dispositions) and repeat `--target ID@rN` for each target added after start. The command reads each source's complete `<key>.md` and assessed revisions, checks them against the live revisions, and prints the actual readers by target. A missing role returns a failure identifying what still needs review. A missing replay pin or prompt warns and records the gap while established coverage stands. Keep the saved `dispositions.json` and `coverage.json` in the round for later use.

Give an additional independent pass its own key at start, e.g. `--require cross-family-2` when the ordinary cross-family pass is already required. A numbered supplemental source normally serves its ordinary role. If it extends a separately requested reader's pass, supply `--coverage FILE` with a JSON object such as `{"assignments":{"cross-family-3":"cross-family-2"}}`. The source serves one pass, and the requested reader's original and supplemental reports must identify the same actual model.

For a permitted delegated follow-up, include a `delegations` list in that file. For example, `{"delegations":[{"pass":"cross-family-2","target":"D003@r2","source":"same-model","prior_round":".canon/canon-blind-review/D003-r1/round-abc","prior_source":"cross-family-3","prior_target":"D003@r1"}]}` identifies a current delegate and the earlier full independent report that served this pass. Use the actual round path and source keys. For an older directory, verify and retain its original report and dispositions with the exact assessed revision. Use a fresh independent reader after an intervening waiver of that pass and document. A confirmation or a different pass supplies no prior full review.

For an L2 design or plan waiver, record the user's decision, missing role, exact revisions and actual coverage in `waiver.md`. Put each scoped pair on a line together, e.g. `cross-family=D003@r2`, and repeat `--waive KEY=ID@rN` for those pairs. For an L1 withdrawal, record the decision and requested cross-family key in `withdrawal.md` and pass `--withdraw KEY` on the existing round. Record only actual readers and obtain L2 approval separately.

## End dispositions

Pass one object to `trace end UNIT OUTCOME --dir DIR --input -` on stdin. A gate could record two findings merged into one claim and confirmed by the cross-family reviewer.

```json
{
  "reviewers": [
    {"role": "same-model", "model": "Reviewer-A", "id": "session-a", "targets": ["D003A@r1", "D007@r2"]},
    {"role": "cross-family", "model": "Reviewer-B", "id": "session-b", "targets": ["D003A@r1"]}
  ],
  "findings": [{
    "by": ["same-model:F1", "cross-family:F1"], "severity": "major", "disposition": "accepted",
    "confirmed": "resolved",
    "confirmations": [{"reviewer": "cross-family", "result": "resolved", "snapshot": null}]
  }],
  "new_blockers": 0
}
```

- Give each independently numbered report one reviewer entry. Use roles `same-model` or `cross-family` for a gate or follow-up, and `spec`, `standards` or `cross-family` for a code review. The first report uses its role as its `key` by default. Give each additional report of that role a unique key such as `cross-family-2`, even when the same reviewer wrote it. Numbered keys start at 2, allow gaps and have no leading zeros.
- Record the actual author's `model` with its spelling preserved, prefixed with `manual:` for a user-run review. Take `id` from `<key>-id.txt`, using null for an absent ID or manual run. Model and non-null ID each occupy one line of 1–200 characters. Omit failed or waived reviewers.
- For each gate or follow-up report with known coverage, supply a nonempty `targets` list of distinct canonical design or plan IDs at the exact positive revisions assessed. Omit this field for code reviews.
- Each merged finding's `by` lists every source once as `<key>:F<n>`, with positive finding numbers. A source belongs to one merged finding. Use the highest `severity` of `blocker`, `major` or `minor`. For a code review include `axis`, either `spec` or `standards`.
- Set `disposition` to `accepted` for a fix in this work, `declined` for a declined finding, `escalated` when awaiting the user, or `deferred` for work the user chose to track for later.
- For a first confirmation, list each actual confirmer's reviewer key, verdict and full 40- or 64-hex snapshot ID, or null when unavailable. A delegate uses its own key. Set `confirmed` to `not-resolved` if any confirmer returned it, otherwise `resolved`. Omit both confirmation fields for findings never sent for confirmation. Set `new_blockers` to the count newly reported in confirmation, otherwise 0.

## Introduced blockers and later rechecks

```text
canon.py trace blocker UNIT LABEL --reviewer KEY --report STEM --snapshot OID|unknown [--from FINDING]
canon.py trace recheck UNIT FINDING --reviewer KEY --snapshot OID --result resolved|not-resolved
                       --report STEM --order N|unknown [--model MODEL]
```

Register each blocker using the actual confirmation report stem, confirmer key and snapshot, or `unknown` for an unavailable confirmation snapshot. Use its report-local F, B or N label and positive number. For a historical unlabelled report, use B plus the one-based order of its new blocker only when the text identifies the claim unambiguously. Otherwise keep its identity unknown.

For a recheck, use any unambiguous `<key>:F<n>` source of an original merged finding, or the registered `blocker:STEM:LABEL`, even when the reports use the same label. Use the actual rechecker's key. Supply its exact model on first use of a previously unlisted key. For an existing key, omit the model or repeat its spelling and case. Give the full 40- or 64-hex snapshot ID from the evidence, including after Git pruning.

If the user requests a recheck before closure, obtain the result, retain its report, and close with the original findings, first verdicts and first-confirmation blocker count intact. Then register each introduced blocker before appending its saved recheck. If a recheck itself introduced a blocker, first append that recheck, then register the new blocker using its actual report, reviewer and snapshot and `--from` the claim rechecked. Use the same order for a closed unit. Later results belong to their own claims.

Keep `<stem>.md`, `<stem>-prompt.md`, `<stem>-id.txt` and `<stem>-snapshot.txt` in the review directory. Use a distinct stem of 1–100 ASCII letters, digits, hyphens or underscores. Give the report's verified positive ordinal for this merged finding, or `unknown` when importing evidence of uncertain order. Record only an outcome the report or preserved evidence establishes. An identical retry succeeds once. History shows the first confirmation, the ordered and unordered rechecks, and whether the exact report survives in the unit's one-time archive.
