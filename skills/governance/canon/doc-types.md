# Doc types

`canon.py new` creates each type with its required sections; `check` enforces them. Other sections may be added freely.

## Concepts (C)

Sections: Motivation, Ideas, Open questions.

Explore freely: ideas, trade-offs, brainstorming. A concept carries no spec and no plan. When an idea becomes work, create or revise a design that links the concept, then archive the concept as `adopted`. Archive rejected ideas as `dropped`.

## Designs (D)

Sections: Goals, Spec, Decisions; Budgets when there are quantitative targets; Known issues while any are open.

- One design per topic, maintained for the topic's whole life. Revise it in place.
- **Goals**: what the design must achieve, measurable where possible.
- **Spec**: the authoritative, precise specification of every topic in `owns`. Give interfaces as code: signatures, schemas, CLI usage, config keys. User-visible behavior (CLI, API, UI) is specified here.
- **Budgets**: numeric targets such as latency, memory or size, each with how it is measured.
- **Decisions**: one line per key decision with its reason.
- **Known issues**: problems found in the design, or in the code it governs, that are neither fixed nor declined, one table row each:

  ```markdown
  | ID | Severity | Issue | Source | Since | Next |
  |----|----------|-------|--------|-------|------|
  | D003-K1 | major | Refresh retries break D005§queue-limits | P007 gate | 2026-10-21 | decide |
  ```

  Ids run `D003-K1`, `D003-K2`, ..., unique within the table. Severity is `blocker`, `major` or `minor`. Source is where it was found: a gate (`P007 gate`), a plan or one of its slices (`P007`, `P007 S3`), other work at the HEAD it ran on (`code review 3f9a1c2`, `docs step 3f9a1c2`, `L0 3f9a1c2`), an [as-built revision](as-built.md) of the commit it records (`as-built 3f9a1c2`), or a review finding (`R004-F2`). Since is the date it was recorded. Next is what it waits for: `decide` (the user's decision), `fix` (a code change), `L1` (a revision of this design) or `L2` (`/canon-design`). Rows are not spec: changing them bumps no `revision`, passes no gate and does not count as checking the design against its code. The change that resolves an issue deletes its row, or else the audit that finds it resolved. An issue the user declines is deleted too, with a Decision when the reason is lasting. Delete the section with its last row. A design cannot be archived while it lists any.
- **Status**: `draft` until the review gate passes (and, in L2, the user approves), then `accepted`. Once an implementation has landed, set `active` and `implemented` to the revision the code matches. Revising an active design keeps it `active`; its spec leads the code until the next implementation lands and raises `implemented`. Archive as `superseded` (successor in `refs`) or `retired` (feature removed). An [as-built revision](as-built.md) takes its status from its gate ([workflow.md](workflow.md#review-gate), step 6).
- **Split**: when a design outgrows one doc (`check` warns at 500 lines), run `new D <slug> --parent D00X` to create `D00XA`, `D00XB`, ... Move the sub-topic's spec, `owns` and `paths` into the sub-design; the parent keeps the overview and links to its children. Only one suffix level exists: a sub-design that outgrows itself becomes a new top-level design.

### Project overview (D000)

Every repository that follows canon has `designs/D000-project-overview.md`, titled `# D000: Project overview`, in the repo root's `docs/`, and no other docs root has a D000; `init` at the repo root creates it. It is a design like any other, with these rules:

- **Goals**: what the project is for, who uses it and what is out of scope.
- **Spec** holds the first four subsections below, in this order, and after them `### Standards`, left out while no design owns a standard that applies across modules:
  - `### Capabilities`: one row per capability the project offers its users or callers, at the grain of a feature list.
  - `### Modules`: one row per module. Path lists the module's directories relative to the project directory, comma-separated, each ending with `/`; `./` is the project directory. In a monorepo, each module's row links that module's designs.
  - `### Dependencies`: the allowed dependency directions between modules.
  - `### Glossary`: terms used across modules; a term one module uses belongs to the design that owns it.
  - `### Standards`: one row per standard that applies across modules, such as error handling, with the design that owns it: `| Standard | Design |`.

  ```markdown
  | Capability | Modules | Design |
  |---|---|---|
  | Token refresh | auth, gateway | [D003: auth](D003-auth.md) |
  | CSV export | export | none |

  | Module | Path | Purpose | Entry points | Design |
  |---|---|---|---|---|
  | auth | src/auth/ | Tokens and sessions | src/auth/index.ts | [D003: auth](D003-auth.md), [D005: sessions](D005-sessions.md) |
  ```

- A Design cell links every top-level design that owns the capability or standard, or that governs the module's code, or reads `none`. Rows name modules, capabilities and standards, never single docs: designs reach their sub-topics through their own links, and `docs/README.md` indexes every doc. Detail below the module level belongs to the module's designs.
- The tables map the project, its planned modules included while D000 is its first L2 design. The change that adds or removes a module, capability or standard, or creates, moves or archives a top-level design, updates their rows in the same commit ([docs step](workflow.md#docs-step)). Rows change no meaning, so they take no revision bump and no gate. Goals, Dependencies and Glossary are spec: adding a module, changing the dependency directions or changing a cross-module interface is L2.
- `audit` reports the code no design covers only under the module Paths, each file in the module with the longest Path that holds it, so tooling, CI and configuration outside every Path go uncounted. A module whose Path is `./` counts them too, so a project with tooling at its root gives its modules narrower Paths.
- `owns` includes `architecture`. `paths` lists only files that embody the architecture, such as dependency-boundary configuration and module wiring, never a directory or glob, which would make every file look governed; it is usually empty.
- In a project with code, D000 is written as an [as-built](as-built.md) design. In a project without code, it is the project's first L2 design, written with the `canon-design` skill.

## Plans (P)

Sections: Current state, Slices, Notes, Log.

- Create a plan only from an accepted or active design: `new P <slug> --from D00X`.
- **Current state** (top): current slice, next action, paused slices with their reasons. Update it at the end of every slice; a new session resumes from here.
- **Slices**: ordered `### S1: name` subsections. Each starts with a `Status:` line (`todo`, `in-progress`, `done`, `paused`), then a `Risk:` line naming the kinds when the slice involves complex logic, concurrency, performance, security or data migration (e.g. `Risk: concurrency, data migration`), then lists its changes and the test criteria that prove it done. Each criterion names its seam: the public interface, as the design's Spec defines it, where the test observes behavior. Seams in an accepted plan are agreed with the user; tests go only there.
- **Notes**: risks and constraints the implementer must keep in mind, findings about the plan the user left for later, and details the plan settled that its design leaves unstated, which the docs step writes into the design.
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

  Severity is `blocker`, `major` or `minor`. Disposition is `open`, `fixed <commit>`, `moved <ID>` (handed to the C, D, P or I that now tracks it; a design tracks it as a known issue) or `declined <reason>`.
- Archive as `closed` as soon as no finding is `open`; `check` blocks it before that.
- R docs cover code, modules or the whole repo. A periodic review of modules or the repo produces one R doc per run, with its reports in `reviews/R00X/`. Code review of a change produces no R doc: its deferred findings become known issues ([workflow.md](workflow.md#code-review)). Design and plan reviews happen in the review gate and produce no R doc.

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
