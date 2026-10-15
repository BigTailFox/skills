---
status: in-progress
created: 2026-10-15
updated: 2026-10-15
revision: 1
modules: [canon]
summary: Builds canon.py trace (event log, snapshots, review dispositions and archives, skill digests, prune), then the skill call sites and the README section.
refs: [D001]
based_on: [D001@r2]
reviewed: 1
reviewers: [claude-opus-5.5, gpt-6.1-sol-high]
---

# P001: Skill telemetry capture

Implements [D001: Skill telemetry with canon trace](../designs/D001-skill-telemetry.md).

## Current state

Next: S3.

## Slices

### S1: Switch and event log

Status: done
Risk: concurrency

Builds on `D001#units`, `D001#switch-and-storage`, `D001#commands` and `D001#event-lines`.

Changes in `skills/governance/canon/scripts/canon.py`, tested in `tests/test_canon.py`:

- A `trace` subcommand with `on`, `off`, `start`, `end` and `status`, dispatched before `main()` builds `Repo()`, since `Repo()` runs Git.
- The trace directory is located as `D001#switch-and-storage` states, without running Git. With tracing off, `end` behaves like `start`: it prints `trace off` and writes nothing.
- `start` validates the kind and `--parent`, prints `trace <id>` and appends a start line with every field of `D001#event-lines` except `base`, `head`, `snapshot`, `skipped` and `manifest`, plus `slice` for a slice. `skill` is the absolute path of `--skill`, null without it. `--slice S<n>` comes with the `slice` kind only and is required there. Each start writes `.canon/canon/.gitignore` when it is missing.
- A doc id resolves through `docs/<category>/` and `docs/archived/<category>/` in the directory holding `.canon/`, then, inside Git, through one `git ls-files -z -co --exclude-standard` with the pathspec `:(glob)**/docs/**/<id>-*.md`, which finds module docs.
- `end` without `--dir` and `--input`, and `status` without the snapshot count, as `D001#commands` states.
- `start` and `end` validate their input, then validate again and append under `events.lock`, with the lock rules of `D001#commands`. Each line goes out in one `os.write`; a line over 16 KiB is invalid input. Reading the events file filters lines by substring (a unit id, a digest, the date prefix of recent ids) before parsing them, so a log of many months stays within the latency budget.
- Every `trace error` exits 0; only argument errors, which argparse reports, exit non-zero.
- `CANON_VERSION` 7.

Test criteria; seam: the `canon.py trace` command line and the files it writes:

1. Without the machine switch, and with it plus an `off` file, `start` and `end` print `trace off`, exit 0, create no file, and never invoke a recording `git` placed first on `PATH`.
2. `on` creates the machine switch and prints the storage notice, which names the `.canon/` exclusion for packaging; `off` deletes it; `off --here` and `on --here` create and delete the `off` file; `status` reports each state with its reason.
3. `start design D001` prints an id matching `^\d{8}T\d{6}Z-[0-9a-f]{6}$` and appends one line whose `docs` is `["D001@r<revision>"]`. An archived doc and a module's doc resolve the same way; a doc that does not exist stays as given.
4. A child records its parent. A parent that is not open, a slice or end check as parent, and a slice whose parent is not an `implement` unit or that has none each print `trace error`, exit 0 and leave the file unchanged. A gate and an end check without `--parent` are top-level. A slice line carries its parent's tier, skill and model.
5. `end` closes the unit it names and prints `trace <id> ended`. An ended unit, a slice, an unknown id, an outcome the kind does not allow, `escalated` without `--to`, and `--to` with another outcome each print `trace error`, exit 0 and leave the file unchanged. Of two `end` calls for one unit run in parallel, one prints `trace <id> ended` and the other `trace error`, and the file holds one end line.
6. `CURSOR_AGENT=1` with `CURSOR_CONVERSATION_ID`, then `CODEX_THREAD_ID`, then `CLAUDECODE=1` give the hosts `cursor`, `codex` and `claude-code` with the matching conversation; none of them gives `other` and a null conversation. `--model Claude-Opus-5.5` is stored as `claude-opus-5.5`.
7. `status` lists the open units started in the last 24 hours, newest first, marks those whose conversation matches the environment's, and omits slices, ended units and older units.
8. An unwritable events file gives `trace error` and exit 0. Fifty `start` processes run in parallel leave fifty lines that parse. A line that does not parse and a line with `"v":2` are skipped, and parent checks still work.
9. After a `start`, `.canon/canon/.gitignore` holds `*`; with `.canon/` removed from the project's `.gitignore`, `git status --porcelain` lists nothing under `.canon/`.

