---
name: canon
description: Canon project documentation system. Use whenever reading, creating, updating, referencing or archiving docs under docs/, when choosing a change's tier (L0, L1, L2) or whether it needs a design or plan, or when AGENTS.md says the project follows canon. Defines numbered concepts, designs, plans, reviews, experiments and investigations for long-running, multi-session, multi-model work, with frontmatter, lifecycle and blind-review gates, and ships canon.py to create, check, query and archive them.
---

# Canon

Canon keeps a project's engineering knowledge in numbered docs under `docs/`, with exactly one authoritative place for each fact. `canon.py` enforces every mechanical rule: follow its output instead of re-checking rules by hand.

## Tool

Execute `canon.py`; do not read it. Use the project's copy at the path named in `AGENTS.md`, otherwise [scripts/canon.py](scripts/canon.py) from this skill. It works from any directory inside the repo.

| Command | Purpose |
|---|---|
| `check [--fix] [--base REF]` | Validate all docs. `--fix` applies mechanical fixes (`refs`, `updated`, indexes, `implemented` of an active design never revised, and deleting an `as_built` left on a reviewed revision). `--base origin/main` also checks the branch against that ref: deleted docs, id collisions, revisions pending review and unfinished docs fail. |
| `new TYPE SLUG [--title T] [--from D00X] [--parent D00X] [--root DIR]` | Create a doc from its template with the next free id. `--from` links a plan to its design; `--parent` creates a sub-design. |
| `archive ID STATUS` | Set a terminal status, move the doc to `archived/`, rewrite every link to it. Refuses D000. |
| `rename ID SLUG` | Change a doc's file slug and rewrite every link to it. |
| `renumber ID\|PATH --base REF` | Give a doc a new id, or a sub-design a new letter, and rewrite the links and references to it. Only for collisions reported by `check`; REF is the branch merged or rebased onto. |
| `index` | Regenerate the indexes in `docs/README.md` and `docs/archived/README.md`. |
| `show ID` / `show ID#slug` | Print a doc's frontmatter and outline, or one section. |
| `find WORDS [--archived]` | Search ids, titles, summaries, owned topics, modules and headings. |
| `which FILE...` | List the designs whose `paths` govern the files, or `doc` for a [project doc](#layout) that no `paths` entry names exactly. |
| `affected [--base REF]` | Designs and plans governing the uncommitted (or branch) changes. |
| `audit` | Designs with code commits since the design last changed that no `Refs:` trailer names, known issues oldest first, idle open docs other than concepts, due reviews, source areas under D000's module Paths that no design covers, ranked by commits in the last 90 days, and designs D000 does not reach by following `refs` from design to design. |
| `snapshot` | Record the work tree, untracked files included, and print the snapshot commit, for a review's confirmation diff (the `canon-blind-review` skill). |
| `init`, `adopt` | Project setup, upgrades and migration; the user runs them through the `canon-init` skill. |

In `trace` calls, `<skill>` is the path of the followed `SKILL.md`'s directory (a gate's is `canon-blind-review`'s, else `canon`'s), `<model>` your model id as the host names it, and `<parent>` the invoking workflow's open unit id, if any. Unless a skill's first `start` prints `trace <id>`, skip its other trace calls; else follow [trace.md](trace.md), using that `<id>`.

## Reading docs

