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
- **Design or concept being written**: every settled decision in place. Unsettled ones go in the concept's Open questions, or in a temporary `## Open questions` section of a draft design that the author removes before the review gate.
- **Experiment or review**: results and dispositions decided so far.

Run `canon.py check --fix`. Commit only if the user asks; the handoff lists what is uncommitted.

## 2. Write the handoff

Write `HANDOFF.md` to `.canon/canon-handoff/<id>-<topic>/` at the repository root, where `<id>` is the current conversation's id (`<YYYYMMDD-HHMM>` when unknown) and `<topic>` is a slug of the work. It holds:

- **Goal**: the work and, when the user passed arguments, what the next session will focus on.
- **Position**: tier, branch, `HEAD` commit, and `git status --short`.
- **Resume from**: doc ids and sections in reading order, e.g. `P012#current-state`, then `D003#token-refresh`.
- **Not in any doc**: instructions and preferences the user gave in conversation, options the user rejected that no doc records, open hunches, environment quirks (services that must run, commands needing special flags).
- **Suggested skills**: which canon skills to use next and on what, e.g. `canon-implement` to resume P012.

Reference docs, commits and files by id or path; never copy their content. Replace secrets and personal data with `<REDACTED>`.

## 3. Report

Give the user the file path and a one-line prompt for the next agent: `Read <path> and continue.`
