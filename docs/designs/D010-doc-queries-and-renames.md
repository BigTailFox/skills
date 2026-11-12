---
status: active
created: 2026-11-12
updated: 2026-11-12
revision: 1
modules: [canon]
summary: Doc queries and renames with canon.py show, find, which and affected, and rename and renumber, with the references and id collisions renumber settles.
refs: [D002, D004, D005, D006]
owns: [doc-queries, doc-renames, doc-renumbering]
paths: [skills/governance/canon/scripts/canon.py, skills/governance/canon/SKILL.md, tests/test_canon.py]
reviewed: 1
reviewers: [claude-opus-5.5]
implemented: 1
---

# D010: Doc queries and renames

## Goals

1. A session finds the docs on a topic with one `find` call and reads one section of a doc with one `show` call, without opening the file.
2. Before editing a file, one `which` call names every live design that governs it; before committing, one `affected` call names every live design the changes touch, which the commit's `Refs:` trailer lists, and the live plans based on them. Both flag a design whose spec leads its code and count its known issues.
3. After `rename` or `renumber` and `check --fix`, no link, `refs`, `based_on` or `moved` entry that named the doc is broken or names an unknown doc.
4. After a merge or rebase leaves two docs with one id, `renumber` on the doc the branch added settles the collision without guessing: whatever neither the branch merged onto nor the links attribute is kept and listed for the user, or, for a sub-design, stops `renumber` before any change.

