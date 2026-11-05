# R001 functional report

Reviewer: fresh subagent on the session's model, at commit `7c2ebf2`; behavior verified in scratch Git repos under `.tmp/r001-functional.*`. Findings F1–F7 are R001-F26–F32.

### F1 [major] D001 revision 6 is not implemented and no plan carries it
- Location: `canon.py` `trace_start`, `take_snapshot`; `tests/test_canon.py`; D001#commands (`start`), D001#snapshots step 4, D001#delivery-and-acceptance (the `as_built` scenario, Pilot exit), D001#replay; `canon-implement/SKILL.md` §2 step 2
- Problem: r6 (e08f898) says a `gate` whose doc has an `as_built` naming a commit records that commit's tree as the snapshot's second parent. `trace_start` never reads `as_built`, `take_snapshot` builds one parent, and no test covers the scenario. `docs/plans/` is empty and D001 lists no known issue, so nothing carries it. r7's in-repo part (open a slice unit only when none is open) is already in `canon-implement` (98ab39c, 26 minutes after r7), so `implemented: 5` is right only because r6 is missing; once r6 lands it goes straight to 7. Meanwhile every traced as-built gate loses the code it records, and the Pilot exit "every snapshot reproduces … the code an as-built gate records" cannot pass.
- Evidence: run in a scratch repo: D001 given `as_built: <HEAD~1>`, tracing on with an isolated `XDG_CONFIG_HOME`, `trace start gate D001 --tier L1 --base HEAD`; the snapshot commit has one parent and `git show <snap>^2:src/a.py` prints `invalid object name`. No `as_built` in the trace code, no `^2` in the tests.
- Suggestion: missing code, the spec rightly leading. Plan it: `trace_start` reads a gate doc's `as_built` and keeps it when it names a commit; `take_snapshot` adds a second parentless commit holding that tree; add the D001 scenario as a test; the docs step sets `implemented: 7`.

