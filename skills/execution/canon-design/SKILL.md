---
name: canon-design
description: Writes or revises a canon design, or a concept, by interviewing the user, then passes the review gate.
disable-model-invocation: true
---

# Design

Read the `canon` skill first. `canon.py` means the project copy named in `AGENTS.md`.

## 1. Frame

1. Gather the facts yourself: `canon.py find <words>`, `which` for the code involved, D000 (its rows, dependency directions and glossary), and the designs that own neighbouring topics.
2. Pick the target and state the tier:
   - The topic is in an existing design's `owns`, within one module: revise that design in place (L1; L2 when the revision rewrites its goals or core approach).
   - A new topic, module, cross-module interface or architecture change: a new design (L2).
   - A parent that has outgrown one doc: a sub-design with `--parent`, L1; the split only moves content, as the `canon` skill's tiers say. A spec change is a revision of its own: gate and commit the split first, then bump the `revision` of the doc that takes the change.
   - The idea still has questions the user cannot settle yet: a concept (`canon.py new C <slug>`). Its Open questions become the frontier of a later design session.
   - The change alters or extends existing behavior that no design states, as the `canon` skill's tiers define it: the target is the design whose `owns` holds that behavior's topic, else a new design, and step 5 gives it an as-built revision before the change's revision. The same holds when the user asks for a design of existing code with no change in view.
3. Confirm the target with the user, then create the doc (`canon.py new D <slug>`, with `--parent D00X` for a split, and bump the parent's `revision` once), or bump `revision` once when revising. The commit that adds a top-level design links it from D000's rows, as the `canon` skill's doc types define them.
4. Run `canon.py trace start design <D or C id> --tier <tier> --skill <skill> --model <model>`.
5. **Backfill.** When step 2 calls for an as-built revision, write this revision as one (the `canon` skill's `as-built.md`), whose steps take the place of the interview, pass it through [Gate](#3-gate) steps 1 to 3 at L1, and commit it as step 5 there says. Then bump `revision` again for the change and interview it; its gate is a new one, not a follow-up round, since its prompt differs from the as-built gate's, and runs at the change's tier with the as-built commit as `Changes since`. With no change in view, end after that commit with Gate's steps 6 and 7, and give no next command.

## 2. Interview

Walk the design tree with the `canon-grill` skill: goals, then interfaces, behavior and edge cases, budgets, and the decisions under each. While walking it:

- **Challenge terms against the glossary.** When the user uses a term that conflicts with D000's glossary or the design's own terms, call it out: "The glossary defines cancellation as X, but you seem to mean Y. Which is it?"
- **Sharpen fuzzy language.** Propose one precise term for a vague or overloaded one. Add a resolved module term to the design that owns it at once. A resolved cross-module term goes into D000's glossary, which is spec: bump D000's `revision` once; that revision is a follow-on target of the design's gate ([Gate](#3-gate)). A glossary entry defines a term; implementation detail belongs in the Spec.
- **Stress-test with scenarios.** Invent concrete cases that probe the boundaries between concepts and force precise answers.
- **Cross-check the code.** When the user states how something works, verify it; surface any contradiction.
- **Design interfaces** with the `canon-codebase-design` vocabulary. When an interface's shape is contested, use its design-it-twice pattern.
- **Settle known issues.** When revising a design, take each known issue the revision touches through the interview, and delete the rows the revision resolves.
- **Write as you go.** Record open decisions and answers as the `canon-grill` skill's Record says. Fill `summary`, `modules`, `owns`, `paths` and `refs` as they become clear.

The interview is done when the frontier is empty and every guidance comment is replaced.

## 3. Gate

1. Link a concept the design absorbed from the design, then run `canon.py check` and fix its errors.
2. Pass the review gate's steps 1 to 5 from the `canon` skill's workflow.
3. Set the status as the gate's step 6 says.
4. Set a concept designs have absorbed in full `adopted` with `canon.py status`; it stays in `concepts/`, as the `canon` skill's doc types say.
5. Commit the docs as the gate's step 7 says (Conventional Commits, `docs` type, `Refs:` trailer). In L2, ask the user to approve the gate's targets, naming `/canon-plan D00X`, or no command for a revision that needs no code change. On a yes, set `approved` on every target to its revision and its status as the workflow's Gate status says, and commit them.
6. Run the `canon-retro` skill's end check only if this work hit concrete friction in the development infrastructure or the agent workflow that could recur, such as a correction to how you worked, a finding a check could have caught, a command that would not run, a check that failed after you thought you were done, a search that took far too long, or a canon step that got in the way. Use only evidence already in context; do not search for reasons to run it. An L1 revision that carries on to implementation runs this after the docs step's commit instead, with the workflow's `implement` unit as `<parent>`.
7. Run `canon.py trace end <id> <outcome>`.

A revision this session makes after step 5's commit runs steps 1 to 5 again, step 2 passing a follow-up round through the gate's step 5, so an L2 revision asks for approval again; the `canon` skill's workflow (Follow-up round) names the revisions that pass a new gate instead, such as the change's revision in Frame step 5.

End with the command for the next phase: `/canon-plan D00X` when the change needs a plan (always in L2, unless it needs no code change). An L1 revision that needs no plan carries on in this session to implementation, code review and the docs step, as the `canon` skill's workflow says. A revision that needs no code change, such as D000 written before the project has code, gives no next command: it ends once its gate has passed and, in L2, the user has approved it, with `implemented` raised as the workflow's Gate status says. A split alone gives no next command.
