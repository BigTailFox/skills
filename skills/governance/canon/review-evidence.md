# Review evidence

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

## Later rechecks

```text
canon.py trace recheck UNIT FINDING --reviewer KEY --snapshot OID --result resolved|not-resolved
                       --report STEM --order N|unknown [--model MODEL]
```

Use any unambiguous `<key>:F<n>` source of the merged finding. Use the actual rechecker's key. Supply its exact model on first use of a previously unlisted key. For an existing key, omit the model or repeat its spelling and case. Give the full 40- or 64-hex snapshot ID from the evidence, including after Git pruning.

Keep `<stem>.md`, `<stem>-prompt.md`, `<stem>-id.txt` and `<stem>-snapshot.txt` in the review directory. Use a distinct stem of 1–100 ASCII letters, digits, hyphens or underscores. Give the report's verified positive ordinal for this merged finding, or `unknown` when importing evidence of uncertain order. Record only an outcome the report or preserved evidence establishes. An identical retry succeeds once. History shows the first confirmation, the ordered and unordered rechecks, and whether the exact report survives in the unit's one-time archive.
