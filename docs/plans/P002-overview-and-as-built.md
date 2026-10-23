---
status: in-progress
created: 2026-10-23
updated: 2026-10-23
revision: 1
modules: [canon]
summary: D000 from init and its upgrade move, history-kept ids, docs in which, audit coverage and reach, as_built, D000 checks, the skill texts and this repo's D000.
refs: [D001, D002, D003]
based_on: [D002@r3]
reviewed: 1
reviewers: [claude-opus-5.5, gpt-6-astra-high]
---

# P002: Overview and as built

Implements [D002: Project overview and as-built designs](../designs/D002-overview-and-as-built.md).

## Current state

Every slice done. Next: the code review from the `Started at` commit, then the docs step.

## Slices

### S1: Ids that history keeps taken

Status: done
Risk: performance

Builds on `D002#project-overview-d000`, the `canon.py` item on ids.

Changes in `skills/governance/canon/scripts/canon.py`, tested in `tests/test_canon.py`:

- In a Git checkout with a HEAD commit, every id and sub-design letter that a doc file has had in the history of HEAD is taken: the ids `path_id` gives the paths `git log -z --format= --name-only --no-renames --full-history -m HEAD -- ':(glob)**/docs/**/*.md'` lists, which include the paths commits deleted or renamed away, those of side branches a merge discarded, and those only a merge's resolution added.
- `new` and `adopt` take the next number above every taken one; `new --parent` takes the first letter not taken; `renumber` skips taken ids and letters as it skips the base's, and refuses a requested id or letter that is taken.
- Outside Git and on an unborn branch, ids are assigned as before.
- `CANON_VERSION` 14.

Test criteria; seam: the `new`, `adopt` and `renumber` command lines, their output and the files they write:

1. With D001 to D003 committed, then `renumber D003 D004` committed, `new D x` creates D005, `adopt notes.md design` then creates D006, and `renumber D001` without an id gives D007. `renumber D002 D003` exits 1 with `already used` and leaves `git status --porcelain` unchanged.
2. With D003 deleted by a commit instead, `new D x` creates D004; so it does with D003 under `模块/docs/designs/`, a module whose path Git quotes.
3. A D004 added on a side branch that `git merge -s ours` discarded stays taken: `new D x` creates D005. So does a D004 that only a merge's resolution added, on a side branch that a later `git merge -s ours` discarded.
4. With D001 and D001A committed, then `renumber D001A D001B` committed, `new D y --parent D001` creates D001C.
5. Outside Git, `new D x` creates D001, then D002.
6. Measured: the time `new D x` takes in a generated checkout of 10,000 commits, 1,000 of them merges, over 2,000 files, 200 of them docs, against the same command without the history lookup. The figures go in the Log; a lookup that adds over 1 s pauses the slice for the user.

### S2: D000 from init

Status: done

Builds on `D002#project-overview-d000`.

Changes in `canon.py` and `tests/test_canon.py`:

- A D000 template: `docs/designs/D000-project-overview.md`, H1 `# D000: Project overview`, `owns: [architecture]`, `paths: []`; `## Goals`; `## Spec` with `### Capabilities`, `### Modules`, `### Dependencies` and `### Glossary` in that order, the first two with the table header rows of `D002#project-overview-d000`; `## Decisions`. Each section and subsection carries a guidance comment stating its rules from `D002#project-overview-d000`, `### Standards` included where it is introduced.
- `init` at the repo root creates D000 from the template when the repo root's `docs/` holds no D000 and no non-archived design owns `architecture` (S3 moves that design instead). `--no-architecture` is gone. `init --root <module>` creates no D000.
- The `AGENTS.md` block links D000 as the place to start and `docs/README.md` as the index.
- `archive D000` exits 1 naming D000 and changes nothing.
- `CanonTest.setUp`, and every other test that ran `init --no-architecture`, runs `init`, so every fixture has a draft D000.
- `CANON_VERSION` 15.

Test criteria; seam: `init`, `archive` and `check` on the command line, and the files `init` writes:

1. `init` in a Git repository without docs creates D000 with the template's frontmatter and the four subsections in order, and `check` exits 0, reporting for D000 only the empty `summary` and the guidance. A second `init` prints `canon init: nothing to do`.
2. `init --root mod` creates `mod/AGENTS.md` and `mod/docs/README.md` and no D000 in either docs root. `init --no-architecture` is an argument error.
3. The root `AGENTS.md` block links `docs/designs/D000-project-overview.md` and `docs/README.md`, and `check` reports no link problem in `AGENTS.md`.
4. `archive D000 retired` exits 1 naming D000, and `git status --porcelain` is unchanged.

### S3: Upgrade move to D000

Status: done
Risk: complex logic, data migration

Builds on `D002#project-overview-d000`, the `init` items and the deleted-doc exception, and `D002#setup`, Upgrade. Depends on S1 and S2.

Changes in `canon.py` and `tests/test_canon.py`:

- `init` at the repo root, when the repo root's `docs/` holds no D000 and a non-archived top-level design there owns `architecture`, moves that design to `D000-project-overview.md` through `renumber`'s machinery: H1 `# D000: Project overview`; its sub-designs (D003A becomes D000A), its attachment directory and its known-issue ids come along, and every link, `refs`, `based_on` and `moved` entry follows. It then appends at the end of `## Spec` each of the four subsections the doc lacks, with the S2 template's guidance comment, and prints the move. The doc keeps its status, so in an accepted or active design `check` reports that guidance as an error until the as-built revision of `D002#setup` replaces it.
- When the non-archived design that owns `architecture` is a sub-design or lies under a module's docs root, `init` exits 1 before changing any file, naming the design and the fix: take `architecture` out of its `owns` and rerun `init`, which then creates a fresh D000 for the design's content to fold into. `renumber` cannot make either one the repo root's D000.
- `check`'s deleted-doc error skips a deleted design whose `owns` held `architecture` in the commit it compares with, HEAD for uncommitted changes and the merge base for `--base`, while the repo root's `docs/` holds a non-archived D000.
- `CANON_VERSION` 16.

Test criteria; seam: `init`, `check` and `new` on the command line, and the doc files:

The fixture stands for a project set up by an older `canon.py`: it deletes the D000 that `setUp`'s `init` created before its first commit.

1. In a committed project with D001 to D003, where D003 is active at revision 2, owns `architecture`, has the sub-design D003A, the attachment `designs/D003/map.svg`, a `### Modules` subsection and the known issue D003-K1, P002 has `based_on: [D003@r2]` and links D003, and R001 has a finding `moved D003`: `init` creates `docs/designs/D000-project-overview.md` with H1 `# D000: Project overview` and D000-K1, `D000A-*.md` and `designs/D000/map.svg`; P002 reads `based_on: [D000@r2]` and links D000; R001 reads `moved D000`; `### Capabilities`, `### Dependencies` and `### Glossary` follow D003's Spec content at the end of `## Spec`, and `### Modules` appears once. `check` then reports D000's guidance as errors and no other problem; once the guidance is replaced, `check --fix` exits 0. With D003 a draft, the guidance gives warnings only.
2. With D000 then filled to over twice the old doc's size, `check` before committing, and `check --base <the commit before init>` after committing, report no deleted doc. A deleted design that did not own `architecture` still gives the deleted-doc error.
3. After that commit, `new D x` creates D004.
4. A second `init` changes no doc. An archived design that also owns `architecture` stays in `archived/`, and D003 is the one moved. With the design owning `architecture` a sub-design, or under `mod/docs/`, `init` exits 1 naming it and the fix, and `git status --porcelain` is unchanged.

### S4: Docs are never code without a design

Status: done
Risk: complex logic

Builds on `D002#project-docs`.

Changes in `canon.py` and `tests/test_canon.py`:

- A file is a doc when its name up to the first `.`, in any case, is `README`, `AGENTS`, `CLAUDE`, `CHANGELOG`, `CONTRIBUTING`, `LICENSE` or `NOTICE`, or when it lies under a docs root.
- A design governs a doc only through a `paths` entry equal to the doc's path; glob and directory entries never match one. `which` prints `<path>: doc` for a doc no design governs. `affected` and `audit`'s unchecked commits apply the same rule to each commit's files, so a commit whose files under a design's entries are all docs those entries do not govern is no unchecked commit of that design.
- `CANON_VERSION` 17.

Test criteria; seam: `which`, `affected` and `audit`, with commits made in the fixture:

1. With a design whose `paths` hold `**`, `which` prints `<path>: doc` for `README.md`, `src/a/readme.rst`, `AGENTS.md`, `CLAUDE.md`, `LICENSE`, `NOTICE`, `CHANGELOG.md`, `CONTRIBUTING.md`, `docs/README.md` and `docs/assets/x.png`, and the design for `src/a/x.py`.
2. With `paths: [src/auth/**]`, `which src/auth/README.md` prints `doc`; with `paths: [src/auth/**, src/auth/README.md]`, it prints the design.
3. `affected src/auth/README.md` reports no design under the glob alone, and the design with the exact entry.
4. A commit without a `Refs:` trailer that changes only `src/auth/README.md` is no unchecked commit of the design holding `src/auth/**`; one that also changes `src/auth/x.py` is one; with the exact entry, the README-only commit is one too.

### S5: Coverage and reach in audit

Status: done
Risk: complex logic, performance

Builds on `D002#coverage-in-audit` and `D002#project-overview-d000`, the Modules table and `audit`'s reach. Depends on S2 and S4.

Changes in `canon.py` and `tests/test_canon.py`:

- The Modules table of the repo root's non-archived D000 is the table under `### Modules` in `## Spec`, its columns found by their header. A Path cell is split at commas, each entry stripped of whitespace and backticks and read as a directory, with or without its trailing `/`; `./` is the project directory. An entry that is not a directory of the project holds no file.
- Coverage as `D002#coverage-in-audit` states, over the files `git ls-files` lists, ranked with one `git log --since=90.days.ago --format=... --name-only --no-renames HEAD`, in that section's output format with the commit counts right-aligned. The repo root's area reads `./`.
- Reach: a heading `Designs D000 does not reach (link each from D000's rows or from a design D000 reaches):`, then a `doc_line` for each non-archived design, sub-designs included, that D000 does not reach.
- Outside Git `audit` prints no coverage, and without a non-archived D000 at the repo root it prints neither coverage nor reach.
- Tests that assert a design's id is absent from `audit`'s output assert on the line they mean, since every fixture design is now unreached.
- `CANON_VERSION` 18.

