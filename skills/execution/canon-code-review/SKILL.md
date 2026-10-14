---
name: canon-code-review
description: Reviews a code change (uncommitted work, or the diff since a commit, branch or merge base) on two separate axes run as parallel subagents. Spec checks the change against its governing designs and plan; Standards checks it against the standards the project's designs and AGENTS.md state plus a code-smell baseline. Use after implementing a change or plan slice and before the docs step, or when the user asks to review a branch, PR, diff or work in progress.
---

# Code review

Two-axis review of one change:

- **Spec**: does the code implement what its governing designs and plan specify, and nothing else?
- **Standards**: does the code follow the standards the project states?

Each axis runs in its own subagent so neither pollutes the other's context; this skill then reports them side by side.

## 1. Pin the fixed point

Use the user's fixed point (a commit, branch, tag or `HEAD~5`). Otherwise use the start commit a plan's Log records, otherwise the default branch (`origin/HEAD`, else `main`); on the default branch itself, review only the uncommitted work.

Diff the working tree against the merge base so uncommitted work is included: `git diff $(git merge-base <fixed-point> HEAD)`. Note the commits with `git log --oneline <fixed-point>..HEAD`. Confirm the ref resolves and the diff is non-empty before spawning anything.

## 2. Collect the spec

- `canon.py affected --base <fixed-point>`: the designs governing the changed files and the plans built on them.
- Ids in the commits' `Refs:` trailers, and any plan or design the user named.
- For each design, the sections that govern the change (`show D00X#<section>`); for a plan, the slices it touched with their test criteria.

When no design governs the change, the Spec axis still runs: it checks that the diff changes no behavior a design should specify (user-visible CLI, API, UI, config or data formats).

## 3. Collect the standards

- Every `AGENTS.md` from the repo root down to the changed files.
- The architecture design: allowed dependency directions and the glossary of cross-module terms.
- Standards stated in the designs that own the touched topics.
- Linter, formatter and type-checker config: skip whatever it enforces.
- The smell baseline in [smells.md](smells.md), pasted in full into the Standards prompt.

## 4. Spawn both subagents in parallel

Issue both calls together, in the foreground. Each prompt carries the diff command, the commit list, and its sources (paths to read, plus the pasted baseline for Standards). Both report findings with severity `blocker`, `major` or `minor`, under 400 words.

**Spec brief**: "Report: (a) requirements the spec or plan asks for that are missing or partial; (b) behavior in the diff that nothing asked for; (c) requirements that look implemented but wrong; (d) behavior the diff changes that its governing design does not specify or contradicts, meaning the change needed a design revision first; (e) slice test criteria with no test at the named seam. Cite the section for each finding, e.g. D003§token-refresh."

**Standards brief**: "Report, per file or hunk, (a) every violation of a stated standard, citing the doc and rule; (b) baseline smells, named and quoted. Stated-standard breaches can be hard violations; baseline smells are always judgement calls, and a stated standard overrides the baseline. Skip anything tooling enforces."

## 5. Report

Present the reports under `## Spec` and `## Standards`, verbatim or lightly cleaned. Do not merge or rerank across axes: a change can pass one and fail the other, and separate reports stop one from masking the other. End with one line per axis: finding count and the worst finding.

## 6. Dispose

- Fix findings in the change, then re-run the checks the fix touched. Review once; do not re-review the fixes.
- A finding the user defers to later work goes into an R doc: `canon.py new R <slug>`, Scope naming the fixed point, `HEAD` and the axes, one row per deferred finding with disposition `open`.
- A finding that shows the design itself is wrong goes to the user; never change a design's intent yourself.
