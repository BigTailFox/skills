# Writing

Agents and people both read these docs, usually after reaching them through a pointer: an `AGENTS.md` line, a link, a `find` hit on a summary or heading.

- Say each thing once, in the doc that owns it, and link to it everywhere else. A design other than D000 states what it owns, and what it leaves out only where a reader would likely assume otherwise; it never states what other designs own.
- Name a doc that does not exist yet by its topic, never by a guessed id: `new` assigns ids.
- Use the fewest plain words that state the exact meaning. A reader new to the project must understand the doc without the conversation that produced it.
- Record only the final state. Leave out the discussion history and superseded drafts, including "X rather than Y" contrasts with an earlier proposal. Keep a rejected alternative only as a one-line Decision when it is likely to be proposed again.
- State the correct approach. Add a counter-example only for a typical, likely misuse; a prohibition earns its place only as a hard guardrail, paired with the behavior to follow instead.
- Prefer numbers to adjectives, code (signatures, schemas, commands) to prose for interfaces, and lists to tables unless the facts are short and tabular.
- Keep a diagram's source with it: Mermaid in the doc, or the generating script in the attachments beside the image it renders, with how to install its dependencies. Keep its labels as text a reviewer can read, never outlines or a raster image, and change it in the commit that changes what it shows.
- Write `summary` lines, titles and headings as pointers: lead with the words a reader would search for, since they feed `find` and the index.
- Keep a topic's definition, rules and caveats under one heading so reading one brings the rest.
- Order the sections a doc type leaves free, such as a design's Spec subsections, and the content within each from the whole to the parts and the core to the details, so a reader meets the frame before what fills it. Among those sections, define each term or name before the first one that uses it; where that cannot be, or another doc defines it, link the definition at its first use.
- Record what the repository cannot tell: reasons, unwritten conventions, gotchas. Name the command or file for facts the environment already states (scripts, config, `--help`) instead of copying them.
- Cut every sentence that changes nothing a capable reader would do anyway.
- `AGENTS.md` holds only what every session needs: pointers and rules. Move detail into designs.
- Design for the project's real constraints. A feature's input validation, the permissions its spec states and protection of the data it handles are part of the feature. Add security hardening beyond that only when the project or feature is security-related or the user asks, and state that requirement in the design; the environment usually provides network isolation.
- Avoid wording that rots, such as "currently", "new" or "recently"; the frontmatter carries time.
- Write docs in the project's documentation language. Keep the template's section headings (`## Goals`), labels (`Status:`, `Commit:`, `Root cause:`) and table headers in English: `canon.py` parses them.
