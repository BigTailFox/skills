---
status: accepted
created: 2026-11-13
updated: 2026-11-13
revision: 1
modules: [canon]
summary: check --rev and --staged, index --staged and stale index levels, check of named docs, init's hook and .worktrees/, worktree trace data, concurrent-work texts.
refs: [D006, D005, D004, D003, D001]
based_on: [D006@r19, D005@r3, D004@r7, D003@r8, D001@r13]
reviewed: 1
reviewers: [claude-opus-5.5, gpt-5.6-sol-high]
approved: 1
---

# P006: Concurrent work and staged checks

Implements [D006: Doc model and writing rules](../designs/D006-doc-model.md) r19 and its follow-ons [D005: Docs index](../designs/D005-docs-index.md) r3, [D004: Project setup](../designs/D004-project-setup.md) r7, [D003: Subagents](../designs/D003-subagents.md) r8 and [D001: Skill telemetry with canon trace](../designs/D001-skill-telemetry.md) r13, which passed one gate together, D006 r19 through its follow-up round. Each design's `implemented` equals its revision at f9479a6, D006 16, D005 2, D004 6, D003 7 and D001 12, so the work is each design's Spec diff from f9479a6 to f37509b.

## Current state

Next: S1.

## Slices

### S1: Check a commit with `--rev`

Status: todo

Risk: every rule that reads a file must read the tree checked, and a read left on the work tree passes or fails a commit by files it does not hold; the reads run per doc, so one Git process per read would make `check` slow in a large repository.

Builds on `D006#check`, `D006#ids-and-file-names` and `D006#layout`.

Changes in `skills/governance/canon/scripts/canon.py`, tested in `tests/test_canon.py`:

- A tree reader that `Repo` and the rules read through, the work tree as now or a Git tree. The Git tree lists REV's entries once with `git ls-tree -r -z --full-tree <REV>` and reads blobs through one `git cat-file --batch` process. Every read of `check` goes through the reader: the file list, doc text, the heading slugs anchors resolve against, whether a link target exists, the index files and their markers, `AGENTS.md` and the other `.md` files `check` scans, D000's `paths` and Modules Paths, `paths` matching, installed skill files and old copies. Paths stay absolute under the repo root, so `by_path` and every message stay as they are.
- In the Git tree, a directory exists when the tree holds a file below it. A symbolic link (mode 120000) resolves component by component, as `realpath` does, so links to directories and links within a path both count; its blob is a path relative to the link's directory, at most 40 links are followed, and a target outside the tree or missing makes it no file. A submodule (mode 160000) is no file.
- `check --rev REV`, which ends before reading any doc with the first of D006's errors that applies: `--fix` with `--rev`, outside Git, a REV that names no commit or starts with `-`, and a REV that the file `git rev-parse --git-path shallow` names lists. The flags are checked before `main` builds the work tree's `Repo`.
- Under `--rev`, the commit compared for `updated` and for deleted docs is REV's parent when REV has exactly one; a root or merge commit gets neither check. The day of the check is either date `git log -1 --format=%ad%n%cd --date=short REV` prints.
- With `--base`, the tip is REV under `--rev`: the merge base, the collision check and the branch's deleted docs run from REV, `no merge base` without a HEAD commit applies only without `--rev`, and `cannot diff against <REF>...<tip>` names REV.
- When Git fails to list the tree, read a blob, a `missing` reply of `cat-file --batch` included, or look REV's parents or dates up, `check` ends with `canon: git <subcommand> failed in <dir>: <reason>`, as `git_checked` ends other calls, rather than read the failure as an empty result.
- The `; <n> fixable with --fix` tail only on the work tree. Unfinished-level problems and pending reviews keep their work-tree level unless `--base` is given, and the version `WARN` appears as on the work tree.
- The `check` row of the `canon` skill's Tool table gains `--rev REV`.
- `CANON_VERSION` 58.

Test criteria; seam: the `check` command line, its output and exit status, in a test repository whose work tree differs from REV:

