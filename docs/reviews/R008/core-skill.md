# Core skill, companion skills and references

## R008-F3 Core skill structure

The maintainer proposed four sections in the order `Tool` → `Doc Type` → `Doc Layout` → `Read Docs`. The review recommendation is `Tool` → `Reading docs` → `Doc types` → `Doc layout` for agents entering an existing project. An agent asked to fix a file can find the governing design straight away. Choosing a document type and a home for it matters when the task calls for writing. The order is open.

Use the introduction to state Canon's purpose and point an agent starting a change to the workflow's tier selection. Give each document type one line on its purpose, including that designs govern behavior and plans track a change. Limit Doc layout to where project and module documents, attachments and archives live. [Document types](../../../skills/governance/canon/doc-types.md) · [Tool draft](#r008-f4-tool-section-of-the-core-skill) · [Reading docs draft](#r008-f6-reading-docs-section-of-the-core-skill)

Move the tier definitions to the start of the workflow, which currently directs agents back to the core skill. [Change flows](../../../skills/governance/canon/workflow.md#flows)

Distribute the seven bullets under Rules. Keep the principle that each standard has one owning design in the introduction. Put stable document IDs and document or section link syntax in the format reference. Let `new` assign the ID, `rename` and `archive` preserve it, and `check` report leftover template guidance. The review gate owns the requirement to review the current revision. Put post-merge checks and collision repair at the merge or rebase step, where `renumber` can report ambiguous references for the agent to resolve. [Current Rules](../../../skills/governance/canon/SKILL.md#rules)

## Core skill reference files

At `0fefb31`, `canon/SKILL.md` has seven companion Markdown files. The maintainer values `doc-types.md`, `as-built.md`, writing guidance and tracing. The proposed homes below follow the action that needs each reference.

- `workflow.md` can be a short guide to tiers, required decisions and the next phase. At the measured commit, Review gate and Subagents account for 3,464 of its 5,205 words. Put reviewer dispatch and confirmation with blind review, worker instructions with implementation, and link to reconciliation when a change closes. [Workflow section assessment](workflow.md#workflow-section-assessment)
- The per-type material in `doc-types.md` would become part of `doc-formats.md` under the maintainer's proposal. [Document formats](#r008-f13-document-formats)
- `as-built.md` belongs in `canon`. Read it when adopting existing designs, documenting existing behavior on request, or preparing to change behavior that has no spec.
- `trace.md` would move to the proposed optional `canon-trace` skill. [Trace activation](#r008-f8-trace-activation)
- `review-evidence.md` and `reviewer-example.md` serve the blind review skill. [Evidence and reviewer configuration](blind-review.md#review-evidence-and-reviewer-configuration)
- `writing.md` holds shared editorial guidance. [Writing guidance](#r008-f11-writing-guidance)

## R008-F8 Trace activation

The first `trace start` in a traced workflow checks the machine switch and checkout opt-out. A returned unit ID leads the agent to `trace.md`. The core skill still carries first-call instructions and each instrumented skill issues its first call even when tracing is off. [D001§call-sites: callers](../../designs/D001-skill-telemetry.md#call-sites) · [D001§budgets: off-path cost](../../designs/D001-skill-telemetry.md#budgets)

Let the CLI check the switch as part of an operation the workflow already performs, such as `review start`. With tracing off, the agent needs no trace-only command or reference. With it on, record the event and point to `canon-trace` when interpretation or recovery needs the agent. Design, plan, handoff and worker-slice boundaries need an observable CLI or host event before their explicit calls can be retired. An explicit history query should still work after recording is turned off. [D001§switch-and-storage: effective switch](../../designs/D001-skill-telemetry.md#switch-and-storage)

## R008-F7 Role of canon-sync

`canon-sync` has three uses. It can run the ordinary docs step on demand for uncommitted work or a branch and leave the commit to the user. After a merge or rebase, it checks against the target and handles document ID collisions. Its audit mode checks for a newer release, investigates unchecked commits, revisits known issues and idle documents, repairs links from D000 and can commit corrections. Normal changes already include the docs step. [Manual skill](../../../skills/governance/canon-sync/SKILL.md) · [Change flows](../../../skills/governance/canon/workflow.md#flows)

At `0fefb31`, `canon.py audit` flagged six commits to check against D005 and three against D009. An agent still needs to compare those commits with the designs. Three commits in the same history carry a `Reconciled:` trailer. The core maintenance workflow also writes that trailer, and Canon trace has no `canon-sync` unit, so the frequency of manual invocation is unknown. [D002§unchecked-commits-in-audit: reconciliation](../../designs/D002-overview-and-as-built.md#unchecked-commits-in-audit) · [D001§units: traced units](../../designs/D001-skill-telemetry.md#units)

The review recommendation is to retire the standalone skill. Keep the on-demand docs step and its suggested commit message, leave collision handling in the merge instructions, and have the read-only audit point to the maintenance procedure when a finding needs judgment. Release discovery belongs with the upgrade flow in `canon-init`. [Maintenance](../../../skills/governance/canon/workflow.md#maintenance) · [Upgrade](../../../skills/governance/canon-init/SKILL.md#upgrade)

## R008-F4 Tool section of the core skill

The maintainer expects agents to encounter the core skill frequently because its trigger includes projects whose `AGENTS.md` declares Canon. Its Tool section includes installation instructions and repeats options already explained by CLI help, such as `check --staged`. [Current Tool section](../../../skills/governance/canon/SKILL.md#tool)

The proposed Tool text uses the standalone `canon` command discussed in R008-F5. The proposed `init.md` owns the installation steps and any prompts to the user when the CLI is missing. [CLI packaging](cli-coverage.md#r008-f5-standalone-cli-package-and-runtime-dependencies)

```markdown
## Tool

Canon provides a CLI to enforce all mechanical rules of the workflow. Each workflow skill names the commands to run at the steps that use them. If the CLI is missing, follow the [setup instructions](init.md).

Use `canon --help` to list commands and their descriptions. Use `canon <command> --help` for a command's usage and options.
```

## R008-F6 Reading docs section of the core skill

The draft uses Canon's reserved project overview ID, D000. [D002§project-overview-d000: project overview](../../designs/D002-overview-and-as-built.md#project-overview-d000)

```markdown
## Reading docs

D000 is the project overview. It describes capabilities, module boundaries and dependencies, and defines shared terms in its glossary.

- `canon which <file>` lists the designs that govern a file.
- `canon show ID` prints a document's frontmatter and section outline. `canon show ID#slug` prints the selected section.
- `canon show D00X#known-issues` shows a design's outstanding issues or reports that it has none.
- `canon find <words>` searches by topic. Consult `docs/archived/` only when researching history, using `canon find --archived <words>` to include it in a search.
```

## R008-F13 Document formats

Give concept (C), design (D), plan (P), review (R), experiment (E) and investigation (I) one line each in `SKILL.md` with their purpose and a direct link to their section of the proposed `doc-formats.md`. D000 is a design and guides are unnumbered. A plan author could run `new P <slug> --from D00X` and open the Plans section. [Current type list](../../../skills/governance/canon/SKILL.md#doc-types)

- **Common conventions.** Explain document identity, file and section references, and shared frontmatter fields once. Describe the meaning of `reviewed`, `approved` and `implemented` where they apply. The workflow owns who can advance them and when. [D006§frontmatter: field meanings](../../designs/D006-doc-model.md#frontmatter)
- **By type.** Give each type a stable heading for its own fields, required sections and status meanings. The current frontmatter example mixes design-only `owns` with plan-only `based_on`. Let `new` generate the template for the chosen type and `check` validate the document. Keep the known-issue row format here. The review step decides where a deferred finding belongs. Update links to the affected sections when moving the material. [Current per-type reference](../../../skills/governance/canon/doc-types.md)
- **Embedded source.** Keep one optional section with a minimal marker example for a file or named region. `embed` refreshes the generated content and `check` detects stale blocks. A source editor can find affected documents with `embed --source FILE --list`. [D011§markers-and-sources: markers](../../designs/D011-embedded-source.md#markers-and-sources) · [D011§generating-and-checking: CLI behavior](../../designs/D011-embedded-source.md#generating-and-checking)

## R008-F12 Concurrent work

At `0fefb31`, Rules, Concurrent work, Frontmatter and Embedded source together take 1,629 of the 4,382 whitespace-separated words in `canon/SKILL.md`. Concurrent work accounts for 872. Move its worktree, staging, scoped checks and handoff procedures to `concurrent-work.md`. Link to it before the first edit when another session may share the checkout, or before staging a partial commit. Point the generated `AGENTS.md` instruction and the docs step to the same reference. Both currently name the section in the core skill. [Concurrent work](../../../skills/governance/canon/SKILL.md#concurrent-work) · [Project instructions](../../../AGENTS.md#docs) · [Docs step](../../../skills/governance/canon/workflow.md#docs-step)

## R008-F11 Writing guidance

`writing.md` can keep shared judgments such as where a fact belongs and what evidence supports a claim. Link situational advice where it applies, such as when adding a diagram. Give mechanically checkable headings and labels to templates and the CLI. [D006§writing-rules: writing rules](../../designs/D006-doc-model.md#writing-rules)
