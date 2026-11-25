# Review scope acceptance cases

These constructed cases exercise the review skills delivered in `41c3029`. A fresh reader saw the inputs and skill instructions without the expected outcomes. The cases test specific decisions and do not establish how often a model will follow the instructions.

## L0 scaffold

The requested delivery is a public-header scaffold with a compile/link probe and no plan. An accepted, unimplemented design requires `uint64_t payload_length` in the ABI and describes a future reconnect scheduler. The patch declares `uint16_t payload_length`. Two reviewers ask for the scheduler. A decoder defect in another design predates the change.

The reader reported the width mismatch as major, requested confirmation of its fix, declined the scheduler requests, and routed the existing decoder defect to its owning design with a duplicate check. It would seek a maintainer decision to expand the task. A C11 compile/link probe succeeded with the wrong width. A compile-time type assertion failed on that declaration and passed after substituting `uint64_t`.

## Mixed-target follow-up

In an L2 round, the same-model reviewer covered A at S1 and B at S2. A later confirmation C checked one of two intervening changes to A. The cross-family reviewer covered A at X1 and has never reviewed B. B is a new design within the agreed scope. O is the original branch base, and N is the follow-up snapshot.

| Reader | Input the reader selected | Coverage |
|---|---|---|
| Returning same-model | `git diff S1 N -- A.md` and `git diff S2 N -- B.md` in the review snapshot store | Incremental review of both paths, with the already-confirmed A claim identified |
| Returning cross-family | `git diff X1 N -- A.md` in the snapshot store | Incremental review of A |
| Fresh cross-family | Full B at N with the original design criteria | First full review of B by the missing role |

The reader kept N as the round target, saved each command in its prompt and omitted the shared baseline. In a temporary Git fixture, S1..N included the second A change, C..N hid it, and O..N reintroduced a change already seen at S1. The B and cross-family A diffs each selected only their named path.
