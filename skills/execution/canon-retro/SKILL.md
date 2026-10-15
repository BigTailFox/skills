---
name: canon-retro
description: Turns friction a session hit in tooling, docs and the agent workflow into fixes to them. Use when the user asks for a retro, a retrospective or lessons from a session, or when a canon workflow's closing step calls for one. Not for the project's own architecture, performance or functionality, which reviews cover. Proposes only what concrete events justify and stays silent otherwise.
---

# Retro

A retro improves how work gets done in the project: checks and CI, the development environment, docs navigation, steering files, review standards and canon itself. The project's own architecture, performance, functionality, security and usability are out of scope even when the session exposed a problem in them; code review, the `canon-review` skill and the `canon-investigate` skill own those. Only the session the user talks to runs a retro; subagents leave it to that session. Read the `canon` skill first; `canon.py` means the project copy named in `AGENTS.md`.

- **End check**: a canon workflow's closing step runs it when the work hit friction in the development infrastructure or the agent workflow that could recur. It covers the work since the previous retro in this session, or since the session began. When one workflow runs inside another, such as code review inside implement, only the outer one runs it.
- **Requested retro**: the user asks for one. It covers this whole session and always reports, if only that nothing qualified.

## 1. Find events

An event is something in the covered work that cost something.

Costly:

- The user corrected a mistake of the agent's, repeated an instruction it had not followed, or found a mistake it had missed.
- Work was thrown away and redone.

Minor:

- An accepted blocker or major code-review finding, or a hook or CI run that failed after the agent considered its work done.
- An investigation found a defect. Look for what let its class through the tooling (no check, tests not run in CI, logs out of reach); the fix and any missing seam stay with the investigation.
- A command failed for an environmental reason (a service down, a missing flag or variable), or took several attempts to run at all.
- Finding one fact took five or more searches or reads.
- A worker reported stuck, or blocked on a question the docs should have answered.
- Information the agent needed was out of reach (logs, data, a service), so it guessed or asked.
- A costly command (a full suite where one test would do, thousands of lines of output) ran more than once.

Record canon's own friction in `skills.jsonl` ([Records](#records)): a skill step or `canon.py` behavior that forced work that bought nothing, contradicted another rule, or left the agent guessing. Leave the skills themselves alone; the project holds installed copies that updates overwrite.

Every event needs evidence you can point to: a message, a command and its output, or a doc entry. Drop an event you recall only as an impression. An end check uses only what is already in context. A requested retro on a compacted session may also read the durable records (the plan's Log, the investigation's Analysis, review outputs under `.canon/canon-blind-review/`) and, when the host names this session's transcript, search it with bounded matches (`rg -o '.{0,200}<words>.{0,200}' <transcript>`) instead of reading it whole.

## 2. Find candidates

An event becomes a candidate only when its cause is still present after this session's work and a change below would make it less likely to recur or cheaper to catch. Look for the cause in how the work was done, never in the product itself.

Not candidates:

- An instance a regression test now covers, a mistake the review fixed that nothing in the environment would have prevented, or a wait the process expects, such as a decision only the user can make.
- A change that is a product decision (new structure, behavior or performance targets); that is review work.
- A purely personal preference, such as the language or tone the user wants; it belongs to the user, not the project. What the project asks of every session, such as a verification step, what a handoff carries or who reviews what, is workflow and stays in scope.

Take the first kind of change that works:

1. **A deterministic check**, for a mechanical mistake (a fixed pattern, a banned API, an import shape, a file-location rule): a linter rule, a type-checker setting, a pre-commit hook or a CI job. Read the project's own check commands and CI config first. A check that exists but is unwired or broken is the finding; so is a project where no hook or CI job runs its lint, type checks and tests.
2. **A fix to the development environment**: a script, a narrower test command, test or tool configuration, a seed command, logs teed to a file the agent can read.
3. **A standard in the design that owns the topic**, for a recurring judgement call about how code is written that the Standards reviewer should enforce. The implementing session carries the most context pressure and the reviewer the least, so standards go where reviewers read them, not into `AGENTS.md`. The retro shows the gap and its evidence; the design flow settles the standard.
4. **A pointer**: a design's `summary`, a heading or `paths` entry (they feed `find` and `which`), a link between docs, or a guide under `docs/guides/`.
5. **An `AGENTS.md` line**, only for what every session needs, outside the `canon:agents` block.

