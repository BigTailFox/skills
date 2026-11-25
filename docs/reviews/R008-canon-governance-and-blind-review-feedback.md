---
status: open
created: 2026-11-25
updated: 2026-11-25
revision: 1
modules: [canon]
summary: Canon 1.0 feedback on maintainer control, workflow and blind review, CLI responsibilities and packaging, skill boundaries and core guidance.
refs: [D000, D001, D002, D003, D004, D006, D007, D011]
---

# R008: Maintainer feedback on Canon governance and blind review

## Scope

The maintainer wants to finish the simplification before Canon 1.0. They want to understand how much rereading it takes to regain a clear picture of the workflow and to see when accumulated fixes change which decisions come back to them. This usability review began at `bd5c4a9` with the governance skills `canon`, `canon-init` and `canon-sync`, and Canon's `canon-blind-review`. The maintainer deferred the execution skills ported from `mattpocock/skills`.

### Maintainer principles

1. **Reveal the workflow one step at a time.** Give the agent the guidance it needs for its next action. At the end of each step, use the result to point to the next action or signal that the workflow is complete.
2. **Leave room for judgment.** Tell the agent what it can do and when a suggested approach saves time or improves the result. Require a particular approach only when there is a compelling reason.
3. **Enforce mechanical rules through `canon.py`.** Put as many mechanically enforceable rules as possible in the CLI. When the rules determine a document template or a piece of code, have the command generate it so the agent can focus on the parts that require judgment.
4. **Keep `SKILL.md` short enough to be read in full.** Allow for harnesses that read only part of a long skill. Put rules specific to one step or situation in a dedicated reference and link to it from the point where the agent needs it.

## Findings

### Direction and maintainer control

| ID | Severity | Finding | Disposition |
|----|----------|---------|-------------|
| R008-F16 | major | The maintainer wants to finish the simplification before 1.0 and is weighing a fresh repository against refactoring this one. [Repository choice](#r008-f16-repository-choice) | open |
| R008-F2 | major | The maintainer wants to spot shifts in who decides as fixes accumulate. The review recommends tracing a routine fix and an L2 design on one page, including agent decisions, CLI checks, reviewers and user approval, to choose which rules and regression cases to keep. [D007§change-tiers: change tiers](../archived/designs/D007-change-tiers.md#change-tiers) | open |
| R008-F1 | major | Assess whether accumulated workflow rules get in the way of an agent exercising judgment on routine tasks, and which rules are worth simplifying. | open |
| R008-F20 | major | Do not duplicate prose or write designs for an equivalent natural-language specification (skills, prompts, playbooks, policy Markdown). Emphasize this rule in Canon 1.0's core skill, `writing.md`, `as-built.md` and `canon-design` so designs cover only code/system contracts, cross-cutting architecture and `Decisions`. | open |

#### R008-F16 Repository choice

The review recommends developing 1.0 on a branch of `BigTailFox/skills`. Projects already pin releases from this repository in `skills-lock.json`. A Python CLI package can ship from the same tree, so a command, the skill that calls it and the regression tests can change together. A separate CLI repository would be worth revisiting if other tools start using the CLI and need a different release schedule. [D004§install: installation and pinning](../designs/D004-project-setup.md#install)

Before 1.0, try both a fresh installation and an upgrade of a project pinned to `v0.9.4` with existing document IDs and links to resolve.

### Workflow and blind review

| ID | Severity | Finding | Disposition |
|----|----------|---------|-------------|
| R008-F10 | major | The workflow reference has grown into another long entry point. Keep the next decision visible and put detailed procedures at the phase that needs them. [Section-by-section assessment and CLI proposals](R008/workflow.md#workflow-section-assessment) | open |
| R008-F18 | major | The maintainer wants a clear boundary for detail in concepts, designs and plans. Skipping plan review would push delivery decisions into the design to get independent scrutiny before implementation. [Detail in concepts, designs and plans](R008/workflow.md#detail-in-concepts-designs-and-plans) | open |
| R008-F17 | major | The maintainer values blind review and finds it time-consuming. Tier mostly reflects design scope. The complexity and scale of the change itself matter, and its difficulty is hard to judge up front. [Blind review effort for a change](R008/workflow.md#blind-review-effort-for-a-change) | open |
| R008-F19 | major | The maintainer has found it effective to review a plan together with the design revisions made while writing it and proposes one blind round for that case. The review recommends a separate verdict for each revision. [Joint design and plan review](R008/workflow.md#joint-design-and-plan-review) | open |
| R008-F15 | major | Keep the first-round independence rules visible in `canon-blind-review`. Open recovery and later-round instructions at their triggers, and let the CLI prepare and check the review records. [Section-by-section blind-review assessment](R008/blind-review.md) | open |

### CLI responsibilities and distribution

| ID | Severity | Finding | Disposition |
|----|----------|---------|-------------|
| R008-F14 | major | Agents still transcribe verified review results and user decisions, maintain structured rows and reconstruct information already available to the CLI. Some documented formats also receive only partial validation. [Current coverage and suggested priorities](R008/cli-coverage.md) | open |
| R008-F5 | major | The maintainer proposes splitting `canon.py` into modules and publishing a Python package with declared dependencies. How projects obtain a CLI version compatible with their pinned skills is open. [Package and installation](R008/cli-coverage.md#r008-f5-standalone-cli-package-and-runtime-dependencies) | open |

### Core and companion skills

| ID | Severity | Finding | Disposition |
|----|----------|---------|-------------|
| R008-F3 | major | Keep the core `SKILL.md` as a concise overview. Each section should link to the dedicated document that owns its detailed rules. [Core skill structure](R008/core-skill.md#r008-f3-core-skill-structure) | open |
| R008-F8 | major | The maintainer proposes an optional `canon-trace` skill and mechanical activation so ordinary sessions can skip trace-specific checks and instructions. [Trace activation](R008/core-skill.md#r008-f8-trace-activation) | open |
| R008-F7 | minor | The maintainer questions the need for `canon-sync` and does not recall invoking it. The review recommends retiring the standalone skill and keeping its on-demand docs, merge and audit functions available. [Maintenance and audit](R008/core-skill.md#r008-f7-role-of-canon-sync) | open |
| R008-F9 | minor | Move review evidence and the reviewer configuration example to the skills that use them. [Evidence and reviewer configuration](R008/blind-review.md#review-evidence-and-reviewer-configuration) | open |

### Core skill instructions and references

| ID | Severity | Finding | Disposition |
|----|----------|---------|-------------|
| R008-F4 | minor | Remove the command catalogue from the core skill. Give the agent the command to run and let the CLI explain usage and next steps through help, results and errors. [Tool section draft](R008/core-skill.md#r008-f4-tool-section-of-the-core-skill) | open |
| R008-F6 | minor | Keep Reading docs short. Point the agent from each reading question to the document, section or query that answers it. [Reading docs draft](R008/core-skill.md#r008-f6-reading-docs-section-of-the-core-skill) | open |
| R008-F13 | minor | List document types by purpose in the core skill. The maintainer proposes one format reference for per-type structure, frontmatter and embedded source. [Document formats](R008/core-skill.md#r008-f13-document-formats) | open |
| R008-F12 | minor | Give concurrent work a dedicated reference that an agent can reach before a shared-checkout write or a partial commit. [Concurrent work](R008/core-skill.md#r008-f12-concurrent-work) | open |
| R008-F11 | minor | Keep the writing guide useful as it grows. Its flat list mixes general editorial judgment with instructions for particular kinds of content. [Writing guidance](R008/core-skill.md#r008-f11-writing-guidance) | open |
