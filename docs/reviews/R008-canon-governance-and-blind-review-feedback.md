---
status: open
created: 2026-11-25
updated: 2026-11-25
revision: 1
modules: [canon]
summary: Maintainer feedback on the core skill, document formats, concurrent work, workflow and writing, blind review, tracing, CLI packaging and canon-sync.
refs: [D000, D001, D002, D003, D004, D006, D007, D011]
---

# R008: Maintainer feedback on Canon governance and blind review

## Scope

The maintainer wants to understand how much rereading it takes to regain a clear picture of Canon. This usability review starts with `canon`, `canon-init`, `canon-sync` and `canon-blind-review` at `bd5c4a9`. The maintainer deferred the execution skills ported from `mattpocock/skills`. The first comments concern the shared workflow and the core `canon` entry point.

### Maintainer principles

1. **Reveal the workflow one step at a time.** Give the agent the guidance it needs for its next action. At the end of each step, use the result to point to the next action or signal that the workflow is complete.
2. **Leave room for judgment.** Tell the agent what it can do and when a suggested approach saves time or improves the result. Require a particular approach only when there is a compelling reason.
3. **Enforce mechanical rules through `canon.py`.** Put as many mechanically enforceable rules as possible in the CLI. When the rules determine a document template or a piece of code, have the command generate it so the agent can focus on the parts that require judgment.
4. **Keep `SKILL.md` short enough to be read in full.** Allow for harnesses that read only part of a long skill. Put rules specific to one step or situation in a dedicated reference and link to it from the point where the agent needs it.

## Findings

