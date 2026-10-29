---
status: active
created: 2026-10-22
updated: 2026-10-29
revision: 3
modules: [canon]
summary: How canon runs reviewers and workers as subagents, new, on the session's model, given only their prompt and resumed by id, and the cross-family reviewer file.
refs: [D001]
owns: [subagents]
paths: [skills/governance/canon/workflow.md, skills/execution/canon-blind-review/SKILL.md, skills/execution/canon-implement/SKILL.md, skills/execution/canon-code-review/SKILL.md, skills/governance/canon-init/SKILL.md, skills/execution/canon-plan/SKILL.md]
reviewed: 3
reviewers: [claude-opus-5.5]
implemented: 3
---

# D003: Subagents

## Goals

1. A reviewer or implementation worker starts with nothing from the session that launches it, so a review stays blind and every slice starts in an empty context window.
2. Subagents run on the model and reasoning effort the user set for the session; only the cross-family reviewer names its own model.
3. A subagent that the workflow continues is resumed whenever the host allows it, so it keeps its context: a reviewer judges the fixes against its own findings, a blocked worker continues with the answer, and a run that stopped finishes instead of starting over.
4. The cross-family reviewer is set up per machine, so the tools and logins it needs never enter the repository.

## Spec

This design covers the subagents of the `canon` workflow, meaning the reviewers of the review gate, of code review and of any other blind review and the workers of `canon-implement`, and the setup of the cross-family reviewer. Subagents that other skills launch for their own steps, such as a codebase review's angles, research, broad searches or alternative interface designs, follow those skills. What a review assesses, and how its findings are merged, belong to the review gate and code review.

### Launch

