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
- For a **cross-family review**, select the first eligible reviewer in the initiating family's order and each additional reviewer the user requests. Follow the `canon` skill's workflow (Subagents → Reviewer file and Reviewer setup) for named and legacy orders, host restrictions, `none` and setup. Run a host subagent with its configured model. For a command, write the filled prompt, substitute its prompt and findings paths for `<prompt>` and `<out>` ([Review files](#review-files)), and launch from this checkout's root.

The review gate and code review say when the cross-family reviewer runs; other reviews run the same-model reviewer, plus the cross-family reviewer when the user asks for another family.

## Launch

- A reviewer that runs as a host subagent is a new subagent from the host's own tool, never a fork of the session, launched without a model or effort so it runs on the session's; only a cross-family reviewer gets a model, the one its entry names. In Claude Code use a `general-purpose` or custom subagent; the built-in Explore and Plan agents cannot be resumed.
- Launch the first-round reviewers together. Start command reviewers in the background first, keeping their job handles. Launch the host reviewers asynchronously so you can observe the commands. A lone host reviewer may run in the foreground.
- While any reviewer reads, keep the work tree outside `.canon/` at its review snapshot. If a first-round report is missing once all readers stop, follow the `canon` workflow's Pending reviews to fix or confirm the reports already received and freeze the next review baseline.
- Once you have no other work, look for the report of a host subagent whose completion notice has not come in the host's record of its run: in Cursor, `subagents/<agent id>.jsonl` in `<cursor home>/projects/<project>/agent-transcripts/$CURSOR_CONVERSATION_ID/`; in Codex, the `rollout-*.jsonl` under `$CODEX_HOME/sessions/` whose `session_meta` names your session as `parent_thread_id`.
- On every route the prompt is what keeps reviewers from modifying files, writing scratch files and reading `.canon/`.

### External review progress

When the host requires permission, announce the pending request in the active chat before submitting it, with the scope and applicable prior authorization from the reviewer file. Report confirmed process start, the first observed reviewer activity, meaningful changes, and exit status with elapsed time since start. During silence, update the chat about once a minute with the last observation. With buffered output, keep the original job handle and query the configured read-only status operation. For a legacy route report only what the host can observe.

At launch, record the absolute checkout, round, report path, provider, model and job handle in a state file under the round's `attempts/<report stem>/<attempt>/`. Bind the provider session ID to that output as soon as you observe it. Retain the prompt, read-only scope, last tool or model activity and recovery count across caller deadlines. Keep attempt state and partial output in that subdirectory, outside the reviewer's input and the round's directly archived files. Permission waits, status polls and launcher heartbeats are observations about the job. Only fresh tool or model activity counts toward [deadline recovery](#stopped-runs).

## Review files

Keep each reviewer's files in `.canon/canon-blind-review/<topic>/`. A gate's topic is its target's id and the revision it reviews, `<id>-r<N>` such as `D007-r4`, a gate with follow-on targets too, so a later gate never overwrites it; a code review's is the one the `canon-code-review` skill names; any other review's is a slug of what it reviews. Each [follow-up round](#follow-up-round) of a gate keeps its files, named the same way, in `<topic>/followup-<k>/`, numbered from 1.

Give each independently numbered report a key. Start with the role (`same-model`, `cross-family`, or the caller's axis) and number further reports in that role from 2, e.g. `cross-family-2`. Before launch write `<key>-prompt.md`. Only a complete terminal report from this run goes in `<key>.md`. Write the ID of the run whose report you merged to `<key>-id.txt`. Leave that file empty when the merged run has no ID, including after a fallback. A confirmation uses `<key>-confirm-prompt.md` and `<key>-confirm.md`. Write each fresh confirmation's ID to `<key>-confirm-id.txt`, preserving the original report and ID.

Save a host subagent's terminal report verbatim and merge it in its original language. Once that report is saved and newer than its prompt, ignore repeated or late completion notices for that run.

Before the first launch in each round, run `canon.py snapshot` from the checkout root and keep its output in the round's `snapshot.txt`. Preserve it through a handoff. Save the input snapshot for each report in `<key>-snapshot.txt`. Take a fresh snapshot for a late or supplemental pass. Save each confirmation's fixed snapshot in `<key>-snapshot-confirm.txt` and the round's latest fixed snapshot in `snapshot-confirm.txt`. Check a snapshot with `git -C .canon/canon/snapshots cat-file -e <commit>`. When tracing supplies an ID, keep it with the round's evidence as the `canon` skill's `trace.md` directs.

## Stopped runs

User cancellation ends the run. For a command, distinguish a caller timeout from a stopped attempt using the job handle and the [saved binding](#external-review-progress). Allow at most two deadline recoveries per attempt, or the route's lower limit, counting any the launcher already performed.

1. Check the original job after a poll times out. While it is running, keep observing it. If the provider already completed the report and the launcher was interrupted before publication, finish publishing that result with the matching binding.
2. When a deadline actually terminated the run, check for fresh tool or model activity since its last launch or recovery. With that activity, a matching binding and a recovery left, resume the same provider session with the original prompt, read-only scope and output.
3. After recovery is exhausted or unavailable, an exit without a complete terminal report spends one stopped attempt. This includes a terminated run with no new activity and a terminal provider failure. Move any partial `<out>` into the stopped attempt's directory.

On the first stopped attempt, give the reviewer one more attempt. This also applies to a host reviewer whose run record shows it stopped without a report. Resume it by its ID when possible, asking only that it continue where it stopped and finish the requested report. For a terminally failed or non-resumable run, launch the same reviewer fresh with the same prompt. On the second stop, proceed by role.

- For a **first-round cross-family reviewer**, try the next eligible reviewer in the configured order for the missing report, then the [manual fallback](#manual-fallback) after the last. Credit only reviewers whose reports you merged.
- **Cross-family reviewer in a confirmation or follow-up round**: its part goes to the resumed same-model reviewer, as [Confirmation](#confirmation) and [Follow-up round](#follow-up-round) say.
- **Same-model reviewer**, a code review's axis reviewers included: the review waits for the user.

## Manual fallback

When an applicable `none` is configured, setup cannot write the reviewer file, or the first-round routes are exhausted, tell the user why. The `canon-init` skill's reviewer setup can change a configured `none`. Give the user the full prompt for the current targets in one code block to run in an independent tool that can read the repository. For a gate, follow the `canon` workflow's Pending reviews, including `pending.md`, L1 withdrawal and an explicit L2 decision for named revisions. An L2 code review waits for the report. When the report arrives, verify which snapshot and targets it covered, save it and its prompt under the assigned key, leave its ID file empty and credit `manual:<model>`.

For a target added during fixes or in a follow-up, follow the `canon` workflow's Target coverage. Launch a fresh blind reviewer for each missing role with all the applicable first-round criteria, the missing targets and their usual `Changes since` commit. Give each such report its own next key and snapshot, including when its model already wrote another report.

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
- For a manual-fallback reviewer, or a cross-family reviewer whose confirmation run stops twice, assign its findings selected for confirmation to the resumed same-model reviewer. Use the same prompt and the actual source key, e.g. `cross-family-2:F<n>`. In a code review, each goes to the resumed reviewer of its axis. Keep the prompt, result and run ID with the source's confirmation files, and record the actual confirmer's key in the dispositions.
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
