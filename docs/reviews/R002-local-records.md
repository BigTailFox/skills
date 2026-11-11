---
status: open
created: 2026-11-10
updated: 2026-11-11
revision: 1
modules: [canon]
summary: Open findings from the retro notes, canon friction log and blind-review outputs kept only in .canon/, and what to restore when moving machines.
refs: [C001, D000, D001, D002, D003, D004]
---

# R002: Open items from local retro and review records

## Scope

- Commit: `990e6cd0d3f026d3a73e747528302a721e24f216`.
- Records: the files under `.canon/` that stay on the machine that wrote them, from 2026-10-15 to 2026-11-05:
  - `canon-retro/notes.md`: 12 retro causes with their events and states, attached as [notes.md](R002/notes.md).
  - `canon-retro/skills.jsonl`: 10 entries of friction in canon's own skills and `canon.py`, attached as [skills.jsonl](R002/skills.jsonl).
  - `canon-blind-review/`: the reviewer outputs of 23 blind reviews, the gates of D000 to D005, P001 and P002 and the code reviews from P001 through R001's fixes.
- Modules and paths: canon (`skills/`, `tests/`) and `scripts/validate.py`.
- Angles: functional, usability, architecture.
- Each item was checked against the commit. Findings are the items whose cause is still present and that no other doc tracks. Left out are the items fixed since and the open items tracked in [D002§known-issues: known issues](../designs/D002-overview-and-as-built.md#known-issues), [D003§known-issues: known issues](../designs/D003-subagents.md#known-issues), [D004§known-issues: known issues](../designs/D004-project-setup.md#known-issues) and [C001: Canon backlog](../concepts/C001-canon-backlog.md). Of `skills.jsonl`'s entries, only R002-F2 and R002-F3 are still open.

## Findings

| ID | Severity | Finding | Disposition |
|----|----------|---------|-------------|
| R002-F1 | minor | functional: Three `git` calls besides `audit`'s (D002-K2) still read a failing Git as an empty result | fixed 8f4f34c |
| R002-F2 | minor | functional: `check` takes canon's own comment markers, quoted in inline code or a fenced block, for leftover template guidance | fixed 8f4f34c |
| R002-F3 | minor | usability: A gate's reviewer files are named by doc id and role, so the next revision's gate overwrites the previous one's | moved D001 |
| R002-F4 | minor | functional: D002 omits the unreadable-checkout refusal of `new`, `adopt` and `renumber` | fixed e01ecd5 |
| R002-F5 | minor | architecture: D000 revision 2 relaxed a Dependencies rule under a same-model gate, and whether it was L2 is unanswered | moved D007 |
| R002-F6 | minor | functional: `validate.py` does not measure D001's 40-token call-site budget | fixed f4d5a01 |
| R002-F7 | minor | functional: `OutsideCheckoutTest` finds the outside-Git tests by matching their source text | fixed 8f4f34c |
| R002-F8 | minor | functional: Test repositories sit directly in the OS temp directory, so a stray `../` write lands in the shared `/tmp` | fixed 8f4f34c |
| R002-F9 | minor | usability: Standards in a project's kept `CONTRIBUTING.md` or `CLAUDE.md` stay outside the designs after setup | open |
| R002-F10 | minor | usability: `canon-review/functional.md` calls unspecified behavior a spec gap or code to remove, without as-built revisions | fixed 80b9688 |
| R002-F11 | minor | usability: `canon-blind-review`'s manual fallback names `/canon-init` in slash form | fixed 80b9688 |
| R002-F12 | minor | usability: In Cursor, an interrupted reviewer command reran three times, and auto-review blocked a reviewer's `canon.py` calls | open |

## Details

### R002-F1: Git failures read as empty results

- Location: `canon.py`, `require_clean_merge` (`ls-files -u`), `Repo.__init__` (`has_head` from `rev-parse --verify -q HEAD`) and `Repo._list_files` (`ls-files -co`).
- Problem: a failing `ls-files -u` reads as no conflicts, so `init` and `adopt` skip the unmerged-entries refusal D004 states. A failing `rev-parse HEAD` reads as an unborn branch, so `history_ids` returns nothing and `new` can reuse an id, the risk R001-F4 removed for a checkout Git cannot read. A failing `ls-files` reads as no files, so `check` passes with 0 docs.
- Suggestion: tell a failure from an empty result in each call, together with D002-K2's `audit`. L0, with regression tests and a `CANON_VERSION` bump.
- Source: code review of f9226e2, spec F4 and standards F2 and F6.

### R002-F2: Guidance check matches quoted markers

- Location: `canon.py`, `check_doc`: `if GUIDANCE in doc.text`.
- Problem: a doc that quotes one of canon's own comments, such as the index start marker, in inline code or a fenced example is reported as holding template guidance, an error once the doc is past its gate. D005 and D004 revision 4 each had to reword such a quote.
- Suggestion: skip inline code and fenced blocks, or match only the guidance comments the templates hold. L0, with a regression test and a `CANON_VERSION` bump.
- Source: `skills.jsonl`, 2026-10-30 and 2026-11-05.

### R002-F3: The next gate overwrites a gate's reviewer files

- Location: [D001§review-files: review files](../designs/D001-skill-telemetry.md#review-files) ("A gate's topic is its doc id") and `canon-blind-review/SKILL.md`, Reviewers, which also replaces `snapshot.txt`.
- Problem: saving D001 revision 8's `same-model.md` overwrote revision 7's. Earlier rounds survived only where a session had moved them into `r1/` or `r6/` by hand, and D000's revision 1 round had to be moved before its revision 2 gate.
- Suggestion: name a gate's topic by revision, such as `D001-r8`, or move the previous gate's files into `r<N>/` before a new first round. L1 revision of D001.
- Source: `skills.jsonl`, 2026-11-05.

### R002-F4: Unreadable-checkout refusal missing from D002

- Location: [D002§project-overview-d000: project overview](../designs/D002-overview-and-as-built.md#project-overview-d000) states only `canon: cannot read the history of HEAD`, for a failing history query with a HEAD commit; the code is `unreadable_checkout` and `Repo.history_ids`.
- Problem: when a directory at or above the working directory holds `.git` but Git fails there (Git missing, dubious ownership, `GIT_CEILING_DIRECTORIES`), `new`, `adopt` and `renumber` exit with `canon: cannot read the history of HEAD in <dir>: <reason>`, on an unborn branch too. Callers see this behavior and no design states it.
- Suggestion: record it in D002 as an as-built revision. L1.
- Source: code review of f9226e2, spec F2 and standards F1 and F5.

### R002-F5: Tier of D000 revision 2

- Location: [D000§dependencies: dependencies](../designs/D000-project-overview.md#dependencies) ("Nothing under `skills/` depends on it"); D000's `reviewers: [claude-opus-5.5]`.
- Problem: revision 2 changed "Nothing in the module depends on it" to "Nothing under `skills/` depends on it". The change itself is the user's decision (R001-F31), but Dependencies are spec, and the `canon` skill makes a change to the architecture L2, which takes a cross-family reviewer. The gate ran one same-model reviewer, whose question on the tier got no answer.
- Suggestion: the user settles the tier. If L2, run D000 revision 2's gate again with the cross-family reviewer.
- Source: D000 revision 2 gate, the same-model reviewer's Questions.

### R002-F6: Call-site token budget unmeasured

- Location: [D001§budgets: budgets](../designs/D001-skill-telemetry.md#budgets), at most 40 `cl100k_base` tokens per call site; `scripts/validate.py` measures none of D001's text budgets.
- Problem: the Standards reviewer of D003 revision 2's implementation found `canon-implement`'s slice call site over 40 tokens. Counting took three attempts: tiktoken is not installed and `python3 -m pip` is missing; `uv run --no-project --with tiktoken python3` worked.
- Suggestion: have `validate.py` check D001's text budgets when tiktoken can be imported and print the `uv run` command otherwise. L0.
- Source: retro cause `call-site-budget-unchecked`.

### R002-F7: Outside-Git guard matches source text

- Location: `tests/test_canon.py`, `OutsideCheckoutTest`.
- Problem: the guard finds the tests that need a directory outside every checkout by searching their source for `self.outside_checkouts()`. A new such test that uses `self.tmpdir()`, or reaches the helper indirectly, would bring back R001-F27 (tests writing docs into the checkout around `TMPDIR`) while the guard still passes.
- Suggestion: have the helper that runs `canon.py` fail when its working directory lies in no test repository and did not come from `outside_checkouts()`, so the property holds by construction. L0.
- Source: code review of eb76e61, spec F2 and standards F3.

### R002-F8: Test repositories in the shared temp directory

- Location: `tests/test_canon.py`, `CanonTest.tmpdir` (`tempfile.TemporaryDirectory()` directly under `TMPDIR`); `AGENTS.md` runs `validate.py` with the system's `TMPDIR`.
- Problem: a red run of `test_init_refuses_a_copy_path_that_is_absolute_or_outside_the_repository` let the old `init` write `../canon.py`, which landed in the shared `/tmp`, and deleting it waited for the user's approval.
- Suggestion: create one directory per test run under `TMPDIR` and each test's directories inside it, so a stray `../` stays in the run's directory and is cleaned up with it. L0.
- Source: retro cause `test-repos-in-shared-tmp`.

### R002-F9: Standards in kept project docs

- Location: [D002§setup: setup](../designs/D002-overview-and-as-built.md#setup) and `canon-init`, steps 1, 5 and 7.
- Problem: setup keeps docs by name such as `CONTRIBUTING.md` and `CLAUDE.md`, and step 7 removes only the `CLAUDE.md` instructions that conflict with canon. Coding standards stated there stay outside the designs that own their topics, where the Standards reviewer looks. The D002 revision 3 gate declined this only as a gap that setup had before that revision.
- Suggestion: have setup move each such standard into the design that owns its topic and leave a link in its place. L1 revision of D002.
- Source: D002 revision 3 gate, same-model F3.

### R002-F10: Functional reference without as-built revisions

- Location: `skills/execution/canon-review/functional.md`, Gaps: "Behavior the code has but no design specifies: a spec gap, or code to remove."
- Problem: canon records such behavior with an as-built revision before anything changes it, but the reference offers functional reviewers only the other two readings. Only the archived P002 Log records this.
- Suggestion: name the as-built revision as the usual disposition of such a gap. L0.
- Source: P002 Log.

### R002-F11: Slash-form command in canon-blind-review

- Location: `skills/execution/canon-blind-review/SKILL.md`, Manual fallback: "(`/canon-init` sets up a missing reviewer)".
- Problem: the `canon` skill tells sessions to give commands in the host's form, such as `$canon-init` in Codex, but `canon-blind-review` can run without the session reading that rule, and Codex does not accept the slash form.
- Suggestion: name the skill (`the canon-init skill`) instead of the command. L0.
- Source: code review of 3ab357c, spec confirmation.

### R002-F12: Cursor host behavior around reviewers

- Problem: during D002's gate, the host reran an interrupted cross-family `codex exec` three times under one tool call, about 4.5 minutes each, the first two writing the same `<out>` at once. In the same gate, Cursor's auto-review blocked the same-model reviewer from running `canon.py`, so it checked code facts by reading files only.
- Suggestion: set up Cursor on each machine so reviewers may run the read-only `canon.py` queries (`show`, `find`, `which`, `affected`, `check` without `--fix`). For the rerun, no fix is known; the retro raises it if it recurs.
- Source: retro causes `host-reran-interrupted-command` and `auto-review-blocks-reviewer-commands`.

## Moving to another machine

- Retro records: copy the attachments back, so `canon-retro` keeps each cause's state, such as `worker-command-stall` declined: `mkdir -p .canon/canon-retro && cp docs/reviews/R002/notes.md docs/reviews/R002/skills.jsonl .canon/canon-retro/`.
- Cross-family reviewer: the reviewer file stays behind (D003-K6). Install and sign in to the Codex CLI, then run the `canon-init` skill's reviewer setup. The old machine's file named one reviewer, recorded as `gpt-6-astra-high`, run from the repo root outside the host's sandbox, since codex writes `~/.codex`: `codex exec -m gpt-6-astra -c model_reasoning_effort="high" -s read-only --color never -o <out> - < <prompt> > <out>.log 2>&1`.
- Upstream for porting: `.canon/upstream/mattpocock-skills` was a clone of `https://github.com/mattpocock/skills`, last fetched at `5beb35b` (2026-10-19).
- Nothing else in `.canon/` needs to move: the 10 trace events are leftovers of tests that wrote into this checkout before eb76e61 (R001-F27), and the rest is review snapshots, subagent ids and scratch.