### S2: Snapshots

Status: done
Risk: complex logic, performance, security

Builds on `D001#snapshots`, `D001#switch-and-storage`, `D001#commands` and `D001#event-lines`.

Changes in `canon.py` and `tests/test_canon.py`:

- The snapshot repository and the six snapshot steps of `D001#snapshots`, run on every start, with `snapshot.lock` guarding the repository's creation. `git init` gets `--object-format=sha256` when the project uses SHA-256 and runs with `GIT_DEFAULT_HASH=sha1` otherwise, so a configured SHA-256 default cannot give a SHA-1 project a SHA-256 snapshot repository. The index copy lives in the snapshot repository's Git directory. `GIT_INDEX_FILE`, `GIT_OBJECT_DIRECTORY` and `GIT_ALTERNATE_OBJECT_DIRECTORIES` hold absolute paths, and the fixed identity goes through the `GIT_AUTHOR_*` and `GIT_COMMITTER_*` variables.
- `--base` resolution as `D001#commands` states. Inside Git, a `--base` that names no commit is invalid input; outside Git, `base` is null and the start records `no-git`.
- Start lines gain `base`, `head`, `snapshot` and `skipped`, end lines gain `head`. A failed step deletes its index copy and records `skipped` and `snapshot-error.txt` as `D001#event-lines` states.
- `status` adds the snapshot count, the skipped starts by reason, and the snapshot repository's disk size.
- `CANON_VERSION` 8.

Test criteria; seams: `trace start` and `trace end` with their lines, the snapshot repository read with `git -C .canon/canon/trace`, and the project's Git state:

1. In a clean checkout, the snapshot's tree and its parent's tree both equal HEAD's. After a commit during the unit, its end line carries that commit as `head`.
2. In a dirty checkout, the snapshot holds unstaged, staged and untracked changes and a submodule at its checked-out commit, and no file ignored by `.gitignore`, `.git/info/exclude` or `core.excludesFile`. The project's work tree, HEAD and refs are unchanged, so are the names and contents of the files under its object directory, and its index is byte-identical, also after a tracked file's timestamp changed without its content.
3. On an unborn branch without an index, the snapshot has no parent and `head` is null.
4. Untracked and unstaged files over 10 MiB give `"skipped": "changes-over-10MiB"`. A directory outside Git gives `no-git` with null `head` and `base`, also when `--base` is passed. A corrupt project index gives the failed step and its exit status in `skipped` and Git's message, at most 64 KiB, in `.canon/canon/trace/<id>/snapshot-error.txt`; `status` counts each skip under its reason. Each start still prints only the id and writes the line, and no `index-*` copy remains, as after a successful start.
5. With `--base main` after `main` moved past the fork, `base` is the merge base, and `git diff <snapshot>^ <snapshot>` equals the project's `git diff <merge base>` plus the untracked files. A `--base` on an unrelated history gives a null `base` and a snapshot whose parent has HEAD's tree.
6. A second start after one file changed adds to the snapshot repository only that blob, the trees above it and the commits of the snapshot. Starting on `main`, then on a branch that changes some files, then on `main` again copies each file version once.
7. `git push --mirror` to a bare repository, `git clone --mirror` and `git bundle create --all` of the project carry no `refs/trace/*` ref, and the snapshot commit is absent from each copy.
8. After `git reset --hard`, `git reflog expire --expire=now --all` and `git gc --prune=now` in the project, `git fsck --strict` passes in the snapshot repository and `git ls-tree -r` reads every snapshot.
9. With `.canon/` gone from the project's `.gitignore` and `.canon/canon/.gitignore` deleted, `git add -A` in the project stages no file under the trace directory, `git status` succeeds, and `git clean -fdx` leaves the directory in place.
10. Snapshots succeed with no Git identity configured (`GIT_CONFIG_GLOBAL` naming an empty file, no `user.*` in the project), and their commits carry `canon-trace <trace@canon.invalid>`.
11. Ten starts run in parallel in a checkout without a snapshot repository each record a snapshot, and `git fsck --strict` passes there.
12. A project made with `git init --object-format=sha256` gets snapshots, and so does a SHA-1 project with `init.defaultObjectFormat=sha256` in the global configuration or `GIT_DEFAULT_HASH=sha256` set; the tests are skipped where Git cannot create a SHA-256 repository.
13. Measured rather than tested: in a generated checkout of 20,000 files with an events file of 20,000 lines, the p95 of 20 starts after the first is under 300 ms. The figures go in the Log.