1. For each kind of read, `check --rev <commit>` reports the problem a commit holds while `check` on the fixed work tree does not, and reports none for a clean commit while the work tree holds it: a doc's missing section, a link to a file only the work tree holds, an anchor only the work tree's target has, a stale index, a broken link in `AGENTS.md`, one in a guide and one in an `.md` file of a doc's attachment directory, an untracked doc with an error, and, each as its `WARN`, a design `paths` entry that matches a file only the work tree holds, a D000 `paths` entry and a D000 Modules Path that are directories only in the work tree, and an old copy of `canon.py` only the work tree holds. Errors set the exit status and warnings do not.
2. A link through a committed symbolic link to a file in the tree passes, and so does one through a linked directory; a link through a symbolic link to a path outside the tree or to a missing one is broken, as is one through a chain of 41 links and one to a submodule's path. An `AGENTS.md` under `.agents/skills/`, and one reached through a committed link `.claude/skills/<name>` to `../../.agents/skills/<name>`, makes no project under `--rev`, as on the work tree.
3. A commit that changes a doc's content without bumping `updated` fails with ``content changed but `updated` was not bumped``, unless `updated` equals its author date or its committer date, set with `GIT_AUTHOR_DATE` and `GIT_COMMITTER_DATE`. The root commit and a merge commit get no such error.
4. A commit that deletes a doc fails with `was deleted`, one that renames it passes, and a merge commit that drops one gets no such error. With HEAD on another branch, `check --rev <commit> --base main` reports the collision of a doc the commit's branch added with one main added since their merge base.
5. Each error exits 1 with D006's message and leaves the files unchanged: `--fix --rev HEAD`, `--rev HEAD` outside Git, `--rev nosuch`, `--rev=-x`, and `--rev HEAD` in a clone made with `git clone --depth 1` from the test repository's `file://` URL, whose HEAD has a parent. `--fix --rev nosuch` gives the `--fix` message.
6. A commit with a fixable problem gets no fixable tail under `--rev`. With the work tree's canon block recording an older version than REV's, `--rev` adds the version `WARN` naming the work tree's version.
7. With a stand-in `git` that fails `ls-tree`, `cat-file` or `log` (as `GitFailureTest` fails other calls), and with the loose object of a committed doc's blob deleted, `check --rev HEAD` ends with `canon: git <subcommand> failed in <dir>: <reason>` and exit 1.

### S2: Check the staged tree with `--staged`

Status: todo

Risk: in a pre-commit hook, Git points `GIT_INDEX_FILE` at a temporary index or at `index.lock`, so a read of the default index, or a Git call that drops the variable, checks something other than the commit.

Builds on `D006#check` and `D006#ids-and-file-names`.

Changes in `canon.py` and `tests/test_canon.py`:

- The staged Git tree, read with S1's reader from the stage-0 entries `git ls-files -s -z` lists, which honors `GIT_INDEX_FILE`, other than intent-to-add entries, found as the Notes say.
- `check --staged`, which ends before reading any doc with the first of D006's errors that applies: both `--staged` and `--rev`, `--fix` with either, either outside Git, then S1's ref errors, and unmerged entries under `--staged` (`git ls-files -u` lists any).
- Under `--staged`, the commit compared for `updated` and for deleted docs is HEAD, when there is one, as for the work tree. The docs whose `updated` is compared are those the staged tree changes against HEAD, from the `git diff --cached --name-status --no-renames` the intent-to-add test reads, not `changed_files`, which diffs the work tree.
- Failures of `git ls-files -s`, `git ls-files -u` and `git diff --cached` end `check` as S1's Git failures do.
- The `check` row of the Tool table gains `--staged`.
- `CANON_VERSION` 59, the first version whose `check` takes `--staged`, which S5's hook compares with.

Test criteria; seam: the `check --staged` command line, and a pre-commit hook the test writes to run it, through real `git commit` calls:

