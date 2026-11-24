---
status: active
created: 2026-10-15
updated: 2026-11-24
revision: 17
modules: [canon]
summary: Opt-in tracing of canon workflows with canon.py trace, repo snapshots for replay, review dispositions and offline analysis of nine questions.
refs: [D002, D003, D000, D007, R002, R003, D004, D006, R004, E003, E004]
owns: [skill-telemetry]
paths: [skills/governance/canon/scripts/canon.py, tests/test_canon.py, skills/governance/canon/trace.md, skills/governance/canon/review-evidence.md, skills/governance/canon/SKILL.md, skills/governance/canon/workflow.md, skills/execution/canon-blind-review/SKILL.md, skills/execution/canon-code-review/SKILL.md, skills/execution/canon-design/SKILL.md, skills/execution/canon-handoff/SKILL.md, skills/execution/canon-implement/SKILL.md, skills/execution/canon-investigate/SKILL.md, skills/execution/canon-plan/SKILL.md, skills/execution/canon-retro/SKILL.md, skills/execution/canon-review/SKILL.md]
reviewed: 17
reviewers: [gpt-6.2-astra]
approved: 15
implemented: 16
---

# D001: Skill telemetry with canon trace

## Goals

1. Answer the nine [questions](#questions) about canon's skills from real work, every rate with its numerator and denominator.
2. Keep the agent's part mechanical: one `canon.py trace` call at each unit boundary, plus the review dispositions and any later recheck only the orchestrating session knows. Everything else is derived offline from docs, Git, review files, retro records and host records.
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
- `.canon/canon-blind-review/<topic>/`: each reviewer's prompt, output and agent id, and its confirmation verdicts, in [files named by its reviewer key](#review-files). A later review of the same topic overwrites them, so trace archives the files each review wrote when it ends.
- Cursor: `<cursor home>/projects/<project>/agent-transcripts/<conversation>/` holds the exported conversation and tool calls and may have a file per subagent. Some starts are absent from the export; each user message carries a `<timestamp>` to the minute. It records no tool output, tokens or per-call times. The agent's shell exposes `CURSOR_CONVERSATION_ID` and `CURSOR_AGENT=1`.
- Codex: `$CODEX_HOME/sessions/**/rollout-*.jsonl` timestamps every line and records tool calls with their output, `turn_context` with `model` and `effort`, `token_count` events with cumulative input, cached, output and reasoning tokens, and `session_meta` with `cwd`, `parent_thread_id` and, for a subagent, `agent_path`.
- Retro: `.canon/canon-retro/notes.md` (causes, events with `fix=present|absent|unverified`, raised and declined items) and `skills.jsonl`, both keyed by session.

Trace adds only what no source holds: the state at each unit start, one event per unit boundary (the only time source inside a Cursor turn), the review dispositions and any later rechecks, the skill content in use, and explicit tier escalations.

### Units

A unit is one traced span of work, named by the id its `start` prints. A child unit passes its parent's id with `--parent`, and `end` names the unit it closes. Only the orchestrating session, the one the user talks to, calls `trace`; workers and reviewers never do.

| Kind | Started by | Ends | Parent |
|---|---|---|---|
| `design`, `plan`, `implement`, `investigate`, `canon-review`, `retro` | the skill of that name; an `implement` unit also the `canon` workflow, for L1 work carried on after its gate | `end` | none |
| `code-review` | `canon-code-review` | `end` | the enclosing unit, if one is open |
| `gate` | the review gate | `end` | the enclosing unit, if one is open |
| `follow-up` | a gate's [D007§follow-up-round: follow-up round](D007-change-tiers.md#follow-up-round) | `end` | the enclosing unit, if one is open |
| `slice` | `canon-implement`, before a worker runs on a slice with no open unit | the first of its commit, the next `start` under its `implement` unit, and that unit's end | `implement` |
| `end-check` | `canon-retro`'s end check | `end` | the unit it closes, if still open |

A `follow-up` unit is traced as a gate is: what this design says of a gate's `<skill>`, `end`, dispositions and review files holds for it. It is not replayed, since its reviewers resume with what they read in the gate, which no snapshot holds. `retro` is a requested retro. A slice's commit is the one that changes its `Status:`; workers run one at a time, so the next start under the same unit also ends a slice. A top-level unit has no parent: a unit of the first row, or a code review, gate or end check with no open unit to name, such as `canon-init`'s gates, `canon-handoff`'s end check and the review of a fix a retro applies. A slice built in the implementing session itself (an L0 change, an L1 revision without a plan) is part of its `implement` unit. An L0 change made outside `canon-implement` opens no unit and leaves only its code review, until a design revision turns it into L1 work, which opens one as [Call sites](#call-sites) states.

Outcomes, given to `end`. Every kind that ends allows `delivered`, `blocked`, `handoff` and `cancelled`; `implement` also allows `partial` and `escalated`, and `end-check` allows only `quiet` and `raised`.

- `delivered`: the unit produced its output: a doc that passed its gate, a committed implementation with every slice done, a resolved investigation, a closed codebase review, a disposed gate or code review, a finished requested retro.
- `partial`: it ended with paused slices.
- `escalated`: it stopped because the work needs another tier or a plan: `--to L1` when an L0 change alters a spec and the unit ends before the design revision that specifies the alteration has passed its gate, whether the user's decision or the revision is left for later; `--to L2` when the change turns out to be L2 work, such as a new design or a rewrite of one; `--to plan` when L1 work needs a plan. `--to` comes with `escalated` only. An L0 change whose alteration the implementing session specifies in a design revision does not stop: it continues as L1, and that revision's gate, under the `implement` unit, runs at L1. Likewise, a design unit started at L1 whose revision turns out to be L2 work does not stop: its gate runs at L2.
- `blocked`: stopped on a problem or decision only the user can settle.
- `handoff`: the work continues in another session.
- `cancelled`: the user stopped it.
- `quiet` or `raised`: whether the end check put items to the user.

### Call sites

Each call runs the project's `canon.py`. `<skill>` is the directory of the `SKILL.md` being followed, for a gate `canon-blind-review`'s or else `canon`'s; `<model>` is the session's model id as the host's model setting names it; `<tier>` is the tier the work runs at, for a gate the tier of its review, which can be above the enclosing unit's; `<id>` is the id printed by this skill's own `start`, and `<parent>` the id of the open unit of the workflow that invoked the skill, left out with `--parent` when there is none. For a workflow recording new units, the skill's first `start` decides: unless it prints `trace <id>`, the skill skips its other trace calls, which also covers a `canon.py` that refuses to run ([D004§install: install](D004-project-setup.md#install)). When it does print an id, the agent follows the `canon` skill's `trace.md`, which states the outcomes and the dispositions format for agents. The placeholders other than `<tier>` and the first-start rule are stated in a paragraph of the `canon` skill itself, after its command table, since the first call needs them before tracing is known to be on; the review gate states the tier it runs at. An agent that lost an id finds it with `trace status`.

- `canon-design`, after Frame step 3: `trace start design <D or C id> --tier <tier> --skill <skill> --model <model>`. Before the closing command: `trace end <id> <outcome>`. An L1 revision that carries on to implementation runs its end check after the docs step's commit instead, under the `implement` unit the workflow opens (below).
- `canon-plan`, after Start step 2: `trace start plan <P id> <D id> --tier <tier> --skill <skill> --model <model>`. Before the closing command: `trace end <id> <outcome>`.
- `canon-implement`, after Start step 4: `trace start implement [<P or D id>] --tier <tier> --base <start commit> --skill <skill> --model <model>`. Before a worker runs on a slice that has no open unit, its first worker or one that takes the slice up again after its unit ended: `trace start slice <P id> --slice S<n> --parent <id>`; a worker resumed or replaced while the slice's unit is open stays in it ([D003§resuming-and-replacing: resuming and replacing](D003-subagents.md#resuming-and-replacing)). After Finish step 3, or when stopping on a wrong tier: `trace end <id> <outcome> [--to L1|L2|plan]`.
- `canon-code-review`, after Pin the fixed point: `trace start code-review [<P id>] --base <fixed point> --tier <tier> --skill <skill> --model <model> [--parent <parent>]`. After Dispose, its end check included: `trace end <id> <outcome> --dir .canon/canon-blind-review/<topic> --input -`, with the dispositions on stdin.
- L1 work in the `canon` workflow that the session revising the design carries on to implementation ([D007§phases: phases](D007-change-tiers.md#phases)), unless `canon-implement` runs it, once the revision has passed its gate: `trace start implement <D id> --tier L1 --skill <skill> --model <model>`. After the docs step's commit and any end check, or when it stops for a plan or an L2 fix: `trace end <implement id> <outcome> [--to plan|L2]`, where `<implement id>` is what that `start` printed.
- The review gate in the `canon` workflow, at step 2: `trace start gate <ids> --tier <tier> --skill <skill> --model <model> [--parent <parent>] [--base <Changes since commit>]`, `<ids>` being its target's id followed by its follow-on targets'. At the end of step 5, after an L2 gate has the user's answers on its escalated findings: `trace end <gate id> <outcome> --dir .canon/canon-blind-review/<topic> --input -`, where `<gate id>` is what the gate's `start` printed. A follow-up round starts the same way with `trace start follow-up`, `<ids>` naming the targets it revises, and without `--base`, since HEAD holds their previous revisions; it ends the same way when its step 5 ends, with `--dir .canon/canon-blind-review/<topic>/followup-<k>`.
- `canon-investigate`, when opening the investigation: `trace start investigate <I id> --skill <skill> --model <model>`. After Phase 6: `trace end <id> <outcome>`.
- `canon-review`, after Create the doc: `trace start canon-review <R id> --skill <skill> --model <model>`. After Close: `trace end <id> <outcome>`.
- `canon-retro`: the end check opens with `trace start end-check --skill <skill> --model <model> [--parent <parent>]` and closes with `trace end <id> quiet|raised`; a requested retro opens with `trace start retro --skill <skill> --model <model>` and closes with `trace end <id> <outcome>`.
- A separately requested targeted recheck uses the saved review unit ID, even in a session that started no unit. If requested before the unit closes, finish the recheck, preserve the first confirmation in the end dispositions and append the saved recheck immediately after the end. Otherwise append it on receipt. Each call observes the current tracing switch.
- `canon-handoff`, after writing the handoff file: `trace end <id> handoff` for each unit this conversation left open; an L0 `implement` unit waiting on a spec change ends `escalated --to L1` instead. A gate or code review ended here passes the `--dir` and `--input -` of its own end, with each finding not yet disposed as `escalated`; `trace.md` states this, and the skill's call site points to it, having no room for more. A session that resumes a pending review starts a new unit with `--continues <handoff-unit>` when the earlier trace is available. Its final end carries the actual reports and coverage, including the saved reports it reused. A handoff without a recorded continuation remains visibly partial.

### Switch and storage

```text
$XDG_CONFIG_HOME/canon/trace      machine switch, present = on (default ~/.config/canon/trace)
.canon/canon/trace/off            this checkout opts out
.canon/canon/trace/events.jsonl   event lines, appended
.canon/canon/trace/events.lock    held by start, end and recheck through append, and by prune while removing evidence
.canon/canon/trace/snapshot.lock  held during opening snapshots, skill storage, review-input publication and prune
.canon/canon/trace/<id>/          archived review files of unit <id>, and its snapshot-error.txt
.canon/canon/trace/.git           snapshot repository: refs/trace/<id>, refs/review-input/<id> for retained rounds, refs/skills/<manifest>
```

- Tracing is on in a checkout when the machine switch exists and its trace directory has no `off` file. Installing skills, `canon-init` and `canon.py init` never turn it on.
- `trace on` creates the machine switch and prints what tracing stores: snapshots of the work tree, untracked files that are not ignored included, kept in the checkout's `.canon/canon/trace/`, which no commit or push reaches, and that packaging which does not read `.gitignore`, such as a Docker build context, must exclude `.canon/`. It writes outside the workspace, so a sandboxed agent asks the user to run it.
- Everything else lives in the checkout's trace directory, `.canon/canon/trace/` at the checkout's root, the nearest directory above the working directory that holds `.git`, else `AGENTS.md`, else the working directory. A linked worktree in `.worktrees/` ([D006§concurrent-work: concurrent work](D006-doc-model.md#concurrent-work)) uses its main checkout's: when the root lies under `<R>/.worktrees/`, where `<R>` holds `.git`, and the root's `.git` is a file whose `gitdir:` line names a Git directory of one of `<R>`'s linked worktrees, a directory directly inside the `worktrees` directory of `<R>`'s common Git directory, the trace directory is found again from `<R>`. `<R>`'s common Git directory is `<R>/.git` when that is a directory, else the directory its `gitdir:` line names, or for a linked worktree, whose named directory lies directly inside one named `worktrees`, the directory two levels above it. A relative `gitdir:` path resolves from the directory holding its `.git` file, and directories compare after resolving symbolic links. A call that finds tracing on with that directory but cannot create a file in it, creating the directory when missing, as when a host started the session in the worktree with a sandbox limited to it, uses the worktree's own trace directory instead, its `off` file included; it tests by creating a uniquely named file there and deleting it. Every `trace` subcommand except `history` is such a call, `status` and `on` included, so one may create the main checkout's empty trace directory; with tracing off, none tests, and `off --here` and `prune` use the main checkout's directory. The read-only `history` lookup under [Commands](#commands) bypasses the switch and the write probe. Locating either store runs no Git command. The Cursor and Codex sandboxes let the agent write it; Codex's keeps the project's `.git` read-only. The directory is not scratch: until `prune`, it holds the only copy of its data.
- Snapshots, `DOC` lookups, `--base` and `--dir` still read the checkout the command runs in, so the units of the worktrees in `.worktrees/` share their main checkout's events, archives, snapshot repository and `off` file, as sessions sharing one checkout do, and removing a worktree keeps them. Every other checkout, a linked worktree elsewhere, another repository's linked worktree under `.worktrees/` and a submodule included, has its own trace directory, as has a worktree whose calls fall back: its events, archives and snapshots share a lifetime, removing such a worktree removes them, and its first snapshot copies the whole tree.
- No commit of the project can hold the trace directory. `start` and `off --here` write `.canon/canon/.gitignore` containing `*` when it is missing, so the project ignores the directory even when its own `.gitignore` lacks `.canon/`, and an `off` file cannot be committed. Without either rule, Git sees a nested repository: `git add -A` records at most a pointer to its HEAD commit, never a file inside it, and `git clean -fdx` skips it.

### Commands

```text
canon.py trace start KIND [DOC ...] [--parent UNIT] [--tier L0|L1|L2] [--slice S<n>]
                     [--base REF] [--skill DIR] [--model ID] [--continues UNIT]
canon.py trace end UNIT OUTCOME [--to L1|L2|plan] [--dir DIR] [--input FILE|-]
canon.py trace status
canon.py trace history [UNIT]
canon.py trace recheck UNIT FINDING --reviewer KEY --snapshot OID --result resolved|not-resolved
                       --report STEM --order N|unknown [--model MODEL]
canon.py trace on [--here]
canon.py trace off [--here]
canon.py trace prune --days N
```

- `start` prints `trace <id>`, or `trace off` without touching Git or writing anything when tracing is off. It resolves each `DOC`, which must be shaped like a doc id such as `D001`, to `<doc>@r<revision>` from the doc's frontmatter, keeping a doc it cannot find as given; checks that `--model` is one line of at most 200 characters, like a reviewer's `model`; checks that `--parent` names an open unit that is neither a slice nor an end check, and an `implement` unit for a slice, and that a kind of the first row of [Units](#units) has none; resolves `--base` to the merge base of that commit and HEAD, which is the commit itself when HEAD descends from it, and treats a `--base` without a merge base, or on an unborn branch, as absent; for a `gate` whose first `DOC`, its target, has an `as_built` that names a commit ([D002§as-built-revisions: as-built revisions](D002-overview-and-as-built.md#as-built-revisions)), keeps that commit itself, never its merge base with HEAD, for the snapshot's second parent, which a snapshot without a first parent does not get; takes a [snapshot](#snapshots); computes the [manifest](#skill-digests); and appends one line.
- A review `start --continues UNIT` links a new unit to a handoff end of the same review kind and primary revision, or the same recorded base and plan for a code review. Keep this link separate from the nesting parent. Reject a second continuation of the same handoff under the event lock. An additional handoff can be continued by its own ID.
- `end` closes the open unit `UNIT` and prints `trace <id> ended`, or, like `start`, `trace off` when tracing is off; `OUTCOME` must be one the unit's kind allows, and `--to` comes with `escalated` only. `--dir`, taken from the checkout's root when relative, must lie under that root's `.canon/`. It copies the regular files directly in it that changed since the unit started into `.canon/canon/trace/<id>/` when they total at most 2 MiB, and otherwise copies nothing; no such file records `none`, and a missing directory `copy: ENOENT`, the unit ending either way. It copies only once the final check under `events.lock` passes, so a call that fails that check archives nothing. `--input` reads the [dispositions](#review-dispositions).
- `status` prints whether tracing is on and why; the open units started in the last 24 hours, newest first, with their ids, kinds, docs and start times, marking those of this conversation when the host names it; the number of snapshots, and of skipped ones by reason; and the snapshot repository's disk size.
- `history [UNIT]` locates existing logs irrespective of the trace switch. A linked worktree configured to share trace storage reads both its main checkout's log and its own fallback log. Discover the existing Git directory relationship without creating a directory or probing write access. Elsewhere read only the local log. Pair a unit and its archives within its originating store. Report a scoped ID that names distinct units in both stores as ambiguous. The unfiltered view lists every unit by start time with its ID, kind, parent, outcome, elapsed wall time and archive status. It flags unmatched non-slice starts including ones older than 24 hours, orphan ends, rechecks without a matching closed review or finding, and review archives recorded as `none`, failed, unrequested or `ok` but missing on disk. When files are missing, report the observation. Pruning is a possible cause and leaves no evidence of its own. An archive consisting solely of a snapshot diagnostic does not establish that review artifacts survive. The report never infers a recovery path in another worktree. Group counts and measured wall seconds by kind. A parent's duration includes its children. Present kinds separately and omit a combined total. A slice has an implicit end under [Units](#units). When locally available Git objects identify a unique completion commit for the recorded plan ID, revision and slice after the starting HEAD, show the commit, its timestamp and the measured duration. Follow that plan ID across renames. If the necessary objects are missing, use the recorded event boundary when present. With no boundary yet, show it as open under its parent. A slice never counts as a missing explicit end. Where event boundaries alone give only an upper bound, label it as such and exclude it from measured totals. Missing or reversed timestamps yield unknown duration. Count malformed or unsupported event lines and preserve usable records. Empty history is a valid empty result. Show the predecessor and continuation IDs of a handed-off review and identify partial coverage. A scoped read rejects an unknown unit. Print the same identity, timing, outcome and archive fields for every kind. For an open review, mark dispositions pending. For a closed review show its reviewers, exact coverage where recorded, findings, first confirmation, rechecks and the latest known verdict with reviewer and snapshot. Legacy omissions display as unknown. History writes no files and never opens host transcripts.
- `recheck` appends the outcome of an independently requested targeted recheck of a finding in a closed gate, follow-up or code review, as [Review dispositions](#review-dispositions) defines. An append and an identical retry both print `trace <id> rechecked`. With tracing off it prints `trace off`. The locks, bounded event size and input error behavior of `end` also apply.
- `on` and `off` create and delete the machine switch; with `--here` they delete and create the `off` file of this checkout's trace directory.
- `prune --days N` deletes the snapshots and archives of units started more than N days ago, and the index copies and `.init-<id>` directories that interrupted starts left more than an hour ago, keeps every line, and runs `git gc --prune=1.hour.ago` in the snapshot repository: the space returns at once, while objects written in the last hour stay. When the snapshot repository exists, prune holds `snapshot.lock` through its deletions and its `gc`, so no start writes there meanwhile.
- Every subcommand exits 0 unless its arguments are invalid or `canon.py` refuses to run, from outside the project or as older than it ([D004§install: install](D004-project-setup.md#install), [D004§project-version: project version](D004-project-setup.md#project-version)). Invalid input (an id that is not an open unit, an outcome the kind does not allow, invalid dispositions) or an events file that cannot be written prints `trace error: <reason>` and appends no line; the agent may correct its input and repeat the call once, then carries on either way. What a failed call stored first, such as a snapshot or an archive, is an orphan that readers ignore and `prune` removes by the time in its id. A failed snapshot, or a checkout outside Git, does not fail `start`: it writes the line without a snapshot.
- A call waits at most 5 s for a lock. A timeout on `events.lock` is a `trace error`; on `snapshot.lock`, a start skips its snapshot and skill storage, and a prune is a `trace error` that deletes nothing.

### Event lines

Each line of `events.jsonl` is one compact UTF-8 JSON object of at most 16 KiB, appended in a single write:

```text
{"v":1,"type":"manifest","digest":"<sha256>","skills":{"canon":"<sha256>","canon-code-review":"<sha256>"}}
{"v":1,"type":"start","id":"20261020T081502Z-3f9a1c","kind":"code-review","at":"2026-10-20T16:15:02+08:00","parent":"20261020T070011Z-91c2d4","docs":["D012@r3","P007@r2"],"tier":"L2","base":"<commit>","head":"<commit>","snapshot":"<commit>","host":"cursor","conversation":"<uuid>","model":"claude-opus-5.5","skill":"/home/me/.agents/skills/canon-code-review","manifest":"<sha256>"}
{"v":1,"type":"end","id":"20261020T081502Z-3f9a1c","kind":"code-review","at":"2026-10-20T16:41:37+08:00","outcome":"delivered","head":"<commit>","manifest":"<sha256>","dispositions":{},"archive":"ok"}
{"v":1,"type":"recheck","id":"20261020T081502Z-3f9a1c","kind":"code-review","at":"2026-10-21T09:00:00+08:00","finding":"spec:F1","reviewer":"cross-family-2","model":"Reviewer-X","snapshot":"1234567890abcdef1234567890abcdef12345678","report":"cross-family-recheck2","order":2,"result":"resolved"}
```

- `id`: the UTC start time and 6 random hex digits; it also names the snapshot ref and the archive.
- `at`: local time with its UTC offset, to the second.
- `parent`: the `--parent` unit, null for a top-level unit. A continuation adds `continues` with the previous handoff unit ID and `archive_since_ns` with its start time in Unix epoch nanoseconds. The archive uses this cutoff to distinguish files updated within the same second. Older starts use the second recorded in their ID.
- `head`, `base` and `snapshot` are full commit ids: `base` as `start` resolved it, `snapshot` in the snapshot repository. `head` is null on an unborn branch or outside Git; `snapshot` is null when none was recorded, with `skipped` giving the reason.
- A reason, in `skipped` or `archive`, is `changes-over-10MiB`, `no-git` or `over-2MiB`, or names the step that failed and how: `<step>: exit <n>` for a Git command, `<step>: <errno name>` for a file operation, `<step>: timeout` for a lock. `<step>` is the Git command (`git add`), `index copy`, `snapshot lock` or `copy`. A reason never holds a path or a message; Git's message, when there is one, goes to `.canon/canon/trace/<id>/snapshot-error.txt`, never to the line or the agent.
- `tier` defaults to the parent's, and a slice takes its parent's `skill` and `model` and records its `S<n>` as `slice`. `skill` is the absolute path of `--skill`, null without it. A start’s `model` is stored in lowercase. `host` comes from the environment: `cursor` when `CURSOR_AGENT=1`, `codex` when `CODEX_THREAD_ID` is set, `claude-code` when `CLAUDECODE=1`, else `other`. `conversation` is `CURSOR_CONVERSATION_ID` or `CODEX_THREAD_ID`, else null.
- `manifest` is written on every start and on the end of a top-level unit, null when `skill` is. A `manifest` line precedes the first use of each digest in the file.
- An end line carries `outcome`, `to` for `escalated`, `head`, `manifest` for a top-level unit, `dispositions` for a gate or code review, null without `--input`, and `archive`: `ok`, `none` or the reason nothing was copied, null without `--dir`. A review end may carry `review_input` ([First-round review input](#first-round-review-input)).
- A unit other than a slice is open from its start until its end; the analysis treats one with no end after 24 hours as incomplete.
- A `recheck` line uses the keys shown above. `id` and `kind` identify the closed review. Store `finding` as the first source in the merged finding’s `by` list, whichever alias the caller supplied. Store `order` as a positive integer or JSON null for `unknown`. Preserve the exact case of `model` from the reviewer or `--model`. The event extends the original end with new evidence.
- Readers skip and count lines that do not parse or carry an unknown `v`.

### Snapshots

Every start records a snapshot of the work tree in the snapshot repository, a non-bare repository with no remote that `start` creates on first use with `git init --template=` and the project's object format, its HEAD on an empty commit. It is built in `.init-<id>` and renamed to `.git`, so a `.git` there is always complete; a failed rename records `git init: <errno name>`. A snapshot holds what `git add -A` and a commit would record: files ignored by `.gitignore`, `.git/info/exclude` or `core.excludesFile` stay out, and a submodule is recorded at its checked-out commit, without changes inside it. Every Git command run against the project sets `GIT_OPTIONAL_LOCKS=0`, so none of them rewrites the project's index, and snapshot commits use the fixed identity `canon-trace <trace@canon.invalid>`, so they need no Git user configuration.

1. List the untracked files and the files with unstaged changes with `git status --porcelain -z --untracked-files=all`; when they total more than 10 MiB, record no snapshot and set `"skipped": "changes-over-10MiB"`.
2. Copy the checkout's index (`git rev-parse --git-path index`) to `index-<id>` in the snapshot repository's Git directory, keeping its modification time, which Git compares entries against to find racily clean ones; when there is no index, start without one.
3. With `GIT_INDEX_FILE` set to that copy, `GIT_OBJECT_DIRECTORY` to the snapshot repository's objects and `GIT_ALTERNATE_OBJECT_DIRECTORIES` to the project's, run `git add -A` and `git write-tree`.
4. With the same variables, `git commit-tree` the tree of the resolved base, or of HEAD without `--base`, as a parentless commit, then the snapshot tree as a commit whose parent is that one; on an unborn branch without `--base`, the snapshot commit has no parent, not even the as-built one below. `git diff <snapshot>^ <snapshot>` then shows the opening work-tree change. For an as-built gate, the tree of its `as_built` commit becomes a second parentless commit and the snapshot's second parent, so `git show <snapshot>^2:<path>` gives the code the revision records.
5. List the objects the snapshot reaches with `git rev-list --objects <commit>`, keep those that `git cat-file --batch-check`, run in the snapshot repository without the variables, reports missing, pack them with `git pack-objects --stdout` into a temporary file in the snapshot repository's Git directory, and feed that to `git index-pack --stdin` there.
6. Run `git update-ref refs/trace/<id> <commit>` in the snapshot repository, which records the snapshot. Then, best-effort and never setting `skipped`, delete the index copy and run `git -c gc.autoDetach=false gc --auto --quiet` there, which repacks once 50 packs or 6,700 loose objects accumulate.

New objects land only in the snapshot repository, and step 5 copies in each object the snapshot borrows from the project, once: the snapshot repository depends on nothing outside it, so rebasing, deleting branches or `git gc --prune=now` in the project cannot break a snapshot, and switching branches back and forth copies each file version once. The whole tree is copied again only into an empty snapshot repository. The project's work tree, index, HEAD and refs do not change, nor do the names and contents of the files in its object store; Git refreshes the modification time of an existing object that a snapshot step writes again, as it does on any such write. Starting from `git read-tree HEAD` instead of a copied index rehashes every file, 10 times slower in a 20,000-file checkout.

No push, clone or bundle of the project reaches the snapshot repository, `git push --mirror` and `git bundle create --all` included: its refs are not the project's, and no commit of the project holds its files ([Switch and storage](#switch-and-storage)). In a 20,000-file checkout with 45 MiB of packed objects, the first snapshot copied the whole tree, 45 MiB in 1.3 s; later ones took about 100 ms and added 15 to 100 KiB, about 10 KiB once repacked. Moving to a branch that changes 2,000 files copied their 2,006 objects, 4.6 MiB, once; switching back and forth afterwards copied nothing.

### First-round review input

A review's start snapshot captures the opening work tree. A gate, follow-up or code review can send a different tree or diff to its first-round reviewers. Before dispatch, the session saves the actual target snapshot commit in `snapshot.txt` and the resolved baseline commit from the prompt in `baseline.txt`, alongside it in the round directory. The baseline can be a project commit or a separately prepared review snapshot. Write `none` for a full-document review with no diff. A code review requires a baseline. Resolve a moving ref when preparing the prompt and use that same commit in the prompt. For a prepared snapshot pair, the host can supply the scoped patch and paths as review input. Recording its pins grants no new reviewer access to the snapshot store. Keep these first-round files through confirmation.

When `trace end --dir` successfully archives these two regular files for this review, retain their trees from the closing checkout's review snapshot store, including project objects it borrows. Each pin holds one full 40- or 64-hex commit ID, apart from the explicit `none`. Preserve just the reachable contents of the pinned trees in the unit's independent trace repository. Publish a synthetic commit at `refs/review-input/<unit>` with the target tree and, for a diff, one parentless commit holding the baseline tree as its only parent. The end event's `review_input` is the synthetic commit ID. A mirror clone can read its target with `git ls-tree -r <review_input>` and its exact diff with `git diff <review_input>^ <review_input>`, using any path scope from the prompt. For a live code review, remove the listed untracked paths from a temporary index of the target only, diff it against the baseline and verify those files' blobs and modes in the complete target. For a prepared patch, compare the same diff options and path scope.

Missing, malformed, unarchived or unavailable pins, a non-commit object, or failed retention leave the review end and its evidence usable with unknown input. An old end without the field also has unknown retained input. Keep opening snapshots and historical event lines intact. Serialize publication with trace snapshot pruning and the accepted end. A rejected competing end cannot replace the accepted pair. Prune the review-input ref at the unit's age cutoff along with its start ref. Scoped history reports the retained ID or unknown. An ID records what was retained at close, including after pruning.

This pair identifies the round's initial input. A continuation, follow-up, handoff or a review with mixed or unverified source inputs remains subject to the replay exclusions. A later confirmation or supplemental snapshot never replaces this pair.

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
- `model`: the reviewer's model id, as a gate writes it to the doc's `reviewers`; a run the user made has `manual:` before it. `id`: the agent id kept for the confirmation round, or the session id a command run reports, such as `codex exec`'s, as `<key>-id.txt` holds it; null for a manual run or an empty id file ([D003§reviewers: reviewers](D003-subagents.md#reviewers)). `model` and a non-null `id` are each one line of at most 200 characters.
- Each independently numbered findings report has a unique source key in the round, bound to its actual author, report file and assessed targets. The first report in a role uses the role name. A supplemental report by the same reviewer has its own next key, so each report may number its findings from F1. Additional reviewers of the same role use that name with a numbered suffix starting at 2, for example `cross-family-2`. The optional `key` defaults to `role`. A numbered key is that role plus a hyphen and a decimal integer of 2 or greater with no leading zero. Gaps are allowed. Reject a key for another role, duplicate keys and repeated `<key>:F<n>` references within or across merged findings. A model and session may recur under different keys. For gates and follow-ups only, optional `targets` is a nonempty list of distinct canonical design or plan IDs with a positive exact `@rN`, including design suffixes. Code reviews reject `targets`. The session supplies it for each gate report with known coverage. Read older records without these fields as a single reviewer per role with unknown coverage. A waived or failed launch supplies no reviewer entry.
- One entry per merged finding. `by` lists every reviewer finding merged into it as `<key>:<F-id>`; `severity` is the highest among them; in a code review, `axis` is `spec` or `standards`.
- `disposition`: `accepted` (fixed in this work, including by a design revision the user decided on), `declined`, `escalated` (still awaiting the user at `end`, as is any finding not yet disposed when a handoff ends the review) or `deferred` (left for later by the user's decision, and tracked as the `canon` workflow's review gate and code review say), in a gate as in a code review.
- `confirmed` retains the first confirmation's result. New records supply `confirmations`, a nonempty list with one entry per actual confirmer of this merged finding. Each entry has exactly a `reviewer` key listed in the review, a `result` of `resolved` or `not-resolved`, and a `snapshot` containing a 40- or 64-hex object ID or null when unavailable. Reject a repeated confirmer key within one finding. A delegate keeps its own identity. One `not-resolved` makes the first aggregate `not-resolved`. Otherwise it is `resolved`. Require `confirmed` with the list and validate that aggregate against it. Old records with only `confirmed` keep their result with unknown individual authorship. `new_blockers` counts blockers the confirmation reported as new.
- Retain each explicit later recheck's own report in the review directory, with a distinct filename such as `cross-family-recheck2.md`. After the original end has been recorded, append it with `trace recheck`. `FINDING` may name any source of that merged finding. `KEY` identifies who actually rechecked, including a delegate. Use its recorded model, or supply `--model` for a previously unlisted reviewer with a fresh key of a valid role. Preserve model spelling. For an existing key omit `--model` or repeat its exact case-sensitive model ID. A new key needs a nonempty, single-line model ID of at most 200 characters. These checks include earlier rechecks in this unit. `OID` is a full 40- or 64-hex ID, normalized to lowercase for storage and comparison. Both recheck and confirmation snapshot IDs are validated by syntax alone so preserved evidence survives Git pruning. `STEM` identifies the actual local report, using ASCII letters, digits, hyphens or underscores, at most 100 characters. Supply `--order N` for the positive sequence number established from the reports for this merged finding. A historical import of uncertain order uses `unknown`. A known ordinal belongs to a single report for that finding. The event contains no report text or arbitrary file path. A session may record a historical recheck from its preserved evidence. Without an actual report or preserved evidence of its outcome, leave the result unknown. Losing the report after recording it leaves its recorded verdict intact.
- Append under the existing event lock. The unit, merged finding and report stem identify a recheck. An identical retry succeeds once in the log, including through another source of that finding. Reject conflicting retries, unrecognized findings and reviewer identities, and invalid results or snapshots without appending. Show all rechecks. The highest verified ordinal gives the latest known verdict on the merged claim even when imports arrive out of order. List unordered evidence separately and mark the definitive latest verdict unknown when it could postdate the ordered results. Check imported reviewer identities against the review. Flag conflicting uses of a report stem or ordinal and show the latest result as unknown when a conflict could postdate the highest verified result. Preserve the first confirmation and its individual verdicts. Rechecks grant no new gate, approval or change to review coverage.

### Review files

`canon-blind-review`, and `canon-code-review` for its axis reviewers, keep each reviewer's files in `.canon/canon-blind-review/<topic>/` under its reviewer key: `<key>-prompt.md`, `<key>.md` with its findings and `<key>-id.txt` with the one id of the run whose report the session merged, then `<key>-confirm-prompt.md` and `<key>-confirm.md` for the confirmation round. Keep the original ID file for the run whose report was merged, empty if it has no ID. Each fresh confirmation has `<key>-confirm-id.txt`. When a source delegates findings to both code-review axes, use a distinct `<source-key>-confirm-<confirmer-key>` stem for each axis and store its prompt, complete report, run ID and fixed snapshot as `<stem>-prompt.md`, `<stem>.md`, `<stem>-id.txt` and `<stem>-snapshot.txt`. Each prompt uses that source’s original finding IDs and input snapshot. Every supplemental report gets its own key and input and confirmation snapshot IDs as [D007§target-coverage: target coverage](D007-change-tiers.md#target-coverage) specifies. A recheck keeps `<stem>-prompt.md`, `<stem>.md`, `<stem>-id.txt` and `<stem>-snapshot.txt`. The archive at `end` is a one-time copy. A report created after the end stays in the review directory. For each recorded recheck, history reports whether its exact `<stem>.md` survives in the unit archive. Missing evidence leaves the recorded result visible. A confirmation never overwrites the first round's findings, so each `by` id resolves in the archive. A gate's topic is its target's id and the revision it reviews, `<id>-r<N>` such as `D007-r4`, a joint gate's too, so a later gate never overwrites it; each [D007§follow-up-round: follow-up round](D007-change-tiers.md#follow-up-round) keeps its files, named the same way, in `<topic>/followup-<k>/`, numbered from 1. A code review's topic is `<P id>-code-review`, else a slug of the change, so it never shares its plan gate's directory.

### Skill digests

A skill's digest covers every regular file under its directory except `LICENSE`, `NOTICE`, `__pycache__/`, `*.pyc` and names starting with `.`. Each file contributes its Git blob id, the SHA-1 of `blob <size>\0` followed by its bytes. The digest is the SHA-256 of the compact UTF-8 JSON, without ASCII escaping, of the sorted list of `[relative_posix_path, blob_id]` pairs.

The manifest maps each directory named `canon` or `canon-*` that holds a `SKILL.md` to its digest. Such directories are searched beside `--skill`, or, when the parent of its parent is named `skills` (the skills repository's `skills/<category>/<name>/` layout), in every category directory. The manifest digest is the SHA-256 of the manifest's compact JSON with sorted keys. A unit whose start and end manifests differ, or whose children recorded another manifest, is mixed-version.

The analysis maps each digest to the skills-repository commits whose tree gives the same digest, from `git ls-tree -r` blob ids. A digest that matches no commit is `local`: an edited or uncommitted copy.

A start whose manifest the snapshot repository lacks also stores the files each digest covers there, as a parentless commit at `refs/skills/<manifest digest>` whose tree holds each skill directory under its name. Storing is best-effort: when it fails, the next start with that manifest stores it. A replay can thus run any recorded version, `local` ones included, and each new version adds only the files it changed.

### Analysis

`scripts/trace_report.py` lives in the skills repository and is not installed with the skills:

```text
python3 scripts/trace_report.py [--project PATH ...] [--since YYYY-MM-DD] [--skills-repo PATH]
                                [--cursor-home DIR] [--cursor-state-db FILE] [--codex-home DIR ...]
                                [--review-evidence TSV] [--json]
```

It reads each project's events, archives, docs, Git history and retro records, and the host records in place, and writes nothing. `--cursor-home` defaults to `~/.cursor`; `--codex-home` defaults to `$CODEX_HOME`, else `~/.codex`, and repeats for a second Codex home such as the Windows side of WSL. Records of other hosts are not read, so their tokens are unknown.

Units link to host records this way:

- Cursor: the transcript named by `conversation`. A unit spans its matched start through its end or slice boundary. For incomplete exports, follow [Reconciling pilot evidence](#reconciling-pilot-evidence).
- Codex: the rollout whose file name holds `conversation`, else the one whose tool output contains `trace <id>`. A unit's tokens are the difference between the cumulative `token_count` totals at its start and its end. Subagent rollouts, found by `parent_thread_id`, are reported separately and never added to the parent.
- A reviewer's tokens come from the Codex rollout its `id` names: a subagent's `agent_path`, or the session id of a command run.

Each question is computed from:

1. Count a merged finding once when every source key has the cross-family role. The denominator counts each review with at least one actual cross-family report once. Show costs by participating reviewer key and count each distinct session's cost once. A missing cost is unknown.
2. Initial `not-resolved` over confirmed findings, with later recheck results reported separately; `new_blockers` per confirmation round.
3. Valid findings per axis over code reviews, by tier.
4. Slice outcomes from the plan at the slice's commit, or the Log and stash of a paused slice, and the worker reports in the host record, over slices started, each counted once however many units it spans, with and without a `Risk:` line.
5. Implement units that changed tier or needed a plan, by target, over implement units by starting tier: `escalated` ones by `--to`, and those started at L0 with a gate at L1 under them, at any depth, as `L1`; a unit counts under every target it reached. Design units whose gate ran at a higher tier than they started at, over design units started at L1.
6. Wall time per kind, from start to end, a slice's ending as [Units](#units) states; subagents launched within a unit's span; tokens where recorded. Cursor wall time includes waiting for the user.
7. For each `applied <commit>` cause in `notes.md`: its `fix=present` events from traced sessions, matched by `conversation` or, for a session named by time, by the start minute of a traced end check or retro, over the units started after the fix whose snapshot holds it, meaning the fix commit's diff applies to the snapshot in reverse (`git apply --check -R`). Units where neither direction applies, or without a snapshot, are counted as unknown and left out. Also repeated identical commands per unit before and after the fix.
8. `end-check` units with their time and tokens, and `raised` end checks over top-level units that ended; declined items from `notes.md`.
9. The replayable units are slices with a snapshot and reviews meeting the single-input rule in [Replay](#replay). List their parameters, dispositions and manifests, whether each was steered, and why a unit has no snapshot or is excluded from scoring.

Rules:

- Compare only within the same kind, tier, host, model and skill digest. An implement or design unit's tier is the highest of its starting tier and those of the gates under it.
- Show every rate as numerator over denominator; with fewer than 20 units, mark it "few units" and list the cases.
- Write `unknown` for what a host does not record, never an estimate.
- List the cases behind every number with their unit ids and record locations.
- Start with the projects read, the lines skipped, the open and incomplete units, and a reminder that untraced work is unknown, not absent.
- A gate or code review that ended `handoff` is incomplete: list it with its dispositions so far, and leave it out of questions 1 to 3 and of replay scoring, since a continuing unit may record the completed review. Count a completed review once at the delivered end for questions 1 to 3, including one with results from different input snapshots. An absent continuation remains incomplete. Question 9 lists continuations and mixed or unknown review inputs as excluded from scoring.

### Reconciling pilot evidence

Keep the project's original events, review archives, host records and Git times intact. Record a correction separately with the project, unit, raw finding or boundary, source location and result. Report the raw and reconciled counts with their denominators. Keep unresolved evidence visible as `unknown`.

**Review attribution.** Compare each delivered first-round report with the end's reviewer entries and finding sources. A report's key identifies its independent numbering, even when another report has the same role, model or finding number. Use the original report and its run or dispatch evidence to recover missing authorship. A shared finding requires evidence that the reports describe the same defect and required correction. Preserve every reporting source and disposition. Equivalent wording, a common file or the same finding number alone cannot establish equivalence. Count a verified defect once and credit each contributor jointly. Count an exclusive contribution only with complete source coverage for that defect. Keep disputed merges, missing authorship and unverified dispositions out of the corresponding contribution totals. A handoff retains its partial coverage.

`--review-evidence TSV` supplies a locally adjudicated table, also used for a pilot. Key rows by the selected project, review unit, one-based raw disposition row (empty for an omitted source), report stem and finding ID. Record a unit-local defect group or `unknown`, the adjudicated disposition or `unknown`, a source locator and the SHA-256 digests of the end line (excluding its newline) and source report bytes. For Silk's commit-title unit, raw row 1 `spec:F1` and row 3 `standards:F1` map to the same group. Match each unit and its evidence unambiguously to the selected project before applying a correction. Conflicting, stale or incomplete mappings leave affected attribution unknown. Without a table, retain the end's explicit groupings and distinguish raw totals from independently verified contributions. A pilot table can be used directly from the experiment attachments.

**Cursor boundaries.** Look first in the named conversation's export. For a missing start, a caller may supply a local Cursor state database for read-only verification. Limit the lookup to tool-call records of that conversation. Match the executed start's kind, targets, slice, parent, tier and other distinguishing arguments to the event, using the host timestamp and surrounding boundaries to disambiguate. Require one execution and one matching unit. Record which source established each boundary. Missing, ambiguous, inaccessible or unsupported evidence yields unknown. A database start locates that boundary only. Count tokens and intermediate tool calls only where their own records support them.

**Worker chronology.** Link each actual run, including resumes and replacements, to its plan, slice and parent session. Compare dispatch and the worker's terminal report with the slice's recorded start and its earliest closing boundary. For an interrupted or failed attempt with no report, a verified host termination closes that run. Record the missing report and assess a replacement from its own dispatch. Use the host's event order or timestamps at their recorded precision. An intermediate update or a delayed parent notification cannot establish when the worker finished. Record each interval as contained, outside, or unknown. Keep an outside run with its observed boundary and exclude its incomplete span from full worker-duration comparisons. A new real slice can verify that the existing wait-before-commit rule works when followed. Report prospective results separately from the frozen cohort and retain every original exception in the pilot verdict.

### Replay

Question 9 compares skill versions on recorded units. A replay clones a unit's snapshot from the snapshot repository into a scratch directory, installs a skill version, the one under test or the recorded one from `refs/skills/<manifest>`, runs the unit headless with its recorded `docs`, `slice` and `tier`, the same models and, where the host records them, the same efforts, the retained first-round input and its baseline for a review, the opening snapshot for a slice, and the opening snapshot's second parent for as-built code only after verifying its tree against the commit the reviewed target and prompt name, and scores the result:

- Only score a gate or code review whose original findings all refer to the input the replay will restore. Exclude every continuation from single-snapshot scoring. Also exclude reviews whose late or supplemental reports used different input trees or whose common input cannot be established. Compare retained input trees and the review base and targets when separate snapshots exist. Exclude as-built gates when the reviewed code tree differs from the opening second parent or their equivalence is unknown. List the reason, preserve all historical findings and keep these reviews outside the replayable-unit count. Score eligible reviews against their original dispositions. Valid findings should be found again and declined ones count as false positives. Later rechecks record subsequent evidence separately.
- A slice by its test criteria, whether a worker reported `blocked` or `stuck`, and the code-review findings that followed; a run the host stopped does not count against it.

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
3. `scripts/trace_report.py`, tested on redacted real Cursor transcripts and Codex rollouts, plus a minimal database fixture for missing, unique, ambiguous and cross-conversation start candidates.
4. The replay harness, as its own design.

Delivery is staged: each step starts once the one before it has ended, so [Analysis](#analysis) specifies step 3 ahead of its code, and [Replay](#replay) states what step 4 can rely on. Until step 3 lands, `implemented` is the latest revision whose step 1 the repository fully implements, and step 1 ends when `implemented` reaches `revision`. Only units traced after that count toward the pilot, and neither a capture fix during the pilot nor a revision that changes no capture restarts it; the check of the text [budgets](#budgets) lies outside the staged steps. Step 3 is written against the revision current when the pilot ends; the change that delivers it adds `scripts/trace_report.py` to `paths`, and from then on `implemented` counts steps 1 and 3. Step 4 starts once step 3 has ended and 20 replayable units exist.

Scenarios for step 1, tested through the commands:

- A joint gate accepts independently keyed reports, precise per-revision coverage and different first-confirmation results on a merged finding. Old dispositions remain readable. Invalid keys, references and conflicting aggregate results leave the trace unchanged.
- Ordered and unordered rechecks of a closed review preserve the first confirmation, including when reports are imported out of order. Identical concurrent retries through different finding aliases append once. Conflicting reports or invalid snapshot IDs append nothing. A handoff admits one continuation under competing starts.
- With tracing on or off, historical queries leave files and directories untouched, find old open units and report missing or diagnostic-only archives. Linked checkouts with both main and fallback logs retain the originating store. Check wall seconds separately for each kind, with upper bounds excluded from measured durations.

- With no machine switch, or with an `off` file, `start` prints `trace off`, runs no Git command and writes nothing.
- A clean checkout's snapshot has HEAD's tree.
- A dirty checkout's snapshot holds unstaged, staged and untracked changes and no ignored file, and leaves the project's work tree, index, HEAD, refs and the names and contents of its object files unchanged, the index byte for byte even after a tracked file's timestamp changed without its content.
- An unborn branch without an index gets a snapshot without a parent. Untracked and unstaged files over 10 MiB in total, a checkout outside Git and a failing Git command skip the snapshot, and the start line records the reason; a failing Git command's message lands in `snapshot-error.txt`, and `start` prints only its id.
- A code review whose fixed point moved on after the branch forked gets the merge base as its opening `base`. A separately prepared baseline and target in a linked checkout survive removal of the checkout and its review store. After an independent mirror clone of the trace store, compare the prepared patch byte for byte, including a binary addition. For a live review, compare its tracked patch and separately listed untracked files. An as-built commit changed between opening and dispatch remains distinguishable in the two retained documents and disqualifies replay if its code tree differs.
- A gate on a doc whose `as_built` names a commit that HEAD has moved past, or that a rebase left out of HEAD's history, gets that commit's tree as the snapshot's second parent: `git show <snapshot>^2:<path>` gives each file as it was at that commit, and `git diff <snapshot>^ <snapshot>` still shows the change since `--base`.
- A snapshot copies only the objects the snapshot repository lacks; switching to another branch and back copies each file version once. `git push --mirror`, `git clone --mirror` and `git bundle create --all` of the project carry no snapshot. After a reset, `git reflog expire --expire=now --all` and `git gc --prune=now` in the project, `git fsck --strict` passes in the snapshot repository and every snapshot can be read. With `.canon/` missing from the project's `.gitignore` and `.canon/canon/.gitignore` deleted, `git add -A` stages no file inside the trace directory and `git clean -fdx` leaves it.
- A child records its `--parent`; a parent that is not open, a slice or end check as parent, and a slice whose parent is not an `implement` unit are rejected and write nothing; a gate or end check without `--parent` is top-level.
- `end` closes the unit it names; an id that is not an open unit, an outcome its kind does not allow, or `--to` without `escalated` writes nothing. Valid dispositions land in the end line; invalid ones write nothing. `--dir` archives only the files changed since the unit started, nothing when they exceed 2 MiB, and the line says why; an unreadable file gives `copy: EACCES` and no path.
- Editing a skill file changes its digest, and `LICENSE`, `NOTICE` and caches do not; the source layout finds skills across categories; each manifest line is written once, and each new manifest's skill files are stored once at `refs/skills/<manifest digest>`.
- `prune` removes the snapshots and archives older than N days, keeps the lines, and shrinks the snapshot repository.
- In a linked worktree at `.worktrees/<branch>`, `start`, `end` and `status` use the main checkout's trace directory and its `off` file, while the snapshot records the worktree's work tree and index, and `DOC` and a relative `--dir` resolve in the worktree; with the main checkout's `.canon/canon/` not writable, they use the worktree's own; a linked worktree elsewhere, another repository's linked worktree under `.worktrees/`, and a submodule, one inside such a worktree included, use their own.

Pilot exit:

- At least 18 of 20 top-level units have a start and an end, or a genuine interruption.
- Every review's dispositions match its conversation. Compare raw and reconciled dispositions using the source reports. Mark any unverifiable claim explicitly.
- Every unit's parent, tier and outcome match its conversation, tier changes included.
- From an independent trace clone, verify opening documents and slice plans at the start ref, and reviewed documents and patches at the retained first-round ref, with the prompt's scope and verified as-built code where applicable. For older records count an opening snapshot as equivalent only with independent evidence for the actual input. To test a capture repair, submit the independently recovered historical inputs to fresh units, verify their clones and report them separately from the original capture results.
- Every Cursor and Codex unit is found in its host record.
- Every worker run, resumed and replacement runs included, falls within one unit of its slice, and no slice's unit is ended by another `start` of the same slice. A prospective run verifies the execution procedure. It cannot clear a failure of this condition in the frozen cohort or authorize step 3 on its own.
- No host in use has a snapshot skipped because its sandbox could not write the trace directory.

If capture falls short, it is fixed before the report is built. [E003: Canon and Silk pilot](../experiments/E003-d001-trace-pilot.md) records the frozen cohort and its original results. [E004: review input revalidation](../experiments/E004-d001-review-input-revalidation.md) verifies the three recovered inputs through independent clones and records the remaining exit failures.

## Budgets

Calls and latency are measured in the pilot; `canon.py` enforces the sizes, and `scripts/validate.py` checks the text limits, as [D000§dependencies: dependencies](D000-project-overview.md#dependencies) says.

- Calls: two ordinary boundary calls per unit except a slice, which takes one. Each independently requested recheck adds one call; one per skill invocation when tracing is off.
- Text, counted in tiktoken's `cl100k_base` tokens: at most 40 per call site in a skill, which is the sentence holding a `canon.py trace start` or `end` call, a code span never ending it; at most 110 for the `canon` skill's paragraph on the placeholders and the first-start rule, the one that starts with ``In `trace` calls``, read whether tracing is on or off; `trace.md` at most 420, read only when tracing is on. Link detailed field definitions from this concise guide for callers recording review evidence.
- Latency: `start` and `end` p95 under 300 ms on a local disk, including a snapshot of a 20,000-file checkout and the digests of 20 skill directories of 1 MiB in total; a checkout's first snapshot, which copies the whole tree, is exempt.
- Size: 16 KiB per line, 2 MiB per archive, 10 MiB of untracked and unstaged files per snapshot, 64 KiB per `snapshot-error.txt`, which keeps the end of Git's message.

## Decisions

- One original confirmation and subsequent report-addressed rechecks preserve both what a gate concluded and what later evidence changed. Silk found three old unresolved results with resolved rechecks, and reviewing a 31-start inventory required matching its ends and archives by hand. [R004: Silk feedback](../archived/reviews/R004-silk-canon-field-feedback.md)

- Agents make only mechanical `trace` calls, plus the review dispositions: written reports cost tokens and attention and are unreliable, and everything else already exists in docs, Git and host records.
- `trace` lives in the project's `canon.py`: agents already run it from a known path with standing permission, and the in-project part is small. The analysis lives in the skills repository, where skill changes are made.
- A machine switch with a per-checkout opt-out, never a `canon-init` question: the skills are public, and other users never meet tracing.
- Snapshots live in a repository of their own, never in the project's refs: no push, clone or bundle of the project can carry one, `--mirror` included, and the project's object store and history views stay untouched. It holds every object its snapshots reach, so nothing done to the project's history breaks a snapshot, and pruning frees space at once. The price is one packed copy of the tree per checkout, 3 to 26% of the object store in six local repositories, and a second copy of what changes while tracing is on.
- All trace data sits in the checkout's `.canon/canon/trace/`: it is the one place the Cursor and Codex sandboxes let an agent write that no commit can hold, since Codex keeps the project's `.git` read-only and Git never adds a file inside a nested repository. Events, archives and snapshots then share a lifetime.
- A linked worktree in `.worktrees/` keeps its trace data in its main checkout's trace directory: canon sends sessions that work at the same time to such worktrees ([D006§concurrent-work: concurrent work](D006-doc-model.md#concurrent-work)), and removing one once its branch merges would remove its units too. The session made the worktree inside the checkout it started in, so its sandbox can write there, and its worktrees share one copy of the tree. A linked worktree elsewhere, such as one a host makes, keeps its own, since its session's sandbox may reach only that worktree (the user's decision, 2026-11-13). For the same reason a call in `.worktrees/` that cannot write the main checkout's falls back to the worktree's own, which keeps the units of a session its host started there (gate of D006 r17). Only `<R>`'s own linked worktrees count, told by their Git directory, so a worktree of a scratch repository made under `.worktrees/` never writes `<R>`'s trace directory (the user's decision, 2026-11-13, on the code review of P006).
- `host` comes from the environment and `model` is stored in lowercase: the analysis groups by both, and names as each agent spells them would split the groups.
- An as-built gate's snapshot takes as its second parent the tree of the commit its target's `as_built` names, which `start` reads from the doc itself: the snapshot repository holds no project history, so the code the revision records reaches a replay only through the snapshot; the first parent still gives the diff from the `Changes since` commit, whose version of the doc can differ from the one at the `as_built` commit; and no call site has to carry the commit.
- Every start takes a snapshot, a clean one included: a clean HEAD can later vanish from the project, and its snapshot adds only what changed since the previous one.
- Snapshots hold what Git would commit, with no per-file limit: a project's ignore files already keep out its data, caches and build outputs. The 10 MiB cap only bounds what a large file not yet ignored would cost, since `git add` hashes it on every start and stores each new version.
- Ignored files a replay needs are the project's to provide: copying them would bloat snapshots and could capture secrets, and the versions a replay compares run against the same files.
- Workers and reviewers never call `trace`: reviewers stay blind and read-only, and the orchestrating session sees every boundary.
- A slice records only its start: its commit, or the plan's Log, already records its end and outcome.
- Children name their parent, and `end` names its unit, by the id `start` printed: exact even when sessions share a checkout, for a few tokens per call, and `trace status` recovers an id lost to compaction.
- Review files are archived when each review ends: `.canon/canon-blind-review/` is scratch space, and the next review of a topic overwrites it.
- A pending review can cross sessions. Its handoff end retains partial coverage and a continuing unit records the completed review. Earlier end lines remain immutable.
- Version exposure comes from content digests mapped to source commits: release numbers and lock hashes do not show the content loaded, and source checkouts are often uncommitted.
- Skill versions are stored with the snapshots: a `local` digest matches no commit, and without its files the version a change replaced could not be replayed.
- Tokens come from host records, offline: no host offers a portable runtime source, and Codex records them locally.
- Retro keeps its records, and the analysis joins `notes.md` and `skills.jsonl` by session, so each record keeps one owner.
- Replays judge skill changes, and real work finds problems and checks recurrence: personal volumes cannot support per-version rates.
- Delivery is staged and, until step 3 lands, `implemented` counts step 1 alone: the analysis is tested on the pilot's real records, which do not exist before it, and a spec lead for code not yet due would show beside every file the design governs (the user's decision; R001-F32).
- Data is kept until the user prunes or deletes it: a baseline at personal volume can take months.
- Evidence feeds human-reviewed experiments, never automatic skill changes.
- A gate's review files go in a directory named by its target and revision, with each follow-up round in a subdirectory: saving D001 revision 8's reports overwrote revision 7's, and sessions invented layouts for joint gates and extra rounds ([R002: Open items from local retro and review records](../archived/reviews/R002-local-records.md), F3; [R003§r003-f10-gate-directory-layout: R003-F10](../archived/reviews/R003-silk-design-phase.md#r003-f10-gate-directory-layout)).
- A follow-up round is a kind of its own, not a gate: returning reviewers assess changes since their prior pass. New targets and previously waived coverage can require a full review. Counting an ordinary follow-up as a gate would skew the gate questions and replay its findings against a full review.

## Known issues

| ID | Severity | Issue | Source | Since | Next |
|---|---|---|---|---|---|
| D001-K4 | major | Historical dispositions can count the same defect separately by axis or omit supplemental reviewers. Preserve raw rows and establish which attributions have independent evidence before computing reviewer contributions. | E003 at `1b9d5cf` | 2026-11-24 | L1 |
| D001-K5 | major | Two Cursor start commands survive in local application storage and are absent from the documented transcript export. Their ends alone cannot identify the start of either span. | E003 at `1b9d5cf` | 2026-11-24 | L1 |
| D001-K6 | major | Two workers returned their final reports after the commits that closed their slices. Verify the existing wait-before-commit rule against the host's terminal worker event. | E003 at `1b9d5cf` | 2026-11-24 | fix |