- Same-model reviewers, workers, and a cross-family reviewer that runs as a host subagent are new subagents from the host's own tool: the Task tool in Cursor, the Agent tool in Claude Code, multi-agent subagents in Codex. None is a fork of the session. A cross-family reviewer can instead run as a command ([Reviewers](#reviewers)).
- Subagents are launched without a model or effort, so they run on the session's, which the user sets. Only a cross-family reviewer that runs as a host subagent gets a model, the one the reviewer file names. Since every worker runs at the session's effort, `canon-plan` names a plan's slices that carry a `Risk:` line beside its closing command and suggests high reasoning effort for the implementation session.
- In Claude Code a reviewer is a `general-purpose` or custom subagent, since the built-in Explore and Plan agents cannot be resumed. A worker is a general-purpose subagent.
- A gate launches its first-round reviewers in parallel, and code review issues its reviewers together, in the foreground. Workers run one at a time, in plan order; work without a plan has no worker.
- The launching session keeps each subagent's id: a reviewer's agent id, or the session id its command reports, in its review files ([D001§review-files: review files](D001-skill-telemetry.md#review-files)), and a worker's agent id in `.canon/canon-implement/<P id>/S<n>-id.txt`.

### Input and reports

- A reviewer's only input is its prompt, which names files in the repository for it to read: the review gate's reviewer prompt in the `canon` workflow, or the `canon-blind-review` template for every other blind review, a code review's carrying the diff command, the untracked files, the commit list and its sources. It never gets the conversation, a summary of it, or the author's reasoning, worries or expected verdict. On every route the prompt is what forbids it to modify any file, write scratch files or read `.canon/`; a confirmation prompt allows only the reviewed copies its diff command reads ([Resuming and replacing](#resuming-and-replacing)).
- A reviewer of a gate or blind review reports every blocker and major finding and at most 10 minor ones, each with its severity and location, then its Questions, and ends with one line, `Verdict: approve` or `Verdict: revise`. A code review reviewer reports findings with severity `blocker`, `major` or `minor`.
- A confirming reviewer answers resolved or not resolved for each finding listed, citing the location that shows it, reports any new blocker the diff introduces, and ends with a Verdict line. The gate or code review records these answers as [D001§review-dispositions: review dispositions](D001-skill-telemetry.md#review-dispositions) describes.
- A worker's only input is the worker prompt, filled with the plan's path, its slice and the design sections the slice builds on, and followed, for a replacement, by the answer its predecessor was blocked on; the plan carries the rest. The prompt has it build the slice test-first, keep its scratch files in `.canon/canon-implement/<P id>/S<n>/`, edit no plan or design and not commit, and tells it that it cannot reach the user.
- A worker stops and reports `blocked` when the plan or a design cannot be followed, naming which and the fix it would propose, or when a decision is needed that the docs and code do not settle; it reports `stuck` when a failing test stays unexplained and its last two attempts produced no new evidence narrowing the cause; otherwise it reports `done`. The report gives the status, the files changed, the tests added with their seams, the test commands run and their results, deviations from the plan and open questions.
- On `done`, the session re-runs the slice's tests and checks that the diff stays within the slice and edits no plan or design.

### Reviewers

- **Same-model reviewer**: a subagent on the session's model and effort. Every gate has one, and code review has two, its Spec and Standards reviewers, each launched the same way.
- **Cross-family reviewer**: the first reviewer in the reviewer file whose model is of another family than the session's. It reviews in the first round of every L2 gate and L2 code review, optionally of an L1 gate, and of any other blind review when the user asks for another family.
- **Reviewer file**: `.canon/canon-blind-review/reviewer.md`, local to the machine. It lists, in no fixed syntax, one or more reviewers, each with its model and effort, how to run it and what the host needs to run it, such as running outside its sandbox. A reviewer runs either as a shell command with `<prompt>` and `<out>` placeholders that starts a new read-only session and leaves the final review in `<out>`, or as a host subagent with a named model. For a command, the session substitutes the cross-family reviewer's prompt and findings files for `<prompt>` and `<out>`, writes the filled prompt to the first, runs the command in the background from the repo root and reads `<out>` when it finishes.
- **Setup**: `canon-init` writes the reviewer file, as one step of setting up a project, or alone when the machine has no reviewer file or sessions start on a model family it has no reviewer of another family for. It asks which model families the user's sessions run on, each of which needs a reviewer of another family; for each reviewer, which tool runs it, an agent CLI, which works from every host, or a subagent of their host with a named model; and its model, suggesting the family's flagship, and its reasoning effort. It builds each command from the tool's `--help`, runs it once on a one-line prompt and fixes it until it works, noting what the host needed. It writes the user's preferred reviewer first, so every session of another family than that reviewer's uses it. Without another family it writes no file.
- **Manual fallback**: when the reviewer file is missing or names no reviewer of another family, or the cross-family reviewer's run fails and is not recovered as [Stopped runs](#resuming-and-replacing) describes, the session tells the user why in one line, suggesting `/canon-init` for a missing reviewer, gives the filled prompt in one code block that any tool able to read the repository can run, and waits for the pasted result. It keeps that prompt and result as the cross-family reviewer's files, without an id, and records the reviewer as `manual:<model>`.

### Resuming and replacing

- **Stopped runs**: a subagent whose run stops before it reports, because the host reports it interrupted, timed out or failed, gets one more run. It is resumed by its id, given only a request to continue where it stopped and end with the report its prompt asks for; when it cannot be resumed, a new one given the same prompt replaces it and starts the work over. A cross-family reviewer that runs as a command cannot be resumed, so a failed command runs once more. When that run stops or fails too, the session stops trying: a worker's slice pauses, with the stopped runs as its problem; a first-round cross-family review falls back to the manual route; findings the cross-family reviewer cannot confirm go to the resumed same-model reviewer, as under Confirmation; and a same-model review waits for the user.
- **Confirmation**: after accepted blocker or major findings are fixed, the reviewers that raised them confirm the fixes in one round, given only the confirmation prompt of the `canon-blind-review` skill and what this list adds to it. Before the first round, the session copies each existing file under review, meaning the target's paths or the files its diff and untracked list name, to `.canon/canon-blind-review/<topic>/reviewed/<path>`, and copies any other file the same way before a fix first edits it. The confirmation prompt's diff command is `git diff --no-index -- <copy> <path>` for each file the fixes touched, with `/dev/null` for the side missing when a fix created or deleted the file; it shows only what changed since the review whether or not anything was committed, and the prompt allows reading those copies and nothing else in `.canon/`. A reviewer that runs as a host subagent, same-model or cross-family, either code review axis included, is resumed by its id: the Task tool's `resume` in Cursor, SendMessage to the agent id in Claude Code. A cross-family reviewer that runs as a command, and a reviewer that cannot be resumed, gets a new run of the same reviewer, given the confirmation prompt followed by its first-round findings. A manual-fallback reviewer's findings, and those the cross-family reviewer could not confirm, are confirmed by the resumed same-model reviewer, given the confirmation prompt followed by those findings, named `cross-family:F<n>`; in a code review, each goes to the resumed reviewer of its axis. There is no further round.
- **Workers**: a worker blocked on a question that the session settles with the `canon-grill` triage is resumed with the answer, and one blocked on a plan problem with one clear fix is resumed after the session edits and logs the plan. A worker that cannot be resumed is replaced by a new one, given the worker prompt followed by the answer when it was blocked on a question. Before a new worker replaces one, the session stashes the slice's changes, new files included, under a message naming the slice and the replacement and logs the stash, so the new worker starts from the slice's start, in the trace unit that [D001§call-sites: call sites](D001-skill-telemetry.md#call-sites) gives it. A question only the user can answer, a plan problem without such a fix, any design problem and a `stuck` report pause the slice; a stuck worker is not retried. A paused slice keeps its changes, new files included, in a stash named after it and its problem in the plan's Log, for whoever resumes it.

## Known issues

| ID | Severity | Issue | Source | Since | Next |
|----|----------|-------|--------|-------|------|
| D003-K3 | minor | No way to resume a subagent is named for Codex | as-built e08f898 | 2026-10-22 | L1 |
| D003-K4 | minor | Nothing says where the session finds the session id a command reviewer reports, which D001's token analysis reads | as-built e08f898 | 2026-10-22 | L1 |

## Decisions

- Subagents are new, never forks of the session: a fork carries the conversation, which would unblind a reviewer and fill a worker's context window (`canon-blind-review`'s definition of a blind reviewer; e71dae1).
- Subagents run on the session's model and effort, which the user sets: in Cursor a Task subagent runs on the session's model unless the user asks for another, from a fixed list whose names fix the effort, so workers and same-model reviewers need no setup (README, Host verification). It replaced per-role effort tables and the Reviewers and Workers lines (3c560ed).
- A confirmation resumes a reviewer that runs as a host subagent, so it judges the fixes against its own findings (3c94281), and reruns a cross-family reviewer that runs as a command with its first-round findings, which needs no per-tool session handling (6ac41ad). Findings whose reviewer cannot confirm them, a manual-fallback reviewer's included, go to the resumed same-model reviewer, so the user relays nothing a second time (`canon-blind-review`).
- A confirmation diffs each file the fixes touched against a copy taken before the review, or before a fix first edited it: work not yet committed has no commit to diff from, and a `git diff` from HEAD mixes the change under review with its fixes. The gates of D001, P001, P002 and D000 each needed an ad-hoc copy or a full reread instead (2026-10-15 to 2026-10-23).
- Reviewers write no scratch files, and workers keep theirs in `.canon/canon-implement/`: a gate reviewer and a code reviewer each left one in the tree under review, and a worker given no place wrote its benchmarks to `/tmp`, where every write waited for the user's approval (2026-10-23).
- The reviewer file is local, since the tools and logins its reviewers rely on differ between machines (6ac41ad; `workflow.md`, Subagents).
- A stuck worker's slice pauses for the user instead of being retried: a94fe18 made workers inherit the session's effort, which left no higher effort to retry at.
- A subagent whose run stopped gets one more run, resumed when it can be: a new one starts the work over, as a replaced reviewer did in D002's gate before the user asked for resuming, while the resumed one finished that review (2026-10-22). A second stop ends the attempts, since a stop that repeats, such as a hanging test or a full context, would otherwise loop.
- A replacement worker starts from the slice's start, its predecessor's changes stashed: a half-built tree would give the new worker a wrong baseline for the tests it must keep green.
