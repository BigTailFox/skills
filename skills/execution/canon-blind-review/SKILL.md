---
name: canon-blind-review
description: Runs blind reviews with fresh reviewers. Use for the canon review gate, the cross-family pass of an L2 code review, or when the user asks for a blind, independent or second-opinion review. Reviewers see only a self-contained prompt about files in the repository; a same-model reviewer runs as a host subagent, a cross-family reviewer as the machine's reviewer file says, and both confirm the fixes and review a gate's later revisions in follow-up rounds.
---

# Blind review

A reviewer is **blind** when its only input is the prompt. It never sees the conversation, a summary of it, the author's reasoning, worries or expected verdict. The prompt names files in the repository and the reviewer reads them itself. Reviewers never modify files or write scratch files.

## Prompt

Every first-round prompt is this template. The caller fills `{artifact}`, the Target lines, the reading line, a whole sentence in place of `{reading line}`, and the Assess items, and passes nothing else, never context about why the review was requested:

- **Review gate**: `a design` or `a plan`, and the lines in the `canon` skill's workflow (Reviewer prompt).
- **Code review**: as the `canon-code-review` skill says, with its briefs.
- **Any other review**: `Target: {paths, or the diff command}`, the reading line `Read the target and whatever it links to or depends on.`, and criteria that fit the artifact, such as correctness against the code it describes; completeness, so a newcomer could act on it alone; consistency with the designs it touches; simplicity, nothing beyond its goals.

`{documentation language}` is the language the project's docs are written in. The finding heading's `{location, ...}` stays as it is, for the reviewer. Keep the first line, without its braces, only when you work in a linked worktree.

```text
{Work in `{worktree root}`, a linked worktree of this repository: run every command from that directory and read every path relative to it.}

You are reviewing {artifact} in this repository with no prior context. Judge it only from the repository.

{Target lines}

{reading line} Do not read `.canon/`. Do not modify any file or write scratch files; read long command output in parts instead. You may run the canon.py that `AGENTS.md` names with `show`, `find`, `which`, `affected`, or `check` without `--fix`, which only read; when the host blocks one, read the files instead.

Assess:
- {item}
- {item}
Report a problem a design lists as a known issue only when it is worse than the entry says, naming the entry.

Report every blocker and major finding and at most 10 minor ones, most severe first, each as:

### F1 [blocker | major | minor] {location, e.g. D003§token-refresh}
Problem: ...
Evidence: ...
Suggestion: ...

Keep each finding as short as it can be while a reader can understand and verify it without redoing your review.
Then list Questions: anything you could not understand from the repository alone.
Write the report in {documentation language}, even where your instructions set another reply language.
End with one line: Verdict: approve | revise
```

## Reviewers

