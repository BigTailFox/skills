---
name: canon-investigate
description: Diagnoses hard bugs and performance regressions. Use when a quick fix has failed or the cause is unclear, for intermittent failures and slowdowns, or when the user asks to diagnose or debug. Not for bugs whose cause is plain; fix those as L0 with a regression test. Builds a red-capable feedback loop, ranks falsifiable hypotheses from the evidence, instruments, then fixes with a regression test, recording it all in a canon investigation doc that survives across sessions.
---

# Investigate

A discipline for hard bugs. A bug whose cause the error already shows needs none of it: fix it as an L0 change with a regression test (`canon-tdd`). Skip a phase only with a stated reason.

## Record

Open the investigation when you start: `canon.py new I <slug>`. Then run `canon.py trace start investigate <I id> --skill <skill> --model <model>`. Write the user's exact symptom into Symptom. Keep the doc current as each phase ends, so another session can resume from it:

- **Reproduction**: the Phase 1 loop as `Commit:`, `Environment:` and `Command:`. Repro scripts, fixtures and captured artifacts go in `investigations/I00X/`.
- **Analysis**: the ranked hypotheses, then each probe and its result, in order.
- **Resolution**: `Root cause:`, `Fix:` and `Verification:` once Phase 6 is done.

Before diagnosing, read the governing design sections for the code involved (`canon.py which <file>`, `show D00X#<section>`). The design's Spec says what correct behavior is.

## Redact

Replace every secret with `<REDACTED>` in anything you show or commit: commands, outputs, captured artifacts. Build loops against environment variables so credentials stay in the environment. From captured artifacts, quote only the lines that carry the signal. If the redacted output is not enough to diagnose the bug, say so and ask the user.

## Phase 1: Build a feedback loop

**This is the skill.** With a **tight** pass/fail signal that goes **red** on this bug, you will find the cause: bisection, hypothesis-testing and instrumentation all just consume it. Spend disproportionate effort here.

Ways to construct one, roughly in this order:

1. **Failing test** at whatever seam reaches the bug: unit, integration, e2e.
2. **Curl or HTTP script** against a running dev server.
3. **CLI invocation** with a fixture input, diffing stdout against a known-good snapshot.
4. **Headless browser script** (Playwright, Puppeteer) asserting on DOM, console or network.
5. **Replay a captured trace**: save a real request, payload or event log to disk and replay it through the code path in isolation.
6. **Throwaway harness**: a minimal subset of the system (one service, mocked dependencies) that exercises the bug path with one call.
7. **Property or fuzz loop**: for "sometimes wrong output", run 1000 random inputs and look for the failure mode.
8. **Bisection harness**: when the bug appeared between two known states, automate "boot at state X, check" so `git bisect run` can drive it.
9. **Differential loop**: run the same input through the old and new version (or two configs) and diff the outputs.
10. **Human in the loop**, last resort: when a person must click, copy [scripts/hitl-loop.template.sh](scripts/hitl-loop.template.sh) into `investigations/I00X/`, edit its steps, and run it; the user follows the prompts and the captured values come back to you.

**Tighten the loop.** Make it faster (cache setup, narrow scope), sharper (assert the specific symptom, not "didn't crash"), and more deterministic (pin time, seed randomness, isolate the filesystem, freeze the network). A 30-second flaky loop is barely better than none.

**Non-deterministic bugs**: raise the reproduction rate instead of chasing a clean repro. Loop the trigger 100×, parallelise, add stress, narrow timing windows. A 50% flake is debuggable; 1% is not.

**When you cannot build a loop yet**, say so: list what you tried and ask for access to an environment that reproduces it, a redacted captured artifact (HAR, log dump, core dump, recording with timestamps), or permission to add temporary production instrumentation. Meanwhile work from the evidence you have, with hypotheses (Phase 3) and probes (Phase 4) that may produce a loop. What waits for the loop is the fix: a fix made without one is unverified, and Resolution's `Verification:` says so.

**Done when** you can name one command you have already run (show it and its redacted output) that is:

- [ ] **Red-capable**: drives the real bug path and asserts the user's exact symptom.
- [ ] **Deterministic**: same verdict every run, or a pinned high reproduction rate.
- [ ] **Fast**: seconds, not minutes.
- [ ] **Agent-runnable**: runs unattended, or through the human-in-the-loop script.

## Phase 2: Reproduce and minimise

Run the loop and watch it go red. Confirm it shows the failure the **user** described, not a nearby one, reproducibly, and capture the exact symptom for later verification.

Then shrink the repro: cut inputs, callers, config, data and steps one at a time, re-running after each cut. Done when every remaining element is load-bearing: removing any one turns the loop green.

## Phase 3: Hypothesise

Write ranked hypotheses before testing any, as many as the evidence supports; one is enough when the evidence points straight at it. Each must be falsifiable: "If X is the cause, then changing Y makes the bug disappear and changing Z makes it worse." A hypothesis without a prediction is a vibe: sharpen or drop it.

Show the ranked list to the user and start on the top one; they often re-rank instantly or have ruled some out, so fold in their answer when it comes.

## Phase 4: Instrument

Each probe tests one prediction from Phase 3; change one variable at a time. Prefer a debugger or REPL, then targeted logs at the boundaries that separate hypotheses; blanket logging buries the signal.

Tag every debug log with a unique prefix such as `[DEBUG-a4f2]` so cleanup is one grep.

**Performance**: measure first. Establish a baseline (timing harness, profiler, query plan), compare it with the design's Budgets, then bisect. Keep raw measurements in `investigations/I00X/`.

## Phase 5: Fix and regression test

Write the regression test before the fix with the `canon-tdd` skill, but only at a **correct seam**: one where the test exercises the real bug pattern as it occurs at the call site. A seam too shallow to replicate the triggering chain gives false confidence.

**If no correct seam exists, that is a finding.** The architecture prevents locking the bug down: record it in Resolution and report it to the user.

With a correct seam:

1. Turn the minimised repro into a failing test there and watch it fail. If you forced the red by mutating code or a fixture, diff against a pristine copy to prove the mutation landed.
2. Apply the fix and watch the test pass.
3. Re-run the Phase 1 loop on the original, un-minimised scenario.

A fix that restores specified behavior is L0. When the root cause shows the design's spec is wrong or silent, tell the user; the design changes only through the tier flow in the `canon` skill.

## Phase 6: Clean up

Before declaring done:

- [ ] The original repro no longer reproduces (Phase 1 loop re-run).
- [ ] The regression test passes, or the missing seam is recorded.
- [ ] Every `[DEBUG-...]` line is removed (grep the prefix).
- [ ] Throwaway harnesses are deleted or kept in `investigations/I00X/`.
- [ ] Resolution is filled. The commit message states the root cause and carries `Refs: I00X`. The docs step archives the investigation as `resolved`.
- [ ] The `canon-retro` skill's end check has run if this work hit concrete friction in the development infrastructure or the agent workflow that could recur, such as a correction to how you worked, a defect class the project's checks let through, a command that would not run, a check that failed after you thought you were done, a search that took far too long, or a canon step that got in the way. Use only evidence already in context; do not search for reasons to run it.

Then run `canon.py trace end <id> <outcome>`.