### S3: Review dispositions and archives

Status: todo
Risk: security

Builds on `D001#review-dispositions`, `D001#commands` and `D001#privacy`.

Changes in `canon.py` and `tests/test_canon.py`:

- `end --input FILE|-` on a gate or code review stores the object as `dispositions` after checking it against `D001#review-dispositions`. Only the keys it documents are allowed, so no free text reaches the line; each `by` entry is `<role>:F<n>` and names a listed reviewer; `axis` appears in every code-review finding and in no gate finding; `model` is a single-line string of at most 200 characters, and `id` is one too or null. Without `--input`, a gate's or code review's end line carries `"dispositions": null`; `--input` on any other kind is invalid.
- `end --dir DIR`: DIR, with symlinks resolved, must lie under the checkout's `.canon/`. A file changed since the unit started is one whose modification time is not before the unit's start. Symlinks inside DIR are not regular files and are not copied.
- `CANON_VERSION` 9.

Test criteria; seams: `trace end` with `--input` and `--dir`, its line, and `.canon/canon/trace/<id>/`:

1. Valid dispositions appear in the end line unchanged: a gate's with a manual-fallback reviewer (`"model": "manual:<model>"`, `"id": null`) and a code review's with both axes. A gate ended without `--input` carries `"dispositions": null`.
2. Each of these prints `trace error`, exits 0 and writes nothing: an unknown key, a role the kind does not allow, a `by` entry naming an unlisted reviewer, an unknown severity or disposition, `deferred` in a gate, a code-review finding without `axis`, a negative `new_blockers`, a multi-line `model`, an `id` that is neither a string nor null, invalid JSON, and `--input` on a design unit.
3. `--dir` copies the files changed since the unit started and skips older files, subdirectories and symlinks; files over 2 MiB in total copy nothing and give `over-2MiB`; an unreadable file gives `copy: EACCES` and no path; no changed file gives `none`; a DIR outside `.canon/`, directly or through a symlink, prints `trace error`.

### S4: Skill digests and stored versions

Status: todo

Builds on `D001#skill-digests` and `D001#event-lines`.

Changes in `canon.py` and `tests/test_canon.py`:

- Skill digests, the manifest and its storage at `refs/skills/<manifest digest>` as `D001#skill-digests` defines them; the stored tree keeps each file's executable bit. A slice computes the manifest from its parent's skill. Without `--skill`, `manifest` is null. Outside Git there is no snapshot repository, and nothing is stored.
- `manifest` fields and lines as `D001#event-lines` states, the check for an existing `manifest` line made under the events lock.
- `CANON_VERSION` 10.