- **Same-model reviewer**: a subagent on the session's model and effort.
- For a **cross-family review**, follow the `canon` skill's workflow (Reviewer file, Authorization for command reviewers and Reviewer setup) for the initiating family's order, additional requested reviewers, host restrictions, `none` and setup. Run a host subagent with its configured model. For every command call, including confirmation, follow-up and recovery, match the grant and enforce its input limits before launch. Write the filled prompt and substitute its prompt and findings paths for `<prompt>` and `<out>` ([Review files](#review-files)). Launch from this checkout's root with the granted view.

The review gate and code review say when the cross-family reviewer runs; other reviews run the same-model reviewer, plus the cross-family reviewer when the user asks for another family.

## Launch

- A reviewer that runs as a host subagent is a new subagent from the host's own tool, never a fork of the session, launched without a model or effort so it runs on the session's; only a cross-family reviewer gets a model, the one its entry names. In Claude Code use a `general-purpose` or custom subagent; the built-in Explore and Plan agents cannot be resumed.
- Launch the first-round reviewers together. Start each command reviewer once on a retained host job with its output attached as below, then launch the host reviewers asynchronously. A lone host reviewer may run in the foreground.
- While any reviewer reads, keep the work tree outside `.canon/` at its review snapshot. If a first-round report is missing once all readers stop, follow the `canon` workflow's Pending reviews to fix or confirm the reports already received and freeze the next review baseline.
- Once you have no other work, look for the report of a host subagent whose completion notice has not come in the host's record of its run: in Cursor, `subagents/<agent id>.jsonl` in `<cursor home>/projects/<project>/agent-transcripts/$CURSOR_CONVERSATION_ID/`; in Codex, the `rollout-*.jsonl` under `$CODEX_HOME/sessions/` whose `session_meta` names your session as `parent_thread_id`.
- On every route the prompt is what keeps reviewers from modifying files, writing scratch files and reading `.canon/`.

### External review progress

Use the host's ordinary permission mechanism. Put the destination, inputs and matching grant's source and scope in the actual request metadata. Give one notice before submitting the request only when the host cannot show that context there. Treat process start as confirmed only once the launcher observes it.

In Codex App attach the launcher's flushed stdout and stderr to its native command item. An integrated terminal works when it attaches to the same job. Use the equivalent command view on other hosts. Send observed process start, first and later reviewer activity, elapsed time, optional idle heartbeats and exit status directly to that view. Return only completion or actionable failure and the report location to the agent. Wait for completion on the original job or its wait handle. Continue an ordinary nonterminal yield on that handle.

For buffered output or an unattached job, give one notice that live output is unavailable and wait quietly on its handle. On either route, use the declared read-only status operation only for a requested update, interruption or recovery decision. Chat carries required decisions, failure and the final outcome. Give routine progress in chat only at the user's request.

At launch, bind the absolute checkout, round, report path, provider, model and job handle under the round's `attempts/<report stem>/<attempt>/`. Use a recoverable launcher only when it demonstrated that it persists the provider session ID with that binding at the opening event, even while the caller waits. Describe only the ID or activity a route can observe. Keep the prompt, read-only scope, partial output, last tool or model activity and recovery count with the binding across caller deadlines, outside the reviewer's input and the round's directly archived files. Only fresh tool or model activity counts toward [deadline recovery](#stopped-runs).

## Review files

Keep each reviewer's files in `.canon/canon-blind-review/<topic>/`. A gate's topic is its target's id and the revision it reviews, `<id>-r<N>` such as `D007-r4`, a gate with follow-on targets too, so a later gate never overwrites it; a code review's is the one the `canon-code-review` skill names; any other review's is a slug of what it reviews. Each [follow-up round](#follow-up-round) of a gate keeps its files, named the same way, in `<topic>/followup-<k>/`, numbered from 1.

Give each independently numbered report a key. Start with the role (`same-model`, `cross-family`, or the caller's axis) and number further reports in that role from 2, e.g. `cross-family-2`. Before launch write `<key>-prompt.md`. Only a complete terminal report from this run goes in `<key>.md`. Write the ID of the run whose report you merged to `<key>-id.txt`. Leave it empty when the merged run has no ID, including after a fallback.

For a source with one confirmer, save its prompt, report and fresh run ID under `<key>-confirm-prompt.md`, `<key>-confirm.md` and `<key>-confirm-id.txt`. If one source goes to multiple confirmers, use a separate stem for each pair, e.g. `cross-family-confirm-spec` and `cross-family-confirm-standards`. Each gets its own `<stem>-prompt.md`, `<stem>.md`, `<stem>-id.txt` and `<stem>-snapshot.txt`. Preserve the original report and ID.

Save a host subagent's terminal report verbatim and merge it in its original language. Once that report is saved and newer than its prompt, ignore repeated or late completion notices for that run.

Before the first launch in each round, run `canon.py snapshot` from the checkout root and keep its output in the round's `snapshot.txt`. Preserve it through a handoff. Save the input snapshot for each report in `<key>-snapshot.txt`. Take a fresh snapshot for a late or supplemental pass. For a single confirmer save the fixed snapshot in `<key>-snapshot-confirm.txt`. Keep the round's latest fixed snapshot in `snapshot-confirm.txt`. Check a snapshot with `git -C .canon/canon/snapshots cat-file -e <commit>`. When tracing supplies an ID, keep it with the round's evidence as the `canon` skill's `trace.md` directs.

## Stopped runs

User cancellation ends the run. For a command, distinguish a caller timeout from a stopped attempt using the job handle and the [saved binding](#external-review-progress). Allow at most two deadline recoveries per attempt, or the route's lower limit, counting any the launcher already performed.

1. Check the original job after an interruption or wait timeout. If it is still running, continue waiting on its handle. If the provider already completed the report and the launcher was interrupted before publication, finish publishing that result with the matching binding.
2. When a deadline actually terminated the run, check for fresh tool or model activity since its last launch or recovery. With that activity, a matching binding, a grant covering recovery and a recovery left, resume the same provider session with the original prompt, read-only scope and output. If recovery lacks a matching grant, return to the `canon` skill's workflow (Authorization for command reviewers) before any further provider call.
3. After recovery is exhausted or unavailable, an exit without a complete terminal report spends one stopped attempt. This includes a terminated run with no new activity and a terminal provider failure. Move any partial `<out>` into the stopped attempt's directory.

On the first stopped attempt, give the reviewer one more attempt. This also applies to a host reviewer whose run record shows it stopped without a report. Resume it by its ID when possible, asking only that it continue where it stopped and finish the requested report. For a terminally failed or non-resumable run, launch the same reviewer fresh with the same prompt. On the second stop, proceed by role.

- For a **first-round cross-family reviewer**, follow the `canon` workflow's Reviewer file to select an unused eligible replacement for these targets and round. Record the outstanding pass and use the [manual fallback](#manual-fallback) when none is available or the user required that specific reviewer. Credit each completed pass once.
- **Cross-family reviewer in a confirmation or follow-up round**: its part goes to the resumed same-model reviewer, as [Confirmation](#confirmation) and [Follow-up round](#follow-up-round) say.
- **Same-model reviewer**, a code review's axis reviewers included: the review waits for the user.

## Manual fallback

When an applicable `none` is configured, setup cannot write the reviewer file, or the first-round routes are exhausted, tell the user why. The `canon-init` skill's reviewer setup can change a configured `none`. Give the user the full prompt for the current targets in one code block to run in an independent tool that can read the repository. For a gate, follow the `canon` workflow's Pending reviews, including `pending.md`, L1 withdrawal and an explicit L2 decision for named revisions. An L2 code review waits for the report. When the report arrives, verify which snapshot and targets it covered, save it and its prompt under the assigned key, leave its ID file empty and credit `manual:<model>`.

## Merge

Accept and fix each finding, decline it with a one-line reason for the user, or escalate it to the user. A finding raised by two reviewers is accepted unless it is clearly wrong. The review gate adds its own merge rules (the `canon` skill's workflow, Review gate).

## Confirmation

After the author fixes accepted blocker or major findings, the reviewers that raised them confirm the fixes in one round. Send only this prompt, started with the template's worktree line when the first round's prompt has one and with `{documentation language}` filled as in the template, never the author's reasoning:

```text
The author revised the target after your review. Confirm these findings:
{For each finding assigned to this reviewer, quote its original ID and text, give the fix location and, if only part was accepted, state the accepted claim.}
{Diff since your review: {diff command}, which reads the review snapshots in `.canon/`. | No diff is available; read each fix at its location.} Read nothing else in `.canon/`.
For each listed finding, judge the accepted claim and answer resolved or not resolved, citing the location that shows it. Then report any new blocker the fixes introduce. Do not modify any file or write scratch files; read long command output in parts instead.
Write the answer in {documentation language}, even where your instructions set another reply language.
End with one line: Verdict: approve | revise
```

- Take the fixed snapshot ([Review files](#review-files)). Run `git -C .canon/canon/snapshots diff <input> <fixed> -- <paths>` using that source's input and confirmation snapshots and the paths its fixes touched. For a legacy first-round report use the shared round snapshots it actually saw. When either commit is unavailable or the command fails, send the no-diff choice.
- Resume each reviewer by its kept id, so it judges the fixes against its own findings.
- A cross-family reviewer that runs as a command, and a reviewer that cannot be resumed, gets a new run of the same reviewer with the same scoped prompt. Keep the full report in the round's findings file.
- For a manual-fallback reviewer, or a cross-family reviewer whose confirmation run stops twice, assign its findings selected for confirmation to the resumed same-model reviewer. Use the same prompt and the actual source key, e.g. `cross-family-2:F<n>`. In a code review, each goes to the resumed reviewer of its axis. Save each delegate's evidence as in [Review files](#review-files) and record its actual reviewer key in the dispositions.
- Blockers still open after this round go to the user.

### Targeted recheck

On a separate request, snapshot the version to check. Use the confirmation prompt for only the named source finding and accepted claim. Name its fix and diff from that reviewer's last checked snapshot, or give the locations when a diff is unavailable. Resume the reviewer when possible. A command or unavailable session gets a fresh run of the same reviewer. Identify any delegate as in Confirmation. Save the prompt, terminal report, actual run ID and checked snapshot in `<stem>-prompt.md`, `<stem>.md`, `<stem>-id.txt` and `<stem>-snapshot.txt` under a new stem. Preserve the first confirmation. Use the saved review ID and the `canon` skill's review evidence instructions to record the recheck on receipt for a closed unit, or immediately after its end if the request came earlier.

## Follow-up round

A gate's follow-up round, which the `canon` skill's workflow says when to run, sends a later revision of its targets to the gate's reviewers. Each reviews what changed since the last snapshot of the gate or its previous round, at the gate's tier and with its first-round criteria, and reports as in a first round.

- Once the new revisions are made, write the round's `snapshot.txt` in `<topic>/followup-<k>/` ([Review files](#review-files)). The diff command is `git -C .canon/canon/snapshots diff <last> <new> -- <paths>`: `<last>` the commit in the round before's `snapshot-confirm.txt`, else in its `snapshot.txt`, that round being the gate's in `<topic>/` for round 1 and `followup-<k-1>/` after it; `<new>` the commit in this round's `snapshot.txt`; `<paths>` the revised targets. Run it yourself first; when a snapshot is missing or the command fails, send the no-diff choice, naming the revised sections.
- Send only this prompt, filled as the confirmation prompt is:

```text
After your last review, the author revised {paths}. Review what changed, at the same tier and with the same criteria and rules as your first-round prompt, reading the rest of the repository for context as that prompt allows. {Diff since your last review: {diff command}, which reads the review snapshots in `.canon/`. | No diff is available; read the revised sections: {sections}.} Read nothing else in `.canon/`.
Do not modify any file or write scratch files; read long command output in parts instead.
Report as your first-round prompt asks, numbering findings from F1, with Questions, in {documentation language}, even where your instructions set another reply language.
End with one line: Verdict: approve | revise
```

- Resume each reviewer that runs as a host subagent by its kept id. A cross-family reviewer that runs as a command, and a reviewer that cannot be resumed, gets a new run, given its first-round prompt followed by the follow-up prompt.
- On targets it previously reviewed in full, a manual-fallback reviewer's part, or that of a cross-family reviewer whose follow-up stops twice, goes to the resumed same-model reviewer. Credit the actual reader of the new revision. An added target needs full passes from its missing roles. After a waiver, give a fresh independent reviewer the full criteria, current targets and follow-up changes. For missing independent coverage follow the `canon` workflow's Pending reviews.
- Confirm accepted blocker and major fixes from each source's own input as in [Confirmation](#confirmation).
