---
status: active
created: 2026-11-10
updated: 2026-11-11
revision: 2
modules: [canon]
summary: Change tiers L0, L1 and L2 and their flows, design problems, and the review gate's steps, reviewer prompt, merge rules, confirmation round and status.
refs: [D001, D002, D003, D006, R003]
owns: [change-tiers, review-gate, design-problems]
paths: [skills/governance/canon/SKILL.md, skills/governance/canon/workflow.md, skills/execution/canon-design/SKILL.md, skills/execution/canon-implement/SKILL.md]
reviewed: 2
reviewers: [claude-opus-5.5]
implemented: 2
---

# D007: Change tiers and the review gate

## Goals

1. Every change states one of three tiers when it starts, and the tier sets which design revisions, review gates and user approvals the change needs.
2. No design or plan revision is accepted or implemented before blind reviewers, judging it only from the repository, have reviewed it at its tier, and each of their findings has been fixed, declined with a reason or put to the user.
3. A flaw found in a design while working from it reaches the user with a proposed fix and its tier; only the user's decision changes what the design intends, and work that does not depend on the flaw carries on.

## Spec

These are the rules an agent following the `canon` skill obeys in the Workflow, Rules and Reading docs sections of its `SKILL.md` and in the Flows, Design problems and Review gate sections of its `workflow.md`. Code review, the docs step, plans and implementation, which `workflow.md` also states, are outside this design.

### Change tiers

Every change has a tier:

- **L0**: changes no spec in any design: bug fixes that restore specified behavior, refactors, dependency bumps, test and tooling changes. The agent implements it, keeps docs factually true and commits.
- **L1**: changes or extends specs inside the owned topics of one existing design, within one module; or multi-step work under an existing design that needs a plan. The agent revises the design in place, bumping `revision` once, in the current session or in a `/canon-design` session the user starts, which the agent offers when the revision needs an interview of the user; it passes the review gate, a step that work changing no spec skips, then implements.
- **L2**: a new topic with no owning design, a new module, a change to a cross-module interface or the architecture (adding, removing or merging a module, or changing which modules depend on which), a revision that rewrites an existing design's goals or core approach, or the user asks for it. The design and the plan each pass the review gate and each needs the user's approval, which starting the next phase gives.

Each tier runs this flow; the parenthesized concept is optional, and of L1's two bracketed parts at least one runs, the plan when the work needs one:

```text
L2: (concept) → design draft → review gate → user approval, accepted → plan draft → review gate → user approval, accepted → implement → code review → docs step → commit
L1: [revise the design in place (revision +1) → review gate] → [plan → review gate] → implement → code review → docs step → commit
L0: implement → code review → docs step → commit
```

### Choosing a tier

