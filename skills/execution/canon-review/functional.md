# Functional angle

Check the code against the active designs that govern the scope. The design's Spec is the definition of correct.

## Spec conformance

For each specified interface:

- It exists with the specified signature, schema or CLI usage.
- Its behavior matches, including error modes and the edge cases the Spec lists.
- A test exercises it at its seam.

## Gaps

- Behavior the code has but no design specifies: a spec gap, or code to remove.
- Spec statements the code no longer honors: a defect or a stale spec; say which the evidence suggests.
- Swallowed errors, unreachable branches, `TODO` and `FIXME` markers on specified behavior.

Cite the design section for every finding, e.g. `D003§token-refresh`.
