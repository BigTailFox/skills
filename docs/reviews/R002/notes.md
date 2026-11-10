## no-reviewer-file: applied 78115a5
- 2026-10-15 e3cebf31-3ae2-4a4b-95c3-ae3b6a6a547e: D001's review gate found no `.canon/canon-blind-review/reviewer.md`, so the agent had to ask the user how to run the cross-family reviewer (AskQuestion in this conversation; answer: the local Codex CLI, read-only)
- 2026-10-15 e3cebf31-3ae2-4a4b-95c3-ae3b6a6a547e: P001's review gate again found no reviewer file and ran the Codex command remembered from D001's gate instead of the workflow's route (`.canon/canon-blind-review/P001/cross-family.log`)
- 2026-10-15 e3cebf31-3ae2-4a4b-95c3-ae3b6a6a547e: set raised
- 2026-10-16 e3cebf31-3ae2-4a4b-95c3-ae3b6a6a547e: P001's code review again found no reviewer file and ran the remembered Codex command for its first round and its confirmation (`.canon/canon-blind-review/P001-code-review/cross-family.log`, `cross-family-confirm.log`)
- 2026-10-29 57059d41-9546-4eeb-947b-125448fcc907: set applied 78115a5 (`canon-init`'s reviewer setup, which wrote this machine's `.canon/canon-blind-review/reviewer.md` on 2026-10-22; the events above predate the file, not the commit, and none has followed it)

## worker-command-stall: declined
- 2026-10-15 e3cebf31-3ae2-4a4b-95c3-ae3b6a6a547e: P001's S2 worker stalled about three hours on a tool call that never returned, until the user interrupted it; resumed inside the sandbox with a timeout, it finished in minutes (P001 Log, S2 entries)
- 2026-10-16 e3cebf31-3ae2-4a4b-95c3-ae3b6a6a547e: set raised
- 2026-10-16 e3cebf31-3ae2-4a4b-95c3-ae3b6a6a547e: set applied 87e79c1
- 2026-10-21 e3cebf31-3ae2-4a4b-95c3-ae3b6a6a547e: set declined (the user reported the stall came from the laptop being closed overnight, not from how the worker ran commands; where and how long tests run is the project's own setting; 87e79c1 reverted in 0a30bdf)

## stalled-subagent-replaced: applied 98ab39c
- 2026-10-22 bf8d565b-1b0f-4b3f-8ed8-b5f646e53133: D002's same-model reviewer stopped twice before reporting, interrupted with the turn after about 17 minutes and then `PING timed out` in the background, and each time a new reviewer was launched instead of resuming it; the user corrected this, and 79057360, resumed with a request to continue, finished its review (the user's message in this conversation; `.canon/canon-blind-review/D002/same-model-id.txt` lists two reviewers)
- 2026-10-22 bf8d565b-1b0f-4b3f-8ed8-b5f646e53133: set raised
- 2026-10-22 bf8d565b-1b0f-4b3f-8ed8-b5f646e53133: set applied 98ab39c (D003 r2 in 5b69dfb, with D001 r7 in 5c80094)

## host-reran-interrupted-command: noted
- 2026-10-22 bf8d565b-1b0f-4b3f-8ed8-b5f646e53133: the interrupted cross-family codex call of D002's gate ran three times under one tool call, about 4.5 minutes each, the first two overlapping while writing the same `<out>` (shell tasks 847582 to 847584; `.canon/canon-blind-review/D002/cross-family.md.log`)
- 2026-10-22 bf8d565b-1b0f-4b3f-8ed8-b5f646e53133: set noted

## auto-review-blocks-reviewer-commands: noted
- 2026-10-22 bf8d565b-1b0f-4b3f-8ed8-b5f646e53133: Cursor's auto-review blocked D002's same-model reviewer from running `canon.py`, so it checked code facts by reading files only (`.canon/canon-blind-review/D002/same-model-79057360.md`, first line)
- 2026-10-22 bf8d565b-1b0f-4b3f-8ed8-b5f646e53133: set noted