1. A doc error only in the work tree passes `check --staged`; one staged, then fixed in the work tree, fails it.
2. With the hook: `git commit -m x <path>` of a clean doc commits while another doc's staged change holds an error; `git commit -a` fails on an error in a tracked doc's work-tree content; `git commit` with no paths fails on a staged error. All three hold in a linked worktree at `.worktrees/b`.
3. A staged content change that keeps `updated` fails against HEAD, also once the work tree's copy is reverted to HEAD's; `git rm` of a doc fails with `was deleted` and `git mv` passes; on an unborn branch neither check runs.
4. A doc added with `git add -N` is no file: its errors go unreported and a staged link to it is broken. A path HEAD holds that `git rm --cached` and then `git add -N` leave as an intent-to-add entry counts as deleted. A staged empty doc, new or emptied, and an empty doc HEAD already holds are files: each fails with ``missing or unterminated `---` frontmatter``.
5. Each error exits 1 with D006's message and leaves the files and `git ls-files -s` unchanged: `--staged --rev HEAD`, `--fix --staged`, `--staged` outside Git, and `--staged` during a merge that left a conflict.
6. A staged fixable problem gets no fixable tail.
7. With a stand-in `git` that fails `ls-files` or `diff`, `check --staged` ends with `canon: git <subcommand> failed in <dir>: <reason>` and exit 1.

### S3: Index levels and `index --staged`

Status: todo

Risk: `index --staged` writes the Git index, so staging any file but the index files, or a work-tree blob or mode, puts work the commit leaves out into it.

Builds on `D005#regeneration` and `D005#check`.

Changes in `canon.py` and `tests/test_canon.py`:

- `index out of date` is an `ERROR` under `--staged`, `--rev` and `--base`, the message adding `; stage the commit's files, run canon.py index --staged and commit with no paths` under `--staged`, and a `WARN` on the work tree, which `--fix` still fixes. An index's links are checked only while it is up to date, as now.
- `canon.py index [--staged]`. With `--staged`, it computes each index file of the staged tree from the staged docs and the staged `docs/README.md`, reading them with S2's reader; writes each one whose staged entry is missing or differs with `git hash-object -w --stdin`; stages it with `git update-index --add --cacheinfo <mode>,<blob>,<path>`, keeping a staged mode of `100644` or `100755` and else using `100644`; prints `staged <path>`; then writes the work tree's index files as `index` does, printing `wrote <path>`.
- Before changing any file or staging anything, `index --staged` ends with the first of D005's refusals that applies: outside Git, unmerged entries, a staged `docs/README.md` with a start marker and no end marker after it, then a work-tree one. A failing `hash-object` or `update-index` ends it with `canon: git <subcommand> failed in <dir>: <reason>`.
- Existing tests that expect `ERROR ... index out of date` from `check` on the work tree expect the `WARN`.
- The `index` row of the Tool table reads `index [--staged]`.
- `CANON_VERSION` 60.

Test criteria; seam: the `index --staged` and `check` command lines, `git ls-files -s`, `git show :<path>` and real commits:

1. A stale work-tree index gives `WARN docs/README.md: index out of date`, counted as fixable, and `check` exits 0 when nothing else fails; `check --fix` regenerates it. A commit with a stale index fails `check --rev` and `check --base main` with the `ERROR`; a stale staged index fails `check --staged` with the `ERROR` and its added text.
2. With two new docs and one of them staged, `index --staged` prints `staged docs/README.md`, the staged README lists only the staged doc and the work tree's lists both. `check --staged` then passes, and `git commit` with no paths records a commit that passes `check --rev HEAD`.
3. After `index --staged`, `git diff --cached --name-only` lists only the staged doc and the index files; a README staged with mode `100755` keeps that mode; a staged archived doc gets a staged `docs/archived/README.md`. A second run stages and prints nothing.
4. Each refusal exits 1 with D005's message and leaves `git ls-files -s` and the work tree unchanged: outside Git, during a merge that left a conflict, a staged README with a start marker and no end marker while the work tree's is intact, and the reverse.

### S4: Check named docs

Status: todo

Builds on `D006#check`.

