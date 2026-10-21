---
name: canon-review
description: Reviews a module or the whole codebase from chosen angles and takes every finding through the user's decision.
disable-model-invocation: true
---

# Codebase review

Read the `canon` skill first. `canon.py` means the project copy named in `AGENTS.md`. This reviews the code as it stands; reviewing one change is the `canon-code-review` skill's job.

## 1. Scope

Use the modules and angles the user names. Otherwise propose a scope and wait for the user to confirm it:

- `canon.py audit`: stale designs and due reviews per docs root.
- Hot spots: the files changed most since the last review, from `git log --since=<last R created> --name-only` within the module's paths.
- Design coverage: designs `check` reports as over 500 lines, and source files where `which` prints `no design`.
- Angles: **architecture** after many changes; **performance** when designs have Budgets or slowness was reported; **functional** when audit reports designs with unchecked code commits; **usability** for user-visible surfaces (CLI, API, UI, config); **security** only when the project or feature is security-related or the user asks.

## 2. Create the doc

Run `canon.py new R <slug>`. Scope records the commit (`git rev-parse HEAD`), the modules and paths, and the angles. Attachments go in `reviews/R00X/`. Then run `canon.py trace start canon-review <R id> --skill <skill> --model <model>`.

## 3. Review each angle

Spawn one subagent per angle, in parallel, in the foreground. Each brief carries:

- The scope: commit, module paths, and the governing designs (`which`, `show`), the architecture design and the relevant `AGENTS.md` files to read.
- The angle's reference pasted in full: [architecture.md](architecture.md), [performance.md](performance.md), [security.md](security.md), [functional.md](functional.md), [usability.md](usability.md).
- The rules: modify no file. Skip anything a design's Decision line already rejected unless the friction is severe enough to reopen it, and then name the Decision. Replace secrets with `<REDACTED>`.
- The output: every blocker and major finding and at most 10 minor ones, most severe first. Each has a title, location (files, design sections), problem, evidence, suggestion, and severity `blocker`, `major` or `minor`. Keep each finding as short as it can be while a reader can understand and verify it without redoing the review.

## 4. Report

1. Fill Findings: one row per finding, ids `R00X-F1`, `R00X-F2`, ..., the angle as a prefix (`architecture: Order intake is shallow`), disposition `open`.
2. Present the findings grouped by angle, with each angle's top recommendation. Keep each angle's own ranking: each angle answers a different question.
3. When the user wants a visual report (offer it in one line when architecture candidates would read better as diagrams), write `reviews/R00X/report.html` following [html-report.md](html-report.md), link it from Scope, and open it for the user (`xdg-open`, `open` or `start`).

## 5. Decide with the user

Sort the findings first. **Fixable now** means an L0 fix, or an L1 change inside one design, small enough for this session; write a short plan for each: the change, the files, the tier, and for L1 the spec change. L2 work and broad architecture changes are recorded for later.

Take the findings to the user in rounds with the `canon-grill` skill. Present the fixable ones with their plans and ask which to fix now; every other finding, and each fixable one the user does not take, gets one of the other dispositions:

- **Fix now** (an approved plan): build it through its tier's flow, L0 with `canon-tdd` and `canon-code-review`, L1 by revising the design and passing the review gate (same-model reviewer) first. Run the docs step, commit each fix on its own, and set `fixed <commit>`.
- **Needs a spec change**: set `moved D00X` to the design that will carry it, or `moved P00X` when a plan covers it, and give the user the next phase's command (`/canon-design D00X` or `/canon-plan D00X`).
- **A defect**: create an investigation (`canon.py new I <slug>`) and set `moved I00X`.
- **Later**: add it as an Idea to the module's backlog concept (`canon.py find backlog`, else `canon.py new C <module>-backlog`) and set `moved C00X`.
- **Rejected**: set `declined <reason>`. When the reason is lasting and the idea likely to return, add a one-line Decision to the owning design so later reviews skip it.

Before deciding on an architecture candidate, the user may explore it: walk it with `canon-grill` and design alternative interfaces with the `canon-codebase-design` skill.

## 6. Close

Once no finding is `open`, run `canon.py archive R00X closed` and `canon.py check --fix`, then commit (Conventional Commits, `docs` type, `Refs: R00X`).

Then run the `canon-retro` skill's end check only if this work hit concrete friction in the development infrastructure or the agent workflow that could recur, such as a correction to how you worked, a finding a check could have caught, a command that would not run, a check that failed after you thought you were done, a search that took far too long, or a canon step that got in the way. Use only evidence already in context; do not search for reasons to run it.

Then run `canon.py trace end <id> <outcome>`.
