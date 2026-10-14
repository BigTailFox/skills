---
name: canon
description: Canon is the project documentation system for long-running, multi-session, multi-model development. It defines numbered concepts, designs, plans, reviews, experiments and investigations under docs/, their frontmatter, references, lifecycle and archiving, the L0/L1/L2 change tiers with blind-review gates, and ships canon.py to create, check, query and archive docs. Use whenever reading, creating, updating, referencing, reviewing or archiving project docs, when designing or planning a change, when deciding whether a change needs a design or plan, or when AGENTS.md says the project follows canon.
---

# Canon

Canon keeps a project's engineering knowledge in numbered docs under `docs/`, with exactly one authoritative place for each fact. `canon.py` enforces every mechanical rule: follow its output instead of re-checking rules by hand.

## Tool

Execute `canon.py`; do not read it. Use the project's copy at the path named in `AGENTS.md`, otherwise [scripts/canon.py](scripts/canon.py) from this skill. It works from any directory inside the repo.

| Command | Purpose |
|---|---|
| `check [--fix] [--base REF]` | Validate all docs. `--fix` applies mechanical fixes (`refs`, `updated`, indexes). `--base origin/main` also checks the branch against that ref: deleted docs and id collisions. |
| `new TYPE SLUG [--title T] [--from D00X] [--parent D00X] [--root DIR]` | Create a doc from its template with the next free id. `--from` links a plan to its design; `--parent` creates a sub-design. |
| `archive ID STATUS` | Set a terminal status, move the doc to `archived/`, rewrite every link to it. |
| `rename ID SLUG` | Change a doc's file slug and rewrite every link to it. |
| `renumber ID\|PATH [--base REF]` | Give a doc a new id and rewrite every link to it. Only for collisions reported by `check`. |
| `index` | Regenerate the indexes in `docs/README.md` and `docs/archived/README.md`. |
| `show ID` / `show ID#slug` | Print a doc's frontmatter and outline, or one section. |
| `find WORDS [--archived]` | Search ids, titles, summaries, owned topics, modules and headings. |
| `which FILE...` | List the designs whose `paths` govern the files. |
| `affected [--base REF]` | Designs and plans governing the uncommitted (or branch) changes. |
| `audit` | Designs with code commits since their last update, idle open docs, due reviews. |
| `init`, `adopt` | Project setup, upgrades and migration; the user runs them through the `canon-init` skill. |

## Reading docs

- Before editing code, run `which <file>` and read the governing design sections with `show ID#slug`. Read a whole doc only when you are writing it.
- Look topics up with `find`; `docs/README.md` is the generated index.
- Skip `docs/archived/` unless researching history (`find --archived`).
- A design is the source of truth. A plan records progress and history; when they disagree, the design wins.

## Layout

```text
<project>/                  any directory with AGENTS.md (the repo root is one)
├── AGENTS.md
└── docs/
    ├── README.md           hand-written intro + generated index
    ├── concepts/  designs/  plans/  reviews/  experiments/  investigations/
    ├── reviews/R003/       attachments of R003; every numbered doc may have one
    ├── guides/             unnumbered docs for users and operators
    ├── assets/             images and files shared by several docs or guides
    └── archived/           same categories, docs in a terminal status only
```

`.canon/` at the repo root holds local working state of canon skills, such as teaching workspaces. `init` adds it to `.gitignore`; nothing in it is a doc.

Attachments of a numbered doc (data, scripts, reports, prototypes, images used only by it) live in `<category>/<ID>/` beside the doc, e.g. `designs/D003/flow.svg`; `archive` and `renumber` move them with it. Create the directory when the first attachment appears. Link large binaries instead of committing them.

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
- `based_on`: design revisions a plan was written against; `check` warns when a design moves past them.

## Rules

- The id is a doc's identity. Create docs with `new`, retire them with `archive`, change slugs with `rename`. Never delete a doc or reuse an id.
- Ids are unique on the current branch. When `check` reports a collision with another branch, renumber the doc your branch added: `renumber <path> --base <ref>` before rebasing, `renumber <path>` after.
- Reference a section as `[D003§token-refresh: refresh flow](../designs/D003-auth.md#token-refresh)` and a whole doc as `[D003: auth design](../designs/D003-auth.md)`. Never reference by line number.
- Each standard lives only in the design that owns its topic; everywhere else links to it.
- A design or plan revision must pass the review gate before it is accepted: `reviewed` equals `revision`.
- Replace every `<!-- canon: ... -->` guidance comment with content.
- After a merge or rebase, run `check --fix`; generated indexes merge line by line and may need regenerating.

## Workflow

Every change has a tier; state it when starting and pick the higher one when unsure.

- **L0**: changes no spec. Implement, keep docs factually true, commit.
- **L1**: changes specs inside one existing design's owned topics within one module, or needs a plan under an existing design. Revise the design in place, pass the review gate (A1), then implement.
- **L2**: a new topic, module, cross-module interface or architecture change. Design and plan each pass the review gate (A1 and A2) and need the user's explicit approval.

Tier criteria, flows, the blind-review gate with its reviewer prompt, code review, and the docs step before committing: [workflow.md](workflow.md).

## Writing

Follow [writing.md](writing.md) for every doc.
