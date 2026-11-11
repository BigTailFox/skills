---
status: active
created: 2026-11-11
updated: 2026-11-11
revision: 1
modules: [canon]
summary: Settling open decisions with the user (canon-grill): triage before asking, rounds over the design tree's frontier, and where answers are recorded.
refs: [D000, D007, D008, D002]
owns: [settling-decisions]
paths: [skills/execution/canon-grill/SKILL.md]
reviewed: 1
reviewers: [claude-opus-5.5]
implemented: 1
---

# D009: Settling decisions

## Goals

1. The user is asked only what only the user can decide: facts, what a design or standard settles, clear choices and questions evidence can answer never reach them.
2. Each question comes with a recommended answer the user accepts by saying "yes".
3. Each answer is written into the doc being worked on as soon as it is settled, or into an L0 change's commit message when it would surprise a reader.

Out of scope: the prototypes and research that triage routes questions to ([D008: Prototypes and research](D008-experiments.md)); design problems, which an answer may raise ([D007§design-problems: Design problems](D007-change-tiers.md#design-problems)).

## Spec

"The session" is the agent following the `canon-grill` skill.

### Triggers

`canon-grill` is an auto skill ([D000§glossary: Glossary](D000-project-overview.md#glossary)). Its description's triggers: a decision blocks the work and only the user can make it; walking a design or plan's decision tree; the user asks to be grilled or to stress-test a plan, design or idea. `canon-design`, `canon-plan`, `canon-implement`, `canon-tdd`, `canon-review` and the as-built steps send decisions here, and a caller's own rule comes before triage: the as-built steps put doubtful behavior to the user however plain it seems ([D002§as-built-revisions: As-built revisions](D002-overview-and-as-built.md#as-built-revisions)), and a `canon-implement` worker, which cannot reach the user, runs the triage itself and reports a question only the user can answer as blocked to its session.

### Triage

For each open decision, the session takes the first branch that applies:

1. **A fact** about the code, docs, tools or environment: the session finds it, dispatching a subagent for broad searches, and never asks the user.
2. **Settled by a design, plan or standard**: the session follows it and cites it, e.g. `D003§token-refresh`. When the work conflicts with a design's intent, the user decides ([D007§design-problems: Design problems](D007-change-tiers.md#design-problems)).
3. **One option is clearly right**, the alternatives plainly worse against the stated goals: the session decides and states the decision in one line where the user sees it.
4. **Evidence would settle it**: a logic, state-model, UI or performance question goes to `canon-prototype`, a question about an external system or library to `canon-research`; the session grills only about what the evidence leaves open.
5. **Otherwise**, a preference, priority, scope, trade-off between goals or design intent: the session asks.

### Rounds

- The open decisions form a design tree: each decision branches into the decisions that hang off it. The frontier is every decision whose prerequisites are settled.
- The session asks the whole frontier in one round and waits for the answers. A question that depends on another question still open in the round belongs to a later round. After each round's answers it recomputes the frontier and asks the next round.
- Each question has this form, worded so that "yes" accepts the recommendation:

  ```
  **Q1 · <title>**: <the decision, its context, and the options when there are several>

  Recommended: <the answer and its one-line reason>
  ```

- When a frontier question needs a fact, the session dispatches a subagent for it and goes on; only the questions downstream of that fact wait.

### Record

Each answer goes where it belongs the moment it is settled, never in a batch at the end:

- writing a design: its Spec, Goals or Decisions; writing a concept: its Ideas or Open questions;
- writing a plan: its slices or Notes;
- implementing: the plan's Log, with the reason;
- with no doc (L0): the commit message, when the choice would surprise a reader.

An answer that changes a design the session is not writing is a design problem ([D007§design-problems: Design problems](D007-change-tiers.md#design-problems)). Outside as-built revisions, whose Decisions follow the as-built steps, a Decision line is added only when the choice is hard to reverse, surprising without context and the result of a real trade-off.

### Done

- Walking a tree (designing, planning, stress-testing): done when the frontier is empty, every branch settled or explicitly deferred to an Open question. The session confirms the shared understanding with the user before acting on it.
- A single blocking decision: done when it is answered and recorded.
- When the user is unavailable, the session follows the rule for paused slices in the `canon` workflow's Implementation section: it parks the decision, finishes the work that does not depend on it, and asks at the end.

## Decisions

- Questions go out a whole frontier per round (82f113f; reason unknown, kept as found).
- `canon-grill` is an auto skill, unlike the repository's manual default (82f113f, kept in 7bd6f5c; reason unknown, kept as found).

## Known issues

| ID | Severity | Issue | Source | Since | Next |
|----|----------|-------|--------|-------|------|
| D009-K1 | minor | Answers settled before any doc exists, as in a discussion before any work, are recorded nowhere and stay only in the chat | R003-F16 | 2026-11-11 | L1 |
| D009-K2 | minor | Record names no place for an answer in L1 work without a plan, nor a design's Budgets, which `canon-design` names; Done defers a branch to an Open question, which only concepts have | as-built cf7b053 | 2026-11-11 | L1 |
| D009-K3 | minor | The description's trigger "stress-test a plan, design or idea" falls past the 190 characters hosts keep | as-built cf7b053 | 2026-11-11 | fix |