Changes in `canon.py` and `tests/test_canon.py`:

- `check [ID|PATH ...]`. An argument of the id form names the doc `archive` would resolve; any other names the doc whose file it is, relative to the working directory; else `check` ends with `canon: <arg> names no doc; give a doc id or the path of a doc file`. A doc named twice counts once.
- With doc arguments, `check` reports only the problems on the named docs' files and on the `.md` files in their attachment directories. A duplicate id or owned topic counts as on each doc it involves, although `check` records it on one. The version `WARN` stays, since D006 adds it in every form of `check`. The summary line counts the named docs, and the exit status follows the errors reported.
- With doc arguments, `--fix` applies only the fixes of the problems it reports, does not exit on a broken index marker and regenerates no index, then checks the named docs again and prints that result.
- Doc arguments with `--base`, `--staged` or `--rev` end `check` with D006's message, in D006's order after the two errors of flags alone.
- The `check` row of the Tool table gains `[ID|PATH ...]`.
- `CANON_VERSION` 61.

Test criteria; seam: the `check` command line with doc arguments:

1. With an error in each of two docs, `check <first id>` reports only the first doc's, counts 1 doc in its summary and exits 1; naming a clean doc exits 0. A broken link in an `.md` file of the named doc's attachment directory is reported; problems in `AGENTS.md`, a guide, the index and a deleted doc are not, while the version `WARN` of a canon block recording an older version still is.
2. With two designs owning one topic, naming either reports the duplicate; with two docs sharing an id, naming either by path reports it.
3. `check --fix <id>` fixes that doc's `refs` and `updated` and prints them, leaves another doc's fixable problem and a stale index as they were, and runs although `docs/README.md` has a start marker and no end marker.
4. From a subdirectory, a path relative to it names the doc. `check nosuch` and `check src/base.py` end with the names-no-doc message, `check D001 --staged` with the doc-arguments message, and `check D001 --staged --fix` with the `--fix` one.

### S5: `init`'s `.worktrees/` line and staged hook

Status: todo

Risk: Git runs one pre-commit hook for every worktree and branch of a repository, so a hook that fails on an older install, or a replaced hook the user wrote, blocks commits in all of them.

Builds on `D004#init`.

Changes in `canon.py`, `tests/test_canon.py` and the `canon-init` skill:

- `.gitignore` gets `.worktrees/` unless a line names `.worktrees` with or without slashes, as it gets `.canon/`.
- The hook is D004's template, `<V>` being 59.
- Every `init` at the repo root replaces version 57's hook, byte for byte the template that version wrote, and the copy hook `OLD_HOOK_RE` matches, printing `updated <hook path>`. The kept message reads ``kept the existing pre-commit hook; add `canon.py check --staged` to it``.
- `canon-init`'s Upgrade says `init` replaces a pre-commit hook an earlier version wrote, not only one that ran a copy.
- `CANON_VERSION` 62.

Test criteria; seam: `init`'s output and the files it writes, and real `git commit` calls running the hook:

1. `init` adds `.worktrees/` to a `.gitignore` without it, and leaves one naming `/.worktrees` or `.worktrees/` unchanged.
2. `init --hook` writes the template with mode 755. With it, `git commit` of clean staged docs succeeds while a work-tree doc holds an error, and a staged error blocks the commit.
3. With the install replaced by a stub `canon.py` that prints `canon 58` for `--version` and logs its arguments, the hook runs `check`; with no install, it prints the no-skill message and exits 1; with a stub whose `--version` fails, it exits 1.
4. Root `init`, with and without `--hook`, replaces version 57's hook and the copy hook, printing `updated <hook path>`. An edited hook stays, `init --hook` printing the kept message, and `init --root <module>` replaces neither.

### S6: Trace data of worktrees in `.worktrees/`

Status: todo

Risk: data location. A wrong rule splits a session's units across two trace directories, or keeps them where removing the worktree deletes them; the fallback's write test must leave no file behind, and locating must still run no Git command.

