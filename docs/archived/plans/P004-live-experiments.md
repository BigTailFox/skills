---
status: done
created: 2026-11-12
updated: 2026-11-12
revision: 1
modules: [canon]
summary: Experiment statuses answered, live concluded, superseded, overturned and dropped in canon.py, its tests and the skill texts that set and archive them.
refs: [D006, D008]
based_on: [D006@r9, D008@r5]
reviewed: 1
reviewers: [claude-opus-5.5, gemini-4-argon-high]
approved: 1
---

# P004: Live concluded experiments

Implements [D006: Doc model and writing rules](../../designs/D006-doc-model.md) r9 and [D008: Prototypes and research](../../designs/D008-experiments.md) r5, which passed one gate together. Each design's `implemented` equals its revision at 13203bc, D006 7 and D008 3, so the work is each design's Spec diff from 13203bc to 832e6c7.

## Current state

Every slice is done, the code review's fixes landed, and the docs step set D006's `implemented` to 9 and D008's to 5. Nothing is left.

## Slices

### S1: The `answered` status

Status: done

Builds on `D006#doc-types` (Experiments, Status), `D006#statuses-and-archiving` (terminal conditions and the `canon.py status` block), `D006#check` (the unfinished level), `D008#recorded-research` step 5, `D008#research-brief` and `D008#prototype-verdicts` step 1.

Changes in `skills/governance/canon/scripts/canon.py`, tested in `tests/test_canon.py`:

- `TYPES["E"]["active"]` becomes `planned`, `running`, `answered`, so `check` accepts `answered` outside `archived/`, `status` moves to it and `status -h` lists it.
- `status E00X answered` checks, after its existing checks, the terminal conditions of `concluded`: `unfinished_problems(doc)` plus `terminal_problems(doc, "concluded")`. Each failure prints `ERROR <path>: <problem>`, as `archive` prints them, and `status` exits 1, changing no file.
- `check`: the unfinished level of an experiment `answered` is `ERROR`, set beside `past_gate` rather than through it, since `past_gate` also gates the unreviewed-revision check that experiments, which have no `reviewed`, would fail; on a live answered experiment `check` reports `terminal_problems(doc, "concluded")` as errors.
- `CANON_VERSION` 41.

Skill text:

- `skills/governance/canon/SKILL.md`: the Doc types row for experiments reads `planned → running → answered → concluded`; the Rules line on unfinished docs adds an experiment before it is answered.
- `skills/governance/canon/doc-types.md`, Experiments: an experiment is `running` while a run or research is under way and `answered` once its Conclusion is written, until a design or plan absorbs it.
- `skills/execution/canon-research/SKILL.md`: the brief gains ``- `summary`: one line that leads with the question's subject and states the answer.``; Absorb sets the experiment `answered` with `canon.py status` once the sources are confirmed, before absorbing the conclusion.
- `skills/execution/canon-prototype/SKILL.md`, Capture step 1: the Conclusion is the verdict, no longer where it was absorbed, which step 2 does later; the same `summary` rule; then set the experiment `answered` with `canon.py status`.

Test criteria; seam: the `status`, `check` and `-h` command lines, their output, exit codes and the files they write:

1. A running experiment with Setup, Conclusion and `summary` filled: `status E001 answered` prints `E001: running -> answered` and exits 0, and `check` then reports no problem for it.
2. A running experiment with an empty `Command:`, no `Sources:`, an empty Conclusion and template guidance: `status E001 answered` exits 1, prints `ERROR docs/experiments/E001-<slug>.md: ` lines for ``Setup: `Command` is empty (research lists `- Sources:` instead)``, `Conclusion is empty` and the guidance, and leaves `git status --porcelain` empty. With `- Sources:` filled, no Setup line fails.
3. `check` on a live answered experiment with an empty `summary` and an empty Conclusion reports both as `ERROR`, and no unreviewed revision; a running experiment with the same content gets only the `WARN` for the empty `summary` and none for the Conclusion.
4. `status -h` lists `E: planned, running, answered`.

### S2: Live `concluded` experiments

Status: done

Risk: `check_doc`'s status branches set the level of every doc's problems, and the live links feed `check`, `status` and S3's `archive`; a link they miss or miscount misleads all three.

