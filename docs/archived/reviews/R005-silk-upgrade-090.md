---
status: closed
created: 2026-11-24
updated: 2026-11-24
revision: 1
modules: [canon]
summary: Silk's 0.9.0 upgrade identified two remaining project rules, missing patch retirement guidance and a need to find documents by embedded source.
refs: [D006, D011, R004]
---

# R005: Silk upgrade to Canon 0.9.0

## Scope

Silk commit `17db9ab` upgraded all 19 Canon skills from v0.8.2 to v0.9.0 (tool versions 67 and 78). The upgrade report found 12 compatible embed blocks in five designs. Silk removed its generator and its local worktree and L2 handoff instructions. Its upgrade check covered stale work-tree and staged blocks. The earlier feedback and its fixes are recorded in [R004: Canon feedback from Silk](R004-silk-canon-field-feedback.md).

## Findings

| ID | Severity | Finding | Disposition |
|----|----------|---------|-------------|
| R005-F1 | major | Review prompts check experimental evidence, but conclusions and public summaries can broaden it. Silk's E022 measured a single CUDA context. A process-wide claim would need evidence across contexts. | fixed 26b8a9c |
| R005-F2 | major | A targeted `check --fix` can write a document another session has edited since the last status check. | fixed 26b8a9c |
| R005-F3 | minor | The 0.9.0 upgrade notes give no guidance on which downstream workarounds can be retired and what responsibilities remain local. | fixed 26b8a9c |
| R005-F4 | minor | After editing a Python attachment owned by Silk's D001, an author has to know that D004 embeds it to refresh just its consumers. | fixed 26b8a9c |

[D006§writing-rules: writing rules](../../designs/D006-doc-model.md#writing-rules) and [D006§concurrent-work: concurrent work](../../designs/D006-doc-model.md#concurrent-work) own the two portable rules. [D011§generating-and-checking: generating and checking](../../designs/D011-embedded-source.md#generating-and-checking) owns source selection. The [release notes](../../../CHANGELOG.md#upgrading-from-082) cover migration.

## Verification

All 19 installed skill trees at Silk's upgrade commit and its parent matched the corresponding upstream v0.9.0 and v0.8.2 trees by Git object ID. The migration table first appeared in `45a0d09`. Its retirement procedure includes a stale-block check against a known consumer.

In an isolated copy of Silk's documents at `17db9ab`, Canon 79 listed only `docs/designs/D004-connection-establishment.md` for `docs/designs/D001/silk-python-api-sketch.py`. Editing its `connection-api` region made the source-scoped check report a stale block at line 165. Refreshing changed only that consumer, left the Git index intact and produced no changes on a second run. A separate source used in three regions of Silk's D002 produced one listing for that design.
