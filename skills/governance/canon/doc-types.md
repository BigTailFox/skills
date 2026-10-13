# Doc types

`canon.py new` creates each type with its required sections; `check` enforces them. Other sections may be added freely.

## Concepts (C)

Sections: Motivation, Ideas, Open questions.

Explore freely: ideas, trade-offs, brainstorming. A concept carries no spec and no plan. When an idea becomes work, create or revise a design that links the concept, then archive the concept as `adopted`. Archive rejected ideas as `dropped`.

## Designs (D)

Sections: Goals, Spec, Decisions; Budgets when there are quantitative targets.

- One design per topic, maintained for the topic's whole life. Revise it in place.
- **Goals**: what the design must achieve, measurable where possible.
- **Spec**: the authoritative, precise specification of every topic in `owns`. Give interfaces as code: signatures, schemas, CLI usage, config keys. User-visible behavior (CLI, API, UI) is specified here.
- **Budgets**: numeric targets such as latency, memory or size, each with how it is measured.
- **Decisions**: one line per key decision with its reason.
- **Status**: `draft` until the review gate passes, then `accepted`. Set `active` once the implementation has landed; an active design describes the current code. Revising an active design keeps it `active`; its spec leads the code until the plan lands. Archive as `superseded` (successor in `refs`) or `retired` (feature removed).
- **Split**: when a design outgrows one doc (`check` warns at 500 lines), run `new D <slug> --parent D00X` to create `D00XA`, `D00XB`, ... Move the sub-topic's spec, `owns` and `paths` into the sub-design; the parent keeps the overview and links to its children. Only one suffix level exists: a sub-design that outgrows itself becomes a new top-level design.
- The repo root has an architecture design: module map, allowed dependency directions, and a glossary of cross-module terms. Module-specific terms belong to the design that owns them.

## Plans (P)

Sections: Current state, Slices, Notes, Log.

- Create a plan only from an accepted or active design: `new P <slug> --from D00X`.
- **Current state** (top): current slice, next action, paused slices with their reasons. Update it at the end of every slice; a new session resumes from here.
- **Slices**: ordered `### S1: name` subsections. Each starts with a `Status:` line (`todo`, `in-progress`, `done`, `paused`), then lists its changes and the test criteria that prove it done.
- **Notes**: risks and constraints the implementer must keep in mind.
- **Log**: append decisions, results, evidence and deviations as they happen. How to handle deviations: [workflow.md](workflow.md#implementation).
- **Status**: `accepted` after the review gate, `in-progress` while implementing. Archive as `done` once every slice is `done`, in the commit that completes the implementation, or as `abandoned`.

## Reviews (R)

Sections: Scope, Findings.

- **Scope**: what was reviewed, at which commit, from which angles (function, performance, security, architecture, usability).
- **Findings**: one table row per finding:

  ```markdown
  | ID | Severity | Finding | Disposition |
  |----|----------|---------|-------------|
  | R003-F1 | major | Refresh races with logout | moved I012 |
  ```

  Severity is `blocker`, `major` or `minor`. Disposition is `open`, `fixed <commit>`, `moved <ID>` (handed to the C, D, P or I that now tracks it) or `declined <reason>`.
- Archive as `closed` as soon as no finding is `open`; `check` blocks it before that.
- R docs cover code, modules or the whole repo. Design and plan reviews happen in the review gate and produce no R doc.

## Experiments (E)

Sections: Question, Setup, Results, Conclusion.

- **Setup** lists `- Commit:`, `- Environment:` and `- Command:` so the experiment can be rerun.
- Keep data and attachments in `experiments/E00X/` beside the doc; link large binaries instead of committing them.
- Absorb the conclusion into the owning design (spec, budget or decision), then archive as `concluded`.

## Investigations (I)

Sections: Symptom, Reproduction, Analysis, Resolution.

- **Reproduction** lists `- Commit:`, `- Environment:` and `- Command:`.
- **Resolution** lists `- Root cause:`, `- Fix:` and `- Verification:`; all must be filled before archiving.
- Archive as `resolved` as soon as the defect is fixed or verified not to be one. When the root cause exposes a spec gap, fix the design too.

## Guides

Unnumbered docs for users and operators under `docs/guides/`; only link checks apply. Guides explain how to use the system and link to designs for specs.