Test criteria; seam: `audit` and `check` output and exit status, with commits made in the fixture, some dated back with `GIT_COMMITTER_DATE`:

1. Only files under the Modules Paths count, and no doc: a `README.md` and a file under a docs root inside a Path, and the files outside every Path, appear in no area.
2. With one module at `src/a/` and nothing under `src/` covered, the files of `src/a/` and its subdirectories form one area, `src/a/  3 files`. With modules at `src/a/` and `src/b/`, `src/b/` holding 5 files of which 3 are covered shows `src/b/  2 of 5 files`, and its fully uncovered subdirectory `src/b/gen/` is an area of its own.
3. A module whose Path is `./` counts the files no longer Path holds, such as `build.sh` and `.github/ci.yml`; a file under a longer Path counts for that module.
4. Areas rank by the commits of the last 90 days that touch their uncovered files, a commit dated 91 days back not counting, then by uncovered files, then by path. With 12 areas, 10 are listed, followed by `and 2 more areas`.
5. With D000 linking D001, whose `refs` name D002, `audit` lists D005, which no design names, and none of D000, D001, D002 or an archived design.
6. `check` exits 0 however much is uncovered, and `audit` exits 0.
7. Measured: `audit`'s time in a generated checkout of 20,000 files in 400 directories with 1,000 commits in the last 90 days, against `audit` without coverage. The figures go in the Log; coverage that adds over 5 s pauses the slice for the user.

### S6: as_built in check

Status: done

Builds on `D002#as-built-revisions`, the `as_built` paragraph.

Changes in `canon.py` and `tests/test_canon.py`:

- `as_built` is an optional design frontmatter field. `check` errors when it names no commit, unless it reads `worktree` outside Git or before the first commit. It names a commit when it is a hex object name, full or abbreviated to at least 7 digits, that `git rev-parse --verify -q <value>^{commit}` resolves; a ref such as `HEAD` or a branch name moves once the change commits, so it names none. `check` also errors when `as_built` remains on a design whose `reviewed` equals its `revision`, an error `check --fix` fixes by deleting the line.
- `CANON_VERSION` 19.

Test criteria; seam: `check` and `check --fix`, and the design file:

1. A draft design pending review passes `check` with `as_built` set to HEAD's full or 7-digit hash, and with `worktree` before the first commit and outside Git.
2. `check` errors with `as_built: 0123456`, which names no commit, with `HEAD`, with `main`, with `worktree` once HEAD has a commit, and with a hash outside Git.
3. With `reviewed` equal to `revision`, `check` reports the remaining `as_built` as a fixable error; `check --fix` deletes that line alone, and `check` then passes.
4. `as_built` on a plan is an unknown frontmatter field.

### S7: The canon skill

Status: done

Builds on `D002#project-overview-d000`, `D002#as-built-revisions`, `D002#backfill`, `D002#project-docs` and `D002#delivery`, step 2.

Changes, as `D002#delivery` step 2 lists them:

- `skills/governance/canon/as-built.md`: when an as-built revision is written, the seven steps, `as_built` while the revision awaits its gate, and that it needs no plan and is committed on its own before the change's revision, which gives that commit as `Changes since`.
- `skills/governance/canon/SKILL.md`: the backfill rules in the tiers; `as_built` among the frontmatter fields, linking `as-built.md`; D000 in Layout and in Reading docs as the place to start; the project's `README.md` in Layout as a project doc; in the Tool table, `audit` with reach and coverage, `which` with `doc`, `check --fix` with the `as_built` it deletes, and `archive` refusing D000.
- `skills/governance/canon/doc-types.md`: D000's rules in place of the architecture design's paragraph; `as-built <commit>` among the known issues' sources.
- `skills/governance/canon/workflow.md`: the reviewer prompt's as-built header line, its Correctness and Completeness variants and its Assess item; the as-built status in the gate's status step; in the docs step, the rules for uncovered files, D000's rows and what READMEs, guides and `AGENTS.md` state.

Test criteria; seam: the skill texts:

1. `python3 scripts/validate.py` and `npx skills add . --list` pass, and `canon.py check` reports no error.
2. The orchestrating session checks the diff against each item of `D002#delivery` step 2: each is stated once, in the file it names, and linked from elsewhere. Gaps go in the Log with their fixes.
3. The trace call sites and the `canon` skill's paragraph on their placeholders are unchanged, so `D001#budgets` holds.

### S8: The other skills and the README

Status: done

Builds on `D002#backfill`, `D002#setup`, `D002#coverage-in-audit`, `D002#project-docs` and `D002#delivery`, steps 3 and 4. Depends on S7.

