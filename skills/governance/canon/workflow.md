# Workflow

## Flows

The tiers are defined in [SKILL.md](SKILL.md#workflow).

- **L2**: (concept) → design draft → review gate → commit → user approval, `accepted` → plan draft → review gate → commit → user approval, `accepted` → implement → code review → docs step → commit.
- **L1**: [revise the design in place (revision +1) → review gate → commit] → [plan → review gate → commit] → implement → code review → docs step → commit. At least one bracketed part runs: the revision when the work changes a spec, the plan when it needs one.
- **L0**: implement → code review → docs step → commit.

A design revision that needs no code change ends once its gate has passed and, in L2, the user has approved it ([Gate status](#gate-status)).

Design, plan and implementation are separate phases, and each can start in a fresh session because the docs carry the state. A phase ends by giving the user the command that starts the next one, e.g. `/canon-plan D012`; the user runs it in this session or a new one. L1 work is the exception: the session that revises the design, including one given L1 work through `canon-implement`, carries on to implementation after the gate, or gives `/canon-plan D012` when the work needs a plan. So does a [design problem](#design-problems) found while planning or implementing, unless its fix is L2. Carried-on L1 implementation outside `canon-implement` runs `canon.py trace start implement <D id> --tier L1 --skill <skill> --model <model>`. It runs `canon.py trace end <implement id> <outcome> [--to plan|L2]` after the docs step's commit and any end check, or when it stops.

## Design problems

A design problem is a flaw found in an accepted or active design while working from it: the design contradicts itself or another design, no implementation can satisfy it, the work would have to change what it states, or it lacks a decision only its intent can settle. Planning, review gates, implementation and code review can all find one, in the design the work builds on or in passing in another. Wherever it is found:

1. Confirm it against the design and the code; a finding the reviewed target can fix within the design is an ordinary finding. Work that depends on the flawed part waits for the user's decision and any fix it brings, and the rest carries on, its gate and commit included. When unsure whether the work depends on it, treat it as dependent.
2. Tell the user, with the fix you would propose and its tier. In a review gate or code review, finish the review first and report it with the review's other findings: a code review in its report, a gate when it merges its findings, before any confirmation round. Never change the design's intent yourself, even when it is plainly wrong.
3. Once the user decides on a change, revise the design in place in the current session, without the `canon-design` skill: bump `revision` and pass the review gate at L1, or a [follow-up round](#follow-up-round) when this session's gate passed the design's previous revision. A design another session is revising gets a [known issue](doc-types.md#designs-d) instead, with the work as Source and Next `L1`, so the request is in the design, never only in a handoff file or a message. A fix the tiers put at L2, such as a rewrite of the design's goals or core approach, goes through `/canon-design D00X`: give the user the command and pause the work that depends on it.
4. When a plan builds on the design, check its slices against the design's diff, move its `based_on` to the new revision and log why. In a plan's review gate, do this before the confirmation round, so the reviewers confirm against the revised design.
5. A problem this session does not fix, because the user deferred it, its fix is L2 or the user has not decided, becomes a [known issue](doc-types.md#designs-d) of the design. One the user rejects leaves no row, only a Decision when the reason is lasting.

A detail the design leaves unstated, which the plan can settle within the design's goals and spec, is not a design problem: the plan settles it and lists it in its Notes for the docs step to write into the design. Changing what the design states never counts as such a detail.

An L0 change that turns out to alter a spec takes the same steps; once the design revision passes its gate, the change continues as L1 work.

## Implementation

Implement slice by slice, each slice in a fresh worker subagent (the `canon-implement` skill). Only the orchestrating session edits the plan and commits: after each slice it sets the slice's `Status:` and updates the plan's Current state and Log.

When the implementation cannot follow the plan or the design:

- **Plan problem with one clear fix**: edit the plan and continue without asking; log the deviation and the decision. Such a fix keeps the plan's `revision`. When the plan problem needs a decision, or its fix would change what the plan delivers, mark the slice `paused` and ask the user: that is a new plan revision, made with the `canon-plan` skill, and it passes the review gate before the slices resume.
- **[Design problem](#design-problems)**: mark the slice `paused` and tell the user.
- While a slice is paused for a design problem or a pending decision, finish the slices that do not depend on it, then report every paused slice with its problem.

## Review gate

Every design or plan revision passes this gate before it is accepted, and every revision of an active design passes it before implementation. Bump a doc's `revision` once, at the revision's first edit; every edit up to its gate's commit joins that revision, and a later edit makes a new one.

A gate covers the revisions one change makes together: its target, the design or plan the change is about, and, for a design, its follow-on targets, the other designs the change revises to match it, D000's glossary included. It runs at the highest tier among them, even within work of a lower tier, such as an L1 revision made while implementing an L0 change, with one set of reviewers, one reviewer prompt naming every target and one `Changes since` commit. A plan's revision passes a gate of its own, after the gate of the designs it builds on, as do an [as-built revision](as-built.md), whose prompt differs, and a revision that a design problem found later in the change brings, unless it takes a [follow-up round](#follow-up-round). A follow-on edit that changes no meaning, such as a restatement replaced with a link or a name a rename changed, bumps no `revision` and needs no gate.

1. When the user shaped the revision, as in a `canon-design` interview, show them what it changes and ask whether their content feedback is finished. Run `canon.py check` and fix its errors, so reviewers spend no effort on formatting. For a revision of an accepted or active design, or of an accepted or in-progress plan, it warns that the revision is not reviewed until step 5.
2. Run `canon.py trace start gate <ids> --tier <tier> --skill <skill> --model <model> [--parent <parent>] [--base <Changes since commit>]`. `<ids>` is the target's id followed by the follow-on targets'. Launch the first-round reviewers with the `canon-blind-review` skill, passing only the reviewer prompt below:
   - **Same-model reviewer**: in every gate.
   - **Cross-family reviewer**: in the first round; in the confirmation round it confirms the fixes of the findings it raised, and in a follow-up round it reviews the new revisions. Required for L2; in L1, only when the user asks for it.
3. Merge the findings as the `canon-blind-review` skill says. A finding the user leaves for later becomes a [known issue](doc-types.md#designs-d) of a target design, or a line in a target plan's Notes. A finding about a design other than the gate's targets, such as a plan finding about its design, follows [Design problems](#design-problems). Declined findings stay out of the doc; record a Decision, in the design that owns the topic, only when its rationale has lasting value. Until step 7, edit the targets only to fix findings; any other edit waits for a [follow-up round](#follow-up-round).
4. When accepted blocker or major findings were fixed, prepare the confirmation diff. For a fix that changes a guarantee, search the affected designs and their sketches for the old claim, equivalent wording and its exceptions. Include corrections across the targets and their sketches in the same diff. A conflict with another design follows [Design problems](#design-problems). Run the `canon-blind-review` skill's confirmation round.
5. Set each target's `reviewed: <revision>` and `reviewers: [<model ids>]`, using `manual:<model>` for user-run reviews, and delete the `as_built` line of an [as-built revision](as-built.md). In L2, report the accepted, declined and escalated findings and the reviewer models, including any fallback, and get the user's answer on each escalated finding. Then run `canon.py trace end <gate id> <outcome> --dir .canon/canon-blind-review/<topic> --input -`, the dispositions on stdin.
6. Set each target's status as [Gate status](#gate-status) says.
7. Commit the targets before any further edit that changes their meaning, so a later edit is a new revision ([Follow-up round](#follow-up-round)). The commit may hold other work, such as the other gates of a setup (the `canon-init` skill).

### Reviewer prompt

The reviewer prompt is the `canon-blind-review` skill's template with `a design` or `a plan` as its artifact, filled with the lines below. The `Follow-on targets` line is only for a gate that has them, and the `Changes since` line only for a gate with a target that revises an existing doc; its commit is the newest one that holds the previous revision of every such target. The `As-built` line is only for [as-built revisions](as-built.md), filled from `as_built`: the first of each choice for a new design and for a commit, the second for a revision and for `worktree`. In Correctness and Completeness, as-built revisions take the second choice and other revisions the first; when the project, or the module the target concerns, has no code yet, Correctness replaces `the current code` with `the experiments and designs it rests on`. A design's prompt drops the `Plans only` item, and only an as-built revision's has the as-built one.

```text
Target: {path}
Follow-on targets: {paths}, revised to match the target
Changes since: {commit} (review what changed; read the rest for context)
As-built: {the target | what this revision adds} records {the code at {commit}, read with `git show {commit}:<path>` since the work tree may hold a later change | the files as they are} and specifies no change to it.

Read the targets, the docs they link to, and the code they govern.

Assess:
- Correctness and feasibility against {the current code | the code it records}. For each guarantee drawn from an experiment, check whether its runs tested or its cited sources cover the conditions the guarantee claims.
- Completeness: a fresh agent could {implement it | change the code it governs} from this document and its links alone.
- Consistency: no conflict with other designs; each standard is stated once, in the design that owns it, and linked elsewhere; a design other than D000 states its own scope, not what other designs own.
- Simplicity: no complexity beyond the goals. A feature's own input validation, permissions and data protection are part of it; security hardening beyond that only where the design or project requires it.
- Plans only: slices are ordered by dependency, independently verifiable, and each has concrete test criteria.
- As-built revisions only: what the revision adds holds for the code it records, apart from behavior that a known issue with source `as-built` and next `fix` names as a defect; it omits no behavior callers rely on within the topic it records; it fixes no private structure; each Decision gives a source or says its reason is unknown.
Formatting, frontmatter and wording style are out of scope.
```

### Follow-up round

Once a gate has committed its targets, the session that ran it passes a follow-up round instead of a new gate for each later revision it makes of a target: the user's feedback on the gate's report, an afterthought, the fix of a design problem the work found. A design first revised to match such a revision joins the round as a follow-on target. A new gate is passed instead by a revision made in another session, by an as-built revision and the revision after an as-built revision's gate, whose prompts differ from the gate's, and by one that would raise the gate's tier, such as a rewrite of a goal or the core approach of an L1 revision. An edit that changes no meaning bumps no `revision` and needs no round.

Run `canon.py trace start follow-up <ids> --tier <tier> --skill <skill> --model <model> [--parent <parent>]`. `<ids>` names the targets the round revises and `<tier>` is the gate's; HEAD holds their previous revisions, so it takes no `--base`. The gate's reviewers review the new revisions as the `canon-blind-review` skill's follow-up round says. Merge their findings as step 3 says, run the confirmation round as step 4 does, then steps 5 to 7 for the new revisions, `reviewers` naming the gate's reviewers; an L2 revision needs the user's approval again. Step 5 runs `canon.py trace end <round id> <outcome> --dir .canon/canon-blind-review/<topic>/followup-<k> --input -`.

### Gate status

Move a status with `canon.py status`, after setting any `implemented` the move needs.

- L1: a draft becomes `accepted`.
- In L2, record the reviewed targets before asking or handing off. Run `canon.py approvals GATE --start ID@rN ...` with the full first round. GATE is its original review topic, e.g. `D001-r15`. Each follow-up runs `canon.py approvals GATE --update ID@rN ...` with the targets it just reviewed, keeping the original key. Give the checkout and key in a handoff.
- In a fresh session, `canon.py approvals` lists outstanding gates in this checkout. Use `canon.py approvals GATE` for the exact revisions to put in its approval question. For a missing record, reconstruct the pending set from the original gate, all follow-ups and their reviewed commits, then use `--recover` with those revisions. To resume a settled plan gate, verify the plan against those commits and use `--recover ID@rN` even if its ID matches the gate key. Reconcile incomplete history or stale entries before asking. For a later review in another gate, verify the superseding commit, then use `--update --retire ID@rN`. After a rename or renumber, verify the file move and supply the replacement `ID@rN` in the same update.
- Put the next phase's command on a separate line after the approval question. Before acting on a bare yes, compare the scoped query with the exact list the user saw. If it changed, present the new list for approval. Set each authorized target's `approved` to its listed revision and each applicable draft to `accepted` with `canon.py status`. Commit those changes together, then run `canon.py approvals GATE --update` to clear the settled entries. An explicit partial approval covers the named revisions. Start the next phase when the user requests it; invoking it approves the revisions that phase uses.
- A revised design that is `accepted` or `active`, and a revised plan that is `accepted` or `in-progress`, keeps its status, in both tiers.
- A design revision that needs no code change, such as D000 written before the project has code, or a rule relaxed that the code already meets, needs no plan or implementation. When it passes its gate, or in L2 once the user approves it, since no next phase starts, its `implemented` rises to it if it equaled the previous revision, and a new design becomes `active` with `implemented` equal to its revision.
- After a split's gate, the sub-design takes its parent's status, except that it is `accepted` when the parent is `active` but its `implemented` does not cover all the spec the sub-design receives; an `active` sub-design gets `implemented: 1`. The parent's `implemented` rises to its new revision when it equaled the previous one.
- After an [as-built revision](as-built.md)'s gate, in place of `accepted`, a new design becomes `active` with `implemented` equal to its revision; a revised design keeps its status, and its `implemented` rises to the new revision only when it equaled the previous one.

## Code review

Review every change once it is complete, before the docs step, with the `canon-code-review` skill: against the governing designs and plan (spec) and the standards their owning designs state. Plan slices are not reviewed one by one. Every change, L0 included, gets a spec reviewer and a standards reviewer, fresh subagents running in parallel, so the session that wrote the change never reviews it; L2 adds the cross-family reviewer in the first round.

Fix findings in the change; when blocker or major fixes changed it, the reviewers that raised them confirm the fixes once. A finding the user defers becomes a [known issue](doc-types.md#designs-d) of the design governing its code, or an Idea in the module's backlog concept when no design governs it, so it stays tracked; code review produces no R doc. A finding that shows a design itself is wrong is a [design problem](#design-problems): the review stays open until any revision the user chose has passed its gate, and a change that depends on a problem awaiting the user's decision or its fix is not committed.

## Subagents

The user sets each session's model and reasoning effort. Implementation workers are new subagents from the host's own tool (the Task tool in Cursor, the Agent tool in Claude Code, multi-agent subagents in Codex), never forks of the session, launched without a model or effort, so they run on the session's. Reviewers are the `canon-blind-review` skill's: how they launch, which one takes over when one stops, and where to find a report whose completion notice has not come.

A subagent is resumed by its id: the Task tool's `resume` in Cursor, SendMessage to the agent id in Claude Code, `send_input` to the agent id in Codex, after `resume_agent` when it was closed. A worker whose run stops before it reports, because the host reports it interrupted, timed out or failed, or its record shows the run ended without a report, gets one more run: resume it, asking only that it continue where it stopped and end with the report its prompt asks for; when it cannot be resumed, replace it as the `canon-implement` skill says. When that run stops too, stop trying; that skill says what follows.

### Reviewer file

Read the machine-local `$XDG_CONFIG_HOME/canon/reviewer.md` (default `~/.config/canon/reviewer.md`). When missing, copy there an earlier setup's `.canon/canon-blind-review/reviewer.md` from this checkout or the main one. Read the earlier file in place if the copy fails. A sandboxed write outside the workspace needs the user's approval.

1. Under `Reviewer priorities`, the first section, use the initiating model family's ordered Markdown links to named reviewers. An existing inline family list counts as its order. For an unlisted family try the named `Default` order, then the legacy unheaded list. Honor entries scoped to this host and entries for all hosts. An applicable `none` ends selection with the manual route.
2. Follow each priority link to its entry under `Reviewer definitions`. Skip the initiating family and reviewers this host cannot run. Take the first eligible reviewer, advancing in order when its stopped runs are exhausted. Run each additional reviewer the user requested even when the first succeeds.
3. Each stable definition gives the reviewer's family, model, reasoning effort, supported hosts, login and other prerequisites, and launch route. A host subagent names its host and model. A command opens a fresh read-only session, reads `<prompt>` and publishes the terminal report to `<out>`. Define a shared launcher once under a named heading and link to it from each definition, supplying that reviewer's model and effort.
4. For a command, record the destination, permitted inputs and tools, how to obtain its early session ID and the available status and resume operations. When the host requests permission, cite this scope and any applicable prior authorization. The host decides permission for this run. Keep provider commands, settings and deadlines local and credentials in the provider's existing credential store.

### Reviewer setup

When selection finds neither an eligible reviewer nor an applicable `none`, configure just the initiating family for a review. A user-requested setup covers the families they name and can replace a configured `none`.

1. Show each family's current order and ask for its reviewer preferences, hosts, tools, models and efforts. Suggest the other family's flagship model. Record `none` when the user declines or has no reviewer, scoped to the current host when other hosts keep their entries.
2. Build each route from the tool's help and try a small read-only prompt. Capture the session ID as soon as it appears, query the trial job with its declared read-only status operation, and inspect the published report. When the route offers resume, demonstrate a read-only continuation of that test session using the observed ID and check its response. Record only capabilities the trial demonstrated.
3. Normalize the edited family's inline definitions into named definitions and priority links, preserving order and host restrictions. Preserve other families, hosts, unheaded fallbacks and shared definitions. Give a changed route its own definition if editing a shared one would change another family's setup. If setup cannot write the file, use the manual route in the `canon-blind-review` skill.

## Docs step

Before committing, after implementation and code review. Scope: the uncommitted changes, or a branch with `--base <ref>`; after per-slice commits, the plan's `Started at` commit is the base.

1. Run `canon.py affected [--base <ref>]`. For each listed design, compare the diff with its governing sections (`show D00X#slug`):
   - The change implements an accepted spec or plan: write into the spec the details the code settled within its accepted intent, including those the plan's Notes list, with the experiment links they carry; they need no revision bump. Once a revision's implementation has fully landed, set `implemented` to that revision and the design `active`.
   - The code contradicts the spec: report it to the user instead of rewriting the spec, and record it as a known issue when the user leaves it for later.
   - The user decided to change the spec's meaning: bump `revision` and pass the review gate.
2. For changed files where `which` prints `no design`, add them to the `paths` of the design that owns the area. When no design owns it and the change altered nothing callers rely on, name each such file with its directory in your report; it needs no new design. When the change altered behavior callers rely on there, it needed an [as-built revision](as-built.md) first, or a new design for a new topic, as the [tiers](SKILL.md#workflow) say: tell the user.
3. Bring D000's rows in line with the change; [doc-types.md](doc-types.md#project-overview-d000) says which changes update them.
4. For each listed plan, update slice statuses, Current state and Log; report paused slices to the user.
5. Set the dispositions of review findings the change fixed, and delete the known issues it resolved. For each design and plan step 1's `affected` listed, set each answered experiment it links `concluded` with `canon.py status`, archiving the earlier experiments on that experiment's question as [doc-types.md](doc-types.md#experiments-e) says. Then archive what is finished, in this order: plans whose every slice is `done` (`done`), reviews with no open finding (`closed`), fixed investigations (`resolved`), and experiments `check` reports concluded but cited by no live doc (`concluded`).
6. Search READMEs, guides and `AGENTS.md` for names the change renamed or removed (commands, flags, config keys, paths) and for what they state of behavior the change altered, and fix them.
7. Choose the scope of `canon.py check --fix` as [Concurrent work](SKILL.md#concurrent-work) says and run it until it reports no errors.
8. When this change archived a plan, run `canon.py audit`. If it reports a due review, end your report with one line suggesting the user run a codebase review (the `canon-review` skill). Never start a review yourself.
9. Commit with Conventional Commits. Every commit that touches a design's `paths`, L0 included, names the designs it was checked against and the plans it updated in a trailer, e.g. `Refs: D003, P012`; `audit` counts code commits whose trailer omits their design as unchecked.

## Maintenance

Run `canon.py audit` before large tasks and periodically. For a design with unchecked code commits, compare it with those commits and update what they changed, then commit with a `Reconciled: D00X` trailer, as an empty commit (`git commit --allow-empty`) when nothing needed changing. `audit` counts from the newest such commit or change to the design beyond its known issues; only this step and `canon-sync` write that trailer. Delete the known issues a change has already resolved, finish or archive idle docs, and tell the user when a review (R) is due and which known issues await a decision.
