---
name: canon-blind-review
description: Runs blind reviews with fresh reviewers. Use for the canon review gate, the cross-family pass of an L2 code review, or when the user asks for a blind, independent or second-opinion review. Reviewers see only a self-contained prompt about files in the repository; a same-model reviewer runs as a host subagent, a cross-family reviewer as the machine's reviewer file says, and both confirm the fixes and review a gate's later revisions in follow-up rounds.
---

# Blind review

A reviewer is **blind** when its only input is the prompt. It never sees the conversation, a summary of it, the author's reasoning, worries or expected verdict. The prompt names files in the repository and the reviewer reads them itself. Reviewers never modify files or write scratch files.

## Prompt

Every first-round prompt is this template. The caller fills `{artifact}`, the Target lines, the reading line and the Assess items, and passes nothing else, never context about why the review was requested:

- **Review gate**: `a design` or `a plan`, and the lines in the `canon` skill's workflow (Reviewer prompt).
- **Code review**: as the `canon-code-review` skill says, with its briefs.
- **Any other review**: `Target: {paths, or the diff command}`, the reading line `Read the target and whatever it links to or depends on.`, and criteria that fit the artifact, such as correctness against the code it describes; completeness, so a newcomer could act on it alone; consistency with the designs it touches; simplicity, nothing beyond its goals.

`{documentation language}` is the language the project's docs are written in. The finding heading's `{location, ...}` stays as it is, for the reviewer.