Changes:

- `canon-init`: setup ends once D000 and the adopted designs that describe existing code pass their gates; the architecture step becomes D000's, filled from the code, without the rule that `paths` cover the main source directories; whole-project docs fold into D000 and READMEs stay; `--no-architecture` is gone; Upgrade gains D000's as-built revision after `init` moved the architecture design, filling D000 as in setup when `init` created a fresh one, and the fix S3's refusal names; Add a module adds the module's row to D000.
- `canon-design`: in Frame, the as-built revision before a change to unspecified behavior, and the end after it when no change is in view; D000's rows for the designs it creates.
- `canon-implement`: the as-built revision for an L0 change or a slice that turns out to alter unspecified behavior.
- `canon-code-review`: the Spec axis's report of altered behavior no design states, and its fix.
- `canon-sync`: audit's coverage areas in its report, and D000's rows pointed at the designs audit reports unreached.
- `canon-review` and its `architecture.md`: the design-coverage scope and the hard check taken from audit's areas.
- Every mention of the architecture design in the skills names D000, in `canon-tdd`, `canon-teach` and `canon-codebase-design` too.
- `README.md`: the roadmap entry on as-built designs becomes part of How canon works, and the Skills table summaries of `canon-init` and `canon-design` follow their changes.

Test criteria; seam: the skill texts as an agent follows them:

1. `python3 scripts/validate.py` and `npx skills add . --list` pass, and `rg -i 'architecture design' skills README.md` finds nothing.
2. The orchestrating session checks the diff against each item of `D002#delivery` steps 3 and 4, as in S7.
3. Backfill dry run: after the worker reports done, the orchestrating session launches a fresh subagent given only the skill texts and a scratch Git project with a small CLI whose one design states its `list` command and not its `export` command, and asks it, following `canon-implement`, to add a column to `export`'s CSV. It should take the change as extending unspecified behavior, write an as-built revision of that design from its start commit, with `as_built` set, recording `export`'s CSV format as the start commit has it and nothing beyond that topic, write the filled reviewer prompt with the as-built lines to `.canon/`, and stop before launching a reviewer. The Log gets what it wrote and where it departed from `D002#as-built-revisions`.
4. Upgrade dry run: a fresh subagent given only the skill texts and a scratch project with a v13 `scripts/canon.py`, taken from this repository's history, and a D001 that owns `architecture` with a module map, a glossary and `paths: [src/**]`, follows `canon-init`'s Upgrade with the skill's `canon.py`, and stops before D000's gate. D000 should have its revision bumped, Goals rewritten as D000's, the old sections folded into the four subsections, `paths` narrowed to files, and `as_built` set. The Log gets the result.

### S9: This repository's D000

Status: done

Builds on `D002#delivery`, step 5, `D002#setup` and `D002#as-built-revisions`. Depends on S2, S4, S5, S6 and S8.

The orchestrating session builds this slice itself, without a worker: it is design work, and workers edit no design (`D003#input-and-reports`). It still takes `canon-implement`'s other steps for a slice, its commit included, inside the `implement` unit, since a slice the implementing session builds opens no slice unit (`D001#units`); it puts doubtful behavior to the user as `as-built.md` says.

Changes:

- Run `python3 skills/governance/canon/scripts/canon.py init --script skills/governance/canon/scripts/canon.py` at the repo root, which adds the canon block to `AGENTS.md`, creates `.gitattributes` with the index rules and creates D000. The rest of `AGENTS.md` stays as it is.
- Fill D000 as `canon-init`'s setup says, as an as-built revision of the slice's start commit, and pass its L1 gate with a same-model reviewer, as `as-built.md` and the review gate say; D000 becomes `active` with `implemented: 1`.
- Extend D001's `paths` to the files `D001#delivery-and-acceptance` step 1 delivers, docs excepted: `skills/governance/canon/scripts/canon.py`, `tests/test_canon.py`, `skills/governance/canon/trace.md`, `skills/governance/canon/SKILL.md`, `skills/governance/canon/workflow.md`, and the `SKILL.md` of `canon-blind-review`, `canon-code-review`, `canon-design`, `canon-handoff`, `canon-implement`, `canon-investigate`, `canon-plan`, `canon-retro` and `canon-review`, the skills with call sites or review-file names. Like the docs step's additions to `paths`, this bumps no revision of D001.

Test criteria; seam: `canon.py check`, `audit` and `which` on this repository, and D000's gate:

1. `check` reports no error, and `audit` lists no design D000 does not reach. Its coverage areas go in the Log.
2. `which README.md AGENTS.md LICENSE` prints `doc` for each, `which skills/governance/canon/scripts/canon.py` lists D001 and D002, and `which skills/execution/canon-retro/SKILL.md` lists D001.
3. D000 passed its gate with the as-built prompt and has `reviewed: 1`, `status: active`, `implemented: 1` and no `as_built`. The Log gets the gate's findings and their dispositions, and the final report shows D000 to the user.

### S10: D000 in check

Status: done

