# skills

Personal agent skills for long-running software projects, built around **canon**: a documentation system that lives in the repository and carries designs, plans and decisions from one session, and one model, to the next. The skills follow the [Agent Skills specification](https://agentskills.io) and install into Cursor, Claude Code, Codex and other agents with the [`skills`](https://github.com/vercel-labs/skills) CLI.

## Install

The skills refer to each other by name, so install all of them. `-g` installs at user level, for every project:

```bash
npx skills add <git-url> -g                                     # pick skills and agents interactively
npx skills add <git-url> -g -s '*' -a cursor -a claude-code -y  # every skill, for the named agents
npx skills update -g                                            # pull the latest version
npx skills ls -g                                                # list installed skills
npx skills remove canon-teach -g                                # remove one skill
```

To try unpushed changes, install from the local path instead. That installs a copy, which `npx skills update` does not track, so rerun the same `add` after each change:

```bash
npx skills add ~/my/skills -g -s '*' -a cursor -y
```

Then run `/canon-init` in a project. It sets up `docs/`, migrates the project's existing docs, and sets up this machine's cross-family reviewer.

## How canon works

Canon keeps a project's knowledge in numbered docs under `docs/`: concepts (C), designs (D), plans (P), reviews (R), experiments (E) and investigations (I). Designs are the long-lived authority on their topics and name the code they govern; a plan carries one change. Every change gets a tier, and the tier sets the flow:

| Tier | When | Flow |
|---|---|---|
| L0 | No spec changes: a bug fix that restores specified behavior, a refactor, a dependency bump, test or tooling work | implement → code review → docs step |
| L1 | Specs change or grow inside one existing design, within one module | revise the design → review gate → plan if needed → implement → code review → docs step |
| L2 | A new topic or module, a cross-module interface or architecture change, a rewrite of a design's goals, or whenever you ask | design → review gate → your approval → plan → review gate → your approval → implement → code review → docs step |

Design, plan and implementation are separate phases, started with `/canon-design`, `/canon-plan` and `/canon-implement`. Each can run in a fresh session because the docs carry the state, and each ends by giving you the command for the next one; for L2, running it is your approval. Along the way:

- **Review gate.** A design or plan revision is accepted only after a blind review by fresh subagents that see a prompt naming files in the repository and nothing of the conversation. A same-model reviewer always reviews; L2 adds a cross-family reviewer, a model from another family.
- **Implementation.** Each plan slice goes to a fresh worker subagent that builds it test-first. The main session verifies the slice, updates the plan and commits; a slice whose worker gets stuck is paused for you to decide.
- **Code review.** Every finished change, L0 included, gets a Spec reviewer (against its designs and plan) and a Standards reviewer (against the project's stated standards) as parallel subagents, so the session that wrote the code never reviews it. L2 adds the cross-family reviewer.
- **Docs step.** Before the final commit, designs absorb the details the code settled, finished plans and reviews are archived, and the commit names the designs it was checked against in a `Refs:` trailer, which lets `canon.py audit` flag code commits nobody checked against their design.

Workers and reviewers inherit the session's model and reasoning effort, so the session you start sets both; start a risky implementation at high effort. The exception is the cross-family reviewer, whose tool, model and effort are set per machine in `.canon/canon-blind-review/reviewer.md`, which `/canon-init` writes after a test run. Without that file, the review falls back to a prompt you run in another tool.

## Skills

Auto skills load when the context calls for them. Manual skills run only as commands: `/canon-init` in Cursor and Claude Code, `$canon-init` in Codex.

### governance

| Skill | Summary | Trigger |
|---|---|---|
| `canon` | The documentation system: doc types, frontmatter, references, lifecycle and archiving, the change tiers, the review gate, how subagents launch, and `canon.py`, which creates, checks, queries and archives docs. | Auto |
| `canon-init` | Sets up canon in a repository or monorepo module, migrates existing docs (design notes, ADRs, RFCs, plans, postmortems, benchmarks), sets up the cross-family reviewer, and upgrades the project's `canon.py`. Rerun it after a fresh clone to set up the reviewer alone. | Manual |
| `canon-sync` | Keeps docs in step with the code: runs the docs step after a change, repairs docs after a merge or rebase, and audits doc health (designs with unchecked code commits, idle docs, reviews that are due). | Manual |

### execution

| Skill | Summary | Trigger |
|---|---|---|
| `canon-design` | Writes or revises a design (or a concept, while the idea is still rough) by interviewing you one decision at a time, in the glossary's terms; then passes the review gate and gives you the next command. | Manual |
| `canon-plan` | Turns an accepted design into dependency-ordered vertical slices, each with seams and test criteria, and marks risky ones (complex logic, concurrency, performance, security, data migration) with `Risk:`; settles open points with you, passes the review gate and gives you the implementation command. | Manual |
| `canon-implement` | Implements an accepted plan, an L1 design revision or an L0 change. A fresh worker builds each slice test-first; the main session verifies and commits each slice and pauses stuck ones for you, then runs the code review and the docs step. | Manual |
| `canon-code-review` | Reviews one finished change (uncommitted work, untracked files or a diff from a base) on two axes, each by a fresh subagent: Spec against its designs and plan, Standards against the project's stated standards and a smell baseline. L2 adds the cross-family reviewer; findings deferred to later work go into an R doc. | Auto |
| `canon-blind-review` | Runs reviewers that see only a self-contained prompt about files in the repository: a same-model subagent, and a cross-family reviewer run as this machine's reviewer file says, with a manual fallback. The reviewers confirm the fixes to their findings. Serves the review gate and any independent review. | Auto |
| `canon-review` | Reviews a module or the whole repository from the angles you pick (architecture, performance, security, functionality, usability), one parallel subagent per angle. Findings go into an R doc, with an HTML report on request, and each gets your decision: fix it, move it into a design, plan, investigation or backlog concept, or decline it with a reason. | Manual |
| `canon-tdd` | Test-driven development in red-green-refactor cycles at the seams a plan slice or design spec names, testing behavior through public interfaces. Done when the test criteria pass and nothing that was green turned red. | Auto |
| `canon-grill` | Settles open decisions: looks up what it can, follows what the designs already say, decides the obvious, hands evidence questions to a prototype or research, and asks you the rest in rounds with recommended answers, writing each answer into its doc. | Auto |
| `canon-prototype` | Builds a throwaway prototype to answer a design or logic question that reading and reasoning cannot settle: a clickable single-file demo of a state model, switchable UI variants on a real page, or a feasibility or speed spike. The question, verdict and prototype are recorded as an E doc. | Auto |
| `canon-research` | Answers questions from primary sources (official docs, specs, source code). Quick facts get a direct answer with links; findings that back a design decision are researched in a background subagent and recorded with citations in an E doc. | Auto |
| `canon-investigate` | Diagnoses hard bugs and performance regressions: a feedback loop that reproduces the failure, falsifiable hypotheses, instrumentation, then a fix with a regression test, all recorded in an I doc that survives across sessions. A bug with a plain cause is fixed directly as L0. | Auto |
| `canon-codebase-design` | Shared vocabulary and principles for deep modules (module, interface, depth, seam, adapter), deepening a module by its dependency category, and designing an interface twice with parallel subagents. The design, TDD and review skills build on it. | Auto |
| `canon-handoff` | Hands the current work to a fresh agent: durable state goes into canon docs, the rest into a short handoff file under `.canon/canon-handoff/` that says where to resume and which skills to use. | Manual |
| `canon-teach` | Teaches a topic: one explanation for a single question, or a course over several sessions with a teaching workspace (goals, resources, lessons, cheat sheet, learning log), kept under `.canon/canon-teach/` inside a project. | Manual |
| `canon-agent-writing` | Reference for writing docs that agents read (skills, `AGENTS.md`, `CLAUDE.md` and docs reached through pointers): context pointers, progressive disclosure, completion criteria, pruning, skill frontmatter and each host's invocation switches. | Manual |

## Repository layout

```
.
├── skills/
│   ├── governance/         # build and maintain the documentation system
│   │   └── <skill-name>/
│   └── execution/          # do development work through it
│       └── <skill-name>/
│           ├── SKILL.md            # required: frontmatter and instructions
│           ├── *.md                # optional: reference material linked from SKILL.md
│           ├── scripts/            # optional: scripts the skill runs or points to
│           ├── agents/openai.yaml  # manual skills: keeps Codex from invoking them implicitly
│           └── LICENSE, NOTICE     # ported skills: upstream license and provenance
├── scripts/
│   └── validate.py         # checks skills, links, the Skills tables and CANON_VERSION, then runs tests/
└── tests/
    └── test_canon.py       # regression tests for canon.py
```

`npx skills` discovers skills at `skills/<category>/<skill-name>/SKILL.md`, and would treat a `SKILL.md` anywhere else as an installable skill too, so keep templates and examples under other names. The two categories:

- **governance** builds and maintains the documentation system that carries a project across sessions and models.
- **execution** does development work (clarifying requirements, TDD, debugging, reviewing) and reads and writes docs only through that system. Most of it is adapted from [mattpocock/skills](https://github.com/mattpocock/skills) (MIT), with the upstream doc conventions replaced by canon's; each ported skill keeps the upstream `LICENSE` and a `NOTICE`.

## Adding a skill

```bash
cd skills/execution && npx skills init canon-my-task && cd -
```

Complete the frontmatter as [AGENTS.md](AGENTS.md) describes: `name` equals the directory name, and `description` leads with the triggers for an auto skill or is a one-line summary for a manual one. A manual skill also gets `disable-model-invocation: true` and `agents/openai.yaml`. Add a row to the Skills tables above, then check:

```bash
python3 scripts/validate.py    # structure, frontmatter, links, Skills tables, CANON_VERSION, tests
npx skills add . --list        # the CLI discovers the skill
```

## Host verification

After installing on a new host, after a major host upgrade, or after changing descriptions, invocation switches or how reviewers launch, run these checks in Cursor, Claude Code and Codex:

| Check | Do | Expect |
|---|---|---|
| Discovery | Open the host's skill list (`/skills` in Codex) | All 18 skills are listed, and no auto skill's triggers are cut off |
| Manual invocation | Run `/canon-sync` (`$canon-sync` in Codex) | The skill loads and follows its steps |
| Manual skills stay manual | In a new session, say "sync the docs" without naming a skill | `canon-sync` does not load |
| Implicit invocation | In a new session, say "this test fails intermittently, find out why" | `canon-investigate` loads |
| Reviewer setup | Run `/canon-init` in a new project | It asks for the cross-family reviewer's tool, model and effort, test-runs it, and writes `.canon/canon-blind-review/reviewer.md` |
| Subagents | Run the review gate on an L2 design | The same-model reviewer is a new subagent, the cross-family reviewer runs as the reviewer file says, and both get only the reviewer prompt. Confirmation resumes the same-model reviewer and reruns the cross-family one with its first-round findings |
| Fallback | Run an L2 review gate on a machine without the reviewer file | One line gives the reason and suggests `/canon-init`, then a reviewer prompt to copy into another tool |
| Workers per slice | Implement a plan with `/canon-implement` | Each slice gets a new worker on the session's model and effort; the main session updates the plan and commits, and a stuck worker's slice is paused and reported at the end |

In Cursor, subagents come from the Task tool, which runs them on the session's model by default. The reasoning effort is part of the model name, and a subagent can use another model only when the user asks for it, from a fixed list. Canon's workers and same-model reviewers keep the default, so they need no setup in Cursor. For a GPT cross-family reviewer, use the codex CLI rather than the Task tool, since the list offers few GPT models and fixes their efforts; codex has to run outside Cursor's sandbox because it writes to `~/.codex`. A reviewer from another family can be a Task subagent on a model from the list.
