# Docs

<!-- canon:index:start -->

### Designs

- [D000: Project overview](designs/D000-project-overview.md) · active · Agent skills built around canon, a documentation system kept in the repository; one module, its capabilities and the designs that own them. · owns: architecture
- [D001: Skill telemetry with canon trace](designs/D001-skill-telemetry.md) · active · Opt-in tracing of canon workflows with canon.py trace, repo snapshots for replay, review dispositions and offline analysis of nine questions. · owns: skill-telemetry · modules: canon
- [D002: Project overview and as-built designs](designs/D002-overview-and-as-built.md) · active · D000, as-built design backfill, design coverage and unchecked commits in audit, staged commit templates and per-commit design reference checks. · owns: project-overview, as-built-design, design-coverage, unchecked-commits · modules: canon
- [D003: Subagents](designs/D003-subagents.md) · active · How canon runs every subagent as a new one, never a fork, reviewers and workers on the session's model, resumed by id, review snapshots, the reviewer file. · owns: subagents · modules: canon
- [D004: Project setup](designs/D004-project-setup.md) · active · canon installed in each project and its recorded version, setup and upgrades with canon.py init, migration of docs with adopt, and the canon-init flows. · owns: project-setup · modules: canon
- [D005: Docs index](designs/D005-docs-index.md) · active · The generated doc index of each docs root in README.md and archived/README.md, its markers and format, regenerating or staging it, and check's index errors. · owns: docs-index · modules: canon
- [D006: Doc model and writing rules](designs/D006-doc-model.md) · active · Doc types, ids, frontmatter, statuses and archiving, new's templates, check on the work tree, staged tree or a commit, concurrent sessions and writing rules. · owns: doc-model, doc-writing, concurrent-work · modules: canon
- [D007: Change tiers and the review gate](designs/D007-change-tiers.md) · active · Change tiers and their flows, design problems, and the review gate of a change: steps, prompt, merge rules, confirmation and follow-up rounds, status. · owns: change-tiers, review-gate, design-problems · modules: canon
- [D008: Prototypes and research](designs/D008-experiments.md) · active · Prototypes and research (canon-prototype, canon-research): quick answers, the research brief, logic, UI and spike prototypes, verdicts in E docs. · owns: prototypes, research · modules: canon
- [D009: Settling decisions](designs/D009-settling-decisions.md) · active · Settling open decisions with the user (canon-grill): triage before asking, open decisions kept in the doc, and small batches of related questions. · owns: settling-decisions · modules: canon
- [D010: Doc queries and renames](designs/D010-doc-queries-and-renames.md) · active · Doc queries and renames with canon.py show, find, which and affected, and rename and renumber, with the references and id collisions renumber settles. · owns: doc-queries, doc-renames, doc-renumbering · modules: canon
- [D011: Source code embedded in docs](designs/D011-embedded-source.md) · active · Embed a repository source file or a named region in Markdown, regenerate its fenced code block and check it against the same Git tree as the document. · owns: source-embeds · modules: canon
- [D012: Paired replay of Canon workflows](designs/D012-workflow-replay.md) · active · Restore one verified unit, compare two skill suites on paired headless runs, and blind the scoring of review findings, slice outcomes and costs. · owns: workflow-replay · modules: canon

### Plans

- [P012: Reliable review rounds and evidence](plans/P012-review-workflow-reliability.md) · in-progress · Eight review workflow corrections covering round ownership, evidence and waivers, confirmation findings and host recovery. · modules: canon

### Reviews

- [R007: Open Canon workflow feedback from Silk and Canon](reviews/R007-canon-workflow-open-feedback.md) · open · Twelve open field findings on plan tiers, review completion, approvals, trace evidence, worktree records, CLI queries and verification coverage. · modules: canon

### Experiments

- [E001: Precedence of project and user skills across hosts](experiments/E001-skill-scope-precedence.md) · concluded · Same-name user and project skills load both in Cursor and Codex, told apart by path; Claude Code runs the user's. npx skills project installs reach all three. · modules: canon
- [E002: Ideas from popular agent skill libraries](experiments/E002-skill-library-survey.md) · answered · Ideas from popular skill libraries (mattpocock, superpowers, ECC, anthropics): skill evals against a baseline, trigger tests and review guards lead. · modules: canon
- [E003: D001 trace pilot on Canon and Silk](experiments/E003-d001-trace-pilot.md) · concluded · A 20-case Canon and Silk pilot found gaps in replay inputs, finding attribution, Cursor transcripts and worker boundaries before trace analysis. · modules: canon
- [E004: D001 review input revalidation](experiments/E004-d001-review-input-revalidation.md) · concluded · All three recovered review inputs survived an independent trace clone. Three other pilot criteria still fail on the frozen Canon and Silk cohort. · modules: canon
- [E005: D001 pilot evidence reconciliation](experiments/E005-d001-pilot-evidence-reconciliation.md) · concluded · Reconcile review attribution, Cursor anchors and worker chronology for the frozen Canon and Silk pilot and two preselected Codex slices. · modules: canon
- [E006: Design references in recent Canon and Silk commits](experiments/E006-refs-trailer-trial.md) · concluded · Of 60 sampled commits, six touched governed paths. One omitted Refs entirely and two cited some of the designs governing shared files. · modules: canon

### Concepts

- [C001: Canon backlog](concepts/C001-canon-backlog.md) · draft · Ideas for the canon module that no design tracks yet, from codebase reviews and deferred findings. · modules: canon
- [C002: Acceptance check of a finished change](concepts/C002-acceptance-check.md) · draft · Acceptance check of a finished change, a canon-acceptance skill whose fresh subagent runs the real artifact against the design's Goals before code review. · modules: canon

<!-- canon:index:end -->
