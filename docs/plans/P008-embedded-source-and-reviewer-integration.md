---
status: in-progress
created: 2026-11-23
updated: 2026-11-24
revision: 1
reviewed: 1
approved: 1
reviewers: [gpt-6.2-astra, gemini-4-neon-xhigh]
modules: [canon]
summary: Deliver embedded source, attachment citations, native command review progress, scoped consent and verified skill references in one change.
refs: [D011, D003, D006, D010, C001, D001, D007]
based_on: [D011@r1, D003@r12, D006@r21, D010@r8]
---

# P008: Embedded source and external reviewer integration

Implements [D011: Source code embedded in docs](../designs/D011-embedded-source.md), [D003: Subagents](../designs/D003-subagents.md), [D006: Doc model](../designs/D006-doc-model.md) and [D010: Doc queries and renames](../designs/D010-doc-queries-and-renames.md). The skill-text changes address the closing and reference-checking entries in [C001: Canon backlog](../concepts/C001-canon-backlog.md).

## Current state

Next: complete code review.

## Slices

### S1: Reuse an authorized reviewer and display its command

Status: done

Risk: A checkout-supplied or overbroad grant can expose material. A buffered command can cause duplicate launches or lose the provider ID during a quiet wait.

Ship the fillable `reviewer-example.md` in the core skill, directly reachable from its `SKILL.md` and workflow. Update `canon-init`, the workflow and `canon-blind-review` to use [D003§authorization-for-command-reviewers: the actual grant](../designs/D003-subagents.md#authorization-for-command-reviewers) and [D003§external-review-progress: the native command surface](../designs/D003-subagents.md#external-review-progress). Show the two-section priorities/definitions layout, reference a shared launcher once, and label approval examples unfilled. Keep user decisions, model preferences, credentials and actual provider commands machine-local. Document setup trials and fallback, including importing old routes and discarding their claimed grants.

- Walk the actual installed skill instructions with synthetic configuration and inputs. For each case, record the route, the next action, what inputs may leave and the justification the instructions would supply. Cover an affirmative batch grant for the first pass and confirmation, a standing grant on linked worktrees, other clones and batches, changed destination or inputs, expiry, revocation and a copied grant. Hold those inputs and destination fixed while varying the model, allowed tools or phase. A setup trial or recovery under a first-pass-only grant must direct zero provider calls until a matching grant or authorized replacement is selected. Include a docs-only grant with a confined view and a route unable to honor that limit. Transmission consent never settles a design approval.
- Walk the published review instructions through an attached command, a buffered job, an explicit status request and an interrupted caller. For each, record prescribed launches, provider calls, local status reads, early ID binding and terminal report. The ordinary attached path launches once, waits on its handle, puts routine output in the command view and issues zero status queries or chat heartbeats. The interrupted path checks the retained job and the matching read-only recovery. Verify the example’s direct links and unfilled grant fields with the repository checks in Notes. Record these walkthroughs in slice scratch evidence.

### S2: Generate and validate source blocks in the selected tree

Status: done

Risk: A source reached through a symlink or the wrong Git tree could be published. A shorter fence in generated content could expose literal examples to doc rewrites.

Add `embed [ID|PATH ...] [--check]` to the core CLI and skill. Reuse the repo and tree inventory, adding component-by-component source resolution in each tree. Validate regular-file membership after walking links and `..` in order. Avoid host realpath and lexical pre-normalization for this operation. Respect full Markdown fences in shared readers. Implement [D011§markers-and-sources: source selection](../designs/D011-embedded-source.md#markers-and-sources) and [D011§generating-and-checking: generation and checking](../designs/D011-embedded-source.md#generating-and-checking). Include only authored live consumers and protect the indexes and historical copies. Apply [D006§layout: layout](../designs/D006-doc-model.md#layout), [D006§check: checking](../designs/D006-doc-model.md#check) and [D006§concurrent-work: worker scope](../designs/D006-doc-model.md#concurrent-work). Update the Tool table, Layout, markers and Concurrent work in the core skill, Guides in its `doc-types.md`, and the worker prompt in `canon-implement`. Direct a worker to regenerate only assigned documents with explicit selectors.

- Through the public commands, generate a whole file, named and empty regions, escaped paths, language tags and longer fences. Generation prints `updated <document>` once per changed file. A second run is quiet and byte-identical. Preserve surrounding text, mixed or CRLF endings and a missing final newline. Exercise root and module docs, guides and attachments, aliases, a scoped repair alongside another invalid doc, and literals inside examples. Walk a worker assigned one of two stale docs and verify that its scoped repair leaves the other untouched. Run `embed --check` over a stale block and an invalid block together. Both diagnostics appear, the bytes stay intact and the exit is 1. A clean selection exits 0 quietly. Accept a plain Markdown source. Reject an acyclic reference to another eligible consumer with an active pair. Malformed markers or regions, binary or missing inputs, cycles, invalid selectors and escaping links report the location and leave all selected documents intact.
- With staged, working and committed versions deliberately different, verify `check`, its doc-scoped form, `--staged`, `--rev`, `--base` and `--fix` against the designated tree. Use a relative symlink followed by `..`, an absolute symlink, an ignored source and an escaping consumer. Inspect the index and work tree after read-only operations. A stale work-tree diagnostic names the scoped repair, a staged one calls for generating and staging the matching block, and a revision diagnostic identifies the checked commit. Test valid, stale and malformed pairs on both sides of the document line limit and protect headings and links inside generated four-backtick fences.

### S3: Preserve sources and citation headings across document moves

Status: done

Risk: ID collisions, headings changed indirectly, and literal code in generated blocks make a plain text substitution ambiguous.

Use the move mapping and heading-settlement logic in `canon.py` for [D011§moves-and-archived-copies: marker paths and freezing](../designs/D011-embedded-source.md#moves-and-archived-copies) and [D010§renumber: final attachment headings](../designs/D010-doc-queries-and-renames.md#renumber). Apply [D006§statuses-and-archiving: archive preflight and moves](../designs/D006-doc-model.md#statuses-and-archiving). Use S2’s resolved consumer selection for marker edits, including files that become eligible on adoption. Exercise both live references and historical copies via the normal commands.

- Through `renumber`, reproduce D010-K10 for a moved attachment and for a stationary owner. Assert both the link destination and the nonleading visible `ID§slug` against the final heading. Keep unrelated citations, inline code and ambiguous collision references correct. Cover headings that themselves depend on a changed citation, a base-sided collision and attachment ownership established solely by a live embed.
- Exercise `rename`, `renumber`, `adopt`, `archive` and the `init` move to D000 with source or consumer moves, percent escapes and a region resembling a doc ID. Rename a source referenced by a real guide and by an escaping guide alias. The real guide follows the move and the ineligible alias target stays byte-identical. Assert marker targets and byte-preservation of generated IDs. Capture an up-to-date CRLF marked span before archive, compare the whole raw span, including the marker path and code IDs, after archive and a renumber of that archived document, then change or delete its original source and check the archive. A stale or invalid outgoing block in the numbered doc or one of its Markdown attachments leaves status, files and Git index intact. An incoming live marker to a moved source still resolves.

### S4: Share workflow closing instructions and validate their references

Status: done

Implement the closing and reference-checking entries in [C001§ideas: backlog](../concepts/C001-canon-backlog.md#ideas) within [D001§budgets: skill budgets](../designs/D001-skill-telemetry.md#budgets). In the core skill add “Closing a workflow” to `workflow.md` and “Deferred findings” beside the known-issue format in `doc-types.md`, following [D006§known-issues-findings-and-slices: issue records](../designs/D006-doc-model.md#known-issues-findings-and-slices) and [D007§merging-findings: destinations](../designs/D007-change-tiers.md#merging-findings).

Use the shared closing condition in `canon-code-review`, `canon-design`, `canon-plan`, `canon-implement`, `canon-review`, `canon-handoff` and `canon-investigate`. Keep their trace timing and exceptions, including nested code review, L1 carry-on, handoff and investigation. Route findings from core `workflow.md`, `as-built.md`, `canon-code-review`, `canon-review` and `canon-retro` as each caller requires. A target-plan finding goes to its Notes, an as-built issue keeps its base and next action, the review keeps its moved disposition and retro Later always goes to the backlog. Keep cross-skill pointers by installed name.

- Extend `scripts/validate.py` and its existing CLI regressions. A same-file or relative Markdown section link must identify a real heading. An explicit named-skill pointer and a named `workflow (Section)` reference must resolve; support the existing parent/child and multiple-section spelling. Normalize explicit comma-form and possessive workflow pointers to the parenthesized form wherever they name a section. Match full-length Markdown fences in the validator; include a four-backtick literal containing inner triple backticks. Inspect actionable path/line diagnostics for missing destinations. Exercise duplicate and punctuated headings, literal examples, ordinary unrelated prose and external links.
- Walk the changed closing steps for a friction-free run, a qualifying standalone workflow, a nested code review, deferred code findings with and without a governing design, and a deferred finding about a target plan that must reach its Notes. Verify the original caller-specific action, trace parent, source and disposition along each path.

## Notes

- Use only the granted repository view for external review. The orchestrator separately exercises D003’s native command route on this machine with an observed synthetic job and one authorized review. Inspect host items, chat events, result and exit; record when visible App rendering cannot be observed. When no suitable route or grant is available, record the skipped live check and the quiet or manual fallback. Where the current machine route conflicts with D003, the orchestrator updates the Codex App display preference under the host’s permission mechanism and records only the actual grant and lifetime. Distributed checks use synthetic inputs and require no launcher, login or network.
- Each slice changing `canon.py` adds public CLI regressions in `tests/test_canon.py`, bumps `CANON_VERSION` and reruns `init` in this checkout in that commit. For skill changes run the repository validator with the default temp directory and measured D001 budgets, and verify discovery with `npx skills add . --list`.
- Review the complete implementation once at L2 against all four designs and this plan. At the docs step reconcile C001 and D010-K10, the README’s reviewer display description, D003’s paths for the example, and D000’s validator dependency description. Raise `implemented` on the four delivered design versions and activate D011.

## Log

- The joint design passed review in `6a473ce`. The four reviewed revisions were approved in `e646349`.
- Started at 2d7ef6499dcd2c3755abe1bd84e53d1497bbcbb2.
- S1 completed. Verified the installed grant and progress instructions using synthetic grants, the unfilled example, a real native command item and six offline launcher cases. All 434 repository tests passed across the default and outside-checkout runs. D001 budgets passed and discovery listed 19 skills.
- S2 completed. Added scoped source generation and checking in the work tree, index and commits, with full-length fences and eligible-file resolution. Eleven CLI regressions and the independent byte and Git-tree checks passed. All 445 repository tests passed across both environments; D001 budgets and discovery of 19 skills passed. Canon version 75.
- S3 completed. Fixed D010-K10 for moved and stationary owners and their dependent headings. Nine public regressions cover moves, adoption, collision ownership and archival freezing. Independently reproduced the original link mismatch, verified the corrected label and target, and compared CRLF spans and the Git index across archive refusal and success. All 454 tests passed, D001 budgets passed and discovery listed 19 skills. Canon version 76.
- S4 completed. Consolidated the seven workflow closing steps and preserved caller-specific finding destinations and trace parents. Five public validator regressions include section links, full fences, named skills and list-item references. All 459 repository tests passed across both test environments, D001 budgets passed, and discovery listed 19 skills.
