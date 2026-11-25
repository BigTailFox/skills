---
status: active
created: 2026-10-22
updated: 2026-11-25
revision: 12
modules: [canon]
summary: D000 checks, as_built validation, doc/skill classification, audit coverage and unchecked commits, staged commit templates and per-commit Refs checks.
refs: [D001, D004, D006, D010, E006, R003]
owns: [project-overview, as-built-design, design-coverage, unchecked-commits]
paths: [skills/governance/canon/scripts/canon.py, tests/test_canon.py]
reviewed: 12
reviewers: [gpt-6.2-astra]
approved: 10
implemented: 12
---

# D002: Project overview, as-built checks and audit

## Goals

1. Every agent can start from one doc, D000, that states what the project does, how it is organized and which designs own each module, capability and cross-module standard, naming those no design owns yet.
2. An existing project adopts canon at the cost of D000 and the docs it already has: setup ends once they have passed their gates, and the next real change already runs through canon's design, implementation and review.
3. A change's tier measures the change, not the docs the project lacks: changing behavior no design states costs one L1 as-built revision more than changing stated behavior, never an L2 detour.
4. What an as-built revision adds holds for the code at the commit it records, apart from defects its known issues name, and it states intent only where evidence or the user gives it.
5. `audit` ranks the parts of the project's modules no design covers by recent commits, and coverage never fails `check`.
6. No tool or step takes a doc, such as the project's README, or a skill installed in the project for code that lacks a design, and the docs step keeps what docs state in line with the change.
7. Authors can generate design references from the staged change. Branch validation catches each new commit that omits a governing design. `audit` also reports unchecked changes since a design last changed or was reconciled.

## Spec

### Project overview (D000)

Every repository that follows canon has `designs/D000-project-overview.md` in the `docs/` of its root, titled `# D000: Project overview`. It is a design like any other, with these rules:

- Goals state what the project is for, who uses it and what is out of scope.
- Spec holds four subsections, in this order:
  - `### Glossary`: terms used across modules; a term one module uses belongs to the design that owns it. It comes first, since the other subsections use its terms ([D006§writing-rules: writing rules](D006-doc-model.md#writing-rules)).
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

  After them, `### Standards` has one row per standard that applies across modules, such as error handling, with the design that owns it: `| Standard | Design |`. It is left out while no design owns one.
- A Design cell links every top-level design that owns the capability or standard, or that governs the module's code, or reads `none`. Rows name modules, capabilities and standards, never single docs: designs reach their sub-topics through their own links, and `docs/README.md` stays the index of every doc. Detail below the module level belongs to the module's designs.
- The tables map the project, its planned modules included, each linking the designs that specify it; a module that a revision of a design with `implemented` specifies gets its row once its directory exists, in the docs step, as files join that design's `paths`. The change that adds or removes a module, capability or standard, or creates, moves or archives a top-level design, updates their rows in the same commit: the docs step checks this for code changes, `canon-design` for the designs it creates, and `canon-sync` points rows at the designs `audit` reports as unreached. Rows change no meaning: no revision bump and no gate. Goals, Dependencies and Glossary are spec. Adding a module, changing the dependency directions or changing a cross-module interface is L2, as the `canon` skill's tiers state.
- `owns` includes `architecture`. `paths` lists only files that embody the architecture, such as dependency-boundary configuration and module wiring, and is usually empty.
- Only the repo root has a D000, and only `init` at the repo root creates one. In a monorepo, D000's Modules rows link each module's designs.
- The `AGENTS.md` block that `init` writes names D000 as the place to start and `docs/README.md` as the index.

`canon.py`:

- `check` errors when the repo root's `docs/` holds no non-archived D000, when another docs root holds a D000, when D000's Spec lacks one of the four subsections, and when an entry of D000's `paths` contains `*`, `?` or `[`, ends with `/`, or is a directory. It warns when a Path in the Modules table is not a directory of the project, as it warns for `paths` that match no file, unless the row's Design cell links a design and no design it links has `implemented`: the module is still planned. The Design column is found by its header in any case, each link in the cell resolves as [D006§links-and-references: links and references](D006-doc-model.md#links-and-references) resolves a target, and a target that is no design counts as no link.
  - D000 is required whether or not the repo root has an `AGENTS.md`. An archived root D000 gets its own error, which says to move it back to `docs/designs/` with a live status; the error for a D000 under another docs root, archived or not, names `renumber <path>`.
  - The subsections are checked for presence, not order, and not while `## Spec` itself is missing. A D000 in another order stays valid; putting its subsections in this order changes no meaning, so it takes no revision bump and no gate.
  - A Modules Path is a directory of the project when it exists on disk inside the project directory, so a file, a missing path and a path leading out through `..` warn.
- `archive D000` is refused.
- In a Git checkout, `new`, `adopt` and `renumber` never assign an id, or a sub-design letter, that a doc file of that type has had in the history of HEAD. The ids come from the doc paths `git log -z --format= --name-only --no-renames --full-history -m HEAD` lists: without `--full-history`, history simplification skips a merged side branch whose docs the merge discarded, and without `-m`, `git log` lists no paths for a merge, whose resolution alone may have added a doc. With a HEAD commit, a history query that fails ends the command with `canon: cannot read the history of HEAD`, since going on could reuse an id.
  - When Git finds no checkout but a directory at or above the working directory holds `.git`, as when Git is not on PATH, refuses a checkout of dubious ownership or stops at `GIT_CEILING_DIRECTORIES`, the three commands end with `canon: cannot read the history of HEAD in <dir>: <reason>` before assigning anything, on an unborn branch too. `<dir>` is the nearest such directory, resolved; `<reason>` is what `git rev-parse --show-toplevel` printed on standard error, else `git rev-parse exited <code>`, or `git is not on PATH`. Ids follow the doc files alone only with no `.git` at or above the working directory, and on an unborn branch of a checkout Git reads.
- `init` at the repo root creates D000 from its template when there is none; it has no flag to skip it. Only a non-archived design that owns `architecture` stands for an existing one: an archived owner does not stop `init`, and a D000 already in the repo root's `docs/`, archived or not, does. The template gives each table its header row and each part a guidance comment: `## Spec`'s states the rules for rows and `paths`, and a second one at the end of `### Dependencies` says when to add `### Standards`.
- `init` in a project with no D000 but a design that owns `architecture` moves that design to `D000-project-overview.md`, titled `D000: Project overview`, as `renumber` moves a doc: its frontmatter, body, sub-designs, attachments and known issues come along, and every reference to it follows, as [D010§renumber: renumber](D010-doc-queries-and-renames.md#renumber) says. It then appends the subsections D000 lacks at the end of `## Spec`, each with a guidance comment. The id rule above keeps the old number taken.
  - Only a non-archived owner moves, and it keeps its status. Like `renumber`, the move rewrites references in other docs without bumping their `updated`, so the agent runs `check --fix` after it.
  - `init` changes no file and exits when several non-archived designs own `architecture`, naming them and asking that all but one drop it, and when the one that does is a sub-design or a module's design, asking that it drop `architecture` so that `init` creates a fresh D000 for its content to fold into.
- `check`'s error for a deleted doc skips a deleted design outside `archived/` that owned `architecture` at the commit it compares with, while D000 exists: once filled out, D000 differs too much from the old doc for Git to pair the two as a rename.
- `audit` lists the non-archived designs D000 does not reach. D000 reaches itself and every design named in the `refs` of a design it reaches, archived ones included; `refs` naming other docs lead nowhere. The list comes last, after [coverage](#coverage-in-audit), under `Designs D000 does not reach (link each from D000's rows or from a design D000 reaches):`.

### As-built revisions

While an as-built revision awaits its gate, its frontmatter holds `as_built: <commit>` (the commit whose existing behavior it records, also read by `trace start` for replay in [D001§replay: replay](D001-skill-telemetry.md#replay)), or `as_built: worktree` outside Git or before the first commit. The gate removes the field when it sets `reviewed`.

`canon.py check` enforces:

- `as_built` must be 7 to 64 lowercase hex digits naming exactly one commit (never a ref), or `worktree` outside Git / before the first commit.
- `as_built` remaining on a doc whose `reviewed` equals its `revision` is an error, removed by `check --fix`.
- A change to `as_built` alone, like `implemented`, needs no `updated` bump; on a reviewed revision only the fixable removal error is reported.

Agent authoring steps and gate prompts for as-built revisions live in the `canon` skill (`as-built.md` and `workflow.md`).

### Backfill

Backfill tiering and agent workflow steps live directly in the `canon` skill and its execution skills; this design specifies only the CLI rules above.

### Setup

Agent setup and upgrade steps for D000 live directly in the `canon-init` skill; `canon.py init` behavior for D000 is specified under [Project overview (D000)](#project-overview-d000).

### Project docs

A project's `README.md`, its hand-written intro for users, belongs to the doc system like its `AGENTS.md` and its docs root; the `canon` skill's Layout names it. A project need not have one, and `check` does not read it. It stays: `canon-init` neither folds it into D000 nor adopts it, and where it restates D000 or a design, they hold.

A file in any directory whose name up to its first `.` is, in any case, `README`, `AGENTS`, `CLAUDE`, `CHANGELOG`, `CONTRIBUTING`, `LICENSE`, `NOTICE`, `SECURITY`, `CODE_OF_CONDUCT` or `COPYING`, or starts with `LICENSE-`, and whose name has no `.` or ends, in any case, in `.md`, `.markdown`, `.rst`, `.txt`, `.adoc` or `.org`, is a doc by its name unless it is an [installed skill file](#installed-skills): `README.md`, `readme.rst`, `LICENSE`, `LICENSE-MIT` and `README.zh.md` are, `agents.py` and `notice.ts` are not. A doc by its name, and any file under a docs root, is a doc:

- `which` prints `<path>: doc` for it, unless an entry of a design's `paths` is its exact path, so neither the docs step, code review nor `canon-review` takes it for code no design covers. A glob or directory entry never matches a doc, in `which`, in `affected` and in the unchecked commits `audit` counts. An entry equals a doc's path after the trimming of whitespace and leading `./` that glob entries get.
- `audit` reads each commit's files with `git log -z -c --name-only --no-renames`: a merge touches the files its resolution changed against every parent, or, for a clean merge, whose combined diff lists none, the files it changed against any parent. A commit, or merge, whose files are all docs its design's entries do not list is no unchecked commit; through `--no-renames`, one that renames governed code to a doc still is.
- Coverage counts no doc.
- The docs step fixes, in READMEs, guides and `AGENTS.md`, the names the change renamed or removed and what they state of behavior the change altered.

### Installed skills

The skills a project commits with its install of canon are tooling, neither code a design specifies nor docs, even a `LICENSE` or `README.md` among them, and an `AGENTS.md` among them makes no project ([D006§layout: layout](D006-doc-model.md#layout)). An installed skill file is one [D004§install: install](D004-project-setup.md#install) defines, such as `.agents/skills/canon/scripts/canon.py`:

- `which` prints `<path>: skill` for it, unless an entry of a design's `paths` is its exact path, so neither the docs step, code review nor `canon-review` takes it for code no design covers. A glob or directory entry never matches it, in `which`, in `affected` and in the unchecked commits `audit` counts, so a skill update is no unchecked commit of a design whose `paths` hold `**/*.py`.
- Coverage counts none.

### Unchecked commits in audit

`audit` lists first the designs whose code changed in commits that do not name them:

```text
Designs with code commits since the design last changed or was reconciled that no `Refs:` trailer names (most first; review `git log <since>..HEAD` on its paths):
  5 commits since c3000f211c47  D002 active docs/designs/D002-overview-and-as-built.md - D000 overview, ...
```

- It reads every non-archived design with `paths`, in a checkout whose HEAD has a commit. A `git log` or `git diff-tree` that fails ends `audit` with `canon: git <command> failed in <dir>: <reason>`, and a checkout Git cannot read ends it with `canon: cannot read the history of HEAD in <dir>: <reason>`, as for `new` in [Project overview](#project-overview-d000), so neither reads as nothing to report.
- A design's baselines are its last change and each reconciliation that `git log <last change>..HEAD` lists.
  - Its last change is the newest commit that `git log -- <the design's file>` lists and that changed the design, against its first parent, beyond its Known issues. The Known issues section starts at the `## Known issues` heading outside code fences and runs to the next heading of level 1 or 2. A commit whose change outside that section lies only in blank lines and in lines starting with `updated:` or `refs:`, and which changed that section, is no such change. Any other change is, one to `updated` or `refs` alone included, and so is the commit that added the file at its current path. A design whose file has no such commit is not listed.
  - A reconciliation of the design is a commit whose message has a line starting with `Reconciled:`, in any case, that names the design's id as a `Refs:` line does, below. The canon workflow's Maintenance and `canon-sync` write it once they have compared the design with the commits `audit` lists for it and updated what those commits changed, in an empty commit (`git commit --allow-empty`) when the design needed no change. No other step writes it.
- Its unchecked commits are the commits `git log HEAD --not <each baseline>` lists that touch a file the design governs by its `paths` ([D006§frontmatter: frontmatter](D006-doc-model.md#frontmatter)), a doc or an [installed skill file](#installed-skills) only through an entry equal to its path, and whose message has no line starting with `Refs:`, in any case, that names the design's id, as a word of `C`, `D`, `P`, `R`, `E` or `I`, three or more digits and an optional capital letter. Which files a commit or merge touches: [Project docs](#project-docs).
- A design with unchecked commits gets the line `  <n> commits since <the first 12 hex digits of the first reconciliation that git log lists, else of the last change>  <doc line>`, the design's doc line as [D010§doc-lines: doc lines](D010-doc-queries-and-renames.md#doc-lines) defines it. The lines run most commits first, and the section is left out when no design has one.

### Design references in commits

`canon.py check --base REF` checks each non-merge commit reachable from the selected tip but not from REF. The tip is HEAD for a work-tree or staged check, and REV for `--rev REV`. Compare each commit to its single parent, or the empty tree for a root. Commits reachable from REF, merge commits and pending changes in the work tree or index create no trailer obligation in this check. A provably empty range needs no history traversal beyond that proof. For a nonempty range, reject a shallow boundary inside it. A shallow boundary reachable from REF could also hide an ancestor reported as new. Require more history unless every such boundary is a known ancestor of every included commit. Unrelated shallow boundaries have no effect.

Use the paths Git records. For each added, modified or type-changed path, read the live governing designs in the resulting tree. For a deletion use the parent tree. Treat a rename as a deletion and an addition. Classify each file as code, a project doc or an installed skill in that same tree. Match design entries against its Git path, including the name of a symlink. Apply the ownership rules in [Project docs](#project-docs). Each required design ID counts once, including every owner of a shared file. Find cited IDs with the same `Refs:` line and ID rules as [Unchecked commits in audit](#unchecked-commits-in-audit). Extra IDs are allowed. Branch validation requires no design ID from a commit with no governed paths. For each missing ID report an error with the commit ID, the missing design and one changed path it governs. A later commit cannot supply an earlier one's reference.

`canon.py commit-template [--subject TEXT]` writes an editable Git message to stdout for the current index. It uses the same changed paths and owners as the proposed commit, comparing the index with HEAD or the empty tree before the first commit. Honor alternate Git indexes, exclude intent-to-add entries, and refuse an unmerged index or a directory outside Git. Write the supplied single-line subject, or leave its line empty for the editor. When there are owners, follow it with a blank line and one `Refs: D001, D002` line containing the distinct required IDs in design ID order. With no owners print just the subject line. Check the staged change against any listed design the author has yet to verify, using its historical version when it supplies ownership. Append any additional references the workflow requires, such as a plan updated by a slice or an as-built design. Generating the message leaves the work tree, index, configuration and commits untouched.

Verify a staged edit in a shared file with an unstaged ownership change. Its generated message must pass the range check after the staged change commits. Missing one owner fails on that commit even if a later commit cites both. Cover both ends of a rename, parent ownership on deletion, a root, a merge and an unowned change. Delete a link into installed skills under a governed glob and verify its classification from the parent. A shallow REF-side boundary that masks a true ancestor must request more history even when a merge base exists. [E006: Commit reference trial](../experiments/E006-refs-trailer-trial.md)

### Coverage in audit

`audit` reports uncovered source areas when there are any:

```text
Source areas no design covers (commits in the last 90 days, most first):
  14 commits  src/billing/  23 files
   6 commits  src/export/  4 of 9 files
  and 3 more areas
```

- Files are the tracked files under the Paths of D000's Modules rows, other than [docs](#project-docs) and [installed skill files](#installed-skills); tooling, CI and configuration outside every module are not counted. A file belongs to the module with the longest Path that holds it, and is covered when the `paths` of a non-archived design, in any project, match it. Area paths are relative to the repo root, and one list covers the repository.
- The Modules table is the first table under `### Modules`, outside code fences, its Path column found by its header in any case. An empty entry, and one that is no existing directory of the project, holds no file. The files are those `git ls-files` lists, so coverage prints nothing outside Git or without a root D000.
- Each uncovered file starts in the area of its directory. While every counted file of its module under the parent directory is uncovered, the area moves up to the parent, never above its module's Path. The files of other modules under that parent neither stop the area nor join it.
- An area whose counted files of its module are all uncovered, its subdirectories' included, shows `<n> files`, counting them all. Any other area shows `<uncovered> of <counted> files`, counting its module's files directly in it.
- Areas rank by the commits of the last 90 days that touch their uncovered files, then by uncovered files, then by path; a merge touches none, since `git log` without `-m` lists no files for it. The first 10 are listed and the rest counted. The repo root's area reads `./`, the commit counts are right-aligned, and the lines keep the plural forms above, as `1 commits`. The list follows `audit`'s other sections.
- Coverage never makes `check` or `audit` fail.

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
- `paths` entries match whole files ([D006§frontmatter: frontmatter](D006-doc-model.md#frontmatter)): a file several designs implement, such as `canon.py`, is in the `paths` of each, so a commit that touches it names in `Refs:` each design it was checked against, and coverage counts the whole file covered once any design names it. A part of a shared file that no design states therefore shows only as a D000 Capabilities row reading `none`, as the rest of `audit` does under the doc health audit. Parts of a file (`file#section`, by heading or by a comment in code) would fragment `paths`, need markers kept in step with the code and need line-level diffs in `which`, `affected` and `audit`, to save a longer `Refs:` and reading the listed designs, which the docs step does anyway (R001-F1; the user's decision, 2026-11-12).
- Coverage is a hint in `audit`, never a `check` error: adoption is gradual and must not block commits.
- A change to a design's known issues alone is no change of it: rows are not spec and do not count as checking the design against its code ([D006§known-issues-findings-and-slices: known issues](D006-doc-model.md#known-issues-findings-and-slices)).
- A reconciliation restarts a design's count through a trailer of its own, `Reconciled:`, on any day and in an empty commit when the design needed no change, which a restart only at a change of the design could not do (settled with R003-F32, the user's decision, 2026-11-11). `Refs:` could not mark it: plan, gate and known-issue commits name designs they never compared with their code (D002 r8 gate).
- A module row whose designs all lack `implemented` maps a module still planned, so its missing Path does not warn, while a row reading `none` still does: the design that specifies planned code tells it apart, with no marker to keep. An ordinary `check` reports the warnings that call for a fix in one pass. An explicit `--base` requests the second check that identifies existing diagnostics ([D006§check: check](D006-doc-model.md#check)) ([R003§r003-f32-permanent-warnings: R003-F32](../archived/reviews/R003-silk-design-phase.md#r003-f32-permanent-warnings); the user's decision, 2026-11-11).
- Moving a design's file, by `rename`, `renumber`, `init`'s move to D000 or by hand, restarts its count, since the baseline search does not follow renames (reason unknown, kept as found).
- Coverage counts only files under D000's module Paths: tooling, CI and configuration need no design, and the Modules table already says where the code lives. A module whose Path is `./` counts them too, so a project with tooling at its root gives its modules narrower Paths.
- READMEs, `AGENTS.md` and the other project docs are docs, never code no design covers: they describe the project rather than implement it, and listing them in the `paths` of the designs they restate, or letting a glob there match them, would count every edit to them, such as a new row of a skills table, as an unchecked commit of each.
- Installed skill files are tooling, neither code no design covers nor docs (the user's decision): committed with the project as [D004§install: install](D004-project-setup.md#install) recommends, they would otherwise show as an uncovered area of every module whose Path is `./`, make each canon upgrade an unchecked commit of any design with a broad glob, and fill the docs step's report with every skill file the upgrade changed.
- `as_built` lives only until the gate: the gate, a resumed session and a replay need the base, and once past its gate the revision is maintained like any other.
- After a backfill, the change's revision is the session's next one only when the session knew of the behavior as it took the work; one found later is a design problem, since the work was tiered or planned without it (D007 gate; the user's decision, 2026-11-11).
