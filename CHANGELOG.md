# Changelog

Notable changes in each release. Versions follow [Semantic Versioning](https://semver.org); while the major version is 0, a minor release may change how skills behave.

## 0.8.0 - 2026-11-13

Sessions that work in one repository at the same time each take a worktree of their own, and `check` checks what a commit records, so one session's uncommitted work no longer fails or gets rewritten by another's.

- The `canon` skill gains a Concurrent work section. When another session works, or will work, in the checkout, the agent works in a linked worktree at `.worktrees/<branch>`, whose branch tracks the one it was made from; a session that finds uncommitted changes nobody told it about asks you before its first edit. The section also says how to finish a worktree's branch and how to commit only part of a checkout's changes, with `check --fix <ids>`, `index --staged` and `check --staged`.
- `check --staged` checks the staged tree, what `git commit` records, and `check --rev REV` the tree of commit REV. Both read docs and indexes through Git, so changes outside the commit neither fail nor pass it. Neither takes `--fix` or the other, and `--staged` refuses while merge conflicts are unresolved.
- `check ID|PATH ...` checks only the named docs, a problem between two docs counting on each, and with `--fix` fixes only those and leaves the indexes alone. Subagents that edit docs, such as workers and researchers, now check only their own.
- `index --staged` regenerates the indexes of the staged tree from the staged docs and stages them, so a commit of some docs carries their index lines.
- A stale index is now a warning in the work tree. It stays an error under `--staged`, `--rev` and `--base`, where the `--staged` message names `index --staged`.
- `init` adds `.worktrees/` to `.gitignore`. The pre-commit hook `init --hook` writes runs `check --staged`, so it checks the commit rather than everything uncommitted, and every `init` at the repo root replaces the hook earlier versions wrote.
- With tracing on, a project's own worktrees in `.worktrees/` keep their trace data in the main checkout's trace directory, so removing a worktree keeps its units; a worktree that cannot write there, as in a sandbox limited to it, keeps its own.
- In a worktree, subagent prompts start with its path, and handoffs and next-phase commands name it. `canon-implement` starts a paused slice's stash message with the plan and slice and finds the stash by that message. The canon block in `AGENTS.md` sends a shared checkout and a partial commit to Concurrent work instead of a plain `check --fix`.
- `canon.py` is now canon version 66: install this release in each project and run `/canon-init` to upgrade, which also replaces the old pre-commit hook.

## 0.7.2 - 2026-11-13

`canon.py`'s errors name the value at fault and the step to take, `which` flags files that exist nowhere, and `new` refuses a plan without its design.

- `check`'s `unknown entry` ends with the step that fits the entry: move one named like a doc into its type directory, move anything else out of `archived/`, adopt a `.md` file with `canon.py adopt` or move it into `guides/`, and move any other entry into `guides/` or `assets/`.
- `new`, `rename` and `adopt` refuse a slug that is not kebab-case with its kebab form as an example, and `adopt` of a path where nothing exists says the file does not exist.
- `new P` refuses without `--from` instead of creating a plan no design backs. When `--from` names a doc that is no accepted or active design, the error gives its status or says it is not a design.
- `show ID#slug` lists the doc's section slugs when the slug matches none, and `find` with no match says how many archived docs match with `--archived`.
- The `--base` errors of `check`, `affected` and `renumber` tell an unknown ref, to fetch or correct, from history that shares no merge base, and in a shallow clone say to run `git fetch --unshallow`. `renumber --base` refuses a ref that names no commit.
- `which` marks a file that exists neither on disk nor in Git as `(missing)` and still names the design that would govern it, so a mistyped path no longer passes for a real one.
- `canon.py` is now canon version 57: install this release in each project and run `/canon-init` to upgrade.

## 0.7.1 - 2026-11-13

`renumber` and `rename` leave no stale reference to a moved doc or a changed heading behind, and `check` catches a cited experiment archived as concluded.

- `renumber`, and `init`'s move of a doc to D000, now rewrite every citation of a moved id outside code, not only links and `refs`: a review's `moved` and `fixed` dispositions, `summary`, prose and link texts. A citation in a link's text follows the doc or attachment directory the link points at, and a doc's citations of its own id stay with it. In an id collision, citations count as evidence of which doc they mean; one written more often than on the base is unclear, so `renumber` keeps it and names the doc for you to settle.
- `rename` also moves the attachments named after the old slug, and refuses to overwrite an existing file. `rename ID SLUG --title T` sets the doc's H1 to `# <ID>: <T>` and rewrites the link texts that repeat the old `<ID>: <title>`.
- References to a heading whose anchor a command changes now follow it. In every doc, the `§<slug>` after a citation follows the heading anchors of what it names: the linked file for a link text's citation of the doc the link points at, the doc itself for its own id, otherwise the one doc with the id after the command. In every `.md` file, guides included, links follow the headings whose link texts or citations the command changes, through chains of such headings. One rare case is left: after `renumber`, a citation in the middle of a doc's link text that points into the moved doc's attachment files keeps its old slug when that file's heading changes.
- `check` warns of an experiment archived as `concluded` that a live doc still cites, naming the docs that link it: move it and its attachment directory back out of `archived/` and fix the links, or remove the links that do not rest on its result.
- `canon.py` is now canon version 56: install this release in each project and run `/canon-init` to upgrade.

## 0.7.0 - 2026-11-13

An experiment stays live while any live doc cites it, and docs define their terms before the sections that use them, D000's Glossary first.

- A concluded experiment now stays in `experiments/` while any live doc links it: a concept, review, investigation or experiment counts as a design or plan does. A link from a concluded experiment counts only while that experiment is cited itself, so concluded experiments that link only one another are uncited, and an experiment's link to itself never counts. `check` warns `concluded, but no live doc cites it` for the rest, which the docs step archives as `concluded`, and `archive E00X concluded` refuses one a live doc cites, naming those docs. Setting `concluded` still needs a live design or plan that links the experiment.
- A later run extends an `answered` experiment only while no live doc cites it, and `status E00X running` refuses the move back otherwise; `planned` and `running` experiments are extended as before.
- `superseded`, `overturned` and `dropped` archive an experiment whatever links it. The session that finds a result wrong now names to the user every other live doc linking the experiment, not only draft designs and plans.
- `writing.md` orders the sections a doc type leaves free, such as a design's Spec subsections, from the whole to the parts, and defines each term or name before the first section that uses it, or links its definition there.
- D000's Spec leads with its Glossary, followed by Capabilities, Modules and Dependencies. `init`'s template and `check`'s message for a missing subsection follow the new order, and the template's hint for `### Standards` moves to the end of Dependencies. An existing D000 in the old order stays valid; reordering its subsections changes no meaning, so it takes no revision bump and no gate.
- `canon.py` is now canon version 53: install this release in each project and run `/canon-init` to upgrade.

## 0.6.0 - 2026-11-12

canon is installed in each project, pinned to a release, and projects keep no copy of `canon.py`.

- Install canon at the repo root with `npx skills add BigTailFox/skills@<tag> -s '*' -a claude-code -a codex -a cursor -y`, as README's Install section shows. It puts the skills in `.agents/skills/`, links them from `.claude/skills/` and records the release in `skills-lock.json`. Commit them with the project, so every clone, worktree and CI job runs the pinned release, or commit only `skills-lock.json` and restore the skills with `npx skills experimental_install`.
- `canon.py` runs only from an install inside the project. Started from canon installed for every project, or from another checkout's install, every command but `-h` and `--version` refuses and says how to install canon in the project. Each skill runs its own install's `canon.py`, `.agents/skills/canon/scripts/canon.py`, which the canon block's Tool line names.
- The canon block of `AGENTS.md` records the canon version the project was last set up with, as `canon version <n> or later`. An older `canon.py` refuses to run in the project; a newer one prints a reminder, and `check` warns, until `/canon-init` upgrades the project.
- `init` writes no copy of `canon.py` and drops `--script`. It warns about a tracked old copy, which `check` also reports while the copy is tracked, and every `init` at the repo root replaces the pre-commit hook an older `init` wrote with one that runs the installed `canon.py`. `init --hook` keeps any other hook, one it cannot read included.
- Installed skill files, `skills-lock.json`, `.agents/skills/` and the links into it, are tooling: `which` prints `skill` for them, a design's `paths` match them only by their exact path, so a skill update is no unchecked commit in `audit`, coverage skips them, and an `AGENTS.md` among them makes no project.
- `canon-retro` reads a skill's hash from the project's `skills-lock.json`.
- `canon.py` is now canon version 51.

Upgrade every machine and project in one pass, since Claude Code runs canon installed for every project instead of the project's, and the new `canon.py` refuses to run from there:

1. Remove canon installed for every project: `npx skills remove -g $(ls ~/.agents/skills ~/.claude/skills 2>/dev/null | grep -E '^canon(-|$)' | sort -u)`.
2. In each project, install this release at the repo root as above and run `/canon-init`. Its Upgrade rewrites the canon block and the old pre-commit hook, and asks before removing the old copy and replacing `python3 <copy>` where files name it, such as CI.
3. A project not yet migrated keeps its copy and its old canon block, which says to install canon for every project; install it in the project instead, or the user install comes back.

## 0.5.1 - 2026-11-12

Fixes to `canon.py`'s `rename`, `renumber`, `affected` and `show`.

- `rename` and `renumber` refuse the repo root's D000, whose file name the canon block of `AGENTS.md` links; a module's D000 can still be renumbered.
- `renumber` accepts a sub-design id written with extra zeros, such as `D0001B`, as `D001B`, and in a checkout Git cannot read ends with Git's reason instead of `unknown ref`.
- `affected` counts a renamed file under both its old and its new path, for uncommitted changes and with `--base`, so the designs governing either path are listed.
- `show` on a doc without frontmatter no longer prints the doc's first lines as frontmatter.
- `canon.py` is now canon version 46: run `/canon-init` in an existing project to upgrade its copy.

## 0.5.0 - 2026-11-12

Experiments stay where readers find them while designs and plans rest on them: a new `answered` status, concluded experiments that stay live while linked, and archiving as `superseded`, `overturned` or `dropped`.

- `answered`: an experiment whose Conclusion is written but that no design or plan has absorbed yet. `canon.py status E00X answered` first checks what archiving as `concluded` would: a filled `summary`, the Setup's run labels or `Sources:`, a Conclusion and no template guidance. `check` reports their absence as errors on a live answered experiment.
- `concluded` means answered and absorbed, and a concluded experiment now stays in `experiments/` while the body of a live design or plan links it. `status E00X concluded` sets it only while such a link exists. The session that writes the link sets it, else `canon-design`'s gate, else the docs step, which now archives plans after concluding the experiments they link. `check` warns about a live concluded experiment that no live design or plan links, and the docs step archives it as `concluded`. `audit` leaves live concluded experiments out of its idle docs. Experiments archived as `concluded` before stay valid.
- Experiments can be archived as `superseded` when a later experiment answers the same question and the result still holds, with the successor in `refs`, as `overturned` when the result is found wrong, and as `dropped`, from any status and without the Setup's run labels, when the question no longer matters. Concluding an experiment archives the earlier ones on its question that it links. `archive E00X concluded` refuses an experiment that is not `concluded`, pointing to `dropped`, and one a live design or plan still links.
- A later run on a question extends an experiment that is `planned` or `running`, or `answered` with no live design or plan linking it, which `status E00X running` moves back for the run; otherwise the run gets a new experiment that links the earlier one. `canon-research` and `canon-prototype` look for earlier experiments with `canon.py find --archived`.
- `canon-research` and `canon-prototype` write a `summary` that leads with the question's subject and states the answer, and a Conclusion that states the answer alone; the new-experiment template asks for that.
- `canon.py` is now canon version 45: run `/canon-init` in an existing project to upgrade its copy.

## 0.4.0 - 2026-11-11

One review gate per change, with follow-up rounds and recorded approval, a command that moves a doc's status, a reviewer file per user, and an `audit` that counts from the last time a design was reconciled with its code.

- One gate per change: a review gate covers every revision one change makes together, its target and the docs revised to match it, at the highest tier among them, with one set of reviewers. It asks first whether your content feedback is finished and commits its targets at once; a later revision in the same session goes to a follow-up round, in which the gate's reviewers read only what changed. A change to docs alone that bumps no revision takes no tier, and a design revision that needs no code change needs no plan.
- Approval: designs and plans record the latest revision you approved in a new `approved` field. For L2, a yes to the gate's request or the start of the next phase is the approval, and `canon-design`, `canon-plan` and `canon-implement` set it and commit it.
- `canon.py status ID STATUS` moves a doc forward along its type's statuses, refuses a move past the gate whose revision is not reviewed and an `active` design without `implemented`, and regenerates the indexes. The phase skills use it instead of editing `status` by hand.
- `canon-blind-review` holds the rules every blind review shares: one prompt template, review files per round, stopped runs, merging and confirmation. The session leaves the work tree alone while reviewers read. Reviewers may run the read-only `canon.py` commands and report in the docs' language, and the session saves each report verbatim.
- The cross-family reviewer file moves to `~/.config/canon/reviewer.md`, one per user on the machine; an earlier checkout's file is copied there. It lists each session family's reviewers in fallback order, a review asks only about a family with no reviewer it can run, and when a reviewer's runs stop twice the next one takes over before the manual route.
- `audit` counts a design's unchecked commits from its last change or from a later commit with a `Reconciled: D00X` trailer, which the Maintenance step and `canon-sync` write once they have compared the design with its code, as an empty commit when nothing needed changing. It now also counts the commits governed by `paths` entries holding `[`, `**` inside a path segment or `*` above a matching directory, and clean merges that Git's history simplification used to hide.
- `check` no longer warns about code not yet written: a design with no `implemented` gets no warning for `paths` that match no file, and a D000 Modules row that links only such designs gets none for its Path. Once a design has `implemented`, its revisions add a file to `paths` when the file exists, in the docs step.
- `canon-grill` asks in batches of at most three related questions, the one most others depend on first, and writes every open decision into the doc before asking it.
- An L1 revision runs in the current session and carries on to implementation, and a split that only moves content is L1. After a backfill, the session that took the change makes its revision; behavior found later is a design problem.
- An adopted concept stays in `concepts/`, and `check` warns while no design links it. `adopt`, `renumber` and `init`'s move to D000 carry links and anchors to the headings they rename. A finding fixed in a doc reads `fixed <id>@r<n>`, which `check` resolves.
- `canon-research` reuses a live experiment, keeps the brief and the researcher's id, recovers a stopped run once, and has the researcher write each finding as it goes; saved excerpts keep their text verbatim, with relative links turned into the source's absolute URLs. `canon-prototype` opens an experiment for every UI prototype and unattached question and keeps the prototype branch.
- `check` reads the links and anchors of Markdown files in attachment directories, counts lines as `wc` does, skips table rows in code fences and canon's markers quoted in code, and ends with `no merge base` for a ref that shares no history with HEAD. `archive` refuses a doc with leftover guidance or an empty summary, and a design with live sub-designs.
- A failing Git query, or a checkout Git cannot read, now ends the command with Git's reason instead of reading as an empty result, so `new`, `adopt` and `renumber` no longer reuse an id that history keeps taken, and `audit` no longer reports a clean tree.
- `canon-implement` names in each slice's `Refs:` trailer every design the slice was checked against, as `affected` lists them, not just its own.
- `init --hook` that cannot write the pre-commit hook finishes every other step and prints the command to run, setup installs the hook last, and `/canon-init` picks its flow when you name none.
- `canon.py` is now canon version 40: run `/canon-init` in an existing project to upgrade its copy.

## 0.3.1 - 2026-10-30

Fixes for projects whose `canon.py` copy is not at `scripts/canon.py`, and for docs files that `canon.py` used to overwrite or cut.

- The copy stays where you put it: `canon.py init` without `--script` takes the copy's path from the canon block of the repo root's `AGENTS.md`, so a project set up with `init --script` keeps its copy through upgrades and new modules, and `canon-init` and `canon-sync` run the copy the block names. `init --script` at the repo root moves the copy, rewrites the pre-commit hook `init` wrote, and warns you to remove the old copy and replace its path where files still name it, such as CI.
- `init` refuses, before changing any file, a copy path that is absolute, holds whitespace or leads out of the repository, a module run that names another copy than the canon block, and a file at the copy's path that is no copy of `canon.py`, which it used to overwrite. `/canon-init` then asks you for a path.
- `/canon-init` leaves the canon block of `AGENTS.md` as `init` wrote it, instead of offering to translate a block that the next `init` rewrites.
- A `docs/README.md` whose index start marker has no end marker after it is reported by `check`, and `check --fix`, `index`, `new`, `adopt`, `archive`, `rename`, `renumber` and `init` exit before changing any file, instead of crashing or adding a second index that cut the hand-written text before it on the next run. `init` likewise refuses a canon block start marker in `AGENTS.md` with no end marker after it.
- Links that `adopt`, `archive`, `rename` and `renumber` rewrite when a doc moves encode whitespace, `%`, `#`, `?` and parentheses in their targets, so they stay valid links.
- `canon.py` is now canon version 24: run `/canon-init` in an existing project to upgrade its copy.

## 0.3.0 - 2026-10-29

Brings canon to existing code: every project gets D000, the project overview, behavior no design states is recorded from the code before a change alters it, and `audit` reports the code no design covers.

- D000, the project overview: every repository that follows canon has `docs/designs/D000-project-overview.md`, where agents start. Its tables map each capability, each module with its source directories, and each cross-module standard to the designs that own it, or say that none does; it also holds the dependency directions and the glossary that the architecture design used to. `canon.py init` creates it, `check` enforces its sections, `archive` refuses it, and the docs step and `canon-sync` keep its rows in step as designs are created, moved or archived. In a project with code, `/canon-init` writes D000 from the code, folds docs about the whole project into it, and ends setup once D000 and the adopted designs pass their review gates; in a project without code, D000 is the first design, written with `/canon-design D000`.
- As-built revisions: before a change alters or extends behavior no design states, `canon-design` or `canon-implement` first records that behavior from the code at the commit the change starts from, as a revision that specifies no change. It passes the review gate at L1 without a plan and is committed on its own, and the change then revises that design like any other. Behavior that looks unintended is put to you, and a defect becomes a known issue. You can also ask `/canon-design` for a design of existing code with no change in view. Code review's Spec reviewer reports altered behavior no design states, whether or not a design governs the changed files, and the fix is the same kind of revision. A design's `as_built` field holds the recorded commit until its gate passes, and `check` validates it.
- Coverage: `canon.py audit` lists the source areas under D000's module Paths that no design covers, ranked by their commits in the last 90 days, and the designs D000 does not reach through their links. Coverage never fails `check`; `canon-sync` and `canon-review` take their coverage work from it.
- Docs by their name, such as READMEs, changelogs and licenses, and every file under a docs root, are never taken for code: a design governs one only through a `paths` entry equal to its path, `which` prints `doc` for one no design names, and `audit` no longer counts a commit as unchecked when it only touches such docs. `/canon-init` leaves READMEs where they are.
- Confirmation rounds read only what the fixes changed: `canon.py snapshot` records the work tree, untracked files included, before a review and again before its confirmation, and the confirming reviewer diffs the two, limited to the files the fixes touched. Snapshots stay in `.canon/canon/snapshots/` for 30 days, tracing on or off, so packaging that does not read `.gitignore` must exclude `.canon/`. Reviewers no longer write scratch files, and workers keep theirs in `.canon/canon-implement/`.
- A reviewer or worker whose run the host stops, because it was interrupted, timed out or failed, gets one more run, resumed where the host allows. A second stop pauses the slice, sends the cross-family review to the manual fallback, or leaves a same-model review for you. Confirmation now resumes every reviewer that runs as a host subagent.
- `canon.py new`, `adopt` and `renumber` no longer assign an id or sub-design letter that a doc has had in HEAD's history, such as one deleted, renamed or dropped by a merge.
- `check` warns about a revision pending review only once its design or plan has been accepted, so a new draft gets no such warning.
- `canon.py` is now canon version 22: run `/canon-init` in an existing project to upgrade its copy. `init` moves the design that owns `architecture` to D000, with its sub-designs, attachments, known issues and every link to it, or creates D000 when no design owns it, and `/canon-init` then rewrites D000 from the code. `init --no-architecture` is gone.

## 0.2.0 - 2026-10-22

Adds `canon-retro`, for 19 skills in all, opt-in tracing, known issues, and a way to handle problems found in accepted designs.

- `canon-retro`, a new skill: a canon workflow that hit friction in the tooling or the agent workflow, such as a correction, a command that would not run or a long search, ends with a retro that proposes at most three fixes concrete events justify (a check, a fix to the development environment, a design standard, a pointer), and you answer them in one reply. Smooth workflows skip it, and you can ask for a retro at any time.
- Tracing: `canon.py trace on` records how canon's workflows run, so the skills can be judged and improved on real work. Each unit of work, such as a design, a plan slice, a review gate or a code review, logs its outcome, its review findings' severities and dispositions, commit ids and digests of the skill files in use; a snapshot of the work tree at each start, and each review's files, are kept for replay. Tracing is off until you turn it on, nothing it records leaves the machine, and no commit or push of the project carries it; `trace status` reports on it and `trace prune` trims it. The README's Tracing section has the details.
- Known issues: a problem found in a design or in the code it governs that you leave for later is listed in that design with its severity, source, date and next step until a change resolves it. `canon.py check` validates the rows, the docs index and `which`, `find` and `affected` count them, and `audit` lists them oldest first. Review gates, code reviews and codebase reviews record there what you leave for later, and code review no longer creates R docs.
- Design problems: a flaw found in an accepted design while planning, implementing or reviewing comes to you with a proposed fix, together with the same review's other findings, and only the work that depends on it waits for your decision. An L1 fix is made in the same session and passes an L1 gate; an L2 fix goes to `/canon-design`. An L0 change that turns out to alter a spec now finishes as L1 in the same session, without a plan, instead of stopping.
- Reviewers report every blocker and major finding and at most 10 minor ones, most severe first, instead of at most 10 findings in all. Code review and `canon-review` replace their word caps with a rule that each finding be as short as a reader can still understand and verify, a worker's report has no word limit, and a code review keeps its reviewers' files apart from the plan gate's instead of replacing them.
- `canon.py renumber` normalizes a requested id such as `D0002` to `D002`.
- `canon.py` is now canon version 13: run `/canon-init` in an existing project to upgrade its copy.

## 0.1.1 - 2026-10-14

Cross-family reviewers per session family, and renumbering that settles id collisions after a merge.

- `.canon/canon-blind-review/reviewer.md` may list several reviewers, and a review uses the first whose family differs from the session's; `/canon-init` asks which model families your sessions run on and sets up a reviewer of another family for each.
- `canon.py renumber --base <branch>` settles an id collision left by a merge or rebase onto that branch: it gives each sub-design, attachment and reference to one of the two docs only when the branch or the links show whose it is, and lists the references it keeps for you to fix. Commands that take an id refuse one that two docs share. This is canon version 5.
- A plan fix that changes what the plan delivers is a new revision, and the plan's slices continue only after it passes the review gate.
- A worker stops on a failing test once two attempts in a row bring no new evidence about its cause, instead of after any two attempts.

## 0.1.0 - 2026-10-14

First release: 18 skills built around canon, for Cursor, Claude Code and Codex.

- `canon`: a documentation system for long-running, multi-session, multi-model work. Numbered concepts, designs, plans, reviews, experiments and investigations live under `docs/`; every change gets an L0, L1 or L2 tier; designs and plans pass a blind review gate with same-model and cross-family reviewers; and `canon.py` (canon version 4) creates, checks, queries, audits and archives the docs.
- `canon-init` and `canon-sync`: set canon up in a project or monorepo module, configure the machine's cross-family reviewer, and keep docs in step with the code.
- Fifteen execution skills that work through canon: design, plan and implementation phases, with a fresh worker subagent per plan slice; two-axis code review; blind and codebase reviews; TDD, grilling, prototyping, research and investigation; handoff, teaching and writing for agents. Fourteen of them are adapted from [mattpocock/skills](https://github.com/mattpocock/skills).
