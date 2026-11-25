---
status: open
created: 2026-11-25
updated: 2026-11-25
revision: 1
modules: [canon]
summary: Maintainer feedback on workflow changes, progressive disclosure, agent discretion, concise skills, CLI enforcement and standalone CLI packaging.
refs: [D000, D004, D007]
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

### R008-F4 Tool section of the core skill

The maintainer expects agents to encounter the core skill frequently because its trigger includes projects whose `AGENTS.md` declares Canon. Its Tool section includes installation instructions and repeats options already explained by CLI help, such as `check --staged`. [Current Tool section](../../skills/governance/canon/SKILL.md#tool)

The proposed Tool text uses the standalone `canon` command discussed in R008-F5. The proposed `init.md` owns the installation steps and any prompts to the user when the CLI is missing.

```markdown
## Tool

Canon provides a CLI to enforce all mechanical rules of the workflow. Each workflow skill names the commands to run at the steps that use them. If the CLI is missing, follow the [setup instructions](init.md).

Use `canon --help` to list commands and their descriptions. Use `canon <command> --help` for a command's usage and options.
```

### R008-F5 Standalone CLI package and runtime dependencies

`canon.py` grew from 1,715 lines in `v0.1.0` to 6,325 at `d8b223a`. The skill ships the CLI as one Python file using only the standard library. [D000§dependencies: runtime dependencies](../designs/D000-project-overview.md#dependencies)

The maintainer proposes having the agent install the separately released package during `canon-init` using `uv` or a project virtual environment. Packaging would let the CLI declare dependencies such as `cyclopts` and `pydantic` when they improve its capabilities. An open design question is how a fresh checkout, a linked worktree and CI would obtain the CLI version that matches the project's pinned skills. [D004§install: project installation](../designs/D004-project-setup.md#install)
