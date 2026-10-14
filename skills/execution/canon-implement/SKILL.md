---
name: canon-implement
description: Implements an accepted plan with a fresh worker per slice, or an L1 design revision or L0 change, then reviews it and runs the docs step.
disable-model-invocation: true
---

# Implement

Read the `canon` skill first; its workflow governs tiers, deviations, code review and the docs step. `canon.py` means the project copy named in `AGENTS.md`.

## 1. Start

1. Identify the work: the plan or design the user named (`canon.py find <words>` when only a topic is given), or an L0 change. State the tier. Work without a plan is one slice built in this session.
2. Check the work against the tier's flow in the `canon` skill's workflow:
   - A plan must be `accepted` or `in-progress`. An L2 plan still `draft` after its gate awaits the user's approval, and invoking this skill on it gives that approval: say so in one line and set it `accepted`.
   - An L1 design revision that passed the gate and needs no plan: follow L1 without a plan below.
   - When an earlier phase is missing, stop and give the user its command, e.g. `/canon-design D00X` or `/canon-plan D00X`.
3. Read the plan's Current state, then the governing design sections (`show D00X#<section>`). If `check` warns that a design moved past the plan's `based_on`, compare the design's changes with the remaining slices first; a conflict is a plan or design problem under the workflow's deviation rules.
4. When the plan is `accepted`: set it `in-progress` and append `Started at <commit>` to its Log. That commit is the code-review fixed point. A resumed plan already has it.

## 2. Each slice

This session orchestrates, and a fresh worker builds each slice, so every slice starts in an empty context window. Run one worker at a time, in plan order. Only this session edits the plan, commits and asks the user.

1. Set the slice's `Status: in-progress`.
2. Launch a worker with the worker prompt below and wait for its report.
3. Act on the report:
   - **done**: re-run the slice's tests and check the diff: it stays within the slice and edits no plan or design.
   - **stuck** on a failure it could not explain: pause the slice without retrying; the user decides the next step.
   - **blocked** on a question: settle it with the `canon-grill` skill's triage and resume the worker with the answer. A question only the user can answer is a pending decision: pause the slice.
   - **blocked** on the plan or design: apply the workflow's deviation rules. For a plan problem with one clear fix, edit the plan, log it and resume the worker. Otherwise pause the slice.

   To pause a slice, set `Status: paused`, stash its changes under a message naming the slice, log the problem and the stash for whoever resumes it, and continue with slices that do not depend on it.
4. When the slice is done by the `canon-tdd` skill's definition, set `Status: done`, point Current state at the next action, and append results, decisions and deviations to the Log.
5. Run `canon.py check --fix`, then commit the slice: code plus plan, Conventional Commits, `Refs: <design>, <plan>` trailer.

### Worker prompt

Fill the placeholders and pass nothing else; the plan carries the context.

```text
You are implementing one slice of a plan in this repository, with no prior context.

Plan: {plan path}, slice {S<n>: name}. Read the plan's Current state and Log, the slice, and the design sections it builds on: {D00X#section, ...}.

Build the slice test-first with the `canon-tdd` skill, at the seams its test criteria name, until those criteria pass and nothing green turned red. Settle unclear points with the `canon-grill` skill's triage. Do not edit the plan or any design, and do not commit.

You cannot reach the user. Stop and report instead when:
- the plan or a design cannot be followed: say which, and the fix you would propose;
- a decision is needed that the docs and code do not settle;
- a test failure stays unexplained after two attempts.

Report in under 300 words: status (done | stuck | blocked), files changed, tests added with their seams, the test commands you ran and their results, deviations from the plan, open questions.
```

### Workers

A worker is a new general-purpose subagent from the host's own tool, never a fork of this session, launched without a model or effort so it runs on the session's (the `canon` skill's workflow, Subagents). Keep its id so you can resume it.

## 3. Finish

1. Review the whole change with the `canon-code-review` skill from the `Started at` commit. Fix the findings, commit, and record deferred ones as it describes.
2. Run the docs step from the `canon` skill's workflow with `--base <Started at>`, so it covers the committed slices. It sets the design's `implemented`, archives the plan as `done` once every slice is done, then commits.
3. Report: slices done, every paused slice with its problem, the R doc holding deferred findings, and the due-review line when the docs step produced one.

## L1 without a plan

The design revision that passed the gate is the work. Build its spec change with `canon-tdd` as one slice, review it from the commit you started at (or the uncommitted diff), run the docs step, which sets `implemented`, and commit. When the work turns out to need several steps, stop and give the user `/canon-plan D00X`.

## L0 change

No plan: build the change with `canon-tdd` as one slice, without plan updates. Then review it from the commit you started at (or the uncommitted diff), run the docs step and commit. When the change turns out to alter a spec, stop and tell the user it is L1, to be revised with `/canon-design D00X`.
