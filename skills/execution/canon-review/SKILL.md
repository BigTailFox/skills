---
name: canon-review
description: Runs a periodic review of a module or the whole repository from chosen angles (architecture, performance, security, functional, usability), one parallel subagent per angle. It records the findings in a canon review doc with a visual HTML report, then takes every finding through the user's decision. A finding is fixed, moved into a design, plan, investigation or backlog concept, or declined with its reason recorded. Use when the user asks for a codebase, module, architecture, performance, security or usability review, or when canon audit reports a review is due.
disable-model-invocation: true
---

# Codebase review

Read the `canon` skill first. `canon.py` means the project copy named in `AGENTS.md`. This reviews the code as it stands; reviewing one change is the `canon-code-review` skill's job.

## 1. Scope

Use the modules and angles the user names. Otherwise propose a scope and wait for the user to confirm it:

- `canon.py audit`: stale designs and due reviews per docs root.
- Hot spots: the files changed most since the last review, from `git log --since=<last R created> --name-only` within the module's paths.
- Design coverage: designs `check` reports as over 500 lines, and source files where `which` prints `no design`.
- Angles: **architecture** after many changes; **performance** when designs have Budgets or slowness was reported; **functional** when active designs have code commits since their last update; **usability** for user-visible surfaces (CLI, API, UI, config); **security** only when the project or feature is security-related or the user asks.

## 2. Create the doc

Run `canon.py new R <slug>`. Scope records the commit (`git rev-parse HEAD`), the modules and paths, and the angles. Attachments go in `reviews/R00X/`.

## 3. Review each angle

Spawn one subagent per angle, in parallel, in the foreground. Each brief carries:

- The scope: commit, module paths, and the governing designs (`which`, `show`), the architecture design and the relevant `AGENTS.md` files to read.
- The angle's reference pasted in full: [architecture.md](architecture.md), [performance.md](performance.md), [security.md](security.md), [functional.md](functional.md), [usability.md](usability.md).
- The rules: modify no file. Skip anything a design's Decision line already rejected unless the friction is severe enough to reopen it, and then name the Decision. Replace secrets with `<REDACTED>`.
- The output: at most 10 findings, most severe first. Each has a title, location (files, design sections), problem, evidence, suggestion, and severity `blocker`, `major` or `minor`. Stay under 600 words.

## 4. Report

1. Fill Findings: one row per finding, ids `R00X-F1`, `R00X-F2`, ..., the angle as a prefix (`architecture: Order intake is shallow`), disposition `open`.
2. Write `reviews/R00X/report.html` following [html-report.md](html-report.md), link it from Scope, and open it for the user (`xdg-open`, `open` or `start`).
3. Present the findings grouped by angle, with each angle's top recommendation. Do not rerank across angles: each angle answers a different question.

## 5. Decide with the user

Take the findings to the user in rounds with the `canon-grill` skill; the user decides each one:

- **Fix now**, when it changes no spec (refactor, or a bug fix restoring specified behavior): implement it as an L0 change with `canon-tdd` and `canon-code-review`, run the docs step, and set `fixed <commit>`.
- **Needs a spec change**: set `moved D00X` to the design that will carry it, or `moved P00X` when a plan covers it, and tell the user the next step is the `canon-design` or `canon-plan` skill.
- **A defect**: create an investigation (`canon.py new I <slug>`) and set `moved I00X`.
- **Later**: add it as an Idea to the module's backlog concept (`canon.py find backlog`, else `canon.py new C <module>-backlog`) and set `moved C00X`.
- **Rejected**: set `declined <reason>`. When the reason is lasting and the idea likely to return, add a one-line Decision to the owning design so later reviews skip it.

Before deciding on an architecture candidate, the user may explore it: walk it with `canon-grill` and design alternative interfaces with the `canon-codebase-design` skill.

## 6. Close

Once no finding is `open`, run `canon.py archive R00X closed` and `canon.py check --fix`, then commit (Conventional Commits, `docs` type, `Refs: R00X`).