Builds on `D002#project-overview-d000`, the `check` items. Depends on S9: from this slice on, `check` fails a repository without D000, this one included.

Changes in `canon.py` and `tests/test_canon.py`:

- `check` errors when the repo root's `docs/` holds no non-archived D000; when another docs root holds a D000; when D000's `## Spec` lacks one of `### Capabilities`, `### Modules`, `### Dependencies` and `### Glossary`; and when an entry of D000's `paths` contains `*`, `?` or `[`, ends with `/`, or is a directory. It warns for a Modules Path that is not a directory of the project, read as S5 reads the table.
- `CANON_VERSION` 20.

Test criteria; seam: `check` output and exit status:

1. A repository fresh from `init` passes `check` with only an unfinished design's warnings.
2. `check` errors with D000 removed, with D000 in `docs/archived/designs/` as `retired`, with a second D000 under `mod/docs/`, with `### Glossary` missing, and with each of `src/**`, `src/` and `src` in D000's `paths`; with `src/base.py` there it passes.
3. A Modules Path `lib/` that is not a directory gives a warning and `check` exits 0; `./` and `src/` give none.
4. `check` passes on this repository.

## Notes

- Seams: the `canon.py` command line (arguments, output, exit status), the files it writes, and the Git state tests read with `git`. Tests run `canon.py` as a subprocess, as the rest of `tests/test_canon.py` does. The skill-text slices are checked through `scripts/validate.py`, the orchestrating session's item-by-item check against `D002#delivery`, and fresh-subagent dry runs.
- Order: `canon.py` lands before the skill texts, so no text names a command or field before it exists; this repository's D000 lands before `check` requires one, as `D002#delivery` step 5 asks, since `check` here runs the skill's `canon.py` directly.
- `canon.py` stays one file on the Python 3.8+ standard library and keeps working on Windows. Every commit that changes it bumps `CANON_VERSION`, since `validate.py` rejects a changed script under an unchanged version: S1 sets 14, and each later slice that changes `canon.py` adds one.
- From S2 on, every fixture has the draft D000 `init` creates, with its guidance warnings; `check --base` fails on them as on any unfinished doc.
- Commits that touch D003's `paths` (`workflow.md`, `canon-implement`, `canon-code-review`, `canon-init`, `canon-plan`) name D003 in their `Refs:` trailers once checked against it; from S9 on, commits that touch D001's `paths` name D001.
- The skill-text slices leave the trace call sites alone. A call site that must change stays within `D001#budgets`; tiktoken is not installed here, and `uv run --no-project --with tiktoken python3` counts tokens.
- `canon-tdd`, `canon-teach` and `canon-codebase-design` lie outside D002's `paths`: S8 changes only their mention of the architecture design, and the docs step reports them as it reports changed files no design covers.
- D001's snapshot of an as-built gate, which takes the commit `as_built` names as its second parent, is D001's own work, at its `implemented: 5`; S6 gives it the field to read.
- S1's history query needs `--full-history`: without it, Git's history simplification skips a merged side branch whose docs the merge discarded. It needs `-m`, since `git log` lists no paths for a merge otherwise, and a doc that only a merge's resolution added may appear in no other commit. Such a doc differs from every parent, so whatever format `log.diffMerges` sets, `-m` lists it; `--diff-merges` would need Git 2.31.
- The docs step writes into D002 the details this plan settles within its intent: the Git command whose paths give the ids history keeps taken, and why it needs `--full-history` and `-m`; that only non-archived designs owning `architecture` count for `init`; `init`'s refusal, and its fix, when the design owning `architecture` is a sub-design or a module's; the D000 template's table header rows and guidance comments; that a doc's name is matched up to its first `.`; how the Modules table and its Path cells are read; that coverage counts the files `git ls-files` lists, prints nothing outside Git, labels the repo root's area `./` and right-aligns the commit counts; reach's heading, and that coverage and reach need a root D000; that `as_built` holds a hex commit name of at least 7 digits or `worktree`, never a ref, and that `check --fix` deletes a remaining one.

## Log