| ID | Severity | Finding | Disposition |
|----|----------|---------|-------------|
| R008-F1 | major | Assess whether accumulated workflow rules get in the way of an agent exercising judgment on routine tasks, and which rules are worth simplifying. | open |
| R008-F2 | major | After a series of small fixes, the maintainer wants to see how the overall workflow compares with their original intent, especially what an agent can decide and what comes back to them. [D007§change-tiers: change tiers](../designs/D007-change-tiers.md#change-tiers) | open |
| R008-F3 | major | Keep the core `SKILL.md` as a concise overview. Each section should link to the dedicated document that owns its detailed rules. | open |
| R008-F4 | minor | Remove the command catalogue from the core skill. Give the agent the command to run and let the CLI explain usage and next steps through help, results and errors. | open |
| R008-F5 | major | Split `canon.py` into modules, publish the CLI as a Python package and let it declare third-party runtime dependencies. | open |
| R008-F6 | minor | Keep Reading docs short. Point the agent from each reading question to the document, section or query that answers it. | open |
| R008-F7 | minor | Does document maintenance need a separate manual `canon-sync` skill? The maintainer does not recall invoking it. | open |
| R008-F8 | major | The maintainer proposes an optional `canon-trace` skill and mechanical activation so ordinary sessions can skip trace-specific checks and instructions. | open |
| R008-F9 | minor | Move review evidence and the reviewer configuration example to the skills that use them. | open |
| R008-F10 | major | The workflow reference has grown into another long entry point. Keep the next decision visible and put detailed procedures at the phase that needs them. [Section-by-section assessment and CLI proposals](R008/workflow.md) | open |
| R008-F11 | minor | Keep the writing guide useful as it grows. Its flat list mixes general editorial judgment with instructions for particular kinds of content. | open |
| R008-F12 | minor | Give concurrent work a dedicated reference that an agent can reach before a shared-checkout write or a partial commit. | open |
| R008-F13 | minor | List document types by purpose in the core skill. The maintainer proposes one format reference for per-type structure, frontmatter and embedded source. | open |
| R008-F14 | major | Agents still transcribe verified review results and user decisions, maintain structured rows and reconstruct information already available to the CLI. Some documented formats also receive only partial validation. [Current coverage and suggested priorities](R008/cli-coverage.md) | open |
| R008-F15 | major | Keep the first-round independence rules visible in `canon-blind-review`. Open recovery and later-round instructions at their triggers, and let the CLI prepare and check the review records. [Section-by-section blind-review assessment](R008/blind-review.md) | open |
| R008-F16 | major | The maintainer wants to finish the simplification before 1.0 and is weighing a fresh repository against refactoring this one. [Repository choice](#r008-f16-repository-choice) | open |

### R008-F3 Core skill structure

The maintainer proposed four sections in the order `Tool` → `Doc Type` → `Doc Layout` → `Read Docs`. The review recommendation is `Tool` → `Reading docs` → `Doc types` → `Doc layout` for agents entering an existing project. An agent asked to fix a file can find the governing design straight away. Choosing a document type and a home for it matters when the task calls for writing. The order is open.

Use the introduction to state Canon's purpose and point an agent starting a change to the workflow's tier selection. The Tool and Reading docs drafts follow. Give each document type one line on its purpose, including that designs govern behavior and plans track a change. Limit Doc layout to where project and module documents, attachments and archives live. [Document types](../../skills/governance/canon/doc-types.md)

Move the tier definitions to the start of the workflow, which currently directs agents back to the core skill. [Change flows](../../skills/governance/canon/workflow.md#flows)

Distribute the seven bullets under Rules. Keep the principle that each standard has one owning design in the introduction. Put stable document IDs and document or section link syntax in the format reference. Let `new` assign the ID, `rename` and `archive` preserve it, and `check` report leftover template guidance. The review gate owns the requirement to review the current revision. Put post-merge checks and collision repair at the merge or rebase step, where `renumber` can report ambiguous references for the agent to resolve. [Current Rules](../../skills/governance/canon/SKILL.md#rules)

### R008-F4 Tool section of the core skill

The maintainer expects agents to encounter the core skill frequently because its trigger includes projects whose `AGENTS.md` declares Canon. Its Tool section includes installation instructions and repeats options already explained by CLI help, such as `check --staged`. [Current Tool section](../../skills/governance/canon/SKILL.md#tool)

The proposed Tool text uses the standalone `canon` command discussed in R008-F5. The proposed `init.md` owns the installation steps and any prompts to the user when the CLI is missing.

```markdown
## Tool

Canon provides a CLI to enforce all mechanical rules of the workflow. Each workflow skill names the commands to run at the steps that use them. If the CLI is missing, follow the [setup instructions](init.md).

Use `canon --help` to list commands and their descriptions. Use `canon <command> --help` for a command's usage and options.
```

### R008-F6 Reading docs section of the core skill

The draft uses Canon's reserved project overview ID, D000. [D002§project-overview-d000: project overview](../designs/D002-overview-and-as-built.md#project-overview-d000)

```markdown
## Reading docs

D000 is the project overview. It describes capabilities, module boundaries and dependencies, and defines shared terms in its glossary.

- `canon which <file>` lists the designs that govern a file.
- `canon show ID` prints a document's frontmatter and section outline. `canon show ID#slug` prints the selected section.
- `canon show D00X#known-issues` shows a design's outstanding issues or reports that it has none.
- `canon find <words>` searches by topic. Consult `docs/archived/` only when researching history, using `canon find --archived <words>` to include it in a search.
```

### R008-F5 Standalone CLI package and runtime dependencies

`canon.py` grew from 1,715 lines in `v0.1.0` to 6,325 at `d8b223a`. The skill ships the CLI as one Python file using only the standard library. [D000§dependencies: runtime dependencies](../designs/D000-project-overview.md#dependencies)

The maintainer proposes having the agent install the separately released package during `canon-init` using `uv` or a project virtual environment. Packaging would let the CLI declare dependencies such as `cyclopts` and `pydantic` when they improve its capabilities. An open design question is how a fresh checkout, a linked worktree and CI would obtain the CLI version that matches the project's pinned skills. [D004§install: project installation](../designs/D004-project-setup.md#install)

### R008-F16 Repository choice

The review recommends developing 1.0 on a branch of `BigTailFox/skills`. Projects already pin releases from this repository in `skills-lock.json`. A Python CLI package can ship from the same tree, so a command, the skill that calls it and the regression tests can change together. A separate CLI repository would be worth revisiting if other tools start using the CLI and need a different release schedule. [D004§install: installation and pinning](../designs/D004-project-setup.md#install)

Start with a one-page account of a routine fix and an L2 design. Show what the agent decides, what the CLI checks, how the reviewers work independently and where the user approves. Use that account to choose which existing rules and regression cases to carry forward. Before 1.0, try both a fresh installation and an upgrade of a project pinned to `v0.9.4` with existing document IDs and links to resolve.

### R008-F7 Role of canon-sync

`canon-sync` has three uses. It can run the ordinary docs step on demand for uncommitted work or a branch and leave the commit to the user. After a merge or rebase, it checks against the target and handles document ID collisions. Its audit mode checks for a newer release, investigates unchecked commits, revisits known issues and idle documents, repairs links from D000 and can commit corrections. Normal changes already include the docs step. [Manual skill](../../skills/governance/canon-sync/SKILL.md) · [Change flows](../../skills/governance/canon/workflow.md#flows)

At `0fefb31`, `canon.py audit` flagged six commits to check against D005 and three against D009. An agent still needs to compare those commits with the designs. Three commits in the same history carry a `Reconciled:` trailer. The core maintenance workflow also writes that trailer, and Canon trace has no `canon-sync` unit, so the frequency of manual invocation is unknown. [D002§unchecked-commits-in-audit: reconciliation](../designs/D002-overview-and-as-built.md#unchecked-commits-in-audit) · [D001§units: traced units](../designs/D001-skill-telemetry.md#units)

The review recommendation is to retire the standalone skill. Keep the on-demand docs step and its suggested commit message, leave collision handling in the merge instructions, and have the read-only audit point to the maintenance procedure when a finding needs judgment. Release discovery belongs with the upgrade flow in `canon-init`. [Maintenance](../../skills/governance/canon/workflow.md#maintenance) · [Upgrade](../../skills/governance/canon-init/SKILL.md#upgrade)

### Core skill reference files

At `0fefb31`, `canon/SKILL.md` has seven companion Markdown files. The maintainer values `doc-types.md`, `as-built.md`, writing guidance and tracing. The proposed homes below follow the action that needs each reference.

- The per-type material in `doc-types.md` would become part of `doc-formats.md` under the maintainer's proposal. [Document formats](#r008-f13-document-formats)
- `as-built.md` belongs in `canon`. Read it when adopting existing designs, documenting existing behavior on request, or preparing to change behavior that has no spec.
- `workflow.md` can be a short guide to tiers, required decisions and the next phase. At the measured commit, Review gate and Subagents account for 3,464 of its 5,205 words. Put reviewer dispatch and confirmation with blind review, worker instructions with implementation, and link to reconciliation when a change closes.
- `writing.md` can keep shared judgments such as where a fact belongs and what evidence supports a claim. Link situational advice where it applies, such as when adding a diagram. Give mechanically checkable headings and labels to templates and the CLI. [D006§writing-rules: writing rules](../designs/D006-doc-model.md#writing-rules)
- `review-evidence.md` serves two readers. Put round inputs, report coverage, confirmations and handoffs with `canon-blind-review`. Keep the shared record format and its validation in the CLI. Optional tracing can reuse the verified record and explain its own archive and replay. Coverage checks and review snapshots still serve the review when tracing is off. [D007§checking-required-review-coverage: review coverage](../designs/D007-change-tiers.md#checking-required-review-coverage) · [D003§review-snapshots: snapshots](../designs/D003-subagents.md#review-snapshots)
- `reviewer-example.md` can live with `canon-blind-review`, which consumes the machine-local configuration. Point to that skill from `canon-init` when configuring a reviewer. A review reads the filled configuration.
- `trace.md` can move to an optional `canon-trace` skill for interpreting records, recovery and history. The CLI can read the effective switch and collect events.

### R008-F8 Trace activation

The first `trace start` in a traced workflow checks the machine switch and checkout opt-out. A returned unit ID leads the agent to `trace.md`. The core skill still carries first-call instructions and each instrumented skill issues its first call even when tracing is off. [D001§call-sites: callers](../designs/D001-skill-telemetry.md#call-sites) · [D001§budgets: off-path cost](../designs/D001-skill-telemetry.md#budgets)

Let the CLI check the switch as part of an operation the workflow already performs, such as `review start`. With tracing off, the agent needs no trace-only command or reference. With it on, record the event and point to `canon-trace` when interpretation or recovery needs the agent. Design, plan, handoff and worker-slice boundaries need an observable CLI or host event before their explicit calls can be retired. An explicit history query should still work after recording is turned off. [D001§switch-and-storage: effective switch](../designs/D001-skill-telemetry.md#switch-and-storage)

### R008-F12 Concurrent work

At `0fefb31`, Rules, Concurrent work, Frontmatter and Embedded source together take 1,629 of the 4,382 whitespace-separated words in `canon/SKILL.md`. Concurrent work accounts for 872. Move its worktree, staging, scoped checks and handoff procedures to `concurrent-work.md`. Link to it before the first edit when another session may share the checkout, or before staging a partial commit. Point the generated `AGENTS.md` instruction and the docs step to the same reference. Both currently name the section in the core skill. [Concurrent work](../../skills/governance/canon/SKILL.md#concurrent-work) · [Project instructions](../../AGENTS.md#docs) · [Docs step](../../skills/governance/canon/workflow.md#docs-step)

### R008-F13 Document formats

Give concept (C), design (D), plan (P), review (R), experiment (E) and investigation (I) one line each in `SKILL.md` with their purpose and a direct link to their section of the proposed `doc-formats.md`. D000 is a design and guides are unnumbered. A plan author could run `new P <slug> --from D00X` and open the Plans section. [Current type list](../../skills/governance/canon/SKILL.md#doc-types)

- **Common conventions.** Explain document identity, file and section references, and shared frontmatter fields once. Describe the meaning of `reviewed`, `approved` and `implemented` where they apply. The workflow owns who can advance them and when. [D006§frontmatter: field meanings](../designs/D006-doc-model.md#frontmatter)
- **By type.** Give each type a stable heading for its own fields, required sections and status meanings. The current frontmatter example mixes design-only `owns` with plan-only `based_on`. Let `new` generate the template for the chosen type and `check` validate the document. Keep the known-issue row format here. The review step decides where a deferred finding belongs. Update links to the affected sections when moving the material. [Current per-type reference](../../skills/governance/canon/doc-types.md)
- **Embedded source.** Keep one optional section with a minimal marker example for a file or named region. `embed` refreshes the generated content and `check` detects stale blocks. A source editor can find affected documents with `embed --source FILE --list`. [D011§markers-and-sources: markers](../designs/D011-embedded-source.md#markers-and-sources) · [D011§generating-and-checking: CLI behavior](../designs/D011-embedded-source.md#generating-and-checking)
