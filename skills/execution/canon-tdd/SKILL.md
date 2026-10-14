---
name: canon-tdd
description: Test-driven development in red-green cycles at agreed seams, producing tests that verify behavior through public interfaces and survive refactors. Use when writing or changing code that should be tested, implementing a plan slice, fixing a bug test-first, writing a regression or integration test, or when the user mentions TDD or red-green-refactor.
---

# TDD

TDD is the red → green loop. This skill makes that loop produce tests worth keeping: what a good test is, where tests go, the anti-patterns, and the rules of the loop. Apply every section on every cycle.

## What a good test is

Tests verify behavior through public interfaces, not implementation details. Code can change entirely; tests shouldn't. A good test reads like a specification: "user can checkout with valid cart" tells you exactly what capability exists, and it survives refactors because it doesn't care about internal structure. Name tests with the terms of the governing design and the architecture design's glossary.

Examples: [tests.md](tests.md). Mocking only at system boundaries: [mocking.md](mocking.md).

## Seams: where tests go

A **seam** is the public boundary you test at: the interface where you observe behavior without reaching inside. Tests live at agreed seams, never against internals. Find the seams in this order:

1. **Plan slice**: the seams its test criteria name. They were agreed when the plan was accepted; use them without asking.
2. **No plan**: the interface the governing design's Spec defines (`canon.py which <file>`, then `show D00X#<section>`). State the seam in one line before the first test.
3. **No specified interface fits**, or where the seam belongs is itself in question: settle it with the `canon-grill` skill before writing the test, using the `canon-codebase-design` vocabulary. Give each proposed seam a one-line note on what it catches and what it misses.

You can't test everything; agreed seams put the effort on the critical paths and complex logic instead of every edge case.

## Anti-patterns

- **Implementation-coupled**: mocks internal collaborators, tests private methods, or verifies through a side channel (querying the database instead of using the interface). The tell: the test breaks when you refactor but behavior hasn't changed.
- **Tautological**: the assertion recomputes the expected value the way the code does (`expect(add(a, b)).toBe(a + b)`), so it passes by construction. Expected values come from an independent source of truth: a known-good literal, a worked example, the design's Spec.
- **Horizontal slicing**: writing all tests first, then all implementation. Bulk tests verify _imagined_ behavior and commit to test structure before you understand the implementation. Work in **vertical slices**: one test → one implementation → repeat, each test a **tracer bullet** that responds to what the last cycle taught you.

## Rules of the loop

- **Red before green.** Write the failing test first and watch it fail on the asserted behavior, not on a compile or import error. Then write only enough code to pass it. No speculative features.
- **One cycle at a time.** One seam, one test, one minimal implementation per cycle.
- **Tight feedback.** Run the touched test file and the type checker every cycle; run the full suite when a plan slice's criteria all pass.
- **Refactoring is not part of the loop.** It belongs to code review, after the behavior is green.