Out of scope: `paths` and the files a design governs ([D006§frontmatter: frontmatter](D006-doc-model.md#frontmatter)); docs by their name, which designs govern only through an exact entry ([D002§project-docs: project docs](D002-overview-and-as-built.md#project-docs)); ids, file names and the `check` errors that ask for `renumber` ([D006§ids-and-file-names: ids and file names](D006-doc-model.md#ids-and-file-names)); ids that history keeps taken, and `init`'s move of a design to D000, which moves it as `renumber` does ([D002§project-overview-d000: D000](D002-overview-and-as-built.md#project-overview-d000)); the link rewriting that every moving command shares ([D006§statuses-and-archiving: statuses and archiving](D006-doc-model.md#statuses-and-archiving)); index regeneration ([D005§regeneration: regeneration](D005-docs-index.md#regeneration)); `adopt` ([D004§adopt: adopt](D004-project-setup.md#adopt)).

## Spec

These commands read the docs of every docs root, live and archived, as `check` reads them ([D006§layout: layout](D006-doc-model.md#layout)), and run from any directory in the repository. `show`, `find`, `which` and `affected` change no file. A refusal prints `canon: <message>` on standard error and exits 1; all other output goes to standard output, with paths relative to the repo root. A Git query that fails while they list the files, or while `rename` and `renumber` look for unmerged entries, ends them with `canon: git <subcommand> failed in <dir>: <reason>`, as for `check` ([D006§check: check](D006-doc-model.md#check)). The agent-facing text of this spec is the Tool table's rows for these commands in the `canon` skill's `SKILL.md`.

### Doc lines

`find`, `affected` and `audit` ([D002§unchecked-commits-in-audit: unchecked commits](D002-overview-and-as-built.md#unchecked-commits-in-audit)) list a doc as a doc line, and `which` as one without its status:

- `<id> <status> <path> - <summary><notes>`: the path relative to the repo root, `?` for an absent `status`, nothing for an absent `summary`.
- `<notes>`, for a design only: ` [spec r<revision> leads code r<implemented>]` when `implemented` is an integer below `revision`, then ` [1 known issue]` or ` [<n> known issues]`, counting the rows of its Known issues table whose ID cell is `<id>-K<n>` and that have all six cells ([D006§known-issues-findings-and-slices: known issues](D006-doc-model.md#known-issues-findings-and-slices)), when it lists any.

### show

```text
canon.py show ID
canon.py show ID#SLUG
```

- ID names a doc, live or archived; `§` may stand for `#`. Another form of argument exits with `canon: expected an id like D003 or D003#slug`; an ID that no doc or several docs have exits with the messages [D006§ids-and-file-names: ids](D006-doc-model.md#ids-and-file-names) gives for `archive`.
- Without SLUG it prints the doc's outline and exits 0:

  ```text
  docs/designs/D003-auth.md
  status: active
  revision: 4
  ...
  # D003: Auth and sessions
  Goals  #goals
  Spec  #spec
    Token refresh  #token-refresh
  Decisions  #decisions
  ```

  That is the path relative to the repo root; the frontmatter lines as written, none for a doc without frontmatter; `# <id>: <title>`, the title empty when the H1 does not start with `<id>: `; and one line per heading of level 2 to 6 outside code fences, indented two spaces per level below 2: its text as written, two spaces and `#<slug>`, the slug as [D006§links-and-references: links and references](D006-doc-model.md#links-and-references) defines it.
- With SLUG it prints `<path>#<SLUG>`, then the first heading, H1 included, whose slug equals SLUG exactly, through the line before the next heading of the same or a higher level, else through the end of the file, trailing blank lines dropped, and exits 0. Without such a heading, a design's `known-issues` prints `<id> has no known issues` and exits 0; any other SLUG exits with `canon: <id> has no section #<SLUG>`.

### find

```text
canon.py find WORD... [--archived]
```

- A doc's metadata is its id, title, summary, `owns` and `modules` joined by spaces. The doc matches when each WORD, ignoring case, is a substring of its metadata, or of its metadata, a space and the text of one heading of level 2 to 6 outside code fences, which is then a matching heading.
- Archived docs take part only with `--archived`.
- For each matching doc, ordered by type as the index groups are ([D005§format: format](D005-docs-index.md#format)), then by number and letter across docs roots, it prints the doc line and, unless every WORD is in the metadata, one line per matching heading: two spaces, `<id>#<slug> <heading text>`.
- With no match it prints `no match`. It exits 0.

### which

```text
canon.py which FILE...
```

- Each FILE is resolved from the working directory, symlinks followed, and printed relative to the repo root. It need not exist; one outside the repository matches no design.
- For each FILE in the order given, it prints one line per live design whose `paths` govern it, in id order: `<file>: <id> <path> - <summary><notes>`. With none: `<file>: doc` for a doc ([D002§project-docs: project docs](D002-overview-and-as-built.md#project-docs)), else `<file>: no design`. It exits 0.

### affected

```text
canon.py affected [FILE...] [--base REF]
```

- The files are the FILE arguments, resolved as for `which`. Without them, they are the changed files: in a Git checkout with a HEAD commit, the files `git diff --name-only HEAD` lists, staged or not, deletions included, and the untracked files Git does not ignore; with `--base REF`, also the files `git diff --name-only REF...HEAD` lists, the branch's changes since its merge base with REF. A renamed file counts under its old and its new path, whatever Git's rename detection pairs. On a branch with no commit, and outside Git, they are all the files `check` reads, and `--base` goes unread. `--base` is ignored with FILE arguments.
- It exits with `canon: cannot diff against <REF>` when Git cannot diff against REF, and with `canon: git <subcommand> failed in <dir>: <reason>` when listing the changes or the untracked files fails.
- For each live design that governs one of the files, ordered by the first file it governs (the changed files in sorted order, FILE arguments as given), it prints the doc line, then `  <file>` for each file the design governs, in the same order. Then it prints `plan <doc line>` for each live plan whose `based_on` names one of these designs, in id order. With no such design it prints `no design governs the changed files`, also for FILE arguments. It exits 0.

### Moving docs

`rename` and `renumber` share these rules:

- They change no file and exit 1 when the Git index has unmerged entries (`canon: resolve the merge conflicts first`) or an index start marker lacks its end marker ([D005§regeneration: regeneration](D005-docs-index.md#regeneration)), before they read their other arguments.
- Each file or directory they move stays in its directory, so a live doc stays live and an archived one archived. They move it with `git mv` in a Git checkout, and with a plain rename outside Git or when Git refuses.
- Every link to a moved file, or into a moved directory, follows it by the rule of [D006§statuses-and-archiving: statuses and archiving](D006-doc-model.md#statuses-and-archiving). They then regenerate the indexes.
- They set no `updated`, so `check` reports each other doc they change that HEAD holds until `check --fix`, as [D006§check: check](D006-doc-model.md#check) says.

### rename

```text
canon.py rename ID SLUG
```

- ID names a doc of any type, live or archived, sub-designs included; an ID that no doc or several docs have exits with the messages [D006§ids-and-file-names: ids](D006-doc-model.md#ids-and-file-names) gives for `archive`. D000 then exits with `canon: D000 keeps its file name, which the AGENTS.md block links`, and a SLUG that is not kebab-case with `canon: slug must be kebab-case`.
- It moves the doc's file to `<ID>-<SLUG>.md`, prints `<old path> -> <new path>`, both relative to the repo root, and exits 0. A SLUG equal to the doc's own changes no file and prints the same line.
- The H1, link texts, and the attachment directory with the names of its files stay as they are.

### renumber

```text
canon.py renumber ID|PATH [NEW] [--base REF]
```

- It is run only when `check` asks for it, for an id collision ([D006§ids-and-file-names: ids](D006-doc-model.md#ids-and-file-names)) or a D000 in a module's docs ([D002§project-overview-d000: D000](D002-overview-and-as-built.md#project-overview-d000)), as `renumber -h` and the Tool table say. It checks for neither and renumbers any doc but the repo root's D000.
- After the refusals of [Moving docs](#moving-docs), it holds the id lock until it ends, as `new` does ([D006§templates-and-new: templates and new](D006-doc-model.md#templates-and-new)).
- The first argument is an id when it reads as one (`D012`, `D012A`), and names a doc, live or archived: `canon: unknown document <id>` when no doc has it, `canon: <id> is ambiguous; pass the file path of the doc to renumber` when several do. Otherwise it is the path of a doc file, resolved from the working directory, and any other path exits with `canon: <argument> is not a canon doc`. The repo root's D000 exits with `canon: D000 is the project overview every project keeps; renumber only a D000 in a module's docs`. With `--base`, a REF that names no commit exits with `canon: unknown ref <REF>`.
- A top-level doc gets a top-level id of its type, and a sub-design another letter of its parent: NEW, written with extra zeros normalized (`D0005` gives `D005`, `D0001B` gives `D001B`), else the next free one, the number one above the highest taken for the type or the first free letter from `A`. Taken are the ids of the doc files in the work tree, those HEAD's history has had ([D002§project-overview-d000: D000](D002-overview-and-as-built.md#project-overview-d000)) and, with `--base`, those of the doc files in REF's tree; a number is taken while any id of its type with that number is, a sub-design's included. A NEW that does not fit exits:
  - for a top-level doc, with `canon: new id must be a top-level <type letter> id` when NEW is of another type, a sub-design id or no id;
  - for a sub-design, with `canon: new id must be a sub-design of <parent>` when NEW, normalized, is not `<parent>` and a letter;
  - with `canon: <NEW> is already used`, NEW as given, when NEW is taken.

  Without NEW, a sub-design whose parent has no free letter exits with `canon: <parent> has no free sub-design letter`.
- A top-level design's sub-designs in its docs root follow it: `<old id>B` becomes `<new id>B`. Each moved doc's file becomes `<new id>-<slug>.md` and its attachment directory `<old id>/` becomes `<new id>/`.
- Besides links, it rewrites:
  - in every doc, live or archived, each `refs` and `based_on` entry naming a moved id, `@r<n>` kept, and in reviews each table line whose last cell is `moved <id>`;
  - in each moved doc, the id of its H1 and each `<old id>-F<n>` and `<old id>-K<n>` in its text.

  No other text changes: elsewhere, a moved id or one of its finding or known issue ids in prose or in another table cell, such as `fixed <id>@r<n>` or a known issue's Source, keeps the old id.
- It prints `<old id> -> <new id>` for each moved doc, the doc first and then its sub-designs in letter order, then the notes of [Id collisions](#id-collisions), then ``run `canon.py check --fix` to finish``, and exits 0.

### Id collisions

While other docs have the renumbered doc's id, `renumber` gives each of these to the renumbered doc, which it then follows, or to the others only on evidence:

- a sub-design of the same number in its docs root, while another doc of the id is in that docs root;
- each file in its attachment directory, while another doc of the id is in the same directory;
- each `refs`, `based_on` and `moved` entry, in any doc, that names a moved id another doc also has.

The evidence:

- With `--base`, REF's tree, when it holds the path of the renumbered doc and of no other doc with the id, or the reverse: a sub-design or attachment file whose path is in REF's tree belongs to the side whose doc is there, any other to the other side; an entry belongs to the side on REF when REF's version of the doc holding it already has it, else to the other side. A `refs` or `based_on` entry matches as written, `@r<n>` included, and a `moved` entry by its finding id and the id it names.
- Links, when only one side has them: a sub-design belongs to the doc it links or that links it, an attachment file to the doc whose body links it, and an entry to the doc that the body of the doc holding it links.
- No evidence, or evidence that disagrees, leaves it unclear.

The results:

- A sub-design follows when it is the renumbered doc's and stays when it is another's. An unclear one ends `renumber` before any change with `canon: cannot tell which <id> owns <paths>; link each sub-design from its parent design or pass --base <ref>, then rerun`, without ` or pass --base <ref>` when `--base` was given. Sub-designs that follow and share an id end it with `canon: sub-designs of <id> share an id; renumber the one this branch added first`.
- The attachment directory moves when each file in it is the renumbered doc's, stays when each is another's, and otherwise stays with the note `kept <directory>: it also holds attachments of another <id>; move this doc's files to <new directory> and fix their links`.
- An entry is rewritten when it is the renumbered doc's, kept when it is another's, and kept when unclear with the note `kept <old id> in <paths>: another doc still has that id; change the entries there that mean <new id>`: one note per id, in id order, its paths sorted and comma-separated, before the attachment notes.

Without another doc of the id, everything follows the renumbered doc.

## Known issues

| ID | Severity | Issue | Source | Since | Next |
|----|----------|-------|--------|-------|------|
| D010-K1 | minor | `renumber` and `init`'s move of a design to D000 rewrite `moved <id>` dispositions but no other plain-text citation of the moved doc's ids, such as `fixed <id>@r<n>`, a known issue's Source (`R004-F2`) or a finding id in prose, so after a conflict renumber they name the old id: they point unnoticed at the other branch's doc with that id, or else `check` reports a disposition fixed in an unknown doc | code review e122546 | 2026-11-11 | L1 |
| D010-K2 | minor | `rename D000 <slug>` moves the overview instead of refusing, so the next `init` writes the `AGENTS.md` block's link to the fixed path again and `check` reports it broken | as-built 374d94d | 2026-11-12 | fix |
| D010-K3 | minor | `renumber` of the repo root's D000 renumbers it instead of refusing, which leaves the project without D000 | as-built 374d94d | 2026-11-12 | fix |
| D010-K4 | minor | `renumber` refuses a sub-design NEW written with extra zeros, such as `D0001B` for a sub-design of D001, with `new id must be a sub-design of D001`, instead of normalizing it | as-built 374d94d | 2026-11-12 | fix |
| D010-K5 | minor | Without FILE arguments, `affected` lists a rename that Git's rename detection pairs under its new path only, as `diff.renames` allows, so a design that governs only the old path is missed and the commit's `Refs:` omits it | as-built 374d94d | 2026-11-12 | fix |
| D010-K6 | minor | `show ID` of a doc without frontmatter prints all its lines but the first and the last as its frontmatter lines | as-built 374d94d | 2026-11-12 | fix |
| D010-K7 | minor | `renumber --base REF` reads REF before the history of HEAD, so in a checkout Git cannot read it exits with `canon: unknown ref <REF>` for a REF that exists, instead of the history error of [D002§project-overview-d000: D000](D002-overview-and-as-built.md#project-overview-d000) | D002 r9 gate | 2026-11-12 | fix |

## Decisions

- `renumber` renumbers any doc it is given but the repo root's D000, with or without a collision, and its `-h` and the Tool table limit its use to what `check` asks for (R001-F23, settled in 4d74020 by the help text); the repo root's D000 is refused, since a project keeps it (the user's decision, 2026-11-12; D010-K3).
- After an id collision, `renumber` gives a sub-design, attachment file or reference to one of the docs sharing the id only when REF's tree or the links show whose it is, stops before any change on an unclear sub-design, and keeps and lists unclear references (550068a).
- `show <id>#known-issues` on a design without the section prints that it has none and exits 0: sessions run it for each design they work from, as the `canon` skill's Reading docs says (8f4f34c).
- `find`, `which` and `affected` exit 0 whether or not anything matches (reason unknown, kept as found).
