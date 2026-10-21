# Workflow

## Flows

The tiers are defined in [SKILL.md](SKILL.md#workflow).

- **L2**: (concept) → design draft → review gate → user approval, `accepted` → plan draft → review gate → user approval, `accepted` → implement → code review → docs step → commit.
- **L1**: revise the design in place (revision +1) → review gate → [plan → review gate] → implement → code review → docs step → commit.
- **L0**: implement → code review → docs step → commit.

Design, plan and implementation are separate phases, and each can start in a fresh session because the docs carry the state. A phase ends by giving the user the command that starts the next one, e.g. `/canon-plan D012`; the user runs it in this session or a new one. A [design problem](#design-problems) found while planning or implementing is the exception: that session revises the design and carries on, unless the fix is L2.

## Design problems

A design problem is a flaw found in an accepted or active design while working from it: the design contradicts itself or another design, no implementation can satisfy it, the work would have to change what it states, or it lacks a decision only its intent can settle. Planning, review gates, implementation and code review can all find one. Wherever it is found:

1. Tell the user, with the fix you would propose. Never change the design's intent yourself, even when it is plainly wrong.
2. Once the user decides on a change, revise the design in place in the current session: bump `revision` and pass the review gate at L1. A fix the tiers put at L2, such as a rewrite of the design's goals or core approach, goes through `/canon-design D00X`: give the user the command and pause the work that depends on it.
3. When a plan builds on the design, check its slices against the design's diff, move its `based_on` to the new revision and log why. In a plan's review gate, do this before the confirmation round, so the reviewers confirm against the revised design.

A detail the design leaves unstated, which the plan can settle within the design's goals and spec, is not a design problem: the plan settles it and lists it in its Notes for the docs step to write into the design. Changing what the design states never counts as such a detail.

An L0 change that turns out to alter a spec takes the same steps; once the design revision passes its gate, the change continues as L1 work.

## Implementation

Implement slice by slice, each slice in a fresh worker subagent (the `canon-implement` skill). Only the orchestrating session edits the plan and commits: after each slice it sets the slice's `Status:` and updates the plan's Current state and Log.

When the implementation cannot follow the plan or the design:

- **Plan problem with one clear fix**: edit the plan and continue without asking; log the deviation and the decision. Such a fix keeps the plan's `revision`. When the plan problem needs a decision, or its fix would change what the plan delivers, mark the slice `paused` and ask the user: that is a new plan revision, made with the `canon-plan` skill, and it passes the review gate before the slices resume.
- **[Design problem](#design-problems)**: mark the slice `paused` and tell the user.
- While a slice is paused for a design problem or a pending decision, finish the slices that do not depend on it, then report every paused slice with its problem.

## Review gate

Every design or plan revision passes this gate before it is accepted, and every revision of an active design passes it before implementation.

1. Run `canon.py check` and fix its errors, so reviewers spend no effort on formatting. It warns that the revision is not reviewed until step 5.
2. Run `canon.py trace start gate <doc id> --tier <tier> --skill <skill> --model <model> [--parent <parent>] [--base <Changes since commit>]`. Launch the first-round reviewers in parallel, with the `canon-blind-review` skill when it is installed. A blind reviewer is a fresh subagent that carries nothing from the current conversation: never fork the session, and pass only the reviewer prompt below.
   - **Same-model reviewer**: a subagent on the author's model and effort (Subagents below).
   - **Cross-family reviewer**: a model of another family than the session's, run as the reviewer file says (Subagents below), in the first round only. Required for L2, optional for L1. When the file names no such reviewer, or the run fails, give the user the filled reviewer prompt to run in another tool, and wait for the result.
3. Merge the findings. Accept and fix, decline with a one-line reason for the user, or escalate to the user. A finding about a design other than the target, such as a plan finding about its design, follows [Design problems](#design-problems). A finding raised by both reviewers is accepted unless it is clearly wrong. Declined findings stay out of the doc; record a Decision, in the design that owns the topic, only when its rationale has lasting value.
4. When accepted blocker or major findings were fixed, the reviewers that raised them confirm the fixes in one more round, as the `canon-blind-review` skill's confirmation describes. Blockers still open after it go to the user; there is no third round.
5. Set `reviewed: <revision>` and `reviewers: [<model ids>]`, using `manual:<model>` for user-run reviews. Then run `canon.py trace end <gate id> <outcome> --dir .canon/canon-blind-review/<doc id> --input -`, the dispositions on stdin.
6. Status. L1: a draft becomes `accepted`. L2: report the accepted, declined and escalated findings and the reviewer models, including any fallback, and get the user's answer on each escalated finding. The user then approves, here or by starting the next phase on the doc; a draft becomes `accepted` at that point and until then stays a `draft` whose `reviewed` equals `revision`. A revised active design stays `active`, and a revised plan in progress stays `in-progress`, in both tiers.

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

Report every blocker and major finding and at most 10 minor ones, most severe first, each as:

### F1 [blocker | major | minor] {location, e.g. D003§token-refresh}
Problem: ...
Evidence: ...
Suggestion: ...

Keep each finding as short as it can be while a reader can understand and verify it without redoing your review.
Then list Questions: anything you could not understand from the repository alone.
End with one line: Verdict: approve | revise
```

## Code review

Review every change once it is complete, before the docs step, with the `canon-code-review` skill when it is installed: against the governing designs and plan (spec) and the standards their owning designs state. Plan slices are not reviewed one by one. Every change, L0 included, gets a spec reviewer and a standards reviewer, fresh subagents running in parallel, so the session that wrote the change never reviews it; L2 adds the cross-family reviewer in the first round.

Fix findings in the change; when blocker or major fixes changed it, the reviewers that raised them confirm the fixes once. A finding deferred to later work goes into an R doc with disposition `open` so it stays tracked; code review produces no R doc otherwise.

## Subagents

The user sets each session's model and reasoning effort. Reviewers and implementation workers are new subagents from the host's own tool (the Task tool in Cursor, the Agent tool in Claude Code, multi-agent subagents in Codex), never forks of the session. Launch them without a model or effort, so they run on the session's.

The cross-family reviewer runs as the reviewer file, `.canon/canon-blind-review/reviewer.md`, says. The file is local because the tools and logins it relies on differ between machines; the `canon-init` skill writes it. It lists one or more reviewers, each with its model and effort, how to run it (a shell command with `<prompt>` and `<out>` placeholders that starts a new read-only session and leaves the final review in `<out>`, or a host subagent with a named model), and what the host needs to run it, such as running outside its sandbox. The cross-family reviewer is the first one whose model is of another family than the current session's.

## Docs step

Before committing, after implementation and code review. Scope: the uncommitted changes, or a branch with `--base <ref>`; after per-slice commits, the plan's `Started at` commit is the base.

1. Run `canon.py affected [--base <ref>]`. For each listed design, compare the diff with its governing sections (`show D00X#slug`):
   - The change implements an accepted spec or plan: write into the spec the details the code settled within its accepted intent, including those the plan's Notes list; they need no revision bump. Once a revision's implementation has fully landed, set `implemented` to that revision and the design `active`.
   - The code contradicts the spec: report it to the user instead of rewriting the spec.
   - The user decided to change the spec's meaning: bump `revision` and pass the review gate.
2. For changed files where `which` prints `no design`, add them to the `paths` of the design that owns the area. If no design owns it, tell the user; a new design is L2.
3. For each listed plan, update slice statuses, Current state and Log. Archive the plan as `done` when every slice is `done`; report paused slices to the user.
4. Set the dispositions of review findings the change fixed. Archive what is finished: reviews with no open finding (`closed`), fixed investigations (`resolved`), experiments whose conclusion is absorbed into a design (`concluded`).
5. Search READMEs, guides and `AGENTS.md` for names the change renamed or removed (commands, flags, config keys, paths) and fix them.
6. Run `canon.py check --fix` until it reports no errors.
7. When this change archived a plan, run `canon.py audit`. If it reports a due review, end your report with one line suggesting the user run a codebase review (the `canon-review` skill). Never start a review yourself.
8. Commit with Conventional Commits. Every commit that touches a design's `paths`, L0 included, names the designs it was checked against and the plans it updated in a trailer, e.g. `Refs: D003, P012`; `audit` counts code commits whose trailer omits their design as unchecked.

## Maintenance

Run `canon.py audit` before large tasks and periodically. For a design with unchecked code commits, compare it with those commits and update what they changed, then commit the design, bumping only `updated` when nothing else changed, so the count restarts. Finish or archive idle docs, and tell the user when a review (R) is due.
