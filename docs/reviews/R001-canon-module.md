---
status: open
created: 2026-11-03
updated: 2026-11-05
revision: 1
modules: []
summary: First codebase review of the canon module at release 0.3.1, from the architecture, usability and functional angles.
refs: [D000, D001, D002, D003, D004, D005]
---

# R001: Codebase review of the canon module

## Scope

- Commit: `7c2ebf258eea9f963af78ff824ac48a4d07b5751` (release 0.3.1), the first codebase review; 140 code commits since the repository began.
- Modules and paths: the one module, canon (`skills/`, `tests/`), plus the repository tooling `scripts/validate.py`.
- Angles: architecture, usability, functional.
- Hot spots, by commits in the last 90 days: `skills/governance/canon/scripts/canon.py` (25, 3383 lines), `tests/test_canon.py` (22), `skills/governance/canon/workflow.md` (21), `skills/governance/canon/SKILL.md` (19), `canon-implement` (18), `canon-blind-review` (14), `canon-init` and `canon-code-review` (13 each), `canon-review` (10).
- Design coverage: 14 of D000's 21 capabilities name no design. `audit` lists, among others, `canon-teach`, `canon-codebase-design`, `canon-prototype`, `canon-tdd`, `canon-grill`, `canon-research` and `canon-agent-writing` as wholly uncovered; no design is over 500 lines. [D001: Skill telemetry with canon trace](../designs/D001-skill-telemetry.md) is at revision 7 with `implemented: 5`, and no plan is open.
- Governing designs: [D000: Project overview](../designs/D000-project-overview.md), [D001: Skill telemetry](../designs/D001-skill-telemetry.md), [D002: Project overview and as-built designs](../designs/D002-overview-and-as-built.md), [D003: Subagents](../designs/D003-subagents.md), [D004: Project setup](../designs/D004-project-setup.md), [D005: Docs index](../designs/D005-docs-index.md).

## Findings

Each angle's report, with locations, evidence and suggestions, is attached: [architecture](R001/architecture.md) (F1–F12), [usability](R001/usability.md) (F13–F25), [functional](R001/functional.md) (F26–F32).

| ID | Severity | Finding | Disposition |
|----|----------|---------|-------------|
| R001-F1 | major | architecture: File-grained `paths` make coverage, `which` and `Refs:` overstate what designs govern; half of `canon.py` has no design yet looks covered | moved D002 |
| R001-F2 | major | architecture: Installed skills and a project's `canon.py` copy drift apart with no minimum-version check | moved D004 |
| R001-F3 | major | architecture: Running a blind review is spread over four skill files that restate each other's rules | moved D003 |
| R001-F4 | major | architecture: A failing Git is read as "outside Git", so `new` can reuse a deleted doc's id | fixed f9226e2 |
| R001-F5 | minor | architecture: Closing steps and finding routing are copied into each workflow skill | moved C001 |
| R001-F6 | minor | architecture: The review snapshot every confirmation needs runs on the opt-in trace subsystem | moved C001 |
| R001-F7 | minor | architecture: The machine-level reviewer file is stored per checkout | moved D003 |
| R001-F8 | minor | architecture: The test suite takes three minutes and `validate.py` always runs all of it | moved C001 |
| R001-F9 | minor | architecture: Anchors and skill names referenced between skill texts are unchecked | moved C001 |
| R001-F10 | minor | architecture: `canon-review/security.md` is classified as a project doc, so coverage skips it | moved C001 |
| R001-F11 | minor | architecture: Uncovered contracts other skills execute (grill triage, tdd, `smells.md`, `writing.md`, skill layout) need designs first | moved C001 |
| R001-F12 | minor | architecture: One doc type's rules are spread across many places in `canon.py` | moved C001 |
| R001-F13 | major | usability: Auto skills fire in projects without canon, and `canon.py new` then writes canon docs there | moved C001 |
| R001-F14 | major | usability: `init --hook` crashes in the agent sandbox and its hook blocks setup's own step-4 commit | open |
| R001-F15 | major | usability: A Claude Code project with an existing `CLAUDE.md` never imports the canon block | open |
| R001-F16 | minor | usability: `/canon-init` has no rule for which flow to run | open |
| R001-F17 | minor | usability: Several `canon.py` error messages do not name the value or the next step | moved C001 |
| R001-F18 | minor | usability: `--base` errors do not say whether the ref is missing or the history shallow | moved C001 |
| R001-F19 | minor | usability: `which` answers confidently for paths that do not exist | moved C001 |
| R001-F20 | minor | usability: Phase-closing commands use the `/skill` form, which Codex does not accept | open |
| R001-F21 | minor | usability: The canon block does not say where to get the skills | open |
| R001-F22 | minor | usability: The README states no requirements (Python 3.8+, Git) | open |
| R001-F23 | minor | usability: `-h` texts are thin, and `renumber` runs without a collision | open |
| R001-F24 | minor | usability: `init --root` with a typo silently creates a module | open |
| R001-F25 | minor | usability: `canon-retro`'s closing-step trigger sits past the 190-character cut | open |
| R001-F26 | major | functional: D001 revision 6 (as-built gate snapshots) is not implemented and no plan carries it | open |
| R001-F27 | major | functional: Tests that expect a directory outside Git write docs into whatever repo holds `TMPDIR` | fixed eb76e61 |
| R001-F28 | minor | functional: `adopt` and the index format and check have almost no tests | moved C001 |
| R001-F29 | minor | functional: `adopt` breaks links to the adopted file's H1 anchor | moved D004 |
| R001-F30 | minor | functional: The canon skill's Tool table disagrees with the CLI (`renumber`, `affected FILE`, audit's idle list) | open |
| R001-F31 | minor | functional: `validate.py` does not catch a `SKILL.md` outside `skills/<category>/<name>/` | open |
| R001-F32 | minor | functional: D001's `implemented` covers only delivery step 1; analysis and replay are missing | open |
