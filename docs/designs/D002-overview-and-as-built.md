---
status: accepted
created: 2026-10-22
updated: 2026-10-23
revision: 2
modules: [canon]
summary: D000 project overview in every project, as-built designs that record existing code, backfill before changing unspecified behavior, and design coverage in audit.
refs: [D001]
owns: [project-overview, as-built-design, design-coverage]
paths: [skills/governance/canon/as-built.md, skills/governance/canon/scripts/canon.py, skills/governance/canon/SKILL.md, skills/governance/canon/workflow.md, skills/governance/canon/doc-types.md, skills/governance/canon-init/SKILL.md, skills/governance/canon-sync/SKILL.md, skills/execution/canon-design/SKILL.md, skills/execution/canon-implement/SKILL.md, skills/execution/canon-code-review/SKILL.md, skills/execution/canon-review/SKILL.md, skills/execution/canon-review/architecture.md]
reviewed: 2
reviewers: [claude-opus-5.5]
---

# D002: Project overview and as-built designs

## Goals

1. Every agent can start from one doc, D000, that states what the project does, how it is organized and which designs own each module, capability and cross-module standard, naming those no design owns yet.
2. An existing project adopts canon at the cost of D000 and the docs it already has: setup ends once they have passed their gates, and the next real change already runs through canon's design, implementation and review.
3. A change's tier measures the change, not the docs the project lacks: changing behavior no design states costs one L1 as-built revision more than changing stated behavior, never an L2 detour.
4. What an as-built revision adds holds for the code at the commit it records, apart from defects its known issues name, and it states intent only where evidence or the user gives it.
5. `audit` ranks the parts of the project's modules no design covers by recent commits, and coverage never fails `check`.
6. No tool or step takes a doc, such as the project's README, for code that lacks a design, and the docs step keeps what docs state in line with the change.

## Spec

### Project overview (D000)

Every repository that follows canon has `designs/D000-project-overview.md` in the `docs/` of its root, titled `# D000: Project overview`. It is a design like any other, with these rules:

- Goals state what the project is for, who uses it and what is out of scope.
- Spec holds four subsections, in this order:
  - `### Capabilities`: one row per capability the project offers its users or callers, at the grain of a feature list.

    ```markdown
    | Capability | Modules | Design |
    |---|---|---|
    | Token refresh | auth, gateway | [D003: auth](D003-auth.md) |
    | CSV export | export | none |
    ```

  - `### Modules`: one row per module. Path lists the module's directories relative to the project directory, comma-separated, each ending with `/`; `./` is the project directory.

    ```markdown
    | Module | Path | Purpose | Entry points | Design |
    |---|---|---|---|---|
    | auth | src/auth/ | Tokens and sessions | src/auth/index.ts | [D003: auth](D003-auth.md), [D005: sessions](D005-sessions.md) |
    ```

  - `### Dependencies`: the allowed dependency directions between modules.
  - `### Glossary`: terms used across modules; a term one module uses belongs to the design that owns it.

  After them, `### Standards` has one row per standard that applies across modules, such as error handling, with the design that owns it: `| Standard | Design |`. It is left out while no design owns one.
