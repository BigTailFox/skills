---
status: active
created: 2026-10-15
updated: 2026-10-21
revision: 5
modules: [canon]
summary: Opt-in tracing of canon workflows with canon.py trace, repo snapshots for replay, review dispositions and offline analysis of nine questions.
refs: []
owns: [skill-telemetry]
paths: [skills/governance/canon/trace.md]
reviewed: 5
reviewers: [claude-opus-5.5]
implemented: 4
---

# D001: Skill telemetry with canon trace

## Goals

1. Answer the nine [questions](#questions) about canon's skills from real work, every rate with its numerator and denominator.
2. Keep the agent's part mechanical: one `canon.py trace` call at each unit boundary, plus the review dispositions only the orchestrating session knows. Everything else is derived offline from docs, Git, review files, retro records and host records.
3. Save the repository state at the start of every unit, so a gate, code review or slice can be replayed with another skill version.
4. Stay local, opt-in and harmless: off unless the machine switch is on, nothing leaves the machine, no push of the project can carry a snapshot, and a failed call never stops the work.

## Spec

### Questions

Every recorded field serves at least one question. A finding is valid when its [disposition](#review-dispositions) is `accepted` or `deferred`: either way it was judged real.

1. **Cross-family reviewer**: how many valid blocker and major findings did only the cross-family reviewer raise, and at what cost in tokens and time?
2. **Confirmation round**: what share of confirmed fixes are judged not resolved, and how many new blockers does the round find?
3. **Two axes at L0**: is the two-axis code review worth it at L0, judged by the valid findings each axis contributes per tier?
4. **Slice workers**: how often do slices stop (stuck, blocked, paused), why, and do slices with a `Risk:` line stop more often?
5. **Tiering**: how often does a unit's tier turn out wrong: an L0 change that alters a spec, L1 work that needs a plan, an L1 design revision that rewrites the design's goals or approach?
6. **Cost**: wall time per unit kind, subagents per unit, and tokens where the host records them.
7. **Retro fixes**: after a retro fix is applied, does its cause recur, per run that has the fix?
8. **Retro cost**: how long do end checks take, what do they cost, and how often do they interrupt the user?
9. **Skill changes**: replayed on the same snapshots, does a changed skill do better than the version it replaced?

### Sources

Most answers already exist and are read offline:

- Docs and Git: slice `Status:` and `Risk:` lines, Log entries and the `Started at` commit; `revision`, `reviewed`, `reviewers` and `implemented`; R-doc findings and dispositions; known issues; I-doc resolutions; commit times and `Refs:` trailers. Every done slice ends in its own commit.
- `.canon/canon-blind-review/<topic>/`: each reviewer's prompt, output and agent id, and its confirmation verdicts, in [files named by its role](#review-files). A later review of the same topic overwrites them, so trace archives the files each review wrote when it ends.
- Cursor: `<cursor home>/projects/<project>/agent-transcripts/<conversation>/` holds the conversation, the arguments of every tool call and one file per subagent; each user message carries a `<timestamp>` to the minute. It records no tool output, tokens or per-call times. The agent's shell exposes `CURSOR_CONVERSATION_ID` and `CURSOR_AGENT=1`.
- Codex: `$CODEX_HOME/sessions/**/rollout-*.jsonl` timestamps every line and records tool calls with their output, `turn_context` with `model` and `effort`, `token_count` events with cumulative input, cached, output and reasoning tokens, and `session_meta` with `cwd`, `parent_thread_id` and, for a subagent, `agent_path`.
- Retro: `.canon/canon-retro/notes.md` (causes, events with `fix=present|absent|unverified`, raised and declined items) and `skills.jsonl`, both keyed by session.

Trace adds only what no source holds: the state at each unit start, one event per unit boundary (the only time source inside a Cursor turn), the review dispositions, the skill content in use, and explicit tier escalations.

### Units

A unit is one traced span of work, named by the id its `start` prints. A child unit passes its parent's id with `--parent`, and `end` names the unit it closes. Only the orchestrating session, the one the user talks to, calls `trace`; workers and reviewers never do.

| Kind | Started by | Ends | Parent |
|---|---|---|---|
| `design`, `plan`, `implement`, `investigate`, `canon-review`, `retro` | the skill of that name | `end` | none |
| `code-review` | `canon-code-review` | `end` | the enclosing unit, if one is open |
| `gate` | the review gate | `end` | the enclosing unit, if one is open |
| `slice` | `canon-implement`, before each worker launch | the first of its commit, the next `start` under its `implement` unit, and that unit's end | `implement` |
| `end-check` | `canon-retro`'s end check | `end` | the unit it closes, if still open |

`retro` is a requested retro. A slice's commit is the one that changes its `Status:`; workers run one at a time, so the next start under the same unit also ends a slice. A top-level unit has no parent: a unit of the first row, or a code review, gate or end check with no open unit to name, such as `canon-init`'s gates, `canon-handoff`'s end check and the review of a fix a retro applies. A slice built in the implementing session itself (an L0 change, an L1 revision without a plan) is part of its `implement` unit.

Outcomes, given to `end`. Every kind that ends allows `delivered`, `blocked`, `handoff` and `cancelled`; `implement` also allows `partial` and `escalated`, and `end-check` allows only `quiet` and `raised`.

- `delivered`: the unit produced its output: a doc that passed its gate, a committed implementation with every slice done, a resolved investigation, a closed codebase review, a disposed gate or code review, a finished requested retro.
- `partial`: it ended with paused slices.
- `escalated`: it stopped because the work needs another tier or a plan: `--to L1` when an L0 change alters a spec and the unit ends before a design revision has passed its gate, whether the user's decision or the revision is left for later; `--to L2` when the change turns out to be L2 work, such as a new design or a rewrite of one; `--to plan` when L1 work needs a plan. `--to` comes with `escalated` only. An L0 change whose design revision the implementing session makes does not stop: it continues as L1, and that revision's gate, under the `implement` unit, runs at L1. Likewise, a design unit started at L1 whose revision turns out to be L2 work does not stop: its gate runs at L2.
- `blocked`: stopped on a problem or decision only the user can settle.
- `handoff`: the work continues in another session.
- `cancelled`: the user stopped it.
- `quiet` or `raised`: whether the end check put items to the user.

### Call sites

Each call runs the project's `canon.py`. `<skill>` is the directory of the `SKILL.md` being followed, for a gate `canon-blind-review`'s or else `canon`'s; `<model>` is the session's model id as the host's model setting names it; `<tier>` is the tier the work runs at, for a gate the tier of its review, which can be above the enclosing unit's; `<id>` is the id printed by this skill's own `start`, and `<parent>` the id of the open unit of the workflow that invoked the skill, left out with `--parent` when there is none. A skill's first `start` decides: unless it prints `trace <id>`, the skill skips its other trace calls, which also covers a project copy of `canon.py` too old to have `trace`. When it does print an id, the agent follows the `canon` skill's `trace.md`, which states the outcomes and the dispositions format for agents. The placeholders other than `<tier>` and the first-start rule are stated in a paragraph of the `canon` skill itself, after its command table, since the first call needs them before tracing is known to be on; the review gate states the tier it runs at. An agent that lost an id finds it with `trace status`.

- `canon-design`, after Frame step 3: `trace start design <D or C id> --tier <tier> --skill <skill> --model <model>`. Before the closing command: `trace end <id> <outcome>`.
- `canon-plan`, after Start step 2: `trace start plan <P id> <D id> --tier <tier> --skill <skill> --model <model>`. Before the closing command: `trace end <id> <outcome>`.
- `canon-implement`, after Start step 4: `trace start implement [<P or D id>] --tier <tier> --base <start commit> --skill <skill> --model <model>`. Before launching each worker: `trace start slice <P id> --slice S<n> --parent <id>`. After Finish step 3, or when stopping on a wrong tier: `trace end <id> <outcome> [--to L1|L2|plan]`.
- `canon-code-review`, after Pin the fixed point: `trace start code-review [<P id>] --base <fixed point> --tier <tier> --skill <skill> --model <model> [--parent <parent>]`. After Dispose, its end check included: `trace end <id> <outcome> --dir .canon/canon-blind-review/<topic> --input -`, with the dispositions on stdin.
- The review gate in the `canon` workflow, at step 2: `trace start gate <doc id> --tier <tier> --skill <skill> --model <model> [--parent <parent>] [--base <Changes since commit>]`. At the end of step 5, after an L2 gate has the user's answers on its escalated findings: `trace end <gate id> <outcome> --dir .canon/canon-blind-review/<doc id> --input -`, where `<gate id>` is what the gate's `start` printed.
- `canon-investigate`, when opening the investigation: `trace start investigate <I id> --skill <skill> --model <model>`. After Phase 6: `trace end <id> <outcome>`.
- `canon-review`, after Create the doc: `trace start canon-review <R id> --skill <skill> --model <model>`. After Close: `trace end <id> <outcome>`.
- `canon-retro`: the end check opens with `trace start end-check --skill <skill> --model <model> [--parent <parent>]` and closes with `trace end <id> quiet|raised`; a requested retro opens with `trace start retro --skill <skill> --model <model>` and closes with `trace end <id> <outcome>`.
- `canon-handoff`, after writing the handoff file: `trace end <id> handoff` for each unit this conversation left open; an L0 `implement` unit waiting on a spec change ends `escalated --to L1` instead. A gate or code review ended here passes the `--dir` and `--input -` of its own end, with each finding not yet disposed as `escalated`; `trace.md` states this, and the skill's call site points to it, having no room for more. The session that continues the review traces nothing more of it.

### Switch and storage

```text
$XDG_CONFIG_HOME/canon/trace      machine switch, present = on (default ~/.config/canon/trace)
.canon/canon/trace/off            this checkout opts out
.canon/canon/trace/events.jsonl   event lines, appended
.canon/canon/trace/events.lock    held by start and end from their final checks to their append
.canon/canon/trace/snapshot.lock  held by each start's snapshot and skill storage, and by prune
.canon/canon/trace/<id>/          archived review files of unit <id>, and its snapshot-error.txt
.canon/canon/trace/.git           snapshot repository: refs/trace/<id> per unit, refs/skills/<manifest> per skill version
```

- Tracing is on in a checkout when the machine switch exists and the checkout has no `off` file. Installing skills, `canon-init` and `canon.py init` never turn it on.
- `trace on` creates the machine switch and prints what tracing stores: snapshots of the work tree, untracked files that are not ignored included, kept in the checkout's `.canon/canon/trace/`, which no commit or push reaches, and that packaging which does not read `.gitignore`, such as a Docker build context, must exclude `.canon/`. It writes outside the workspace, so a sandboxed agent asks the user to run it.
- Everything else lives in the checkout's trace directory, `.canon/canon/trace/` in the nearest directory above the working directory that holds `.git`, else `AGENTS.md`, else the working directory; locating it runs no Git command. The Cursor and Codex sandboxes let the agent write it; Codex's keeps the project's `.git` read-only. The directory is not scratch: until `prune`, it holds the only copy of its data. Each checkout, linked worktrees included, has its own: its events, archives and snapshots share a lifetime, removing a worktree removes them, and a new worktree's first snapshot copies the whole tree.
- No commit of the project can hold the trace directory. `start` and `off --here` write `.canon/canon/.gitignore` containing `*` when it is missing, so the project ignores the directory even when its own `.gitignore` lacks `.canon/`, and an `off` file cannot be committed. Without either rule, Git sees a nested repository: `git add -A` records at most a pointer to its HEAD commit, never a file inside it, and `git clean -fdx` skips it.

### Commands

```text
canon.py trace start KIND [DOC ...] [--parent UNIT] [--tier L0|L1|L2] [--slice S<n>]
                     [--base REF] [--skill DIR] [--model ID]
canon.py trace end UNIT OUTCOME [--to L1|L2|plan] [--dir DIR] [--input FILE|-]
canon.py trace status
canon.py trace on [--here]
canon.py trace off [--here]
canon.py trace prune --days N
```

- `start` prints `trace <id>`, or `trace off` without touching Git or writing anything when tracing is off. It resolves each `DOC`, which must be shaped like a doc id such as `D001`, to `<doc>@r<revision>` from the doc's frontmatter, keeping a doc it cannot find as given; checks that `--model` is one line of at most 200 characters, like a reviewer's `model`; checks that `--parent` names an open unit that is neither a slice nor an end check, and an `implement` unit for a slice, and that a kind of the first row of [Units](#units) has none; resolves `--base` to the merge base of that commit and HEAD, which is the commit itself when HEAD descends from it, and treats a `--base` without a merge base, or on an unborn branch, as absent; takes a [snapshot](#snapshots); computes the [manifest](#skill-digests); and appends one line.
- `end` closes the open unit `UNIT` and prints `trace <id> ended`, or, like `start`, `trace off` when tracing is off; `OUTCOME` must be one the unit's kind allows, and `--to` comes with `escalated` only. `--dir`, taken from the directory holding `.canon/` when relative, must lie under `.canon/`. It copies the regular files directly in it that changed since the unit started into `.canon/canon/trace/<id>/` when they total at most 2 MiB, and otherwise copies nothing; no such file records `none`, and a missing directory `copy: ENOENT`, the unit ending either way. It copies only once the final check under `events.lock` passes, so a call that fails that check archives nothing. `--input` reads the [dispositions](#review-dispositions).
- `status` prints whether tracing is on and why; the open units started in the last 24 hours, newest first, with their ids, kinds, docs and start times, marking those of this conversation when the host names it; the number of snapshots, and of skipped ones by reason; and the snapshot repository's disk size.
- `on` and `off` create and delete the machine switch; with `--here` they delete and create this checkout's `off` file.
- `prune --days N` deletes the snapshots and archives of units started more than N days ago, and the index copies and `.init-<id>` directories that interrupted starts left more than an hour ago, keeps every line, and runs `git gc --prune=1.hour.ago` in the snapshot repository: the space returns at once, while objects written in the last hour stay. When the snapshot repository exists, prune holds `snapshot.lock` through its deletions and its `gc`, so no start writes there meanwhile.
- Every subcommand exits 0 unless its arguments are invalid. Invalid input (an id that is not an open unit, an outcome the kind does not allow, invalid dispositions) or an events file that cannot be written prints `trace error: <reason>` and appends no line; the agent may correct its input and repeat the call once, then carries on either way. What a failed call stored first, such as a snapshot or an archive, is an orphan that readers ignore and `prune` removes by the time in its id. A failed snapshot, or a checkout outside Git, does not fail `start`: it writes the line without a snapshot.
- A call waits at most 5 s for a lock. A timeout on `events.lock` is a `trace error`; on `snapshot.lock`, a start skips its snapshot and skill storage, and a prune is a `trace error` that deletes nothing.

### Event lines

Each line of `events.jsonl` is one compact UTF-8 JSON object of at most 16 KiB, appended in a single write:

```text
{"v":1,"type":"manifest","digest":"<sha256>","skills":{"canon":"<sha256>","canon-code-review":"<sha256>"}}
{"v":1,"type":"start","id":"20261020T081502Z-3f9a1c","kind":"code-review","at":"2026-10-20T16:15:02+08:00","parent":"20261020T070011Z-91c2d4","docs":["D012@r3","P007@r2"],"tier":"L2","base":"<commit>","head":"<commit>","snapshot":"<commit>","host":"cursor","conversation":"<uuid>","model":"claude-opus-5.5","skill":"/home/me/.agents/skills/canon-code-review","manifest":"<sha256>"}
{"v":1,"type":"end","id":"20261020T081502Z-3f9a1c","kind":"code-review","at":"2026-10-20T16:41:37+08:00","outcome":"delivered","head":"<commit>","manifest":"<sha256>","dispositions":{},"archive":"ok"}
```

- `id`: the UTC start time and 6 random hex digits; it also names the snapshot ref and the archive.
- `at`: local time with its UTC offset, to the second.
- `parent`: the `--parent` unit; null for a top-level unit.
- `head`, `base` and `snapshot` are full commit ids: `base` as `start` resolved it, `snapshot` in the snapshot repository. `head` is null on an unborn branch or outside Git; `snapshot` is null when none was recorded, with `skipped` giving the reason.
- A reason, in `skipped` or `archive`, is `changes-over-10MiB`, `no-git` or `over-2MiB`, or names the step that failed and how: `<step>: exit <n>` for a Git command, `<step>: <errno name>` for a file operation, `<step>: timeout` for a lock. `<step>` is the Git command (`git add`), `index copy`, `snapshot lock` or `copy`. A reason never holds a path or a message; Git's message, when there is one, goes to `.canon/canon/trace/<id>/snapshot-error.txt`, never to the line or the agent.
- `tier` defaults to the parent's, and a slice takes its parent's `skill` and `model` and records its `S<n>` as `slice`. `skill` is the absolute path of `--skill`, null without it. `model` is stored in lowercase. `host` comes from the environment: `cursor` when `CURSOR_AGENT=1`, `codex` when `CODEX_THREAD_ID` is set, `claude-code` when `CLAUDECODE=1`, else `other`. `conversation` is `CURSOR_CONVERSATION_ID` or `CODEX_THREAD_ID`, else null.
- `manifest` is written on every start and on the end of a top-level unit, null when `skill` is. A `manifest` line precedes the first use of each digest in the file.
- An end line carries `outcome`, `to` for `escalated`, `head`, `manifest` for a top-level unit, `dispositions` for a gate or code review, null without `--input`, and `archive`: `ok`, `none` or the reason nothing was copied, null without `--dir`.
- A unit other than a slice is open from its start until its end; the analysis treats one with no end after 24 hours as incomplete.
- Readers skip and count lines that do not parse or carry an unknown `v`.

### Snapshots

Every start records a snapshot of the work tree in the snapshot repository, a non-bare repository with no remote that `start` creates on first use with `git init --template=` and the project's object format, its HEAD on an empty commit. It is built in `.init-<id>` and renamed to `.git`, so a `.git` there is always complete; a failed rename records `git init: <errno name>`. A snapshot holds what `git add -A` and a commit would record: files ignored by `.gitignore`, `.git/info/exclude` or `core.excludesFile` stay out, and a submodule is recorded at its checked-out commit, without changes inside it. Every Git command run against the project sets `GIT_OPTIONAL_LOCKS=0`, so none of them rewrites the project's index, and snapshot commits use the fixed identity `canon-trace <trace@canon.invalid>`, so they need no Git user configuration.

1. List the untracked files and the files with unstaged changes with `git status --porcelain -z --untracked-files=all`; when they total more than 10 MiB, record no snapshot and set `"skipped": "changes-over-10MiB"`.
2. Copy the checkout's index (`git rev-parse --git-path index`) to `index-<id>` in the snapshot repository's Git directory, keeping its modification time, which Git compares entries against to find racily clean ones; when there is no index, start without one.
3. With `GIT_INDEX_FILE` set to that copy, `GIT_OBJECT_DIRECTORY` to the snapshot repository's objects and `GIT_ALTERNATE_OBJECT_DIRECTORIES` to the project's, run `git add -A` and `git write-tree`.
4. With the same variables, `git commit-tree` the tree of the resolved base, or of HEAD without `--base`, as a parentless commit, then the snapshot tree as a commit whose parent is that one; on an unborn branch without `--base`, the snapshot commit has no parent. `git diff <snapshot>^ <snapshot>` then shows the change under review.
5. List the objects the snapshot reaches with `git rev-list --objects <commit>`, keep those that `git cat-file --batch-check`, run in the snapshot repository without the variables, reports missing, pack them with `git pack-objects --stdout` into a temporary file in the snapshot repository's Git directory, and feed that to `git index-pack --stdin` there.
6. Run `git update-ref refs/trace/<id> <commit>` in the snapshot repository, which records the snapshot. Then, best-effort and never setting `skipped`, delete the index copy and run `git -c gc.autoDetach=false gc --auto --quiet` there, which repacks once 50 packs or 6,700 loose objects accumulate.

New objects land only in the snapshot repository, and step 5 copies in each object the snapshot borrows from the project, once: the snapshot repository depends on nothing outside it, so rebasing, deleting branches or `git gc --prune=now` in the project cannot break a snapshot, and switching branches back and forth copies each file version once. The whole tree is copied again only into an empty snapshot repository. The project's work tree, index, HEAD and refs do not change, nor do the names and contents of the files in its object store; Git refreshes the modification time of an existing object that a snapshot step writes again, as it does on any such write. Starting from `git read-tree HEAD` instead of a copied index rehashes every file, 10 times slower in a 20,000-file checkout.

No push, clone or bundle of the project reaches the snapshot repository, `git push --mirror` and `git bundle create --all` included: its refs are not the project's, and no commit of the project holds its files ([Switch and storage](#switch-and-storage)). In a 20,000-file checkout with 45 MiB of packed objects, the first snapshot copied the whole tree, 45 MiB in 1.3 s; later ones took about 100 ms and added 15 to 100 KiB, about 10 KiB once repacked. Moving to a branch that changes 2,000 files copied their 2,006 objects, 4.6 MiB, once; switching back and forth afterwards copied nothing.

### Review dispositions

After merging the findings, any confirmation round and the user's answers that the workflow collects before `end`, the orchestrating session passes one JSON object to the `trace end` of the gate or code review:

```json
{"reviewers": [{"role": "same-model", "model": "claude-opus-5.5", "id": "a3f0c2e1"},
               {"role": "cross-family", "model": "gpt-6-astra", "id": "/root/d012_review"}],
 "findings": [{"by": ["same-model:F1", "cross-family:F2"], "severity": "major",
               "disposition": "accepted", "confirmed": "resolved"},
              {"by": ["cross-family:F1"], "severity": "blocker", "disposition": "escalated"}],
 "new_blockers": 0}
```

- `role`: `same-model` or `cross-family` in a gate; `spec`, `standards` or `cross-family` in a code review.
- `model`: the reviewer's model id, as a gate writes it to the doc's `reviewers`; a run the user made has `manual:` before it. `id`: the agent id kept for the confirmation round, or the session id a command run reports, such as `codex exec`'s; null for a manual run. `model` and a non-null `id` are each one line of at most 200 characters.
- One entry per merged finding. `by` lists every reviewer finding merged into it as `<role>:<F-id>`; `severity` is the highest among them; in a code review, `axis` is `spec` or `standards`.
- `disposition`: `accepted` (fixed in this work, including by a design revision the user decided on), `declined`, `escalated` (still awaiting the user at `end`, as is any finding not yet disposed when a handoff ends the review) or `deferred` (left for later by the user's decision, and tracked as the `canon` workflow's review gate and code review say), in a gate as in a code review.
- `confirmed`: `resolved` or `not-resolved` for a finding sent to the confirmation round, absent otherwise. `new_blockers`: the blockers that round reported as new, 0 without a round.

### Review files

`canon-blind-review`, and `canon-code-review` for its axis reviewers, keep each reviewer's files in `.canon/canon-blind-review/<topic>/` under its role: `<role>-prompt.md`, `<role>.md` with its findings and `<role>-id.txt`, then `<role>-confirm-prompt.md` and `<role>-confirm.md` for the confirmation round. A confirmation never overwrites the first round's findings, so each `by` id resolves in the archive. A gate's topic is its doc id; a code review's is `<P id>-code-review`, else a slug of the change, so it never shares its plan gate's directory.

### Skill digests

A skill's digest covers every regular file under its directory except `LICENSE`, `NOTICE`, `__pycache__/`, `*.pyc` and names starting with `.`. Each file contributes its Git blob id, the SHA-1 of `blob <size>\0` followed by its bytes. The digest is the SHA-256 of the compact UTF-8 JSON, without ASCII escaping, of the sorted list of `[relative_posix_path, blob_id]` pairs.

The manifest maps each directory named `canon` or `canon-*` that holds a `SKILL.md` to its digest. Such directories are searched beside `--skill`, or, when the parent of its parent is named `skills` (the skills repository's `skills/<category>/<name>/` layout), in every category directory. The manifest digest is the SHA-256 of the manifest's compact JSON with sorted keys. A unit whose start and end manifests differ, or whose children recorded another manifest, is mixed-version.

The analysis maps each digest to the skills-repository commits whose tree gives the same digest, from `git ls-tree -r` blob ids. A digest that matches no commit is `local`: an edited or uncommitted copy.

A start whose manifest the snapshot repository lacks also stores the files each digest covers there, as a parentless commit at `refs/skills/<manifest digest>` whose tree holds each skill directory under its name. Storing is best-effort: when it fails, the next start with that manifest stores it. A replay can thus run any recorded version, `local` ones included, and each new version adds only the files it changed.

### Analysis

`scripts/trace_report.py` lives in the skills repository and is not installed with the skills:

```text
python3 scripts/trace_report.py [--project PATH ...] [--since YYYY-MM-DD] [--skills-repo PATH]
                                [--cursor-home DIR] [--codex-home DIR ...] [--json]
```

It reads each project's events, archives, docs, Git history and retro records, and the host records in place, and writes nothing. `--cursor-home` defaults to `~/.cursor`; `--codex-home` defaults to `$CODEX_HOME`, else `~/.codex`, and repeats for a second Codex home such as the Windows side of WSL. Records of other hosts are not read, so their tokens are unknown.

Units link to host records this way:

- Cursor: the transcript named by `conversation`. A unit spans the tool calls from its `trace start` command, matched by its arguments in order, to the `trace end` command that names its id.
- Codex: the rollout whose file name holds `conversation`, else the one whose tool output contains `trace <id>`. A unit's tokens are the difference between the cumulative `token_count` totals at its start and its end. Subagent rollouts, found by `parent_thread_id`, are reported separately and never added to the parent.
- A reviewer's tokens come from the Codex rollout its `id` names: a subagent's `agent_path`, or the session id of a command run.

Each question is computed from:

1. Findings whose `by` names only the cross-family reviewer, by severity and disposition, over reviews that had one; that reviewer's tokens and the duration of its rollout.
2. `not-resolved` over confirmed findings; `new_blockers` per confirmation round.
3. Valid findings per axis over code reviews, by tier.
4. Slice outcomes from the plan at the slice's commit, or the Log and stash of a paused slice, and the worker reports in the host record, over slices started, with and without a `Risk:` line.
5. Implement units that changed tier or needed a plan, by target, over implement units by starting tier: `escalated` ones by `--to`, and those started at L0 with a gate at L1 under them, at any depth, as `L1`; a unit counts under every target it reached. Design units whose gate ran at a higher tier than they started at, over design units started at L1.
6. Wall time per kind, from start to end, a slice's ending as [Units](#units) states; subagents launched within a unit's span; tokens where recorded. Cursor wall time includes waiting for the user.
7. For each `applied <commit>` cause in `notes.md`: its `fix=present` events from traced sessions, matched by `conversation` or, for a session named by time, by the start minute of a traced end check or retro, over the units started after the fix whose snapshot holds it, meaning the fix commit's diff applies to the snapshot in reverse (`git apply --check -R`). Units where neither direction applies, or without a snapshot, are counted as unknown and left out. Also repeated identical commands per unit before and after the fix.
8. `end-check` units with their time and tokens, and `raised` end checks over top-level units that ended; declined items from `notes.md`.
9. The replayable units: gates, code reviews and slices with a snapshot, their parameters, dispositions and manifests, whether each was steered, and the units whose snapshot was skipped, with the reasons ([Replay](#replay)).

Rules:

- Compare only within the same kind, tier, host, model and skill digest. An implement or design unit's tier is the highest of its starting tier and those of the gates under it.
- Show every rate as numerator over denominator; with fewer than 20 units, mark it "few units" and list the cases.
- Write `unknown` for what a host does not record, never an estimate.
- List the cases behind every number with their unit ids and record locations.
- Start with the projects read, the lines skipped, the open and incomplete units, and a reminder that untraced work is unknown, not absent.
- A gate or code review that ended `handoff` is incomplete: list it with its dispositions so far, and leave it out of questions 1 to 3 and of replay scoring, since another session settles the rest untraced.

### Replay

Question 9 compares skill versions on recorded units. A replay clones a unit's snapshot from the snapshot repository into a scratch directory, installs a skill version, the one under test or the recorded one from `refs/skills/<manifest>`, runs the unit headless with its recorded `docs`, `slice` and `tier`, the same models and, where the host records them, the same efforts, the snapshot's parent standing in for `base`, and scores the result:

- A gate or code review against the original dispositions: valid findings should be found again, and declined ones count as false positives.
- A slice by its test criteria, whether the worker stopped, and the code-review findings that followed.

No recorded prompt is needed: reviewers and workers start fresh from prompts the skill builds out of the docs, code and parameters, so each version builds its own, and the reviewer prompts and outputs archived with the unit tell what the original findings were. What the orchestrating session took from the conversation is not replayed. The analysis marks a unit steered when a user message falls inside its span, and the original worker brief stays in the host record, for the harness to compare with the brief a replay builds.

A snapshot restores only what Git would commit. Ignored files a unit needs, such as data, installed dependencies and secrets, are the project's to provide, and every version under test runs against the same ones.

Each version runs at least three times per unit. The replay harness is its own design, started once 20 replayable units exist, and settles how a project provides its ignored files; this design guarantees the other inputs.

### Privacy

- Event lines hold ids, kinds, outcomes, commit ids, digests, times, doc ids, host and model names and the skill path; never prompts, outputs, source code or free text.
- Archives copy local review files, keep a failed snapshot's Git message, and stay in `.canon/`.
- Snapshots stay in a local repository that no push of the project reaches ([Snapshots](#snapshots)).
- The analysis prints counts, ids and record locations, never transcript text.
- Nothing is uploaded, and there is no export command.

### Delivery and acceptance

1. `canon.py trace`, with tests in `tests/test_canon.py` and a `CANON_VERSION` bump in every commit that changes `canon.py`; `trace.md` in the `canon` skill, and a line in its layout saying `.canon/canon/trace/` is not scratch; the call sites and the [review file](#review-files) names; a README section on turning tracing on and what it stores.
2. A pilot on real work: at least 20 top-level units across at least two projects and every host in use.
3. `scripts/trace_report.py`, tested on redacted real Cursor transcripts and Codex rollouts.
4. The replay harness, as its own design.

Scenarios for step 1, tested through the commands:

- With no machine switch, or with an `off` file, `start` prints `trace off`, runs no Git command and writes nothing.
- A clean checkout's snapshot has HEAD's tree.
- A dirty checkout's snapshot holds unstaged, staged and untracked changes and no ignored file, and leaves the project's work tree, index, HEAD, refs and the names and contents of its object files unchanged, the index byte for byte even after a tracked file's timestamp changed without its content.
- An unborn branch without an index gets a snapshot without a parent. Untracked and unstaged files over 10 MiB in total, a checkout outside Git and a failing Git command skip the snapshot, and the start line records the reason; a failing Git command's message lands in `snapshot-error.txt`, and `start` prints only its id.
- A code review whose fixed point moved on after the branch forked gets the merge base as `base`, and `git diff <snapshot>^ <snapshot>` equals the review's diff.
- A snapshot copies only the objects the snapshot repository lacks; switching to another branch and back copies each file version once. `git push --mirror`, `git clone --mirror` and `git bundle create --all` of the project carry no snapshot. After a reset, `git reflog expire --expire=now --all` and `git gc --prune=now` in the project, `git fsck --strict` passes in the snapshot repository and every snapshot can be read. With `.canon/` missing from the project's `.gitignore` and `.canon/canon/.gitignore` deleted, `git add -A` stages no file inside the trace directory and `git clean -fdx` leaves it.
- A child records its `--parent`; a parent that is not open, a slice or end check as parent, and a slice whose parent is not an `implement` unit are rejected and write nothing; a gate or end check without `--parent` is top-level.
- `end` closes the unit it names; an id that is not an open unit, an outcome its kind does not allow, or `--to` without `escalated` writes nothing. Valid dispositions land in the end line; invalid ones write nothing. `--dir` archives only the files changed since the unit started, nothing when they exceed 2 MiB, and the line says why; an unreadable file gives `copy: EACCES` and no path.
- Editing a skill file changes its digest, and `LICENSE`, `NOTICE` and caches do not; the source layout finds skills across categories; each manifest line is written once, and each new manifest's skill files are stored once at `refs/skills/<manifest digest>`.
- `prune` removes the snapshots and archives older than N days, keeps the lines, and shrinks the snapshot repository.

Pilot exit:

- At least 18 of 20 top-level units have a start and an end, or a genuine interruption.
- Every review's dispositions match its conversation.
- Every unit's parent, tier and outcome match its conversation, tier changes included.
- Every snapshot, cloned from the snapshot repository, reproduces its unit's input: the doc revision, the diff from `base`, the plan at the slice.
- Every Cursor and Codex unit is found in its host record.
- No host in use has a snapshot skipped because its sandbox could not write the trace directory.

If capture falls short, it is fixed before the report is built.

## Budgets

Measured in the pilot.

- Calls: two per unit except a slice, which takes one; one per skill invocation when tracing is off.
- Text: at most 40 tokens per call site in a skill; at most 110 for the `canon` skill's paragraph on the placeholders and the first-start rule, read whether tracing is on or off; `trace.md` at most 420 tokens, read only when tracing is on.
- Latency: `start` and `end` p95 under 300 ms on a local disk, including a snapshot of a 20,000-file checkout and the digests of 20 skill directories of 1 MiB in total; a checkout's first snapshot, which copies the whole tree, is exempt.
- Size: 16 KiB per line, 2 MiB per archive, 10 MiB of untracked and unstaged files per snapshot, 64 KiB per `snapshot-error.txt`, which keeps the end of Git's message.

## Decisions

- Agents make only mechanical `trace` calls, plus the review dispositions: written reports cost tokens and attention and are unreliable, and everything else already exists in docs, Git and host records.
- `trace` lives in the project's `canon.py`: agents already run it from a known path with standing permission, and the in-project part is small. The analysis lives in the skills repository, where skill changes are made.
- A machine switch with a per-checkout opt-out, never a `canon-init` question: the skills are public, and other users never meet tracing.
- Snapshots live in a repository of their own, never in the project's refs: no push, clone or bundle of the project can carry one, `--mirror` included, and the project's object store and history views stay untouched. It holds every object its snapshots reach, so nothing done to the project's history breaks a snapshot, and pruning frees space at once. The price is one packed copy of the tree per checkout, 3 to 26% of the object store in six local repositories, and a second copy of what changes while tracing is on.
- All trace data sits in the checkout's `.canon/canon/trace/`: it is the one place the Cursor and Codex sandboxes let an agent write that no commit can hold, since Codex keeps the project's `.git` read-only and Git never adds a file inside a nested repository. Events, archives and snapshots then share a lifetime; units traced in a worktree go with it.
- `host` comes from the environment and `model` is stored in lowercase: the analysis groups by both, and names as each agent spells them would split the groups.
- Every start takes a snapshot, a clean one included: a clean HEAD can later vanish from the project, and its snapshot adds only what changed since the previous one.
- Snapshots hold what Git would commit, with no per-file limit: a project's ignore files already keep out its data, caches and build outputs. The 10 MiB cap only bounds what a large file not yet ignored would cost, since `git add` hashes it on every start and stores each new version.
- Ignored files a replay needs are the project's to provide: copying them would bloat snapshots and could capture secrets, and the versions a replay compares run against the same files.
- Workers and reviewers never call `trace`: reviewers stay blind and read-only, and the orchestrating session sees every boundary.
- A slice records only its start: its commit, or the plan's Log, already records its end and outcome.
- Children name their parent, and `end` names its unit, by the id `start` printed: exact even when sessions share a checkout, for a few tokens per call, and `trace status` recovers an id lost to compaction.
- Review files are archived when each review ends: `.canon/canon-blind-review/` is scratch space, and the next review of a topic overwrites it.
- A review handed off part-way is not traced further: the next session has no open unit to end, linking the two parts would take another field and call site, and handoffs inside a review are rare. Its `handoff` end keeps the archive and the dispositions so far, and the analysis sets it aside as incomplete.
- Version exposure comes from content digests mapped to source commits: release numbers and lock hashes do not show the content loaded, and source checkouts are often uncommitted.
- Skill versions are stored with the snapshots: a `local` digest matches no commit, and without its files the version a change replaced could not be replayed.
- Tokens come from host records, offline: no host offers a portable runtime source, and Codex records them locally.
- Retro keeps its records, and the analysis joins `notes.md` and `skills.jsonl` by session, so each record keeps one owner.
- Replays judge skill changes, and real work finds problems and checks recurrence: personal volumes cannot support per-version rates.
- Data is kept until the user prunes or deletes it: a baseline at personal volume can take months.
- Evidence feeds human-reviewed experiments, never automatic skill changes.
