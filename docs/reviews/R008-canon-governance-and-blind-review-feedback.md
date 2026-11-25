---
status: open
created: 2026-11-25
updated: 2026-11-25
revision: 1
modules: [canon]
summary: Maintainer feedback on agent discretion, cumulative workflow changes, the scope of the core skill and self-describing CLI commands.
refs: [D007]
---

# R008: Maintainer feedback on Canon governance and blind review

## Scope

The maintainer wants to understand how much rereading it takes to regain a clear picture of Canon. This usability review starts with `canon`, `canon-init`, `canon-sync` and `canon-blind-review` at `bd5c4a9`. The maintainer deferred the execution skills ported from `mattpocock/skills`. The first comments concern the shared workflow and the core `canon` entry point.

## Findings

| ID | Severity | Finding | Disposition |
|----|----------|---------|-------------|
| R008-F1 | major | Assess whether accumulated workflow rules get in the way of an agent exercising judgment on routine tasks, and which rules are worth simplifying. | open |
| R008-F2 | major | After a series of small fixes, the maintainer wants to see how the overall workflow compares with their original intent, especially what an agent can decide and what comes back to them. [D007§change-tiers: change tiers](../designs/D007-change-tiers.md#change-tiers) | open |
| R008-F3 | major | The core skill reads like a general introduction. Keep frequently needed guidance at the entry point and surface initialization details when setting up a project. | open |
| R008-F4 | minor | Remove the command catalogue from the core skill. Give the agent the command to run and let the CLI explain usage and next steps through help, results and errors. | open |

The maintainer expects agents to encounter the core skill frequently because its trigger includes projects whose `AGENTS.md` declares Canon. Its Tool section opens with installation instructions and then describes individual commands. For example, both the command table and `canon.py check -h` explain how to check staged changes. [Core skill and command table](../../skills/governance/canon/SKILL.md#tool)