Builds on `D006#doc-types` (Experiments, Status), `D006#statuses-and-archiving`, `D006#check` (unlinked concluded experiment), `D006#templates-and-new`, `D008#prototype-verdicts` and `D008#absorbing-a-conclusion`.

Changes in `canon.py` and `tests/test_canon.py`:

- `Repo` gains the live links: for each file, the ids of the designs and plans outside `archived/`, in every docs root, whose body links it (`doc_links`), cached as `design_linked` is. A link to the experiment's file counts with or without an anchor; a link into its attachment directory does not.
- `check`: a `concluded` experiment outside `archived/` is valid, as an adopted concept is. On every live concluded experiment, linked or not, `check` reports `terminal_problems(doc, "concluded")` as errors, and its unfinished level is `ERROR`, as for every terminal status. One that no live design or plan links also gets `WARN concluded, but no live design or plan links it; link it or archive it as concluded`.
- `status_moves("E")` ends with `concluded`, which `status` no longer refuses as terminal. `status E00X concluded` checks first that a live design or plan links the experiment (`canon: <id> needs a live design or plan that links it to become concluded`), then the terminal conditions as `answered` does.
- `audit` leaves a live concluded experiment out of its idle docs, and its `--days` help names concluded experiments beside concepts and active designs.
- The experiment template's Conclusion guidance reads `<!-- canon: The answer the Results give to the Question. -->`, no longer asking where it was absorbed.
- `CANON_VERSION` 42.

Skill text:

- `skills/governance/canon/SKILL.md`: the Doc types header says an adopted concept and a concluded experiment may stay live; the Tool table's `status` row adds that an experiment may move to a live `concluded`; its `audit` row leaves out concluded experiments with concepts and active designs.
- `doc-types.md`: the opening paragraph sets a live experiment's `concluded` with `canon.py status`, as a live concept's `adopted`. The Plans **Notes** bullet ends: which the docs step writes into the design with the experiment links they carry. Experiments replaces its Absorb bullet with D006's Status rule: `concluded` means answered and absorbed, and `canon.py status` sets it only while the body of a live design or plan links the experiment; the session that writes the link sets it, else `canon-design`'s Gate step 4, else the docs step before it archives any plan; it stays live while such a link remains and is archived as `concluded` once none does, which the docs step does for each that `check` reports unlinked.
- `skills/governance/canon/workflow.md`, Docs step: step 1 writes the details the plan's Notes list into the spec with the experiment links they carry. Step 4 updates each listed plan's slice statuses, Current state and Log and reports paused slices, but no longer archives the plan. Step 5, after the dispositions and known issues, sets `concluded` with `canon.py status` each answered experiment that the designs and plans step 1's `affected` listed link, then archives what is finished in this order: plans whose every slice is `done` (`done`), reviews with no open finding (`closed`), fixed investigations (`resolved`), and experiments `check` reports concluded but unlinked (`concluded`).
- `skills/execution/canon-design/SKILL.md`, Gate step 4: also set each answered experiment the design links `concluded` with `canon.py status`; both stay live, as the `canon` skill's doc types say.
- `skills/execution/canon-research/SKILL.md`, Absorb: step 2 absorbs the conclusion with a link to the experiment in a design and in a plan's Notes alike; step 3 becomes: the session that wrote the link sets the experiment `concluded` with `canon.py status`, and the `canon` skill's doc types say which other steps set it and when it is archived.
- `skills/execution/canon-prototype/SKILL.md`, Capture: step 2 writes the decision with a link to the experiment, into the design or the plan's Notes; step 4 becomes research's step 3.

Test criteria; seam: the `check`, `status`, `audit`, `new` and `-h` command lines and their output, exit codes and files:

1. A concluded experiment in `experiments/` that the body of a live draft plan links, of a live design with an anchored link (`E001-<slug>.md#results`), or of a live design in a module's docs root (`init --root mod`): `check` reports neither a status error nor the unlinked warning for it. Linked only from an archived design or plan, from a concept or another experiment, or into `experiments/E001/`: `check` warns `concluded, but no live design or plan links it; link it or archive it as concluded` and reports no status error. An archived concluded experiment that nothing links gets no warning.
2. A live concluded experiment that a live plan links, with an empty `summary` or an empty Conclusion: `check` exits 1 with each as `ERROR`.
3. `status E001 concluded` on an answered experiment a live plan links prints `E001: answered -> concluded`, exits 0 and leaves the experiment in `experiments/`; a running one linked and complete goes straight to `concluded`. With no live link, it exits 1 with `canon: E001 needs a live design or plan that links it to become concluded`, also when the Conclusion is empty, and changes no file; linked with an empty Conclusion, it prints the `ERROR` line and exits 1.
4. `audit` with a live concluded and a running experiment, both untouched for longer than its idle days, lists the running one only; `audit -h` names concluded experiments in `--days`.
5. `new E` writes the new Conclusion guidance; `status -h` lists `E: planned, running, answered, concluded`.

### S3: Archiving as superseded, overturned or dropped

Status: done

Builds on `D006#doc-types` (Experiments, Status) and `D006#statuses-and-archiving` (terminal conditions and the `canon.py archive` block).

Changes in `canon.py` and `tests/test_canon.py`:

- `TYPES["E"]["terminal"]` becomes `concluded`, `superseded`, `overturned`, `dropped`, so `archive` takes them, `archive -h` lists them and `check` accepts them inside `archived/` and, `concluded` aside, rejects them outside it with the existing message.
- `archive E00X concluded` refuses, after the terminal-status check and before the live sub-design check, changing no file: an experiment whose status is another (`canon: <id> is <status>, not concluded; archive an experiment nothing absorbed as dropped`), then one the body of a live design or plan links (`canon: <id> is linked by <ids>; it stays live while a live design or plan links it`).
- `terminal_problems` skips the Setup labels for `dropped`; `Conclusion is empty` still applies.
- `test_archive_checks_every_terminal_condition` archives its planned experiment as `dropped`, since `archive E001 concluded` now refuses a planned one before the terminal conditions.
- `CANON_VERSION` 43.

Skill text:

- `skills/governance/canon/SKILL.md`: the Doc types row for experiments reads `planned → running → answered → concluded, superseded, overturned, dropped`.
- `doc-types.md`, Experiments, from D006's Status rule: whichever step sets an experiment `concluded` archives each live answered or concluded experiment it links on the same question, as `superseded` after moving to the new experiment the links of live designs and plans that cite the earlier one when its result still holds, or as `overturned` when the new result shows it wrong; `superseded` keeps its successor in `refs`; `overturned` has its Conclusion state what was wrong and link what showed it, and the session that finds a result wrong treats each accepted or active design linking it as a design problem, revises a draft design it is writing that links it, and names each other draft design and each live plan linking it to the user; `dropped`, from any status, when the question no longer matters, its Conclusion saying why.
- `workflow.md`, docs step 5: setting an experiment `concluded` archives the earlier experiments on its question as `doc-types.md` says.
- `canon-design`, Gate step 4, `canon-research`, Absorb step 3, and `canon-prototype`, Capture step 4: the same, so every step that sets `concluded` archives the earlier experiments on the question as the `canon` skill's doc types say.

Test criteria; seam: the `archive`, `check` and `-h` command lines and their output, exit codes and files:

1. `archive E001 concluded` exits 1 and changes no file: on a running experiment with `canon: E001 is running, not concluded; archive an experiment nothing absorbed as dropped`, on an answered one with `is answered, not concluded`, and on a concluded one that a live design D001 and a live plan P001 link with `canon: E001 is linked by D001, P001; it stays live while a live design or plan links it`. A concluded one that only an archived plan links is archived, and the plan's link follows it.
2. `archive E001 dropped` on a planned experiment with empty Setup labels and a Conclusion succeeds; with an empty Conclusion it prints `Conclusion is empty` and exits 1. `superseded` and `overturned` with empty Setup labels and no `Sources:` print the Setup errors.
3. `check` passes an archived dropped experiment with empty Setup labels and reports them for an archived superseded one; a live `dropped` experiment gets ``status `dropped` requires the doc to be in archived/; use `canon.py archive` ``, and an archived `answered` one ``status `answered` requires the doc to be outside archived/; set one of concluded, superseded, overturned, dropped``.
4. `archive -h` lists `E: concluded, superseded, overturned, dropped`.

