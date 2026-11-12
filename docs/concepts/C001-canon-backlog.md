---
status: draft
created: 2026-11-05
updated: 2026-11-12
revision: 3
modules: [canon]
summary: Ideas for the canon module that no design tracks yet, from codebase reviews and deferred findings.
refs: [R001, D006, D007, D008, D001, D003, R003]
---

# C001: Canon backlog

## Motivation

Findings that are not defects of code a design governs, and work that needs a new design first, land here so they stay tracked until a design or an L0 change takes them up.

## Ideas

- **Skills outside canon projects** ([R001: Codebase review of the canon module](../archived/reviews/R001-canon-module.md), F13). Installed globally, the auto skills trigger on generic requests in any repository, and `canon.py new` then writes canon docs and an index into a project that never set canon up. Scope each auto trigger to projects whose `AGENTS.md` has the canon block with a fallback to the skill's plain discipline, and make `new` and `adopt` refuse without the block. A new topic: `/canon-design`.
- **A design for skill layout and invocation** (R001-F10, F11). AGENTS.md's Skill rules, `scripts/validate.py`, `agents/openai.yaml` and the trigger modes have no design; neither do the contracts other skills execute: `canon-grill`'s triage, `canon-tdd`'s definition of done and `canon-code-review/smells.md`. Backfill them before they next change. `canon-review/security.md` counts as a project doc by its name, so the design that takes on `canon-review` lists its exact path.
- **One place for closing a workflow** (R001-F5). The retro end-check paragraph is copied into seven skills and the rule for routing a deferred finding into six; one section in `workflow.md` and one rule beside the known-issue format would replace them.
- **Work-tree snapshots apart from trace** (R001-F6). `canon.py snapshot`, which every confirmation uses, is built from the opt-in trace subsystem's parts; a section of its own, with `trace start` and `snapshot` as its callers, would let either change alone.
- **A faster test suite** (R001-F8). 172 tests take about 190 s and `validate.py` runs them after any skill change. Run `tests/` only when `canon.py` or `tests/` changed, and copy one initialized template repository per test.
- **Check references between skill texts** (R001-F9). `validate.py` drops `#anchor` from links and checks no skill names or "workflow (Section)" references.
- **One record per doc type in `canon.py`** (R001-F12). A type's rules are spread over `TYPES`, `TEMPLATES`, the field tables, `check_doc`'s branches and the id helpers. Speculative.
- **Error messages that name the next step** (R001-F17, F18). `check`'s unknown entry, `new`'s slug and `--from` errors, `show`'s missing section, `find`'s miss of an archived doc, `adopt` of a missing file (whose wording D004 states) and the `--base` errors (missing ref or shallow history) stop short of the value or the command to run.
- **`which` on missing paths** (R001-F19). `which` answers `no design`, or a design, for paths that exist neither on disk nor in Git.
- **Tests for `adopt` and the index format** (R001-F28). D004's `adopt` and D005's format and `index out of date` error are as-built and almost untested.
- **Experiment bookkeeping** ([D008: Prototypes and research](../designs/D008-experiments.md), found in its as-built revision). Nothing fills an experiment's `summary`, `modules` and `refs`; a research Conclusion does not name where it was absorbed, as a prototype's does; and neither skill says who commits the experiment and its attachments, or when.
- **How strong a reviewer needs to be** (the user, 2026-11-12). Nothing shows how a reviewer's model and reasoning effort trade review quality against time: a same-model reviewer runs on the session's model and effort ([D003: Subagents](../designs/D003-subagents.md)), and the reviewer file orders cross-family reviewers by preference alone. Research and experiments that replay gates and code reviews with known findings at several models and efforts could set defaults that stay fast and still catch what matters; the snapshots and review dispositions of [D001: Skill telemetry](../designs/D001-skill-telemetry.md) could supply the cases.
- **Research and runs in `E` docs** (the user, 2026-11-12). Source research (`canon-research`) and runs (`canon-prototype`, benchmarks) stay in one doc type ([D006: Doc model and writing rules](../designs/D006-doc-model.md), [D008: Prototypes and research](../designs/D008-experiments.md)) while keeping separate execution skills: both answer one question with external evidence for designs and plans to cite, share the same status and link rules, and combine on one doc when a run follows research on the same question ([R003§r003-f18-a-research-experiment-later-measured: R003-F18](../reviews/R003-silk-design-phase.md#r003-f18-a-research-experiment-later-measured)). D006 has no Decision stating why they share `E`, and three rough edges remain: the type directory `experiments/` reads narrowly for source research (where `E` acts as evidence); `canon.py new E` pre-fills `Commit:`, `Environment:` and `Command:`, which every research doc deletes to write `- Sources:`; and `terminal_problems` skips all three run labels whenever `Sources:` is filled, so a research doc that leaves empty template labels behind or gains a later run with missing run labels passes `check`.
- **`new P` without `--from`** ([D006: Doc model and writing rules](../designs/D006-doc-model.md), found in its as-built revision). Plans come only from an accepted or active design, yet `new` creates one without `--from` silently; it could warn.

## Open questions

- Should a project's `AGENTS.md` without the canon block make the auto skills stand down entirely, or run their plain discipline without docs?