- The agent states the tier when starting a change and picks the higher one when unsure.
- When a change may alter behavior or standards a design specifies, the agent first runs `canon.py which <file>` and reads the governing sections with `canon.py show D00X#slug`.
- Behavior no design states, and the tier of a change to it, follow [D002§backfill: backfill](D002-overview-and-as-built.md#backfill).
- Splitting a design into sub-designs is L1 when the split only moves what [D006§doc-types: doc types](D006-doc-model.md#doc-types) moves with a topic, without changing what it states. Though it changes no spec, the parent's new revision and the sub-design each pass the review gate at L1, so reviewers confirm nothing was lost, and take their status as [Gate status](#gate-status) states. A split that also changes spec takes the tier of that change.
- A commit that touches a design's `paths`, in any tier, names the designs it was checked against in a `Refs:` trailer (`affected` lists them); `audit` treats commits without one as unchecked.

### Phases

- Design, plan and implementation are separate phases, and each can start in a fresh session because the docs carry the state.
- A phase ends by giving the user the command that starts the next one, such as `/canon-plan D012`; the user runs it in this session or a new one. The canon skills write such commands in that form, and the agent gives each in the host's form, such as `$canon-plan D012` in Codex.
- L1 work is the exception: the session that revises the design, including one given L1 work through `canon-implement`, carries on to implementation after the gate, or gives `/canon-plan D012` when the work needs a plan. So does a [design problem](#design-problems) found while planning or implementing, unless its fix is L2.

### Design problems

A design problem is a flaw found in an accepted or active design while working from it: the design contradicts itself or another design, no implementation can satisfy it, the work would have to change what it states, or it lacks a decision only its intent can settle. Planning, review gates, implementation and code review can all find one, in the design the work builds on or in passing in another. The agent reads the known issues of each design it works from (`show D00X#known-issues`); one the work depends on is a design problem unless the work fixes it.

The session that finds a design problem takes these steps, wherever it is found:

1. Confirm it against the design and the code; a finding the reviewed target can fix within the design is an ordinary finding. Work that depends on the flawed part waits for the user's decision and any fix it brings, and the rest carries on, its gate and commit included. When unsure whether the work depends on it, treat it as dependent.
2. Tell the user, with the proposed fix and its tier. A review gate or code review finishes the review first and reports it with the review's other findings: a code review in its report, a gate when it merges its findings, before any confirmation round. The agent never changes the design's intent itself, even when it is plainly wrong.
3. Once the user decides on a change, revise the design in place in the current session, without the `canon-design` skill: bump `revision` and pass the review gate at L1. A design another session is revising gets a known issue instead, with the work as Source and Next `L1`, so the request is in the design, never only in a handoff file or a message. A fix the tiers put at L2, such as a rewrite of the design's goals or core approach, goes through `/canon-design D00X`: the agent gives the user the command and pauses the work that depends on it.
4. When a plan builds on the design, check its slices against the design's diff, move its `based_on` to the new revision and log why. In a plan's review gate, this comes before the confirmation round, so the reviewers confirm against the revised design.
5. A problem this session does not fix, because the user deferred it, its fix is L2 or the user has not decided, becomes a known issue of the design. One the user rejects leaves no row, only a Decision when the reason is lasting.

A detail the design leaves unstated, which the plan can settle within the design's goals and spec, is not a design problem: the plan settles it and lists it in its Notes for the docs step to write into the design. Changing what the design states never counts as such a detail.

An L0 change that turns out to alter a spec takes the same steps; once the design revision passes its gate, the change continues as L1 work.

### Review gate

Every design or plan revision passes the review gate before it is accepted, and every revision of an active design passes it before implementation: a revision is accepted or implemented only once `reviewed` equals `revision`, and `check` reports a pending one as [D006§frontmatter: frontmatter](D006-doc-model.md#frontmatter) states. The gate runs at the revision's tier, even within work of a lower tier, such as an L1 revision made while implementing an L0 change.

Besides the tiers' flows and step 3 of [Design problems](#design-problems), `workflow.md` sends these revisions through the gate: a new plan revision, made with the `canon-plan` skill, when implementation meets a plan problem that needs a decision or whose fix would change what the plan delivers, before the slices resume; a change to a spec's meaning the user decides on in the docs step; and a revision the user chose for a design problem a code review found, which passes before that review closes.

The gate's reviewers:

- **Same-model reviewer**: a subagent on the author's model and effort, in every gate.
- **Cross-family reviewer**: a model of another family than the session's, launched in the first round only; in the confirmation round it confirms the fixes of the findings it raised ([D003§resuming-and-replacing: resuming and replacing](D003-subagents.md#resuming-and-replacing)). Required for L2; in L1, only when the user asks for it.

The steps, which `as-built.md`, `doc-types.md` and [D001§call-sites: call sites](D001-skill-telemetry.md#call-sites) cite by number:

1. Run `canon.py check` and fix its errors, so reviewers spend no effort on formatting. For a revision of an accepted or active design, or of an accepted or in-progress plan, it warns that the revision is not reviewed until step 5.
2. Start the gate's trace unit, then launch the first-round reviewers in parallel, with the `canon-blind-review` skill when it is installed. Each is a blind reviewer: a fresh subagent that carries nothing from the current conversation, never a fork of the session, given only the [reviewer prompt](#reviewer-prompt). A cross-family reviewer that cannot run falls back to the user as [D003§reviewers: reviewers](D003-subagents.md#reviewers) states.
3. Merge the findings as [Merging findings](#merging-findings) states.
4. Run the [confirmation round](#confirmation-round) when it is due.
5. Set `reviewed: <revision>` and `reviewers: [<model ids>]`, using `manual:<model>` for a review the user ran, and delete an as-built revision's `as_built` line ([D002§as-built-revisions: as-built revisions](D002-overview-and-as-built.md#as-built-revisions)). In L2, report the accepted, declined and escalated findings and the reviewer models, including any fallback, and get the user's answer on each escalated finding. Then end the gate's trace unit.
6. Set the status as [Gate status](#gate-status) states.

### Reviewer prompt

The gate fills the placeholders of this prompt and passes nothing else; `canon-blind-review` takes it from `workflow.md` for every gate.

```text
You are reviewing a {design | plan} in this repository with no prior context. Judge it only from the repository.

Target: {path}
Changes since: {commit} (review what changed; read the rest for context)

Read the target, the docs it links to, and the code it governs. Do not read `.canon/`. Do not modify any file or write scratch files; read long command output in parts instead. You may run the canon.py that `AGENTS.md` names with `show`, `find`, `which`, `affected`, or `check` without `--fix`, which only read; when the host blocks one, read the files instead.

Assess:
- Correctness and feasibility against {the current code | the code it records}.
- Completeness: a fresh agent could {implement it | change the code it governs} from this document and its links alone.
- Consistency: no conflict with other designs; each standard is stated once, in the design that owns it, and linked elsewhere; a design other than D000 states its own scope, not what other designs own.
- Simplicity: no complexity beyond the goals. A feature's own input validation, permissions and data protection are part of it; security hardening beyond that only where the design or project requires it.
- Plans only: slices are ordered by dependency, independently verifiable, and each has concrete test criteria.
Formatting, frontmatter and wording style are out of scope.
Report a problem a design lists as a known issue only when it is worse than the entry says, naming the entry.

Report every blocker and major finding and at most 10 minor ones, most severe first, each as:

### F1 [blocker | major | minor] {location, e.g. D003§token-refresh}
Problem: ...
Evidence: ...
Suggestion: ...

Keep each finding as short as it can be while a reader can understand and verify it without redoing your review.
Then list Questions: anything you could not understand from the repository alone.
Write the report in {documentation language}, even where your instructions set another reply language.
End with one line: Verdict: approve | revise
```

- The `Changes since` line is only for revisions of an existing doc.
- In Correctness and Completeness, a revision other than an as-built one takes the first choice. For an as-built revision, the prompt gains an `As-built:` line after `Changes since` and an Assess item after `Plans only`, and takes the second choices ([D002§as-built-revisions: as-built revisions](D002-overview-and-as-built.md#as-built-revisions)).
- `{documentation language}` is the language the project's docs are written in.
- The report the prompt asks for is the one [D003§input-and-reports: input and reports](D003-subagents.md#input-and-reports) states for every gate and blind review.

### Merging findings

- Each finding is accepted and fixed, declined with a one-line reason for the user, or escalated to the user. A finding the user then leaves for later becomes a known issue of a target design, or a line in a target plan's Notes.
- A finding about a design other than the target, such as a plan finding about its design, follows [Design problems](#design-problems).
- A finding raised by both reviewers is accepted unless it is clearly wrong.
- Declined findings stay out of the doc. A Decision records one, in the design that owns the topic, only when its rationale has lasting value.

### Confirmation round

- It runs only when accepted blocker or major findings were fixed: the reviewers that raised them confirm the fixes in one more round, as the `canon-blind-review` skill's confirmation describes ([D003§resuming-and-replacing: resuming and replacing](D003-subagents.md#resuming-and-replacing)).
- Blockers still open after it go to the user; there is no third round.

### Gate status

- L1: a draft becomes `accepted`.
- L2: the user approves, at this step or by starting the next phase on the doc; a draft becomes `accepted` at that point, and until then stays a `draft` whose `reviewed` equals `revision`.
- A revised design that is `accepted` or `active`, and a revised plan that is `accepted` or `in-progress`, keeps its status, in both tiers.
- After a split's gate, the sub-design takes its parent's status; when the parent is `active`, the sub-design gets `implemented: 1`, and the parent's `implemented` rises to its new revision when it equaled the previous one.
- An as-built revision takes its status after the gate as [D002§as-built-revisions: as-built revisions](D002-overview-and-as-built.md#as-built-revisions) states.

## Decisions

- The user can approve an L2 design or plan by starting the next phase on it, and until approved it stays a `draft` whose `reviewed` equals `revision` (6fc017c; reason unknown, kept as found).
- A revision that rewrites a design's goals or core approach is L2, even inside one design's owned topics (6fc017c; reason unknown, kept as found).
- A change to the architecture adds, removes or merges a module, or changes which modules depend on which; relaxing a dependency rule inside one module, as D000 revision 2 did, is L1 (R002-F5; the user's decision, 2026-11-11).
- L2 gates require a cross-family reviewer, and an L1 gate runs one only when the user asks (2c3bc26; the user's decision, 2026-11-11). In one project's gates, each family caught majors the other passed ([R003§works-well: works well](../reviews/R003-silk-design-phase.md#works-well)).
- The prompt asks for every blocker and major finding and at most 10 minor ones: a cap of 10 findings in all could cut real problems in a large change (b387f60).
- The prompt sets no word cap and asks for each finding as short as a reader can still verify: a cap limits how many findings fit and could force out a blocker or major one, and a report in Chinese cannot be counted in words (869e499).
- A gate has at most one confirmation round, and blockers still open after it go to the user (2c3bc26, 6fc017c; reason unknown, kept as found).
- An L1 revision, a design problem's included, runs in the current session without `canon-design`, a manual skill an agent cannot invoke, unless the user starts a `/canon-design` session for it; an L0 change that alters a spec takes the design-problem steps instead of stopping (9b007fb, 392f4a9, 1c7c1f0; R003-F40, the user's decision, 2026-11-11).

## Known issues

| ID | Severity | Issue | Source | Since | Next |
|----|----------|-------|--------|-------|------|
| D007-K4 | major | The gate runs per doc revision, so one change across several designs takes a gate and reviewers per doc | R003-F1 | 2026-11-10 | L2 |
| D007-K5 | major | No rule covers edits after a gate passes, so sessions rerun whole gates or commit edits no reviewer saw | R003-F2 | 2026-11-10 | L2 |
| D007-K6 | minor | Which commit fills `Changes since` for a revision other than the one after an as-built revision is unstated, and a revision that passed its gate but was not committed leaves none | R003-F6 | 2026-11-10 | L2 |
| D007-K7 | minor | The tier of changes to C, R and E docs alone, and how a D000 without code is planned and marked, are unstated | R003-F21 | 2026-11-10 | L2 |
| D007-K8 | minor | Revision and approval bookkeeping around a gate, such as the L2 approval of a revised active design, leaves no record; the user wants it designed with D006-K10 | R003-F24 | 2026-11-10 | L2 |
| D007-K12 | minor | Whether a gate drops the prompt's Assess items for other targets, `Plans only` for a design and `As-built revisions only` for another revision, is unstated | D007 gate | 2026-11-10 | L1 |
| D007-K13 | minor | After a split from an active parent whose `implemented` lags its previous revision, Gate status still gives the sub-design `implemented: 1`, though the moved spec may lead the code | D007 gate | 2026-11-11 | L1 |