### S4: A later run on an answered experiment

Status: done

Builds on `D006#doc-types` (Experiments: a later run), `D006#statuses-and-archiving` (the `canon.py status` block: the move back), `D008#recorded-research` step 2 and `D008#prototype-framing` step 2.

Changes in `canon.py` and `tests/test_canon.py`:

- `status E00X running` on an answered experiment moves it back to `running` when no live design or plan links it, else exits 1 with `canon: <id> is linked by <ids>; a later run gets a new experiment that links it`, a check at the step of the move's conditions.
- The forward-only refusal for an answered experiment ends with `, or back to running` after its later statuses. No other status moves back.
- The `status` subcommand's help names the move back, and `HelpTest` asserts the new text.
- `CANON_VERSION` 44.

Skill text:

- `doc-types.md`, Experiments: a later run extends an experiment that is `planned` or `running`, or `answered` with no live design or plan linking it, which moves back to `running` for the run; otherwise the run gets a new experiment that links it.
- `skills/governance/canon/SKILL.md`: the Tool table's `status` row adds the move back of an answered experiment to `running`.
- `canon-research`, Reserve: look for experiments on the same question with `canon.py find --archived`; extend one that is `planned` or `running`, or `answered` with no live design or plan linking it, setting a `planned` or `answered` one `running` with `canon.py status`; otherwise run `canon.py new E <slug>`, fill Question, link each earlier experiment found on the question, and set it `running` with `canon.py status`. One already `running` from another session is still handled as Recover says.
- `canon-prototype`, Frame: set a new experiment `running` with `canon.py status`, or extend or link an earlier experiment on the same question as `canon-research` does when it reserves its doc.

Test criteria; seam: the `status` command line, its output, exit code and the files it writes:

1. An answered experiment that only an archived design links: `status E001 running` prints `E001: answered -> running` and exits 0.
2. One a live plan P001 links: it exits 1 with `canon: E001 is linked by P001; a later run gets a new experiment that links it` and changes no file.
3. `planned` or `answered` on an answered experiment exits 1 with `canon: E001 is answered; status moves only forward, to concluded, or back to running`; `running` on a concluded one with `canon: E001 is concluded; status moves only forward`; `planned` on a running one with `canon: E001 is running; status moves only forward, to answered, concluded`.
4. `canon.py -h` describes `status` with the move back.

## Notes

