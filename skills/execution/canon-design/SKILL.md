---
name: canon-design
description: Writes or revises a canon design, or a concept, by interviewing the user, then passes the review gate.
disable-model-invocation: true
---

# Design

Read the `canon` skill first. `canon.py` means the project copy named in `AGENTS.md`.

## 1. Frame

1. Gather the facts yourself: `canon.py find <words>`, `which` for the code involved, the architecture design (module map, dependency directions, glossary), and the designs that own neighbouring topics.
2. Pick the target and state the tier:
   - The topic is in an existing design's `owns`, within one module: revise that design in place (L1; L2 when the revision rewrites its goals or core approach).
   - A new topic, module, cross-module interface or architecture change: a new design (L2), or a sub-design with `--parent` when the parent has outgrown one doc.
   - The idea still has questions the user cannot settle yet: a concept (`canon.py new C <slug>`). Its Open questions become the frontier of a later design session.
3. Confirm the target with the user, then create the doc (`canon.py new D <slug>`), or bump `revision` once when revising.

## 2. Interview

Walk the design tree with the `canon-grill` skill: goals, then interfaces, behavior and edge cases, budgets, and the decisions under each. While walking it:

- **Challenge terms against the glossary.** When the user uses a term that conflicts with the architecture design's glossary or the design's own terms, call it out: "The glossary defines cancellation as X, but you seem to mean Y. Which is it?"
- **Sharpen fuzzy language.** Propose one precise term for a vague or overloaded one. Add a resolved cross-module term to the architecture design's glossary and a module term to the design that owns it, at once. A glossary entry defines a term; implementation detail belongs in the Spec.
- **Stress-test with scenarios.** Invent concrete cases that probe the boundaries between concepts and force precise answers.
- **Cross-check the code.** When the user states how something works, verify it; surface any contradiction.
- **Design interfaces** with the `canon-codebase-design` vocabulary. When an interface's shape is contested, use its design-it-twice pattern.
- **Write as you go.** Put each settled decision into Goals, Spec, Budgets or Decisions the moment it is settled. Fill `summary`, `modules`, `owns`, `paths` and `refs` as they become clear.

The interview is done when the frontier is empty and every guidance comment is replaced.

## 3. Gate

1. Run `canon.py check` and fix its errors.
2. Pass the review gate from the `canon` skill's workflow.
3. Set the status as the gate's last step describes.
4. Archive a concept the design absorbed as `adopted`, linked from the design.
5. Commit the docs (Conventional Commits, `docs` type, `Refs:` trailer).
6. Run the `canon-retro` skill's end check only if this work hit concrete friction in the development infrastructure or the agent workflow that could recur, such as a correction to how you worked, a finding a check could have caught, a command that would not run, a check that failed after you thought you were done, a search that took far too long, or a canon step that got in the way. Use only evidence already in context; do not search for reasons to run it.

End with the command for the next phase: `/canon-plan D00X` when the change needs a plan (always in L2), otherwise `/canon-implement D00X`. In L2, the user starting it approves the design.