## call-site-budget-unchecked: noted
- 2026-10-22 bf8d565b-1b0f-4b3f-8ed8-b5f646e53133: the Standards reviewer of the D003 r2 implementation found `canon-implement`'s slice call site over D001's 40-token budget, which `scripts/validate.py` does not measure (`.canon/canon-blind-review/resume-stopped-subagents/standards.md`, F1)
- 2026-10-22 bf8d565b-1b0f-4b3f-8ed8-b5f646e53133: counting the tokens took three attempts, since tiktoken is not installed and `python3 -m pip` is missing; `uv run --no-project --with tiktoken python3` worked (this conversation's shell output)
- 2026-10-22 bf8d565b-1b0f-4b3f-8ed8-b5f646e53133: set noted

## scratch-outside-workspace: applied ab8aa25
- 2026-10-23 9359d03d-71b1-4d58-ad2c-56b9a9b65b22: P002's S1 worker wrote its benchmark scripts and generated checkout to `/tmp/canon-s1-bench/`, outside the workspace, where writes wait for the user's approval; the user corrected it and asked for a rule that temporary directories go under the repository's `.tmp/` (the user's message in this conversation; the S1 worker's report)
- 2026-10-23 9359d03d-71b1-4d58-ad2c-56b9a9b65b22: set applied ab8aa25 (AGENTS.md Workflow line and `.tmp/` in `.gitignore`, at the user's request)

## scratch-deletion-waits-for-approval: applied ffaeb9c
- 2026-10-23 dc113232-b36a-4733-9583-e1aa9f8cc122: P002's S3 worker deleted its scratch under `.tmp/` with `rm -rf` three times, twice to reset `.tmp/s3-scratch` and once to clean up, and the S4 worker once to reset `.tmp/s4log`; file-deletion protection makes each such command wait for the user's approval, and the user asked for a rule that leaves `.tmp/` alone until it passes a size limit such as 32 GB (the user's message in this conversation; the S3 and S4 workers' shell commands in session 9359d03d-71b1-4d58-ad2c-56b9a9b65b22; the protection's behavior as found in session 111e02b7-ce8d-419d-864d-dba8428ad0c1)
- 2026-10-23 dc113232-b36a-4733-9583-e1aa9f8cc122: set applied ffaeb9c (AGENTS.md Workflow line, at the user's request)
- 2026-10-23 9359d03d-71b1-4d58-ad2c-56b9a9b65b22: this session deleted scratch under `.tmp/` after ffaeb9c had landed, resetting `.tmp/dry-backfill` and `.tmp/dry-upgrade` before P002's S8 dry runs and deleting `.tmp/D000-reviewed.md`, `.tmp/.tmp_canon_view.py` and `.tmp/d000-tail.md` after D000's confirmation round; the `AGENTS.md` it loaded at its start predates ab8aa25 and ffaeb9c, while the workers it launched later read the rule and left their scratch, such as `.tmp/review-fixes.4H2u/` (this conversation's shell commands; ffaeb9c, fix=absent from the session's loaded `AGENTS.md`)

## test-repos-in-shared-tmp: noted
- 2026-10-29 e66d900a-e453-4463-8f8b-71e3e7b35f73: a red run of `test_init_refuses_a_copy_path_that_is_absolute_or_outside_the_repository` let the old `init` write `../canon.py` from its test repository, which `CanonTest.tmpdir` puts directly in the OS temp directory, so the copy landed in the shared `/tmp/canon.py` and deleting it waited for the user's approval (this conversation's test output `created ../canon.py` and the approved `rm /tmp/canon.py`)
- 2026-10-29 e66d900a-e453-4463-8f8b-71e3e7b35f73: set noted

## zsh-variable-as-command: applied 268c3bd
- 2026-10-29 e66d900a-e453-4463-8f8b-71e3e7b35f73: `C="python3 skills/.../canon.py"; $C ...` failed with "no such file or directory" because zsh does not word-split unquoted variables; a shell function worked (this conversation's shell output before compaction)
- 2026-10-29 e66d900a-e453-4463-8f8b-71e3e7b35f73: set noted
- 2026-10-30 0f81950e-6c0b-4ce6-82b8-d2b03ef5a9eb: the D005 as-built check in `.tmp/d005-asbuilt.ghJd` ran `C="python3 -B .../canon.py"; $C init` and every `$C` call failed with "no such file or directory"; a shell function worked on the rerun (this conversation's shell output)
- 2026-10-30 0f81950e-6c0b-4ce6-82b8-d2b03ef5a9eb: set raised
- 2026-10-30 0f81950e-6c0b-4ce6-82b8-d2b03ef5a9eb: set applied 268c3bd (AGENTS.md Workflow line)

## background-reviewer-result-unseen: later C001
- 2026-11-05 004bd37b-7dac-43c4-a85c-b59020a3c6a7: D001 r8's same-model reviewer a65d4231, resumed in the background for its confirmation, finished at 22:57 with approve, but no completion notice reached the session, which waited until the user asked at 23:02 whether it was stuck (the subagent transcript's mtime 22:57:01 and the user's message "你是不是卡住了")
- 2026-11-05 004bd37b-7dac-43c4-a85c-b59020a3c6a7: set raised
- 2026-11-05 004bd37b-7dac-43c4-a85c-b59020a3c6a7: set later C001 (990e6cd)

## scratch-command-ran-in-workspace: applied 268c3bd
- 2026-10-30 0f81950e-6c0b-4ce6-82b8-d2b03ef5a9eb: commands meant for the scratch repository `.tmp/d005-asbuilt.ghJd`, given to the Shell tool through `working_directory` with no `cd` in the command, ran in the workspace: `canon.py new` created `docs/concepts/C001-idea.md`, `docs/designs/D001A-child.md` and `docs/designs/D006-sub-thing.md`, and `docs/README.md` was deleted and overwritten; restoring it took a `git checkout` and a deletion the user had to approve (the command's output listing this repository's D000 to D005, then `git status`)
- 2026-10-30 0f81950e-6c0b-4ce6-82b8-d2b03ef5a9eb: set raised
- 2026-10-30 0f81950e-6c0b-4ce6-82b8-d2b03ef5a9eb: set applied 268c3bd (AGENTS.md Workflow line)
