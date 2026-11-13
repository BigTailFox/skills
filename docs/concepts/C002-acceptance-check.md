---
status: draft
created: 2026-11-13
updated: 2026-11-13
revision: 2
modules: [canon]
summary: Acceptance check of a finished change, a canon-acceptance skill whose fresh subagent runs the real artifact against the design's Goals before code review.
refs: [C001, D001, D003, E002]
---

# C002: Acceptance check of a finished change

## Motivation

No step of canon's flow runs a finished change the way a user would. `canon-tdd` calls a slice or change done when its test criteria pass at the seams the plan names and nothing green turned red, `canon-code-review` reads the diff, and `canon-implement` then runs the docs step. Every slice can pass at its own seams while the whole change fails where slices meet or at edges no seam covers: an entry point never wired up, a missing config key or migration, a UI control that calls nothing. This repository meets the gap itself: the README's [Host verification](../../README.md#host-verification) checks are an acceptance list run by hand, because no test covers them.

Canon serves long-running work that sessions often finish unattended, so the user comes back to a claim that a change is done. Evidence that it works, the commands run and what they printed, serves that user better than a report of green tests. Code review keeps the session that wrote the code from reviewing it ([D003§reviewers: reviewers](../designs/D003-subagents.md#reviewers)), and the same reason applies to judging that the code works.

## Ideas

- **A `canon-acceptance` skill.** A fresh subagent that saw none of the implementation reads the governing designs' Goals and Spec and the change's acceptance scenarios, builds and runs the real artifact from outside (CLI, HTTP, browser, real files), and reports each scenario as pass or fail with the commands it ran and what it observed. It is an auto skill: `canon-implement` reaches it by name, and requests such as "try it out", "smoke test" or "does it actually work" should load it. Its name avoids "verify", which `canon-implement` uses for checking a worker's slice.
- **Scenarios written at planning time.** `canon-plan` adds a few acceptance scenarios to the plan, each a user-visible action and its expected outcome, traced to a design Goal. Without a plan, the subagent derives them from the design's Goals and Spec and lists them in its report for the user to check.
- **Place in the flow.** `canon-implement` runs it after the last slice and before the code review, so the fixes it causes reach the reviewed diff.
- **Running the artifact** ([E002§conclusion: E002](../experiments/E002-skill-library-survey.md#conclusion), item 6). A bundled script starts the app's servers, waits for their ports and runs the scenario commands, and the subagent calls it as a black box, as anthropics/skills' `webapp-testing` does. Each scenario's verdict is pass, fail, unavailable or blocked, so an artifact the sandbox cannot run is reported as such and never as a pass. For steps only the user can perform, a generated script walks the user through them and captures the results, as mattpocock/skills' `wizard` and `canon-investigate`'s human-in-the-loop template do. A scenario checked by a tool the agent cannot argue with, such as a real browser, axe-core or a vulnerability database, weighs more than the project's own tests, the one check the agent writes itself.
- **Results.** Each scenario's verdict, command and observed output go into the plan's Log, with screenshots and long outputs as plan attachments. A failure is fixed in the change, or deferred as a known issue of the governing design, as a deferred code review finding is.
- **Scaled to the change.** It runs when a change alters user-visible behavior, which L1 and L2 changes usually do. L0 changes skip it unless the user asks: a bug fix carries a regression test that reproduces the failure, and a refactor alters nothing callers see.
- **Cost, and evidence before building it.** It adds a subagent to every change it runs on, against the cost items of [C001: Canon backlog](C001-canon-backlog.md), such as code review scaled to risk and a token budget for the core texts. Before a design, the trace analysis of [D001: Skill telemetry](../designs/D001-skill-telemetry.md) on projects piloting canon could count investigations and L0 fixes that touch a design's code soon after a plan under it is archived `done`, as a proxy for defects that tests and code review let through.

## Open questions

- What does the subagent need to run the artifact (build commands, services, credentials, seeded data), and where does a project state it: D000, a design, or `AGENTS.md`?
- Do scenarios belong to the plan, which is archived when done, or to the design, so later changes can rerun them as a regression suite? If the design, in which section and in what form?
- What may the subagent read and stay independent: the code, to learn how to build and run it, but not the plan's Log or the worker reports?
- Who decides that a change alters user-visible behavior: the plan's author at planning time, or `canon-implement` at the end?
