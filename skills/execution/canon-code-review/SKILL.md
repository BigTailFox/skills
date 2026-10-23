---
name: canon-code-review
description: Reviews one complete code change. Use when a change is finished and before the docs step, or when the user asks to review a branch, PR, diff or work in progress. Not for single plan slices or whole-codebase reviews. Checks the diff and untracked files against the governing designs and plan (Spec) and the project's stated standards plus a smell baseline (Standards), with one fresh reviewer per axis plus a cross-family reviewer for L2.
---

# Code review

Review of one complete change on two axes:

- **Spec**: does the code implement what its governing designs and plan specify, and nothing else?
- **Standards**: does the code follow the standards the project states?

Every change, whatever its tier, gets both axes, each from a fresh subagent: the session that wrote the change never reviews it, and neither axis colors the other. An L2 change adds the cross-family reviewer.

## 1. Pin the fixed point

Use the user's fixed point (a commit, branch, tag or `HEAD~5`). Otherwise use the start commit a plan's Log records, otherwise the default branch (`origin/HEAD`, else `main`); on the default branch itself, review only the uncommitted work.

Diff the working tree against the merge base so uncommitted work is included: `git diff $(git merge-base <fixed-point> HEAD)`. Untracked new files are missing from that diff; list them with `git ls-files --others --exclude-standard` and pass them as files to read in full. Note the commits with `git log --oneline <fixed-point>..HEAD`. Confirm the ref resolves and the change is non-empty before spawning anything.

Run `canon.py trace start code-review [<P id>] --base <fixed-point> --tier <tier> --skill <skill> --model <model> [--parent <parent>]`.

## 2. Collect the spec

- `canon.py affected --base <fixed-point>`: the designs governing the changed files and the plans built on them.
- Ids in the commits' `Refs:` trailers, and any plan or design the user named.
- For each design, the sections that govern the change (`show D00X#<section>`); for a plan, the slices it touched with their test criteria.

When no design governs the change, the Spec axis still runs: it reports behavior callers rely on that the diff alters and no design states.

## 3. Collect the standards

- Every `AGENTS.md` from the repo root down to the changed files.
- D000: allowed dependency directions and the glossary of cross-module terms.
- Standards stated in the designs that own the touched topics.
- Linter, formatter and type-checker config: skip whatever it enforces.
- The smell baseline in [smells.md](smells.md), pasted in full into the Standards prompt.

## 4. Spawn the reviewers

Issue the calls together, in the foreground: a Spec reviewer and a Standards reviewer, each launched like the same-model reviewer in the `canon-blind-review` skill, plus, for an L2 change, the cross-family reviewer through that skill with a prompt carrying both briefs and both sets of sources. Keep each reviewer's files in `.canon/canon-blind-review/<topic>/` (topic: `<P id>-code-review`, else a slug of the change) as that skill names them, by role: `spec`, `standards` or `cross-family`, e.g. `spec-prompt.md`, `spec.md` and `spec-id.txt`. Each prompt carries the diff command, the untracked files, the commit list, and its sources (paths to read, plus the pasted baseline for Standards). Reviewers report findings with severity `blocker`, `major` or `minor`.

**Spec brief**: "Report: (a) requirements the spec or plan asks for that are missing or partial; (b) behavior in the diff that nothing asked for; (c) requirements that look implemented but wrong; (d) behavior the diff changes that its governing design contradicts, meaning the change needed a design revision first; (e) behavior callers rely on (results, errors, side effects, config keys, data formats) that the diff alters or extends and no design states, whether or not a design governs the changed files, meaning the change needed an as-built revision first; (f) slice test criteria with no test at the named seam. Cite the section for each finding, e.g. D003§token-refresh."

**Standards brief**: "Report, per file or hunk, (a) every violation of a stated standard, citing the doc and rule; (b) baseline smells, named and quoted. Stated-standard breaches can be hard violations; baseline smells are always judgement calls, and a stated standard overrides the baseline. Skip anything tooling enforces."

Both briefs end with: "Report a problem a design lists as a known issue only when it is worse than the entry says, naming the entry."

## 5. Report

Present the findings under `## Spec` and `## Standards`, verbatim or lightly cleaned, and an L2 cross-family report after them under `## Cross-family (<model>)`. Keep the axes apart instead of merging or reranking across them: a change can pass one and fail the other, and separate reports stop one from masking the other. End with one line per axis: finding count and the worst finding. A design problem goes in the same report, with the fix you propose and its tier, so the user decides on everything at once.

## 6. Dispose

- Fix findings in the change, then re-run the checks the fix touched. When blocker or major fixes changed the code, the reviewers that raised them confirm the fixes once, as the `canon-blind-review` skill's confirmation describes.
- A finding the user defers becomes a known issue of the design governing its code (`canon.py which`), with source `code review <HEAD commit>`, as the `canon` skill's doc types define; when no design governs it, an Idea in the module's backlog concept (`canon.py find backlog`, else `canon.py new C <module>-backlog`).
- A finding that shows the design itself is wrong is a design problem: follow the `canon` skill's workflow (Design problems). The review ends once any revision the user chose has passed its gate.
- A finding of altered behavior no design states is fixed by an as-built revision from the merge base the review diffs against, written as the `canon` skill's `as-built.md` says, which passes its L1 gate and is committed on its own. The change then alters what that design states, which needs a revision of it: a design problem, as above.
- Unless another workflow invoked this review, run the `canon-retro` skill's end check only if this work hit concrete friction in the development infrastructure or the agent workflow that could recur, such as a correction to how you worked, a finding a check could have caught, a command that would not run, a check that failed after you thought you were done, a search that took far too long, or a canon step that got in the way. Use only evidence already in context; do not search for reasons to run it.

Then run `canon.py trace end <id> <outcome> --dir .canon/canon-blind-review/<topic> --input -`, with the dispositions on stdin.
