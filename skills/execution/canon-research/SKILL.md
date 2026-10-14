---
name: canon-research
description: Researches questions against primary sources. Use when a design or decision depends on facts about an external library, service, protocol or standard, when the user wants a topic researched or API facts gathered, or when grill triage routes a question here. Quick facts get a direct answer with source links; findings that back a decision are researched in a background subagent from official docs, specs and source code, and recorded with citations as a canon experiment.
---

# Research

A fact one or two primary sources settle (a signature, a default, a limit, a supported version) gets a direct answer: look it up and reply with the source links, no doc. Use the flow below when the answer will back a design decision, needs several sources weighed, or is worth running in the background.

## 1. Frame

Write the question, the answer that would settle it, and the doc that will absorb the answer (usually the design being written or revised).

## 2. Reserve the doc

In the main session, run `canon.py new E <slug>`, fill Question, and set `status: running`. Reserving the id before the subagent starts keeps ids unique while both sessions write docs.

## 3. Launch

Start a background subagent where the host supports one; otherwise do the research inline. Pass this brief with the placeholders filled:

```text
Research this question and record the findings in {path to E00X}.

Question: {question}
Settles it: {what answer would settle it}

Rules:
- Use primary sources only: official documentation, specifications, source code, first-party APIs. Trace every claim back to the source that owns it; a secondary write-up is a lead, never evidence. Your own memory is never evidence.
- Note the version or date each source describes.
- Setup: replace the Commit, Environment and Command lines with `- Sources:` followed by one indented line per source, as a markdown link.
- Results: one finding per bullet, each linked to its source. Mark inferences as inferences. Report conflicts between sources.
- Conclusion: the answer, your confidence, and what remains open.
- Put long excerpts worth keeping in {E00X attachment dir}/ and link them.
- Replace every `<!-- canon: ... -->` comment. Write in {documentation language}.
- Modify nothing except that doc and its attachment directory.
```

Keep working on what does not depend on the answer.

## 4. Absorb

When the subagent finishes:

1. Open the sources behind the findings your decision depends on and confirm they say what the doc claims.
2. Absorb the conclusion into the target doc: a Spec constraint, a Budget, or a Decision linking the experiment. An accepted or active design changes only through the tier flow in the `canon` skill.
3. The docs step archives the experiment as `concluded` once a design absorbs it.
