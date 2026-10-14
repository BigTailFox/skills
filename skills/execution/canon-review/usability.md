# Usability angle

Judge every user-visible surface against its design's Spec and the guides, from the point of view of someone using it for the first time.

- **CLI**: help text completeness, consistent flag and command naming, sensible defaults, exit codes, actionable error messages that say what to do next.
- **API**: consistent naming and shapes, one error format, pagination and limits, behavior on invalid input.
- **UI**: the main flows end to end, empty, loading and error states, keyboard access and labels.
- **Config**: defaults, validation messages, what happens when a key is missing or misspelled.
- **Docs**: guides and READMEs match actual behavior; every documented command runs as written.

For each finding give the exact input or step, what the user sees, and what they should see.