- A Design cell links every top-level design that owns the capability or standard, or that governs the module's code, or reads `none`. Rows name modules, capabilities and standards, never single docs: designs reach their sub-topics through their own links, and `docs/README.md` stays the index of every doc. Detail below the module level belongs to the module's designs.
- The tables map the project, its planned modules included while D000 is its first L2 design. The change that adds or removes a module, capability or standard, or creates, moves or archives a top-level design, updates their rows in the same commit: the docs step checks this for code changes, `canon-design` for the designs it creates, and `canon-sync` points rows at the designs `audit` reports as unreached. Rows change no meaning: no revision bump and no gate. Goals, Dependencies and Glossary are spec. Adding a module, changing the dependency directions or changing a cross-module interface is L2, as the `canon` skill's tiers state.
- `owns` includes `architecture`. `paths` lists only files that embody the architecture, such as dependency-boundary configuration and module wiring, and is usually empty.
- Only the repo root has a D000, and only `init` at the repo root creates one. In a monorepo, D000's Modules rows link each module's designs.
- In a project with code, D000 is written as an [as-built](#as-built-revisions) design. In a project without code, it is the project's first L2 design, written with the `canon-design` skill.
- The `AGENTS.md` block that `init` writes names D000 as the place to start and `docs/README.md` as the index.

`canon.py`:

- `check` errors when the repo root's `docs/` holds no non-archived D000, when another docs root holds a D000, when D000's Spec lacks one of the four subsections, and when an entry of D000's `paths` contains `*`, `?` or `[`, ends with `/`, or is a directory. It warns when a Path in the Modules table is not a directory of the project, as it warns for `paths` that match no file.
- `archive D000` is refused.
- In a Git checkout, `new`, `adopt` and `renumber` never assign an id, or a sub-design letter, that a doc file of that type has had in the history of HEAD.
- `init` at the repo root creates D000 from its template when there is none; it has no flag to skip it.
- `init` in a project with no D000 but a design that owns `architecture` moves that design to `D000-project-overview.md`, titled `D000: Project overview`, as `renumber` moves a doc: its frontmatter, body, sub-designs, attachments and known issues come along, and every link, `refs`, `based_on` and `moved` entry follows. It then appends the subsections D000 lacks at the end of `## Spec`, each with a guidance comment. The id rule above keeps the old number taken.
- `check`'s error for a deleted doc skips a deleted design that owned `architecture` at the commit it compares with, while D000 exists: once filled out, D000 differs too much from the old doc for Git to pair the two as a rename.
- `audit` lists the non-archived designs D000 does not reach. D000 reaches itself and every design named in the `refs` of a design it reaches.

### As-built revisions

An as-built revision records behavior the code already has, at one commit, and specifies no change to it. It is the first revision of a new design, or a revision that adds existing behavior to the design that owns its topic.

While it awaits its gate, its frontmatter holds `as_built: <commit>`, the commit it records. The gate builds its reviewer prompt from it, and a session that resumes the work or replays the gate ([D001§replay: replay](D001-skill-telemetry.md#replay)) finds the base there. Outside Git, and before the first commit, it reads `as_built: worktree`: the revision records the files as they are and passes its gate before any of them change. The gate removes the field when it sets `reviewed`; nothing marks the revision after that. `check` errors when `as_built` names no commit, unless it reads `worktree` outside Git or before the first commit, and when it remains on a doc whose `reviewed` equals its `revision`; `check --fix` removes it then.

It is written:

- by `canon-init`, for D000 and for adopted designs that describe existing code;
- before a change alters behavior no design states ([Backfill](#backfill));
- when the user asks for a design of existing code.

`skills/governance/canon/as-built.md` states for agents how to write one:

1. **Base**: the commit the change starts from: the commit the session started at, a plan's `Started at`, or for a code review the merge base it diffs against; HEAD when no change follows. Once the work tree or HEAD has moved past the base, read files as `git show <base>:<path>`; never record code the change already altered.
2. **Scope**: the topic the change touches, as one whole interface or capability, neither the whole module nor only the lines to change. It goes into the design whose `owns` holds the topic, else into a new design. A new design's `owns` and `paths` cover exactly what it records, `paths` listing the files that implement it and their tests; a revision adds what it records to them.
3. **Level**: what callers rely on, meaning what another module, a user or an external system can observe through an interface: results, errors, side effects, config keys and data formats, given as code. Private structure stays out.
4. **Intent**: evidence, strongest first, is tests, user-facing docs, commit messages, pull requests and issues, then the code. Intent chooses what to write and at which level; what the revision states still holds for the code at the base.
5. **Doubtful behavior**, behavior that looks unintended, goes to the user in rounds with the `canon-grill` skill, which looks every fact up itself. Intended behavior goes into the Spec. A defect puts the correct behavior in the Spec and adds a known issue with next `fix` stating what the code does instead; like a defect that code review defers, the issue does not lower `implemented`, and its fix is L0, since it restores specified behavior. Behavior the user cannot judge stays in the Spec as it is, with a known issue with next `decide`. Both issues have the source `as-built <base>`. What the change depends on is settled before the change's own revision.
6. **Decisions**: a choice that is hard to reverse and surprising without context gets a line with its source, or with `reason unknown, kept as found`.
7. **No improvements**: an idea found while reading becomes a known issue with next `fix`, `L1` or `L2`, or an Idea in the module's backlog concept.

Gate and status:

- The gate runs at L1, also before an L2 change: a same-model reviewer, a cross-family one optional.
- The reviewer prompt in the `canon` workflow's review gate gains a header line, filled from `as_built` for as-built revisions only, the first choice for a new design and for a commit:

  ```text
  As-built: {the target | what this revision adds} records {the code at {commit}, read with `git show {commit}:<path>` since the work tree may hold a later change | the files as they are} and specifies no change to it.
  ```

  For as-built revisions its Correctness item reads `against the code it records` in place of `against the current code`, its Completeness item reads `a fresh agent could change the code it governs` in place of `could implement it`, and its Assess list gains:

  ```text
  - As-built revisions only: what the revision adds holds for the code it records, apart from behavior that a known issue with source `as-built` and next `fix` names as a defect; it omits no behavior callers rely on within the topic it records; it fixes no private structure; each Decision gives a source or says its reason is unknown.
  ```

- After the gate, a new design is `active` with `implemented` equal to its revision, in place of the `accepted` that the gate's status step gives an L1 draft. A revised design keeps its status, and its `implemented` rises to the new revision only when it equaled the previous one.
- An as-built revision needs no plan. It is committed on its own, as a `docs` commit with a `Refs:` trailer, before the change's own revision, which gives that commit as `Changes since`. Outside Git, the change's own revision starts once the gate has passed.

### Backfill

The tiers in the `canon` skill gain these rules:

- Behavior is unspecified when no design states it. `which` for its files, `find` for its topic and D000's rows are where to look; a file `which` maps to no design, or a row reading `none`, does not settle it alone.
- Before a change alters or extends existing behavior no design states, an as-built revision records that behavior; it is L1, also when it creates a design. From then on the change alters stated behavior and is tiered and handled like any such change: in a `canon-design` session it is the session's next revision, gated at its tier; anywhere else it is a design problem, as the `canon` workflow defines one, so the user decides on the revision, which passes its gate at its tier, and an L2 revision goes through `/canon-design`.
- Where no design states the behavior, an L0 change alters nothing callers rely on: a refactor, a dependency bump, test or tooling work, or a fix for a defect no caller could rely on, such as a crash.
- New behavior with nothing existing to record is tiered by the other rules: a new topic is L2.

The skills apply them:

- `canon-design`, in Frame, once step 4 has started the design unit: when the change alters unspecified behavior, the session writes the as-built revision, passes its L1 gate and commits it, then makes the change's revision and passes the gate at the change's tier, in one run. Started on existing code with no change in view, it ends after the as-built revision.
- `canon-implement`: an L0 change or a slice that turns out to alter unspecified behavior gets an as-built revision from the commit it started at, or the plan's `Started at`, which passes its L1 gate and is committed. The work then alters a spec: an L0 change continues as the L0 rule for such a change states, and a slice pauses as for a design problem.
- `canon-code-review`: the Spec axis reports behavior callers rely on that the diff alters and no design states, whether or not a design governs the change. Its fix is an as-built revision from the review's merge base, after which the change needs a revision of that design: a design problem, as above.
- The docs step: a changed file no design covers, in a change that altered nothing callers rely on, is named in the report with its directory; it needs no new design.

### Setup

- Setup ends once D000 and the adopted designs that describe existing code have passed their gates. `canon-init` writes no other as-built design; the first change that alters unspecified behavior records what it needs.
- A doc that describes the whole project, such as an architecture overview, is folded into D000 and removed, as an ADR is folded into its design; a [project doc](#project-docs), such as the README, is not.
- `canon-init` fills D000 from the code: Goals, every capability and module with its Path and designs or `none`, the standards designs own across modules, the dependency directions and the glossary. D000 passes the L1 gate as an as-built design, like the adopted designs that describe existing code, and is shown to the user.
- Upgrade: after `init` has moved the architecture design to D000, the agent bumps D000's revision and, as an as-built revision, rewrites Goals as D000's, folds the old sections into the four subsections, fills what is still missing and narrows `paths` to files, then passes the L1 gate. Code the old `paths` covered shows in coverage until designs cover it. When `init` created a fresh D000 instead, the agent fills it as in setup.

### Project docs

A project's `README.md`, its hand-written intro for users, belongs to the doc system like its `AGENTS.md` and its docs root; the `canon` skill's Layout names it. A project need not have one, and `check` does not read it. It stays: `canon-init` neither folds it into D000 nor adopts it, and where it restates D000 or a design, they hold.

A file in any directory whose name, before its extension and in any case, is `README`, `AGENTS`, `CLAUDE`, `CHANGELOG`, `CONTRIBUTING`, `LICENSE` or `NOTICE`, and any file under a docs root, is a doc:

- `which` prints `<path>: doc` for it, unless an entry of a design's `paths` is its exact path, so neither the docs step, code review nor `canon-review` takes it for code no design covers. A glob or directory entry never matches a doc, in `which`, in `affected` and in the unchecked commits `audit` counts.
- Coverage counts no doc.
- The docs step fixes, in READMEs, guides and `AGENTS.md`, the names the change renamed or removed and what they state of behavior the change altered.

### Coverage in audit

`audit` reports uncovered source areas when there are any:

```text
Source areas no design covers (commits in the last 90 days, most first):
  14 commits  src/billing/  23 files
   6 commits  src/export/  4 of 9 files
  and 3 more areas
```

- Files are the tracked files under the Paths of D000's Modules rows, other than [docs](#project-docs); tooling, CI and configuration outside every module are not counted. A file belongs to the module with the longest Path that holds it, and is covered when the `paths` of a non-archived design, in any project, match it. Area paths are relative to the repo root, and one list covers the repository.
- Each uncovered file starts in the area of its directory. While every counted file under the parent directory is uncovered, the area moves up to the parent, never above its module's Path.
- An area whose counted files are all uncovered, its subdirectories' included, shows `<n> files`, counting them all. Any other area shows `<uncovered> of <counted> files`, counting the files directly in it.
- Areas rank by the commits of the last 90 days that touch their uncovered files, then by uncovered files, then by path. The first 10 are listed and the rest counted.
- Coverage never makes `check` fail, and `audit` exits 0.
- `canon-sync` reports the listed areas, and `canon-review` takes its design-coverage scope from them, the architecture angle's hard check included.

### Delivery

1. `canon.py`, with tests in `tests/test_canon.py` and a `CANON_VERSION` bump in every commit that changes it: D000's template and checks, the refusal to archive it, ids that history keeps taken, `init`'s D000 and its upgrade move, the deleted-doc exception, `as_built` and its checks, the `AGENTS.md` block, `which` for docs, and `audit`'s coverage and reach.
2. The `canon` skill: `as-built.md`; the backfill rules in the tiers; `as_built` among the frontmatter fields; D000 in Layout, in Reading docs and in `doc-types.md`, in place of the architecture design, and the project's `README.md` in Layout; the `audit` row of the Tool table; in `workflow.md`, the reviewer prompt's as-built lines, the as-built status in the gate's status step and the docs step's rules for uncovered files, D000's rows and what docs state; the `as-built <commit>` source among the known issues' sources.
3. `canon-init`, `canon-design`, `canon-implement`, `canon-code-review`, `canon-sync` and `canon-review` as this design states, `canon-review`'s `architecture.md` included. `canon-init`'s architecture step becomes D000's and drops its rule that `paths` cover the main source directories. Every mention of the architecture design in the skills names D000.
4. `README.md`: the roadmap entry on as-built designs becomes part of How canon works, and the Skills table summaries of `canon-init` and `canon-design` follow their changes.
5. This repository's own D000, no later than the commit that adds `check`'s D000 rule: `init --script skills/governance/canon/scripts/canon.py` run here adds the canon block to `AGENTS.md` and the `.gitattributes` rules and creates D000, which is filled as in setup. D001's `paths` are extended to the files it specifies, docs excepted.

Scenarios, tested through the commands:

- `init` in a repository without docs creates D000 with the four subsections, and `check` reports only the warnings of an unfinished design; `init --root <module>` creates none.
- `init` in a project whose D003 owns `architecture`, lists D003-K1 and is in plan P002's `based_on` moves it to D000 with D000-K1 and `based_on: [D000@r<n>]`, rewrites the links to it and appends the missing subsections at the end of `## Spec`. After D000 is filled out to over twice the old doc's size, neither `check` nor `check --base` reports a deleted doc. A later `new D` does not get D003, even when D003 was the highest D number, and `new D --parent` does not reuse the letter of a sub-design that `renumber` gave another letter.
- `check` errors without D000, with a D000 under a module's docs root, with a subsection missing, with `src/**`, `src/` or an existing directory in D000's `paths`, with an `as_built` that names no commit, or reads `worktree` once HEAD has a commit, and with an `as_built` left on a reviewed revision, which `check --fix` removes. It only warns for a Modules Path that is not a directory.
- `archive D000` is refused.
- `which` prints `doc` for `README.md`, `src/a/readme.rst`, `AGENTS.md`, `CLAUDE.md`, `LICENSE` and a file under a docs root, and for `src/auth/README.md` while a design's `paths` hold `src/auth/**`; it prints the design for a README whose exact path a design's `paths` list. A commit that changes only `src/auth/README.md` is no unchecked commit of that design.
- `audit` counts only files under D000's module Paths, and no doc among them. It lists a fully uncovered `src/a/` with its subdirectories folded in but never above its module's Path, `src/b/` as `2 of 5 files`, and the files of a module whose Path is `./`; it ranks areas by commits of the last 90 days, lists 10 and counts the rest. It lists a design D000 does not reach, and not one reached through another design's `refs`.

## Decisions

- D000 has a fixed id: every project, skill and `check` rule can name it, and it heads the index.
- D000 is the architecture design, extended with Goals, capabilities and standards: a separate overview would hold the module map twice.
- D000's rows name modules, capabilities and standards, never single docs: the generated index lists every doc, merges by union and cannot go stale.
- D000's rows are kept by the change that alters what they map, with no revision or gate: they restate facts the code and the other docs already hold.
- D000's `paths` hold only files: a directory or glob would make every file look governed and hide the gaps coverage reports.
- The upgrade moves the architecture design to D000 rather than superseding it: the doc keeps its history, gate state and known issues, and ids that history keeps taken stop its old number from returning.
- As-built revisions pass at L1: they change no behavior, and a fresh reviewer can check each statement against the code.
- An as-built revision records the change's start commit: a design derived from the changed code would let the review check the code against itself.
- A confirmed defect goes into the Spec as it should be, with a known issue: the Spec states intent, so the fix restores specified behavior and stays L0.
- Doubtful behavior stays in the Spec as it is until the user decides: callers of existing code rely on what it does, so changing it should take a revision.
- Backfill precedes behavior changes only: designs written for every touched file would follow incidental edits rather than behavior.
- Setup stops at D000 and the docs the project already has: the first change that needs a baseline records it, so setup writes nothing for work that may never come.
- Coverage is a hint in `audit`, never a `check` error: adoption is gradual and must not block commits.
- Coverage counts only files under D000's module Paths: tooling, CI and configuration need no design, and the Modules table already says where the code lives. A module whose Path is `./` counts them too, so a project with tooling at its root gives its modules narrower Paths.
- READMEs, `AGENTS.md` and the other project docs are docs, never code no design covers: they describe the project rather than implement it, and listing them in the `paths` of the designs they restate, or letting a glob there match them, would count every edit to them, such as a new row of a skills table, as an unchecked commit of each.
- `as_built` lives only until the gate: the gate, a resumed session and a replay need the base, and once past its gate the revision is maintained like any other.
