---
status: open
created: 2026-11-24
updated: 2026-11-24
revision: 1
modules: [canon]
summary: Silk reported repeated review work, scope expansion in design and scaffold reviews, and a CI gap for required commit trailers.
refs: [D002, D007, R005]
---

# R006: Silk feedback on review scope and commit checks

## Scope

This review covers the usability of Canon's review instructions and the CI behavior of `canon.py check --base`. Findings F1–F4 follow records 23–26 in Silk's `.canon/canon-retro/skills.jsonl`. One Cursor session recorded them on November 24, 2026, the first two on Canon 79 (v0.9.1) and the last two on Canon 80 (v0.9.2). Silk's `.canon/canon-retro/notes.md` records the local decisions. The comparison uses Silk at `c444098` and Canon v0.9.3 at `19d59da`. [R005: previous Silk upgrade review](../archived/reviews/R005-silk-upgrade-090.md)

## Findings

| ID | Severity | Finding | Disposition |
|----|----------|---------|-------------|
| R006-F1 | major | A follow-up that combines previously reviewed and newly added targets can send reviewers the original cumulative diff. | open |
| R006-F2 | major | The Spec reviewer can treat future requirements in an accepted design as missing deliverables of an L0 scaffold. | open |
| R006-F3 | minor | A commit can change code governed by a design, omit the required `Refs:` trailer and still pass the CI check. | open |
| R006-F4 | major | When merging findings, the author can expand the task without asking the maintainer, especially when reviewers agree. | open |

### R006-F1 Follow-up diff for each target

In Silk's gate `20261124T071149Z-f048db`, both prompts in `.canon/canon-blind-review/D000-r20/followup-1/` used the original base `1ad3fb5`. Silk estimates that reviewers reread about 250 lines of `D003` and `D005` and records two maintainer interruptions. Silk asks the prompt to apply Canon's two existing rules together. Returning reviewers get the diff since their last review snapshot for targets they covered. For an added target, each role that has yet to review it gets a full pass. [D007§follow-up-round: follow-up round](../designs/D007-change-tiers.md#follow-up-round) · [D007§target-coverage: target coverage](../designs/D007-change-tiers.md#target-coverage)

### R006-F2 Spec review of an L0 scaffold

Silk's `1a5d3e7` added a build and module scaffold. The five governing designs, `D001` through `D005`, were `accepted` and had no `implemented` revision. In review `20261124T094113Z-def54b`, F12 in `.canon/canon-blind-review/scaffold-l0/spec.md` rated their missing runtime behavior `major` and called for a reviewed plan or the implementation. Silk asks the Spec brief for an L0 scaffold without a plan to check the module boundaries, interfaces, wire formats, ABI and behavior the patch actually introduces. [Spec reviewer brief](../../skills/execution/canon-code-review/SKILL.md#4-spawn-the-reviewers)

### R006-F3 Missing design references in CI

Silk's `1a5d3e7` changed `src/` and `bindings/python/` without naming their governing designs. The `canon.py check --base` CI job passed. `canon.py audit` flagged all five designs and exited successfully. The maintainer declined a Silk-specific hook and requested a Canon check that fails when a non-merge commit in `<base>..HEAD` omits a governing design from its `Refs:` trailer. [D002§unchecked-commits-in-audit: unchecked commits in audit](../designs/D002-overview-and-as-built.md#unchecked-commits-in-audit)

### R006-F4 Scope decisions when merging findings

Silk's `D000` gate expanded to `D003`, `D004`, `D005` and their attachments during fixes (`c61e986`). The scaffold review led to about 1,051 lines of speculative implementation and two cleanup passes, according to Silk's retro. The second pass (`892377f`) removed 15 domain files.

Silk added a temporary `AGENTS.md` rule in `04f24c1` and asks Canon to apply it when merging design and code review findings. Expanding the task requires the maintainer's approval even when two reviewers agree. A request for future code or documentation outside the task is declined with a reason. An unrelated defect in existing work goes in the governing design's Known issues. [D007§merging-findings: merging findings](../designs/D007-change-tiers.md#merging-findings)