Test criteria; seams: `trace start` and `trace end` with `--skill`, their lines, and `refs/skills/*` in the snapshot repository:

1. A skill's digest equals the `D001#skill-digests` formula computed in the test from `git hash-object` blob ids. Editing a covered file changes it; adding `LICENSE`, `NOTICE`, `__pycache__/x.pyc` or a dotfile does not.
2. The installed layout (`--skill` among its siblings) and the source layout (`skills/<category>/<name>/`) both find every `canon` and `canon-*` directory holding a `SKILL.md`, and no other directory.
3. Each `manifest` line appears once, before the first line that uses its digest, also when ten starts with a manifest the file lacks run in parallel. A top-level unit's end line carries the manifest computed at its end; a child's end line carries none.
4. A manifest the snapshot repository lacks is stored once at `refs/skills/<digest>`, its tree matching the covered files, with mode `100755` for an executable file; a repeated manifest stores nothing.

### S5: Prune

Status: todo
Risk: concurrency

Builds on `D001#commands`.

Changes in `canon.py` and `tests/test_canon.py`: `trace prune --days N` as `D001#commands` states, choosing what to delete by the time in each snapshot ref's and archive's id, so it needs no event line. It keeps `refs/skills/*`, deletes index copies and `.init-*` build directories older than an hour, which an interrupted start leaves, prints what it removed and the repository's size, and works with tracing off. `CANON_VERSION` 11.

Test criteria; seams: `trace prune`, the trace directory and the snapshot repository:

1. Snapshot refs and archives whose ids are more than N days old are deleted, and so are an index copy and a `.init-*` directory older than an hour; newer ones, every line and `refs/skills/*` stay. Old units are written into the fixture in the documented formats.
2. With the pruned snapshots' object files dated more than an hour back, prune shrinks the snapshot repository and `git fsck` passes; objects written in the last hour remain.
3. Prune runs with the machine switch absent.

### S6: Agent instructions and the gate

Status: todo

Builds on `D001#call-sites`, `D001#review-files` and `D001#review-dispositions`.

Changes:

- `skills/governance/canon/trace.md`, at most 400 tokens: the outcomes each kind allows and when `--to` applies; the dispositions object and the roles of each review kind; on `trace error`, correct the input and repeat the call once, then carry on; `trace status` recovers a lost id; workers and reviewers never call `trace`.
- `skills/governance/canon/SKILL.md`: a link to `trace.md`, and a line beside its `.canon/` rules saying `.canon/canon/trace/` is not scratch: until `trace prune` it holds the only copy of its data.
- `skills/governance/canon/workflow.md`: the gate's call sites, at step 2 and after step 5 of the review gate.
- `skills/execution/canon-blind-review/SKILL.md`: reviewer files named by role, as `D001#review-files` gives them.

Test criteria; seam: the skill texts as an agent follows them, run through the `trace` command line:

1. `python3 scripts/validate.py` and `npx skills add . --list` pass.
2. `trace.md` is at most 400 tokens and each gate call site at most 40, counted with tiktoken's `cl100k_base` encoding, or as characters divided by 4 where tiktoken is unavailable. The counts go in the Log.
3. After the worker reports done, the orchestrating session launches a fresh subagent that, given only the skill texts and a scratch project with tracing on, runs the gate's call sites as `workflow.md` spells them, naming review files as `canon-blind-review` says. The result is a gate with its dispositions and an archive holding each role's files; with tracing off, the first call prints `trace off`. The Log gets the commands it ran and what the lines and archive held.

### S7: Workflow call sites and README

Status: todo

Builds on `D001#call-sites`, `D001#review-files`, `D001#switch-and-storage` and `D001#privacy`.

Changes:

