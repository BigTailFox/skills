---
status: active
created: 2026-11-10
updated: 2026-11-11
revision: 1
modules: [canon]
summary: Doc types, ids, frontmatter, sections, statuses and archiving of canon docs, the templates of new, the doc rules check enforces and the writing rules.
refs: [D000, D001, D002, D003, D004, D005, D007, D008]
owns: [doc-model, doc-writing]
paths: [skills/governance/canon/SKILL.md, skills/governance/canon/doc-types.md, skills/governance/canon/writing.md, skills/governance/canon/scripts/canon.py, tests/test_canon.py]
reviewed: 1
reviewers: [claude-opus-5.5]
implemented: 1
---

# D006: Doc model and writing rules

## Goals

1. Every engineering doc of a project is one of six numbered types, each with fixed sections, statuses and frontmatter fields, and an id that identifies it for life, so any session or model can find, read and reference it.
2. `canon.py check` enforces the doc model's mechanical rules and `check --fix` applies the fixes that need no judgment, so agents follow its output instead of re-checking rules by hand.
3. `canon.py new` creates each doc from its type's template with the next free id; `canon.py archive` moves a doc and its attachments to `archived/` and rewrites every link to them, and refuses while the type's terminal conditions fail.
4. Docs state each fact once, in the doc that owns it, for a reader who arrives through a pointer.

Out of scope: the generated index ([D005: Docs index](D005-docs-index.md)); D000, as-built revisions and `as_built`, ids that Git history keeps taken, docs by their name such as READMEs, and coverage in `audit` ([D002: Project overview and as-built designs](D002-overview-and-as-built.md)); trace and review files ([D001: Skill telemetry with canon trace](D001-skill-telemetry.md)); subagents and review snapshots ([D003: Subagents](D003-subagents.md)); `init`, `adopt` and the `AGENTS.md` block ([D004: Project setup](D004-project-setup.md)); change tiers, the review gate and design problems ([D007: Change tiers and the review gate](D007-change-tiers.md)); `rename`, `renumber`, `show`, `find`, `which`, `affected` and the rest of `audit`, which no design covers.

## Spec

The agent-facing text of this spec is the `canon` skill: `SKILL.md` (Layout, Doc types, Frontmatter, Rules), `doc-types.md` and `writing.md` in `skills/governance/canon/`.

### Layout

- A project is a directory holding an `AGENTS.md` that Git tracks or would add; outside Git, one found while walking the tree, skipping directories named `node_modules` or `venv` or starting with `.`. Its docs root is its `docs/` directory, when that exists. Repo-wide and cross-module docs live in the repo root's `docs/`, a module's docs in the module's `docs/`; a more specific `AGENTS.md` and its `docs/` govern their subtree and override broader rules.
- The repo root is the top of the Git work tree, from whichever of its directories a command runs, else the directory the command runs in. `check` reads the files Git tracks or would add that exist on disk, or outside Git the files that walk finds.
- A docs root holds:

  ```text
  docs/
  ├── README.md                  the index (D005)
  ├── concepts/  designs/  plans/  reviews/  experiments/  investigations/
  │   ├── <id>-<slug>.md         a numbered doc of the directory's type
  │   └── <id>/                  its attachments
  ├── guides/                    unnumbered docs for users and operators
  ├── assets/                    images and files shared by several docs or guides
  └── archived/                  README.md (D005) and the six type directories, for docs in a terminal status
  ```