Builds on `D001#switch-and-storage`, `D001#commands` and `D001#delivery-and-acceptance`.

Changes in `canon.py`, `tests/test_canon.py` and `README.md`:

- The trace directory is found from the checkout root as now, then from `<R>` when the root's `.git` is a file whose `gitdir:` line names a directory directly inside one named `worktrees`, and the root lies under `<R>/.worktrees/` where `<R>` holds `.git`. The `.git` file is read without Git.
- When tracing is on with `<R>`'s trace directory and a call cannot create that directory or a file in it, the call uses the checkout root's own trace directory, its `off` file included. The test creates a uniquely named file and deletes it.
- `start`, `end`, `status`, `prune` and `on`/`off --here` use that trace directory, and `start` and `off --here` write `.canon/canon/.gitignore` in the checkout that holds it. Snapshots, `DOC` lookups, `--base`, `--dir` and the `snapshot` command keep the checkout root.
- `README.md`'s Tracing section, which says every linked worktree has its own trace directory, says instead that the worktrees in `.worktrees/` share their main checkout's, `off` file included, so removing one keeps its units; that a call that cannot write there uses the worktree's own; and that every other checkout has its own.
- `CANON_VERSION` 63.

Test criteria; seam: the `trace` and `snapshot` command lines with the machine switch on, the trace directory's `events.jsonl`, and the snapshot repositories:

1. In a worktree made with `git worktree add --track -b b .worktrees/b main`, `start` and `end` append to the main checkout's `events.jsonl` and `status` lists the open unit. The unit's snapshot holds the worktree's files, a change staged only there included; a `DOC` only the branch holds resolves; and `end --dir .canon/x` archives the worktree's file. Afterwards no file the write test made remains in the main checkout's trace directory.
2. The main checkout's `off` file turns tracing off in the worktree, `off --here` in the worktree creates that file and `on --here` deletes it.
3. With the main checkout's `.canon/canon/` read-only, skipped when the tests run as root, `start` in the worktree writes the worktree's own trace directory and leaves no file in the main checkout's.
4. Run in the worktree, `prune` deletes an old unit's archive and snapshot from the main checkout's trace directory, and, with the main checkout's `.canon/canon/` read-only, skipped as in criterion 3 when the tests run as root, from the worktree's own, leaving the other directory's as they were.
5. A linked worktree outside `.worktrees/`, and a submodule inside `.worktrees/b`, each use their own trace directory.
6. `snapshot` in the worktree records into the worktree's `.canon/canon/snapshots/`.
7. With tracing off, the worktree's calls run no Git command, as `test_tracing_off_writes_nothing_and_runs_no_git` checks for a checkout.

### S7: Concurrent work in the skill texts

Status: todo

Builds on `D006#concurrent-work`, `D006#layout`, `D003#launch` and `D003#resuming-and-replacing`.

Changes in the skill texts; no `canon.py` change:

- The `canon` skill's `SKILL.md`: Layout shows `.worktrees/<branch>/`, ignored as `.canon/` is. Rules state D006's concurrent work:
  - when a session takes a worktree, and the question it asks when `git status --porcelain` shows changes nobody told it about;
  - the `git worktree add --track` command, and the `info/exclude` line when `.worktrees/` is not ignored;
  - the worktree's own install;
  - what a shared checkout shares, and what a session told late does;
  - the change staying in the worktree, with the worktree's path in every handoff and next-phase command;
  - updating the branch from its upstream with `check --fix` and `renumber` before it goes back, and leaving merging and removal to the user;
  - subagents in the session's worktree, with its root first in every prompt and a reviewer's command run from it;
  - one session staging at a time per checkout, and subagents checking only their docs with `check <ids> [--fix]`;
  - the four steps of a partial commit.

  The paragraph on giving the user commands names the worktree's path beside the command.
