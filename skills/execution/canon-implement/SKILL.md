---
name: canon-implement
description: Implements a change the canon way. Works through an accepted plan slice by slice (or directly an L0 change or an L1 design revision without a plan), test-first at the plan's seams, and commits each slice. It then reviews the whole change, runs the docs step that archives the finished plan, and reports paused slices and deferred findings. Use when the user asks to implement, build, execute, continue or resume a plan, design or change.
disable-model-invocation: true
---

# Implement

Read the `canon` skill first; its workflow governs tiers, deviations, code review and the docs step. `canon.py` means the project copy named in `AGENTS.md`.

## 1. Start

1. Identify the work: the plan or design the user named (`canon.py find <words>` when only a topic is given), or an L0 change. State the tier.
2. Check the work against the tier's flow in the `canon` skill's workflow:
   - A plan must be `accepted` or `in-progress`. An L2 plan still `draft` after its gate awaits the user's approval, and invoking this skill on it gives that approval: say so in one line and set it `accepted`.
   - An L1 design revision that passed the gate and needs no plan: follow L1 without a plan below.
   - When an earlier phase is missing, stop and give the user its command, e.g. `/canon-design D00X` or `/canon-plan D00X`.
3. Read the plan's Current state, then the governing design sections (`show D00X#<section>`). If `check` warns that a design moved past the plan's `based_on`, compare the design's changes with the remaining slices first; a conflict is a plan or design problem under the workflow's deviation rules.
4. When the plan is `accepted`: set it `in-progress` and append `Started at <commit>` to its Log. That commit is the code-review fixed point. A resumed plan already has it.

## 2. Each slice

1. Set the slice's `Status: in-progress`.
2. Build it with the `canon-tdd` skill at the seams its test criteria name. Run the type checker and the touched test files often.
3. When something is unclear, use the `canon-grill` skill's triage. A logic or design question that evidence can settle goes to `canon-prototype`. A defect goes to `canon-investigate`.
4. When the code cannot follow the plan or the design, apply the workflow's deviation rules: fix a plan problem with one clear answer and log it. Pause the slice for a design problem or a pending decision, and continue with slices that do not depend on it.
5. The slice is done when every test criterion passes and the full suite is green. Set `Status: done`, point Current state at the next action, and append results, decisions and deviations to the Log.
6. Run `canon.py check --fix`, then commit the slice: code plus plan, Conventional Commits, `Refs: <design>, <plan>` trailer.

## 3. Finish

1. Review the whole change with the `canon-code-review` skill from the `Started at` commit. Fix the findings, commit, and record deferred ones as it describes.
2. Run the docs step from the `canon` skill's workflow with `--base <Started at>`, so it covers the committed slices. It sets the design's `implemented`, archives the plan as `done` once every slice is done, then commits.
3. Report: slices done, every paused slice with its problem, the R doc holding deferred findings, and the due-review line when the docs step produced one.

## L1 without a plan

The design revision that passed the gate is the work. Build its spec change with `canon-tdd` as one slice, review it from the commit you started at (or the uncommitted diff), run the docs step, which sets `implemented`, and commit. When the work turns out to need several steps, stop and give the user `/canon-plan D00X`.

## L0 change

No plan: build the change with `canon-tdd` as one slice, without plan updates. Then review it from the commit you started at (or the uncommitted diff), run the docs step and commit. When the change turns out to alter a spec, stop and tell the user it is L1, to be revised with `/canon-design D00X`.
