---
name: canon-blind-review
description: Runs blind reviews with fresh reviewers. Use for the canon review gate, the cross-family pass of an L2 code review, or when the user asks for a blind, independent or second-opinion review. Reviewers see only a self-contained prompt about files in the repository; a same-model reviewer runs as a host subagent, a cross-family reviewer as the machine's reviewer file says, and both confirm the fixes after a revision.
---

# Blind review

A reviewer is **blind** when its only input is the prompt. It never sees the conversation, a summary of it, the author's reasoning, worries or expected verdict. The prompt names files in the repository and the reviewer reads them itself. Reviewers never modify files.

## Prompt

- **Design or plan in the review gate**: the reviewer prompt in the `canon` skill's workflow (Review gate). Fill its placeholders and pass nothing else.
- **Anything else**: fill this template. Pick the criteria that fit the artifact; never add context about why the review was requested.

```text
You are reviewing {artifact} in this repository with no prior context. Judge it only from the repository.

Target: {paths, or the diff command}

Read the target and whatever it links to or depends on. Do not read `.canon/`. Do not modify any file.

Assess:
- {criterion, e.g. correctness against the code it describes}
- {criterion, e.g. completeness: a newcomer could act on it alone}
- {criterion, e.g. consistency with the designs it touches}
- {criterion, e.g. simplicity: nothing beyond its goals}

Report at most 10 findings, most severe first, each as:

### F1 [blocker | major | minor] {location}
Problem: ...
Evidence: ...
Suggestion: ...

Then list Questions: anything you could not understand from the repository alone.
End with one line: Verdict: approve | revise
```

## Reviewers

- **Same-model reviewer**: a new subagent from the host's own tool, launched without a model or effort so it runs on the session's (the `canon` skill's workflow, Subagents). In Claude Code use a `general-purpose` or custom subagent; the built-in Explore and Plan agents cannot be resumed.
- **Cross-family reviewer**: the first reviewer in `.canon/canon-blind-review/reviewer.md` whose model is of another family than yours, run as the file says (the same workflow section). For a command, write the filled prompt to its prompt file, substitute `<prompt>` and `<out>` with the paths of its prompt and findings files (below), run it in the background from the repo root, and read `<out>` when it finishes. For a host subagent, launch it like the same-model reviewer with the named model.

The review gate and code review say when the cross-family reviewer runs; other reviews run the same-model reviewer, plus the cross-family reviewer when the user asks for another family.

Launch all first-round reviewers in parallel. Each is a new agent, never a fork of the current session. Keep each reviewer's files in `.canon/canon-blind-review/<topic>/` (topic: the doc id or change under review), named by its role, `same-model` or `cross-family`: its prompt in `<role>-prompt.md`, its findings in `<role>.md` and its agent or session id in `<role>-id.txt`. The confirmation round needs them. On every route the prompt is what forbids modifying files.

## Manual fallback

When the reviewer file is missing or names no reviewer of another family than yours, or when its command fails, tell the user why in one line (`/canon-init` sets up a missing reviewer), give them the filled prompt in one code block and say that any tool able to read the repository can run it. Wait for the pasted result. Record the reviewer as `manual:<model>`, and keep its prompt and result as the `cross-family` reviewer's files, without an id.

## Merge

For the review gate, follow its merge rules in the `canon` skill. Otherwise merge the findings: accept and fix, decline with a one-line reason for the user, or escalate to the user. A finding raised by two reviewers is accepted unless it is clearly wrong.

## Confirmation

After the author fixes accepted blocker or major findings, the reviewers that raised them confirm the fixes in one round. Send only this prompt, never the author's reasoning:

```text
The author revised the target after your review. Fixed findings: {F-ids, each with the location of its fix}. Diff since your review: {diff command}.
For each listed finding, answer resolved or not resolved, citing the location that shows it. Then report any new blocker the diff introduces. Do not modify any file.
End with one line: Verdict: approve | revise
```

- **Same-model reviewer**: resume it by its kept id, so it judges the fixes against its own findings: the Task tool's `resume` in Cursor, SendMessage to the agent id in Claude Code.
- **Cross-family reviewer**, and a reviewer that cannot be resumed: a new run of the same reviewer, given the confirmation prompt followed by its first-round findings.
- Findings from a manual-fallback reviewer are confirmed by the resumed same-model reviewer, so the user relays nothing a second time.
- Keep each reviewer's confirmation prompt and answer in `<role>-confirm-prompt.md` and `<role>-confirm.md`; its first-round files stay as they were.
- There is no further round; blockers still open go to the user.