- The call sites of `canon-design`, `canon-plan`, `canon-implement`, `canon-code-review`, `canon-investigate`, `canon-review`, `canon-retro` and `canon-handoff`, at the steps `D001#call-sites` names.
- `skills/execution/canon-code-review/SKILL.md`: its axis reviewers' files named by role, as `D001#review-files` gives them.
- `README.md`: a Tracing section on turning tracing on and off, what it stores and where, why packaging that ignores `.gitignore` must exclude `.canon/`, `trace status` and `trace prune`.

Test criteria; seam: the skill texts as an agent follows them, run through the `trace` command line:

1. `python3 scripts/validate.py` and `npx skills add . --list` pass.
2. Each call site is at most 40 tokens, counted as in S6. The counts go in the Log.
3. After the worker reports done, the orchestrating session launches a fresh subagent that, given only the skill texts and a scratch project with tracing on, runs every call site as its skill spells it, in the order the workflows run them. Every unit other than a slice ends exactly once, each unit has the parent `D001#units` assigns, the code review's archive holds each role's files, and `trace status` ends with no open unit. The run covers a design and a plan with their gates, an implementation with two slices and a code review, an investigation, a codebase review, a requested retro, an end check inside a unit and one with no open unit, and a handoff that ends two open units. The Log gets the commands it ran and each unit's kind, parent and outcome.

## Notes

- Scope: step 1 of `D001#delivery-and-acceptance`. The pilot, step 2, starts once this plan is done; `scripts/trace_report.py`, step 3, gets its own plan, written from the pilot's records.
- Seams, agreed with the user: the `canon.py trace` command line (arguments, output, exit status) and what it writes: `events.jsonl`, archives, the switch and `off` files, `.canon/canon/.gitignore`, and the snapshot repository's refs and objects, read with `git`. Tests also read the project's Git state to show it unchanged. They run `canon.py` as a subprocess, as the rest of `tests/test_canon.py` does, and call no internal function of `trace`.
- Tests set `XDG_CONFIG_HOME` to a temporary directory and set or clear `CURSOR_AGENT`, `CURSOR_CONVERSATION_ID`, `CODEX_THREAD_ID` and `CLAUDECODE` for every run: the suite runs inside agent hosts that set them, and must never touch the real machine switch.
- `canon.py` stays one file on the Python 3.8+ standard library and keeps working on Windows, where `O_APPEND` writes from two processes can collide; the events lock covers that. Locks follow `id_lock`'s `fcntl` and `msvcrt` pattern but time out as `D001#commands` states, where `id_lock` waits a minute and exits non-zero.
- Every commit that changes `canon.py` bumps `CANON_VERSION`, since `validate.py` rejects a changed script under an unchanged version: S1 sets 7, and each later slice that changes `canon.py` adds one.
- The call sites land last. Before S6 nothing calls `trace`, so a project whose `canon.py` is upgraded mid-plan is unaffected; between S6 and S7 only gates are traced.
- `main()` builds `Repo()`, which runs Git and scans every doc, before dispatching. `trace` dispatches first, so tracing off touches no Git, and it reads only the docs a call names, to stay within the latency budget.
- The snapshot repository is non-bare and its HEAD names a commit. When the trace directory is not ignored, the project's `git add -A` fails on a nested repository whose HEAD is unborn, and a staged pointer to a bare one breaks the project's `git status`.
- The project's objects reach a snapshot only through `GIT_ALTERNATE_OBJECT_DIRECTORIES` during the snapshot steps, never through an `objects/info/alternates` file, so the snapshot repository depends on nothing outside it.
- Codex keeps the project's `.git` read-only, so nothing may write there, an index refresh or `index.lock` included. Cursor's sandbox lets the agent create the nested repository but protects every existing repository's `.git/config` and `.git/hooks`: the snapshot repository never changes its config after `git init`, and deleting test repositories by hand needs a command run outside the sandbox.
- Clean filters run in snapshot step 3 as in a commit. Git LFS's stores a changed file's content under the project's `.git/lfs/`; under Codex's read-only `.git` it fails, and the snapshot is skipped.
- A change to a file's executable bit alone keeps its skill's digest, which covers content only (`D001#skill-digests`), so the stored tree keeps the mode first stored. Skills run `canon.py` through `python3`, and their one executable file is a template the agent copies, edits and runs, so replays are unaffected.
- A checkout's first snapshot copies the whole tree. Where it outlasts a host's command timeout, the start prints no id and the unit goes untraced; the pilot watches for this.
- The docs step writes into D001 the details this plan settles within its intent: `end` with tracing off; the `slice` field; `skill` and `manifest` null without `--skill`; `dispositions` null without `--input`; the limits on `model` and `id`; where the index copy lives; the non-bare snapshot repository; that the project's object store keeps the names and contents of its files, while Git refreshes the modification time of an existing object a snapshot step writes again, as it does on any such write. It adds `skills/governance/canon/trace.md` to D001's `paths`; `canon.py`, its tests and the skill texts serve all of canon and stay outside them.
- `CODEX_THREAD_ID` and `CLAUDECODE` come from the Codex binary and Claude Code's documentation, not from a live session; the pilot confirms them.
- D001's snapshot timings and sizes come from measurements that no experiment doc records; S2's last criterion measures them again.

