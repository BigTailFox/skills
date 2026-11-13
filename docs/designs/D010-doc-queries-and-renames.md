---
status: active
created: 2026-11-12
updated: 2026-11-13
revision: 6
modules: [canon]
summary: Doc queries and renames with canon.py show, find, which and affected, and rename and renumber, with the references and id collisions renumber settles.
refs: [D002, D004, D005, D006, R001]
owns: [doc-queries, doc-renames, doc-renumbering]
paths: [skills/governance/canon/scripts/canon.py, skills/governance/canon/SKILL.md, tests/test_canon.py]
reviewed: 6
reviewers: [claude-opus-5.5]
approved: 2
implemented: 5
---

# D010: Doc queries and renames

## Goals

1. A session finds the docs on a topic with one `find` call and reads one section of a doc with one `show` call, without opening the file.
2. Before editing a file, one `which` call names every live design that governs it; before committing, one `affected` call names every live design the changes touch, which the commit's `Refs:` trailer lists, and the live plans based on them. Both flag a design whose spec leads its code and count its known issues.
3. After `rename` or `renumber` and `check --fix`, no reference that named the doc, whether a link, a `refs` or `based_on` entry, a disposition or a citation of its ids in a doc outside code, is broken or names an unknown doc. After `rename`, no attachment named after the old slug keeps that name, and with `--title` neither the H1 nor a link text reading `<id>: <old title>` keeps the old title.
4. After a merge or rebase leaves two docs with one id, `renumber` on the doc the branch added settles the collision without guessing: whatever neither the branch merged onto nor the links attribute is kept and listed for the user, or, for a sub-design, stops `renumber` before any change.