Removing what misled is a change too: a line in `AGENTS.md` or a design that is stale, contradicts another, or changes nothing (the `canon` skill's writing rules).

Give each change its tier by the `canon` skill's tier rules, not by where it lands: a standard for a topic no design owns, or one spanning modules, is L2.

## 3. Pick

With no candidate and no new friction for `skills.jsonl`, the end check adds nothing to the report. Otherwise read `.canon/canon-retro/notes.md`.

Each event counts once. An event already listed under its cause, with the same session and evidence, is not new, and seeing it again in a later check is not a recurrence. A recurrence is a new event with the same cause, later in this session or in another one. List each new candidate under its cause, then act on the cause's state:

- **None yet, or `noted`**: raise it when the event is costly or a recurrence; otherwise set `noted`.
- **`raised`, `later C00X` or `declined`**: raise nothing.
- **`applied <commit>`**: inspect the recorded fix and the checkout where the new event occurred; commit ancestry alone misleads after a revert, cherry-pick, rebase or squash merge. If the fix was present, raise its failure, citing the commit. If it was absent or you cannot tell, raise nothing. Only events with the fix present count against its effectiveness.

Raise at most three, ranked by what their events cost times how likely they are to recur, and set the rest `noted`. A requested retro raises up to five, minor events included, and also lists the causes still `raised` and those with three or more events. It ends with one line on how the retro itself is doing since the first date in `notes.md`: the causes by latest state, how many items were raised and how many of those were declined, and how many applied causes have had no recurrence while their fix was present, excluding unverified cases and reporting those separately.

## 4. Report and apply

Put the items at the end of the workflow's report, before any closing command or prompt line it ends with. One line each: the event with its evidence, the change with its place and tier, and whether to apply it now. Then one line for each friction added to `skills.jsonl`. Set each raised cause to `raised`. The user answers every item in one reply:

- **Apply**, when it fits in this session. Commit docs edits that change no spec's meaning (pointers, summaries, headings, `paths`, guides, `AGENTS.md` lines) after `canon.py check --fix`; build an L0 change through its flow, code review and docs step included. Commit each change on its own and set `applied <commit>`. For an L1 or L2 change, follow **Later** below, then give the user the `/canon-design` command.
- **Later**: add it as an Idea to the module's backlog concept (`canon.py find backlog`, else `canon.py new C <module>-backlog`). Run `canon.py check --fix` until it reports no errors, then commit the concept and its index changes separately (Conventional Commits, `docs` type, `Refs: C00X`). Set `later C00X` only after the commit succeeds; otherwise keep `raised` and report the failure.
- **No**: set `declined`.

Without an answer the cause stays `raised`.

## Records

`.canon/canon-retro/` holds two local files; replace secrets with `<REDACTED>` in both. `<session>` is the conversation id, else the time of this session's first retro as `YYYYMMDD-HHMM`.

- `notes.md`: one section per cause, headed `## <cause>: <state>`, where `<cause>` is a short kebab-case slug and `<state>` is `noted`, `raised`, `declined`, `later C00X` or `applied <commit>`. Under it, one line per event, `- <date> <session>: <event> (<evidence>)`, and one line per state change, `- <date> <session>: set <state>`; a state change also updates the heading. State lines are not events. For an event assessed against an applied fix, include the fix commit and `fix=present|absent|unverified` in its evidence.
- `skills.jsonl`: one JSON object per line, appended, with keys `date`, `session`, `host`, `model`, `skill`, `skill_hash`, `canon`, `step`, `event` and `suggestion`. `skill_hash` is the skill's `skillFolderHash` in the global `npx skills` lock (`$XDG_STATE_HOME/skills/.skill-lock.json`, else `~/.agents/.skill-lock.json`), or its `computedHash` in the project's `skills-lock.json`. `canon` is the output of `canon.py --version`. Write `unknown` for anything you cannot get.
