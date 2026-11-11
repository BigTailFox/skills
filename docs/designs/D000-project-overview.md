---
status: active
created: 2026-10-23
updated: 2026-11-11
revision: 3
modules: []
summary: Agent skills built around canon, a documentation system kept in the repository; one module, its capabilities and the designs that own them.
refs: [D001, D002, D003, D004, D005, D006, D007, D008, D009]
owns: [architecture]
paths: []
reviewed: 3
reviewers: [claude-opus-5.5]
implemented: 3
---

# D000: Project overview

## Goals

1. Agent skills for long-running software projects, built around canon: a documentation system that lives in each project's repository and carries designs, plans and decisions from one session, and one model, to the next.
2. They serve developers who install them into Cursor, Claude Code, Codex or another agent that follows the [Agent Skills specification](https://agentskills.io), and the agents that run them in those developers' projects. The skills refer to each other by name, so they are installed together.
3. Out of scope: installing, updating and removing skills, which the `skills` CLI (`npx skills`) does, and skills outside the canon documentation system.

## Spec

### Capabilities

| Capability | Modules | Design |
|---|---|---|
| Docs that live in the repository: numbered docs with frontmatter, references, a lifecycle and archiving, created, checked and archived with `canon.py`, and the rules for writing them | canon | [D006: Doc model and writing rules](D006-doc-model.md) |
| Queries of the docs and the code they govern (`canon.py show`, `find`, `which`, `affected`), and renaming and renumbering docs (`rename`, `renumber`) | canon | none |
| The generated index of each docs root's docs in `docs/README.md` and `docs/archived/README.md` (`canon.py index`) | canon | [D005: Docs index](D005-docs-index.md) |
| Change tiers and the flow each sets, the review gate, and design problems found while working from a design | canon | [D007: Change tiers and the review gate](D007-change-tiers.md) |
| Writing designs and plans, and implementing plans slice by slice (`canon-design`, `canon-plan`, `canon-implement`) | canon | none |
| The project overview, D000, with the designs `audit` finds D000 does not reach, the source areas it finds no design covers and the designs whose code changed in commits that do not name them | canon | [D002: Project overview and as-built designs](D002-overview-and-as-built.md) |
| As-built designs, and the backfill before a change to behavior no design states | canon | [D002: Project overview and as-built designs](D002-overview-and-as-built.md) |
| Blind reviews by fresh subagents, a cross-family reviewer included, for the review gate, code review or any request (`canon-blind-review`), and a fresh worker for each plan slice | canon | [D003: Subagents](D003-subagents.md), [D007: Change tiers and the review gate](D007-change-tiers.md) |
| Opt-in tracing of workflow runs for replay and analysis (`canon.py trace`) | canon | [D001: Skill telemetry with canon trace](D001-skill-telemetry.md) |
| Project setup: `docs/`, the `AGENTS.md` block, migration of existing docs and upgrades of a project's `canon.py` (`canon-init`) | canon | [D004: Project setup](D004-project-setup.md) |
| Docs kept in step with the code: the docs step, repair after a merge or rebase, and the doc health audit (`canon-sync`) | canon | none |
| Code review of a finished change (`canon-code-review`) | canon | none |
| Codebase review from chosen angles (`canon-review`) | canon | none |
| Test-driven development at a slice's seams (`canon-tdd`) | canon | none |
| Settling open decisions (`canon-grill`) | canon | [D009: Settling decisions](D009-settling-decisions.md) |
| Throwaway prototypes (`canon-prototype`) and research from primary sources (`canon-research`), recorded as E docs | canon | [D008: Prototypes and research](D008-experiments.md) |
| Diagnosis of hard bugs and performance regressions, recorded as I docs (`canon-investigate`) | canon | none |
| Deep-module vocabulary and designing an interface twice (`canon-codebase-design`) | canon | none |
| Handoff to a fresh agent (`canon-handoff`) | canon | none |
| Retro on friction in the tooling and the agent workflow (`canon-retro`) | canon | none |
| Teaching a topic in one answer or a course (`canon-teach`) | canon | none |
| Reference for writing docs that agents read (`canon-agent-writing`) | canon | none |
| A layout the `skills` CLI installs from: each skill at `skills/<category>/<name>/SKILL.md`, and no `SKILL.md` elsewhere | canon | none |

### Modules

| Module | Path | Purpose | Entry points | Design |
|---|---|---|---|---|
| canon | skills/, tests/ | The skills: `skills/governance/` builds and maintains the documentation system, `skills/execution/` does development work through it, and `tests/` holds the regression tests of `canon.py` and of the repository tooling | `skills/governance/canon/SKILL.md`, `skills/governance/canon/scripts/canon.py`, each skill's `SKILL.md` | [D001: Skill telemetry with canon trace](D001-skill-telemetry.md), [D002: Project overview and as-built designs](D002-overview-and-as-built.md), [D003: Subagents](D003-subagents.md), [D004: Project setup](D004-project-setup.md), [D005: Docs index](D005-docs-index.md), [D006: Doc model and writing rules](D006-doc-model.md), [D007: Change tiers and the review gate](D007-change-tiers.md), [D008: Prototypes and research](D008-experiments.md), [D009: Settling decisions](D009-settling-decisions.md) |

### Dependencies

There is one module, so no direction between modules applies. These hold inside it and at its edges:

- Skills refer to each other by name, never by a relative path across skill directories, since `npx skills` installs them flat by name.
- A skill runs the project's copy of `canon.py` at the path the canon block of the repo root's `AGENTS.md` names, and the `canon` skill's own `scripts/canon.py` while the project has no copy. `init` puts the copy where [D004§init: init](D004-project-setup.md#init) states.
- Execution skills read and write project docs only through the documentation system the governance skills define.
- `canon.py` is a single file on the Python 3.8+ standard library, and runs `git` in a Git checkout.
- The repository tooling, `scripts/validate.py`, checks each skill's layout, frontmatter, length and links, that every `SKILL.md` on disk that Git tracks or does not ignore is a skill's own, directly inside a non-hidden `skills/<category>/<name>/`, failing when Git cannot list the files, the links of the root's Markdown files, the Skills tables of `README.md`, `CANON_VERSION`, and [D001§budgets: budgets](D001-skill-telemetry.md#budgets) for skill text, failing when no paragraph of the `canon` skill starts as they say. That last check needs tiktoken and its `cl100k_base` encoding; when either fails to load, it prints why, with the `uv run` command that adds a missing tiktoken. It runs `tests/`, where `test_validate.py` tests it. Nothing under `skills/` depends on it.

### Glossary

The module and the repository tooling share these terms. The Skill rules of [AGENTS.md](../../AGENTS.md) state what a skill must meet. The `canon` skill defines the documentation system's terms, such as tier, review gate and slice, and `canon-codebase-design` those of module design.

- **Skill**: a directory `skills/<category>/<name>/` holding a `SKILL.md`; the directory name is the skill's name.
- **Category**: `governance`, for skills that build and maintain the documentation system, or `execution`, for skills that do development work through it.
- **Manual skill**: a skill that runs only as a command. An **auto skill** also loads when the context calls for it. The README's Skills tables give each skill's trigger mode.
- **Ported skill**: a skill adapted from [mattpocock/skills](https://github.com/mattpocock/skills), whose directory holds the upstream `LICENSE` and a `NOTICE`.
- **`CANON_VERSION`**: the decimal integer, written as a string, that `canon.py` carries and `init` compares with a project's copy to decide whether to replace it.

## Decisions

- The repository ships no install script; installing, updating and removing are left to `npx skills` (`AGENTS.md`).
- `CANON_VERSION` is separate from the release version: `init` upgrades a project's copy by version number only (`AGENTS.md`).
- `canon.py` is one file on the standard library, copied into each project, where agents and CI run it (`canon.py`'s docstring, `canon-init`; reason unknown, kept as found).
- The tooling's tests share `tests/` with `canon.py`'s, which `validate.py` already runs, and only `skills/`, the part that is installed, must not depend on the tooling (the user's decision; R001-F31). Until a design lists `tests/test_validate.py`, coverage reports it as uncovered; like the tooling it tests, it needs no backfill.
