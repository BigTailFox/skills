# As-built revisions

An as-built revision records behavior the code already has, at one commit, and specifies no change to it. It is the first revision of a new design, or a revision that adds existing behavior to the design whose `owns` holds its topic. Write one:

- in `canon-init`'s setup, for D000 and for adopted designs that describe existing code;
- before a change alters or extends behavior no design states, as the [tiers](SKILL.md#workflow) require;
- when the user asks for a design of existing code.

## `as_built`

While the revision awaits its gate, its frontmatter holds `as_built: <commit>`: the [base](#steps) as a hex commit name, full or abbreviated to at least 7 digits. Never write a ref such as `HEAD` or a branch name: it moves once the change commits. Outside Git, and before the first commit, write `as_built: worktree`: the revision records the files as they are and passes its gate before any of them change. The gate fills its reviewer prompt from the field, and a resumed session or a replay of the gate finds the base there; the gate deletes it when it sets `reviewed` ([workflow.md](workflow.md#review-gate), step 5).

## Steps

1. **Base**: the commit the change starts from: the commit the session started at, a plan's `Started at`, or for a code review the merge base it diffs against; HEAD when no change follows. Once the work tree or HEAD has moved past the base, read files as `git show <base>:<path>`; never record code the change already altered.
2. **Scope**: the topic the change touches, as one whole interface or capability, neither the whole module nor only the lines to change. It goes into the design whose `owns` holds the topic, else into a new design. A new design's `owns` and `paths` cover exactly what it records, `paths` listing the files that implement it and their tests; a revision adds what it records to them.
3. **Level**: what callers rely on, meaning what another module, a user or an external system can observe through an interface: results, errors, side effects, config keys and data formats, given as code. Private structure stays out.
4. **Intent**: evidence, strongest first, is tests, user-facing docs, commit messages, pull requests and issues, then the code. Intent chooses what to write and at which level; what the revision states still holds for the code at the base.
5. **Doubtful behavior**, behavior that looks unintended, is the user's to judge however plain it seems: put it to the user in rounds with the `canon-grill` skill, which looks every fact up itself. Intended behavior goes into the Spec. A defect puts the correct behavior in the Spec and adds a [known issue](doc-types.md#designs-d) with next `fix` stating what the code does instead; like a defect that code review defers, the issue does not lower `implemented`, and its fix is L0, since it restores specified behavior. Behavior the user cannot judge stays in the Spec as it is, with a known issue with next `decide`. Both issues have the source `as-built <base>`. Settle what the change depends on before the change's own revision.
6. **Decisions**: a choice that is hard to reverse and surprising without context gets a Decision line with its source, or with `reason unknown, kept as found`.
7. **No improvements**: an idea found while reading becomes a known issue with next `fix`, `L1` or `L2`, or an Idea in the module's backlog concept.

## Gate and commit

The revision passes the review gate at L1, as the [tiers](SKILL.md#workflow) say, with the reviewer prompt's as-built lines ([workflow.md](workflow.md#reviewer-prompt)). It needs no plan. Commit it on its own, as a `docs` commit whose `Refs:` trailer names the design, before the change's own revision, whose gate gives that commit as `Changes since`. Outside Git, start the change's own revision once this gate has passed.
