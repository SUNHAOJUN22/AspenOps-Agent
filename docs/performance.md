# Performance Engineering

## Cost model

For `N` points and `W` persistent workers:

\[
T_{naive}\approx N(T_{start}+T_{open}+T_{solve}),
\]

\[
T_{pool}\approx W(T_{start}+T_{open})+\frac{N_{unique}}{W}(T_{solve}+T_{verify})+T_{IPC}.
\]

AspenOps removes repeated startup/open cost, deduplicates identical requests, caches reproducible cold-state evaluations and crosses IPC once per point.

## Effective worker count

\[
W_{effective}=\min(W_{configured},W_{license},W_{memory},W_{stable}).
\]

More processes are not automatically faster. Models with recycles, difficult phase behavior or expensive columns may compete for memory and license services.

## Scheduling, recycling and cache rules

Workers draw tasks from a shared queue rather than fixed equal chunks. Long-lived COM servers are recycled according to `ASPENOPS_WORKER_MAX_POINTS` and `ASPENOPS_WORKER_MAX_AGE_S`.

A result is cached only when reset mode is `reinitialize`, all validity gates pass, and runtime/backend/model/registry/request identity matches exactly. Failure caching is disabled by default.

## Authoritative performance-evidence workflow

`generate-performance-evidence.yml` is an evidence producer, not an arbitrary-ref executor. Its default baseline is the validated main-history runtime:

```text
ebef32ee1f2be74df5d5c5489e7ca86d35ac7bb2
```

Before tool installation or Python execution:

```text
checkout current trusted main workflow revision
→ fetch main history and tags
→ resolve candidate_ref and baseline_ref with --end-of-options
→ require both immutable SHAs to belong to main
→ require baseline to be an ancestor of candidate
→ detached checkout of validated candidate SHA
→ create detached baseline worktree
```

The manual candidate input is never passed directly to `actions/checkout`.

Two independent frozen environments are then created:

```text
candidate/uv.lock → candidate .venv → candidate benchmark script
baseline/uv.lock  → baseline .venv  → baseline benchmark script
```

Each lockfile is checked independently, each environment uses `uv sync --frozen`, and each revision executes the benchmark script stored in its own repository. Dependency, source or harness incompatibility fails explicitly.

## Evidence isolation

All current-run performance logs, SHAs, JSON results, Markdown reports and smoke output are written only to:

```text
$RUNNER_TEMP/aspenops-performance-evidence
```

Shell steps use GitHub's default `$RUNNER_TEMP` variable. The upload action uses `${{ runner.temp }}/aspenops-performance-evidence`, where the `runner` context is valid. The workflow does not read or upload tracked `var/benchmarks` files from the candidate checkout, so an early failure cannot publish stale committed benchmark results.

## Real benchmark protocol

For each worker count, record startup, model-open, mean/P50/P95 solve time, throughput, peak memory, failure rate and license wait. Repeat from clean processes and private model copies.

Portable Mock measurements are orchestration evidence only. They must not be described as licensed Aspen solve speed or engineering-model performance.
