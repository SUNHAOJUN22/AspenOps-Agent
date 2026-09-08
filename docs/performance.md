# Performance Engineering

## Cost model

For `N` points and `W` persistent Workers:

\[
T_{naive}\approx N(T_{start}+T_{open}+T_{solve}),
\]

\[
T_{pool}\approx W(T_{start}+T_{open})+\frac{N_{unique}}{W}(T_{solve}+T_{verify})+T_{IPC}.
\]

AspenOps removes repeated startup/open cost, deduplicates identical requests, caches reproducible cold-state evaluations and crosses IPC once per point.

Portable Python overhead matters most when `T_solve` is small or cached/deduplicated work avoids the simulator completely. Licensed Aspen performance remains dominated by the approved model, runtime, licence service, convergence behaviour and Worker count.

## Effective Worker count

\[
W_{effective}=\min(W_{configured},W_{license},W_{memory},W_{stable}).
\]

More processes are not automatically faster. Windows spawn creates a fresh interpreter, and real simulators consume memory and licence services. Models with recycles, difficult phase behaviour or expensive columns may become slower or less stable when Worker count rises.

## Scheduling, recycling and cache rules

Workers draw tasks from a shared queue rather than fixed equal chunks. Long-lived COM servers are recycled according to `ASPENOPS_WORKER_MAX_POINTS` and `ASPENOPS_WORKER_MAX_AGE_S`.

A result is cached only when reset mode is `reinitialize`, all validity gates pass, and runtime/backend/model/registry/request identity matches exactly. Failure caching is disabled by default.

Retained cache and batch optimizations preserve those rules:

- flush-threshold accounting uses an O(1) pending-hit total;
- SQLite batches are generated lazily within the parameter budget;
- persistent and in-memory snapshots use compact JSON with `allow_nan=False`;
- schema initialization executes bounded `PRAGMA optimize` while WAL and NORMAL synchronous mode remain enabled;
- duplicate keys inside one `get_many` call decode once;
- memory hits do not open SQLite;
- standard-library C JSON decoding returns independent nested values across calls;
- repeated references to one immutable request object reuse one cache-key computation in a batch;
- one cacheable solve generates one canonical result dictionary;
- deduplicated and singleflight result objects remain deeply isolated.

A structured-object memory LRU using generic `deepcopy()` was measured and rolled back. A zero-decode counter did not justify keeping a candidate that could be slower than the C JSON decoder for representative nested results.

Model and registry hashes remain byte-derived. mtime/size digest shortcuts are not permitted because they weaken cache and evidence identity.

## CLI startup model

The installed console script points to `aspenops_nexus.cli_bootstrap:main`.

```text
version or help request
→ lightweight argparse surface
→ exit without Pool, Scheduler, Optimizer, Evidence or MCP imports

executed command
→ delegate once
→ full CLI import
→ one parse and normal execution
```

The bootstrap and full parser help output are tested for exact equality. A real command is not parsed twice.

## Deterministic low-noise evidence

Run:

```bash
uv run python scripts/measure_operation_counts.py \
  --output var/ci/operation-counts.json

uv run python scripts/measure_job_store_queries.py \
  --output var/ci/job-store-query-plan.json \
  --records 1000 \
  --limit 20
```

`operation-counts.json` records:

- cache-key calls;
- solver calls;
- canonical result serializations;
- same-batch deduplicated result count;
- deep result isolation;
- pending cache-hit state after threshold flush;
- compact-JSON decode count and SQLite connection count for memory hits;
- Pareto dominance calls after exact deduplication;
- cProfile diagnostics;
- tracemalloc current and peak bytes;
- process RSS before and after.

`job-store-query-plan.json` records:

- durable-record population;
- recent-job limit and returned count;
- SQLite connection count;
- SELECT statement count;
- persistent index inventory;
- `EXPLAIN QUERY PLAN` details;
- SQLite runtime version;
- commit and environment identity.

Current hard contracts are:

```text
100 repeated request references
→ 1 cache-key computation
→ 1 solver call
→ 1 canonical serialization
→ 99 same_batch_dedup results
→ deep nested isolation

1024 cache hits
→ pending_hit_total == 0 after threshold flush

3 memory hits across 2 calls
→ 2 compact-JSON decodes
→ 0 SQLite connections
→ deep nested isolation

1000 identical Pareto points
→ dominance_calls == 0

1000 durable jobs, recent limit 20
→ 1 connection
→ 1 SELECT
→ 20 returned records
→ idx_jobs_recent_created_job used
→ no USE TEMP B-TREE
```

Operation and query counts are deterministic performance gates. cProfile and memory measurements are diagnostics with profiler overhead explicitly labelled.

## Indexed recent-job read boundary

The compatibility method `JobStore.list_recent()` retains its historical ID query followed by one `get()` per row. The product-facing MCP `list_recent_jobs` path uses `job_queries.list_recent_job_records()` instead:

```text
bounded limit
→ one SQLite connection
→ lazily committed idx_jobs_recent_created_job
→ one SELECT of public job fields
→ ORDER BY created_at DESC, job_id DESC
→ shared row decoder
```

The query does not select request bodies. Index creation is idempotent, committed and followed by bounded `PRAGMA optimize`.