- Drafted from D002@r2, after the user approved D002 by starting this plan.
- The user agreed the seams, both of S8's dry runs, and S9's scope with a same-model gate, as drafted.
- Review gate: S9 moved to the orchestrating session, since workers edit no design; S1's history query gained `-z`, `--full-history` and `-m`, checked in a scratch repository under every `log.diffMerges` format; `as_built` takes only a hex commit name or `worktree`; S3 moves only a non-archived owner, keeps its status and refuses a sub-design or module owner, naming the fix; S5 reads Path entries as directories; S1 and S5 pause on measured thresholds.
- The user approved the plan by starting its implementation. Started at 7c53381.
- S1 done: 8 tests in `HistoryIdTest`, 107 in the suite, all passing. Each of `-z`, `--full-history` and `-m` went into the query only after a test failed without it. Criterion 6, medians of 15 runs in a generated checkout of 10,000 commits, 1,000 of them merges, over 2,002 files, 200 of them docs: `new D x` took 0.517 s, against 0.113 s without the history lookup, so the lookup adds 0.40 s, under the 1 s threshold. The query alone takes 0.400 s; without `--full-history` and `-m` it takes 0.255 s.
- S1 decision: with a HEAD commit, a history query that fails ends the command with `canon: cannot read the history of HEAD`, since going on could reuse an id.
- S2 done: 5 tests in `ProjectOverviewTest`, 112 in the suite, all passing. The fifth pins that an archived design owning `architecture` does not stop `init` from creating D000. A D000 in the repo root's `docs/`, archived or not, does, so `init` never writes a second one.
- S2 decisions: the guidance comments are single lines without links, since `check` checks links inside comments and reads a line starting with `#` as a heading. `### Standards` is introduced by a second comment at the end of `### Glossary`, where it would go; the rules for rows and for `paths` go in `## Spec`'s comment, since the frontmatter holds none.
- Until S3, `init` in a project whose design owns `architecture` writes an `AGENTS.md` block that links a D000 it does not create, a broken link for `check`; until S8, `canon-init`'s setup still passes the removed `--no-architecture`.
- S3 done: 7 tests in `OverviewMoveTest`, 119 in the suite, all passing. The fixture also takes the D000 link out of the `AGENTS.md` block, as an older `canon.py` wrote it, so `init`'s refusal is seen to change no file. Breaking each new condition in turn made its test fail.
- S3 decisions, for the docs step to write into D002: `init` also refuses when several non-archived designs own `architecture`, naming them and asking that all but one drop it, since `owns` must be unique and picking one would be a guess. The deleted-doc exception, like the move, counts only a design outside `archived/`. `renumber`'s moving and link rewriting is now `move_doc`, which `init` calls with D000's slug and title; `renumber`'s output is unchanged.
- For S8: `init`'s move rewrites references in other docs without bumping their `updated`, as `renumber` does, so canon-init's Upgrade runs `check --fix` after `init`.
- S4 done: 6 tests in `ProjectDocsTest`, 125 in the suite, all passing. Breaking the empty-file-list guard, the case folding or the docs-root rule each turned a test red.
- S4 decisions, for the docs step to write into D002: `audit` reads each commit's files with `git log -z -c --name-only --no-renames`, so a merge counts by the files its resolution changed against every parent, and one whose resolution changed only docs its design's entries do not list is no unchecked commit; a merge with no such files counts as before. Through `--no-renames`, a commit that renames governed code to a README-named file still counts. A `paths` entry is compared with a doc's path after the trimming of whitespace and leading `./` that glob entries already get.
- S5 done: 9 tests in `CoverageTest` and `ReachTest`, 134 in the suite, all passing; each of 19 mutants of the new rules turned a test red. Criterion 7, medians of 15 runs in a generated checkout of 20,021 tracked files in 400 source directories with 1,001 commits in the last 90 days: `audit` took 0.326 s, against 0.272 s without coverage, so coverage adds 0.055 s, under the 5 s threshold.
- S5 decision: an area moves up while every counted file of its own module under the parent is uncovered, and counts only its module's files. Read literally, `D002#coverage-in-audit` would let another module's files stop or join a `./` module's area, splitting it into one area per directory and counting the longer module's files twice; criterion 3 and D002's goal 5 take areas as parts of modules.
- S5 details, for the docs step to write into D002: only the first table under `### Modules` counts, outside code fences, its Path column found by a header matched in any case; an empty entry holds no file. Coverage counts the index, as `git ls-files` lists it, and a merge touches no area, since `git log` without `-m` lists no files for it. The lines keep D002's plural forms, as `1 commits`. Reach follows only `refs` that name designs, archived ones included. Coverage and then reach come after `audit`'s other sections.
- S6 done: 5 tests in `AsBuiltTest`, 139 in the suite, all passing; each of 10 mutants of the new rules failed a test.
- S6 details, for the docs step to write into D002: `as_built` holds 7 to 64 lowercase hex digits, so a SHA-256 name fits. A change to the `as_built` line alone, like one to `implemented`, needs no `updated` bump, so `check --fix` deleting it leaves no other error. On a reviewed revision only the fixable error for the remaining field is reported, whatever its value.
- S7 done: `validate.py`, `npx skills add . --list` and `check` pass, `check` now with no warning since `as-built.md` exists. The `trace` call sentences and the `canon` skill's placeholder paragraph are unchanged.
- S7 check against `D002#delivery` step 2: every item is in the file it names. Two gaps, fixed by this session: the worker had the gate delete `as_built` in the status step, where D002 has it go when `reviewed` is set, so it moved to step 5, outside that step's `trace end` sentence; and the docs step repeated the list of changes that update D000's rows, which now only `doc-types.md` states, the docs step linking it. The docs step's rule for files no design covers also tells the user when the change altered behavior callers rely on there, since that change needed an as-built revision first.
- S8 done: `validate.py`, `npx skills add . --list` and `check` pass, and `rg -i 'architecture design' skills README.md` finds nothing. The `trace` call sentences are unchanged.
- S8 check against `D002#delivery` steps 3 and 4: every item is in the file it names. The worker's decisions: `canon-implement` also takes Backfill when Start already shows that the change alters unspecified behavior; a slice pauses, stashing its worker's changes, before its as-built revision, so that revision commits alone; setup in a project without code leaves D000 to `/canon-design D000`; Upgrade's refusal case covers several owners too; `canon-sync` links an unreached sub-design from its parent.
- S8 backfill dry run: the fresh subagent took the column as extending unspecified behavior and wrote D001 r2 as an as-built revision of the start commit, with `as_built` set: a `### Export` section with its usage, the `id,name,qty` header, rows sorted by id, CSV quoting, `\n` line ends and the read error shared with `list`; D001-K1, minor, next `fix`, for the header printed before the file is read, so a failed read leaves it on stdout; and D001-K2, minor, next `L1`, for the traceback that malformed JSON gives `list` and `export`. It wrote the same-model prompt to `.canon/canon-blind-review/D001/same-model-prompt.md` with the as-built line for a revision and the as-built Correctness, Completeness and Assess items, and stopped before the reviewer. Departure from `D002#as-built-revisions`: it judged K1 a defect itself, by `canon-grill`'s triage, instead of putting it to the user; `as-built.md` step 5 now says doubtful behavior is the user's to judge however plain it seems. It was also unsure which tier to state at Start; `canon-implement` now says such a change is at least L1.
- S8 upgrade dry run: the fresh subagent ran `init` with the skill's `canon.py` over a v13 project, which moved D001 to D000 and appended Capabilities, Modules and Dependencies. It committed that output unchanged, so Git keeps the rename, which canon-init leaves to the agent, then bumped D000 to revision 2 with `as_built` naming that commit, whose code equals the start's: Goals rewritten as purpose, users and scope; the module map folded into Modules with entry points, the dependency directions into Dependencies, the glossary kept; three Capabilities rows reading `none`; `paths: []`. It stopped before the gate, and `audit` listed `src/store/` and `src/app/` as uncovered. The fixture tracked `.pyc` files, which `audit` counted, a flaw of the fixture.
- Open points outside S8, for the final report: `canon-design` adds a resolved cross-module term to D000's glossary at once, while `D002#project-overview-d000` makes the Glossary spec, which takes a revision and gate; `canon-review`'s `functional.md`, outside D002's `paths`, still calls behavior no design specifies a spec gap or code to remove, without naming as-built revisions.
- S9 done: `init --script` added the canon block to `AGENTS.md`, the `.gitattributes` rules and D000, which was filled as an as-built revision of 80979959e860, passed its L1 gate with a same-model reviewer and was committed alone as 1f42ef4. `check` reports no error, `audit` lists no design D000 does not reach, `which` prints `doc` for `README.md`, `AGENTS.md` and `LICENSE`, D001 and D002 for `canon.py`, and D001 for `canon-retro`'s `SKILL.md`. D001's `paths` hold the files the plan names, with no revision bump.
- S9 decisions: D000 has one module, `canon`, over `skills/` and `tests/`, since D001 to D003 all name `modules: [canon]`; `scripts/validate.py` stays repository tooling outside every module. A Capabilities row links a design only when the design's `owns` holds the capability, so the rows for setup, sync, code review and the other skills read `none`. D000's `paths` stay empty.
- S9 gate: the first round asked for revision with 1 major and 6 minor findings. F1, major, accepted: Dependencies said a skill runs `canon.py` from the path `AGENTS.md` names, while `canon-sync`'s Audit step 1 and `canon-init`'s Upgrade and Add a module take `scripts/canon.py`; the user judged it a defect, so D000 states the rule and D000-K1, minor, next `fix`, names the three places. F2, accepted: the install row became the layout the `skills` CLI installs from, which Goal 3 does not exclude. F3 and F4, accepted in part: the Glossary links `AGENTS.md`'s Skill rules and keeps only definitions, the `validate.py` bullet lists its checks, and the two Decisions that restated skill-format rules went; declined, stating the skill format in D000 or giving it a `skill-format` topic, which would state `AGENTS.md`'s rules twice. F5, F6 and F7, accepted: the tiers row names its three skills and a row names `canon-blind-review`; `CANON_VERSION` is a decimal integer; a Decision records the single-file `canon.py` copied into each project, reason unknown. The confirmation round found all seven resolved and approved.
- S9 coverage areas, as `audit` lists them: `skills/execution/canon-teach/` (6 files, 4 commits), `skills/governance/canon/` (1 of 6 files, `writing.md`; 4), `skills/execution/canon-review/` (5 of 7 files; 3), `skills/execution/canon-codebase-design/` (3 files; 3), `skills/execution/canon-prototype/` (3 files; 3), `skills/execution/canon-tdd/` (3 files; 3), `skills/execution/canon-grill/` (1 file; 3), `skills/execution/canon-agent-writing/` (3 files; 2), `skills/execution/canon-research/` (1 file; 2), `skills/execution/canon-code-review/` (1 of 2 files, `smells.md`; 1), and 9 more areas.
- Open point from the S9 gate, for the final report: `init` without `--script` ignores the path the `AGENTS.md` block names; D000-K1's fix covers `canon-init`'s Upgrade, and whether `init` itself should keep the path is for the user.
- S10 done: 6 tests in `OverviewCheckTest`, 145 in the suite, all passing; each of 13 mutants of the new rules turned a test red. `validate.py`, `npx skills add . --list` and `check` on this repository pass.
- S10 deviations, in tests only: `OverviewMoveTest` stands for a project an older `canon.py` set up, without D000, so its commits now accept the missing D000 as `check`'s only error; its architecture design gets `paths: [src/base.py]` instead of the helper's `src/**`, which the new rule rejects once `init` moves it to D000, as `canon-init`'s Upgrade expects the agent to narrow it.
- S10 details, for the docs step to write into D002: `check` requires D000 whether or not the repo root has an `AGENTS.md`; an archived root D000 gets its own error, which says to move it back to `docs/designs/` with a live status; any D000 under a module's docs root is an error, archived or not, naming `renumber <path>`; the subsections are checked for presence, not order, and not when `## Spec` itself is missing; a Modules Path is a directory of the project when it exists on disk inside the project directory, so a file, a missing path and `..` warn. The Modules table's separator row is no longer read as a Path entry, which also corrects S5's reader without changing coverage.
- Code review from 7c53381 at L2, first round: Spec (same model) 1 major and 8 minor, revise; Standards (same model) 9 minor, approve; cross-family (gpt-6-astra-high) 3 major and 4 minor, revise. Two were design problems the user decided to fix now, as D002 r3 at L1: Spec F1, a doc by its name matched up to its first `.` made `agents.py` and `license.py` docs; cross-family F2, setup kept every project doc, every file under a docs root included, so none could be migrated. Spec F2, S5's per-module folding, goes into the same revision. Accepted, to fix in the change: cross-family F1 (a clean merge of README-only branches counted as an unchecked commit), F3 with Spec F3 (`canon-design` writing D000's glossary without a revision), F4 (a hex branch name passing as `as_built`) and F5 (coverage counting a module Path that is no directory); Spec F4 (an as-built revision that creates a design adds its D000 rows), F5 (a change known at Start to alter unspecified behavior needs `/canon-design`, as for any missing design phase; Backfill is for work that turns out to), F6 (`canon-init`'s setup commit gets a `Refs:` trailer), F7 (Upgrade commits `init`'s move before rewriting D000) and F8 (`init`'s refusal names no `--base`); Standards F1 (the `canon-sync` summary) and, by the user's choice, the refactors F4 to F9 with cross-family F7. Declined: Spec F8's dry run before writing, since `init` is idempotent and a rerun writes the same files; Spec F9, the `.tmp/` rules the user asked for; Standards F2, since D000 owns the dependency rules and restating them changes no meaning; Standards F3, since S2 asks the template's comments to state D000's rules; cross-family F6, since `AGENTS.md`'s rule covers the agent's own scratch files, not the suite's fixtures.
- D002 r3 gate (L1, same model): the first round asked for revision with 1 major and 3 minor findings. Accepted: F1, major, setup now keeps only docs by name outside every docs root and a docs root's own `README.md`, migrating every other file under a docs root; F2, the names gain `SECURITY`, `CODE_OF_CONDUCT`, `COPYING` and a `LICENSE-` prefix; F4, the display rule counts the area's module only, with a scenario. Declined: F3, moving standards out of kept project docs, a gap setup had before this revision. The confirmation round found F1, F2 and F4 resolved and approved. `based_on` is now D002@r3.
- Code review fixes: a worker brought `canon.py` to D002 r3 and fixed the accepted findings, test-first, with `CANON_VERSION` 21; 7 new tests, 152 in the suite, all passing, and 11 mutants of which the one survivor is equivalent. Docs by their name follow r3's names and extensions; a clean merge counts by the files it changed against any parent; `as_built` accepts only the object name of exactly one commit, never a ref; a Modules Path that is no existing directory holds no file in coverage, as in `check`'s warning; `init`'s refusals from the move suggest no `--base`. The refactors left `audit`, `which` and `check` output unchanged on a generated checkout of 20,000 files and 60 designs, where `audit` went from 0.44 s to 0.60 s, since coverage now matches each design's `paths` on their own. This session fixed the skill texts: Spec F3 to F7 and Standards F1.
- Open points from the fixes, for the final report: under r3, `skills/execution/canon-review/security.md`, skill instructions, is a doc by its name, so `which` prints `doc` for it and coverage skips it until a design lists its exact path; when the move refuses during `init`, `init` has already written its other files, as before S10, which a rerun after the fix writes again unchanged.
- Code review confirmation: the Spec reviewer found F1 resolved and approved. The cross-family reviewer found F1, F2 and F3 resolved and raised one new major finding: Upgrade's commit of `init`'s output as it is fails a pre-commit hook running `check`, since the guidance `init` appends to a moved active design is an error. The user chose to keep that commit, so Git keeps the rename, and `canon-init` now commits it with `--no-verify` when such a hook is installed. The user kept r3's names as they are, `skills/execution/canon-review/security.md` included.
