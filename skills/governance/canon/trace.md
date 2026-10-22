# Tracing

Only the orchestrating session calls `trace`, never a worker or reviewer. On `trace error`, correct the input and retry once, then carry on either way. `trace status` recovers a lost id.

End every unit you start but a slice: delivered when it produced its output, blocked on what only the user can settle, handoff when another session continues it, cancelled when the user stopped it. Implement also allows partial, leaving paused slices, and escalated `--to` what it needs: L1 when an L0 change ends awaiting a spec change, L2 for a new or rewritten design, plan when L1 work needs one. An end check ends only quiet, or raised if it put items to the user.

A gate's or code review's `end`, at a handoff too, takes its `--dir` and, with `--input -`, reads its dispositions from stdin:

```json
{"reviewers":[{"role":"same-model","model":"claude-opus-5.5","id":"a3f0c2e1"}],
 "findings":[{"by":["same-model:F1"],"severity":"major","disposition":"accepted","confirmed":"resolved"}],
 "new_blockers":0}
```

- Roles: same-model and cross-family in a gate; spec, standards and cross-family in a code review, whose findings add `axis`, spec or standards.
- `model` as in `reviewers`, `id` from `<role>-id.txt`; a user-run review has `manual:<model>` and a null `id`.
- A finding merges reviewer findings: `by` lists them all, `severity` is the highest.
- `disposition`: accepted (fixed), declined, escalated (awaiting the user, or undecided at a handoff), or deferred (by the user, tracked for later).
- `confirmed`: resolved or not-resolved, only on findings sent to confirmation. `new_blockers`: new blockers it reported, else 0.
