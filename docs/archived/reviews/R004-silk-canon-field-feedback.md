---
status: closed
created: 2026-11-23
updated: 2026-11-25
revision: 1
modules: [canon]
summary: Fourteen findings from Silk on approvals, experiment claims, concurrent edits, external reviews, trace history and CLI diagnostics, with upstream fixes.
refs: [D001, D003, D006, D007, D009, D010, R003, P007]
---

# R004: Canon feedback from Silk on design reviews and concurrent work

## Scope

Silk used canon v0.8.2 (`canon.py` 67, installed in Silk commit `5c582b9`) to review related designs across sessions and worktrees. This usability and functional review covers 19 feedback entries recorded by six sessions on November 18–23, 2026, including gates run from November 16. The skills checkout was at `67284b5`. Silk's `main` was at `e174026` and the November 23 review worktree at `6e889a8`.

Record numbers below are one-based lines in Silk's local `.canon/canon-retro/skills.jsonl`. Its sibling `notes.md` records what Silk or the machine operator actually changed. Gate reports, trace events and Git commits corroborate the examples. IDs in code font and commit hashes in the findings refer to Silk. The three earlier records, from canon 22, concern design ownership, verbatim reviewer reports and snapshot identification. The first review tracks their upstream fixes. [R003: Canon friction in Silk's design phase](R003-silk-design-phase.md)

## Findings

The first three findings have short remedies already in Silk's project instructions. They are the highest priority to carry upstream. The dispositions track changes to the distributed skills.

| ID | Severity | Finding | Disposition |
|----|----------|---------|-------------|
| R004-F1 | major | An L2 approval request can omit an earlier target or imply permission to start planning. | fixed 2c4e46c |
| R004-F2 | major | Reviewers accepted a design guarantee broader than the experiment that supported it. | fixed 4e2663a |
| R004-F3 | major | A session can run a repository-wide fix after another session starts editing the same checkout. | fixed 977ff17 |
| R004-F4 | major | An external review can make progress for minutes without a visible status or a usable way to resume. | fixed 30596c4 |
| R004-F5 | major | The manual fallback leaves the gate's state unclear when an independent reviewer is unavailable. | fixed e92eebc |
| R004-F6 | minor | Reviewer setup repeats launch commands and can omit the scope of an existing authorization. | fixed 30596c4 |
| R004-F7 | minor | Fixing one occurrence of a guarantee can leave contradictory wording elsewhere. | fixed 4e2663a |
| R004-F8 | minor | A fresh confirmation reviewer can reopen findings the maintainer already declined. | fixed 8478e13 |
| R004-F9 | minor | A reply approving some decisions and asking about others can trigger premature edits. | fixed 33e1e47 |
| R004-F10 | major | Review records can misattribute a revision or give an outdated result for a finding. | fixed e92eebc |
| R004-F11 | minor | Historical trace gaps require manually matching events to review directories. | fixed bb35f13 |
| R004-F12 | minor | A worktree handoff can leave the maintainer guessing whether the work reached the target branch. | fixed 977ff17 |
| R004-F13 | minor | Renumbering an experiment can break a command needed to reproduce it. | fixed de9c466 |
| R004-F14 | minor | A strict branch check gives no indication that a reported error already exists on the base. | fixed c44410b |

### Design approval and shared checkouts

