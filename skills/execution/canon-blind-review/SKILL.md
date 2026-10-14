---
name: canon-blind-review
description: Runs a blind review by launching fresh reviewers that carry nothing from the current conversation, optionally from a different model family, and passing them only a self-contained prompt about an artifact in the repository (design, plan, doc, code or anything else); after fixes, the same reviewers confirm them. Covers Cursor, Claude Code and Codex subagents, cross-family reviewers through agent CLIs, and the manual fallback. Use for the canon review gate (A1 and A2 reviewers), or when the user asks for a blind, independent or second-opinion review.
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

- **A1**: the author's model, at the reasoning effort the caller asks for (the `canon` skill's gate: default for L1, highest for L2).
- **A2**: a different model family at its highest reasoning effort.

Launch all first-round reviewers in parallel. Each is a new agent, never a fork of the current session. Keep each reviewer's agent or session id beside its prompt and output in `.canon/canon-blind-review/<topic>/` (topic: the doc id or change under review); the confirmation round resumes it.

## Launching by host

- **Cursor**: the Task tool with a new subagent, `model` set to the reviewer's slug; the prompt keeps it read-only. For A2, pick a slug of another family from the available models.
- **Claude Code**: the Task tool with a new `general-purpose` or custom subagent restricted to read-only tools; the built-in Explore and Plan agents cannot be resumed. Subagents are Claude models, so A2 needs a CLI below or the manual fallback.
- **Codex**: a new `codex exec` process (below) for A1 as well as A2.

## Cross-family CLIs

Use whichever is installed (`command -v`). Write the filled prompt to `.canon/canon-blind-review/<topic>/`, run in the background from the repo root with the output in the same directory, and read the final message when it finishes:

```bash
codex exec -s read-only --json -m <model> -c model_reasoning_effort=xhigh -o <out.md> - < <prompt.txt> > <events.jsonl>
claude -p --model <model> --permission-mode plan --session-id <new-uuid> "$(cat <prompt.txt>)" > <out.md>
agent -p --mode=ask --model <model> --output-format json "$(cat <prompt.txt>)" > <out.json>
```

The session id to keep: for codex the `thread_id` of the `thread.started` event in `<events.jsonl>`, for claude the UUID you passed, for agent the `session_id` in `<out.json>` (the review is its `result` field). Check `<cli> --help` when a flag is rejected. Without an installed and authenticated CLI for another family, use the manual fallback.

## Manual fallback

Give the user the filled prompt in one code block and say that any tool able to read the repository can run it. Wait for the pasted result. Record the reviewer as `manual:<model>`.

## Merge

For the review gate, follow its merge rules in the `canon` skill. Otherwise merge the findings: accept and fix, decline with a one-line reason for the user, or escalate to the user. A finding raised by two reviewers is accepted unless it is clearly wrong.

## Confirmation

After the author fixes accepted blocker or major findings, the reviewers that raised them confirm the fixes in one round. Resume each one by its kept id, so it judges the fixes against its own findings: the Task tool's `resume` in Cursor (it keeps the reviewer's model), SendMessage to the agent id in Claude Code, or the CLI's resume:

```bash
codex exec -s read-only -o <out2.md> resume <thread_id> "$(cat <confirm.txt>)"
claude -p --permission-mode plan --resume <uuid> "$(cat <confirm.txt>)" > <out2.md>
agent -p --mode=ask --resume <session_id> --output-format json "$(cat <confirm.txt>)" > <out2.json>
```

Send only this prompt, never the author's reasoning:

```text
The author revised the target after your review. Fixed findings: {F-ids, each with the location of its fix}. Diff since your review: {diff command}.
For each listed finding, answer resolved or not resolved, citing the location that shows it. Then report any new blocker the diff introduces. Do not modify any file.
End with one line: Verdict: approve | revise
```

- Findings from a manual-fallback reviewer are confirmed by the resumed A1, so the user relays nothing a second time.
- A reviewer that cannot be resumed (its id is lost, or it ran in another main session) is replaced by a new one of the same model, given the confirmation prompt plus its first-round findings.
- There is no further round; blockers still open go to the user.
