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

The manual `generate-performance-evidence.yml` workflow is an evidence producer, not an arbitrary-ref executor. Its default baseline is the validated main-history runtime:

```text
ebef32ee1f2be74df5d5c5489e7ca86d35ac7bb2
```

Before any dependency synchronization or Python execution, it performs:

```text
checkout the trusted workflow revision from main
→ fetch trusted main history and tags
→ resolve candidate_ref and baseline_ref with --end-of-options
→ require both immutable SHAs to belong to main
→ require baseline to be an ancestor of candidate
→ detached checkout of the validated candidate SHA
→ create a detached baseline worktree
```

The untrusted manual candidate input is never passed directly to `actions/checkout`.

It then builds two independent frozen environments:

```text
candidate checkout/uv.lock → candidate .venv → candidate benchmark script
baseline worktree/uv.lock → baseline .venv → baseline benchmark script
```

Each lockfile is checked independently, each environment is synchronized with `--frozen`, and each revision executes the benchmark script stored in its own repository. The workflow records both SHAs, both lock/sync logs, both raw result files and the final comparison.

This prevents:

- unmerged or unrelated commits from producing authoritative-looking evidence;
- candidate input from controlling the initial checkout action;
- candidate dependency changes from contaminating the baseline measurement;
- candidate source or benchmark harness changes from executing baseline code under the wrong environment;
- reverse-time comparisons where the baseline is newer than the candidate.

A schema or dependency incompatibility must fail explicitly rather than silently changing the comparison method.

## Real benchmark protocol

For each worker count, record startup time, model-open time, mean/P50/P95 solve time, throughput, peak memory, failure rate and license wait. Repeat the full benchmark from clean processes and private model copies.

Portable Mock measurements are orchestration evidence only. They must not be described as licensed Aspen solve speed or engineering-model performance.