- Attachments of a numbered doc (data, scripts, reports, prototypes, images used only by it) live in `<type directory>/<id>/` beside the doc. The directory is created with the first attachment; large binaries are linked, not committed. `archive` moves the directory with its doc.
- Guides explain how to use the system and link to designs for specs. Only link checks apply to the `.md` files under `guides/` and `assets/`; files in attachment directories get no link check.
- Readers skip `archived/` unless researching history.
- Temporary files of canon skills (prompts, scratch prototypes, handoffs) go in `.canon/<skill>/<topic>/` at the repo root, `<topic>` a short kebab-case slug, never in the OS temp directory or the tracked tree. Nothing there is a doc: what is worth keeping becomes an attachment or doc content. `.canon/canon/trace/` is not scratch ([D001§switch-and-storage: switch and storage](D001-skill-telemetry.md#switch-and-storage)), and `new` keeps its id lock at `.canon/id.lock` ([Templates and `new`](#templates-and-new)).

`check` errors on entries that do not fit:

- an entry directly in `docs/` or `docs/archived/` other than those above, `guides/` and `assets/` being allowed only outside `archived/`, once per entry: `ERROR <entry path>: unknown entry; allowed: README.md, archived/, guides/, assets/, concepts/, designs/, plans/, reviews/, experiments/, investigations/`, the list inside `archived/` being `README.md` and the six type directories;
- a file in a type directory that is neither a doc file of that type ([Ids and file names](#ids-and-file-names)) nor inside a directory named like an id of that type: `ERROR <path>: invalid doc path; expected designs/DNNN-kebab-slug.md (D may add one A-Z suffix)`, naming the type's directory and letter, the suffix note for designs only;
- a file in an attachment directory whose id no doc has in the same docs root and the same live or archived part: `ERROR <path>: attachment directory <id> has no matching doc beside it`, once per file.

### Ids and file names

- An id is a type letter (`C`, `D`, `P`, `R`, `E`, `I`), a number of at least 3 digits, zero-padded to 3 and with no other leading zero (`D012`, `D1000`, never `D0012`), and for a sub-design one letter `A` to `Z` (`D012A`).
- A doc's file is `<id>-<slug>.md` in its type's directory, the slug kebab-case (`[a-z0-9]+(-[a-z0-9]+)*`). Its title is its only H1, `# <id>: <title>`.
- Ids are unique across the repository, over every docs root and archived docs included. The id is a doc's identity: docs are created with `new`, retired with `archive`, and given a new slug with `rename`; a doc is never deleted and an id never reused.
- A new doc's number is one above the highest of its type among the docs of every docs root, archived docs and sub-designs included, and the ids history keeps taken ([D002§project-overview-d000: D000](D002-overview-and-as-built.md#project-overview-d000)). A sub-design gets the first letter, from `A`, not taken the same way.
- Sub-designs have one level. `check` errors with `sub-design needs parent D012` when no doc, archived included, has the parent's id.
- `new` and `archive` exit with `canon: unknown document <id>` for an id argument no doc has, and `canon: <id> is the id of <path> and <path>; renumber one of them first` for one several docs have.

`check` errors:

- on each doc whose id an earlier doc has: ``duplicate id <id>, also <path>; run `canon.py renumber <path> --base <ref>` on the doc this branch added, with the branch it merged or rebased onto``;
- with `--base REF`, on each doc whose id exists in REF's tree but not at the merge base with REF: ``<id> was also added on <REF> as <path in REF>; run `canon.py renumber <path> --base <REF>` ``;
- in a Git checkout with a HEAD commit, on each doc file deleted, not renamed as Git's rename detection pairs it, whose id no doc has, among the uncommitted changes against HEAD and, with `--base`, on the branch since the merge base: `<id> was deleted; restore it and archive it instead`, except for a design that owned `architecture` ([D002§project-overview-d000: D000](D002-overview-and-as-built.md#project-overview-d000)).

### Doc types

| Type | Directory | Required sections | Statuses, terminal ones last |
|---|---|---|---|
| C concepts | `concepts/` | Motivation, Ideas, Open questions | draft → adopted, dropped |
| D designs | `designs/` | Goals, Spec, Decisions | draft → accepted → active → superseded, retired |
| P plans | `plans/` | Current state, Slices, Notes, Log | draft → accepted → in-progress → done, abandoned |
| R reviews | `reviews/` | Scope, Findings | open → closed |
| E experiments | `experiments/` | Question, Setup, Results, Conclusion | planned → running → concluded |
| I investigations | `investigations/` | Symptom, Reproduction, Analysis, Resolution | open → resolved |

A doc may add other sections. `check` errors with ``missing section `## <name>` `` for each required `## ` heading, matched by its exact text in any order, and with ``body must have exactly one H1 reading `# <id>: <title>` `` unless the body outside code fences has one H1 and its text is `<id>: ` and a title.

- **Concepts**: ideas, trade-offs and brainstorming, with no spec and no plan. When an idea becomes work, a design that links the concept is created or revised and the concept archived as `adopted`; a rejected idea is archived as `dropped`.
- **Designs**: one per topic, revised in place for the topic's whole life, and the source of truth: where a plan disagrees, the design wins.
  - Goals: what the design must achieve, measurable where possible. Spec: the authoritative, precise specification of every topic in `owns`, interfaces given as code (signatures, schemas, CLI usage, config keys); user-visible behavior is specified here. Budgets, only when there are quantitative targets: each target with how it is measured. Decisions: one line per key decision with its reason. Known issues: [below](#known-issues-findings-and-slices).
  - Status: `draft` until the review gate makes it `accepted` ([D007§gate-status: gate status](D007-change-tiers.md#gate-status)); `active` with `implemented` once an implementation has landed, and still `active` while a revision's spec leads the code. Archived as `superseded`, with the successor in `refs`, or `retired` when the feature is removed. An as-built revision's status: [D002§as-built-revisions: as-built](D002-overview-and-as-built.md#as-built-revisions).
  - Split: a design that outgrows one doc gets sub-designs with `new D <slug> --parent D012`; the sub-topic's spec, `owns` and `paths` move into the sub-design, and the parent keeps the overview and links its children. A sub-design that outgrows itself becomes a new top-level design.
- **Plans**: the implementation plan and log of one change, created only from an accepted or active design, with `new P <slug> --from D012`; `new` does not enforce this and creates a plan without `--from` too.
  - Current state, at the top: the current slice, the next action and paused slices with their reasons, updated at the end of every slice; a new session resumes from it.
  - Slices: ordered `### S1: <name>` subsections. Each starts with a `Status:` line, then a `Risk:` line naming the kinds when the slice involves complex logic, concurrency, performance, security or data migration (`Risk: concurrency, data migration`), then lists its changes and the test criteria that prove it done. Each criterion names its seam, the public interface the design's Spec defines where the test observes behavior; an accepted plan's seams are agreed with the user, and tests go only there.
  - Notes: risks and constraints for the implementer, findings about the plan the user left for later, and details the plan settled that its design leaves unstated, which the docs step writes into the design. Log: decisions, results, evidence and deviations, appended as they happen.
  - Status: `accepted` after the review gate ([D007§gate-status: gate status](D007-change-tiers.md#gate-status)), `in-progress` while implementing. Archived as `done` once every slice is `done`, in the commit that completes the implementation, or as `abandoned`.
- **Reviews**: findings of a review of code, modules or the whole repo. Scope states what was reviewed, at which commit and from which angles (function, performance, security, architecture, usability). A periodic review produces one R doc per run, its reports in `reviews/<id>/`. Code review of a change and the review gate produce no R doc. Archived as `closed` as soon as no finding is `open`.
- **Experiments**: one question answered with evidence, by a run (benchmark, prototype, measurement) or by research of primary sources (official docs, specs, source code). Setup lists `- Commit:`, `- Environment:` and `- Command:` for a run, so it can be rerun, and `- Sources:` for research, one primary source per indented line. Results link every measurement to its raw data and every finding to its source. Prototype code, raw data and source excerpts go where [D008§prototype-files: prototype files](D008-experiments.md#prototype-files) puts them. The conclusion is absorbed as [D008§absorbing-a-conclusion: absorbing a conclusion](D008-experiments.md#absorbing-a-conclusion) states, then the experiment is archived as `concluded`.
- **Investigations**: debugging and profiling. Reproduction lists `- Commit:`, `- Environment:` and `- Command:`; repro scripts and captured logs or traces go in `investigations/<id>/`, secrets replaced by `<REDACTED>`. Resolution lists `- Root cause:`, `- Fix:` and `- Verification:`, all filled before archiving. Archived as `resolved` as soon as the defect is fixed or verified not to be one; a root cause that exposes a spec gap gets the design fixed too.

### Statuses and archiving

- `check` errors with ``status `<status>` invalid; use one of <the type's statuses>`` for a status outside the type's, a missing `status` giving only the missing-field error ([Frontmatter](#frontmatter)), with ``status `<status>` requires the doc to be in archived/; use `canon.py archive` `` for a terminal status outside `archived/`, and with ``status `<status>` requires the doc to be outside archived/; set one of <the type's terminal statuses>`` for another status inside it.
- A non-terminal status is set by editing the field; only `archive` sets a terminal one, and no command moves a doc back out of `archived/`.
- Terminal conditions, which `archive` checks for the status it sets and `check` reports as errors on each archived doc:
  - every doc: a non-empty `summary` and no template guidance, with the messages of [check](#check);
  - a plan archived as `done`: at least one slice, else `plan has no slices`, and each slice `done`: ``slice `<heading>` is <status>, not done``, or `is without status, not done`;
  - a review: `finding <id> is still open` for each finding whose disposition's first word is `open`;
  - a design: `known issue <id> is still listed; move it to the design that takes over, or remove it`;
  - an experiment: unless `Sources:` has a value, ``Setup: `<label>` is empty (research lists `- Sources:` instead)`` for each of `Commit`, `Environment` and `Command` without one, and `Conclusion is empty` when that section holds only whitespace and template guidance;
  - an investigation: ``Reproduction: `<label>` is empty`` for `Commit`, `Environment` and `Command`, and ``Resolution: `<label>` is empty`` for `Root cause`, `Fix` and `Verification`.
- A label line is `Label: value` or `- Label: value`, `*` ignored so that `**Label:**` counts; indented lines below a label extend its value.

```text
canon.py archive ID STATUS
```

- `archive` changes no file and exits when the Git index has unmerged entries (`canon: resolve the merge conflicts first`), when an index start marker lacks its end marker ([D005§regeneration: regeneration](D005-docs-index.md#regeneration)), when no or several docs have ID, for D000 ([D002§project-overview-d000: D000](D002-overview-and-as-built.md#project-overview-d000)), when the doc is archived (`canon: <id> is already archived`) when STATUS is no terminal status of its type (`canon: <id> can be archived as adopted or dropped`, listing the type's), and for a design with a sub-design outside `archived/` (`canon: <id> has live sub-designs <ids>; archive them first`). A failed terminal condition prints `ERROR <path>: <problem>` for each and exits 1. `archive -h` lists each type's terminal statuses.
- Otherwise it sets `status` to STATUS and `updated` to today, from any non-terminal status, and moves the doc to `<docs root>/archived/<type directory>/` under its file name and its attachment directory to `archived/<type directory>/<id>/`, with `git mv` in a Git checkout and a plain rename outside Git or when Git refuses. It regenerates the indexes ([D005§regeneration: regeneration](D005-docs-index.md#regeneration)), prints `<old path> -> <new path>` and exits 0.
- Every inline link or image, `[text](target)` outside code with a path as its target, in each `.md` file of the repository that `check` reads, that points at the moved doc or into its attachment directory follows the move, and the moved files' own links are rewritten for their new directory. A root-absolute link (`/path`) stays root-absolute, an anchor stays, link texts stay, and a rewritten target percent-encodes whitespace, `%`, `#`, `?`, `(` and `)` in its path. `adopt` ([D004§adopt: adopt](D004-project-setup.md#adopt)), `rename`, `renumber` and `init`'s move of a design to D000 rewrite links by this rule too. The docs whose links change keep their `updated`, so `check` reports each one HEAD holds until `check --fix`.

### Frontmatter

A doc starts with a `---` line, and its frontmatter ends at the next `---` line; without both, `check` errors with ``missing or unterminated `---` frontmatter`` and checks nothing else of the doc. Each non-blank line between is `key: value`, else ``unparseable frontmatter line: <line>``. A value loses surrounding whitespace and `'` or `"` characters. In a list field, `[a, b]` is a list, its items split at commas and stripped the same way, empty items dropped; in an integer field, digits alone make an integer.

```yaml
---
status: active
created: 2026-03-02
updated: 2026-05-17
revision: 4
modules: [auth, gateway]
summary: Token issuing, refresh and session lifecycle.
refs: [D001, D007]
owns: [auth-token, session]
paths: [src/auth/**, src/session/]
reviewed: 4
reviewers: [claude-opus-high, gpt-high]
implemented: 4
---
```

- Every type requires `status`, `created`, `updated`, `revision`, `modules`, `summary` and `refs`; designs also `owns` and `paths`, plans `based_on`. Designs may add `reviewed`, `reviewers`, `implemented` and `as_built`, plans `reviewed` and `reviewers`. `check` errors with ``missing frontmatter field `<key>` ``, ``unknown frontmatter field `<key>` `` for any other field, and ``` `<key>` must be a list like [a, b] ``` for a list field (`modules`, `refs`, `owns`, `paths`, `based_on`, `reviewers`) that is no list.
- `created`, `updated`: dates, ``` `<key>` must be YYYY-MM-DD ``` otherwise, and ``` `updated` is earlier than `created` ```. `updated` is the date of the doc's last content change ([check](#check)).
- `revision`: a positive integer (``` `revision` must be a positive integer ```) counting semantic changes: bumped when a goal, spec or plan changes meaning, never for wording.
- `modules`: the modules the doc concerns; empty means the whole project of its docs root.
- `summary`: one line, which feeds the index and `find`. Empty: ``` `summary` is empty ```, at the unfinished level ([check](#check)). Over 160 characters once trimmed: `WARN` ``` `summary` is <n> chars (max 160) ```.
- `refs`: ids of related docs, each an existing doc's (``` `refs` entry <id> does not exist ```), including every doc the body links to ([Links and references](#links-and-references)).
- `owns` (D): topics the design is the single authority for, kebab-case (``` `owns` entry `<topic>` must be kebab-case ```) and unique across non-archived designs of every docs root: `` topic `<topic>` is already owned by <id> `` on each later design.
- `paths` (D): globs, relative to the project directory, of the code the design governs; they drive `which`, `affected` and `audit`. Whitespace and leading `./` are ignored; `**/` matches any directories, none included, `**` anything, `*` any characters but `/`, `?` one character but `/`, and a trailing `/` everything below; an entry also matches every path below a match; other characters, `[` included, match themselves. `WARN` ``` `paths` entry `<entry>` matches no file ``` when no file of the project that `check` reads matches, except for an archived design. D000's `paths` and docs: [D002: Project overview and as-built designs](D002-overview-and-as-built.md).
- `reviewed`, `reviewers` (D, P): the revision that passed the review gate and who reviewed it, `manual:<model>` for a review the user ran; the gate sets them ([D007: Change tiers and the review gate](D007-change-tiers.md)). On a design or plan with `reviewed`: ``` `reviewed` must be an integer revision not above `revision` ``` and, with `reviewers` empty, ``` `reviewers` must list who reviewed revision <n> ```; another type gets only the unknown-field error. A plan `in-progress` without `reviewed`: ``plan in progress without `reviewed` ``. Otherwise, a design `accepted` or `active`, or a plan `accepted` or `in-progress`, whose `reviewed` differs from `revision`: ``revision <n> is not reviewed (reviewed: <r>); pass the review gate, then set `reviewed` and `reviewers` ``, `<r>` reading `none` without the field, a `WARN` that `--base` makes an error.
- `implemented` (D): the revision the code fully implements, required once the design is `active`. Below `revision`, the spec leads the code and the difference is an open plan's work, not a defect. Errors: ``` `implemented` must be an integer revision from 1 to `revision` ```; ``` `implemented` r<i> is above `reviewed` r<r>; implement only reviewed revisions ```; ``` `implemented` is set but status is `<status>`; a design whose code has landed is `active` ``` for `draft` and `accepted`; for an active design without it, ``active design needs `implemented`: the revision its code fully implements``, fixable with `implemented: 1` when the design's `revision` at HEAD, or in the work tree for a file HEAD lacks, is 1 and no non-archived plan names it in `based_on`.
- `as_built` (D): [D002§as-built-revisions: as-built](D002-overview-and-as-built.md#as-built-revisions).
- `based_on` (P): the design revisions the plan was written against, `D012@r4`; `new P --from` fills it. Errors: ``` `based_on` entry `<entry>` must look like D003@r4 ```, ``` `based_on` design <id> does not exist ```. While the plan's status is not terminal and the design's `revision` is above the entry's: `WARN` ``based on <entry> but <id> is at r<n>; re-check the plan and update `based_on` ``.

### Known issues, findings and slices

A design lists in `## Known issues`, present only while it lists any, the problems found in it or in the code it governs that are neither fixed nor declined:

```markdown
| ID | Severity | Issue | Source | Since | Next |
|----|----------|-------|--------|-------|------|
| D003-K1 | major | Refresh retries break D005§queue-limits | P007 gate | 2026-10-21 | decide |
```

- Ids run `<design id>-K1`, `-K2`, …, unique in the table. Severity is `blocker`, `major` or `minor`. Source is where it was found: a gate (`P007 gate`), a plan or one of its slices (`P007`, `P007 S3`), other work at the HEAD it ran on (`code review 3f9a1c2`, `docs step 3f9a1c2`, `L0 3f9a1c2`), an as-built revision of the commit it records (`as-built 3f9a1c2`), or a review finding (`R004-F2`). Since is the date it was recorded. Next is what it waits for: `decide` (the user's decision), `fix` (a code change), `L1` (a revision of this design) or `L2` (`/canon-design`).
- Rows are not spec: changing them bumps no `revision`, passes no gate and does not count as checking the design against its code. The change that resolves an issue deletes its row, or else the audit that finds it resolved; one the user declines leaves as [D007§design-problems: design problems](D007-change-tiers.md#design-problems) states. The section goes with its last row, and a design that lists any cannot be archived.
- How an agent reads the known issues of the designs it works from is [D007§design-problems: design problems](D007-change-tiers.md#design-problems)'s.

A review lists its findings in `## Findings`, one row each:

```markdown
| ID | Severity | Finding | Disposition |
|----|----------|---------|-------------|
| R003-F1 | major | Refresh races with logout | moved I012 |
```

Ids run `<review id>-F1`, `-F2`, …; Severity as above. Disposition is `open`, `fixed <commit>`, `moved <id>` (handed to the C, D, P or I that now tracks it, a design as a known issue) or `declined <reason>`.

`check` reads as rows the lines of the section outside code fences that start with `|`, apart from a header row whose first cell reads `ID` in any case and separator rows of `-`, `:` and spaces; cells past the table's columns are ignored. It errors with:

- `known issue row must be | <id>-K<n> | severity | issue | source | since | next |`, or `finding row must be | <id>-F<n> | severity | finding | disposition |`, for a row whose first cell is not the doc's id, `-K` or `-F` and digits, or that has fewer cells than the columns;
- `duplicate known issue id <id>`, `duplicate finding id <id>`, and `<id> severity must be one of blocker, major, minor`;
- for a known issue: `<id> needs the issue and its source`, `<id> since must be the date it was recorded, YYYY-MM-DD`, `<id> since <date> is later than today` and `<id> next must be one of decide, fix, L1, L2`;
- for a finding: `<id> disposition must start with one of open, fixed, moved, declined`, and ``<id> moved to unknown doc `<id>` `` when no doc has the id after `moved`; what follows `fixed` or `declined` goes unchecked.

A `## Known issues` section with no row, well-formed or not, gives `WARN` ``` `## Known issues` lists no issue; delete the section ```.

A plan's slices are the `### ` headings of `## Slices` outside code fences. A slice's status is the first `Status:` line, optionally after `- ` and with `*` ignored, before the next slice; `check` errors with ``slice `<heading>` needs a `Status:` line with one of todo, in-progress, done, paused`` when it is missing or another value. The `S1: <name>` form and the `Risk:` line go unchecked.

### Links and references

- A section is referenced as `[D003§token-refresh: refresh flow](../designs/D003-auth.md#token-refresh)` and a whole doc as `[D003: auth design](../designs/D003-auth.md)`, never by line number. Each standard lives only in the design that owns its topic, and everywhere else links to it.
- `check` reads the inline links `[text](target)` and images `![alt](target)`, with an optional `"title"`, outside fenced code and inline code, in each numbered doc below its frontmatter, each project's `AGENTS.md`, the `.md` files under `guides/` and `assets/`, and an index file while it is up to date ([D005§check: check](D005-docs-index.md#check)). It skips a target with a URL scheme or starting with `//`, resolves `/path` from the repo root and any other path from the file's directory, percent-decoded, and errors, with the line, as `ERROR <path>:<line>: <message>`:
  - `broken link <target>` when nothing exists there;
  - `missing anchor #<anchor>` for an anchor in the same file, `missing anchor #<anchor> in <path>` for a `.md` target, that no heading's slug matches;
  - for a link, not an image, to a numbered doc: `link to <id> must read [<id>: ...] or [<id>§slug: ...] with #slug` unless the text starts with the doc's id, an optional `§<section>`, `: ` and a non-space character, and `link text section and #anchor differ; use [<id>: ...] or [<id>§slug: ...] with #slug` when the section and the anchor differ, a missing one counting as empty.
- A heading's slug is its text with links reduced to their text and backticks dropped, trimmed, lowercased, every character other than letters, digits, `_`, `-` and spaces dropped and spaces turned into `-`; a second heading with the same slug gets `-1`, a third `-2`. Headings in fenced code do not count, and trailing `#` characters of a heading are no part of its text.
- Each numbered doc a doc links to, other than through an image or to itself, belongs in its `refs`: ``linked docs missing from `refs`: <ids>``, fixable by appending them in sorted order.

### Templates and `new`

```text
canon.py new TYPE SLUG [--title T] [--root DIR] [--parent D012] [--from D012]
```

- TYPE is a type letter in either case or a type's directory name, plural or singular (`designs`, `design`); else `canon: unknown type <type>; use one of C D P R E I`. A SLUG that is not kebab-case ends `new` with `canon: slug must be kebab-case`.
- The project is `--root`, a project directory or its `docs/`, else the nearest directory from the working directory up to the repo root that holds an `AGENTS.md`; without one, ``canon: no AGENTS.md at <absolute path>; set the project up with `canon.py init` first``.
- `--parent` takes a top-level design and TYPE D, else `canon: --parent takes a top-level design and only applies to designs`, and excludes `--root`: `canon: --parent puts the sub-design beside its parent; drop --root`. The sub-design goes into the parent's docs root, with the parent's id and its first free letter, else `canon: <id> has no free sub-design letter; create a new top-level design`. Without `--parent`, the doc gets the next free id ([Ids and file names](#ids-and-file-names)).
- `--from` applies to TYPE P and takes an accepted or active design, else `canon: --from takes an accepted or active design`. The plan gets the design's `modules`, `refs: [<id>]`, `based_on: [<id>@r<revision>]` and, after its H1, the line `Implements [<id>: <title>](<relative path>).` With another TYPE, `new` ends with `canon: --from only applies to plans`.
- The title is `--title`, else the slug with each `-` turned into a space and its first letter capitalized (`api-v2` gives `Api v2`).
- `new` writes `<project>/docs/<type directory>/<id>-<slug>.md`, creating directories, and exits with `canon: <path> already exists` rather than overwrite a file. It then regenerates the indexes ([D005§regeneration: regeneration](D005-docs-index.md#regeneration)) and prints the path relative to the repo root.
- It allocates the id under the lock `.canon/id.lock` at the repo root, which the OS releases when the holder ends and nothing breaks by age, and exits with `canon: another canon command has held .canon/id.lock for a minute; let it finish` after waiting 60 s. Parallel runs get distinct ids.

The file is the frontmatter, a blank line, the H1 and the type's template:

```markdown
---
status: draft
created: 2026-11-10
updated: 2026-11-10
revision: 1
modules: []
summary: 
refs: []
owns: []
paths: []
---

# D012: Api v2

## Goals

<!-- canon: What this design must achieve, measurable where possible. -->

## Spec
```

- The frontmatter holds the type's first status, `created` and `updated` today, `revision: 1`, empty `modules`, `summary` and `refs`, and empty `owns` and `paths` for a design or `based_on` for a plan.
- The template holds each required section, in the order of [Doc types](#doc-types), as `## <name>`, a blank line, a guidance comment `<!-- canon: ... -->` and a blank line, with these differences: a design's adds `## Budgets` before Decisions, its guidance saying to delete the section when there are no targets; a review's Findings holds the table's header and separator rows before its guidance, which names `<id>-F1` and the severity and disposition values; an experiment's Setup holds `- Commit:`, `- Environment:` and `- Command:` before its guidance, which says research replaces them with `- Sources:`; an investigation's Reproduction holds those three labels and its Resolution `- Root cause:`, `- Fix:` and `- Verification:`, with no guidance. The guidance texts are `TEMPLATES` in `canon.py`; D000's template is [D002§project-overview-d000: D000](D002-overview-and-as-built.md#project-overview-d000).
- Every guidance comment is replaced with content.

### check

```text
canon.py check [--fix] [--base REF]
```

- `check` checks every doc of every docs root, archived ones included, with the rules of this design, D000's and `as_built`'s ([D002: Project overview and as-built designs](D002-overview-and-as-built.md)) and the index's ([D005§check: check](D005-docs-index.md#check)).
- It prints one line per problem, sorted by path and then line, `<LEVEL> <path>[:<line>]: <message>` with `ERROR` or `WARN`, then `canon check: <docs> docs, <errors> errors, <warnings> warnings`, followed without `--fix` by `; <n> fixable with --fix` when any problem is. It exits 1 when there is an error, else 0.
- This design's `WARN` problems are a long `summary`, the line limits, `paths` entries that match no file, a Known issues section without issues, a plan behind its `based_on` and a revision pending review. The unfinished level applies to an empty `summary` and to template guidance: `WARN` for a doc whose status is one of its type's non-terminal statuses, other than a design `accepted` or `active` and a plan `accepted` or `in-progress`, and `ERROR` otherwise. Under `--base`, every unfinished-level problem and every pending review is an `ERROR`. Its other problems are errors.
- Template guidance: ``template guidance `<!-- canon: ... -->` left in the doc`` when a line outside fenced code, inline code removed, holds `<!-- canon:`.
- Line limits: a file's lines are counted as `wc -l` counts them, plus a last line without a newline. `WARN` `<n> lines (max 500)` for a numbered doc over 500, followed for a top-level design by `; split into sub-designs (<id>A, <id>B, ...)` and for a sub-design by `; make it a new top-level design`; `WARN` `<n> lines (max 150); move detail into docs` for a project's `AGENTS.md` over 150.
- `updated`: in a Git checkout with a HEAD commit, for a doc whose file differs from its version at HEAD under the same path, when the lines other than those starting with `implemented:` or `as_built:` differ, and `updated` equals HEAD's and is not today: ``content changed but `updated` was not bumped``, fixable with today's date.
- `--fix` first exits on an index start marker without its end marker ([D005§regeneration: regeneration](D005-docs-index.md#regeneration)). It runs the checks and applies each fix, setting the field, in place or as a new line before the closing `---`, or deleting it, and prints `fixed <path>: set <field>` or `fixed <path>: deleted <field>` for each; it regenerates the indexes as D005 states, then checks again and prints that result. The fixes are `refs`, `updated`, `implemented`, `as_built` and the indexes.
- `--base REF` makes the unfinished level and pending reviews errors and adds the deleted-doc and collision checks against the branch ([Ids and file names](#ids-and-file-names)). Before any fix, `check` ends with `canon: no merge base with <REF>` when REF shares no history with HEAD, and with `canon: cannot diff against <REF>...HEAD` when Git cannot diff against REF otherwise.
- `check`, `new` and `archive` end with `canon: git <subcommand> failed in <dir>: <reason>` when Git fails to list the files, look HEAD up, diff the work tree against HEAD or list unmerged entries, rather than read the failure as an empty result.

### Writing rules

Agents and people read docs, usually after reaching them through a pointer: an `AGENTS.md` line, a link, a `find` hit on a summary or heading. `writing.md` applies to every doc:

- Say each thing once, in the doc that owns it, and link to it everywhere else.
- Use the fewest plain words that state the exact meaning; a reader new to the project understands the doc without the conversation that produced it.
- Record only the final state: no discussion history, superseded drafts or "X rather than Y" contrasts with an earlier proposal. A rejected alternative stays only as a one-line Decision when it is likely to be proposed again.
- State the correct approach. A counter-example is added only for a typical, likely misuse, and a prohibition only as a hard guardrail, paired with the behavior to follow instead.
- Prefer numbers to adjectives, code (signatures, schemas, commands) to prose for interfaces, and lists to tables unless the facts are short and tabular.
- Write `summary` lines, titles and headings as pointers that lead with the words a reader would search for.
- Keep a topic's definition, rules and caveats under one heading.
- Record what the repository cannot tell (reasons, unwritten conventions, gotchas), and name the command or file for facts the environment already states.
- Cut every sentence that changes nothing a capable reader would do anyway.
- `AGENTS.md` holds only the pointers and rules every session needs; detail goes into designs.
- Design for the project's real constraints: a feature's input validation, the permissions its spec states and protection of the data it handles are part of the feature. Further security hardening comes only when the project or feature is security-related or the user asks, and the design states it.
- Avoid wording that rots, such as "currently", "new" or "recently"; the frontmatter carries time.
- Write docs in the project's documentation language, keeping the template's section headings, labels and table headers in English, since `canon.py` parses them.

## Decisions

- A doc is archived, never deleted, and its id is never reused: the id is a doc's identity (the `canon` skill's Rules).
- A link to a doc carries the doc's id in its text, and for a section the section's slug (the `canon` skill's Rules; reason unknown, kept as found).
- Frontmatter is a flat subset of YAML, one `key: value` per line with `[a, b]` lists, that `canon.py` parses itself, since it runs on the standard library alone ([D000§decisions: decisions](D000-project-overview.md#decisions)).
- Brackets make a list only in list fields, so a `summary` such as `[a, b]` stays text (0b2c737; `test_brackets_make_lists_only_in_list_fields`).
- A change to the `implemented` or `as_built` line alone needs no `updated` bump: `implemented` tracks the code and `as_built` the pending gate, not the doc (`content_lines` in `canon.py`; `test_setting_implemented_alone_needs_no_updated_bump`).
- `check --fix` gives `implemented: 1` only to an active design never revised and named by no open plan: a design becomes active once its code lands, so one never revised implements r1, while for a revised design only the code and the history can tell (`check_doc` in `canon.py`; `ImplementedTest`; 6fc017c).
- An empty `summary` and template guidance only warn until a design or plan passes its gate or a doc is archived, and fail under `--base` (0b2c737; reason unknown, kept as found).
- Code review and the review gate produce no R doc; what the user leaves for later becomes a known issue of a design or a line in a plan's Notes ([D007§merging-findings: merging findings](D007-change-tiers.md#merging-findings)) (1c7c1f0; reason unknown, kept as found).
- `archive`, `adopt`, `rename`, `renumber` and `init`'s move of a design to D000 share one link rewriting, so all encode targets alike, and the design that takes on the moving commands owns its rule: D006, with `archive` ([D004§decisions: decisions](D004-project-setup.md#decisions); the user's decision).
- The line limit warns and never fails, on every type, with a split hint for designs only (`check_doc` in `canon.py`; reason unknown, kept as found).
- Sub-designs have one level: a sub-design that outgrows itself becomes a new top-level design (`doc-types.md`; reason unknown, kept as found).

## Known issues

| ID | Severity | Issue | Source | Since | Next |
|----|----------|-------|--------|-------|------|
| D006-K1 | minor | `check` counts the parts a file splits into at newlines, so 500 lines ending in a newline warn as 501, and `AGENTS.md` alike at 150 | as-built 0872d6d | 2026-11-10 | fix |
| D006-K2 | minor | A missing `status` also gives ``status `None` invalid``, and the pending-review warning reads `(reviewed: None)` | as-built 0872d6d | 2026-11-10 | fix |
| D006-K3 | minor | `reviewed` on a C, R, E or I doc also gets the `reviewed` and `reviewers` checks besides the unknown-field error | as-built 0872d6d | 2026-11-10 | fix |
| D006-K4 | minor | Known-issue and finding rows are read inside code fences too, so a fenced example row gives a row error | as-built 0872d6d | 2026-11-10 | fix |
| D006-K5 | minor | A live status inside `archived/` gives ``use `canon.py archive` ``, which refuses an archived doc | as-built 0872d6d | 2026-11-10 | fix |
| D006-K6 | minor | `new` ignores `--from` for a type other than P, and runs the `--root` lookup with `--parent`, then ignores it | as-built 0872d6d | 2026-11-10 | fix |
| D006-K7 | minor | An archived design warns for each `paths` entry that matches no file | as-built 0872d6d | 2026-11-10 | fix |
| D006-K8 | minor | `archive` accepts leftover guidance or an empty `summary`, which `check` then reports on the archived doc, and neither catches a `done` plan with no slices or a Conclusion holding only template guidance | as-built 0872d6d | 2026-11-10 | fix |
| D006-K9 | minor | `archive` archives a design and leaves its sub-designs live | as-built 0872d6d | 2026-11-10 | fix |
| D006-K10 | minor | No command changes a non-terminal status | R003-F36 | 2026-11-10 | decide |
| D006-K11 | minor | The line-limit hint tells a sub-design to split into `<id>A`, `<id>B`, ..., which one-level sub-designs forbid | as-built 0872d6d | 2026-11-11 | fix |
| D006-K12 | minor | The unknown-entry message inside `archived/` also lists `archived/`, `guides/` and `assets/` as allowed | as-built 0872d6d | 2026-11-11 | fix |
| D006-K13 | minor | With a HEAD commit, a REF that shares no history with HEAD gives `cannot diff against <REF>...HEAD`, since the deleted-doc diff fails first; `no merge base` shows only without a HEAD commit | as-built 0872d6d | 2026-11-11 | fix |
