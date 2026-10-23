# Architecture angle

Find structure that makes the code harder to change, test or run, and the refactors that would fix it. Describe structure with the `canon-codebase-design` vocabulary (module, interface, implementation, depth, seam, adapter, leverage, locality) and name domain things with the project's own terms.

## Where to look

Structural fixes pay off by making future changes easier, so weight the hot spots in the scope first. Explore organically and note where you feel friction:

- **Depth**: understanding one concept requires bouncing between many small modules; a module is **shallow** (its interface nearly as complex as its implementation); pure functions were extracted for testability but the real bugs hide in how they are called (no **locality**); code is untested, or hard to test through its current interface.
- **Coupling**: modules leak across their seams, or depend on each other in a cycle.
- **Data ownership**: several modules write the same data, or one reads another's storage instead of going through its interface.
- **State and concurrency**: shared mutable state with no clear owner; ordering or locking assumptions the interface does not state.
- **Evolution**: interfaces and schemas (APIs, events, file formats, tables) that change without versioning or a migration path.
- **Failure handling and observability**: errors swallowed, retried without bound or translated inconsistently across seams; failures that leave no log, metric or trace to diagnose them.

Apply the **deletion test** to anything suspected shallow: would deleting it concentrate complexity, or just move it? "Concentrates" is the signal.

## Hard checks

- **Dependency directions**: imports that cross the allowed directions in D000's Dependencies, and cycles between modules. Each one is at least `major`.
- **Design coverage**: the source areas no design covers that the scope lists from `audit`, and designs over 500 lines that should split.

## Each candidate

- **Files** involved.
- **Problem**: why the current structure causes friction.
- **Solution**: what would change, in plain words. Interfaces are designed later, with the user.
- **Benefits**: in locality and leverage for a deepening, otherwise what becomes safer or easier; and how tests would improve.
- **Dependency category** of what sits behind the seam, for a deepening: in-process, local-substitutable, ports and adapters, or mock.
- **Strength**: `Strong`, `Worth exploring` or `Speculative`.
