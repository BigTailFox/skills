---
name: canon-plan
description: Writes or revises the plan for an accepted design as vertical slices with test criteria, then passes the review gate.
disable-model-invocation: true
---

# Plan

Read the `canon` skill first. `canon.py` means the project copy named in `AGENTS.md`.

## 1. Start

1. The design must have passed the review gate (`reviewed` equals `revision`) and be `accepted` or `active`. An L2 design still `draft` after its gate awaits the user's approval, and invoking this skill on it gives that approval: say so in one line, naming the gate's reviewers, and set it `accepted`. Otherwise stop and give the user `/canon-design D00X` to finish it.
2. New plan: `canon.py new P <slug> --from D00X`. Revising a plan: edit it in place and bump `revision`.
3. Read the whole design, the code its `paths` govern, the existing tests and the commands that run them.

## 2. Draft

Draft the whole plan yourself before asking anything:

- **Vertical slices.** Each slice delivers one observable behavior end to end, a tracer bullet, so it can be verified on its own. Never one slice for all the tests and another for all the code.
- **Order by dependency**, riskiest first among independent slices. When a slice depends on an unanswered design question, its first step is an experiment (`canon-prototype`) whose conclusion feeds the design.
- **Each slice**: `### S<n>: <name>`, a `Status: todo` line, a `Risk:` line when the slice involves complex logic, concurrency, performance, security or data migration (it is implemented at high reasoning effort), the changes (modules, files, migrations), and test criteria. Each criterion names its seam, the interface from the design's Spec where the test observes behavior (`canon-codebase-design` vocabulary), and the expected behavior.
- **Notes**: risks, constraints, migration and rollout concerns the implementer must keep in mind.
- **Current state**: `Next: S1`.

Then settle what the draft leaves open with the `canon-grill` skill: slice boundaries, order, seams and risk. Write each answer into the plan at once.

## 3. Gate

1. Run `canon.py check` and fix its errors.
2. Pass the review gate from the `canon` skill's workflow.
3. Set the status as the gate's last step describes.
4. Commit the plan (Conventional Commits, `docs` type, `Refs:` trailer).

End with the command for the next phase, `/canon-implement P00X`. In L2, the user starting it approves the plan.
