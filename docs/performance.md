# Performance Engineering

## Cost model

For `N` points and `W` persistent workers:

\[
T_{naive}\approx N(T_{start}+T_{open}+T_{solve}),
\]

\[
T_{pool}\approx W(T_{start}+T_{open})+\frac{N_{unique}}{W}(T_{solve}+T_{verify})+T_{IPC}.
\]

AspenOps removes repeated startup/open cost, deduplicates identical physical requests, caches reproducible cold-state evaluations and crosses IPC once per point.

## Worker count

Use:

\[
W_{effective}=\min(W_{configured},W_{license},W_{memory},W_{stable}).
\]

A higher process count is not automatically faster. Aspen models with recycles, difficult phase behavior or expensive columns may compete for memory and license services. Benchmark on the target host.

## Dynamic scheduling

Work is not partitioned into fixed equal chunks. Worker threads draw tasks from a shared queue. This reduces idle time when solve durations are heterogeneous.

## Recycling

Long-lived COM servers can accumulate memory or unstable state. Workers are recycled when either threshold is reached:

```text
ASPENOPS_WORKER_MAX_POINTS
ASPENOPS_WORKER_MAX_AGE_S
```

Recycling opens a fresh private model copy and increments the worker generation recorded in diagnostics.

## Cache rules

By default a result is cached only when:

- reset mode is `reinitialize`;
- all validity gates pass;
- runtime, backend, model, registry and physical request identity match exactly.

Failure caching is disabled by default because transient license or solver failures should normally be retried rather than frozen.

## Real benchmark protocol

For each worker count, record startup time, model-open time, mean/P50/P95 solve time, throughput, peak memory, failure rate and license wait. Repeat the full benchmark from a clean process. Do not use Mock throughput as a claim about Aspen performance.
