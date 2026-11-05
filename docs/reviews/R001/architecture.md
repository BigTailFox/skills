# R001 architecture report

Reviewer: fresh subagent on the session's model, at commit `7c2ebf2`. Findings A1–A12 are R001-F1–F12.

### A1 [major] File-grained `paths` make coverage, `which` and `Refs:` overstate what designs govern
- Location: `paths` of D001–D005; `Doc.governs`, `coverage_report`, `unchecked_commits` in `canon.py`; D000#capabilities; D002#coverage-in-audit
- Problem: a `paths` entry matches a whole file, and the hot files hold many topics: `canon.py` is in all five designs, `tests/test_canon.py` in four, `workflow.md`, `canon-implement/SKILL.md` and `canon-code-review/SKILL.md` in three. A design constraining a few lines claims the whole file, so coverage (this review's own hard check) cannot see the biggest undesigned area, and `affected` names five designs for any `canon.py` edit, so every commit's `Refs:` lists all of them and no longer says which designs were checked, weakening unchecked-commit detection.
- Evidence: D000's first capability (doc model, frontmatter, lifecycle, `check_doc`, archive/rename/renumber, `move_doc`/`rewrite_for_moves`, `show`/`find`/`affected`, audit's unchecked commits; roughly half of `canon.py`) is `none`, and D004's Decisions say those commands "have no design", yet `which canon.py` names five designs and audit lists nothing under `skills/governance/canon/scripts/`. `which` maps `canon-investigate`, `canon-retro` and `canon-handoff` `SKILL.md` to D001 alone, for their trace call sites, while D000's rows for those capabilities read `none`. 59256c7, an index-marker fix (D005's topic), carries `Refs: D005, D004, D002, D001, D003`.
- Suggestion: let a `paths` entry name part of a file (`file#slug` for Markdown headings, `canon.py`'s existing `# ----` banner sections such as `canon.py#trace`), with `which` and `affected` mapping changed lines to sections and coverage counting sections. Meanwhile make D000's first row the first backfill target. Benefits: `Refs:` names only the designs a diff touches; coverage shows the real gaps. Strength: Worth exploring (section paths); Strong (the core design itself).

### A2 [major] Installed skills and a project's `canon.py` copy drift apart with no version contract
- Location: canon/SKILL.md#tool; canon-sync Audit step 1; canon-init Upgrade; D000#dependencies
- Problem: skills update per machine (`npx skills update -g`); a project's copy changes only through a manual `/canon-init` upgrade or `/canon-sync` audit. Skills use new commands and fields as soon as they ship, but none checks `canon.py --version` before relying on them. D001 (trace) and D003 (snapshot) handle "copy too old" locally; nothing else does. The canon skill tells agents to follow `canon.py`'s output, so an old copy's errors steer them wrong.
- Evidence: `CANON_VERSION` went 1→24 between 2026-10-13 and 2026-10-30. At v18 (7c9c7d0^) `OPTIONAL_FIELDS` lacks `as_built`, so `check` reports the field `as-built.md` requires as an ERROR (`unknown frontmatter field`), and gate step 1 says to fix check's errors. At v21 (385464d^) there is no `snapshot`, so confirmations fall back to "no diff". Older copies also lack D000's checks and audit coverage, which `canon-review` takes its scope from.
- Suggestion: the canon skill's Tool section states the minimum `CANON_VERSION` the installed skills need; each workflow compares it with `canon.py --version` at the start and stops with the upgrade command when the copy is older; `validate.py` checks the stated minimum is not above `CANON_VERSION`. Consider making `canon.py` its own module in D000, so its CLI and frontmatter schema become a cross-module interface (L2 to change). Strength: Strong.

### A3 [major] Running a blind review is spread over four skill files that restate each other's rules
- Location: workflow.md (Review gate, Reviewer prompt, Code review, Subagents); canon-blind-review (Prompt, Reviewers, Merge, Confirmation); canon-code-review §4; canon-review §3; canon-implement §2/Workers; D003
- Problem: the reviewer report contract ("every blocker and major … at most 10 minor", "Keep each finding as short …") is in workflow.md, the canon-blind-review template and the canon-review brief; "Report a problem a design lists as a known issue only when …" in workflow.md, canon-code-review and canon-review; "raised by both reviewers is accepted" in workflow.md step 3 and canon-blind-review Merge; "a stopped subagent gets one more run" in workflow.md, canon-blind-review twice, and canon-implement. workflow.md says to use canon-blind-review and canon-code-review "when it is installed", implying a standalone path that D000 Goal 2 (installed together) rules out and that has no snapshot, review files or confirmation prompt anyway.
- Evidence: b387f60 and 869e499 each edited the same reviewer rule in 3–4 files; 98ab39c (resume before replacing) touched workflow.md, canon-blind-review, canon-implement and D003; 0cba31c touched 5 files. Commits in 90 days: workflow.md 21, canon-blind-review 14, canon-code-review 13, canon-implement 18.
- Suggestion: make canon-blind-review the one module that runs a blind review. Callers pass the target, criteria or briefs, roles and topic; it owns the prompt skeleton (report contract, known-issue rule), launch, review files and snapshot, stopped runs, the manual fallback, the baseline merge rule and confirmation. The gate in workflow.md keeps only its criteria, as-built lines, doc-specific merge rules and the status step; canon-code-review keeps its two briefs; canon-review points its angle briefs at the shared contract. Drop the "when it is installed" hedges. Benefits: locality (a review-rule change edits one file, not 3–6); leverage (three callers share one implementation); README's Host verification rows test one skill. Dependency category: in-process (instruction text composed into prompts). Strength: Strong.

### A4 [major] A failing Git is read as "outside Git", which silently drops id protection
- Location: `git()` and `Repo.__init__` in `canon.py`; `trace_root`/`trace_git`; D002#project-overview-d000 (ids that history keeps taken)
- Problem: `git()` turns every failure into None and drops stderr, whether Git is missing, refuses with dubious ownership, or the directory is not a repo. `Repo` sets `is_git` from that, so when Git refuses a real checkout, `history_ids` and `deleted_docs` return nothing: `new`, `adopt` and `renumber` can reuse a deleted doc's id, and `check` skips the deleted-doc and `updated` rules. This is exactly what D002 guards with `canon: cannot read the history of HEAD`. Elsewhere None is read as "no files" (`coverage_report`) or "no commits" (`unchecked_commits`). The trace half decides Git by whether `.git` exists and raises errors with the exit code, so the two halves of the file disagree about the same checkout.
- Evidence: in a scratch repo, D001 committed then deleted: `new D second` gave D002; with Git unavailable, `env PATH=/nonexistent python3 canon.py new D third` created `D001-third.md`. Dubious ownership (common on WSL `/mnt/c` and in CI containers) makes `rev-parse` exit 128 down the same path.
- Suggestion: when a `.git` exists but Git fails, exit with Git's message. Give `git()` a required mode that exits on failure, and keep None only where absence means something. Dependency category: local-substitutable (tests already use real Git and a stand-in `git` on PATH). Strength: Strong.

### A5 [minor] Closing steps and finding routing are copied into each workflow skill
- Location: canon-design Gate, canon-plan Gate, canon-implement Finish, canon-code-review Dispose, canon-review Close, canon-handoff Report, canon-investigate Phase 6; workflow.md gate step 3 and Code review; canon-retro Later; as-built.md step 7
- Problem: the retro end-check trigger paragraph is verbatim in six skills plus a variant in canon-investigate; "deferred finding → known issue of the governing design, else backlog Idea" is restated in six places. This breaks writing.md's first rule, "Say each thing once".
- Evidence: 62ad100 edited seven skills; 1c7c1f0 touched 15 files.
- Suggestion: one "Closing a workflow" section in workflow.md and one routing rule beside doc-types.md's known-issue format, referred to by name. The trigger stays in the always-read canon skill, so canon-retro still loads lazily. Dependency category: in-process. Strength: Worth exploring.

### A6 [minor] The mandatory review snapshot runs on the opt-in trace subsystem
- Location: `cmd_snapshot`, `expire_review_snapshots`, `take_snapshot` in `canon.py`; `ReviewSnapshotTest(TraceCase)`; D003#review-snapshots
- Problem: `canon.py snapshot`, used by every confirmation with tracing on or off, is built from trace's parts: `trace_root`, `trace_git`, `SnapshotSkip`, `snapshot_lock`, `ignore_trace_dir`, the 10 MiB cap, the 5 s lock wait, and `prune_snapshots`, whose `TraceError` it suppresses. Deletion test: removing an opt-in feature breaks reviews. D001's pending r6–r7 work changes the parents `take_snapshot` builds, which reviews also run.
- Suggestion: a work-tree snapshot section with its own error type, root finding and limits; `trace start` (copying objects) and `snapshot` (borrowing them) become its two callers. Dependency category: local-substitutable (a temporary Git repo). Strength: Worth exploring.

### A7 [minor] Machine-level reviewer setup is stored per checkout
- Location: D003 Goal 4 and #reviewers; canon-init's reviewer setup
- Problem: D003 says the cross-family reviewer is set up "per machine", but `reviewer.md` lives in each checkout's `.canon/` beside review scratch. Every clone and linked worktree (this repo puts them under `.worktrees/`) starts without it, and its L2 gates fall back to the manual reviewer until `/canon-init` runs again (README: "Rerun it after a fresh clone").
- Suggestion: read `$XDG_CONFIG_HOME/canon/reviewer.md` first and the checkout's copy second; since sandboxed agents cannot write the machine path, canon-init gives the user the install command, as it does for `trace on`. Strength: Worth exploring.

### A8 [minor] The test suite takes three minutes, and `validate.py` always runs all of it
- Location: `CanonTest.setUp`, `TraceCase.tool` in `tests/test_canon.py`; `run_tests` in `scripts/validate.py`; AGENTS.md Workflow
- Problem: 172 tests run serially, each through subprocesses; every test runs `git init` and `canon.py init`; each CLI call costs about 150 ms because `-B` recompiles the 3,383-line file; three lock tests each wait out the fixed 5 s timeout. `validate.py` cannot skip the suite, and AGENTS.md requires it after any skill change.
- Evidence: `Ran 172 tests in 190.333s`; `--durations` shows the lock tests at 6.1, 5.9 and 5.4 s, most others 1–3 s; ten `python3 -B canon.py --version` runs took 1.5 s.
- Suggestion: run `tests/` only when `canon.py` or `tests/` differ from HEAD; copy one pre-initialized template repo per test instead of setting each up. Strength: Worth exploring.

### A9 [minor] References between skill texts are unchecked
- Location: `broken_links` in `scripts/validate.py`; `Repo.scope_md` in `canon.py`
- Problem: the skills hold 22 `*.md#anchor` links (e.g. `workflow.md#design-problems`, four times) and 10 prose references like "the `canon` skill's workflow (Section)". `validate.py` drops the anchor and checks only that the file exists, and checks no skill names; `canon.py check` reads only docs roots and `AGENTS.md`.
- Suggestion: check anchors with `canon.py`'s slug rule, that each backticked `canon-…` name is an existing skill, and that each "workflow (X)" names a heading in workflow.md. Strength: Worth exploring.

### A10 [minor] `canon-review/security.md` is classified as a project doc
- Location: D002#project-docs (the name list includes `SECURITY`); `Repo.is_doc`
- Problem: the security angle's reference is an instruction file, but its name makes it a doc, so coverage skips it (audit's `canon-review/  4 of 6 files` counts 6 of 7 non-license files) and a commit changing only it is never counted as unchecked.
- Evidence: `canon.py which skills/execution/canon-review/security.md` prints `doc`.
- Suggestion: list its exact path in the `paths` of the design that takes on canon-review (the rule allows exact paths). Strength: Strong.

### A11 [minor] Hard checks: uncovered areas that other skills depend on come first
- Location: the uncovered areas audit lists; D000#capabilities
- Problem: some uncovered files are contracts other skills execute: canon-grill's triage (worker prompt, canon-design, canon-plan, canon-review, as-built step 5), canon-tdd's definition of done (canon-implement), `smells.md` (pasted into every Standards prompt), `writing.md` (rules for every doc), and `agents/openai.yaml` with `validate.py` (the manual-trigger switch; D000's layout row is `none`). A change to any of them alters canon-implement or code review with no design to flag it. The other uncovered skills and files are leaves. Dependency directions do not apply (one module); no relative links across skill directories; no design over 500 lines.
- Suggestion: backfill these first when they next change: one design for skill layout and invocation (AGENTS.md's Skill rules, `validate.py`, `openai.yaml`), one for building a slice (canon-tdd plus the triage workers use). Strength: Worth exploring.

### A12 [minor] One doc type's rules are spread across `canon.py`
- Location: `TYPES`, `TEMPLATES`, `TYPE_FIELDS`/`OPTIONAL_FIELDS`, `default_fields`, `check_doc` (167 lines with per-type branches), `terminal_problems`, `id_entries`/`remap_ids`, `issue_label`
- Problem: changing a type's rule means finding every one of these places; 1c7c1f0 (known issues) changed 154 lines of `canon.py` across them.
- Suggestion: one record per type, with `check_doc` dispatching to it. Dependency category: in-process. Strength: Speculative.

Top recommendation: A2. State the minimum `canon.py` version the skills need and check it at the start of each workflow; a few lines that stop every project with an older copy from getting errors that contradict the skills.
