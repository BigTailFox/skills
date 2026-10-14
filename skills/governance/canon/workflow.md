# Workflow

## Tiers

State the tier when starting a change; pick the higher one when unsure.

- **L0**: changes no spec in any design. Bug fixes that restore specified behavior, refactors, dependency bumps, test and tooling changes.
- **L1**: changes or extends specs inside the owned topics of one existing design, within one module; or multi-step work under an existing design that needs a plan.
- **L2**: a new topic with no owning design, a new module, a change to a cross-module interface or the architecture, a revision that rewrites an existing design's goals or core approach, or the user asks for it.

## Flows

- **L2**: (concept) → design draft → review gate → user approval, `accepted` → plan draft → review gate → user approval, `accepted` → implement → code review → docs step → commit.
- **L1**: revise the design in place (revision +1) → review gate → [plan → review gate] → implement → code review → docs step → commit.
- **L0**: implement → code review → docs step → commit.

Design, plan and implementation are separate phases, and each can start in a fresh session because the docs carry the state. A phase ends by giving the user the command that starts the next one, e.g. `/canon-plan D012`; the user runs it in this session or a new one.

## Implementation

Implement slice by slice. After each slice, set its `Status:` and update the plan's Current state and Log.

When the implementation cannot follow the plan or the design:

- **Plan problem with one clear fix**: edit the plan and continue without asking; log the deviation and the decision. When the plan problem needs a decision, mark the slice `paused` and ask the user.
- **Design problem**: no implementation can satisfy the design, or the design contradicts itself. Mark the slice `paused` and tell the user. Never change the design's intent yourself, even when it is plainly wrong.
- While a slice is paused for a design problem or a pending decision, finish the slices that do not depend on it, then report every paused slice with its problem.

A design changes only after the user decides, through the tier's flow (revision bump and review gate).

## Review gate

Every design or plan revision passes this gate before it is accepted, and every revision of an active design passes it before implementation.

1. Run `canon.py check` and fix its errors, so reviewers spend no effort on formatting. It warns that the revision is not reviewed until step 5.
2. Launch the first-round reviewers in parallel, with the `canon-blind-review` skill when it is installed. A blind reviewer is a fresh subagent that carries nothing from the current conversation: never fork the session, and pass only the reviewer prompt below.
   - **A1**: same model as the author. Default reasoning effort for L1, highest available for L2.
   - **A2**: a different model family at its highest reasoning effort, in the first round only. Required for L2, optional for L1. If the host cannot launch another family, give the user the filled reviewer prompt to run in another tool, and wait for the result.
3. Merge the findings. Accept and fix, decline with a one-line reason for the user, or escalate to the user. A finding raised by both reviewers is accepted unless it is clearly wrong. Declined findings stay out of the doc; record a Decision only when its rationale has lasting value.
4. When accepted blocker or major findings were fixed, the reviewers that raised them confirm the fixes in one more round, as the `canon-blind-review` skill's confirmation describes. Blockers still open after it go to the user; there is no third round.
5. Set `reviewed: <revision>` and `reviewers: [<model ids>]`, using `manual:<model>` for user-run reviews.
6. Status. L1: a draft becomes `accepted`. L2: report the accepted, declined and escalated findings and the reviewer models, including any fallback, and get the user's answer on each escalated finding. The user then approves, here or by starting the next phase on the doc; a draft becomes `accepted` at that point and until then stays a `draft` whose `reviewed` equals `revision`. A revised active design stays `active` in both tiers.

### Reviewer prompt

Fill the placeholders and pass nothing else. The `Changes since` line is only for revisions of an existing doc.

```text
You are reviewing a {design | plan} in this repository with no prior context. Judge it only from the repository.

Target: {path}
Changes since: {commit} (review what changed; read the rest for context)

Read the target, the docs it links to, and the code it governs. Do not read `.canon/`. Do not modify any file.

Assess:
- Correctness and feasibility against the current code.
- Completeness: a fresh agent could implement it from this document and its links alone.
- Consistency: no conflict with other designs; each standard is stated once, in the design that owns it, and linked elsewhere.
- Simplicity: no complexity beyond the goals. A feature's own input validation, permissions and data protection are part of it; security hardening beyond that only where the design or project requires it.
- Plans only: slices are ordered by dependency, independently verifiable, and each has concrete test criteria.
Formatting, frontmatter and wording style are out of scope.

Report at most 10 findings, most severe first, each as:

### F1 [blocker | major | minor] {location, e.g. D003§token-refresh}
Problem: ...
Evidence: ...
Suggestion: ...

Then list Questions: anything you could not understand from the repository alone.
End with one line: Verdict: approve | revise
```

## Code review

Review every change before the docs step, with the `canon-code-review` skill when it is installed: against the governing designs and plan (spec) and the standards their owning designs state. L2 changes add a reviewer from another model family in the first round. Fix findings in the change; when blocker or major fixes changed it, the reviewers that raised them confirm the fixes once. A finding deferred to later work goes into an R doc with disposition `open` so it stays tracked; code review produces no R doc otherwise.

## Docs step

Before committing, after implementation and code review. Scope: the uncommitted changes, or a branch with `--base <ref>`; after per-slice commits, the plan's `Started at` commit is the base.

1. Run `canon.py affected [--base <ref>]`. For each listed design, compare the diff with its governing sections (`show D00X#slug`):
   - The change implements an accepted spec or plan: write into the spec the details the code settled within its accepted intent; they need no revision bump. Once a revision's implementation has fully landed, set `implemented` to that revision and the design `active`.
   - The code contradicts the spec: report it to the user instead of rewriting the spec.
   - The user decided to change the spec's meaning: bump `revision` and pass the review gate.
2. For changed files where `which` prints `no design`, add them to the `paths` of the design that owns the area. If no design owns it, tell the user; a new design is L2.
3. For each listed plan, update slice statuses, Current state and Log. Archive the plan as `done` when every slice is `done`; report paused slices to the user.
4. Set the dispositions of review findings the change fixed. Archive what is finished: reviews with no open finding (`closed`), fixed investigations (`resolved`), experiments whose conclusion is absorbed into a design (`concluded`).
5. Search READMEs, guides and `AGENTS.md` for names the change renamed or removed (commands, flags, config keys, paths) and fix them.
6. Run `canon.py check --fix` until it reports no errors.
7. When this change archived a plan, run `canon.py audit`. If it reports a due review, end your report with one line suggesting the user run a codebase review (the `canon-review` skill). Never start a review yourself.
8. Commit with Conventional Commits; L1 and L2 commits add a trailer naming the docs, e.g. `Refs: D003, P012`.

## Maintenance

Run `canon.py audit` before large tasks and periodically. Refresh designs with many code commits since their last update, finish or archive idle docs, and tell the user when a review (R) is due.
