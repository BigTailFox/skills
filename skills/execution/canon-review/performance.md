# Performance angle

Evidence is a measurement or a clear complexity argument. A suspicion without either is at most `minor`.

## Budgets

For each Budget in the governing designs:

- Is its measurement method runnable? Run it when it takes under a few minutes and compare with the target.
- A budget without a runnable measurement is a finding; suggest an experiment to establish it.

## Hot paths

Look in request handlers, loops over growing data, startup, and anything the hot spots touch:

- Work that grows faster than the data: nested scans, repeated sorting, quadratic string building.
- N+1 queries and chatty network calls inside loops.
- Blocking I/O on latency-sensitive paths.
- Unbounded growth: caches, queues, buffers, retained references.
- Missing pagination, streaming or batching on large results.
- Allocation and serialization in tight loops.
- Expensive startup or per-request initialization that could happen once.

For each finding give the path, the expected scale, and the cost at that scale.
