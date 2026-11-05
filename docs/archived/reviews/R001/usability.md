# R001 usability report

Reviewer: fresh subagent on the session's model, at commit `7c2ebf2`; writing commands ran in scratch Git repos under `.tmp/r001-usability.*`. Findings U1–U13 are R001-F13–F25.

### U1 [major] Auto skills fire in projects that don't use canon, and canon.py then writes canon docs there
- Location: `README.md#install` (`-g` "for every project"); `description` of `canon`, `canon-investigate`, `canon-tdd`, `canon-code-review`, `canon-grill`, `canon-research`, `canon-prototype`; `canon.py new` and `check`
- Problem: the README installs globally, and the auto descriptions trigger on generic requests in any repo ("docs under docs/", "writing or changing code that should be tested", "review a branch, PR", "cause is unclear"). No description or SKILL.md says what to do when the project has no canon block. In a repo with an `AGENTS.md` but no canon block, `canon-investigate`'s first step `canon.py new I flaky-test` succeeds: it creates `docs/investigations/I001-flaky-test.md`, appends a canon index to the user's hand-written `docs/README.md`, and leaves an unignored `.canon/`. In a repo without `AGENTS.md`, `check` replies `run canon.py init at the repo root`, steering the agent to set canon up uninvited, and a refused `new` still leaves an untracked `.canon/id.lock`. Expected: outside canon projects these skills do not trigger, or fall back to their plain discipline, and `canon.py` creates no docs.
- Evidence: run in scratch repos; `git diff docs/README.md` showed the appended `<!-- canon:index:start -->…` block.
- Suggestion: scope every auto trigger to "in a project whose `AGENTS.md` has the canon block", with a one-line fallback in each auto SKILL.md; make `new` and `adopt` refuse when the repo root's `AGENTS.md` has no canon block, pointing to `/canon-init`; take `.canon/id.lock` only after the `AGENTS.md` check.

