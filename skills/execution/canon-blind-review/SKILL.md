---
name: canon-blind-review
description: Runs a blind review by launching fresh reviewers that carry nothing from the current conversation, optionally from a different model family, and passing them only a self-contained prompt about an artifact in the repository (design, plan, doc, code or anything else). Covers Cursor, Claude Code and Codex subagents, cross-family reviewers through agent CLIs, and the manual fallback. Use for the canon review gate (A1 and A2 reviewers), or when the user asks for a blind, independent or second-opinion review.
---

# Blind review

A reviewer is **blind** when its only input is the prompt. It never sees the conversation, a summary of it, the author's reasoning, worries or expected verdict. The prompt names files in the repository and the reviewer reads them itself. Reviewers never modify files.

## Prompt

- **Design or plan in the review gate**: the reviewer prompt in the `canon` skill's workflow (Review gate). Fill its placeholders and pass nothing else.
- **Anything else**: fill this template. Pick the criteria that fit the artifact; never add context about why the review was requested.

```text
You are reviewing {artifact} in this repository with no prior context. Judge it only from the repository.

Target: {paths, or the diff command}

Read the target and whatever it links to or depends on. Do not modify any file.

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

Launch all reviewers in parallel. Each is a new agent, never a fork or resumption of the current session.

## Launching by host

- **Cursor**: the Task tool with a fresh read-only subagent (no `resume`), `model` set to the reviewer's slug. For A2, pick a slug of another family from the available models.
- **Claude Code**: the Task tool with a fresh subagent restricted to read-only tools. Subagents are Claude models, so A2 needs a CLI below or the manual fallback.
- **Codex**: a fresh `codex exec` process (below) for A1 as well as A2.

## Cross-family CLIs

Use whichever is installed (`command -v`). Write the filled prompt to a temporary file, run in the background from the repo root, and read the final message when it finishes:

```bash
codex exec -s read-only --ephemeral -m <model> -c model_reasoning_effort=xhigh -o <out.md> - < <prompt.txt>
claude -p --model <model> --permission-mode plan "$(cat <prompt.txt>)" > <out.md>
agent -p --mode=ask --model <model> --output-format text "$(cat <prompt.txt>)" > <out.md>
```

Check `<cli> --help` when a flag is rejected. Without an installed and authenticated CLI for another family, use the manual fallback.

## Manual fallback

Give the user the filled prompt in one code block and say that any tool able to read the repository can run it. Wait for the pasted result. Record the reviewer as `manual:<model>`.

## Merge

For the review gate, follow its merge rules in the `canon` skill. Otherwise merge the findings: accept and fix, decline with a one-line reason for the user, or escalate to the user. A finding raised by two reviewers is accepted unless it is clearly wrong.
