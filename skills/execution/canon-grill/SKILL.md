---
name: canon-grill
description: Settles open decisions with the user. Use when a decision blocks the work and only the user can make it, when walking a design or plan's decision tree, or when the user asks to be grilled or to stress-test a plan, design or idea. First rules out what can be looked up, read from the designs, decided outright, or answered by a prototype or research, then asks the rest in rounds of numbered questions with recommended answers.
---

# Grill

Ask the user only what only the user can decide. Every question you ask costs their attention; every decision you silently assume costs rework.

## Triage

For each open decision, take the first branch that applies:

1. **A fact** about the code, docs, tools or environment: find it yourself, dispatching a subagent for broad searches. Never ask the user for something you could look up.
2. **Settled by a design, plan or standard**: follow it and cite it, e.g. `D003§token-refresh`. When the work conflicts with a design's intent, the user decides; never resolve it yourself.
3. **One option is clearly right**: the alternatives are plainly worse against the stated goals. Decide, and state the decision in one line where the user will see it.
4. **Evidence would settle it**: a logic, state-model, UI or performance question goes to the `canon-prototype` skill; a question about an external system or library goes to the `canon-research` skill. Grill only about what the evidence leaves open.
5. **Otherwise** (preference, priority, scope, a trade-off between goals, design intent): ask.

## Rounds

Map the open decisions as a **design tree**: every decision branches into the decisions that hang off it. The **frontier** is every decision whose prerequisites are settled: the questions you can ask now without guessing at answers you haven't heard.

Ask the whole frontier in one round, then wait for the answers. A question that depends on another question still open in this round belongs to a later round. Format each question:

```
**Q1 · <title>**: <the decision, its context, and the options when there are several>

Recommended: <your answer and its one-line reason>
```

Word each question so "yes" accepts your recommendation. Each round of answers reshapes the tree: recompute the frontier and ask the next round.

Facts are never the user's job. When a frontier question needs one, dispatch a subagent and keep going: only the questions downstream of that fact wait for it.

## Record

Write each answer where it belongs the moment it is settled, never in a batch at the end:

- Writing a design: its Spec, Goals or Decisions. Writing a concept: Ideas or Open questions.
- Writing a plan: its slices or Notes.
- Implementing: the plan's Log, with the reason.
- No doc (L0): the commit message, when the choice would surprise a reader.

An answer that changes a design you are not writing is a design problem: follow the `canon` skill's workflow (Design problems).

A Decision line is worth adding only when the choice is hard to reverse, surprising without context, and the result of a real trade-off.

## Done

- **Walking a tree** (designing, planning, stress-testing): done when the frontier is empty: every branch settled or explicitly deferred to an Open question. Confirm the shared understanding with the user before acting on it.
- **A single blocking decision**: done when it is answered and recorded.

When the user is unavailable, follow the `canon` skill's rule for paused slices: park the decision, finish the work that does not depend on it, and ask at the end.