### F2 [major] Tests that expect a directory outside Git run `canon.py` in whatever Git repo holds TMPDIR
- Location: `CanonTest.tmpdir` in `tests/test_canon.py`, used by 8 tests (`AsBuiltTest.test_worktree_passes_…`, `ReachTest.test_outside_git_…`, `SkillDigestTest.test_a_manifest_…`, `SnapshotTest.test_a_directory_outside_git_…`, `TraceTest.test_the_trace_directory_is_the_nearest_…`, `HistoryIdTest.test_outside_git_ids_…`, `PruneTest.test_outside_git_prune_…`, `ReviewSnapshotTest.test_a_snapshot_that_cannot_be_taken_…`); `run_tests` in `scripts/validate.py`; AGENTS.md Workflow; D000#dependencies
- Problem: these tests assume `tempfile`'s directory is outside every Git work tree and never check. When it is inside one, `canon.py` finds that checkout (through `git rev-parse`, or by walking up to `.git` in `trace_root`) and runs `init`, `new D`, `check --fix`, `trace` and `snapshot` there. AGENTS.md puts temp files inside the repo (`.tmp/`), never `/tmp`, and requires `validate.py` before every commit, which runs the suite with the inherited `TMPDIR`. An agent that points `TMPDIR` at a plain `.tmp/<dir>` makes the suite create docs and rewrite the index in this repository.
- Evidence: run: `TMPDIR=<git-inited scratch>/t python3 -m unittest discover -s tests` ran 172 tests with 3 failures and 5 errors, all these cases, and left `AGENTS.md`, `scripts/canon.py`, `.gitattributes`, `.gitignore` and `docs/designs/D000…D006` in the scratch repo. This review hit it for real: the first architecture run, with `TMPDIR` in a non-Git `.tmp/` directory, created nine untracked drafts `D006-area.md`…`D014-x.md` (the tests' default slugs) in this repository's `docs/designs/` and rewrote `docs/README.md`; they were deleted before the rerun.
- Suggestion: a defect in the tests. Create their directory where `git rev-parse` fails, or skip when it succeeds (`GIT_CEILING_DIRECTORIES` alone does not stop `trace_root`'s `.git` walk); or have `validate.py` give the suite a fresh `TMPDIR` and refuse one inside a work tree.

### F3 [minor] D004#adopt and D005's format and check have almost no tests
- Location: `AdoptTest`, `IndexTest` in `tests/test_canon.py`; D004#adopt, D005#format, D005#check
- Problem: `AdoptTest` has only two percent-encoding tests; nothing covers type aliases, project lookup, the default slug, the `<id>: <text>` and `<id>§<anchor>:` link texts, the dropped-frontmatter message, the H1 rewrite and prepend, appended sections, `git mv` versus plain rename, or any of the five error messages. Nothing asserts the index's group headings and order, `?` placeholders, sub-design order, `No documents.`, the archived README's layout, or `ERROR <path>: index out of date` (only an `assertNotIn`).
- Evidence: searched the tests, then ran the behaviors in scratch; they match the spec today (e.g. `[D002§goals: the notes]`, `[D002: D002]`, `[D001A: ?](…) · ? · ?`, `# Archived docs`).
- Suggestion: add regression tests; no code change. Both designs are as-built, so tests are what holds the behavior.

### F4 [minor] `adopt` breaks links to the adopted file's H1 anchor
- Location: `adopt_doc`, `rewrite_for_moves` in `canon.py`; D004#adopt
- Problem: `adopt` rewrites the H1 to `# <id>: <title>`, changing its anchor (`#auth-notes` → `#d002-auth-notes`); links to the old anchor, in the file and elsewhere, stay, and `check` then fails. D004 says links follow the move and is silent on the H1 anchor.
- Evidence: run: adopting a file containing `[self](#auth-notes)` gives `ERROR docs/designs/D002-auth-notes.md:15: missing anchor #auth-notes`.
- Suggestion: a spec gap. Rewrite links to the H1 anchor in the same pass, or state in D004 that they break.

### F5 [minor] The canon skill's Tool table disagrees with the CLI
- Location: `skills/governance/canon/SKILL.md`#tool; `main()`, `check_overview`, `cmd_audit` in `canon.py`
- Problem: the table reads `renumber ID|PATH --base REF`, "only for collisions"; the CLI is `renumber TARGET [NEW] [--base REF]`, and `check`'s error for a D000 under a module's docs root tells the agent to run `canon.py renumber <path>` with no `--base` and no collision. `affected` also accepts undocumented `FILE...` arguments. The table says `audit` lists "idle open docs other than concepts", but the code also skips active designs.
- Evidence: read from the code (around lines 1193, 2264–2267, 3298–3326).
- Suggestion: the skill text is stale. Document the optional new id and `--base` and the D000 case; document or drop `affected FILE`; say active designs are exempt from the idle list.

### F6 [minor] `validate.py` does not enforce "no `SKILL.md` outside skills/<category>/<name>/"
- Location: `scripts/validate.py`; AGENTS.md (first rule); D000#capabilities (layout row), D000#dependencies
- Problem: `validate.py` only looks at `skills/<category>/<dir>/SKILL.md`; a stray or nested `SKILL.md` passes and the `skills` CLI would install it. Only a manual `npx skills add . --list` would catch it.
- Evidence: run: a scratch repo with one valid skill plus `docs/SKILL.md` and `skills/execution/canon-x/templates/SKILL.md` gave `1 skill(s) checked, 0 problem(s)`.
- Suggestion: a tooling gap. Fail on any tracked `SKILL.md` not exactly at `skills/<category>/<name>/SKILL.md`.

### F7 [minor] D001's `implemented` means delivery step 1 only
- Location: D001 frontmatter, D001#analysis, D001#delivery-and-acceptance; the canon skill's Frontmatter section (`implemented`)
- Problem: a81ad5f set `implemented: 5`, yet `scripts/trace_report.py` (D001#analysis, with a specified CLI) and the replay harness do not exist, while the canon skill defines `implemented` as "the revision the code fully implements". So `which`, `find` and `affected` show no "spec leads code" note for that missing interface, and no plan carries it.
- Evidence: `ls scripts` shows only `validate.py`; `git show a81ad5f`.
- Suggestion: the spec is stale. State in D001 that `implemented` tracks delivery step 1 and the analysis waits for the pilot, or move analysis and replay into a later design.

Top recommendation: F2. Guard the outside-Git tests first: a small change that stops the `validate.py` run AGENTS.md requires from writing docs into this repository, protecting every later fix.
