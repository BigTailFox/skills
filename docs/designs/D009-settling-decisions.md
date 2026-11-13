---
status: active
created: 2026-11-11
updated: 2026-11-13
revision: 2
modules: [canon]
summary: Settling open decisions with the user (canon-grill): triage before asking, open decisions kept in the doc, and small batches of related questions.
refs: [D000, D007, D008, D002, D003]
owns: [settling-decisions]
paths: [skills/execution/canon-grill/SKILL.md, skills/execution/canon-handoff/SKILL.md]
reviewed: 2
reviewers: [claude-opus-5.5]
implemented: 2
---

# D009: Settling decisions

## Goals

1. The user is asked only what only the user can decide: facts, what a design or standard settles, clear choices and questions evidence can answer never reach them.
2. The user gets at most three related questions at a time, each with a recommended answer they accept by saying "yes".
3. While a decision tree is walked, no decision lives only in the chat: an open decision is in a doc before it is asked, and its answer takes its place there as soon as it is settled.

Out of scope: the prototypes and research that triage routes questions to ([D008: Prototypes and research](D008-experiments.md)); design problems, which an answer may raise ([D007§design-problems: Design problems](D007-change-tiers.md#design-problems)).

## Spec

"The session" is the agent following the `canon-grill` skill.

### Triggers

`canon-grill` is an auto skill ([D000§glossary: Glossary](D000-project-overview.md#glossary)). Its description starts "Settles open decisions with the user. Use when only the user can settle a blocking decision, when walking a design or plan's decision tree, or to grill or stress-test a plan, design or idea." `canon-design`, `canon-plan`, `canon-implement`, `canon-tdd`, `canon-review` and the as-built steps send decisions here, naming the skill without restating how it asks, and a caller's own rule comes before this design's: the as-built steps put doubtful behavior to the user however plain it seems and give what the user leaves open their own known issue ([D002§as-built-revisions: As-built revisions](D002-overview-and-as-built.md#as-built-revisions)), and a `canon-implement` worker, which cannot reach the user, runs the triage itself and reports a question only the user can answer as blocked to its session.

### Triage

For each open decision, the session takes the first branch that applies:

1. **A fact** about the code, docs, tools or environment: the session finds it, dispatching a subagent for broad searches, new as [D003§launch: launch](D003-subagents.md#launch) states, and never asks the user.
2. **Settled by a design, plan or standard**: the session follows it and cites it, e.g. `D003§token-refresh`. When the work conflicts with a design's intent, the user decides ([D007§design-problems: Design problems](D007-change-tiers.md#design-problems)).
3. **One option is clearly right**, the alternatives plainly worse against the stated goals: the session decides and states the decision in one line where the user sees it.
4. **Evidence would settle it**: a logic, state-model, UI or performance question goes to `canon-prototype`, a question about an external system or library to `canon-research`; the session grills only about what the evidence leaves open.
5. **Otherwise**, a preference, priority, scope, trade-off between goals or design intent: the session asks.

### Questions

- The open decisions form a design tree: each decision branches into the decisions that hang off it. The frontier is every decision whose prerequisites are settled.
- The session asks in batches of at most three frontier questions. A batch starts with the question the most other open decisions depend on, then the most important; the others share its topic or bear on it, and none depends on another's answer. A question that needs a long explanation or is a major trade-off, such as one that changes a goal or picks the core approach, goes alone. An unrelated question waits for a later batch even when the batch has room. The session waits for the answers, records them, recomputes the frontier and asks the next batch.
- Each question has this form, worded so that "yes" accepts the recommendation, numbered across the session:

  ```
  **Q1 · <title>**: <the decision, its context, and the options when there are several>

  Recommended: <the answer and its one-line reason>
  ```

- A question may ask the user to pick several items of a list, such as which review findings to fix now.
- When a frontier question needs a fact, the session dispatches a subagent for it and asks the questions that do not depend on it meanwhile.

### Record

While walking a tree, the session writes every open decision it finds into the doc before asking it, and moves each answer, and each decision it settles itself by triage, to where it belongs the moment it is settled, deleting the open decision:

| Doc | Open decisions | Answers |
|---|---|---|
| A design being written or revised | a temporary `## Open questions` section | its Goals, Spec, Budgets or Decisions |
| A plan being written or revised | a temporary `## Open questions` section | its slices or Notes |
| A concept | its Open questions | its Ideas |

When a tree has no doc yet, as in a discussion before any work, the session first creates a concept (`canon.py new C <slug>`) and records there. A stress test of a design or plan keeps its open decisions in the same temporary section. A handoff leaves the open decisions where this table puts them (`canon-handoff`). A single blocking decision is recorded once answered: with a plan, in its Log with the reason; in L1 work without a plan, in the commit message; in L0 work, in the commit message when the choice would surprise a reader.

An answer that changes a design the session is neither writing nor revising is a design problem ([D007§design-problems: Design problems](D007-change-tiers.md#design-problems)). Outside as-built revisions, whose Decisions follow the as-built steps, a Decision line is added only when the choice is hard to reverse, surprising without context and the result of a real trade-off.

### Done

- Walking a tree (designing, planning, stress-testing): done when the frontier is empty, every branch settled or deferred by the user. A deferred branch stays in a concept's Open questions, becomes a known issue of a design with Source `grill <HEAD>` and Next `decide`, and a line in a plan's Notes; the temporary section, then empty, is deleted, so no review gate sees it. An answer that changes a design or plan under a stress test is a design problem or a plan revision, as for any other answer. The session confirms the shared understanding with the user before acting on it.
- A single blocking decision: done when it is answered and recorded.
- When the user is unavailable, the session follows the rule for paused slices in the `canon` workflow's Implementation section: it parks the decision, finishes the work that does not depend on it, and asks at the end.

## Decisions

- At most three questions per batch, by dependency then importance, on one topic and none depending on another, a major one alone: the user's attention is limited, related questions share their context, and an answer can reshape the questions after it (the user's decision, 2026-11-11).
- Open decisions are in the doc before they are asked, so a later session or a reviewer finds them and the user's earlier answers there, not in old chats (the user's decision, 2026-11-11; R003-F16).
- `canon-grill` is an auto skill, unlike the repository's manual default (82f113f, kept in 7bd6f5c; reason unknown, kept as found).
