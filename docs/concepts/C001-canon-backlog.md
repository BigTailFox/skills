---
status: draft
created: 2026-11-05
updated: 2026-11-10
revision: 1
modules: [canon]
summary: Ideas for the canon module that no design tracks yet, from codebase reviews and deferred findings.
refs: [R001]
---

# C001: Canon backlog

## Motivation

Findings that are not defects of code a design governs, and work that needs a new design first, land here so they stay tracked until a design or an L0 change takes them up.

## Ideas

- **Skills outside canon projects** ([R001: Codebase review of the canon module](../archived/reviews/R001-canon-module.md), F13). Installed globally, the auto skills trigger on generic requests in any repository, and `canon.py new` then writes canon docs and an index into a project that never set canon up. Scope each auto trigger to projects whose `AGENTS.md` has the canon block with a fallback to the skill's plain discipline, and make `new` and `adopt` refuse without the block. A new topic: `/canon-design`.
- **A design for skill layout and invocation** (R001-F10, F11). AGENTS.md's Skill rules, `scripts/validate.py`, `agents/openai.yaml` and the trigger modes have no design; neither do the contracts other skills execute: `canon-grill`'s triage, `canon-tdd`'s definition of done, `canon-code-review/smells.md` and `canon/writing.md`. Backfill them before they next change. `canon-review/security.md` counts as a project doc by its name, so the design that takes on `canon-review` lists its exact path.
- **One place for closing a workflow** (R001-F5). The retro end-check paragraph is copied into seven skills and the rule for routing a deferred finding into six; one section in `workflow.md` and one rule beside the known-issue format would replace them.
- **Work-tree snapshots apart from trace** (R001-F6). `canon.py snapshot`, which every confirmation uses, is built from the opt-in trace subsystem's parts; a section of its own, with `trace start` and `snapshot` as its callers, would let either change alone.
- **A faster test suite** (R001-F8). 172 tests take about 190 s and `validate.py` runs them after any skill change. Run `tests/` only when `canon.py` or `tests/` changed, and copy one initialized template repository per test.
- **Check references between skill texts** (R001-F9). `validate.py` drops `#anchor` from links and checks no skill names or "workflow (Section)" references.
- **One record per doc type in `canon.py`** (R001-F12). A type's rules are spread over `TYPES`, `TEMPLATES`, the field tables, `check_doc`'s branches and the id helpers. Speculative.
- **Error messages that name the next step** (R001-F17, F18). `check`'s unknown entry, `new`'s slug and `--from` errors, `show`'s missing section, `find`'s miss of an archived doc, `adopt` of a missing file (whose wording D004 states) and the `--base` errors (missing ref or shallow history) stop short of the value or the command to run.
- **`which` on missing paths** (R001-F19). `which` answers `no design`, or a design, for paths that exist neither on disk nor in Git.
- **Tests for `adopt` and the index format** (R001-F28). D004's `adopt` and D005's format and `index out of date` error are as-built and almost untested.

## Open questions

- Should a project's `AGENTS.md` without the canon block make the auto skills stand down entirely, or run their plain discipline without docs?
