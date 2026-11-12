# Docs

<!-- canon:index:start -->

### Designs

- [D000: Project overview](designs/D000-project-overview.md) · active · Agent skills built around canon, a documentation system kept in the repository; one module, its capabilities and the designs that own them. · owns: architecture
- [D001: Skill telemetry with canon trace](designs/D001-skill-telemetry.md) · active · Opt-in tracing of canon workflows with canon.py trace, repo snapshots for replay, review dispositions and offline analysis of nine questions. · owns: skill-telemetry · modules: canon
- [D002: Project overview and as-built designs](designs/D002-overview-and-as-built.md) · active · D000 overview, as-built designs of existing code, backfill before changing unspecified behavior, and audit's unchecked commits and design coverage. · owns: project-overview, as-built-design, design-coverage, unchecked-commits · modules: canon
- [D003: Subagents](designs/D003-subagents.md) · active · How canon runs reviewers and workers as new subagents on the session's model, resumed by id, the review snapshots confirmations diff, and the reviewer file. · owns: subagents · modules: canon
- [D004: Project setup](designs/D004-project-setup.md) · active · 1 known issue · Project setup and upgrades with canon.py init, migration of existing docs with adopt, and the canon-init flows for setup, upgrade and new modules. · owns: project-setup · modules: canon
- [D005: Docs index](designs/D005-docs-index.md) · active · The generated doc index in each docs root's README.md and archived/README.md, its markers and format, the commands that regenerate it and check's index errors. · owns: docs-index · modules: canon
- [D006: Doc model and writing rules](designs/D006-doc-model.md) · active · Doc types, ids, frontmatter, sections, statuses and archiving of canon docs, the templates of new, the doc rules check enforces and the writing rules. · owns: doc-model, doc-writing · modules: canon
- [D007: Change tiers and the review gate](designs/D007-change-tiers.md) · active · Change tiers and their flows, design problems, and the review gate of a change: steps, prompt, merge rules, confirmation and follow-up rounds, status. · owns: change-tiers, review-gate, design-problems · modules: canon
- [D008: Prototypes and research](designs/D008-experiments.md) · active · Prototypes and research (canon-prototype, canon-research): quick answers, the research brief, logic, UI and spike prototypes, verdicts in E docs. · owns: prototypes, research · modules: canon
- [D009: Settling decisions](designs/D009-settling-decisions.md) · active · Settling open decisions with the user (canon-grill): triage before asking, open decisions kept in the doc, and small batches of related questions. · owns: settling-decisions · modules: canon
- [D010: Doc queries and renames](designs/D010-doc-queries-and-renames.md) · active · 8 known issues · Doc queries and renames with canon.py show, find, which and affected, and rename and renumber, with the references and id collisions renumber settles. · owns: doc-queries, doc-renames, doc-renumbering · modules: canon

### Reviews

- [R003: Canon friction in Silk's design phase](reviews/R003-silk-design-phase.md) · open · Canon friction in a docs-only bilingual project: review gates per doc, parallel sessions, archived experiments, translations, check gaps, tool drift. · modules: canon

### Concepts

- [C001: Canon backlog](concepts/C001-canon-backlog.md) · draft · Ideas for the canon module that no design tracks yet, from codebase reviews and deferred findings. · modules: canon

<!-- canon:index:end -->
