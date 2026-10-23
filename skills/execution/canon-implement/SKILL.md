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
   - A plan must be `accepted` or `in-progress`, with `reviewed` equal to `revision`. An L2 plan still `draft` after its gate awaits the user's approval, and invoking this skill on it gives that approval: say so in one line and set it `accepted`.
   - An L1 design revision that passed the gate and needs no plan: finish Start, then follow L1 without a plan below.
   - A change without a plan or revision that alters or extends behavior no design states, as the `canon` skill's tiers define it, lacks its design phase, as a change to a stated spec does: `/canon-design` records that behavior first. [Backfill](#backfill) is for work that only turns out to alter such behavior.
   - When an earlier phase is missing, stop and give the user its command, e.g. `/canon-design D00X` or `/canon-plan D00X`.
3. Read the plan's Current state, then the governing design sections (`show D00X#<section>`). If `check` warns that a design moved past the plan's `based_on`, compare the design's changes with the remaining slices first; a conflict is a plan or design problem under the workflow's deviation rules.
4. When the plan is `accepted`: set it `in-progress` and append `Started at <commit>` to its Log. That commit is the code-review fixed point. A resumed plan already has it.
5. Run `canon.py trace start implement [<P or D id>] --tier <tier> --base <start commit> --skill <skill> --model <model>`.

## 2. Each slice

This session orchestrates, and a fresh worker builds each slice, so every slice starts in an empty context window. Run one worker at a time, in plan order. Only this session edits the plan, commits and asks the user.

1. Set the slice's `Status: in-progress`.
2. Unless the last `trace start` under the implement unit was this slice's, run `canon.py trace start slice <P id> --slice S<n> --parent <id>`. Then launch a worker with the worker prompt below and wait for its report.
3. Act on the report:
   - **done**: re-run the slice's tests and check the diff: it stays within the slice and edits no plan or design.
   - **stuck** on a failure it could not explain: pause the slice without retrying; the user decides the next step.
   - **blocked** on a question: settle it with the `canon-grill` skill's triage and resume the worker with the answer. A question only the user can answer is a pending decision: pause the slice.
   - **blocked** on the plan or design: apply the workflow's deviation rules. For a plan problem with one clear fix, edit the plan, log it and resume the worker. Otherwise pause the slice. A slice that alters or extends behavior no design states takes [Backfill](#backfill).
   - **No report**, because the host stopped the run: give it one more run, as the workflow's Subagents says, replacing it as [Workers](#workers) says when it cannot be resumed. When that run stops too, pause the slice with the stopped runs as its problem.

   To pause a slice, set `Status: paused`, stash the worker's changes, new files included but not the plan, under a message naming the slice, log the problem and the stash for whoever resumes it, and continue with slices that do not depend on it.
4. When the slice is done by the `canon-tdd` skill's definition, set `Status: done`, point Current state at the next action, and append results, decisions and deviations to the Log.
5. Run `canon.py check --fix`, then commit the slice: code plus plan, Conventional Commits, `Refs: <design>, <plan>` trailer.

### Worker prompt

Fill the placeholders and pass nothing else, except the answer a replacement worker gets ([Workers](#workers)); the plan carries the context.

```text
You are implementing one slice of a plan in this repository, with no prior context.

Plan: {plan path}, slice {S<n>: name}. Read the plan's Current state and Log, the slice, and the design sections it builds on: {D00X#section, ...}.

Build the slice test-first with the `canon-tdd` skill, at the seams its test criteria name, until those criteria pass and nothing green turned red. Settle unclear points with the `canon-grill` skill's triage. Do not edit the plan or any design, and do not commit.

You cannot reach the user. Stop and report instead when:
- the plan or a design cannot be followed: say which, and the fix you would propose;
- a decision is needed that the docs and code do not settle;
- a failing test stays unexplained and your last two attempts produced no new evidence narrowing its cause.

Your final message is your report: status (done | stuck | blocked), files changed, tests added with their seams, the test commands you ran and their results, deviations from the plan, open questions.
```

### Workers

A worker is a new general-purpose subagent from the host's own tool, never a fork of this session, launched without a model or effort so it runs on the session's (the `canon` skill's workflow, Subagents). Write its id to `.canon/canon-implement/<P id>/S<n>-id.txt` so you can resume it. A worker that cannot be resumed is replaced: stash its changes as a pause does, under a message naming the slice and the replacement, log the stash, and launch a new worker with the worker prompt, followed by the answer when it was blocked on a question.

## 3. Finish

1. Review the whole change with the `canon-code-review` skill from the `Started at` commit. Fix the findings, commit, and record deferred ones as it describes.
2. Run the docs step from the `canon` skill's workflow with `--base <Started at>`, so it covers the committed slices. It sets the design's `implemented`, archives the plan as `done` once every slice is done, then commits.
3. Run the `canon-retro` skill's end check only if this work hit concrete friction in the development infrastructure or the agent workflow that could recur, such as a correction to how you worked, a finding a check could have caught, a command that would not run, a check that failed after you thought you were done, a search that took far too long, or a canon step that got in the way. Use only evidence already in context; do not search for reasons to run it.
4. Run `canon.py trace end <id> <outcome>`.
5. Report: slices done, every paused slice with its problem, the known issues recorded for deferred findings, and the due-review line when the docs step produced one.

## L1 without a plan

The design revision that passed the gate is the work. Build its spec change with `canon-tdd` as one slice, review it from the commit you started at (or the uncommitted diff), run the docs step, which sets `implemented`, commit, and take the retro and trace steps in [Finish](#3-finish). When the work turns out to need several steps, run `canon.py trace end <id> escalated --to plan`, then stop and give the user `/canon-plan D00X`.

## L0 change

No plan: build the change with `canon-tdd` as one slice, without plan updates. Then review it from the commit you started at (or the uncommitted diff), run the docs step, commit, and take the retro and trace steps in [Finish](#3-finish). When the change turns out to alter or extend behavior no design states, take [Backfill](#backfill) first. When the change turns out to alter a spec, follow the `canon` skill's workflow (Design problems); once the design revision passes its gate, finish the change as [L1 without a plan](#l1-without-a-plan), from the step it had reached. If you stop before then, run `canon.py trace end <id> escalated --to L1`, or `--to L2` when the fix is L2 work. When the change needs a new design, run `canon.py trace end <id> escalated --to L2`, then stop and give the user `/canon-design`.

## Backfill

A change or slice that alters or extends existing behavior no design states, whether a worker's report or the work itself shows it, first gets that behavior recorded by this session:

1. Pause a slice as for a design problem, which stashes its worker's changes.
2. Write an as-built revision, as the `canon` skill's `as-built.md` says, from the commit the work started at: the plan's `Started at` for a slice. Pass it through the review gate at L1 and commit it on its own.
3. The work now alters a spec. A change continues as [L0 change](#l0-change) says for one that alters a spec; a slice stays paused, as for a design problem, until the user has decided on the revision and it has passed its gate.
