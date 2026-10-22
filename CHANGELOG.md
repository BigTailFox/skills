# Changelog

Notable changes in each release. Versions follow [Semantic Versioning](https://semver.org); while the major version is 0, a minor release may change how skills behave.

## 0.2.0 - 2026-10-22

Adds `canon-retro`, for 19 skills in all, opt-in tracing, known issues, and a way to handle problems found in accepted designs.

- `canon-retro`, a new skill: a canon workflow that hit friction in the tooling or the agent workflow, such as a correction, a command that would not run or a long search, ends with a retro that proposes at most three fixes concrete events justify (a check, a fix to the development environment, a design standard, a pointer), and you answer them in one reply. Smooth workflows skip it, and you can ask for a retro at any time.
- Tracing: `canon.py trace on` records how canon's workflows run, so the skills can be judged and improved on real work. Each unit of work, such as a design, a plan slice, a review gate or a code review, logs its outcome, its review findings' severities and dispositions, commit ids and digests of the skill files in use; a snapshot of the work tree at each start, and each review's files, are kept for replay. Tracing is off until you turn it on, nothing it records leaves the machine, and no commit or push of the project carries it; `trace status` reports on it and `trace prune` trims it. The README's Tracing section has the details.
- Known issues: a problem found in a design or in the code it governs that you leave for later is listed in that design with its severity, source, date and next step until a change resolves it. `canon.py check` validates the rows, the docs index and `which`, `find` and `affected` count them, and `audit` lists them oldest first. Review gates, code reviews and codebase reviews record there what you leave for later, and code review no longer creates R docs.
- Design problems: a flaw found in an accepted design while planning, implementing or reviewing comes to you with a proposed fix, together with the same review's other findings, and only the work that depends on it waits for your decision. An L1 fix is made in the same session and passes an L1 gate; an L2 fix goes to `/canon-design`. An L0 change that turns out to alter a spec now finishes as L1 in the same session, without a plan, instead of stopping.
- Reviewers report every blocker and major finding and at most 10 minor ones, most severe first, instead of at most 10 findings in all. Code review and `canon-review` replace their word caps with a rule that each finding be as short as a reader can still understand and verify, a worker's report has no word limit, and a code review keeps its reviewers' files apart from the plan gate's instead of replacing them.
- `canon.py renumber` normalizes a requested id such as `D0002` to `D002`.
- `canon.py` is now canon version 13: run `/canon-init` in an existing project to upgrade its copy.

## 0.1.1 - 2026-10-14

Cross-family reviewers per session family, and renumbering that settles id collisions after a merge.

- `.canon/canon-blind-review/reviewer.md` may list several reviewers, and a review uses the first whose family differs from the session's; `/canon-init` asks which model families your sessions run on and sets up a reviewer of another family for each.
- `canon.py renumber --base <branch>` settles an id collision left by a merge or rebase onto that branch: it gives each sub-design, attachment and reference to one of the two docs only when the branch or the links show whose it is, and lists the references it keeps for you to fix. Commands that take an id refuse one that two docs share. This is canon version 5.
- A plan fix that changes what the plan delivers is a new revision, and the plan's slices continue only after it passes the review gate.
- A worker stops on a failing test once two attempts in a row bring no new evidence about its cause, instead of after any two attempts.

## 0.1.0 - 2026-10-14

First release: 18 skills built around canon, for Cursor, Claude Code and Codex.

- `canon`: a documentation system for long-running, multi-session, multi-model work. Numbered concepts, designs, plans, reviews, experiments and investigations live under `docs/`; every change gets an L0, L1 or L2 tier; designs and plans pass a blind review gate with same-model and cross-family reviewers; and `canon.py` (canon version 4) creates, checks, queries, audits and archives the docs.
- `canon-init` and `canon-sync`: set canon up in a project or monorepo module, configure the machine's cross-family reviewer, and keep docs in step with the code.
- Fifteen execution skills that work through canon: design, plan and implementation phases, with a fresh worker subagent per plan slice; two-axis code review; blind and codebase reviews; TDD, grilling, prototyping, research and investigation; handoff, teaching and writing for agents. Fourteen of them are adapted from [mattpocock/skills](https://github.com/mattpocock/skills).
