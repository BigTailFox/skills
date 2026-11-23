# Tracing

Only the orchestrating session calls `trace`. On `trace error`, correct the input and retry once, then continue. `trace status` lists recent open IDs. [`trace history [UNIT]`](SKILL.md#tool) works with tracing off.

End each unit except a slice. Use delivered for completed output, blocked on what only the user can settle, handoff when another session continues, cancelled when the user stopped it. Implement also allows partial for paused slices and escalated `--to` L1 when L0 work ends awaiting a spec change, L2 for a new or rewritten design, or plan when L1 work needs one. An end check ends quiet, or raised if it put items to the user.

A gate, follow-up or code review ends with its `--dir` and JSON dispositions on stdin through `--input -`. Record the report keys, the target revisions each gate or follow-up report assessed, the merged findings and their first confirmations. At handoff, mark every undecided finding `escalated`. Use the [review evidence fields and example](review-evidence.md).

For a separately requested recheck, use the saved review unit ID. If it is still open, keep the recheck evidence and append it immediately after the end. For a closed review, append it on receipt. Each call observes the current trace switch.