- Every commit that changes `canon.py` bumps `CANON_VERSION` and adds regression tests: S1 41, S2 42, S3 43, S4 44, later fixes from 45. Before each commit, run `python3 scripts/validate.py` with the default `TMPDIR` and D001's text budgets measured, and `npx skills add . --list`; one test class runs with `python3 -m unittest discover -s tests -p 'test_canon.py' -k <class>`.
- No edited sentence holds a `trace` call, so D001's budgets bind none of this text; `validate.py` must still measure them before a commit.
- Projects that upgrade `canon.py` keep valid docs: experiments archived as `concluded` stay valid (D006's decision), and a live `running` experiment with a written Conclusion stays valid until a session sets it `answered`. This repository has no experiments.
- The docs step moves archiving a plan from step 4 into step 5's ordered archive list, after setting `concluded` and before archiving unlinked concluded experiments, so step 5 holds the experiments' rules, as D006§spec cites it, and an experiment only a plan links is set `concluded` before the plan is archived and then archived itself. No design owns the docs step apart from its experiments (D007 leaves it out, D000 gives it none), so the user's approval of this plan covers the move; `canon-implement`'s line that the docs step archives the plan stays true.
- The plan settles these details D006 leaves unstated, for the docs step to write into it: the live links count a link to the experiment's file, with or without an anchor, from the body of a design or plan outside `archived/` in any docs root, and not a link into its attachment directory; the `<ids>` of `archive`'s and `status`'s linked refusals are sorted and comma-separated.
- The docs step sets `implemented` to D006 9 and D008 5. R003-F17 is already `fixed D006@r8`, and D008-K4 and D008-K7 left with D008 r5.
- The skills the user installed with `npx skills add -g` change only when the user updates them; slices edit only the repository.

## Log

- 2026-11-12: Started from D006 r9 and D008 r5, approved by the user at 832e6c7.
- 2026-11-12: The user approved this plan at 72297ad. Started at 72297ad.
- 2026-11-12, S1 done: `answered` among the experiment's non-terminal statuses; `status` checks the terminal conditions of `concluded` before setting it, and `check` gives a live answered experiment the `ERROR` unfinished level and its terminal conditions (`CANON_VERSION` 41). `unmet_terminal` now prints the failed terminal conditions for both `archive` and `status`. Tests: three new in `StatusTest` and `UnfinishedDocTest`, with the `EXPERIMENT` and `RUN` fixtures, and the `HelpTest` assertion; `validate.py` passed with D001's budgets measured. In `canon-research`, Absorb step 1 sets `answered` at its end, so steps 2 and 3 keep the numbers S2 cites; in `canon-prototype`, the Conclusion is the verdict, since `UI.md` already asks for the winning variant and why.
- 2026-11-12, S2 done: `LIVE_TERMINAL` names the terminal status each type may hold live (a concept's `adopted`, an experiment's `concluded`), which `check` and `status_moves` share; `Repo.live_links()` maps each file to the ids of the live designs and plans whose body links it, in `docs` order, which puts designs before plans and sorts each by id; `check` sends both live statuses through the terminal branch, warning on an unlinked one; `status` checks the live link, then the terminal conditions; `audit` and its `--days` help leave out live concluded experiments; the experiment template's Conclusion guidance asks for the answer only (`CANON_VERSION` 42). Tests: eight new in `DocRulesTest`, `UnfinishedDocTest`, `StatusTest` and `AuditTest`, and `HelpTest` assertions; a mutation counting only plans as live linkers turned the criterion 1 test red. `validate.py` passed with D001's budgets measured. The main session restored "into the design or plan" in `canon-prototype`'s Capture step 2.
- 2026-11-12, S3 done: `superseded`, `overturned` and `dropped` join the experiment's terminal statuses; `archive E00X concluded` refuses another status, then a live link, naming the linking ids from `live_links()`; `terminal_problems` skips the Setup labels for `dropped` (`CANON_VERSION` 43). Tests: five new in `DocRulesTest`, the `archive_refused` helper, a literal `archive -h` assertion in `HelpTest`, whose loop over `TYPES` passes whatever the types hold, and `test_archive_checks_every_terminal_condition` archiving as `dropped`; mutations confirmed the two tests that passed on arrival can fail. `validate.py` passed with D001's budgets measured. `doc-types.md` puts D006's archiving rules in a **Superseded, overturned** and a **Dropped** bullet, and docs step 5 links them rather than restating them.
- 2026-11-12, S4 done: `status` moves an answered experiment back to `running` unless a live design or plan links it, refusing with the linking ids from `live_links()`; its forward-only refusal for an answered experiment ends with `, or back to running`, and its help names the move back (`CANON_VERSION` 44). Tests: three new in `StatusTest` and the `HelpTest` assertion; a mutation letting `concluded` move back turned the criterion 3 test red. `validate.py` passed with D001's budgets measured.
- 2026-11-12: Code review from 72297ad, with a Spec, a Standards and a cross-family (gemini-4-argon-high) reviewer: no blocker or major finding and eight minor ones, the cross-family reviewer none. Fixed in 93f3913 (`CANON_VERSION` 45): the superseded experiment gains its successor in its `refs`, the archiving of earlier experiments names the newly concluded one as the linker, docs step 5 walks each affected design and plan, `canon.py` reads the live linkers once per command and calls the printing helper `report_unmet_terminal`, the tests share a `DESIGN` body and a `refuses` helper, and this Log names the main session. Declined: one helper for the experiment status rules that `check` and `status` each branch on, since `canon.py` branches per type throughout.
- 2026-11-12: Docs step: D006 states what counts as a live link and the order of the linking ids, and its `implemented` is 9; D008's is 5. Archived as done.