- Start at D000, the project overview in the repo root's `docs/` ([its rules](doc-types.md#project-overview-d000)): its rows name the designs that own each capability and cross-module standard or govern each module's code, or `none`, and its Glossary defines the terms used across modules.
- When a change may alter behavior or standards a design specifies, run `which <file>` and read the governing sections with `show ID#slug` first. Read a whole doc only when you are writing it.
- Read the known issues of each design you work from (`show D00X#known-issues`; `which`, `find` and `affected` count them). An issue the work depends on is a [design problem](workflow.md#design-problems) unless the work fixes it, and the change that resolves an issue deletes its row.
- Look topics up with `find`; `docs/README.md` is the generated index.
- Skip `docs/archived/` unless researching history (`find --archived`).
- A design is the source of truth. A plan records progress and history; when they disagree, the design wins. A flaw in the design itself is a [design problem](workflow.md#design-problems).

## Layout

```text
<project>/                  any directory with AGENTS.md (the repo root is one)
├── AGENTS.md
├── README.md               the project's intro for users, if it has one
└── docs/
    ├── README.md           hand-written intro + generated index
    ├── concepts/  designs/  plans/  reviews/  experiments/  investigations/
    ├── designs/D000-project-overview.md   repo root only: the place to start
    ├── reviews/R003/       attachments of R003; every numbered doc may have one
    ├── guides/             unnumbered docs for users and operators
    ├── assets/             images and files shared by several docs or guides
    └── archived/           same categories, docs in a terminal status only
```

Temporary files of canon skills (prompts, scratch prototypes, handoffs, teaching workspaces) go in `.canon/<skill>/<topic>/` at the repo root, never in the OS temp directory or the tracked tree; `<topic>` is a short kebab-case slug. `init` adds `.canon/` to `.gitignore`; if `git check-ignore -q .canon` fails, add it yourself. Nothing in `.canon/` is a doc: anything worth keeping becomes an attachment or doc content. `.canon/canon/trace/` is not scratch: until `canon.py trace prune` it holds the only copy of its data.

Attachments of a numbered doc (data, scripts, reports, prototypes, images used only by it) live in `<category>/<ID>/` beside the doc, e.g. `designs/D003/flow.svg`; `archive` and `renumber` move them with it. Create the directory when the first attachment appears. Link large binaries instead of committing them.

The project's `README.md`, its hand-written intro for users, belongs to the doc system like `AGENTS.md` and `docs/`: it stays, and where it restates D000 or a design, they hold. A doc by its name is a file in any directory whose name up to its first `.` is, in any case, `README`, `AGENTS`, `CLAUDE`, `CHANGELOG`, `CONTRIBUTING`, `LICENSE`, `NOTICE`, `SECURITY`, `CODE_OF_CONDUCT` or `COPYING`, or starts with `LICENSE-`, and that has no extension or ends in `.md`, `.markdown`, `.rst`, `.txt`, `.adoc` or `.org`. `canon.py` takes it, and every file under a docs root, for a project doc, never for code: a design governs one only through a `paths` entry equal to its path, never through a glob or directory.

A more specific `AGENTS.md` and its `docs/` govern their subtree and override broader rules. Repo-wide and cross-module docs live in the root `docs/`; module docs live in the module's `docs/`. Ids are global across the repo: `D003` exists once, whichever `docs/` holds it.

## Doc types

File names are `<id>-<kebab-slug>.md`, e.g. `designs/D003-auth.md`. The title is the H1 `# D003: Auth and sessions`.

| Type | Purpose | Statuses (terminal ones live in `archived/`) |
|---|---|---|
| C concepts | Ideas and brainstorming; the source of future work. No spec or plan. | draft → adopted, dropped |
| D designs | Long-lived authoritative design and spec of one topic. | draft → accepted → active → superseded, retired |
| P plans | Implementation plan and log of one change. | draft → accepted → in-progress → done, abandoned |
| R reviews | Findings of a functional, performance, security, architecture or usability review. | open → closed |
| E experiments | A question answered with evidence: a run (benchmark, prototype) or research of primary sources. | planned → running → concluded |
| I investigations | Debugging and profiling. | open → resolved |

Sections and per-type rules: [doc-types.md](doc-types.md).

## Frontmatter

```yaml
---
status: active
created: 2026-03-02
updated: 2026-05-17
revision: 4
modules: [auth, gateway]
summary: Token issuing, refresh and session lifecycle.
refs: [D001, D007]
owns: [auth-token, session]          # D only
paths: [src/auth/**, src/session/]   # D only
reviewed: 4                          # D and P
reviewers: [claude-opus-high, gpt-high]
implemented: 4                       # D only
based_on: [D003@r4]                  # P only
---
```

- `modules`: modules the doc concerns; empty means the whole project of this `docs/`.
- `summary`: one line; it feeds the index and `find`.
- `refs`: ids of related docs; must include every doc linked from the body (`check --fix` adds missing ones).
- `revision`: counts semantic changes. Bump it when a goal, spec or plan changes meaning, never for wording.
- `owns`: topics this design is the single authority for, unique across non-archived designs.
- `paths`: code globs relative to the project directory; they drive `which`, `affected` and `audit`.
- `reviewed`, `reviewers`: the revision that passed the review gate and who reviewed it (`manual:<model>` for a review the user ran).
- `implemented`: the revision the code fully implements; required once a design is `active`. Below `revision`, the spec leads the code and the difference is an open plan's work, not a defect.
- `as_built`: the commit an [as-built revision](as-built.md) records, only while the revision awaits its gate.
- `based_on`: design revisions a plan was written against; `check` warns when a design moves past them.

## Rules

- The id is a doc's identity. Create docs with `new`, retire them with `archive`, change slugs with `rename`. Never delete a doc or reuse an id.
- Ids are unique on the current branch. When `check` reports a collision with another branch, renumber the doc your branch added with `renumber <path> --base <ref>`, where `<ref>` is the branch you merge or rebase onto, before or after the merge or rebase. Then fix the references it reports as kept; only you can tell which doc they mean.
- Reference a section as `[D003§token-refresh: refresh flow](../designs/D003-auth.md#token-refresh)` and a whole doc as `[D003: auth design](../designs/D003-auth.md)`. Never reference by line number.
- Each standard lives only in the design that owns its topic; everywhere else links to it.
- A design or plan revision must pass the review gate before it is accepted or implemented: `reviewed` equals `revision`. Once a design or plan has been accepted, `check` warns while a later revision is pending; `check --base` fails.
- Replace every `<!-- canon: ... -->` guidance comment with content. While a doc is unfinished (a design or plan before its review gate, any other doc before archiving), `check` only warns about guidance and an empty `summary`; `check --base` fails.
- After a merge or rebase, run `check --fix`; generated indexes merge line by line and may need regenerating.

## Workflow

Every change has a tier; state it when starting and pick the higher one when unsure.

- **L0**: changes no spec in any design: bug fixes that restore specified behavior, refactors, dependency bumps, test and tooling changes. Implement, keep docs factually true, commit.
- **L1**: changes or extends specs inside the owned topics of one existing design, within one module; or multi-step work under an existing design that needs a plan. Revise the design in place with the `canon-design` skill, pass the review gate (same-model reviewer), then implement. A [design problem](workflow.md#design-problems) is revised by the session that finds it.
- **L2**: a new topic with no owning design, a new module, a change to a cross-module interface or the architecture, a revision that rewrites an existing design's goals or core approach, or the user asks for it. Design and plan each pass the review gate (same-model and cross-family reviewers) and need the user's approval, which starting the next phase gives.

Behavior no design states is unspecified. Look for a statement with `which` for its files, `find` for its topic and D000's rows; a file `which` maps to no design, or a row reading `none`, does not settle it alone.

- **Backfill**: before a change alters or extends existing behavior no design states, an [as-built revision](as-built.md) records that behavior. It is L1, also when it creates a design or precedes an L2 change. The change then alters stated behavior and is tiered and handled like any such change: in a `canon-design` session it is the session's next revision, gated at its tier; anywhere else it is a [design problem](workflow.md#design-problems), so the user decides on the revision, which passes its gate at its tier, and an L2 revision goes through `/canon-design`.
- Where no design states the behavior, an L0 change alters nothing callers rely on: a refactor, a dependency bump, test or tooling work, or a fix for a defect no caller could rely on, such as a crash.
- New behavior with nothing existing to record is tiered by the rules above: a new topic is L2.

A commit that touches a design's `paths`, in any tier, names the designs it was checked against in a `Refs:` trailer (`affected` lists them); `audit` treats commits without one as unchecked.

Flows, the blind-review gate with its reviewer prompt, code review, how subagents launch (and the cross-family reviewer's local file), and the docs step before committing: [workflow.md](workflow.md).

## Writing

Follow [writing.md](writing.md) for every doc.