```text
You are reviewing {artifact} in this repository with no prior context. Judge it only from the repository.

{Target lines}

Read {what to read}. Do not read `.canon/`. Do not modify any file or write scratch files; read long command output in parts instead. You may run the canon.py that `AGENTS.md` names with `show`, `find`, `which`, `affected`, or `check` without `--fix`, which only read; when the host blocks one, read the files instead.

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
- **Cross-family reviewer**: the first reviewer the reviewer file lists for your model family that your host can run, run as the file says. The `canon` skill's workflow (Subagents) says where the file is and how to set it up, which you do before the review when it gives your family neither such a reviewer nor a `none` that covers your host. For a command, write the filled prompt to its prompt file, substitute `<prompt>` and `<out>` with the paths of its prompt and findings files ([Review files](#review-files)), run it from the repo root, read `<out>` when it finishes, and write its session id to its id file: where the entry says it is printed, else from a line of its output naming it, else leave the file empty. For a host subagent, launch it like the same-model reviewer with the named model.

The review gate and code review say when the cross-family reviewer runs; other reviews run the same-model reviewer, plus the cross-family reviewer when the user asks for another family.

## Launch

- A reviewer that runs as a host subagent is a new subagent from the host's own tool, never a fork of the session, launched without a model or effort so it runs on the session's; only a cross-family reviewer gets a model, the one its entry names. In Claude Code use a `general-purpose` or custom subagent; the built-in Explore and Plan agents cannot be resumed.
- Launch all first-round reviewers in parallel. Start a reviewer that runs as a command first, in the background; run a host subagent in the foreground unless you have other work meanwhile, such as another review.
- While reviewers read, in any round, edit nothing in the work tree outside `.canon/`, so each reads what the review snapshot records; fix findings once the reports are in.
- Once you have no other work, look for the report of a host subagent whose completion notice has not come in the host's record of its run: in Cursor, `subagents/<agent id>.jsonl` in `<cursor home>/projects/<project>/agent-transcripts/$CURSOR_CONVERSATION_ID/`; in Codex, the `rollout-*.jsonl` under `$CODEX_HOME/sessions/` whose `session_meta` names your session as `parent_thread_id`.
- On every route the prompt is what keeps reviewers from modifying files, writing scratch files and reading `.canon/`.

## Review files

Keep each reviewer's files in `.canon/canon-blind-review/<topic>/`. A gate's topic is its target's id and the revision it reviews, `<id>-r<N>` such as `D007-r4`, a joint gate's too, so a later gate never overwrites it; a code review's is the one the `canon-code-review` skill names; any other review's is a slug of what it reviews. Each [follow-up round](#follow-up-round) of a gate keeps its files, named the same way, in `<topic>/followup-<k>/`, numbered from 1.

Name each file by the reviewer's role, `same-model` or `cross-family` unless the caller names others: its prompt in `<role>-prompt.md`, written before its run starts; its findings in `<role>.md`; and the agent or session id of the run whose report you merged in `<role>-id.txt`. A confirmation adds `<role>-confirm-prompt.md` and `<role>-confirm.md`; the round's other files stay as they were.

Save a host subagent's report, from any round, verbatim in its findings file, never a translation or summary, and merge it in whatever language it came. A report is saved once its findings file is newer than its prompt file, so a completion notice for a saved report changes nothing; hosts repeat notices and deliver them late.

Before a round's reviewers start, run `canon.py snapshot` (the `canon` skill's Tool) from the repo root with its output written to `snapshot.txt` in the round's directory, replacing any earlier one; once the fixes for its confirmation are made, run it again with its output written to `snapshot-confirm.txt` beside it. The commit it prints is a ref of `.canon/canon/snapshots`, not its HEAD: check it with `git -C .canon/canon/snapshots cat-file -e <commit>`.

## Stopped runs

A reviewer whose run stops before it reports, because the host reports it interrupted, timed out or failed, or its record shows the run ended without a report, gets one more run, as does a reviewer command that exits without writing `<out>`: resume it by its id (the `canon` skill's workflow, Subagents), asking only that it continue where it stopped and end with the report its prompt asks for; when it cannot be resumed, launch a new one with the same prompt, or run the command once more. When that run stops too, stop trying:

- **First-round cross-family reviewer**: the next reviewer the reviewer file lists for your family that your host can run takes its place, with the same prompt and files, and the [manual fallback](#manual-fallback) follows the last; `reviewers` and the dispositions name the reviewer whose report you merged.
- **Cross-family reviewer in a confirmation or follow-up round**: its part goes to the resumed same-model reviewer, as [Confirmation](#confirmation) and [Follow-up round](#follow-up-round) say.
- **Same-model reviewer**, a code review's axis reviewers included: the review waits for the user.

## Manual fallback

When the reviewer file gives your family a `none` that covers your host or a setup cannot write it, or when the first-round runs of every reviewer it lists for your family that your host can run stop twice, tell the user why in one line (for `none`, the `canon-init` skill's reviewer setup, run by name, replaces it), give them the filled prompt in one code block and say that any tool able to read the repository can run it. Wait for the pasted result. Record the reviewer as `manual:<model>`, and keep its prompt and result as the `cross-family` reviewer's files, without an id.

## Merge

Accept and fix each finding, decline it with a one-line reason for the user, or escalate it to the user. A finding raised by two reviewers is accepted unless it is clearly wrong. The review gate adds its own merge rules (the `canon` skill's workflow, Review gate).

## Confirmation

After the author fixes accepted blocker or major findings, the reviewers that raised them confirm the fixes in one round. Send only this prompt, with `{documentation language}` filled as in the template, never the author's reasoning:

```text
The author revised the target after your review. Fixed findings: {F-ids, each with the location of its fix}. {Diff since your review: {diff command}, which reads the review snapshots in `.canon/`. | No diff is available; read each fix at its location.} Read nothing else in `.canon/`.
For each listed finding, answer resolved or not resolved, citing the location that shows it. Then report any new blocker the fixes introduce. Do not modify any file or write scratch files; read long command output in parts instead.
Write the answer in {documentation language}, even where your instructions set another reply language.
End with one line: Verdict: approve | revise
```

- Before sending it, write the round's `snapshot-confirm.txt` ([Review files](#review-files)). The diff command is `git -C .canon/canon/snapshots diff <first> <second> -- <paths>`: the commits in the round's `snapshot.txt` and `snapshot-confirm.txt`, and the files the fixes touched. Run it yourself first; when either file holds no commit or the command fails, send the no-diff choice.
- Resume each reviewer by its kept id, so it judges the fixes against its own findings.
- A cross-family reviewer that runs as a command, and a reviewer that cannot be resumed, gets a new run of the same reviewer instead, given the confirmation prompt followed by the findings it raised in the round.
- Findings from a manual-fallback reviewer, and those of a cross-family reviewer whose confirmation run stops twice, go to the resumed same-model reviewer, given the confirmation prompt followed by those findings, named `cross-family:F<n>`; in a code review, each goes to the resumed reviewer of its axis. The user relays nothing a second time.
- There is no further round; blockers still open go to the user.

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
- A manual-fallback reviewer's part, and that of a cross-family reviewer whose follow-up run stops twice, goes to the resumed same-model reviewer, whose review of the same diff covers it; the user relays nothing a second time.
- Fixes of the round's accepted blocker and major findings pass a [confirmation](#confirmation) from the round's own snapshot: its `snapshot.txt` to its `snapshot-confirm.txt`.
