# Docs

<!-- canon:index:start -->

### Designs

- [D000: Project overview](designs/D000-project-overview.md) · active · Agent skills built around canon, a documentation system kept in the repository; one module, its capabilities and the designs that own them. · owns: architecture
- [D001: Skill telemetry with canon trace](designs/D001-skill-telemetry.md) · active · Opt-in tracing of canon workflows with canon.py trace, repo snapshots for replay, review dispositions and offline analysis of nine questions. · owns: skill-telemetry · modules: canon
- [D002: Project overview and as-built designs](designs/D002-overview-and-as-built.md) · active · 2 known issues · D000 project overview in every project, as-built designs that record existing code, backfill before changing unspecified behavior, and design coverage in audit. · owns: project-overview, as-built-design, design-coverage · modules: canon
- [D003: Subagents](designs/D003-subagents.md) · active · 4 known issues · How canon runs reviewers and workers as new subagents on the session's model, resumed by id, the review snapshots confirmations diff, and the reviewer file. · owns: subagents · modules: canon
- [D004: Project setup](designs/D004-project-setup.md) · active · 2 known issues · Project setup and upgrades with canon.py init, migration of existing docs with adopt, and the canon-init flows for setup, upgrade and new modules. · owns: project-setup · modules: canon
- [D005: Docs index](designs/D005-docs-index.md) · active · The generated doc index in each docs root's README.md and archived/README.md, its markers and format, the commands that regenerate it and check's index errors. · owns: docs-index · modules: canon

### Reviews

- [R001: Codebase review of the canon module](reviews/R001-canon-module.md) · open · First codebase review of the canon module at release 0.3.1, from the architecture, usability and functional angles.

### Concepts

- [C001: Canon backlog](concepts/C001-canon-backlog.md) · draft · Ideas for the canon module that no design tracks yet, from codebase reviews and deferred findings. · modules: canon

<!-- canon:index:end -->