### U2 [major] `init --hook`, as canon-init step 3 runs it, crashes in the agent sandbox and then blocks setup's own step-4 commit
- Location: `canon-init/SKILL.md` Set up steps 3–4; D004#init (`--hook`); D004#the-canon-init-skill
- Problem: in Cursor's sandbox an existing repo's `.git/hooks` is read-only (D001#switch-and-storage notes Codex keeps `.git` read-only too). `init --hook` dies with a traceback, `OSError: [Errno 30] Read-only file system: '.../.git/hooks/pre-commit'`, exit 1, after creating `AGENTS.md`, `scripts/canon.py` and D000, printing none of its `created` lines and leaving `docs/README.md` without an index. Expected: finish the other steps, then print an actionable line ("cannot write .git/hooks/pre-commit; run `init --hook` yourself outside the sandbox"), as the README does for `trace on`. With the hook installed, step 4's "Commit before restructuring" is rejected: the hook runs `check`, which errors on every file step 5 has yet to fold (`ERROR docs/architecture.md: unknown entry`, exit 1). The skill offers `--no-verify` only for Upgrade, and folding first loses the rename pairing step 4 exists to protect.
- Evidence: in a scratch repo, `init --hook` gave the traceback; `adopt docs/notes/auth.md D` then `git commit` failed in the hook's `check`.
- Suggestion: install the hook after step 11, once `check` passes, or commit step 4 with `--no-verify`; catch `OSError` around the hook write.

### U3 [major] Claude Code projects with an existing `CLAUDE.md` never see the canon block
- Location: `canon-init/SKILL.md` step 7; D004#the-canon-init-skill step 7
- Problem: `init` writes the canon block into `AGENTS.md`, creating it when missing; step 7 adds `@AGENTS.md` only when the project "has no `CLAUDE.md`". A Claude Code project with a `CLAUDE.md` and no `AGENTS.md` (a common layout) gets a new `AGENTS.md` its `CLAUDE.md` never imports, so by the skill's own premise its sessions never read the block (the D000 entry point, the tool path, the tiers). Old doc conventions in `CLAUDE.md` also stay: step 7 cleans only `AGENTS.md`, and the survey leaves docs by name in place.
- Evidence: the import appears only in that branch of step 7 and the matching line of D004; no other step mentions `CLAUDE.md`.
- Suggestion: in step 7, add `@AGENTS.md` to an existing `CLAUDE.md` that lacks it, and apply "remove instructions that conflict with canon" to `CLAUDE.md` too.

### U4 [minor] `/canon-init` has no rule for which flow to run
- Location: `canon-init/SKILL.md`; `README.md` ("Rerun it after a fresh clone to set up the reviewer alone")
- Problem: four sections (Setup, cross-family reviewer, Upgrade, Add a module) and nothing choosing between them; in a set-up project, an agent invoked with no arguments guesses, and Setup step 1 starts a full survey.
- Suggestion: a "Pick the flow" list at the top: no canon block → Setup; copy's `--version` older than the skill's → Upgrade; no `.canon/canon-blind-review/reviewer.md` → reviewer; the user names a module → Add a module.

### U5 [minor] Error messages that stop short of the next step
- Location: `canon.py` (`check`, `new`, `adopt`, `show`, `find`)
- Problem: `check`'s `ERROR docs/architecture.md: unknown entry; allowed: …` names no remedy (`adopt <file> <type>`, or move into `guides/`). `new D Auth_Tokens` → `canon: slug must be kebab-case` with neither the slug nor an example. `new P x --from D002` → `canon: --from takes an accepted or active design` without saying D002 is a draft that has not passed its gate. `adopt nonexistent.md D` → `is not a markdown file` though the file does not exist (D004#adopt specifies this wording). `show D002#nope` → `has no section #nope` without listing the slugs. `find R001` → `no match` though `find --archived R001` finds it.
- Suggestion: name the value and the next command in each message.

### U6 [minor] The `--base` errors give no cause, which is the usual CI failure
- Location: canon-init step 9; D004 setup step 9
- Problem: `check --base origin/main` → `canon: cannot diff against origin/main...HEAD`; `affected --base nosuchref` → `canon: cannot diff against nosuchref`. In CI the cause is usually a missing ref or a shallow fetch, and the message says neither.
- Suggestion: say which ("origin/main is not a known ref" or "no merge base with HEAD") and suggest `git fetch` with enough depth.

### U7 [minor] `which` doesn't flag paths that don't exist
- Location: `canon.py which`; the docs step in `workflow.md`
- Problem: `which nonexist.txt` → `no design`; run from `src/auth/`, `which src/auth/login.py` resolves to `src/auth/src/auth/login.py` and still prints `D003`. Both exit 0, so a typo gets a confident, wrong answer.
- Suggestion: mark paths neither on disk nor in Git as `(missing)`.

### U8 [minor] Phase-closing commands use Cursor and Claude Code syntax only
- Location: `workflow.md#flows`; closing lines of `canon-design`, `canon-plan`, `canon-implement`, `canon-review`, `canon-retro`
- Problem: the skills tell the user to run `/canon-plan D012`; Codex invokes skills as `$canon-plan` (`README.md#skills`, `canon-agent-writing/SKILL-MECHANICS.md`), so a Codex user gets a command that does not work.
- Suggestion: say once in `workflow.md#flows` to give the host's form of the command.

### U9 [minor] The canon block doesn't say where to get the skills
- Location: the `canon.py` AGENTS template; D004#init
- Problem: the block says the repo "follows the canon documentation system (`canon` skill)" and "the review gate defined by the `canon` skill"; a teammate's or CI agent without the skills cannot find the rules the block requires.
- Suggestion: add one clause naming the install command, `npx skills add BigTailFox/skills`.

### U10 [minor] The README states no requirements
- Location: `README.md#install`
- Problem: no mention of Python 3.8+, `python3` on PATH, or Git, though every flow runs `python3 <copy>` (on Windows `python3` is often not on PATH). The first install command offers an interactive skill picker right after "install all of them".
- Suggestion: a Requirements line, and "select every skill" beside the interactive command.

### U11 [minor] `-h` texts are thin and differ from the documented usage
- Location: `canon.py` argparse help; the Tool table in `canon/SKILL.md`
- Problem: `archive -h` lists no valid statuses; `show -h` does not explain `ref` / `ID#slug`; `rename` and `--title` have no text; `trace end -h` lists no outcomes; `trace on/off --here` has none; `which -h` omits its `doc` and `no design` outputs. `renumber` takes `[--base BASE]` as optional while the Tool table and `canon-sync` give it as required, and `renumber D002` with no collision silently printed `D002 -> D003`.
- Suggestion: add help strings; make `renumber` require `--base` or a reported collision.

### U12 [minor] `init --root` with a typo silently creates a module
- Location: D004#init
- Problem: `init --root nonexist` prints `created nonexist/AGENTS.md` and `created nonexist/docs/README.md`.
- Suggestion: refuse a `--root` that is not an existing directory.

### U13 [minor] `canon-retro`'s closing-step trigger is past the 190-character cut
- Location: `canon-retro` frontmatter; AGENTS.md's rule on trigger placement
- Problem: the first sentence takes 88 characters, pushing "or when a canon workflow's closing step calls for one" past character 190, which hosts truncate. Low impact, since workflows invoke it by name.
- Suggestion: shorten the first sentence.

Top recommendation: U1. Make the auto skills and `canon.py new`/`adopt` apply only in projects whose root `AGENTS.md` has the canon block: the README tells everyone to install globally, so a routine debugging or review request in any repository can write canon docs into it today.