- `canon-implement`: stash messages start with `<P id> S<n>` and a stash is found by its message, never by its `stash@{<n>}` position; the worker prompt starts with the worktree's root when the session works in a linked worktree, and tells a worker that edits a numbered doc to check it with `canon.py check <id> --fix`.
- `canon-blind-review`: the template starts with the worktree's root when the session works in a linked worktree, in every round, and a reviewer's command runs from that root.
- `canon-handoff`: Position names the worktree's path, and the next agent's prompt reads `In <worktree path>, read <path> and continue.`
- `canon-research`: the brief has the researcher run `canon.py check {E00X} --fix` and fix that doc's errors.

Test criteria; seam: the skill texts, checked by `validate.py` and by the code review's Spec axis:

1. `python3 scripts/validate.py` passes with D001's text budgets measured, and `npx skills add . --list` lists every skill.
2. Each bullet of `D006#concurrent-work`, the partial commit's four steps included, has its agent-facing statement in the `canon` skill's Rules, and no canon skill text locates a stash by its position.
3. The prompt templates of `canon-blind-review` and `canon-implement` carry the worktree line; every other subagent prompt follows the `canon` skill's Rules.

## Notes

- The staged tree leaves out intent-to-add entries (`D006#check`, r19). An entry holding the empty blob is one when `git diff --cached --name-status --no-renames` lists its path as deleted while HEAD holds it, or does not list it as added while HEAD lacks it: that porcelain diff ignores such entries, and on an unborn branch it runs against the empty tree. `git ls-files -s` shows no difference, and `git ls-files --debug` flags are no stable interface.
- `main` checks `check`'s flag combinations, and S4 its doc arguments, before building any `Repo`, so they end `check` before any doc is read, in D006's order. They are canon's own messages, not argparse's mutually exclusive group, whose message D006 does not use.
- Commands other than `check` and `index --staged` read the work tree as now, and only the work tree's form of `check` applies fixes or writes files.
- Every slice that changes `canon.py` bumps `CANON_VERSION`, since `validate.py` compares it with the commit that set the version, and reruns `init` at the worktree's root in the same commit, so the canon block records it. Here `init` finds `.worktrees/` in `.gitignore` already and no pre-commit hook. If the slices change order, the hook's `<V>` stays the version of the slice that adds `--staged`.
- Tests run through the `canon.py` command line in `CanonTest` repositories, the seam every existing test uses. A test that needs a linked worktree makes it at `.worktrees/<branch>` inside its test repository; one that makes a directory read-only restores it in a cleanup. Every test passes alone and beside any other, and `validate.py` runs with the system's default `TMPDIR`.
- Details the plan settles that the designs leave unstated, for the docs step to write into them: in D006, symbolic links resolve component by component, the flag errors come before the work tree is read too, `updated` under `--staged` compares the docs the staged tree changes against HEAD, and a doc named twice counts once; in D005, a failing `hash-object` or `update-index` ends `index --staged` with D006's Git failure message; in D001, the fallback's test creates and deletes a file of its own.
- The docs step after S7 sets `implemented` to D006 19, D005 3, D004 7, D003 8 and D001 13, writing the details above needing no revision bump, and adds to D006's `paths` the skill files S7 changes that state its concurrent-work rules.
- Rollout, outside this plan: a project gets the new hook at its next root `init`, and a worktree whose install predates `--staged` runs `check` through the hook's version test. The branch stays in `.worktrees/concurrent-checks`, neither merged nor pushed; merging it, a release and its `CHANGELOG.md` entry are the user's to start.

## Log

- 2026-11-13: Drafted against D006 r18 and its follow-ons. Found that `git ls-files -s` lists an intent-to-add entry as a stage-0 empty blob that `git commit` does not record, and that `git diff --cached` omits it, or lists it as deleted over a path HEAD holds (a scratch repository under `.tmp/`). Read literally, `D006#check`'s "stage-0 entries" would make `check --staged` and `index --staged` take such a doc for an empty file the commit does not hold, against the design's aim of checking what the commit records. The user chose to fix the design: D006 r19 leaves intent-to-add entries out of the staged tree, through a follow-up round of its gate, and `based_on` moved to D006@r19; its diff touches only S2's reader, which S3 reads through.