Out of scope: `paths` and the files a design governs ([D006§frontmatter: frontmatter](D006-doc-model.md#frontmatter)); docs by their name and installed skill files, which designs govern only through an exact entry ([D002§project-docs: project docs](D002-overview-and-as-built.md#project-docs), [D002§installed-skills: installed skills](D002-overview-and-as-built.md#installed-skills)); ids, file names and the `check` errors that ask for `renumber` ([D006§ids-and-file-names: ids and file names](D006-doc-model.md#ids-and-file-names)); ids that history keeps taken, and `init`'s move of a design to D000, which moves it as `renumber` does ([D002§project-overview-d000: D000](D002-overview-and-as-built.md#project-overview-d000)); the link rewriting that every moving command shares ([D006§statuses-and-archiving: statuses and archiving](D006-doc-model.md#statuses-and-archiving)); index regeneration ([D005§regeneration: regeneration](D005-docs-index.md#regeneration)); `adopt` ([D004§adopt: adopt](D004-project-setup.md#adopt)).

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
- With SLUG it prints `<path>#<SLUG>`, then the first heading, H1 included, whose slug equals SLUG exactly, through the line before the next heading of the same or a higher level, else through the end of the file, trailing blank lines dropped, and exits 0. Without such a heading, a design's `known-issues` prints `<id> has no known issues` and exits 0; any other SLUG exits with `canon: <id> has no section #<SLUG>; sections: <slugs>`, the slugs of the outline's headings in its order, separated by `, `, and without `; sections: <slugs>` when the outline has no heading.

### find

```text
canon.py find WORD... [--archived]
```

- A doc's metadata is its id, title, summary, `owns` and `modules` joined by spaces. The doc matches when each WORD, ignoring case, is a substring of its metadata, or of its metadata, a space and the text of one heading of level 2 to 6 outside code fences, which is then a matching heading.
- Archived docs take part only with `--archived`.
- For each matching doc, ordered by type as the index groups are ([D005§format: format](D005-docs-index.md#format)), then by number and letter across docs roots, it prints the doc line and, unless every WORD is in the metadata, one line per matching heading: two spaces, `<id>#<slug> <heading text>`.
- With no match it prints `no match`, followed, without `--archived` and when archived docs would match, by ``; 1 archived doc matches with `--archived` `` or ``; <n> archived docs match with `--archived` ``. It exits 0.

### which

```text
canon.py which FILE...
```

- Each FILE is resolved from the working directory, symlinks followed, and printed relative to the repo root. It need not exist; one outside the repository matches no design.
- For each FILE in the order given, it prints one line per live design whose `paths` govern it, in id order: `<file>: <id> <path> - <summary><notes>`. With none: `<file>: skill` for an installed skill file ([D002§installed-skills: installed skills](D002-overview-and-as-built.md#installed-skills)), `<file>: doc` for a doc ([D002§project-docs: project docs](D002-overview-and-as-built.md#project-docs)), else `<file>: no design`. It exits 0.
- A FILE is missing when nothing exists at its resolved path and, in a Git checkout, neither HEAD's tree nor the Git index holds that path or a file below it. Each line of a missing FILE starts `<file> (missing): ` instead of `<file>: `, such as `src/auht.py (missing): no design`.

### affected

```text
canon.py affected [FILE...] [--base REF]
```

- The files are the FILE arguments, resolved as for `which`. Without them, they are the changed files: in a Git checkout with a HEAD commit, the files `git diff --name-only HEAD` lists, staged or not, deletions included, and the untracked files Git does not ignore; with `--base REF`, also the files `git diff --name-only REF...HEAD` lists, the branch's changes since its merge base with REF. A renamed file counts under its old and its new path, whatever Git's rename detection pairs. On a branch with no commit, and outside Git, they are all the files `check` reads, and `--base` goes unread. `--base` is ignored with FILE arguments.
- With `--base` read, it exits with the `--base` errors of [D006§check: check](D006-doc-model.md#check), and with `canon: git <subcommand> failed in <dir>: <reason>` when listing the changes or the untracked files fails.
- For each live design that governs one of the files, ordered by the first file it governs (the changed files in sorted order, FILE arguments as given), it prints the doc line, then `  <file>` for each file the design governs, in the same order. Then it prints `plan <doc line>` for each live plan whose `based_on` names one of these designs, in id order. With no such design it prints `no design governs the changed files`, also for FILE arguments. It exits 0.

### Moving docs

`rename` and `renumber` share these rules:

- They change no file and exit 1 when the Git index has unmerged entries (`canon: resolve the merge conflicts first`) or an index start marker lacks its end marker ([D005§regeneration: regeneration](D005-docs-index.md#regeneration)), before they read their other arguments.
- Each file or directory they move stays in its directory, so a live doc stays live and an archived one archived. They move it with `git mv` in a Git checkout, and with a plain rename outside Git or when Git refuses.
- Every link to a moved file, or into a moved directory, follows it by the rule of [D006§statuses-and-archiving: statuses and archiving](D006-doc-model.md#statuses-and-archiving). They then regenerate the indexes.
- They set no `updated`, so `check` reports each other doc they change that HEAD holds until `check --fix`, as [D006§check: check](D006-doc-model.md#check) says.

### rename

```text
canon.py rename ID SLUG [--title TITLE]
```

- ID names a doc of any type, live or archived, sub-designs included; an ID that no doc or several docs have exits with the messages [D006§ids-and-file-names: ids](D006-doc-model.md#ids-and-file-names) gives for `archive`. D000 then exits with `canon: D000 keeps its file name, which the AGENTS.md block links`, a SLUG that is not kebab-case with the message `new` gives ([D006§templates-and-new: templates and new](D006-doc-model.md#templates-and-new)), and a TITLE that, once stripped of surrounding whitespace, is empty or holds a line break, `[` or `]`, which would break the link texts and index lines that carry it, with `canon: title must be one line of text without [ or ]`.
- It moves the doc's file to `<ID>-<SLUG>.md`, and each file in its attachment directory, at any depth, whose name up to its first `.` is the doc's old slug to the same directory, SLUG in place of the old slug: `D001/skill-telemetry.zh.md` becomes `D001/telemetry.zh.md`. A file it would move to that exists ends it before any change with `canon: <path> already exists`. It prints `<old path> -> <new path>`, both relative to the repo root, for the doc and then for each attachment file in path order, and exits 0. A SLUG equal to the doc's own moves no file and prints only the doc's `<old path> -> <new path>` line, both paths the same.
- With `--title`, it sets the doc's H1, the first heading of level 1 outside code fences, to `# <ID>: <TITLE>`, TITLE stripped of surrounding whitespace, and in every `.md` file the text of each link to the doc that reads exactly `<ID>: <old title>`, the old title being the H1's text after `<ID>: `, to `<ID>: <TITLE>`. Links to the H1's anchor follow it, as do links to the headings whose link texts it changes ([D006§statuses-and-archiving: statuses and archiving](D006-doc-model.md#statuses-and-archiving)), and in every doc the `§<slug>` after a citation follows the heading anchors of what it names, as in [renumber](#renumber). A doc without an H1 ends it before any change with `canon: <ID> has no H1`.
- The other attachments keep their names and, without `--title`, the H1 and link texts stay as they are.

### renumber

```text
canon.py renumber ID|PATH [NEW] [--base REF]
```

- It is run only when `check` asks for it, for an id collision ([D006§ids-and-file-names: ids](D006-doc-model.md#ids-and-file-names)) or a D000 in a module's docs ([D002§project-overview-d000: D000](D002-overview-and-as-built.md#project-overview-d000)), as `renumber -h` and the Tool table say. It checks for neither and renumbers any doc but the repo root's D000.
- After the refusals of [Moving docs](#moving-docs), it holds the id lock until it ends, as `new` does ([D006§templates-and-new: templates and new](D006-doc-model.md#templates-and-new)).
- The first argument is an id when it reads as one (`D012`, `D012A`), and names a doc, live or archived: `canon: unknown document <id>` when no doc has it, `canon: <id> is ambiguous; pass the file path of the doc to renumber` when several do. Otherwise it is the path of a doc file, resolved from the working directory, and any other path exits with `canon: <argument> is not a canon doc`. The repo root's D000 exits with `canon: D000 is the project overview every project keeps; renumber only a D000 in a module's docs`. With `--base`, a REF that names no commit exits with the unknown-ref error of [D006§check: check](D006-doc-model.md#check).
- A top-level doc gets a top-level id of its type, and a sub-design another letter of its parent: NEW, written with extra zeros normalized (`D0005` gives `D005`, `D0001B` gives `D001B`), else the next free one, the number one above the highest taken for the type or the first free letter from `A`. Taken are the ids of the doc files in the work tree, those HEAD's history has had ([D002§project-overview-d000: D000](D002-overview-and-as-built.md#project-overview-d000)) and, with `--base`, those of the doc files in REF's tree; a number is taken while any id of its type with that number is, a sub-design's included. A NEW that does not fit exits:
  - for a top-level doc, with `canon: new id must be a top-level <type letter> id` when NEW is of another type, a sub-design id or no id;
  - for a sub-design, with `canon: new id must be a sub-design of <parent>` when NEW, normalized, is not `<parent>` and a letter;
  - with `canon: <NEW> is already used`, NEW as given, when NEW is taken.

  Without NEW, a sub-design whose parent has no free letter exits with `canon: <parent> has no free sub-design letter`.
- A top-level design's sub-designs in its docs root follow it: `<old id>B` becomes `<new id>B`. Each moved doc's file becomes `<new id>-<slug>.md` and its attachment directory `<old id>/` becomes `<new id>/`.
- Besides links, it rewrites the references to a moved id:
  - in every doc, live or archived, each `refs` and `based_on` entry, `@r<n>` kept;
  - in reviews, each disposition, the last cell of a table line, that reads `moved <id>` or `fixed <id>@r<n>`;
  - in every `.md` file, in the text of each link or image outside code, each citation of the id of the doc it points at, or into whose attachment directory it points, a reference's leading id included: it follows that doc, taking its new id when the doc moves and staying otherwise;
  - in every doc, each other citation in `summary` and in the body outside code fences and inline code, link texts included and link targets not;
  - in each moved doc, also each `<old id>-F<n>` and `<old id>-K<n>` in code.

  A citation is the id as a whole word in its case, so that `D012` matches neither `D012A`, `D0123` nor `d012`, with the `@r<n>`, `-F<n>` or `-K<n>` right after it, if any: a known issue's Source (`R004-F2`), a path (`D012-auth.md`) or a mention in prose. In every doc, a citation followed by `§<slug>` has its slug follow the heading anchors of what it names after the command, as a link's `§<anchor>` does: a citation, in a link's text, of the doc the link points at names the linked file, the doc or a file in its attachment directory; any other names the moved doc when it takes its new id, the doc it is in when it is that doc's own id, and otherwise the one doc with the id, when only one has it. A doc's citations of its own id are its own: they follow in a moved doc and stay in another doc that has the id. No other text changes: frontmatter fields other than `refs`, `based_on` and `summary`, and code outside a moved doc, keep the old id. A heading whose text changes gets a new anchor, which the links to it follow ([D006§statuses-and-archiving: statuses and archiving](D006-doc-model.md#statuses-and-archiving)).
- It prints `<old id> -> <new id>` for each moved doc, the doc first and then its sub-designs in letter order, then the notes of [Id collisions](#id-collisions), then ``run `canon.py check --fix` to finish``, and exits 0.

### Id collisions

While other docs have the renumbered doc's id, `renumber` gives each of these to the renumbered doc, which it then follows, or to the others only on evidence:

- a sub-design of the same number in its docs root, while another doc of the id is in that docs root;
- each file in its attachment directory, while another doc of the id is in the same directory;
- each reference of [renumber](#renumber), in any doc, that names a moved id another doc also has, other than a doc's citation of its own id and a link text's citation of the doc the link points at, which follow those docs.

The evidence:

- With `--base`, REF's tree, when it holds the path of the renumbered doc and of no other doc with the id, or the reverse: a sub-design or attachment file whose path is in REF's tree belongs to the side whose doc is there, any other to the other side; a reference belongs to the side on REF when REF's version of the doc holding it already has it, else to the other side. A `refs` or `based_on` entry matches as written, `@r<n>` included, and a disposition by its finding id and the id it names. A doc's citations written alike count as one reference, which REF's version of the doc has when it holds that citation at least as many times as the doc does now; when it holds it fewer times but at least once, the reference is unclear.
- Links, when only one side has them: a sub-design belongs to the doc it links or that links it, an attachment file to the doc whose body links it, and a reference to the doc that the body of the doc holding it links.
- No evidence, or evidence that disagrees, leaves it unclear.

The results:

- A sub-design follows when it is the renumbered doc's and stays when it is another's. An unclear one ends `renumber` before any change with `canon: cannot tell which <id> owns <paths>; link each sub-design from its parent design or pass --base <ref>, then rerun`, without ` or pass --base <ref>` when `--base` was given. Sub-designs that follow and share an id end it with `canon: sub-designs of <id> share an id; renumber the one this branch added first`.
- The attachment directory moves when each file in it is the renumbered doc's, stays when each is another's, and otherwise stays with the note `kept <directory>: it also holds attachments of another <id>; move this doc's files to <new directory> and fix their links`.
- A reference is rewritten when it is the renumbered doc's, kept when it is another's, and kept when unclear with the note `kept <old id> in <paths>: another doc still has that id; change the references there that mean <new id>`: one note per id, in id order, its paths sorted and comma-separated, before the attachment notes.

Without another doc of the id, everything follows the renumbered doc.

## Known issues

| ID | Severity | Issue | Source | Since | Next |
|----|----------|-------|--------|-------|------|
| D010-K10 | minor | After `renumber`, a citation of the moved doc in a doc's link text, other than a reference's leading `<ID>§<anchor>`, keeps its old `§<slug>` when the link points at a file in the moved doc's attachment directory whose heading the command changes, since the docs' citations settle before the headings of other files do. | code review 3ccf260 | 2026-11-13 | L1 |

## Decisions

- `renumber` renumbers any doc it is given but the repo root's D000, with or without a collision, and its `-h` and the Tool table limit its use to what `check` asks for (R001-F23, settled in 4d74020 by the help text); the repo root's D000 is refused, since a project keeps it (the user's decision, 2026-11-12).
- After an id collision, `renumber` gives a sub-design, attachment file or reference to one of the docs sharing the id only when REF's tree or the links show whose it is, stops before any change on an unclear sub-design, and keeps and lists unclear references (550068a).
- `renumber` rewrites the citations of a moved id in a doc's text by the same evidence as its other references, since a citation left behind after a collision points unnoticed at the other doc with the id, and keeps the ids in code, which holds examples and literal text (code review e122546, 2026-11-13).
- `rename` renames only the attachments whose name up to its first `.` is the old slug, as a doc's translations and exports are named (`D001/<slug>.zh.md`), and `--title` rewrites only link texts that read `<id>: <old title>`; other names and link texts are the author's choice (R003-F37, 2026-11-13).
- `show <id>#known-issues` on a design without the section prints that it has none and exits 0: sessions run it for each design they work from, as the `canon` skill's Reading docs says (8f4f34c).
- `find`, `which` and `affected` exit 0 whether or not anything matches (reason unknown, kept as found).
- `which` marks a missing file but still answers for it: a design may list code not yet written, and sessions look a file up before creating it, while a typo or a path given from the wrong directory otherwise got a confident answer ([R001: Codebase review of the canon module](../archived/reviews/R001-canon-module.md), F19).
