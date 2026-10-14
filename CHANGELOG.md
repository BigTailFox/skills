# Changelog

Notable changes in each release. Versions follow [Semantic Versioning](https://semver.org); while the major version is 0, a minor release may change how skills behave.

## 0.1.0 - 2026-10-14

First release: 18 skills built around canon, for Cursor, Claude Code and Codex.

- `canon`: a documentation system for long-running, multi-session, multi-model work. Numbered concepts, designs, plans, reviews, experiments and investigations live under `docs/`; every change gets an L0, L1 or L2 tier; designs and plans pass a blind review gate with same-model and cross-family reviewers; and `canon.py` (canon version 4) creates, checks, queries, audits and archives the docs.
- `canon-init` and `canon-sync`: set canon up in a project or monorepo module, configure the machine's cross-family reviewer, and keep docs in step with the code.
- Fifteen execution skills that work through canon: design, plan and implementation phases, with a fresh worker subagent per plan slice; two-axis code review; blind and codebase reviews; TDD, grilling, prototyping, research and investigation; handoff, teaching and writing for agents. Fourteen of them are adapted from [mattpocock/skills](https://github.com/mattpocock/skills).
