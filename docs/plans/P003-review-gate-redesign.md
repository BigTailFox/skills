---
status: in-progress
created: 2026-11-11
updated: 2026-11-11
revision: 1
modules: [canon]
summary: canon.py status, approved and follow-up trace units; blind-review rules in one skill; joint gates, follow-up rounds and approval in the skill texts.
refs: [D007, D001, D003, D005, D006]
based_on: [D007@r5, D001@r12, D003@r7, D005@r2, D006@r5]
reviewed: 1
reviewers: [claude-opus-5.5, gemini-4-argon-high]
approved: 1
---

# P003: Review gate redesign

Implements [D007: Change tiers and the review gate](../designs/D007-change-tiers.md) r5 and the revisions its r4 gate made with it: [D001: Skill telemetry with canon trace](../designs/D001-skill-telemetry.md) r12, [D003: Subagents](../designs/D003-subagents.md) r7, [D005: Docs index](../designs/D005-docs-index.md) r2 and [D006: Doc model and writing rules](../designs/D006-doc-model.md) r5. Each design's `implemented` equals its revision at 7801614, so the work is each design's Spec diff from 7801614 to 1d127eb.

## Current state

Next: the docs step from 904c18b.

## Slices

### S1: `canon.py status`

Status: done

Builds on `D006#statuses-and-archiving` (the `canon.py status` block) and `D005#regeneration`.

Changes in `skills/governance/canon/scripts/canon.py`, tested in `tests/test_canon.py`:

- A `status ID STATUS` subcommand, listed by `-h`, that moves a doc forward along its type's non-terminal statuses: design `draft`, `accepted`, `active`; plan `draft`, `accepted`, `in-progress`; experiment `planned`, `running`; concept `draft`, then a live `adopted`. A review's and an investigation's only non-terminal status is `open`. A move may skip a status.
- It checks, in this order, changing no file and exiting 1 on the first that fails: an index start marker with no end marker (`require_intact_indexes`, as `archive` does); no or several docs with ID; an archived doc (`canon: <id> is archived`); a STATUS outside the type's statuses (`canon: <status> is not a status of <id>; use one of <the type's non-terminal statuses, comma-separated>`); a terminal STATUS other than a concept's `adopted` (``canon: <status> is terminal for <id>; use `canon.py archive` ``); a STATUS not after the doc's (`canon: <id> is <status>; status moves only forward`, followed by `, to <later statuses, comma-separated>` when there are any); the move's condition (`canon: <id> needs <condition> to become <status>`): `accepted` and `in-progress` need `` `reviewed` equal to `revision` ``, and a design's `active` needs `` `implemented` not above `reviewed` ``, which a missing `implemented` fails and in which a missing `reviewed` reads as 0.
- Otherwise it sets `status` and `updated` to today, regenerates the indexes (`write_indexes`), prints `<id>: <old status> -> <new status>` and exits 0. It sets no other field.
- `CANON_VERSION` 33.

Skill text: a `status ID STATUS` row in the Tool table of `skills/governance/canon/SKILL.md` (moves a doc's status forward and checks the move); `doc-types.md` says a concept is set `adopted`, and a non-terminal status set, with `canon.py status` or by editing the field.

Test criteria; seam: the `status` command line, its output, exit code and the files it writes:

1. A draft design with `reviewed` equal to `revision`: `status D001 accepted` prints `D001: draft -> accepted`, exits 0, sets `status` and `updated` and no other frontmatter line, and `docs/README.md` shows the design as `accepted`.
2. A draft design with `implemented` and `reviewed` equal to `revision` goes straight to `active`; a draft concept goes to `adopted` and stays in `concepts/`; a draft plan with `reviewed` equal to `revision` goes to `in-progress`.
3. Each of these exits 1 with its message and leaves `git status --porcelain` unchanged: an unknown id; an archived doc; `done` for a design; `retired` for a design; `accepted` for an accepted design, whose message ends `, to active`, and for an active one, whose message has no list; `accepted` with `reviewed` below `revision`; plan `in-progress` without `reviewed`; design `active` without `implemented`, with `implemented` above `reviewed`, and with `implemented: 1` and no `reviewed`; any status while `docs/README.md` has a start marker and no end marker.
4. `canon.py -h` lists `status`.

### S2: The `approved` field

Status: done

Builds on `D006#frontmatter` (`approved`, `reviewed`, `reviewers`, `implemented`).