This optimization changes only the governed read surface. Creation, claim, heartbeat, retry, cancellation, lease recovery, events and idempotent result commits remain in the original transactional `JobStore` implementation.

## Environment-sensitive startup evidence

Run:

```bash
uv run python scripts/measure_cli_startup.py \
  --output var/ci/cli-startup.json \
  --trials 7 \
  --warmups 2
```

The probe compares lightweight bootstrap and full CLI control paths under the same interpreter and machine. It records median, P95, min, max, coefficient of variation and raw samples. A separate Python `-X importtime` process records import diagnostics so profiler overhead is not included in normal startup samples.

The startup probe also creates `operation-counts.json` and `job-store-query-plan.json` in the same artifact directory. A sidecar failure fails the evidence-producing step rather than silently publishing an incomplete performance result.

Shared-runner wall time is visible evidence but is not a narrow hard gate. Module-import boundaries, parser equivalence, operation counts and query plans are enforced separately by deterministic tests.

## Optimizer allocation and Pareto work

Differential evolution still performs one batch evaluation per generation and preserves the configured evaluation budget. Sampling three peer indices uses `range(population_size - 1)` and maps around the target index, removing one population-sized exclusion-list allocation per target.

Pareto-front processing:

1. removes exact duplicates while preserving order;
2. removes infeasible points before pairwise work when a feasible point exists;
3. retains only minimum-violation points when every point is infeasible;
4. performs objective dominance comparisons only among feasible unique points.

This preserves Deb feasibility ordering while reducing duplicate and infeasible comparison work.

## Update decisions

The detailed V2 decision table is in [Performance Audit V2](performance-audit-2026-07-27-v2.md).

Current decisions include:

- Python 3.14 support is deferred until a separate pywin32/COM/MCP/cryptography/Wheel/Windows matrix exists;
- uv remains pinned at `0.11.16`, the current stable line used by workflows;
- MCP remains on stable v1 with package boundary `mcp>=1.9,<2`;
- the lockfile already resolves recent `mcp 1.28.1` and `mypy 2.3.0`, so no marketing-version-only lock refresh was performed;
- replacing stdlib SQLite with a separate binding is deferred;
- NumPy/SciPy/Numba/Rust are rejected until profile evidence shows Python optimizer overhead dominates real evaluation cost;
- global bytecode compilation and `uv cache prune --ci` remain inconclusive/deferred pending same-environment install and job-level timing evidence;
- request/result canonical bytes are not reused as readable evidence members without current-HEAD CPU and archive-size evidence.

## Authoritative performance-evidence workflow

`generate-performance-evidence.yml` is an evidence producer, not an arbitrary-ref executor. Its default baseline is:

```text
ebef32ee1f2be74df5d5c5489e7ca86d35ac7bb2
```

The first Ubuntu step always runs. It records the dispatch ref and explicitly exits with status 2 when `GITHUB_REF` is not `refs/heads/main`; an invalid manual dispatch therefore fails rather than becoming all-skipped.

Before tool installation or Python execution:

```text
record dispatch-ref.txt and dispatch-guard.log in runner temporary evidence
→ explicitly require GITHUB_REF == refs/heads/main
→ checkout current trusted main workflow revision
→ fetch main history and tags
→ resolve candidate_ref and baseline_ref with --end-of-options
→ require both immutable SHAs to belong to main
→ require baseline to be an ancestor of candidate
→ detached checkout of validated candidate SHA
→ create detached baseline worktree
```

The manual candidate input is never passed directly to `actions/checkout`.

Two independent frozen environments are created:

```text
candidate/uv.lock → candidate .venv → candidate benchmark script
baseline/uv.lock  → baseline .venv  → baseline benchmark script
```

Each lockfile is checked independently, each environment uses `uv sync --frozen`, and each revision executes the benchmark script stored in its own repository. Dependency, source or harness incompatibility fails explicitly.

The quality benchmark comparison emits:

```text
var/ci/cli-startup.json
var/ci/operation-counts.json
var/ci/job-store-query-plan.json
```

## Evidence isolation

Current-run performance logs, SHAs, JSON results, Markdown reports, guard evidence and smoke output are written only to:

```text
$RUNNER_TEMP/aspenops-performance-evidence
```

Shell steps use GitHub's `$RUNNER_TEMP`. Upload uses `${{ runner.temp }}/aspenops-performance-evidence`. The workflow does not upload tracked benchmark files from the candidate checkout, so an early failure cannot publish stale committed results.

Quality-job artifacts use `var/ci` inside the checked-out current commit and include `github.run_id` and `github.run_attempt` in the artifact name.

## Real benchmark protocol

For each Worker count, record startup, model-open, mean/P50/P95 solve time, throughput, peak memory, failure rate and licence wait. Repeat from clean processes and private model copies.

Bind every licensed result to:

- exact AspenOps commit;
- Aspen product/build and successful ProgID;
- approved model and registry hashes;
- licence server and feature identity;
- Worker count and licence slots;
- convergence, constraints and balances;
- environment metadata;
- qualified process-engineering acceptance.

Portable Mock and SQLite measurements are control-plane evidence only. They must not be described as licensed Aspen solve speed or engineering-model performance.
