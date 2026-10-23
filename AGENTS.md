# AGENTS.md

This repository is a personal collection of agent skills, installed and distributed with `npx skills` (vercel-labs/skills). Each skill is a directory containing a `SKILL.md`, under `skills/execution/` or `skills/governance/`.

Do not commit a `SKILL.md` outside `skills/`, templates and examples included: the CLI would treat it as an installable skill. Do not add custom install scripts either; installing, updating and removing are left to `npx skills`.

## Categories

- `governance/`: builds and maintains a documentation system that follows the project's lifecycle and serves as the shared standard, guide, record and information hub for long-running development across sessions and models.
- `execution/`: does concrete development work (clarifying requirements, writing code, testing, debugging, reviewing), and reads and writes project docs only through the documentation system governance defines.
- When unsure, ask whether the skill builds or maintains the documentation system itself, or uses it to get development work done. The former goes in `governance/`, the latter in `execution/`.

## Porting upstream skills

`execution/` is mostly ported from [mattpocock/skills](https://github.com/mattpocock/skills) (MIT). When porting:

- Keep upstream links, attribution and change notes out of `SKILL.md` and the files it references; they take up context and distract the agent.
- Put provenance in the skill directory: `LICENSE` is the upstream license copied verbatim, and `NOTICE` names the upstream repository and skill and states that it was modified.
- Follow only the governance layer's doc conventions. Upstream conventions worth keeping (`GLOSSARY.md`, ADRs, the issue tracker, `setup-matt-pocock-skills` and so on) are absorbed into governance first and then referenced by skills; a ported skill no longer depends on or mentions upstream conventions.

## Skill rules

- The directory name is the skill name: lowercase letters, digits and hyphens, at most 64 characters. Skill names are unique across the whole repository, across categories too.
- Every skill belongs to the canon documentation system: the core skill is `canon`, and every other skill is named `canon-<task>`, with the task word matching a doc type where possible (`canon-design`, `canon-plan`, `canon-investigate`).
- `npx skills` installs skills flat by name, without the category directories. Skills refer to each other by name (e.g. "follow the `canon` skill"), never by relative paths across skill directories; to run `canon.py`, use the path given in the project's `AGENTS.md`.
- `SKILL.md` starts with YAML frontmatter containing:
  - `name`: equal to the directory name.
  - `description`: non-empty, at most 1024 characters, in the third person, and free of `: ` (it breaks YAML parsing). An auto-invoked skill states what it does in one short sentence, followed at once by "Use when …" triggers and, where needed, when it does not apply; keep the trigger words within the first 190 characters, because hosts truncate long descriptions. A manual skill gets a one-line summary for humans.
- Skills are manual by default: add `disable-model-invocation: true` to the frontmatter (read by Claude Code and Cursor), and put `agents/openai.yaml` in the skill directory with `allow_implicit_invocation: false` under `policy:` (read by Codex). Remove both only from a skill that truly needs to trigger from context; `validate.py` checks that they come in pairs.
- Keep the `SKILL.md` body under 500 lines; move details into other `.md` files in the same directory, linked directly from `SKILL.md` (one level deep).
- Write only what the agent does not already know; skip common knowledge. Give one default approach instead of a list of options.
- Use `/` in paths, and write nothing time-sensitive (such as "before 2026, use the old API").
- Scripts shipped with a skill go in `scripts/`, and `SKILL.md` says whether each is to be executed or read as reference.

## Workflow

- When you need a linked git worktree, create it at `.worktrees/<branch>` inside the repository, never beside it: the agent sandbox allows writes only inside the workspace, so every edit to a worktree outside it waits for the user's approval. `.gitignore` excludes the directory, and `npx skills add .` searches it only with `--full-depth`.
- Put temporary files and directories, such as scratch repositories and benchmark scripts, inside the repository, never in `/tmp` or another OS temp directory, which also waits for the user's approval: a canon skill's go in `.canon/` as the `canon` skill says, any other in `.tmp/`. `.gitignore` excludes both, and `npx skills add .` searches `.tmp/` only with `--full-depth`.
- Leave files in `.tmp/` when a task ends, and start over in a new directory (`mktemp -d .tmp/<name>.XXXX`) rather than by deleting the old one: file-deletion protection makes every deletion wait for the user's approval, which stalls a task meant to run unattended. Instead, check `du -sh .tmp` when a task starts; only when it exceeds 32 GB, delete the entries untouched for a day, in one command so the user approves once: `find .tmp -mindepth 1 -maxdepth 1 -mtime +0 -exec rm -rf {} +`.
- New skill: run `npx skills init <name>` in `skills/<category>/`, then complete the frontmatter (including `disable-model-invocation`) and `agents/openai.yaml` as the rules above describe.
- When adding or removing a skill, or changing its purpose or trigger mode, update the Skills tables in `README.md`. `validate.py` checks their names, categories and trigger modes against the frontmatter; check the summaries yourself.
- After changing any skill, run `python3 scripts/validate.py` (it also runs `tests/`) and `npx skills add . --list`, and commit only once both pass.
- When changing `canon.py`, add regression tests to `tests/test_canon.py` and bump `CANON_VERSION` in the same commit: `init` upgrades a project's copy by version number only, and `validate.py` rejects a `canon.py` whose content changed while its version did not.
- Commit messages follow Conventional Commits, with the skill name as the scope, e.g. `feat(canon-code-review): add security checklist`; repository-wide changes use no scope or `repo`.
- Releases follow Semantic Versioning and are tagged `vX.Y.Z`. To release, write the version's entry in `CHANGELOG.md` from the commits since the last tag, in terms of what changes for users; commit it as `chore(repo): release X.Y.Z` and tag that commit. `CANON_VERSION` is separate and changes only with `canon.py`.
- Write everything in English: skills, `README.md` and `AGENTS.md`.