Changes in `canon.py` and `tests/test_canon.py`:

- `approved` joins the optional fields of designs and plans. On a design or plan, a value that is not an integer from 1 to `reviewed`, `reviewed` reading 0 without the field, gives ``` `approved` must be an integer revision from 1 to `reviewed` ```. Another type gets the unknown-field error. `check --fix` neither sets nor deletes it.
- `CANON_VERSION` 34.

Skill text, in the Frontmatter section of `skills/governance/canon/SKILL.md`: `approved: 4  # D and P` in the example and a bullet saying it is the latest revision the user approved, set as the workflow's Gate status says; `reviewers` names who reviewed that revision, never accumulated across revisions; a revision that needs no code change raises `implemented` as the workflow's Gate status says.

In this slice's commit, the orchestrating session sets `approved` at the revision the user has approved by then: D001 12, D003 7, D005 2 and D006 4, approved by starting `/canon-plan D007`; D007 5 and this plan 1 once the user approves them with this plan's gate report or by starting `/canon-implement P003`.

Test criteria; seam: `canon.py check` output:

1. A design with `reviewed: 3` and `approved: 3`, and a plan with `reviewed: 1` and `approved: 1`, give no error.
2. `approved: 4` on that design, `approved: 0`, `approved: x`, and `approved: 1` on a plan without `reviewed` each give the error above.
3. `approved: 1` on a concept gives ``unknown frontmatter field `approved` ``.

### S3: Follow-up trace units

Status: done

Builds on `D001#units`, `D001#call-sites` and `D001#review-dispositions`.

Changes in `canon.py` and `tests/test_canon.py`:

- `follow-up` joins the trace kinds, outside the first row of Units: it takes `--parent` like a gate and is top-level without one; a slice or end check cannot be its parent.
- Its `end` takes `--dir` and `--input` like a gate's, and its dispositions take the gate's roles, `same-model` and `cross-family`; the end line carries them. The `--input` help and its error name the follow-up unit: `--input comes with gate, follow-up and code-review units only`.
- `start` keeps the as-built second parent for a `gate` only.
- `CANON_VERSION` 35.

Skill text, measured by `validate.py`:

- `skills/governance/canon/SKILL.md`, the paragraph starting "In `trace` calls": a follow-up round's `<skill>` is `canon-blind-review`'s, as a gate's is. The paragraph has 108 of its 110 tokens, so the sentence is reworded to make room.
- `skills/governance/canon/trace.md`: a follow-up round's `end` takes `--dir` and dispositions as a gate's, with the gate's roles. The file has 419 of its 420 tokens, so its wording is trimmed to make room.

Test criteria; seam: `canon.py trace start` and `trace end`, and the lines in `.canon/canon/trace/events.jsonl`:

1. `trace start follow-up D007 --tier L2 --skill <dir> --model m --parent <design unit>` prints `trace <id>`, and its start line has kind `follow-up`, `docs` `["D007@r<revision>"]` and that parent; without `--parent` it is top-level.
2. `trace end <id> delivered --dir .canon/canon-blind-review/D007-r4/followup-1 --input -` with same-model and cross-family dispositions writes them to the end line and archives the directory's files; a `spec` role gives `trace error` and writes nothing.
3. `--parent` naming a slice gives `trace error`, as for a gate; `--input` on a design unit's `end` gives the error above.
4. `validate.py` measures `trace.md` and the placeholder paragraph within their budgets.

### S4: One home for the shared blind-review rules

Status: done

Builds on `D003#launch`, `D003#input-and-reports`, `D003#resuming-and-replacing`, `D003#review-snapshots`, `D001#review-files` and `D007#reviewer-prompt`.

Changes in skill text only:

- `skills/execution/canon-blind-review/SKILL.md` states, once, what every blind review shares:
  - its prompt template, whose Target lines, reading line (`Read {what to read}.`) and Assess items the caller fills: the review gate from the `canon` workflow, code review from its briefs, any other review the target and whatever it links to or depends on, with criteria that fit the artifact. The template keeps, after the reading line, the rules on reading and writing (`Do not read .canon/` onward), then the report contract and the known-issue rule, Questions, the language line and the Verdict line;
  - launching: new subagents, never forks, without a model or effort; the first round in parallel; a host subagent in the foreground unless the session has other work meanwhile, such as another review, and a command in the background; once no other work remains, the lookup of a report whose completion notice has not come, in the host's record of the run (Cursor's `subagents/<agent id>.jsonl`, Codex's `rollout-*.jsonl`); a general-purpose subagent in Claude Code; and, while reviewers read in any round, no edit in the work tree outside `.canon/`, findings fixed once the reports are in;
  - review files: a gate's topic `<id>-r<N>`, a joint gate's named by its target; each follow-up round in `<topic>/followup-<k>/`, numbered from 1; a code review's topic; saving reports verbatim; `snapshot.txt` and `snapshot-confirm.txt`;
  - stopped runs of reviewers, the cross-family fallback chain, and a cross-family reviewer's confirmation or follow-up part going to the resumed same-model reviewer after a second stop; the manual fallback; the merge baseline;
  - the confirmation round and a new follow-up round with its prompt: review what changed since the last snapshot of the gate or its previous round, at the gate's tier and with its first-round criteria, reported as in a first round; the diff command over the revised targets or, without one, the revised sections; only the diff command allowed in `.canon/`; a host subagent resumed, a command or unresumable reviewer given its first-round prompt followed by the follow-up prompt, a manual reviewer's part given to the resumed same-model reviewer; fixes confirmed from the round's own snapshot.
- `skills/governance/canon/workflow.md`:
  - Review gate: keeps only the gate's own lines, merge rules and status, and names `canon-blind-review` for the rest, without "when it is installed"; the Code review section drops that hedge for `canon-code-review` too.
  - Reviewer prompt: the gate's lines are the Target line, a `Follow-on targets` line, the `Changes since` line with its rule (its commit is the newest one that holds the previous revision of every target that revises an existing doc), the As-built line, the reading line `Read the targets, the docs they link to, and the code they govern.`, and the Assess items ending with `Formatting, frontmatter and wording style are out of scope.`
  - Subagents: keeps the reviewer file, its setup, resuming by id per host and the stopped-run rule for workers, and points to `canon-blind-review` for reviewers, their launching and the lookup of a missing report.
- `skills/execution/canon-code-review/SKILL.md` keeps its briefs, topic and roles, and drops what the shared template and confirmation state, such as the known-issue sentence appended to both briefs.
- `skills/execution/canon-review/SKILL.md`: angle reviewers report as `canon-blind-review`'s report contract says, each finding's location followed by the title the R doc's Findings rows take; their brief keeps the scope, the angle's reference, modifying no file, skipping rejected Decisions and redacting secrets.
- `canon-blind-review`'s description may name follow-up rounds beside confirmation, keeping its triggers within the first 190 characters; the README Skills table's summary is checked against it.

Test criteria; seam: the skill files, `scripts/validate.py` and `npx skills add . --list`:

1. `rg -l` for `at most 10 minor`, `known issue only when it is worse`, ``Do not read `.canon/` `` and `gets one more run` over `skills/` lists only `canon-blind-review/SKILL.md`, apart from the `canon` workflow's stopped-run rule for workers.
2. The gate's prompt assembled from `workflow.md` and `canon-blind-review` for D007 r4 with its follow-on targets, written to `.canon/canon-implement/P003-S4-gate-prompt.md`, says what D007§reviewer-prompt's text says; the Log keeps that path.
3. `canon-blind-review` names `<id>-r<N>`, `followup-<k>`, `snapshot-confirm.txt`, the follow-up prompt, the no-edit rule and both host records.
4. `validate.py` passes with D001's text budgets measured, and `npx skills add . --list` lists every skill.

### S5: Joint gates, follow-up rounds and approval in the workflow

Status: done

Builds on every section of D007 r5 except the Reviewer prompt, `D001#call-sites` (the review gate bullet) and `D004#init` (the canon block).

Changes:

