# AspenOps 2.0 performance and update audit V2 — 2026-07-27

## Scope and baseline

This independent V2 pass started from `main` commit:

```text
4c95fdef39adacf2cf6ce9965c05e8a5c17d9a55
```

It re-audits dependency updates, portable Python performance, ResultCache behaviour, durable-job reads, SQLite query plans, MCP read surfaces, performance evidence and documentation contracts.

It does **not** claim faster licensed Aspen Plus or Aspen HYSYS model open, nonlinear solve or engineering performance. Those claims require a licensed Windows host, an approved model and registry, fixed runtime identity, repeated trials and qualified engineering acceptance.

## Primary-source update review

The review used official sources current on 2026-07-27:

- Python release and command-line documentation;
- Python `cProfile`, `tracemalloc` and multiprocessing documentation;
- SQLite release, WAL, query-planner, `EXPLAIN QUERY PLAN` and `PRAGMA optimize` documentation;
- uv release and GitHub Actions integration documentation;
- MCP Python SDK official repository and release guidance;
- Ruff, mypy, pytest, SciPy and NumPy official release/documentation surfaces;
- GitHub Actions official documentation.

Search summaries and secondary blogs were not treated as authority.

## Dependency and runtime decision table

| Component | Repository state | Current upstream signal | Value of updating | Main risk | Decision |
|---|---|---|---|---|---|
| Python | public matrix 3.11–3.13 | 3.14 is the current stable feature line; 3.15 is pre-release | possible interpreter improvements | pywin32, COM, MCP, cryptography, Wheel and licensed-host qualification | **DEFERRED** until a separate 3.14 Windows/Wheel matrix exists |
| uv | workflows pin `0.11.16` | `0.11.16` is current stable | none | unnecessary workflow churn | **RETAINED** |
| MCP SDK | lock resolves `1.28.1`; package requires `mcp>=1.9,<2` | v1 remains the supported stable line while v2 migration develops | no proven performance gain | API/lifespan/tool-registration regression | **RETAINED** with `<2` boundary |
| mypy | lock resolves `2.3.0` | recent current line | already current enough for this audit | strict-mode behaviour changes | **RETAINED** |
| SQLite | supplied by each Python runtime | upstream has newer releases than some Python builds | planner/runtime fixes may exist | replacing stdlib SQLite changes deployment and Windows qualification | **DEFERRED**; record `sqlite3.sqlite_version` in evidence |
| NumPy/SciPy | not required | active current releases | possible vectorized optimizer work | Wheel size, install time, cold start and Windows matrix | **REJECTED** until profile proves Python optimizer overhead dominates evaluations |
| Python bytecode compilation | not globally enabled | uv supports compile-bytecode options | possible cold-start benefit | longer sync and broader cache footprint | **INCONCLUSIVE** pending same-environment install/startup evidence |
| `uv cache prune --ci` | not inserted into active quality path | officially supported | smaller persisted CI cache | pruning before later Wheel/smoke steps can slow the same job | **DEFERRED** until placed after all cache consumers and timed |

No lockfile was regenerated merely because a newer marketing version exists.

## New retained optimizations

### PERF-V2-001 — indexed single-query recent-job reader

The existing compatibility method `JobStore.list_recent()` performs an ID query followed by one `get()` connection/query per row. The product-facing MCP `list_recent_jobs` path is now routed through `list_recent_job_records()`:

```text
bounded limit
→ one SQLite connection
→ one SELECT of the complete public job record
→ ORDER BY created_at DESC, job_id DESC
→ shared row decoder
```

The reader lazily and idempotently creates:

```sql
CREATE INDEX IF NOT EXISTS idx_jobs_recent_created_job
ON jobs(created_at DESC, job_id DESC)
```

Index creation is explicitly committed and followed by bounded `PRAGMA optimize`. No request body is selected. Creation, claim, heartbeat, cancellation, recovery, lease ownership and idempotent result commits remain in the original `JobStore` transaction implementation.

Decision: **RETAINED**.

### PERF-V2-002 — deterministic JobStore query-plan evidence

`scripts/measure_job_store_queries.py` creates a 1000-record portable database and records:

- connection count;
- SELECT statement count;
- returned row count;
- persistent index inventory;
- `EXPLAIN QUERY PLAN` details;
- SQLite runtime version;
- commit and environment identity.

Hard contract:

```text
1000 records, limit 20
→ 1 connection
→ 1 SELECT
→ 20 records
→ idx_jobs_recent_created_job used
→ no USE TEMP B-TREE
```

Output:

```text
var/ci/job-store-query-plan.json
```

Decision: **RETAINED**.

### PERF-V2-003 — performance sidecar integration

The existing CLI startup evidence step now emits three colocated artifacts:

```text
cli-startup.json
operation-counts.json
job-store-query-plan.json
```

A sidecar failure fails the existing quality step instead of silently publishing incomplete performance evidence.

Decision: **RETAINED**.

## Rolled-back candidate

### PERF-V2-004 — structured-object memory LRU

Candidate: store parsed dictionaries in the in-process ResultCache LRU and return `deepcopy()` values to avoid `json.loads`.

Correctness tests proved isolation, but a same-interpreter representative nested-payload experiment showed that generic Python `deepcopy()` could be materially slower than the C implementation used by `json.loads`. A zero-decode counter alone therefore did not prove improved throughput.

The candidate was reverted. The retained strategy is:

```text
compact JSON snapshot in memory
→ one C JSON decode per unique key per get_many call
→ zero SQLite connections for memory hits
→ independent nested return objects
```

The deterministic operation-count artifact records three requested hits across two calls as:

```text
json_decode_calls = 2
sqlite_connection_calls = 0
strategy = compact_json_snapshot
```

Decision: **ROLLED_BACK**.

## Inconclusive candidate

### PERF-V2-005 — reuse canonical evidence bytes

`write_run_bundle()` currently writes readable sorted JSON members and independently computes canonical request/result hashes. Writing compact canonical members could remove repeated serialization and reduce archive bytes, but it changes the human-readable member representation and has no current-HEAD bundle CPU/size benchmark.

No evidence byte contract was changed.

Decision: **INCONCLUSIVE**.

## Preserved deterministic contracts

The following remain hard gates:

```text
100 repeated request references
→ 1 cache-key calculation
→ 1 governed solver call
→ 1 canonical result serialization
→ 99 same_batch_dedup results
→ deep nested isolation

1024 cache hits
→ pending hit counter flushed to zero

3 memory-cache hits across 2 calls
→ 2 compact-JSON decodes
→ 0 SQLite connections
→ deep nested isolation

1000 identical Pareto points
→ 0 dominance calls

1000 durable jobs, recent limit 20
→ 1 connection
→ 1 SELECT
→ indexed order
→ no temporary sort
```

## Security and correctness invariants

Every retained change preserves:

1. one COM owner per Worker process and STA;
2. private staged model copies;
3. Windows Job Object and process-fingerprint boundaries;
4. licence-slot limits;
5. fail-closed configuration, paths, backend protocol and finite evidence;
6. content-derived model and registry SHA-256;
7. cache identity over runtime, model, registry and physical request;
8. scheduler lease, heartbeat, recovery, cancellation and atomic commit semantics;
9. MCP 1.x runtime and `<2` package boundary;
10. bundle structure, member hashes, strict `all_ok`, ZIP safety and Ed25519 verification;
11. the distinction between Mock orchestration evidence and licensed engineering evidence.

## Commands and generated evidence

```bash
uv run python scripts/measure_cli_startup.py \
  --output var/ci/cli-startup.json \
  --trials 7 \
  --warmups 2

uv run python scripts/measure_operation_counts.py \
  --output var/ci/operation-counts.json

uv run python scripts/measure_job_store_queries.py \
  --output var/ci/job-store-query-plan.json \
  --records 1000 \
  --limit 20
```

Full qualification still requires:

```bash
uv lock --check
uv sync --frozen --extra dev --extra agent --extra signing
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest -W error::ResourceWarning \
  --cov=aspenops_nexus \
  --cov-branch \
  --cov-fail-under=94.5
uv build
```

## Verification boundary

The connected execution environment could not clone the full repository because external GitHub DNS resolution remained unavailable. A standalone SQLite reproduction confirmed that the governed recent-job query returns 20 of 1000 records using:

```text
SCAN jobs USING INDEX idx_jobs_recent_created_job
```

That reproduction is useful design evidence, not a substitute for current-HEAD Ruff, strict mypy, full pytest, coverage, build, Wheel installation, public Windows or hosted Actions results. Those claims require current commit artifacts.
