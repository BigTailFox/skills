---
name: canon-codebase-design
description: Vocabulary and principles for deep modules. Use when designing or changing a module's interface, writing the interfaces of a design's Spec, deciding where a seam or test belongs, judging whether code is too shallow or tangled, or when another canon skill needs the vocabulary. Covers module, interface, depth, seam, adapter, leverage, locality and the deletion test, deepening by dependency category, and designing an interface twice with parallel subagents.
---

# Codebase design

Design **deep modules**: a lot of behaviour behind a small interface, placed at a clean seam, testable through that interface. Use this language and these principles wherever code is being designed or restructured. The aim is leverage for callers, locality for maintainers, and testability for everyone.

## Glossary

Use these terms for design analysis, so skills, reviewers and docs mean the same thing by them. Where the project already gives a word its own meaning (a "service" as a deployable unit, a "component" of its UI framework), keep the project's meaning and use the glossary term for the analysis concept.

**Module**: anything with an interface and an implementation. Deliberately scale-agnostic: a function, class, package, or tier-spanning slice. _Avoid_: unit, component, service.

**Interface**: everything a caller must know to use the module correctly: the type signature, but also invariants, ordering constraints, error modes, required configuration, and performance characteristics. _Avoid_: API, signature (too narrow, they refer only to the type-level surface).

**Implementation**: what's inside a module, its body of code. Distinct from **Adapter**: a thing can be a small adapter with a large implementation (a Postgres repo) or a large adapter with a small implementation (an in-memory fake). Reach for "adapter" when the seam is the topic; "implementation" otherwise.

**Depth**: leverage at the interface. The amount of behaviour a caller (or test) can exercise per unit of interface they have to learn. A module is **deep** when a large amount of behaviour sits behind a small interface, **shallow** when the interface is nearly as complex as the implementation. The ratio of implementation lines to interface lines does not measure it: padding the implementation would raise that ratio.

**Seam** _(Michael Feathers)_: a place where you can alter behaviour without editing in that place; the *location* at which a module's interface lives. Where to put the seam is its own design decision, distinct from what goes behind it. _Avoid_: boundary (overloaded with DDD's bounded context).

**Adapter**: a concrete thing that satisfies an interface at a seam. Describes *role* (what slot it fills), not substance (what's inside).

**Leverage**: what callers get from depth. More capability per unit of interface they learn. One implementation pays back across N call sites and M tests.

**Locality**: what maintainers get from depth. Change, bugs, knowledge, and verification concentrate in one place rather than spreading across callers. Fix once, fixed everywhere.

## Principles

- **Depth is a property of the interface, not the implementation.** A deep module can be internally composed of small, mockable, swappable parts; they just aren't part of the interface. A module can have **internal seams** (private to its implementation, used by its own tests) as well as the **external seam** at its interface.
- **The deletion test.** Imagine deleting the module. If complexity vanishes, it was a pass-through. If complexity reappears across N callers, it was earning its keep.
- **The interface is the test surface.** Callers and tests cross the same seam. If you want to test *past* the interface, the module is probably the wrong shape.
- **One adapter means a hypothetical seam. Two adapters means a real one.** Don't introduce a seam unless something actually varies across it.

When designing an interface, ask: can I reduce the number of entry points, simplify the parameters, hide more complexity inside?

## Designing for testability

- **Accept dependencies, don't create them.** `processOrder(order, paymentGateway)` is testable; a function that constructs its own `StripeGateway` is not.
- **Return results, don't produce side effects.** `calculateDiscount(cart): Discount` beats `applyDiscount(cart): void` that mutates the cart.
- **Small surface area.** Fewer entry points mean fewer tests; fewer parameters mean simpler setup.

## In a canon project

- A design's Spec gives each module's interface in the full sense above: signatures as code, plus invariants, ordering, error modes, configuration and performance characteristics. Budgets hold the numeric performance targets.
- Seams named in the Spec are the default places for tests, and plan slices name the seam each test criterion exercises.
- Name modules with the project's terms: D000's glossary for cross-module terms, the governing design for module terms.

## Going deeper

- **Deepening a cluster given its dependencies**: [DEEPENING.md](DEEPENING.md), covering dependency categories, seam discipline, and replace-don't-layer testing.
- **Exploring alternative interfaces**: [DESIGN-IT-TWICE.md](DESIGN-IT-TWICE.md), with parallel subagents designing the interface several radically different ways, then comparing on depth, locality, and seam placement.
