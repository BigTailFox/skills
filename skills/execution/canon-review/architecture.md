# Architecture angle

Find **deepening opportunities**: refactors that turn shallow modules into deep ones, for testability and navigability. Use the `canon-codebase-design` vocabulary exactly: module, interface, implementation, depth, seam, adapter, leverage, locality. Never substitute component, service, API or boundary.

## Where to look

Deepening pays off by making future changes easier, so weight the hot spots in the scope first. Explore organically and note where you feel friction:

- Understanding one concept requires bouncing between many small modules.
- A module is **shallow**: its interface is nearly as complex as its implementation.
- Pure functions were extracted for testability, but the real bugs hide in how they are called (no **locality**).
- Tightly coupled modules leak across their seams.
- Code is untested, or hard to test through its current interface.

Apply the **deletion test** to anything suspected shallow: would deleting it concentrate complexity, or just move it? "Concentrates" is the signal.

## Hard checks

- **Dependency directions**: imports that cross the module map's allowed directions in the architecture design. Each one is at least `major`.
- **Design coverage**: source directories no design's `paths` covers, and designs over 500 lines that should split.

## Each candidate

- **Files** involved.
- **Problem**: why the current structure causes friction.
- **Solution**: what would change, in plain words. Do not propose interfaces yet.
- **Benefits** in locality and leverage, and how tests would improve.
- **Dependency category** of what sits behind the seam: in-process, local-substitutable, ports and adapters, or mock.
- **Strength**: `Strong`, `Worth exploring` or `Speculative`.
