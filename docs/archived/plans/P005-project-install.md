---
status: done
created: 2026-11-12
updated: 2026-11-12
revision: 1
modules: [canon]
summary: canon.py run only from the project's install, init without a copy, the version check, installed skill files as tooling, and the skill texts.
refs: [D004, D000, D002, D006, D010, E001, R003]
based_on: [D004@r5, D000@r4, D002@r10, D006@r10, D010@r2]
reviewed: 1
reviewers: [claude-opus-5.5, gemini-4-argon-high]
approved: 1
---

# P005: Project install

Implements [D004: Project setup](../../designs/D004-project-setup.md) r5 and its follow-ons [D000: Project overview](../../designs/D000-project-overview.md) r4, [D002: Project overview and as-built designs](../../designs/D002-overview-and-as-built.md) r10, [D006: Doc model and writing rules](../../designs/D006-doc-model.md) r10 and [D010: Doc queries and renames](../../designs/D010-doc-queries-and-renames.md) r2, which passed one gate together. Each design's `implemented` equals its previous revision at b6396c6, D004 4, D000 3, D002 9, D006 9 and D010 1, so the work is each design's Spec diff from b6396c6 to 1300ed7.

## Current state

Done. Every slice landed, the code review approved the change, and the docs step wrote the Notes' details into the designs. The rollout in the Notes is left to the user.

## Slices

### S1: canon.py runs only from inside the project

Status: done

Risk: the check runs before every command, so a wrong rule refuses every project, one under a symbolic link such as macOS's `/tmp` or a linked worktree included, or lets a user install through; and every test now runs `canon.py` through a link the harness places.

Builds on `D004#spec` (the intro) and `D004#install` (the location check, its message, its place before the version check, the link for tests and scratch repositories, linked worktrees).

Changes in `skills/governance/canon/scripts/canon.py`, tested in `tests/test_canon.py`:

- `main()`, after `parse_args`, which exits on `-h` and `--version`, and before every dispatch, `trace` and `snapshot` included: the start path is `os.path.abspath(__file__)`, never resolved. Its top, found with no Git command, is the nearest directory at or above the working directory that holds `.git`, a directory or a file; without one, the working directory and every directory above it that holds an `AGENTS.md` qualify. The start path passes when one of the directories it passes through, walked up without resolving links, is `os.path.samefile` with a qualifying directory; otherwise the command exits 1 with D004's message, `<path>` being the unresolved start path. `trace_root()` keeps its own rule.
- `CANON_VERSION` 47.

Changes in `tests/test_canon.py`:

- `canon_process` runs `[sys.executable, "-B", <link>]`, the link being `<top>/.agents/skills/canon/scripts/canon.py` pointing at `SCRIPT`, created when missing. `<top>` is found as the check finds it: the nearest directory within `RUN_DIR` at or above the working directory that holds `.git`; outside Git, the nearest directory at or above the working directory, within the `outside_checkouts` directory, that holds an `AGENTS.md`, else the working directory. In a Git checkout the harness adds `/.agents/skills/canon/scripts/canon.py` to the file `git rev-parse --git-path info/exclude` names, so `git status`, `refuses()`, `affected` and snapshots never see the link. A `script=` option starts another path, for the refusal tests.
- The link is the test repository's installed `canon.py`: no test writes through it, and `canon_process` fails when the path exists and is not a link resolving to `SCRIPT`. A test that needs it tracked adds the link with `git add -f`, and a commit that changes only it retargets the link between an absolute and a relative target, both `SCRIPT`.
- Tests that assert a directory's exact contents leave out the harness's `.agents`, such as `PruneTest`'s outside-Git prune, which expects only `AGENTS.md`.

Repository: the scratch-repository bullet of `AGENTS.md`'s Workflow links the working tree's `canon.py` at `<dir>/.agents/skills/canon/scripts/canon.py` and calls the link through the shell function, since the working tree's path refuses there.

Test criteria; seam: `canon.py` started by a given path, its exit code, its output and the files it changes:

1. In a test repository, `which src/base.py` and `check` started by `SCRIPT`'s own path exit 1 with ``canon: canon runs only from an install inside the project, and this canon.py is <SCRIPT>; install canon in the project as https://github.com/BigTailFox/skills#install says, and remove a user install of canon with `npx skills remove -g` `` and leave `git status --porcelain` empty; `-h` and `--version` started by the same path exit 0.
2. Through the test repository's link, the same commands run from the repo root, from `src/` and from a module directory that holds its own `AGENTS.md`.
3. With a link to the test repository placed beside it, the link's path as the start path's prefix and the real directory as the working directory runs, and so does the reverse.
4. In a linked worktree of the test repository, created in another test directory so the main checkout's `git status` stays clean, the main checkout's link refuses with the worktree as the working directory, and the worktree's own link runs.
5. With Git missing from `PATH`, `trace status` started by `SCRIPT`'s own path refuses with the message, and started through the link prints its status.
6. Outside Git, in an `outside_checkouts` directory: `init` through a link in the working directory runs; from a subdirectory, a link in an ancestor that holds an `AGENTS.md` runs; a link in a sibling directory refuses.
7. The whole suite passes through the link with the system's default `TMPDIR`.

### S2: init sets a project up without a copy

Status: done

Risk: data migration. Upgrading a project that kept a copy must leave the copy and every hook but the exact old one alone and leave CI and each `docs/README.md` to the warning; taking this repository's canon source, or an installed `canon.py`, for an old copy would warn on every `check`.