- `skills/governance/canon/SKILL.md`, Workflow: every change has a tier except one that touches only docs that no design's `paths` names and bumps no revision; the paragraph on such changes; L2's approval as the workflow's Gate status says; the split's one joint gate with the parent as target.
- `skills/governance/canon/workflow.md`:
  - Flows: a commit after each review gate; a design revision that needs no code change ends once its gate has passed and, in L2, the user has approved it.
  - Design problems step 3: a follow-up round when this session's gate passed the design's previous revision.
  - Review gate: the revision-bump rule; the gate per change with its target and follow-on targets, D000's glossary included, at the highest tier, with one set of reviewers, one prompt and one `Changes since`; a plan's and an as-built revision's gates of their own; follow-on edits that change no meaning; the cross-family reviewer in follow-up rounds; step 1's question on content feedback; step 2's `trace start gate <ids>`; step 3's fix-only edits until step 7; step 5 on each target and `--dir .canon/canon-blind-review/<topic>`; step 7, commit the targets before any further edit that changes their meaning, the commit possibly holding other work.
  - Merging findings: "other than the gate's targets".
  - A Follow-up round section: the revisions it covers and the ones that pass a new gate (another session's, an as-built revision and the revision after an as-built revision's gate, one that raises the tier); its trace call site, `trace start follow-up <ids>` without `--base`, ended with `--dir .canon/canon-blind-review/<topic>/followup-<k>`.
  - Gate status: what counts as L2 approval, `approved` set and committed, a draft set `accepted` with `canon.py status`; a revised design that is `accepted` or `active`, and a revised plan that is `accepted` or `in-progress`, keeps its status; the rule for a revision that needs no code change.
- `canon.py`'s canon block template, and this repo's `AGENTS.md` block, read ``- State each change's tier (L0, L1, L2) before starting, unless it touches only docs that no design's `paths` names and bumps no revision. Designs and plans pass the review gate defined by the `canon` skill.``; `CANON_VERSION` 36.

Test criteria; seam: the skill files, `canon.py init`, `scripts/validate.py`:

1. Every Spec hunk of D007's diff from 7801614 to 1d127eb, outside the Reviewer prompt, maps to a sentence of `SKILL.md` or `workflow.md`; the Log keeps the mapping.
2. `validate.py` measures the gate's and the follow-up round's trace call sites within 40 tokens.
3. `init` in a new project writes the new tier line into the canon block (`InitTest`).
4. `canon.py check` passes.

### S6: Approval and commits in the phase skills

Status: done

Builds on `D007#gate-status`, `D007#follow-up-round`, `D007#phases`, `D002#backfill`, `D006#frontmatter` (`approved`) and `D006#doc-types` (Status).

Changes in skill text:

- `skills/execution/canon-design/SKILL.md`:
  - Interview, Sharpen fuzzy language: a D000 glossary revision is a follow-on target of the design's gate.
  - Gate keeps its step numbers, which Frame step 5 and D006's Spec cite: 1, link a concept the design absorbed from the design, then run `check` and fix its errors; 2, pass the review gate's steps 1 to 5; 3, set the status as the gate's step 6 says; 4, set a concept designs have absorbed in full `adopted` with `canon.py status`; 5, commit the docs as the gate's step 7 says, and in L2 ask for approval naming `/canon-plan D00X`, or with no command for a revision that needs no code change; on a yes, set `approved` on every target, set a draft `accepted` with `canon.py status`, or a new design that needs no code change `active` with `implemented` equal to its revision, and commit; 6, retro; 7, trace end. A revision this session makes after step 5's commit takes a follow-up round.
  - Frame step 5: the change's revision after the as-built commit passes a new gate, not a follow-up round.
  - The closing paragraph: a revision that needs no code change ends with `implemented` raised as Gate status says and gives no next command.
- `skills/execution/canon-plan/SKILL.md`:
  - Start: invoking it approves the named design and the follow-on targets its gate passed with it; before `new P --from`, set `approved` on each at its revision where it is lower and a draft `accepted` with `canon.py status`, say so in one line naming the gate's reviewers, and commit them.
  - Gate: step 3 cites the gate's step 6; step 4 commits the plan as the gate's step 7 says, and in L2 asks for approval naming `/canon-implement P00X`; on a yes, set the plan's `approved`, set a draft `accepted` with `canon.py status` and commit. A revision this session makes after that commit takes a follow-up round.
- `skills/execution/canon-implement/SKILL.md`, Start: invoking it on a plan sets the plan's `approved` to its revision and a draft plan `accepted` with `canon.py status`, and commits them; step 4 sets `in-progress` with `canon.py status`.
- `skills/governance/canon/doc-types.md`: the Designs Status line says how L2 approval is given and recorded and that a design is `active` with `implemented` once a revision that needs no code change has passed as Gate status says; the Plans Status line says how L2 approval is given and recorded; the D000 bullet says that a D000 written before the project has code needs no plan.

Test criteria; seam: the skill files, `scripts/validate.py`, `npx skills add . --list`:

1. `canon-design`, `canon-plan` and `canon-implement` each say when they set `approved` and with which revision, and none still sets a status by hand where `canon.py status` applies.
2. `canon-design` Frame step 5's citations of Gate steps 1 to 3, step 5 and steps 6 and 7, and D006§spec's citation of Gate step 4, name the steps they meant before this slice.
3. Every Spec hunk of D007's Gate status and Follow-up round diff from 7801614 to 1d127eb, and of D006's Frontmatter `approved` bullet and Doc types Status lines from 7801614 to c3000f2, maps to a sentence of these skills or `doc-types.md`; the Log keeps the mapping.
4. `validate.py` passes with D001's text budgets measured, and `npx skills add . --list` lists every skill.

## Notes

- Every commit that changes `canon.py` bumps `CANON_VERSION` and adds regression tests: S1 33, S2 34, S3 35, S5 36, the code review's fixes 37, D006 r5 38. Before each commit, run `python3 scripts/validate.py` outside the sandbox with the default `TMPDIR`, with D001's budgets measured, and `npx skills add . --list`.
- S3's skill text must fit budgets that are nearly full; when rewording cannot fit it without dropping a rule, that is a design problem in D001's budgets, not a reason to raise them.
- The plan settles these details the designs leave open, for the docs step to write into them where they belong: the order of `status`'s checks, that its lists are comma-separated, that `status -h` lists each type's statuses in order, that a current status outside the type's moves counts as before all of them, and that a missing or non-integer `reviewed` reads as 0, so a move that needs a passed gate needs `reviewed` of at least 1 and `active` an `implemented` of at least 1 (D006); the canon block's tier line (D004 names the block, not its lines); the split of the reviewer prompt into `canon-blind-review`'s template and the gate's lines, with the reading line a whole sentence the caller fills in place of `{reading line}`, and the follow-up prompt's wording (D003).
- `approved` cannot be written before S2, since `check` rejects unknown fields; S2's commit records the approvals given before it.
- The docs step sets `implemented` to D007 5, D001 12, D003 7, D005 2 and D006 5, and sets each of these findings' disposition to `fixed <commit>` with the commit of the slice that finishes it: R003-F36 S1; R003-F5, R003-F10 and R002-F3 S4; R003-F1 and R003-F6 S5; R003-F2, R003-F21 and R003-F24 S6.
- The skills the user installed with `npx skills add -g` change only when the user updates them; slices edit only the repository.

## Log

