# Tracing

Only the orchestrating session calls `trace`. On `trace error`, correct the input and retry once, then continue. `trace status` lists recent open IDs. [`trace history [UNIT]`](SKILL.md#tool) works with tracing off.

End each unit except a slice. Use delivered for completed output, blocked on what only the user can settle, handoff when another session continues, cancelled when the user stopped it. Implement also allows partial for paused slices and escalated `--to` L1 when L0 work ends awaiting a spec change, L2 for a new or rewritten design, or plan when L1 work needs one. An end check ends quiet, or raised if it put items to the user.

A gate's, follow-up round's or code review's `end`, at a handoff too, takes its `--dir` and, with `--input -`, reads its dispositions from stdin:

```json
{"reviewers":[{"role":"same-model","model":"claude-opus-5.5","id":"a3f0c2e1"}],
 "findings":[{"by":["same-model:F1"],"severity":"major","disposition":"accepted","confirmed":"resolved"}],
 "new_blockers":0}
```

- Roles: spec, standards and cross-family in a code review, whose findings add `axis`, spec or standards; else same-model and cross-family.
- `model` as in `reviewers`; `id` from `<role>-id.txt`, null if empty or missing; a user-run review has `manual:<model>`.
- A finding merges reviewer findings: `by` lists them all, `severity` is the highest.
- `disposition`: accepted (fixed), declined, escalated (awaiting the user, or undecided at a handoff), or deferred (by the user, tracked for later).
- `confirmed`: resolved or not-resolved, only on findings sent to confirmation. `new_blockers`: new blockers it reported, else 0.
