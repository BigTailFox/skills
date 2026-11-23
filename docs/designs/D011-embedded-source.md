---
status: draft
created: 2026-11-23
updated: 2026-11-23
revision: 1
modules: [canon]
summary: Embed a repository source file or a named region in Markdown, regenerate its fenced code block and check it against the same Git tree as the document.
refs: [C001, D006, D010, D005]
owns: [source-embeds]
paths: [skills/governance/canon/scripts/canon.py, skills/governance/canon/SKILL.md, tests/test_canon.py]
reviewed: 1
reviewers: [gpt-6.2-astra, gemini-4-neon-xhigh]
---

# D011: Source code embedded in docs

## Goals

1. Authors edit a source file once. A reader of the rendered document sees the selected code inline.
2. A check of the work tree, staged files or a commit detects a stale block using that tree's sources. Running the generator twice on the same inputs produces no second change.

## Spec

The Tool table and marker instructions in the `canon` skill document generating a fenced copy from a local source. [D006§check: document checks](D006-doc-model.md#check) defines the trees, diagnostic scope and line limits. The docs indexes belong to [D005: Docs index](D005-docs-index.md).

### Markers and sources

Consumers are the bodies of valid numbered documents after frontmatter, and Markdown guides, assets and numbered-doc attachments in live docs roots. The two index READMEs are reserved for the index writer. Markdown outside those locations and examples in code fences remain literal. Discover each eligible document by its resolved path in its own docs root, using that path's parent for every source. A symlink alias to that document selects the same consumer once. Skip aliases leaving the eligible locations during discovery and reject an explicit selection of one. Both checks and writes use this identity.

At column one outside a fenced block, write the following comments with the literal spaces shown. A line beginning with `<!-- embed:` or `<!-- /embed` there must fit the syntax. Pairs are disjoint and closed. An empty pair is ready to generate.

```markdown
<!-- embed: D002/queue.py#enqueue -->
<!-- /embed -->
```

Split the operand at the first literal `#` before URL-decoding the path once. A fragment, when present, must be a nonempty region name. Encode whitespace, literal `%` and `#` in a filename as percent escapes. Use a relative repository path from the consumer. Walk its components and any relative symlink targets in order in the selected tree: `..` pops the last resolved directory. Reject a step above the repository root, an absolute path or symlink target, a symlink loop or more than 40 hops. The final source must be a regular file in that tree's inventory, including a nonignored new work-tree file. The consumer and source must resolve to different files. Read UTF-8, rejecting invalid encoding or a NUL byte. Another eligible Markdown consumer with an active pair cannot be a source. Marker-looking text in ordinary source code stays literal.

A region delimiter occupies a whole source line, with optional indentation and trailing whitespace. Its comment prefix is `#` or `//`, followed by optional horizontal space and `region NAME` or `endregion` with an optional name. Separate the keyword and name by horizontal whitespace. A name is one or more ASCII letters, digits, underscores or hyphens. Either prefix may close a region; a supplied closing name must match. Validate the whole source for duplicate names, nesting and unpaired delimiters for every selection. Select the named body, or the whole file with delimiters omitted. Remove common indentation, then trim leading and trailing whitespace-only lines.

The generated lines are the opening fence and language, the selected lines, and the closing fence, directly between the comments. An empty selection has just the two fences. Use at least three backticks and one more than the longest backtick run in the selected text. Use `python` for `.py`, `cpp` for `.h`, `.hpp` and `.cpp`, `capnp` for `.capnp` and an empty language for other suffixes. Canon’s Markdown readers match the full opening run of backticks or tildes. A closing run uses the same character, is at least as long, and has only whitespace after it. Shorter fences, headings, links and marker examples inside generated code stay literal.

### Generating and checking

```text
canon.py embed [ID|PATH ...] [--check]
```

Both forms use the work tree. With no selectors, visit all live consumers. An ID selects the numbered doc and its Markdown attachments. A path selects one eligible Markdown file relative to the working directory. Resolve duplicate selections once. Validate every selected document and source before writing. Any invalid selector or block exits 1 and leaves the documents as found. Print a block diagnostic as `ERROR <document>:<line>: <reason>` with a repository-relative path and one-based marker line. A valid write prints `updated <document>` once per changed file, exits 0 and is quiet on a no-op. Preserve bytes outside replaced blocks, including existing line endings and the last newline. `check --fix` handles the doc's `updated` date. Staging remains a separate operation.

`embed --check` checks without writing and reports every stale or invalid block in scope. It exits 1 on a problem and otherwise exits 0 quietly. The regular document check reports the same block errors in the selected tree. A stale work-tree block names the scoped `embed` command; a staged error directs the author to generate against the source intended for the commit and stage the matching block. A revision check identifies that commit's stale block. `check --fix` leaves generation to `embed`. Discount the interior lines of a syntactically paired, non-nested embed from a numbered document's line count, even when its source is stale or invalid. Count the two marker lines.

### Moves and archived copies

Use the shared [D006§statuses-and-archiving: move rules](D006-doc-model.md#statuses-and-archiving). A marker in a document that will be an eligible live consumer after the move, including a file being adopted, names its source relative to the document's original directory. If either moves, write the relative path from the new directory to the moved or stationary source, escaping reserved filename characters and retaining the region. Only the path field participates in move rewriting. Preserve both the literal source between markers and any ID in a region name. This covers `init`'s move to D000 and [D010§renumber: renumbering](D010-doc-queries-and-renames.md#renumber).

Before archiving a numbered doc and its attachments, check their live embeds. An invalid or stale block stops the archive before any mutation. Once archived, their present code and paired comments are a frozen copy. Generation and checks skip historical embeds, including existing archived files, and renumbering leaves their marked code literal. A live document pointing to a moved source still follows it.

## Decisions

- [C001: Canon backlog](../concepts/C001-canon-backlog.md) records a downstream project where a generated code block was edited by hand. Keeping the source authoritative makes that discrepancy detectable before commit.
