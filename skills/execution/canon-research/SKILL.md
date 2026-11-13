---
name: canon-research
description: Researches questions against primary sources. Use when a design or decision depends on facts about an external library, service, protocol or standard, when the user wants a topic researched or API facts gathered, or when grill triage routes a question here. Quick facts get a direct answer with source links; findings that back a decision are researched in a background subagent from official docs, specs and source code, and recorded with citations as a canon experiment.
---

# Research

A fact one or two primary sources settle (a signature, a default, a limit, a supported version) gets a direct answer: look it up and reply with the source links, no doc. Use the flow below when the answer will back a design decision, needs several sources weighed, or is worth running in the background.

## 1. Frame

Write the question, the answer that would settle it, and the doc that will absorb the answer (usually the design being written or revised).

## 2. Reserve the doc

In the main session, look for experiments on the same question with `canon.py find --archived`. Extend one that is `planned` or `running`, or `answered` and cited by no live doc (the `canon` skill's doc types), setting a `planned` or `answered` one `running` with `canon.py status`. Otherwise run `canon.py new E <slug>`, fill Question, link each earlier experiment you found on the question, and set it `running` with `canon.py status`. One already `running` from another session is still handled as [Recover](#4-recover) says. Reserving the id before the subagent starts keeps ids unique while both sessions write docs.

## 3. Launch

Start a background subagent where the host supports one, and keep the brief you pass it and the subagent's id in `.canon/canon-research/<E00X>/` as `brief.md` and `id.txt`. Otherwise do the research inline under the brief's rules, keeping neither file. The brief, with the placeholders filled:

```text
Research this question and record the findings in {path to E00X}.

Question: {question}
Settles it: {what answer would settle it}

Rules:
- Use primary sources only: official documentation, specifications, source code, first-party APIs. Trace every claim back to the source that owns it; a secondary write-up is a lead, never evidence. Your own memory is never evidence.
- Note the version or date each source describes.
- Setup: replace empty Commit, Environment and Command lines with `- Sources:` followed by one indented line per source, as a markdown link. Keep filled ones, from an earlier run of the same question, and put `- Sources:` after them.
- Write each finding into the doc as soon as you have its source, so a run that stops loses nothing. Keep the findings the doc already holds and research only what they leave open.
- Results: one finding per bullet, each linked to its source. Mark inferences as inferences. Report conflicts between sources.
- Conclusion: the answer, your confidence, and what remains open.
- `summary`: one line that leads with the question's subject and states the answer.
- Put long excerpts worth keeping in {E00X attachment dir}/ and link them. Copy each verbatim except its link and image targets: resolve each relative or `/`-rooted one against the source's URL, since `check` checks the links there.
- Replace every `<!-- canon: ... -->` comment. Write in {documentation language}.
- Modify nothing except that doc and its attachment directory; keep scratch files in .canon/canon-research/{E00X}/scratch/, never in the OS temp directory. Search tools that honor .gitignore skip .canon/: read its paths directly.
```

Keep working on what does not depend on the answer.

## 4. Recover

When the subagent stops before finishing, resume it once by the id in `id.txt` where the host allows; otherwise rerun `brief.md` once in a new subagent. After a second stop, take it to the user. An experiment you find still `running` from another session gets its `brief.md` rerun only once the user confirms that no other session is running it.

## 5. Absorb

When the subagent finishes:

1. Open the sources behind the findings your decision depends on and confirm they say what the doc claims, then set the experiment `answered` with `canon.py status`.
2. Absorb the conclusion into the target doc with a link to the experiment: in a design, a Spec constraint, a Budget, or a Decision; in a plan, its Notes. An accepted or active design changes only through the tier flow in the `canon` skill.
3. Once you have written the link, set the experiment `concluded` with `canon.py status` and archive the earlier experiments on its question; the `canon` skill's doc types say how, which other steps set `concluded` and when the experiment is archived.
