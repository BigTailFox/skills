# Writing

Agents and people both read these docs, usually after reaching them through a pointer: an `AGENTS.md` line, a link, a `find` hit on a summary or heading.

- Say each thing once, in the doc that owns it, and link to it everywhere else.
- Use the fewest plain words that state the exact meaning. A reader new to the project must understand the doc without the conversation that produced it.
- Record only the final state. Leave out the discussion history and superseded drafts, including "X rather than Y" contrasts with an earlier proposal. Keep a rejected alternative only as a one-line Decision when it is likely to be proposed again.
- State the correct approach. Add a counter-example only for a typical, likely misuse; a prohibition earns its place only as a hard guardrail, paired with the behavior to follow instead.
- Prefer numbers to adjectives, code (signatures, schemas, commands) to prose for interfaces, and lists to tables unless the facts are short and tabular.
- Write `summary` lines, titles and headings as pointers: lead with the words a reader would search for, since they feed `find` and the index.
- Keep a topic's definition, rules and caveats under one heading so reading one brings the rest.
- Record what the repository cannot tell: reasons, unwritten conventions, gotchas. Name the command or file for facts the environment already states (scripts, config, `--help`) instead of copying them.
- Cut every sentence that changes nothing a capable reader would do anyway.
- `AGENTS.md` holds only what every session needs: pointers and rules. Move detail into designs.
- Design for the project's real constraints. A feature's input validation, the permissions its spec states and protection of the data it handles are part of the feature. Add security hardening beyond that only when the project or feature is security-related or the user asks, and state that requirement in the design; the environment usually provides network isolation.
- Avoid wording that rots, such as "currently", "new" or "recently"; the frontmatter carries time.
- Write docs in the project's documentation language. Keep the template's section headings (`## Goals`), labels (`Status:`, `Commit:`, `Root cause:`) and table headers in English: `canon.py` parses them.
