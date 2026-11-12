---
name: canon-plan
description: Writes or revises the plan for an accepted design as vertical slices with test criteria, then passes the review gate.
disable-model-invocation: true
---

# Plan

Read the `canon` skill first. `canon.py` means the `canon` skill's `scripts/canon.py`, as its Tool section says.

## 1. Start

1. The design must have passed the review gate (`reviewed` equals `revision`); otherwise stop and give the user `/canon-design D00X` to finish it. Invoking this skill on a design approves it: before `new P --from`, set its `approved` to its revision where it is lower and a draft `accepted` with `canon.py status`, say so in one line naming the gate's reviewers, and commit them. A new plan also approves each other design you add to its `based_on`: set it likewise, committed with the plan.
2. New plan: `canon.py new P <slug> --from D00X`. Revising a plan: edit it in place and bump `revision`.
3. Run `canon.py trace start plan <P id> <D id> --tier <tier> --skill <skill> --model <model>`.
4. Read the whole design, the code its `paths` govern, the existing tests and the commands that run them.

## 2. Draft

Draft the whole plan yourself before asking anything:

- **Vertical slices.** Each slice delivers one observable behavior end to end, a tracer bullet, so it can be verified on its own. Never one slice for all the tests and another for all the code.
- **Order by dependency**, riskiest first among independent slices. When a slice depends on an unanswered design question, its first step is an experiment (`canon-prototype`) whose conclusion feeds the design.
- **Each slice**: `### S<n>: <name>`, a `Status: todo` line, a `Risk:` line when the slice involves complex logic, concurrency, performance, security or data migration, the changes (modules, files, migrations), and test criteria. Each criterion names its seam, the interface from the design's Spec where the test observes behavior (`canon-codebase-design` vocabulary), and the expected behavior.
- **Notes**: risks, constraints, migration and rollout concerns the implementer must keep in mind, and the details the plan settles that the design leaves unstated, for the docs step to write into the design.
- **Current state**: `Next: S1`.

Then settle what the draft leaves open with the `canon-grill` skill: slice boundaries, order, seams and risk.

A slice that would alter or extend behavior no design states, as the `canon` skill's tiers define it, first gets that behavior recorded: write an as-built revision from HEAD (the `canon` skill's `as-built.md`), pass it through the review gate at L1 and commit it on its own; the slices it touches then wait as for a design problem.

When drafting or the gate finds a design problem, as when a slice would have to change what the design states or depends on a known issue no slice fixes, follow the `canon` skill's workflow (Design problems); the slices it touches wait for the user's decision and any revision it brings.

## 3. Gate

1. Run `canon.py check` and fix its errors.
2. Pass the review gate's steps 1 to 5 from the `canon` skill's workflow.
3. Set the status as the gate's step 6 says.
4. Commit the plan as the gate's step 7 says (Conventional Commits, `docs` type, `Refs:` trailer). In L2, ask the user to approve the plan, naming `/canon-implement P00X`. On a yes, set the plan's `approved` to its revision and a draft `accepted` with `canon.py status`, and commit them.
5. Run the `canon-retro` skill's end check only if this work hit concrete friction in the development infrastructure or the agent workflow that could recur, such as a correction to how you worked, a finding a check could have caught, a command that would not run, a check that failed after you thought you were done, a search that took far too long, or a canon step that got in the way. Use only evidence already in context; do not search for reasons to run it.
6. Run `canon.py trace end <id> <outcome>`.

A revision this session makes after step 4's commit runs steps 1 to 4 again, step 2 passing a follow-up round through the gate's step 5, so an L2 revision asks for approval again; the `canon` skill's workflow (Follow-up round) names the revisions that pass a new gate instead.

End with the command for the next phase, `/canon-implement P00X`. When slices carry a `Risk:` line, name them beside the command and suggest high reasoning effort for the implementation session, since every worker runs at the session's effort.
