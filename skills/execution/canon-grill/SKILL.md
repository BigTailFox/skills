---
name: canon-grill
description: Settles open decisions with the user. Use when only the user can settle a blocking decision, when walking a design or plan's decision tree, or to grill or stress-test a plan, design or idea. First rules out what can be looked up, read from the designs, decided outright, or answered by a prototype or research, then asks the rest in small batches of related questions with recommended answers, keeping a decision tree's open decisions in the doc.
---

# Grill

Ask the user only what only the user can decide. Every question you ask costs their attention; every decision you silently assume costs rework.

A calling skill's own rule comes before this skill's: the `canon` skill's as-built steps, for one, put doubtful behavior to the user however plain it seems and give what the user leaves open a known issue with source `as-built <base>`.

## Triage

For each open decision, take the first branch that applies:

1. **A fact** about the code, docs, tools or environment: find it yourself, dispatching a subagent for broad searches. Never ask the user for something you could look up.
2. **Settled by a design, plan or standard**: follow it and cite it, e.g. `D003§token-refresh`. When the work conflicts with a design's intent, the user decides; never resolve it yourself.
3. **One option is clearly right**: the alternatives are plainly worse against the stated goals. Decide, and state the decision in one line where the user will see it.
4. **Evidence would settle it**: a logic, state-model, UI or performance question goes to the `canon-prototype` skill; a question about an external system or library goes to the `canon-research` skill. Grill only about what the evidence leaves open.
5. **Otherwise** (preference, priority, scope, a trade-off between goals, design intent): ask.

## Questions

Map the open decisions as a **design tree**: every decision branches into the decisions that hang off it. The **frontier** is every decision whose prerequisites are settled: the questions you can ask now without guessing at answers you haven't heard.

Ask in batches of at most three frontier questions, then wait for the answers:

- Start a batch with the question the most other open decisions depend on, then the most important.
- Add only questions on its topic or bearing on it, none depending on another's answer. An unrelated question waits for a later batch even when this one has room.
- A question that needs a long explanation or is a major trade-off, such as one that changes a goal or picks the core approach, goes alone.

Format each question, numbering them across the session:

```
**Q1 · <title>**: <the decision, its context, and the options when there are several>

Recommended: <your answer and its one-line reason>
```

Word each question so "yes" accepts your recommendation. A question may ask the user to pick several items of a list, such as which review findings to fix now. Each batch of answers reshapes the tree: record the answers, recompute the frontier and ask the next batch.

Facts are never the user's job. When a frontier question needs one, dispatch a subagent and keep going: only the questions downstream of that fact wait for it.

## Record

While walking a tree, write every open decision into the doc before you ask it, and move each answer, and each decision you settle yourself by triage, to where it belongs the moment it is settled, deleting the open decision:

| Doc | Open decisions | Answers |
|---|---|---|
| A design being written or revised | a temporary `## Open questions` section | Goals, Spec, Budgets or Decisions |
| A plan being written or revised | a temporary `## Open questions` section | slices or Notes |
| A concept | Open questions | Ideas |

When the tree has no doc yet, as in a discussion before any work, first create a concept (`canon.py new C <slug>`, with the `canon` skill's `scripts/canon.py`, as its Tool section says) and record there. A stress test of a design or plan keeps its open decisions in the same temporary section, and an answer that changes the doc is a design problem or a plan revision, as below.

Record a single blocking decision once it is answered: with a plan, in its Log with the reason; in L1 work without a plan, in the commit message; in L0 work, in the commit message when the choice would surprise a reader.

An answer that changes a design you are neither writing nor revising, the design you are stress-testing included, is a design problem: follow the `canon` skill's workflow (Design problems). One that changes a plan you are stress-testing makes a new plan revision with the `canon-plan` skill.

Outside an as-built revision, whose Decisions follow the `canon` skill's `as-built.md`, add a Decision line only when the choice is hard to reverse, surprising without context, and the result of a real trade-off.

## Done

- **Walking a tree** (designing, planning, stress-testing): done when the frontier is empty: every branch settled or deferred by the user. A deferred branch stays in a concept's Open questions, becomes a known issue of a design with Source `grill <HEAD commit>` and Next `decide`, or a line in a plan's Notes. Then delete the empty temporary section, so no review gate sees it. Confirm the shared understanding with the user before acting on it.
- **A single blocking decision**: done when it is answered and recorded.

When the user is unavailable, follow the `canon` skill's rule for paused slices: park the decision, finish the work that does not depend on it, and ask at the end.
