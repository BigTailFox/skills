---
status: active
created: 2026-10-23
updated: 2026-11-25
revision: 4
modules: []
summary: Agent skills built around canon, a documentation system kept in the repository; one module, its capabilities and the designs that own them.
refs: [D001, D002, D004, D005, D006, D010, D011, D012, D013]
owns: [architecture]
paths: []
reviewed: 4
reviewers: [claude-opus-5.5, gemini-4-argon-high]
approved: 4
implemented: 4
---

# D000: Project overview

## Goals

1. Agent skills for long-running software projects, built around canon: a documentation system that lives in each project's repository and carries designs, plans and decisions from one session, and one model, to the next.
2. They serve developers who install them into Cursor, Claude Code, Codex or another agent that follows the [Agent Skills specification](https://agentskills.io), and the agents that run them in those developers' projects. The skills refer to each other by name, so they are installed together.
3. Out of scope: installing, updating and removing skills, which the `skills` CLI (`npx skills`) does, and skills outside the canon documentation system.

## Spec

### Glossary

The module, `canon`, and the repository tooling, `scripts/validate.py`, share these terms. The Skill rules of [AGENTS.md](../../AGENTS.md) state what a skill must meet. The `canon` skill defines the documentation system's terms, such as tier, review gate and slice, and `canon-codebase-design` those of module design.

- **Skill**: a directory `skills/<category>/<name>/` holding a `SKILL.md`; the directory name is the skill's name.
- **Category**: `governance`, for skills that build and maintain the documentation system, or `execution`, for skills that do development work through it.
- **Manual skill**: a skill that runs only as a command. An **auto skill** also loads when the context calls for it. The README's Skills tables give each skill's trigger mode.
- **Ported skill**: a skill adapted from [mattpocock/skills](https://github.com/mattpocock/skills), whose directory holds the upstream `LICENSE` and a `NOTICE`.
- **`CANON_VERSION`**: the decimal integer, written as a string, that `canon.py` carries. A project records the one it was last set up with, and every command compares it with its own ([D004§project-version: project version](D004-project-setup.md#project-version)).

### Capabilities

| Capability | Modules | Design |
|---|---|---|
| Docs that live in the repository: numbered docs with frontmatter, references, a lifecycle and archiving, created, checked (work tree, staged index, or commit) and archived with `canon.py` | canon | [D006: Doc model](D006-doc-model.md) |
| Queries of the docs and the code they govern (`canon.py show`, `find`, `which`, `affected`), and renaming and renumbering docs (`rename`, `renumber`) | canon | [D010: Doc queries and renames](D010-doc-queries-and-renames.md) |
| Source files and named regions embedded in documentation, refreshed with `canon.py embed` and verified in the selected tree | canon | [D011: Source code embedded in docs](D011-embedded-source.md) |
| The generated index of each docs root's docs in `docs/README.md` and `docs/archived/README.md` (`canon.py index`) | canon | [D005: Docs index](D005-docs-index.md) |
| Review CLI: isolated review rounds and snapshots (`canon.py review start`, `snapshot`), required coverage checks (`review check`), and worktree-local pending L2 approvals (`approvals`) | canon | [D013: Review CLI](D013-review-cli.md) |
| Project overview D000, `as_built` frontmatter checks, doc/skill path classification, `audit` coverage and unchecked commits, staged commit templates and per-commit `Refs:` validation | canon | [D002: Project overview, as-built checks and audit](D002-overview-and-as-built.md) |
| Opt-in workflow capture and history (`canon.py trace`), with an offline report on reviewer contributions, outcomes, measured costs and replay eligibility (`scripts/trace_report.py`) | canon | [D001: Skill telemetry with canon trace](D001-skill-telemetry.md) |
| Prepare, run, score and summarize paired replays of recorded reviews and plan slices (`scripts/replay_workflows.py`) | canon | [D012: Paired replay of Canon workflows](D012-workflow-replay.md) |
| Project setup CLI: project-local install location check, `CANON_VERSION` check, `canon.py init` and `canon.py adopt` | canon | [D004: Project setup](D004-project-setup.md) |
| Agent skill prose (`canon` workflow, tiers, review gate, concurrent work, writing rules, `canon-init`, `canon-sync`, `canon-blind-review`, `canon-design`, `canon-plan`, `canon-implement`, `canon-code-review`, `canon-review`, `canon-tdd`, `canon-grill`, `canon-prototype`, `canon-research`, `canon-investigate`, `canon-codebase-design`, `canon-handoff`, `canon-retro`, `canon-teach`, `canon-agent-writing`) | canon | none (skill text is authoritative) |
| A layout the `skills` CLI installs from: each skill at `skills/<category>/<name>/SKILL.md`, and no `SKILL.md` elsewhere | canon | none |

### Modules

| Module | Path | Purpose | Entry points | Design |
|---|---|---|---|---|
| canon | skills/governance/canon/scripts/, scripts/, tests/ | Code subsystems: the `canon.py` CLI (`skills/governance/canon/scripts/`), repository validation, trace reporting and paired replay tooling (`scripts/`), and their test suites (`tests/`). Pure-Markdown skill directories under `skills/` are self-authoritative and excluded from design coverage | `skills/governance/canon/scripts/canon.py`, `scripts/validate.py`, `scripts/trace_report.py`, `scripts/replay_workflows.py` | [D001: Skill telemetry with canon trace](D001-skill-telemetry.md), [D002: Project overview, as-built checks and audit](D002-overview-and-as-built.md), [D004: Project setup](D004-project-setup.md), [D005: Docs index](D005-docs-index.md), [D006: Doc model](D006-doc-model.md), [D010: Doc queries and renames](D010-doc-queries-and-renames.md), [D011: Source code embedded in docs](D011-embedded-source.md), [D012: Paired replay of Canon workflows](D012-workflow-replay.md), [D013: Review CLI](D013-review-cli.md) |

### Dependencies

There is one module, so no direction between modules applies. These hold inside it and at its edges:

- Skills refer to each other by name, never by a relative path across skill directories, since `npx skills` installs them flat by name.
- A skill runs the `scripts/canon.py` of the `canon` skill installed in the project, which refuses to run from outside the project ([D004§install: install](D004-project-setup.md#install)). In this repository, agents, reviewers included, run the working tree's `skills/governance/canon/scripts/canon.py` instead of the one the canon block's Tool line names, as `AGENTS.md` says outside the block, which `init` rewrites; a commit that bumps `CANON_VERSION` reruns `init`, so the block records the new version.
- Execution skills read and write project docs only through the documentation system the governance skills define.
- `canon.py` is a single file on the Python 3.8+ standard library, and runs `git` in a Git checkout.
- The offline report in `scripts/trace_report.py` uses the working tree's `canon.py` for trace history and Git reads. It reads project stores, host evidence and an optional adjudication table. It runs from a checkout of this repository.
- The repository tooling, `scripts/validate.py`, checks each skill's layout, frontmatter, length and links, that every `SKILL.md` on disk that Git tracks or does not ignore is a skill's own, directly inside a non-hidden `skills/<category>/<name>/`, failing when Git cannot list the files, the links of the root's Markdown files, section links and explicit skill and workflow references in skill text, the Skills tables of `README.md`, `CANON_VERSION`, and [D001§budgets: budgets](D001-skill-telemetry.md#budgets) for skill text, failing when no paragraph of the `canon` skill starts as they say. That last check needs tiktoken and its `cl100k_base` encoding; when either fails to load, it prints why, with the `uv run` command that adds a missing tiktoken. It runs `tests/`, where `test_validate.py` tests it. Nothing under `skills/` depends on it.

## Decisions

- The repository ships no install script; installing, updating and removing are left to `npx skills` (`AGENTS.md`).
- `CANON_VERSION` is separate from the release version: it changes only with `canon.py`, and a project's recorded version is compared by it alone ([D004§project-version: project version](D004-project-setup.md#project-version)).
- `canon.py` is one file on the standard library, which agents and CI run from the `canon` skill installed in each project; projects keep no copy of it ([D004: Project setup](D004-project-setup.md) gives the reasons).
- The tooling's tests share `tests/` with `canon.py`'s, which `validate.py` already runs, and only `skills/`, the part that is installed, must not depend on the tooling (the user's decision; R001-F31). Until a design lists `tests/test_validate.py`, coverage reports it as uncovered; like the tooling it tests, it needs no backfill.
- Pure skill Markdown (`skills/**/*.md`) is its own single source of truth: do not write designs that restate an equivalent natural-language specification or backfill prose skills as-built. `docs/designs/` specifies only code subsystems (`canon.py`, telemetry/replay tooling, tests) and cross-cutting architecture, invariants and `Decisions` that do not belong in runtime skill text (the user's decision, 2026-11-25; supersedes D003/D007 prose and retires D008/D009).
