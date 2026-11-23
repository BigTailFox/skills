---
name: canon-handoff
description: Hands the current work to a fresh agent, saving durable state in canon docs and the rest in a short handoff file.
disable-model-invocation: true
argument-hint: "What will the next session be used for?"
---

# Handoff

Read the `canon` skill first. The canon docs are the state the next agent trusts; the handoff file only points at them and carries the rest.

## 1. Flush state into the docs

Bring every doc this session touched up to date:

- **Plan**: slice statuses; Current state with the current slice, next action and paused slices with reasons; Log entries for decisions, deviations and evidence since the last update.
- **Investigation**: Reproduction, and Analysis with every hypothesis and probe result so far.
- **Design, plan or concept with open decisions**: every settled decision in place, and the open ones where the `canon-grill` skill's Record puts them.
- **Experiment or review**: results and dispositions decided so far.

Run `canon.py check --fix` with the scope the `canon` skill's Concurrent work prescribes. Commit only if the user asks; the handoff lists what is uncommitted.

## 2. Write the handoff

Write `HANDOFF.md` to `.canon/canon-handoff/<id>-<topic>/` at the repository root, where `<id>` is the current conversation's id (`<YYYYMMDD-HHMM>` when unknown) and `<topic>` is a slug of the work. It holds:

- **Goal**: the work and, when the user passed arguments, what the next session will focus on.
- **Position**: tier, branch, `HEAD` commit and `git status --short`. In a linked worktree, include its path, target branch and verified integration status as the `canon` skill's Concurrent work says.
- **Resume from**: doc ids and sections in reading order, e.g. `P012#current-state`, then `D003#token-refresh`.
- For a pending gate, point to the round's `pending.md` with the checkout and original gate key. For a handed-off code review, point to its evidence directory, fixed base, plan revision if any, and outstanding reports. Keep the trace unit ID there when recorded. Resume at the missing work using the `canon` skill's review evidence instructions. Once the review resolves, update this handoff and its pending record.
- **Not in any doc**: instructions and preferences the user gave in conversation, options the user rejected that no doc records, open hunches, environment quirks (services that must run, commands needing special flags).
- **Suggested skills**: which canon skills to use next and on what, e.g. `canon-implement` to resume P012.

Reference docs, commits and files by id or path; never copy their content. Replace secrets and personal data with `<REDACTED>`.

End each unit you left open with `canon.py trace end <unit id> handoff`, as the `canon` skill's `trace.md` says for reviews and L0 changes.

## 3. Report

Follow the `canon` skill's workflow (Closing a workflow). The end check has no trace parent after the handoff closes the open units.

Give the user the handoff file path and a one-line prompt for the next agent, `Read <path> and continue.` In a linked worktree, report the branch, tip, target and integration status from Position and use `In <worktree path>, read <path> and continue.`