## Log

- Drafted from D001@r1. The user settled the scope, the seams and the slicing as drafted.
- The review gate found that D001 contradicted itself on `skipped`: Git's error in the line, yet no free text in lines. The user chose a bounded reason in the line and Git's message in `snapshot-error.txt`, revised into D001@r2.
- The user approved the plan by starting its implementation. Started at 5bd0cff.
- S1 done: 14 tests in `TraceTest`, 46 in the suite, all passing. A held `events.lock` gives `trace error` after 5.07 s; with a 20,000-line events file, calls take 56–75 ms. Python 3.8 is not installed here, so 3.8 compatibility was checked by reading.
- S1 decisions: `--parent` on a kind of `D001#units`'s first row is a `trace error`, since that row has no parent; `off --here` also writes `.canon/canon/.gitignore`, so the `off` file cannot be committed; any unexpected exception prints `trace error` and exits 0. The docs step adds the first two to D001. `id_lock` now shares a `file_lock` helper with the trace locks, its behavior unchanged.
- S2 plan fixes, from the worker's questions: a SHA-1 project's snapshot repository is created with `GIT_DEFAULT_HASH=sha1`, since a configured SHA-256 default would make every snapshot fail. Criterion 2 compares the names and contents of the project's object files: Git refreshes the modification time of an existing object that `git add` or `git write-tree` writes again, no option turns that off, and under Codex's read-only `.git` the refresh fails and Git writes the object into the snapshot repository instead. S5's prune also deletes the `.init-*` directories an interrupted repository creation leaves.
- S2 done: 16 tests in `SnapshotTest`, 62 in the suite, all passing. Criterion 13, on a local ext4 disk with 20,002 files and a 20,000-line events file: the first start took 565 ms; later starts 139 ms at p95 when clean and 148 ms when dirty; `end` 80–81 ms at p95; the snapshot repository held 17.2 MiB. A held `snapshot.lock` skips the snapshot after 5.08 s.
- S2 decisions: every start line has `skipped`, null when the snapshot was recorded. On an unborn branch `--base` is ignored, and a `--base` starting with `-` is invalid input. The snapshot repository is built in `.init-<id>` under the lock and renamed to `.git`; a failed rename gives `git init: <errno>`. Step 5's pack goes through a temporary file in the snapshot repository's Git directory rather than a pipe, and an `OSError` there gives `git pack-objects: <errno>`, checked with a script because no seam can trigger it. The index copy keeps the index's modification time, which Git compares entries against to find racily clean ones. The docs step writes the temporary pack file and the `.init-<id>` directory into D001.
- S2's worker stalled for about three hours on a tool call that never returned, after writing the SHA-1 test and before running it; resumed and limited to the sandbox, it finished in minutes.
