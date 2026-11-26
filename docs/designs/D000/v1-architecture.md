# Canon 1.0 architecture contract

Working draft for the architecture milestone on `v1`.

## Responsibilities

The agent interprets a task or a review finding. The maintainer decides changes to accepted design intent. The CLI checks facts available in project files and Git. For example, it can verify which reviewers covered a revision. Recording maintainer approval requires a decision naming that revision. The distinction must be visible to a session that resumes the work. [R008§maintainer-principles: maintainer principles](../../reviews/R008-canon-governance-and-blind-review-feedback.md#maintainer-principles) · [D013§goals: review CLI](../D013-review-cli.md#goals)

## Project installation

Canon 1.0 distributes the `canon-cli` Python package independently from the skills. Both are maintained in this repository. The core skill declares the minimum package version it needs in its `compatibility` field. Any installed version at or above that minimum satisfies the requirement. The `canon --version` command reports the installed Python distribution version. [Core skill](../../../skills/governance/canon/SKILL.md)

The CLI subproject uses uv for its development environment and build, ty for type checking and Ruff for linting and formatting. Its development lockfile applies to contributors. [CLI development](../../../cli/README.md)

## Acceptance cases

- **Routine fix.** An agent fixes a broken document link in a linked worktree. CI checks the resulting commit. Both obtain the CLI from the project's recorded setup and agree on whether the link resolves.
- **Unresolved design choice.** A reviewer rechecks a proposed fix and the same blocker remains. A fresh session can identify the affected revision, the unresolved finding and the decision to return to the maintainer. [R007§r007-f14-an-unresolved-blocker-after-a-targeted-recheck: Silk recheck case](../../reviews/R007-canon-workflow-open-feedback.md#r007-f14-an-unresolved-blocker-after-a-targeted-recheck)

## Open questions

How should `canon-init`, existing hooks and CI jobs that invoke `python3 .agents/skills/canon/scripts/canon.py` transition to the packaged command when a project upgrades from `v0.9.4`? [D004§install: project installation](../D004-project-setup.md#install) · [R008§r008-f16-repository-choice: upgrade case](../../reviews/R008-canon-governance-and-blind-review-feedback.md#r008-f16-repository-choice)
