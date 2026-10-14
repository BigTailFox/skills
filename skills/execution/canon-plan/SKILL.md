---
name: canon-plan
description: Writes or revises a canon plan for an accepted design. It drafts vertical slices ordered by dependency, each with test criteria at named seams, settles the open points with the user, then passes the review gate and gets approval. Use when the user wants to plan the implementation of a design, break a change into slices, or revise a plan.
disable-model-invocation: true
---

# Plan

Read the `canon` skill first. `canon.py` means the project copy named in `AGENTS.md`.

## 1. Start

1. The design must be `accepted` or `active` with `reviewed` equal to `revision`. Otherwise stop and tell the user (the `canon-design` skill writes it).
2. New plan: `canon.py new P <slug> --from D00X`. Revising a plan: edit it in place and bump `revision`.
3. Read the whole design, the code its `paths` govern, the existing tests and the commands that run them.

## 2. Draft

Draft the whole plan yourself before asking anything:

- **Vertical slices.** Each slice delivers one observable behavior end to end, a tracer bullet, so it can be verified on its own. Never one slice for all the tests and another for all the code.
- **Order by dependency**, riskiest first among independent slices. When a slice depends on an unanswered design question, its first step is an experiment (`canon-prototype`) whose conclusion feeds the design.
- **Each slice**: `### S<n>: <name>`, a `Status: todo` line, the changes (modules, files, migrations), and test criteria. Each criterion names its seam, the interface from the design's Spec where the test observes behavior (`canon-codebase-design` vocabulary), and the expected behavior.
- **Notes**: risks, constraints, migration and rollout concerns the implementer must keep in mind.
- **Current state**: `Next: S1`.

Then settle what the draft leaves open with the `canon-grill` skill: slice boundaries, order, seams and risk. Write each answer into the plan at once.

## 3. Gate

1. Run `canon.py check` until it is clean.
2. Pass the review gate from the `canon` skill's workflow.
3. L1: set the plan `accepted`. L2: report the findings and reviewers, and set `accepted` only after the user approves.
4. Commit the plan (Conventional Commits, `docs` type, `Refs:` trailer).

Tell the user the plan is ready for the `canon-implement` skill.
