---
status: open
created: 2026-11-10
updated: 2026-11-11
revision: 1
modules: [canon]
summary: Canon friction in a docs-only bilingual project: review gates per doc, parallel sessions, archived experiments, translations, check gaps, tool drift.
refs: [C001, D000, D001, D003, D005, R001, R002, D002, D006]
---

# R003: Canon friction in Silk's design phase

## Scope

- Commit: `f38221d107895804c8b653007f47c4455bb6fcd8` (`canon.py` version 28). Every finding still holds at this commit.
- Project: Silk, in its design phase with no code yet: concept `C001`, designs `D000` to `D003`, experiments up to `E016` and review `R001`, written in English with Simplified Chinese translations as attachments, and edited by several Cursor sessions at once in one checkout. It ran the skills of canon 24 (`59256c7`) and a project copy of `canon.py` at version 22. Its repository is private, so this review states canon's behavior and leaves Silk's content out.
- Ids in code font (`D001`) are Silk's docs; this repository's docs appear only as links.
- Evidence: 34 Cursor sessions on one machine from 2026-11-03 to 2026-11-10 with their reviewer subagents' transcripts, the 14 merged gate records in Silk's `.canon/canon-blind-review/`, and Silk's 68 commits since 2026-10-29. The work of 2026-10-29 to 2026-11-02 ran on another machine and left only its commits. A session on a machine without the skills installed is left out.
- Sources name a session by the first 8 characters of its id and a 0-based line of its transcript, e.g. e56224b2 L237. The raw event lists stay untracked in Silk's `.canon/canon-retro/all-sessions/`.
- Angles: usability, functional, architecture. Severity: the review's high-cost findings are major, the rest minor.
- Left out as fixed after canon 24: the canon block naming how to install missing skills ([R001: Codebase review of the canon module](../archived/reviews/R001-canon-module.md), F21, fixed in `116798a`).
- Tiers: no design owns the change tiers and their flow, the doc types and lifecycle, `check`, `show`, `rename` or the research and grill skills ([D000§capabilities: capabilities](../designs/D000-project-overview.md#capabilities) reads `none`). A change to an existing rule or command there needs an as-built revision of it first (backfill), after which the user decides on it as a design problem, unless it fixes a defect no caller could rely on (L0); a rule with nothing existing to record is a new topic (L2).

## Findings

| ID | Severity | Finding | Disposition |
|----|----------|---------|-------------|
| R003-F1 | major | usability: The review gate runs per doc revision, so one change across several designs takes a gate and reviewers per doc | fixed 5050e04 |
| R003-F2 | major | usability: No rule covers edits after a gate passes, so sessions rerun whole gates or commit edits no reviewer saw | fixed 564af98 |
| R003-F3 | major | usability: Without a reviewer file every L2 gate rediscovers the cross-family reviewer, and a hung reviewer stalls the session | fixed 86c7087 |
| R003-F4 | minor | usability: Reviewer reports live only in tool results and follow the user's reply language | fixed 0872d6d |
| R003-F5 | minor | functional: Reviewers read the live work tree, which the author and other sessions change during the review | fixed f9b0449 |
| R003-F6 | minor | usability: A revision that passed its gate but was not committed leaves the next gate no `Changes since` commit | fixed 5050e04 |
| R003-F7 | minor | usability: The reviewer prompt assumes code exists, and nothing allows a qualitative target before a first measurement | fixed 0b25d98 |
| R003-F8 | minor | usability: A session learns that trace is off only by calling `trace start` in each gate | declined a session learns it from the `trace start` call D001§budgets designs as the one call per skill invocation when tracing is off |
| R003-F9 | minor | usability: `snapshot` prints a commit that is not the snapshot repository's HEAD | fixed 80b9688 |
| R003-F10 | minor | usability: Gate directories have no layout for joint gates, later revisions or extra rounds | fixed f9b0449 |
| R003-F11 | minor | usability: Reviewers cannot tell whether they may run `check` or read `.canon/canon/snapshots` | fixed 0872d6d |
| R003-F12 | minor | usability: A late, repeated completion notice makes the session handle a reviewer twice | fixed 0872d6d |
| R003-F13 | major | usability: A session cannot pass a request to another running session; handoff files go unnoticed or are read stale | fixed 18b7dcf |
| R003-F14 | major | functional: Sessions sharing a checkout disturb each other: `check --fix` rewrites others' docs and staging one's own index lines takes hand-built blobs | open |
| R003-F15 | major | usability: A background researcher writes only at the end, so an interrupted one loses its work | fixed 18b7dcf |
| R003-F16 | minor | usability: Decisions grilled before any doc exists stay only in the chat | moved D009 |
| R003-F17 | major | usability: Archiving concluded experiments hides the evidence live designs rest on | moved D008 |
| R003-F18 | minor | usability: Nothing says whether a measurement added to a research experiment extends it or opens a new one | fixed 18b7dcf |
| R003-F19 | major | usability: A concept absorbed piece by piece by several designs can be neither frozen nor archived | fixed 0b25d98 |
| R003-F20 | minor | usability: Concepts have no review flow, and a review that restates a concept becomes a second spec | fixed 18b7dcf |
| R003-F21 | minor | usability: The tier of changes to C, R and E docs alone, and how a D000 without code is planned and marked, are unstated | fixed 564af98 |
| R003-F22 | minor | usability: Nothing keeps a design from stating other designs' scope, and splitting a design has no checklist | fixed 18b7dcf |
| R003-F23 | minor | usability: Design section rules get applied to concepts | fixed 18b7dcf |
| R003-F24 | minor | usability: Revision and approval bookkeeping around a gate is left to guesswork | fixed 564af98 |
| R003-F25 | minor | usability: `fixed <commit>` takes an extra commit for a fix made in docs | fixed 18b7dcf |
| R003-F26 | minor | usability: Sessions guess ids for docs not yet created and mislead the user | fixed 18b7dcf |
| R003-F27 | major | usability: Translations double every edit and still drift; canon has no translation convention | open |
| R003-F28 | minor | usability: Code shown in docs is kept twice by hand, so the project built its own `embed.py` | open |
| R003-F29 | minor | usability: The 500-line limit forces cuts in concepts, goes unenforced on reviews and is escaped by long lines | fixed 0b25d98 |
| R003-F30 | minor | usability: Diagram sources, tools and readability have no rules | fixed 18b7dcf |
| R003-F31 | minor | architecture: `canon.py` runs from a project copy that lags the installed skills, with project helpers beside it | open |
| R003-F32 | minor | usability: Permanent `check` warnings for planned paths and modules bury new ones | fixed ac86361 (planned paths and modules; the user declined setting apart the warnings new since HEAD) |
| R003-F33 | minor | functional: `check` skips links and anchors in attachment Markdown | fixed ecf822f |
| R003-F34 | minor | functional: `check` cannot validate a commit or the staged state | open |
| R003-F35 | minor | usability: `show D00X#known-issues` fails when a design has no Known issues section | fixed 8f4f34c |
| R003-F36 | minor | usability: No command changes a non-terminal status | fixed a26f057 |
| R003-F37 | minor | functional: `rename` leaves the H1 title, link texts and attachments named after the slug | open |
| R003-F38 | minor | usability: The 160-character `summary` limit shows only after the summary is written | fixed d733c74 |
| R003-F39 | minor | usability: A stale index is an error, which blocks a subagent allowed to edit only its own files | open |
| R003-F40 | minor | usability: The `canon` skill sends L1 revisions to `canon-design`, which the agent cannot invoke | fixed 18b7dcf |
| R003-F41 | minor | usability: Shell and tool pitfalls (zsh, the ignored `.canon/`, `/tmp`) reach no subagent prompt | fixed 80b9688 (the `.canon/` and `/tmp` pitfalls; the user declined the zsh rules) |
| R003-F42 | minor | usability: No rule orders concepts and designs from the whole to the parts with each term defined before use, and D000 puts its Glossary last | open |

## Details

### R003-F1: One review gate per doc revision

- Location: `canon/workflow.md`, Review gate ("Every design or plan revision passes this gate"); `canon-design/SKILL.md`, which sends a D000 glossary edit "through its own review gate at L1"; [D001§review-files: review files](../designs/D001-skill-telemetry.md#review-files) ("A gate's topic is its doc id"); `trace start gate <doc id>`.
- Problem: a change made mainly in `D002`, with follow-on edits to `D001` and `D003`, was set up as 3 gates with 6 reviewers until the user stopped it (e56224b2 L232, L237). A `D001` change that touched D000's glossary sent `D000` r5 through a gate of its own (01d9545f L5, L80). Gates were joined by hand three times (Silk `6e85abc`, `ede4da7`, `65cfacb`), so the records of `D003` r2 and r3 sit under `D002/r3/` and `D001/r4/`, and `D003`'s own merge record skips them.
- Suggestion: gate a change instead of a doc: one gate with a main target and follow-on targets, `Changes since` covering every changed doc, one tier for the whole change, and every target's `reviewed` set when it passes. A follow-on edit that only replaces a restatement with a link, or follows a rename, bumps no revision, like D000's rows. L2; D001's review files and gate units follow.

### R003-F2: Edits after a gate passes

- Location: `canon/workflow.md`, Review gate steps 4 and 5: one confirmation round, then `reviewed`.
- Problem: when the user asked for changes after a gate passed, or the confirmation round's minor findings were fixed afterwards, sessions either ran a full gate again or committed edits no reviewer read. `D000` had 9 reviewer runs in one evening, one of them an improvised post-gate round (fce15e7b L113, L148). `D001` passed 5 gates on 2026-11-10 (r3 joint, r4, r5, r6, r6a), with 49 reviewer prompt files that day. The merge records of `D000` r1, `D001` r2 and `D003` r1 each note edits made after the confirmation round that no reviewer read.
- Suggestion: before opening a gate, ask the user whether content feedback is finished. Add an incremental round: an edit after the gate passed and before the commit goes to the original reviewers with the snapshot diff, and only an edit that touches goals or the core approach reruns the gate. A non-blocking finding becomes a known issue or joins the incremental round. L2, with F1.

### R003-F3: Cross-family reviewer without a reviewer file

- Location: `canon-blind-review/SKILL.md`, Reviewers and Manual fallback; [D003§launch: launch](../designs/D003-subagents.md#launch) ("in the foreground"); [D003§reviewers: reviewers](../designs/D003-subagents.md#reviewers).
- Problem: Silk had no reviewer file until 2026-11-10. Before that, each L2 gate searched old transcripts for how Gemini had been run and asked the user again (01d9545f L4 to L17, 4714e84a L6); earlier still, the user ran Gemini in another tool and pasted its report (8ee6aa2c L0, 66923f0f L35). A Gemini host subagent that hit "region not available" never returned, and the session recovered its report from the subagent transcript only after the user typed "continue" (01d9545f L260 to L264).
- Suggestion: when the file is missing, write it from the user's first answer, as Silk did by hand. Run every reviewer in the background; [C001: Canon backlog](../concepts/C001-canon-backlog.md)'s "Waiting on a background reviewer" weighs the other way. Let the file list fallback reviewers, tried in order when one stops twice. L1 revision of D003, with D003-K6 and D003-K7.

### R003-F4: Where reviewer reports live and their language

- Location: [D003§input-and-reports: input and reports](../designs/D003-subagents.md#input-and-reports); `canon-blind-review/SKILL.md`, Reviewers: the session writes `<role>.md`.
- Problem: a host subagent's report reaches the session only as the tool result. Sessions sometimes saved a translation or a summary, and after context compaction the original could be recovered only from the subagent transcript. The user's rule to reply in Simplified Chinese reached the reviewers, so some review files are in Chinese (01d9545f L29, L275; fce15e7b L132).
- Suggestion: have the prompt ask for the report in the project's documentation language and let the reviewer write its own `<role>.md`, the one file it may write. L1 revision of D003.

### R003-F5: Reviewers read the live work tree

- Location: `canon/workflow.md`, Reviewer prompt ("Judge it only from the repository"); [D003§review-snapshots: review snapshots](../designs/D003-subagents.md#review-snapshots), which serve only the confirmation diff.
- Problem: authors held off editing while reviewers read (fce15e7b L82, 01d9545f L267). One author edited while Gemini was still reading, then counted its approve as covering those edits (e56224b2 L385). Other sessions' uncommitted edits entered gates: `D003` r1's snapshot held them, and `D002`'s reviewers read a `D001` that another session was changing (01d9545f L35).
- Suggestion: check out the first snapshot into a worktree under `.canon/` and point the prompt at it. L1 revision of D003.

### R003-F6: No `Changes since` after an uncommitted gate

- Location: `canon/workflow.md`, Reviewer prompt: `Changes since: {commit}`.
- Problem: `D001` r2 and `D002` r2 passed their gates but stayed uncommitted, so the next revision's gate had no commit to diff from and its reviewers read the whole doc again.
- Suggestion: allow a snapshot commit as `Changes since`, with the diff command that reads it from `.canon/canon/snapshots`. L1 revision of D003.

### R003-F7: Reviewer prompt in a project without code

- Location: `canon/workflow.md`, Reviewer prompt: "Correctness and feasibility against the current code", "a fresh agent could implement it"; `canon/doc-types.md`, Budgets: "numeric targets".
- Problem: with no code, each reviewer improvised what correctness meant. A budget went back and forth: reviewers flagged "no number, cannot judge" as major, the user chose 90%, then judged the number baseless and asked for a qualitative target, and the next gate's reviewer asked for the number again (fce15e7b L109, L159, L175).
- Suggestion: a Correctness variant for a project without code, against the experiments and designs the target rests on, and a Budgets rule that allows a qualitative target "set after the first measurement". The prompt is an L1 revision of D003; the Budgets rule is L2.

### R003-F8: Trace state found by trial

- Location: `canon/SKILL.md`, Tool: "Unless a skill's first `start` prints `trace <id>`, skip its other trace calls"; the Tool table has no `trace` row.
- Problem: every gate began with a `trace start` call only to learn that tracing was off (01d9545f L255).
- Suggestion: add `trace` to the Tool table and say that tracing is on when `~/.config/canon/trace` exists and `.canon/canon/trace/off` does not ([D001§switch-and-storage: switch and storage](../designs/D001-skill-telemetry.md#switch-and-storage)). L0.

### R003-F9: Snapshot commit and HEAD

- Location: [D003§review-snapshots: review snapshots](../designs/D003-subagents.md#review-snapshots): `refs/snapshots/<id>` per snapshot.
- Problem: the commit `snapshot` prints is not the HEAD of `.canon/canon/snapshots`, and sessions took the difference for a failed snapshot.
- Suggestion: say in `canon-blind-review` that each snapshot is a ref, checked with `git -C .canon/canon/snapshots cat-file -e <commit>`. L0.

### R003-F10: Gate directory layout

- Location: [D001§review-files: review files](../designs/D001-skill-telemetry.md#review-files); `canon-blind-review/SKILL.md`, Reviewers.
- Problem: each session invented a layout for later revisions, joint gates and extra rounds: `r6a`, `post-gate`, `C001-r25`. [R002: Open items from local retro and review records](../archived/reviews/R002-local-records.md), F3, covers a revision's gate overwriting the previous one; joint gates (F1) and incremental rounds (F2) have no place either.
- Suggestion: settle the layout with R002-F3: `<topic>/r<N>/` per revision, a joint gate under its main target, one subdirectory per extra round. L1 revision of D001.

### R003-F11: What reviewers may run and read

- Location: `canon/workflow.md`, Reviewer prompt: "Do not read `.canon/`. Do not modify any file"; `canon-blind-review/SKILL.md`, Confirmation, whose diff reads `.canon/canon/snapshots`.
- Problem: reviewers weighed whether `canon.py check` counts as modifying files and whether reading the snapshots breaks the `.canon/` ban, and answered differently. R002-F12 records Cursor blocking a reviewer's `canon.py` calls.
- Suggestion: name in both prompts the read-only commands a reviewer may run (`show`, `find`, `which`, `check` without `--fix`) and the `.canon/` paths it may read. L1 revision of D003.

### R003-F12: Late, repeated completion notices

- Problem: the host delivered a reviewer's completion notice again, late, after the session had merged that report, and the session checked the reviewer a second time.
- Suggestion: before acting on a notice, look at the reviewer's files: an existing `<role>.md` or `<role>-confirm.md` means it was handled. L1 revision of D003, with C001's "Waiting on a background reviewer".

### R003-F13: Requests between running sessions

- Location: `canon-handoff`, which hands work to the next fresh session only; `canon/workflow.md`, Design problems step 5.
- Problem: sessions passed requests through `.canon/canon/d00X-handoff/` files that the receiving session never noticed; the user relayed them at least 5 times (030ef32a L0, 4714e84a L87, three times in 01d9545f). `D002`'s reviewers started, then another session rewrote `from-d001.md`, so the gate judged a stale request. The user's decision that the session writing `D003` r4 would absorb `E014` (9dcef57a L66) was written nowhere; that session asked again and the work was deferred.
- Suggestion: say that a request for another design is a row in its Known issues (Source `D001 r4 gate`, Next `L1`), which `which`, `affected` and `audit` count and sessions read before working (L0). Add a reminder of the rows added since a design's last revision, in `check` or an `inbox ID` command (L2); for a running session, a Cursor hook can print them with each prompt.

### R003-F14: Sessions sharing one checkout

- Location: `check --fix` and `index` act on every doc; `new` counts untracked files.
- Problem: `check --fix` set `updated`, `refs` and index lines on other sessions' docs, so sessions skipped `--fix` or restored others' files by hand (01d9545f L98, L177; 4ad3a665 L449). Staging only one's own index lines took a hand-built blob at each commit (4ad3a665 L300, L462). One session reverted with `git checkout HEAD -- docs/concepts/` in the shared checkout (5af8e831 L30); another committed others' work with `git add -A docs` (b19051bf L261). The `D002` session edited `D001` during `D001`'s gate and overwrote its edits, the only blocker of `D002` r2 (4714e84a L82, L131). Other sessions' drafts made `check` fail (01d9545f L114), `new` skipped ids held by others' untracked files, and `C001` went from revision 22 to 24. Silk then added rules to leave others' changes alone and stage by path (Silk `1cdbbe4`).
- Suggestion: tell sessions that work in parallel to take a worktree and branch each; `check --base` and `renumber` already settle id collisions (L0). Add `check --fix <ID>...` with `--dry-run` (backfill), and `index --only <ID>...` (L1 revision of D005).

### R003-F15: Interrupted background researcher

- Location: `canon-research`, Launch: the brief has the subagent record its findings in the experiment, in no set order.
- Problem: two background researchers were interrupted before writing anything (030ef32a L69). Resuming one from another session failed with "not found" (L74), and the rerun redid all of its research (L78).
- Suggestion: have the brief write each finding and its source into the experiment as it goes, and keep the brief and the agent id in `.canon/canon-research/<E id>/`. L0.

### R003-F16: Decisions grilled before a doc exists

- Location: `canon-grill`, Record: answers go into the doc being written, or the commit message.
- Problem: in a "discuss first, no work yet" session, the decisions on `D001` stayed in chat. Three days later the writing session exported its own transcript and reread it, one reply alone about 75K characters (da8ce426 L113), and reviews that needed the user's earlier choices searched other sessions.
- Suggestion: when grilling toward a design that does not exist yet, create its draft (`new D`) at the first settled answer and record every answer there. L0.

### R003-F17: Archived experiments hide live evidence

- Location: `canon/doc-types.md`, Experiments: "Absorb the conclusion ... then archive as `concluded`"; `canon/workflow.md`, Docs step 5; the canon block: "Skip `docs/archived/`"; `find` without `--archived`.
- Problem: `D003` links 6 archived experiments and `C001` 8. `find` with the words of `D003`'s core mechanism misses `E003`, its evidence. The user asked why `E002` was archived (b19051bf L0), and twice asked for absorbed experiments to be archived, following the rule. Sessions were unsure when to archive, so `E011` to `E016` stayed `running`.
- Suggestion: keep `concluded` experiments in `experiments/` as a live status, and archive one only when a later experiment overturns or replaces it, under a terminal status `superseded` with its successor in `refs`. L2.

### R003-F18: A research experiment later measured

- Location: `canon/doc-types.md`, Experiments: a run or research.
- Problem: `E016` was researched, then measured, and its doc was redone once because nothing said whether the measurement joins it or opens another experiment.
- Suggestion: a run that answers the same question extends the experiment's Setup and Results; a new question opens a new experiment. L0.

### R003-F19: A concept absorbed by several designs

- Location: `canon/doc-types.md`, Concepts: archived as `adopted` or `dropped`.
- Problem: `C001` was absorbed over weeks by several designs. After `R001-F12` proposed freezing it, it went from r25 to r35, and `D000`'s revisions still had to be mirrored into `C001` and its two translations. It gathered 26 revisions, none gated, down to step-level detail: a de facto spec (4d64b7b6 L12).
- Suggestion: archive a concept as `adopted` once the first designs that absorb it pass their gates, moving its open ideas into a backlog concept, as this repository's C001 holds them (L0). Marking single ideas "absorbed by D00X§slug" and freezing them is the alternative; it needs a new rule (L2).

### R003-F20: Concept reviews and reviews as specs

- Location: `canon/doc-types.md`, Reviews: R docs cover code, modules or the whole repo; design and plan reviews happen in the gate.
- Problem: canon has no flow for reviewing a concept, so each review was improvised. `R001`'s Recommended protocol restated `C001`, so every `C001` revision had to be mirrored into it (3cf3d5ba L260); it reached 12 revisions and 592 lines and is still `open`. Experiments that restated `C001`'s approach went stale the same way.
- Suggestion: a concept review uses the `canon-blind-review` template and produces one R doc per run, recording findings against one fixed revision and linking the design that owns each spec instead of restating it. L0.

### R003-F21: Tiers for docs-only work

- Location: `canon/SKILL.md`, Workflow; `canon/doc-types.md`, Project overview: "In a project without code, it is the project's first L2 design".
- Problem: sessions disagreed on whether a change to concept, review or experiment docs alone is L0 or L1; 266cfe42 said L1, then L0. The user asked twice whether the outline `D000` needs L2, a plan or an implementation (fce15e7b L122, 85b63c79 L0).
- Suggestion: state that changes to C, R and E docs alone take no tier. For a project without code, state which D000 changes are L2, that D000 needs no plan, and what `active` and `implemented` mean before code exists. L2, with F1 and F2.

### R003-F22: Design scope and splits

- Location: `canon/writing.md`: "Say each thing once, in the doc that owns it"; `canon/workflow.md`, Reviewer prompt, Consistency; `canon/doc-types.md`, Split.
- Problem: `D001` r1 had a Scope section listing what other designs own, and two gate rounds passed it; the user explained the rule again (01d9545f L156). After `D002` split off from `D001`, `D001` kept contract rules in other words until the user asked (da8ce426 L455). Silk added the rule to its `AGENTS.md` (Silk `b5c6a4f`) and its review checklist (Silk `e4e7246`).
- Suggestion: say in `writing.md` that a design states what it owns, not what it leaves out unless that is easily misread, nor what other designs own, and add this to the prompt's Consistency (L1 revision of D003). Give Split a checklist: move the spec, `owns`, `paths` and known issues, and replace every restatement left behind with a link (L0).

### R003-F23: Design rules applied to concepts

- Location: `canon/doc-types.md`, Concepts: "Sections: Motivation, Ideas, Open questions"; "Other sections may be added freely".
- Problem: asked whether a concept's Goals and Requirements overlap, the session merged Goals into Requirements "in canon terms", and the user restored them (b19051bf L32, L39).
- Suggestion: say that a concept arranges its sections freely and that design rules, such as measurable Goals, do not bind it. L0.

### R003-F24: Revision and approval bookkeeping

- Location: `canon/workflow.md`, Review gate; `canon/SKILL.md`, Frontmatter.
- Problem: sessions guessed whether an edit before the gate joins the pending revision, whether an edit after the gate resets `reviewed`, whether "please continue" counts as L2 approval (85b63c79 L68), and whether `reviewers` accumulates across revisions.
- Suggestion: one sentence on each in `workflow.md`. L2, with F1 and F2.

### R003-F25: `fixed <commit>` for fixes in docs

- Location: `canon/doc-types.md`, Reviews: disposition `fixed <commit>`.
- Problem: a finding fixed in a doc gets its hash only after the fix is committed, so each review round took an extra commit.
- Suggestion: allow `fixed <ID>@r<N>`, such as `fixed C001@r22`, for a fix in a doc. L0.

### R003-F26: Ids for docs not yet created

- Problem: a session called a design that did not exist yet by a guessed id, and the user took it for an existing doc (da8ce426 L48).
- Suggestion: say in `writing.md` to name a doc not yet created by its topic; `new` assigns the id. L0.

### R003-F27: Translations

- Location: `canon/writing.md`: "Write docs in the project's documentation language"; attachments go unchecked (F33).
- Problem: 43 of Silk's 68 commits touch `.zh.md` files, and sessions edit both languages about equally (173 English edits to 152 Chinese in da8ce426). Drift happened anyway: `D001`'s translation fell behind another session's edit; `R001-F51` is a translation that changed the meaning; code identifiers were translated until the user objected (b19051bf L157); Chinese code comments were lost when code moved into embedded files. Each session wrote its own parity script.
- Suggestion: define a translation as `<ID>/<slug>.<lang>.md` with `translation-of: r<N>`, have `check` warn once the source's revision passes it, keep code identifiers untranslated, and sync translations at milestones such as a design's acceptance, as `R001-F12` proposed. L2.

### R003-F28: Code kept twice

- Problem: canon cannot include a file in a doc, so Silk wrote `scripts/embed.py` and an `AGENTS.md` rule to copy attachment code into docs (e56224b2 L169, L173). A session later edited a generated block by hand.
- Suggestion: a `canon.py embed` that `check` verifies, with generated blocks left out of the line count. L2.

### R003-F29: The 500-line limit

- Location: `canon.py`, `MAX_DOC_LINES`: a warning on every doc type, with the split hint only for designs; `canon/doc-types.md`, Split covers designs only.
- Problem: `C001` reached 503 to 516 lines several times, and sessions cut API examples they had just added, in both languages, or packed lists into paragraphs (66923f0f L162 to L170, L292). `R001` sits at 592 lines with no action, and long lines pass the limit.
- Suggestion: state whether the limit binds C, R and E docs and how each splits: a concept into several concepts, a review into one doc per run, reports into attachments. L0.

### R003-F30: Diagrams

- Problem: three sessions found the dependencies of Silk's `make_diagrams.py` in three different places. Its SVGs turn text into outlines, which reviewers cannot read, and the diagrams fell behind the text.
- Suggestion: say in `writing.md` that a diagram keeps its source beside it as an attachment (Mermaid, or the script with its dependencies), keeps its text as text, and changes in the commit that changes what it shows. L0.

### R003-F31: Project copy of `canon.py`

- Location: `canon/SKILL.md`, Tool: the project's copy at the path `AGENTS.md` names; `init` keeps the copy.
- Problem: Silk's `scripts/canon.py` has stayed at version 22 since Silk `be83c5e`, while the installed skills, written for version 24, describe what it lacks. Silk's `embed.py` sits beside it in `scripts/`. D004-K1 tracks the missing version check.
- Suggestion: run `canon.py` from the skill directory, with `AGENTS.md` naming only a minimum version and the tool printing a notice on a mismatch; helpers canon takes over become subcommands. L2 revision of D004.

### R003-F32: Permanent warnings

- Problem: every `check` in Silk printed the same 11 warnings: 10 for code paths and module directories that do not exist yet, 1 for `R001`'s length. Sessions explained them each time or filtered them out with `rg -v`.
- Suggestion: let D000's module rows and a design's `paths` be marked planned (L1 revision of D002), and have `check` set apart the warnings new since HEAD (backfill).

### R003-F33: Links in attachments

- Location: `canon.py`, `Repo._scan` and `run_check`: `check_links` runs on numbered docs, `AGENTS.md`, guides and assets, not on attachment Markdown.
- Problem: translations and reports are attachments, so their links and anchors go unchecked; at least 4 sessions wrote their own checkers.
- Suggestion: run `check_links` on `.md` attachments. Backfill.

### R003-F34: Checking a commit or the staged state

- Problem: to verify the docs of a commit or of the staged state, sessions built temporary worktrees or used `git archive` (e56224b2 L222).
- Suggestion: `check --rev <commit>` and `check --staged`. Backfill.

### R003-F35: `show` on a missing Known issues section

- Location: `canon.py`, `cmd_show`: `canon: <id> has no section #<slug>`, exit 1.
- Problem: the `canon` skill says to read `show D00X#known-issues` before working from a design, and the call fails for every design without known issues.
- Suggestion: print that the design has no known issues and exit 0. L0.

### R003-F36: No status command

- Problem: `archive` sets terminal statuses only; `draft`, `accepted` and `active` are hand edits that sessions get wrong.
- Suggestion: `canon.py status ID STATUS`, checking the transition and, for `accepted`, that `reviewed` equals `revision`. L2.

### R003-F37: `rename` leaves names behind

- Location: `canon.py`, `cmd_rename`: moves the file and rewrites link targets.
- Problem: the H1 title, link texts that repeat the old title, and attachments named after the slug, such as `D001/<slug>.zh.md`, keep the old name.
- Suggestion: rewrite the H1 with `--title`, and rename attachments whose names start with the old slug. Backfill.

### R003-F38: Summary limit found late

- Problem: `check` reports a `summary` over 160 characters only after it is written, which happened at least 6 times.
- Suggestion: state the limit in each template's `summary` line. L0.

### R003-F39: Stale index as an error

- Location: [D005: Docs index](../designs/D005-docs-index.md): `ERROR <path>: index out of date`.
- Problem: a subagent told to edit only its own files cannot regenerate the shared index, so its `check` fails on others' changes.
- Suggestion: report a stale index as a warning, and as an error under `check --base`. L1 revision of D005.

### R003-F40: `canon-design` cannot be invoked

- Location: `canon/SKILL.md`, Workflow, L1: "Revise the design in place with the `canon-design` skill"; `canon-design` sets `disable-model-invocation: true`.
- Problem: a session told to follow `canon-design` for an L1 revision finds no such skill in its list; one found it on disk and read it by path (fce15e7b L4).
- Suggestion: have L1 revisions follow the `canon` skill's own steps, as Design problems step 3 already does, and offer `/canon-design D00X` to the user when an interview is needed. L0.

### R003-F41: Shell and tool pitfalls

- Problem: in 6 or more sessions, subagents included, zsh expanded `echo ===` as `=cmd`, kept unquoted variables as one word and aborted commands on unmatched globs. The fix so far is a personal Cursor rule on one machine. Cursor's Grep and Glob skip the git-ignored `.canon/`, and subagents often wrote scratch files to `/tmp`.
- Suggestion: have every subagent brief (research, workers, reviewers) name its scratch directory under `.canon/` and say that `.canon/` is git-ignored, so search it with `rg --no-ignore` or read its paths directly. A project with a non-default shell states it in `AGENTS.md`. L0.

### R003-F42: Section order in concepts and designs

- Location: `canon/writing.md` and [D006§writing-rules: writing rules](../designs/D006-doc-model.md#writing-rules), which keep a topic under one heading but set no order between headings; `canon/doc-types.md`, Concepts ("adds or orders others as its ideas need") and Designs, which fix only Goals, Spec and Decisions; [D002§project-overview-d000: project overview](../designs/D002-overview-and-as-built.md#project-overview-d000) and the `new` template, which put D000's Glossary after Capabilities, Modules and Dependencies.
- Problem: nothing tells a writer to lead with the overview or to define a term before the sections that use it, so a concept or design can open with details and use names a later section defines. Its reader meets details before the frame they belong to and names before their meaning, and has to read ahead to understand what came first. Canon's own D000 order breaks the rule: in this repository's [D000: Project overview](../designs/D000-project-overview.md), Capabilities, Modules and Dependencies use "skill" and "execution skills" before the Glossary defines skill and category.
- Suggestion: add a rule to `writing.md`: order a concept's or design's sections, and the content within each, from the whole to the parts, the important to the minor and the core to the details, and put the section that defines a term or name before the first section that uses it, or link the doc that defines it. L1 revision of D006. Make Glossary D000's first Spec subsection in D002, `doc-types.md` and the template; `check` tests only that the subsections exist, so existing D000s stay valid. L1 revision of D002.

## Priorities

Canon changes, most costly friction first:

1. Gate a change, with an incremental round after the gate: F1, F2, F10, F24.
2. Keep concluded experiments live: F17.
3. A translation convention and its check: F27, F33.
4. `check --fix` and `index` limited to given docs: F14, F39.
5. Run `canon.py` from the skill directory: F31.
6. A reviewer prompt for projects without code, and planned paths: F7, F32.
7. Concepts absorbed in parts: F19.
8. Research that writes as it goes, and grill answers in a draft: F15, F16.

Silk can act without a canon change: a worktree and branch per session (F14), requests to other designs as Known issues rows (F13), translations synced only when a design is accepted (F27), `R001` closed and `C001` archived (F19, F20), and an environment section in `AGENTS.md` (F41).

## Works well

- `show ID#slug` let sessions read the 500-line `C001` and `R001` by section. `new` picked free ids under concurrency, `check --fix` filled `refs` and indexes, and `archive` moved attachments and fixed links in both languages.
- Blind review paid off: each family caught majors the other passed (01d9545f L353; e56224b2 L248 and L385), and two reviewers once raised the same major independently. Snapshots with the confirmation round almost always worked the first time.
- Silk's retro produced 4 fixes on its side: a design-scope review item, the local reviewer file, the rules for concurrent sessions and a local zsh rule.