- 2026-11-11: The plan's gate found two design problems in D007 r4: it sent the revision after an as-built revision's gate to a follow-up round, whose reviewers keep the as-built criteria, and its "commit at once" conflicted with setup's single commit after all its gates (D004). The user chose a new gate for the former and a commit before any edit that changes the targets' meaning for the latter. D007 r5 (1d127eb) passed a follow-up round of the r4 gate; `based_on` moves to D007@r5, S5 carries step 7 and the Follow-up round's new gates, and S6 carries Frame step 5's new gate.
- 2026-11-11: The user approved D007 r5 and this plan by starting `/canon-implement P003`; `approved` is recorded in S2's commit. Started at 904c18b.
- 2026-11-11, S1 done: `status` and `status_moves` in `canon.py` (`CANON_VERSION` 33), `StatusTest` with 7 tests plus `status` cases in `IndexTest` and `HelpTest`; `validate.py` passed with D001's budgets measured. Deviation: `status -h` lists each type's statuses in order. Settled in the slice: a current status outside the type's moves counts as before all of them, and a `reviewed` that is not an integer reads as 0. Open: a concept's not-a-status message lists only `draft`, as D006 states, though `adopted` is its other valid target; put to the user.
- 2026-11-11, S2 done: `approved` among the optional and integer fields of designs and plans, checked from 1 to `reviewed` (`CANON_VERSION` 34), `ApprovedTest` with 3 tests; `validate.py` passed with D001's budgets measured. The `SKILL.md` Frontmatter bullets link the review gate's step 6, which S5 rewrites; S5 keeps them pointing at Gate status. This commit sets `approved`: D001 12, D003 7, D005 2, D006 4, D007 5 and this plan 1.
- 2026-11-11, S3 done: `follow-up` among the trace kinds, sharing the gate's roles (`GATE_ROLES`), `--dir` and `--input`, with the `--input` help and error naming it (`CANON_VERSION` 35); `FollowUpTest` with 3 tests, a `HelpTest` assertion and a follow-up case in the as-built snapshot test. The placeholder paragraph now has 110 of 110 tokens and `trace.md` 420 of 420: `trace.md`'s Roles bullet names the code review's roles and gives same-model and cross-family to the rest with "else".
- 2026-11-11, S4 done: `canon-blind-review` holds the shared template, launching, review files, stopped runs, manual fallback, merge baseline, confirmation and the new follow-up round with its prompt; `workflow.md` keeps the gate's own lines and rules, the reviewer file and worker runs; `canon-code-review` fills the template with the reading line `Read the change and these sources: {paths}.`; `canon-review`'s angle reviewers report from the template's known-issue rule to its Verdict line, a title after each location. The gate prompt assembled for D007 r4 is at `.canon/canon-implement/P003-S4-gate-prompt.md` and equals D007§reviewer-prompt's text filled for that gate; checks in `.canon/canon-implement/P003/S4/`. The orchestrator also reworded two pointers left stale: `SKILL.md`'s line on `workflow.md` (how workers launch) and `doc-types.md`'s concept review.
- 2026-11-11, S5 done: `workflow.md` gains the revision-bump rule, the gate per change, step 7, a Follow-up round section and a Gate status section that step 6 and `SKILL.md` link; `SKILL.md`'s Workflow states the docs-only exemption; the canon block's tier line in `canon.py` and `AGENTS.md` (`CANON_VERSION` 36), with an `InitTest` case. Trace call sites measure 39, 37, 33 and 39 of 40 tokens; the follow-up round's end names its unit `<round id>` to fit. The mapping of D007's Spec hunks is at `.canon/canon-implement/P003/S5/mapping.md`, with `check_mapping.py` beside it.
- 2026-11-11, S6 done: `canon-design`, `canon-plan` and `canon-implement` say when they set `approved`, commit it and move statuses with `canon.py status`; `canon-design`'s Gate keeps its step numbers, and both phase skills send this session's later revisions to follow-up rounds, naming the workflow's list of revisions that pass a new gate; `doc-types.md`'s Status lines and D000 bullet follow Gate status. Deviations: `canon-plan`'s Gate step 2 passes the review gate's steps 1 to 5, as `canon-design`'s does, so steps 6 and 7 do not run twice; the start skills require a passed gate rather than `accepted`, since invoking them now sets a draft `accepted`. The orchestrator dropped the split bullet's "as step 5 does for a backfill", which read as a new gate after a split, named where `canon-plan` finds a gate's follow-on targets, and pointed `doc-types.md`'s as-built status at Gate status. The mapping is at `.canon/canon-implement/P003/S6/mapping.md`, with `check_s6.py` beside it. Left for the docs step: `README.md`'s line that starting the next phase is the L2 approval.
- 2026-11-11, code review from 904c18b (spec, standards and cross-family reviewers, all approving with minor findings). Fixed: `status` let a doc with neither `revision` nor `reviewed` become `accepted`, and one with `implemented: 0` and no `reviewed` become `active` (`Doc.reviewed`, `CANON_VERSION` 37, two `StatusTest` cases); a follow-up round in the phase skills ran the gate's steps 6 and 7 twice, so it now stops at step 5; `README.md`'s tier, approval, follow-up, trace and snapshot lines and the Tool table's `snapshot` row; `doc-types.md`'s Status lines and `canon-design`'s approval step link Gate status instead of restating it; the template's `{reading line}` takes a whole sentence; "a joint gate" became "a gate with follow-on targets"; `canon-plan` approves the designs a new plan's `based_on` names, as D006 states, not a gate's follow-on targets; Notes gain three S1 details. Declined: moving the `.canon/` checks this Log cites into attachments, since their results are stated here; one table of the statuses that need a passed gate, and shared test helpers, refactors beyond this change. Put to the user: the concept's not-a-status message, and a draft becoming `active` past `accepted` while `reviewed` lags `revision` (D006).
- 2026-11-11: The user chose to fix both D006 questions. D006 r5 lists the statuses `status` moves along in its not-a-status message, so a concept's names `adopted`, and makes a move that skips `accepted` meet `accepted`'s condition first. It passed a follow-up round of the D007 r4 gate (one minor wording finding, fixed); `based_on` moves to D006@r5, and the `canon.py` change follows once the user approves r5.