**F1. Carry the whole approval forward.** The last of two follow-ups listed three revisions. A later session had to read the original gate and both follow-ups to recover the fourth, `D002@r6`. Commit `03050e1` records all four. In a separate gate, the maintainer answered yes to a combined approval and planning question, then had to interrupt planning. Silk recorded the approval in `847ce66` and changed its handoff wording in `707d0b4`. Keep a machine-readable list in `.canon/canon-design/` for each change, carrying each target and its exact reviewed revision forward until approved or superseded. Ask for approval of that list and put the planning command on its own line. A bare yes records the revisions. An explicit request for both also starts planning. Records 8, 9 and 19. [D007§gate-status: gate status](../designs/D007-change-tiers.md#gate-status)

In the skills repository, `4e2663a` made a bare yes approve the listed revisions. Commit `2c4e46c` added `canon.py approvals` to recover the list in the same worktree. Replaying the original Silk gate and both follow-ups returned all four revisions, including `D002@r6`. Replaying the approval in Silk commit `03050e1` cleared the list. [D007§pending-l2-approvals: pending L2 approvals](../designs/D007-change-tiers.md#pending-l2-approvals)

**F2. Check the conditions of experimental claims.** One experiment measured a stall within a single CUDA context. Two successive design revisions applied the result to a whole process, which can contain multiple contexts. The maintainer caught the change in scope after two review rounds. Silk narrowed the claim and added a reviewer instruction in `14319d3`. The upstream correctness prompt should ask whether the experiment exercised the conditions under which the design promises the result. Record 6. [D007§reviewer-prompt: reviewer prompt](../designs/D007-change-tiers.md#reviewer-prompt)

**F3. Recheck ownership before a write.** The checkout was clean at the author's first edit. Hours later, a full `check --fix` ran with 11 uncommitted files from concurrent work. The author discovered the overlap in the command's output. Silk's rule in `5ef9ce7` compares `git status --short` with the author's own files immediately before a full fix, staging or commit. Add that check to the upstream concurrent-work instructions and use the existing per-document or partial-commit procedure when another writer appears. Record 7. [D006§concurrent-work: concurrent work](../../designs/D006-doc-model.md#concurrent-work)

### Running an external reviewer

**F4. Show progress and preserve the session.** One first pass took nearly 15 minutes while the launcher buffered its final output. The maintainer could not tell whether launch approval was pending or review had begun. A separate review hit the caller's 1,000-second deadline and needed a one-off script to resume the same session. Have the invoking host report pending approval, actual start, observed activity, and exit status with elapsed time. Silk's launcher exposes its last observation to buffered hosts and sends a short heartbeat during silence. Save the session ID at startup so an interrupted run can resume. The machine-local launcher times out after 1,800 seconds without activity, and its retro records 42 passing offline cases. Record 18 and the `external-review-progress` and `external-review-resume` notes. [D003§resuming-and-replacing: resuming and replacing](../designs/D003-subagents.md#resuming-and-replacing)

**F5. Report what actually passed.** The independent reviewer returned HTTP 429 twice during one L2 gate. Its same-model reviewer had already confirmed seven fixes. The maintainer initially offered a manual report, then had no other family available. Keep the gate pending and show the completed findings, the outstanding cross-family requirement and how to resume it. If the maintainer explicitly grants an exception, record the exact gate and revisions and credit only reviews actually received. Silk's `D003-r24/waiver.md` records that single-gate decision. Record 16. [D007§review-gate: review gate](../designs/D007-change-tiers.md#review-gate)

**F6. Define each reviewer once.** Adding a second model behind one CLI duplicated its launch and report-extraction commands. On a hosted route, the maintainer also had to repeat the approved destination and read-only tool scope. Silk's machine file now puts per-family priority lists first, with links to one definition per reviewer. Document that layout in setup and lookup. Each definition identifies the model, effort, supported host, launcher and prerequisites. A family or host can declare `none`. An authorization request can cite the configured destination, inputs and existing approval while the host makes its own decision. Keep model priorities and provider settings local. Record 17 and the `hosted-review-destination-approval` notes. [D003§reviewers: reviewers](../designs/D003-subagents.md#reviewers)

### Fixing findings and recording decisions

**F7. Look for the same promise in other sections.** The old wording of a corrected guarantee survived in another design's results and then in a Decisions section, costing two targeted rechecks. In a second gate, the old wording survived in Goals after the contract and decisions had been fixed. Before sending a semantic fix for confirmation, search the affected designs and sketches for the old guarantee and its exception. Include the other affected locations in the same diff. Record 11, with the first case in `D003-r9/merge-notes.md`. [D007§confirmation-round: confirmation round](../designs/D007-change-tiers.md#confirmation-round)

**F8. Give a fresh reviewer the accepted claims to confirm.** A prompt requested F2–F13, including only the accepted parts of F5 and F6, then appended the full first-round report. The reviewer also judged the previously declined F1 unresolved. The author had to reconcile that verdict by hand. Send the original text of each requested finding and identify the accepted subclaim where a finding was split. Archive the full first report and keep the invitation to report new blockers introduced by the fixes. Record 21, `D001-r21/cross-family-confirm-prompt.md` and its response. [D003§resuming-and-replacing: resuming and replacing](../designs/D003-subagents.md#resuming-and-replacing)

**F9. Answer the unresolved part of a mixed reply.** The maintainer approved two numbered choices and asked three questions. The author announced a policy edit on one of the questions and was asked to answer first. Give `canon-grill` a worked example. The author retains the two approvals, answers the three questions and waits for decisions on those points before editing them. Record 20. [D009§record: recording decisions](../designs/D009-settling-decisions.md#record)

### Review history

**F10. Attribute each review and recheck to the revision it covered.** Silk requested extra cross-family reviewers, but the trace accepted one entry for that role. A follow-on target joined while findings were being fixed, so only the confirming reviewer saw it. The workflow still called for the gate's reviewers in the revision metadata. A separate gate's trace retained three unresolved findings after the archived rechecks recorded their resolution. Set a revision's `reviewers` field from the reviewers who read it. Let the trace identify each reviewer within a role and append each recheck with its finding, reviewer and snapshot. A reader could then retrieve both the first confirmation and the latest result. Records 4, 5 and 12, including trace `20261116T081751Z-6d9406`. [D001§review-dispositions: review dispositions](../../designs/D001-skill-telemetry.md#review-dispositions) and [D007§follow-up-round: follow-up round](../designs/D007-change-tiers.md#follow-up-round)

**F11. Make old trace gaps visible.** A November 20 inventory counted 31 starts and 30 ends. The unmatched design start was older than the 24-hour window in `trace status`. A follow-up recorded `archive=none` although its reports still existed in the review directory. Offer a read-only historical view that pairs starts and ends and flags missing archives. Report wall time by workflow kind so nested gates and their parent design sessions can be read separately. Record 13, trace events 17 and 26. [D001§commands: trace commands](../../designs/D001-skill-telemetry.md#commands)

A replay of the 31-start trace with `bb35f13` exposed the unmatched design and the follow-up with an empty archive. Replaying the later F2 result with `81c92e6` preserved its first confirmation. The handoff fixture for `e92eebc` retained each source’s coverage. Review fixes in `bd4fef3` preserved both delegates’ reports and identified conflicting historical evidence. The slice query in `b69fc41` recognizes a renamed plan’s completion commit using locally available Git objects. [P007§log: implementation log](../plans/P007-blind-review-recovery-and-history.md#log)

### Worktree handoffs and command diagnostics

**F12. Say where the delivered commit is.** Three worktree handoffs described the branch or commits without establishing whether local `main` contained them. In one, `git rev-list --count 03050e1..b81a533` returns five. The maintainer had to ask about integration. Silk added the rule in `cea0afa`. Have the handoff name the branch, tip and target. Use `git merge-base --is-ancestor <tip> <target>` and give the outstanding commit count when integration is pending. Use the same wording in prototype handoffs. Record 14. [D006§concurrent-work: concurrent work](../../designs/D006-doc-model.md#concurrent-work)

**F13. Check runnable paths after renumbering.** Moving an experiment from `E031` to `E033` moved all nine attachments and rewrote Markdown links. The setup command still invoked `docs/experiments/E031/run.py`. The author repaired it in `b8afa12`. Have `renumber` report the file and line of any literal path to a moved attachment that survives in the experiment's instructions. A regression fixture can use two experiments claiming the same ID and a fenced command naming one of their scripts. Record 15. [D010§renumber: renumber](../../designs/D010-doc-queries-and-renames.md#renumber)

**F14. Identify an inherited strict-check error.** `canon.py check --rev 0f2afbf --base 707d0b4` reports one error, pending review of `D002@r7`. Repeating the check with `--rev 707d0b4` reports that same error and a second one. Both commands exited 1. Label a matching diagnostic already present on the base, preserving strict repository-wide validation and its exit status. Record 22. [D006§check: check](../../designs/D006-doc-model.md#check)

Replaying the same Silk commits with `c44410b` marked the pending `D002@r7` error and the missing module-directory warning `[also on base]`. The selected commit still reported one error and one warning and exited 1. The additional pending review of `D003@r25` appeared only in the base's own check.

## Project-specific decisions

Silk's original proposal also serves as an overview for external readers. The maintainer declined the proposed overview-drift rule. Silk's project convention calls for updating the overview's ideas and links when a design changes what they describe. Record 10 asks upstream to clarify where to document such an exception. Commit `c44410b` added an example alongside the default concept lifecycle showing how a project records its own update rule in `AGENTS.md`. [D006§doc-types: doc types](../../designs/D006-doc-model.md#doc-types)

Two other retro items have local owners. Silk added a commit-title CI check in `26bc940`. Its reviewer also found three Python examples missing a required argument. Commit `3c5a983` corrected the examples, and checking them against the API signatures in Silk's docs CI remains a proposal. Both are recorded in Silk's `notes.md`.
