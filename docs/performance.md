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

## Effective worker count

\[
W_{effective}=\min(W_{configured},W_{license},W_{memory},W_{stable}).
\]

A higher process count is not automatically faster. Models with recycles, difficult phase behavior or expensive columns may compete for memory and license services. Benchmark on the target host.

## Dynamic scheduling and recycling

Workers draw tasks from a shared queue rather than fixed equal chunks. This reduces idle time when solve durations are heterogeneous.

Long-lived COM servers are recycled when either threshold is reached:

```text
ASPENOPS_WORKER_MAX_POINTS
ASPENOPS_WORKER_MAX_AGE_S
```

Recycling opens a fresh private model copy and records a new worker generation.

## Cache rules

By default, a result is cached only when reset mode is `reinitialize`, every validity gate passes, and runtime/backend/model/registry/request identity matches exactly. Failure caching remains disabled by default because transient license or solver failures should normally be retried.

## Authoritative performance-evidence workflow

The manual `generate-performance-evidence.yml` workflow is an evidence producer, not a general arbitrary-ref executor. It enforces the following sequence before any dependency synchronization or Python execution:

```text
checkout candidate ref
→ fetch trusted main history
→ resolve immutable candidate and baseline SHAs
→ require candidate SHA to belong to main
→ require baseline SHA to belong to main
→ require baseline SHA to be an ancestor of candidate SHA
→ create detached baseline worktree
→ install frozen candidate dependencies
→ run repeated baseline/candidate matrices
→ enforce stable-regression policy
→ upload run-ID-scoped evidence
```

This prevents unmerged or unrelated commits from producing evidence that looks authoritative. Exact candidate and baseline SHAs are recorded in the artifact.

The baseline source is executed through the same candidate benchmark harness and frozen candidate environment so dependency and harness drift do not masquerade as runtime performance changes. A baseline that is not compatible with that environment must fail rather than silently change the comparison method.

## Real benchmark protocol

For each worker count, record startup time, model-open time, mean/P50/P95 solve time, throughput, peak memory, failure rate and license wait. Repeat the full benchmark from a clean process.

Portable Mock measurements are orchestration evidence only. They must not be described as licensed Aspen solve speed or engineering-model performance.
