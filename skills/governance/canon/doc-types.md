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
- **Status**: `draft` until the review gate passes (and, in L2, the user approves), then `accepted`. Once an implementation has landed, set `active` and `implemented` to the revision the code matches. Revising an active design keeps it `active`; its spec leads the code until the next implementation lands and raises `implemented`. Archive as `superseded` (successor in `refs`) or `retired` (feature removed).
- **Split**: when a design outgrows one doc (`check` warns at 500 lines), run `new D <slug> --parent D00X` to create `D00XA`, `D00XB`, ... Move the sub-topic's spec, `owns` and `paths` into the sub-design; the parent keeps the overview and links to its children. Only one suffix level exists: a sub-design that outgrows itself becomes a new top-level design.
- The repo root has an architecture design: module map, allowed dependency directions, and a glossary of cross-module terms. Module-specific terms belong to the design that owns them.

## Plans (P)

Sections: Current state, Slices, Notes, Log.

- Create a plan only from an accepted or active design: `new P <slug> --from D00X`.
- **Current state** (top): current slice, next action, paused slices with their reasons. Update it at the end of every slice; a new session resumes from here.
- **Slices**: ordered `### S1: name` subsections. Each starts with a `Status:` line (`todo`, `in-progress`, `done`, `paused`), then a `Risk:` line naming the kinds when the slice involves complex logic, concurrency, performance, security or data migration (e.g. `Risk: concurrency, data migration`), then lists its changes and the test criteria that prove it done. Each criterion names its seam: the public interface, as the design's Spec defines it, where the test observes behavior. Seams in an accepted plan are agreed with the user; tests go only there.
- **Notes**: risks and constraints the implementer must keep in mind.
- **Log**: append decisions, results, evidence and deviations as they happen. How to handle deviations: [workflow.md](workflow.md#implementation).
- **Status**: `accepted` after the review gate (and, in L2, the user's approval), `in-progress` while implementing. Archive as `done` once every slice is `done`, in the commit that completes the implementation, or as `abandoned`.

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
- R docs cover code, modules or the whole repo. A periodic review of modules or the repo produces one R doc per run, with its reports in `reviews/R00X/`. Code review of a change records only its deferred findings in an R doc ([workflow.md](workflow.md#code-review)). Design and plan reviews happen in the review gate and produce no R doc.

## Experiments (E)

Sections: Question, Setup, Results, Conclusion.

An experiment answers one question with evidence, either by running something (benchmark, prototype, measurement) or by researching primary sources (official docs, specs, source code).

- **Setup** for a run lists `- Commit:`, `- Environment:` and `- Command:` so it can be rerun. Research lists `- Sources:` instead, one primary source per indented line.
- **Results** link every measurement to its raw data and every finding to its source.
- Prototype code, raw data and source excerpts go in `experiments/E00X/`. A prototype wired into the product code stays on a `prototype/E00X-<slug>` branch that `Commit:` points to.
- Absorb the conclusion into the owning design (spec, budget or decision), then archive as `concluded`.

## Investigations (I)

Sections: Symptom, Reproduction, Analysis, Resolution.

- **Reproduction** lists `- Commit:`, `- Environment:` and `- Command:`. Repro scripts and captured logs or traces go in `investigations/I00X/`, with secrets replaced by `<REDACTED>`.
- **Resolution** lists `- Root cause:`, `- Fix:` and `- Verification:`; all must be filled before archiving.
- Archive as `resolved` as soon as the defect is fixed or verified not to be one. When the root cause exposes a spec gap, fix the design too.

## Guides

Unnumbered docs for users and operators under `docs/guides/`; only link checks apply. Guides explain how to use the system and link to designs for specs.
