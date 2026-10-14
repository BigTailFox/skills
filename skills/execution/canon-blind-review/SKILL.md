---
name: canon-blind-review
description: Runs blind reviews with fresh reviewers. Use for the canon review gate (A1 and A2), the cross-family pass of an L2 code review, or when the user asks for a blind, independent or second-opinion review. Reviewers see only a self-contained prompt about files in the repository, can run on another model family (host subagents, agent CLIs or a manual fallback), and confirm the fixes after a revision.
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

- **A1**: the author's model, unless the `Reviewers:` line names another.
- **A2**: the flagship model of another family; a smaller model of another family does not count.

The `Reviewers:` line and each reviewer's reasoning effort are in the `canon` skill's workflow (Models and effort). Other reviews run A1 at high effort, plus A2 when the user asks for another family.

Launch all first-round reviewers in parallel. Each is a new agent, never a fork of the current session. Keep each reviewer's agent or session id beside its prompt and output in `.canon/canon-blind-review/<topic>/` (topic: the doc id or change under review); the confirmation round resumes it.

## Launching by host

Use the host's own subagents first, a CLI below when the host cannot run the reviewer's model, and the manual fallback last. Set each reviewer's effort where the route allows; elsewhere it runs at the host's default. On every route the prompt is what forbids modifying files.

- **Cursor**: GPT models run through the codex CLI below, named by their codex model id. Other models run on the Task tool with a new subagent: A1 leaves `model` unset, which inherits the author's model, unless the `Reviewers:` line names one; any other reviewer sets `model` to the slug the line names, because the Task tool accepts a model other than the default only when the user asked for it. A slug fixes its effort; use it as named.
- **Claude Code**: the Task tool with a new `general-purpose` or custom subagent; the built-in Explore and Plan agents cannot be resumed. Subagents are Claude models, so A2 needs a CLI below or the manual fallback.
- **Codex**: a new `codex exec` process (below) for A1; A2 needs another family's CLI or the manual fallback.

## Agent CLIs

For another family, or GPT in Cursor, use the matching CLI if it is installed (`command -v`). Write the filled prompt to `.canon/canon-blind-review/<topic>/`, run in the background from the repo root with the output in the same directory, and read the final message when it finishes. `<effort>` is the reviewer's effort. A host that sandboxes shell commands, such as Cursor, must run the CLI outside its sandbox: the CLI writes the session that the confirmation resumes under the home directory. The CLI's own read-only mode still applies.

```bash
codex exec -s read-only --json -m <model> -c model_reasoning_effort=<effort> -o <out.md> - < <prompt.txt> > <events.jsonl>
claude -p --model <model> --effort <effort> --permission-mode plan --session-id <new-uuid> "$(cat <prompt.txt>)" > <out.md>
agent -p --mode=ask --model <model> --output-format json "$(cat <prompt.txt>)" > <out.json>
gemini -p "$(cat <prompt.txt>)" -m <model> --approval-mode plan -o stream-json > <events.jsonl>
```

The session id to keep: for codex the `thread_id` of the `thread.started` event in `<events.jsonl>`, for claude the UUID you passed, for agent the `session_id` in `<out.json>` (the review is its `result` field), for gemini the session id in the `init` event of `<events.jsonl>` (the review is the text of its assistant `message` events). Check `<cli> --help` when a flag is rejected. Without an installed and authenticated CLI for another family, use the manual fallback.

## Manual fallback

Give the user the filled prompt in one code block and say that any tool able to read the repository can run it. Wait for the pasted result. Record the reviewer as `manual:<model>`.

## Merge

For the review gate, follow its merge rules in the `canon` skill. Otherwise merge the findings: accept and fix, decline with a one-line reason for the user, or escalate to the user. A finding raised by two reviewers is accepted unless it is clearly wrong.

## Confirmation

After the author fixes accepted blocker or major findings, the reviewers that raised them confirm the fixes in one round. Resume each one by its kept id, so it judges the fixes against its own findings: the Task tool's `resume` in Cursor (it keeps the reviewer's model), SendMessage to the agent id in Claude Code, or the CLI's resume:

```bash
codex exec -s read-only -m <model> -o <out2.md> resume <thread_id> "$(cat <confirm.txt>)"
claude -p --permission-mode plan --resume <uuid> "$(cat <confirm.txt>)" > <out2.md>
agent -p --mode=ask --resume <session_id> --output-format json "$(cat <confirm.txt>)" > <out2.json>
gemini -r <session_id> -p "$(cat <confirm.txt>)" --approval-mode plan -o stream-json > <events2.jsonl>
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