Builds on `D004#init` (the synopsis, Old copy, the `AGENTS.md` block and its Tool line, the docs index intro, `--hook` and its warning), `D004#install` (the commands the block gives and the installed skill file) and `D000#dependencies` (this repository runs its working tree's `canon.py` and reruns `init` with each bump).

Changes in `canon.py`, tested in `tests/test_canon.py`:

- `cmd_init` keeps no copy: the copy path, `--script`, `block_script`, `repo_relative`, the move of a copy and its warnings go, and `script_version` stays only if the old-copy rule uses it. The init parser loses `--script`, and its help no longer says it upgrades the script copy.
- `AGENTS_BLOCK` becomes the template drafted in Notes, with `{version}` filled with `CANON_VERSION`; `DOCS_README`'s intro names `canon.py find <words>` with no path.
- `Repo.is_installed_skill(rel)`: the repo root's `skills-lock.json`, a path under `.agents/skills/`, or a path whose real path, read from the work tree, lies in the real path of `<root>/.agents/skills`. S4 puts it to its other uses.
- Old copy: in a Git checkout, the files `git ls-files -z` lists that are named `canon.py` and hold a line matching `^CANON_VERSION = "\d+"`, other than installed skill files and the `<dir>/scripts/canon.py` whose `<dir>/SKILL.md` has `name: canon` in its frontmatter. `init` at the repo root prints D004's `warning: ` line for each, before its change lines or `canon init: nothing to do`; `check` reports each as a `WARN` on the file, counted among its warnings.
- Hook: `PRE_COMMIT_HOOK` becomes D004's text. Every `init` at the repo root replaces a hook matching `^#!/bin/sh\nexec python3 \S+ check\n?$` and prints `updated <hook path>`; `init --hook` keeps any other existing hook and prints ``kept the existing pre-commit hook; add `canon.py check` to it``. Under `--hook`, a hook that cannot be written prints ``warning: cannot write the pre-commit hook: <reason>; rerun `canon.py init --hook` where .git is writable``, as when `git rev-parse --git-path` fails; without `--hook`, `init` warns only when an old hook it found cannot be replaced, and says nothing when it finds no hook path or no old hook.
- `CANON_VERSION` 48.

Repository: `AGENTS.md` says, outside the canon block, that in this repository agents and reviewers run `python3 skills/governance/canon/scripts/canon.py` instead of the path the block's Tool line names, and that a commit bumping `CANON_VERSION` reruns `init` here so the block records the new version; then `init` reruns here. The docstring of `check_canon_version` in `scripts/validate.py`, and the reason `AGENTS.md`'s Workflow gives for bumping `CANON_VERSION`, say projects record the version instead of upgrading a copy by it.

Test criteria; seam: the `init` and `check` command lines, their output and the files they write (`AGENTS.md`, `docs/README.md`, the hook):

1. `init` in a new repository writes no `canon.py`; the block holds the Tool line ``- Tool: `scripts/canon.py` of the `canon` skill installed in this project, `.agents/skills/canon/scripts/canon.py` as `npx skills` installs it, canon version <CANON_VERSION> or later, run from the repo root (`-h` lists commands).``, the command `npx skills add BigTailFox/skills@<tag> -s '*' -a claude-code -a codex -a cursor -y`, the `git ls-remote` line that finds `<tag>` and `npx skills experimental_install`; `docs/README.md` names `canon.py find <words>` and no `python3`. `init --script x` exits 2.
2. With a tracked `scripts/canon.py` holding `CANON_VERSION = "18"` and a block naming it, `init` leaves the file byte for byte, prints ``warning: the project no longer keeps a copy of canon.py; remove scripts/canon.py and replace `python3 scripts/canon.py` where files still name it, such as CI and each `docs/README.md` `` and rewrites the block; `check` then reports the same message, without `warning: `, as `WARN scripts/canon.py: …` among its warnings, and none once the file is removed from Git. `init --root <module>` prints no such warning.
3. No warning for an untracked copy, the harness's link at `.agents/skills/canon/scripts/canon.py` tracked with `git add -f`, a tracked `tools/canon/scripts/canon.py` beside `tools/canon/SKILL.md` with `name: canon`, or a tracked `lib/canon.py` without the version line.
4. A hook holding `#!/bin/sh\nexec python3 scripts/canon.py check\n` is replaced by D004's hook on `init` without `--hook`, which prints `updated .git/hooks/pre-commit`; a hook with another line added stays, and `init --hook` prints the kept message; `init --hook` in a repository without a hook writes D004's hook with mode 755; `init --root <module>` leaves the old hook. The hook run as `git commit` runs it exits 1 with D004's message in a checkout without the link, and runs `check` through it in one with it.
5. Where the hook cannot be written, as with a read-only hooks directory, `init --hook` finishes its other steps and prints the warning naming `canon.py init --hook`.
6. In this repository, `check` reports no old copy and `python3 scripts/validate.py` passes. Tests whose counts included the copy follow, such as `CoverageTest`'s module at the project directory, whose `./` area drops from 5 files to 4.

### S3: The project's version gates every command

Status: done

Risk: the check also runs before every command, so a parse that misreads the Tool line refuses every project or silences the check.

Builds on `D004#project-version`.

Changes in `canon.py`, tested in `tests/test_canon.py`:

- The recorded version is read from the `AGENTS.md` in S1's top, or outside Git in the working directory. Without that file or without a complete canon block in it, a start marker with an end marker after it, read without `canon_block_span`'s exit, no version check runs. In a complete block, `canon version (\d+) or later` in the block's first line starting with `- Tool:` gives the version, and a Tool line without it records none.
- `main()`, right after S1's check: a running `CANON_VERSION` below the recorded one exits 1 with D004's message. Above it, or with none recorded, D004's reminder goes to standard error, except under `check`, which reports it as `WARN AGENTS.md: <message without canon: >` counted among its warnings, and under `init` without `--root`, which prints nothing. Equal prints nothing.
- `CANON_VERSION` 49; `init` reruns here.

Test criteria; seam: any command's exit code, standard output, standard error and the files it changes:

1. With the block recording `canon version 9999 or later`: `which src/base.py`, `check`, `init`, `init --root <module>` and `trace status` exit 1 with ``canon: this project needs canon version 9999 or later, and this canon.py is version <m>; install a newer canon release as the canon block of AGENTS.md says`` and change no file; `-h` and `--version` run.
2. With `canon version 1 or later`: `find x` prints ``canon: this project is set up for canon version 1; run `/canon-init` to upgrade it to version <m>`` on standard error and its usual output; `check` prints `WARN AGENTS.md: this project is set up for canon version 1; …`, counts it, and prints nothing on standard error; `init` prints no reminder and rewrites the block to `<m>`, after which `check` has no such `WARN`; `init --root <module>` prints the reminder.
3. With a block whose Tool line is `python3 scripts/canon.py`, the reminder and the `WARN` read ``this project records no canon version; run `/canon-init` to upgrade it to version <m>``.
4. With the recorded version equal, `which src/base.py` prints nothing on standard error; without `AGENTS.md`, without a block, and with a start marker and no end marker after it, `which src/base.py` prints no reminder.
5. Started from outside the project with the block recording 9999, a command exits with S1's message.

### S4: Installed skill files are tooling

Status: done

Risk: the file matching that `which`, `affected`, `audit`'s unchecked commits and coverage share; a wrong predicate hides governed code from its design or counts installed skills as uncovered code.

Builds on `D002#installed-skills`, `D002#project-docs`, `D002#unchecked-commits-in-audit`, `D002#coverage-in-audit`, D002's Delivery step 7 and its installed-skills scenario, `D006#layout` and `D010#which`.

Changes in `canon.py`, tested in `tests/test_canon.py`:

- `is_doc` is false for an installed skill file; `designs_for` and `unchecked_commits` match an installed skill file only through an entry equal to its path, as they match a doc; `cmd_which` prints `<path>: skill` before trying `doc`, and its help names `skill`; `Repo` takes no project root from an `AGENTS.md` that is an installed skill file; `coverage_report` skips installed skill files.
- `skills/governance/canon/SKILL.md`: the `which` row of the Tool table names `skill`.
- `CANON_VERSION` 50; `init` reruns here.

Test criteria; seam: the `which`, `affected`, `audit` and `check` command lines and their output, through the tree of D002's scenario, committed and again untracked: `.agents/skills/canon/SKILL.md`, `.agents/skills/canon-tdd/LICENSE`, `skills-lock.json` and the link `.claude/skills/canon` pointing at `../../.agents/skills/canon`, beside the harness's link at `.agents/skills/canon/scripts/canon.py`, tracked with `git add -f` where the criterion commits it (S1):

1. `which` prints `.agents/skills/canon/SKILL.md: skill` for that file and for `.claude/skills/canon/SKILL.md`, `skills-lock.json: skill` and `.agents/skills/canon-tdd/LICENSE: skill`, and `no design` for the same `SKILL.md` copied to `.cursor/skills/canon/SKILL.md`. A design whose `paths` list `.agents/skills/canon/SKILL.md` governs it; one whose `paths` hold `**` or `.agents/**` does not.
2. With D000's Modules Path `./`, `audit` lists no area under `.agents/` or `.claude/` and not `skills-lock.json`.
3. With a design whose `paths` hold `.claude/**`, `affected` lists no file of the install, named on the command line or found as changed files.
4. A commit that changes only `.agents/skills/canon/scripts/canon.py`, by retargeting the tracked link, is no unchecked commit of a design whose `paths` hold `**/*.py`; one that also changes `src/a.py` is.
5. An `AGENTS.md` under `.agents/skills/canon/` adds no docs root: `which .agents/skills/canon/docs/x.md` prints `skill`, and `check` reports no project there.

### S5: Agents install canon in the project and run its canon.py

Status: done

Builds on `D004#spec` (the intro), `D004#install` (the agent's flow), `D004#project-version`, `D004#the-canon-init-skill` and `D000#dependencies`.

Skill text:

- `skills/governance/canon/SKILL.md`, Tool: run this skill's own `scripts/canon.py`, the one installed in the project; a subagent given only a prompt runs the one the Tool line of `AGENTS.md` names. When `canon.py` refuses to run from outside the project, the agent asks whether to install canon in the project, installs on a yes with the commands of the canon block, asks whether to remove a user install with `npx skills remove -g` and the canon skills' names when one exists, and then reads the skills it follows again from the project's install; a refusal as older than the project asks the same about a newer release. Any Tool table row that names a copy or `--script` follows.
- `canon-design`, `canon-plan`, `canon-implement`, `canon-review`, `canon-retro` and `canon-sync`: `canon.py` means the `canon` skill's `scripts/canon.py`, as its Tool section says; `canon-grill`'s line on creating a concept says the same.
- `canon-init`: its frontmatter `description` says it upgrades the project's canon install, not its `canon.py`; the preamble drops `<canon>/scripts/canon.py` and `<copy>`, and says a first run from a user install refuses and installs first as the `canon` skill says; the flow choice runs Upgrade when the project's version is below `canon.py --version` or not recorded; Setup steps 2, 3, 4, 9 and 12, Upgrade and Add a module as D004 states.
- `canon-sync`, step 1: look for a newer release than `skills-lock.json` records for `canon`, found as D004's Install finds the newest, and offer to install it and run `canon-init`'s Upgrade.

Repository:

- `README.md`: Install installs canon in each project, pinned, with D004's commands, explains committing the skills or only `skills-lock.json` with `npx skills experimental_install`, and removing a user install with `npx skills remove -g`; trying unpushed changes installs from the local path in a scratch project. The `-g` instructions go, as the D004 r5 gate's confirmation round deferred to this plan. Tracing's commands run `.agents/skills/canon/scripts/canon.py`, and its sentence on a project whose `canon.py` predates tracing follows. The Skills table summary of `canon-init` says it upgrades the project's canon install.
- `AGENTS.md`, Skill rules: a canon skill runs the `scripts/canon.py` of the `canon` skill it follows, and a reviewer the one `AGENTS.md` names.

Test criteria; seam: the skill texts as installed, `validate.py`, `npx skills` and a scratch project:

1. `python3 scripts/validate.py` passes with D001's text budgets measured, and `npx skills add . --list` lists every skill once.
2. `rg` finds in `skills/` and `README.md` no "project copy", `<copy>`, `--script`, and no `-g` but in `npx skills remove -g`.
3. In a scratch repository under `.tmp/`, `npx skills add <this repository> -s '*' -a claude-code -a codex -a cursor -y` puts the skills in `.agents/skills/` and links them from `.claude/skills/`; `python3 .agents/skills/canon/scripts/canon.py init` sets the project up with the Tool line and runs `check`; the working tree's `canon.py` run there refuses with S1's message.

### S6: This repository runs its skills from the working tree

Status: done

Builds on `D000#dependencies` (this repository's agents and reviewers run the working tree's `canon.py`) and `D004#install` (where `npx skills` puts a project install).

Changes, in the repository only:

- This repository loads its own skills from the working tree, the user's decision: `.agents/skills/<name>` links to `../../skills/<category>/<name>` and `.claude/skills/<name>` to `../../.agents/skills/<name>`, so agents follow the texts being developed and the canon block's Tool line reaches the working tree's `canon.py`. `.gitignore` gains `.claude/skills/` beside its `.agents/` and `skills-lock.json` lines.
- `AGENTS.md`'s Workflow gives the zsh command that creates the links, to run once per checkout and again after adding or removing a skill. It sets up this checkout for development and installs nothing for users, who install with `npx skills`, so it is no install script in the sense of `AGENTS.md`'s rule.

Test criteria; seam: the checkout after the command, `npx skills`, `validate.py` and `canon.py` run through the link:

1. `git status --porcelain` shows nothing new, `python3 scripts/validate.py` passes, and `npx skills add . --list` lists every skill once; a scratch run with one linked skill already listed it once.
2. `python3 .agents/skills/canon/scripts/canon.py --version` prints the working tree's version, and `check` through that path runs and reports as through the working tree's path.
3. `which .agents/skills/canon/SKILL.md` resolves the link and prints the designs that govern `skills/governance/canon/SKILL.md`, since the source stays code here; S4 covers `skill` on a real install.

## Notes

- Every slice that changes `canon.py` bumps `CANON_VERSION`, since `validate.py` compares it with the commit that set the version, and reruns `init` here after the bump; from S3 on, a bump not yet recorded makes every command here print the reminder until `init` reruns.
- Run `validate.py` with the system's default `TMPDIR`. The harness's link and its `info/exclude` line are what keep `git status` clean in the tests; a test that writes `info/exclude` itself appends to it.
- The canon block's template, for S2, before review in the code review:

  ```markdown
  ## Docs

  This repo follows the canon documentation system, run from the `canon` skill installed in this project. Without that skill, or when its `canon.py` says it runs only from an install inside the project or that the project needs a newer canon version, ask the user whether to install canon here. At the repo root, `npx skills experimental_install` restores the release `skills-lock.json` records for `canon`; for the newest release, run `npx skills add BigTailFox/skills@<tag> -s '*' -a claude-code -a codex -a cursor -y`, where `<tag>` is the name after `refs/tags/` on the first line of `git ls-remote --tags --refs --sort=-v:refname https://github.com/BigTailFox/skills 'v*'`. Engineering docs live in `docs/` and in module `docs/` directories. Start at [D000: Project overview](docs/designs/D000-project-overview.md); [docs/README.md](docs/README.md) indexes every doc.

  - Tool: `scripts/canon.py` of the `canon` skill installed in this project, `.agents/skills/canon/scripts/canon.py` as `npx skills` installs it, canon version {version} or later, run from the repo root (`-h` lists commands). Run `check --fix` before committing and after every merge or rebase.
  ```

  The three bullets after the Tool line stay as they are.
- Details the plan settles that the designs leave unstated, for the docs step to write into D004 and D002: the version check reads the `AGENTS.md` in the top the location check finds, or outside Git in the working directory, so it runs no Git command either; a link counts as an installed skill file by its target in the work tree, `.agents/skills` itself or a path under it, compared with `.agents/skills` unresolved, so a commit's path that is no link there counts by its path alone and a linked `.agents/skills` leaves its target's files their own kind; `new` and `adopt`, walking up to a project, pass an `AGENTS.md` among installed skill files; `init --hook` keeps an existing hook it cannot read, with the kept message; the old hook's path is a run of non-whitespace and its final newline is optional; `init` prints its old-copy warnings before its change lines. D001§commands, which says every `trace` subcommand exits 0 unless its arguments are invalid, gets a reference to D004's two checks.
- The cross-family reviewer and the reviewer prompt of `canon-blind-review` keep running the `canon.py` that `AGENTS.md` names; in this repository that note outside the block, from S2, names the working tree's.
- Rollout, after the docs step and outside this plan: release 0.6.0 with its `CHANGELOG.md` entry, tagging and pushing only once the user confirms. On this machine, migrate in one pass rather than updating the user install: Claude Code runs a user install over the project's ([E001: Precedence of project and user skills across hosts](../../experiments/E001-skill-scope-precedence.md)), so an updated user install would refuse in every project, migrated ones included. First remove the user install with `npx skills remove -g` and the canon skills' names, then in each project install the release at the repo root with README's command and run `/canon-init`, whose Upgrade finds the copy. A project not yet migrated keeps its copy and its old block, which says to install with `npx skills add … -g`; install in the project instead, or the user install comes back. The `CHANGELOG.md` entry gives users the same steps.
- The docs step sets `implemented` to D004 5, D000 4, D002 10, D006 10 and D010 2, and gives R003-F31 its disposition.

## Log

- Drafted from D004 r5 and its follow-ons at 1300ed7.
- S6: this repository loads its skills through links to the working tree rather than a copy from `npx skills add .`, stale after each edit, or a pinned release, whose texts lag the code and whose `canon.py` refuses once the block records a newer version (the user's decision).
- Review gate r1 (claude-opus-5.5, gemini-4-argon-high): accepted every finding, seven from the same-model reviewer and four from the cross-family reviewer, which overlapped on all but `PruneTest` and `CoverageTest`. The fixes cover the `list` command `canon.py` lacks, the harness link shared with the S2 and S4 fixtures and with `PruneTest`, `CoverageTest`'s count without the copy, S6's `which` criterion, the stale help texts and `canon-init` description, the silent hook lookup without `--hook`, the version check needing a complete block, and a one-pass rollout. Both reviewers confirmed the fixes.
- 2026-11-12: The user approved this plan at 4cc4c2e. Started at 4cc4c2e.
- S1 done: `require_project_install()` in `main()` after `parse_args`, `CANON_VERSION` 47; the harness starts the link at `<top>/.agents/skills/canon/scripts/canon.py`, rechecks its `info/exclude` line on every call, passes the working directory unresolved and creates no link under `script=`; `SnapshotTest` appends to `info/exclude`. Criteria 1 and 6 went red first; criteria 2 to 5 held already, so a scratch mutation script applied six wrong rules in turn (resolved start path, string comparison, `AGENTS.md` before `.git`, `git rev-parse`, any ancestor outside Git, no check), each turning a test red. 269 tests pass with the default `TMPDIR`; `init` here had nothing to do.
- S2 done: `init` keeps no copy, writes the Notes' block with `canon version 48 or later`, and warns of old copies found by `old_copies()`, which `check` reports as `WARN`; `OLD_HOOK_RE` finds the old hook, which every root `init` replaces in place, keeping its mode. The exemption rules and the hook rules each passed a scratch mutation run of seven wrong rules. Review found that `old_copies` read the parent directory name from the absolute path, so a repository directory named `scripts` exempted a root `canon.py` by a `SKILL.md` outside the repository; it now reads the repo-relative path, with a regression test. For the code review: an unreadable hook under `--hook` gets the cannot-write warning, and stays silent without it. `init` here rewrote the block to version 48; the suite passes with the default `TMPDIR`.
- S3 done: `require_project_install()` returns the top whose `AGENTS.md` `project_version_notice()` reads, through `marker_span` so an incomplete block skips the check; versions compare as integers; `CANON_VERSION` 49. Deviation: the plan said `init` without `--root` prints no reminder, D004 says `init` at the repo root, so an `init --root` naming the repo root is silent too, as D004 has it; a module's `init --root` reminds. Criteria 1 and 2 went red first; a scratch mutation run of fifteen wrong rules all turned tests red. `init` here rewrote the block to version 49.
- S4 done: `Repo.is_code` (neither doc nor installed skill file) drives `designs_for`, `unchecked_commits` and coverage, and `Doc.governs`' `doc_file` became `exact`; `which` prints `skill` first; an installed `AGENTS.md` makes no root; `CANON_VERSION` 50. Each test runs on the install untracked and committed, the harness link added with `git add -f`; criterion 3's design also holds `.agents/**` and `*.json`, since `which` and `affected` resolve `.claude/...` to `.agents/...`. A scratch mutation run of nine wrong rules turned tests red but for dropping `is_doc`'s own exclusion, which every caller already covers; it stays, as D002 states it. For the code review: `is_installed_skill` resolves two real paths per call, about 1.6 s per 100k tracked files in coverage; the `canon` skill does not yet define an installed skill file, for S5. 279 tests pass; `init` here rewrote the block to version 50.
- S5 done: skill texts, README and `AGENTS.md`'s Skill rules as the slice lists. Additions: the `canon` skill's Layout defines an installed skill file (S4's Log); its Tool section gives the install commands in full, since a first `/canon-init` from a user install finds no canon block yet; whether a user install exists is read from `~/.agents/skills/` or `~/.claude/skills/`, and README removes it with `npx skills remove -g $(ls ~/.agents/skills | grep -E '^canon(-|$)')`, which picked exactly the 19 canon skills on this machine. No automated test: criteria 2 and 3 ran as a scratch script, red before the texts changed, green after, the scratch project under `.tmp/`. `validate.py` measured D001's budgets. For the code review: `canon-retro`'s `skill_hash` reads the global lock before the project's `skills-lock.json`, which project installs may want reversed; D004 does not cover it.
- S6 done: `AGENTS.md` gives the zsh command, which also drops links of removed skills; `.gitignore` adds `.claude/skills/`; the links exist in this checkout, and `.agents/skills/canon/scripts/canon.py --version` prints the working tree's. Beyond the plan, `LinkedSkillSourceTest` keeps criterion 3 tested without the links: `which` through a link into the skill source prints the source's designs; it held at once, and a scratch mutation run of two wrong rules turned it red. For the code review: a plain `npx skills add .` at this repo's root replaces the links with stale copies, and the two worktrees under `.worktrees/` have no links yet. 283 tests pass.
- Code review from 4cc4c2e (claude-opus-5.5 on Spec and Standards, gemini-4-argon-high cross-family): all three approved, with minor findings only. Fixed, `CANON_VERSION` 51: the installed-skill rule, the `new` and `adopt` walks and the unreadable hook as the Notes now state them; `main()` hands the version reminder to every command and `init` decides by its own top; constants name the install directory and the old-copy warning; the harness checks the working directory under `script=` too; README removes a user install from `~/.claude/skills/` as well; `canon-retro` reads `skill_hash` from the project's `skills-lock.json` alone, since canon runs only from the project's install; `AGENTS.md` and `validate.py` drop a contrast with the copy. Declined: rewording 8ab23e4's scope to `repo`, which rewrites history for a label; later commits that change several skills use `repo`. 286 tests pass.
- Docs step from 4cc4c2e: the Notes' details went into D004§install, §project-version, §init and §adopt and D006§templates-and-new, and D001§commands names D004's two checks among a `trace` call's failures; `implemented` is D000 4, D002 10, D004 5, D006 10 and D010 2; R003-F31 is fixed. `.gitignore` and `scripts/validate.py` changed with no design owning them and nothing callers rely on.
