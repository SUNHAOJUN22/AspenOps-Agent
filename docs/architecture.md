# AspenOps 2.0 Architecture

## Design objective

Aspen Automation is a stateful COM interface around a proprietary nonlinear solver. The runtime must preserve COM apartment ownership, simulator lifecycle, model identity, licence limits and engineering evidence. AspenOps treats these as first-class invariants rather than incidental implementation details.

Performance is subordinate to correctness. An optimization is retained only when it preserves identity, isolation, durability, evidence and certification boundaries and is covered by deterministic operation-count contracts or same-environment measurements. A candidate that appears simpler or reports a lower counter may still be rolled back when representative measurement shows worse execution cost.

## Control plane and data plane

The control plane performs policy, schema validation, semantic resolution, unit conversion, queueing, caching, optimization, provenance and certification. The data plane consists of spawned Workers. Each Worker owns:

- one OS process;
- one COM STA;
- one simulator Automation Server;
- one private staged model copy;
- one semantic registry instance;
- one sequential command stream.

No COM proxy crosses a process boundary.

## Configuration and path-policy boundary

Environment variables and direct Python `Settings(...)` construction enter the same fail-closed validation boundary. Construction rejects:

- unsupported backends or operating modes;
- string or numeric values pretending to be Boolean flags;
- non-integral, non-finite, zero or negative resource budgets;
- non-`Path` values in state and allowed-root fields;
- real backends without absolute allowed roots;
- a real-backend state directory outside those roots.

```text
environment / Python API
→ type and finite-budget validation
→ backend and mode allowlist
→ real-backend root policy
→ expanduser + resolve
→ controlled operation
```

`Policy.assert_path()` resolves a requested path and requires it to remain under an approved root. This rejects traversal, symlink, junction and other realpath escapes before Worker, COM or evidence creation. `readonly`, `default` and `enhanced` remain explicit operation modes; an unknown mode cannot silently inherit default authority.

## Simulator-neutral intent plane

The Process Intent plane accepts a constrained graph rather than executable simulator code:

```text
Human / text / image / search Agent
→ aspenops.flowsheet/v1
→ deterministic validation and digest
→ future backend compiler
→ existing execution control plane
```

The graph declares components, property package, units, typed ports, streams and finite scalar parameters. Unknown fields, executable metadata keys, raw Tree Paths, invalid references and unsafe connection structures fail closed.

Process understanding is separated from simulator execution. A concept, parameter or repair Agent may produce only validated Process Intent IR. It cannot directly own COM, write arbitrary Python/VBA/Shell or call unrestricted simulator methods.

## Compiler boundary

Backend execution and automatic flowsheet compilation are independent capabilities. Aspen Plus and HYSYS execution exist for approved models on licensed Windows, but their IR compilers remain planned. DWSIM, IDAES and Modelica/FMI are roadmap backends only; no adapter is claimed until a compiler conformance suite and execution tests exist.

```text
IR valid
AND compiler available
AND backend execution available
AND policy approved
```

Only then may an IR-driven model-construction request enter the execution control plane.

## Bounded Agent pipeline

```text
Knowledge
→ Concept / topology
→ Parameter declaration
→ Validated execution request
→ Bounded repair proposal
→ Convergence, balance and human-review gate
```

Every stage has a declared responsibility and permitted output. Simulator feedback may propose bounded IR edits, but it cannot silently rewrite execution policy or self-grant engineering approval.

## Lightweight CLI boundary

The installed `aspenops` entry point targets `cli_bootstrap.py`, not the full execution module. The bootstrap contains only the public argparse surface, package version and package-resource path resolution.

```text
aspenops --version / --help / command --help
→ lightweight bootstrap
→ exit without Pool, Scheduler, Optimizer, Evidence or MCP imports

executed command
→ lightweight dispatch check
→ one import of full cli.py
→ one parse and normal execution
```

The bootstrap and full parser help output are tested for exact equality. Real commands are not parsed twice. This improves common cold-start paths without creating a second command implementation or weakening any execution gate.

## MCP compatibility and ownership

AspenOps 2.0 uses the MCP Python SDK 1.x API. Project and built-Wheel metadata constrain the `agent` extra to `mcp>=1.9,<2`; the frozen environment resolves `mcp 1.28.1`. CI inspects the actual Wheel `Requires-Dist` entry after `uv build`. Before importing `FastMCP`, runtime reads the installed distribution version and rejects missing, unparseable or non-1.x versions.

MCP server lifetime owns the durable execution fabric:

```text
FastMCP lifespan enter
→ validate supported SDK before API import
→ scheduler.start()
→ serve fourteen constrained tools
→ lifespan exit
→ scheduler.stop()
→ Worker and PoolManager cleanup
```

The MCP facade never exposes arbitrary Shell, Python, VBA, COM methods or raw Aspen Tree Paths. Lifecycle cleanup is software evidence only and cannot grant licensed Aspen physical or engineering certification.

## Evaluation transaction

```text
RECEIVED
  → VALIDATED
  → REINITIALIZED | WARM_START
  → WRITES_COMMITTED
  → ENGINE_RETURNED
  → OUTPUTS_READ
  → VERIFIED | FAILED
```

A batched transaction is sent over one duplex pipe message with a correlation ID. The Worker validates and executes the complete point. The parent process enforces the hard deadline. If the Worker does not respond, only that Worker is terminated and later replaced.

The backend run protocol is typed rather than truthy. `engine_returned` and `converged` must be actual Boolean fields, and `convergence_state` must be a non-empty string. Aspen Plus and HYSYS running properties are normalized from explicit booleans, COM `-1/0/1` and bounded known strings. Unknown values become `None`, preserving an unknown state instead of guessing.

## Worker ownership and recycling

A Worker is an ownership unit, not a thread around a shared COM object:

```text
source model
→ temporary worker-generation copy
→ spawned Python process
→ Windows Job scope and one simulator owner
→ correlated IPC protocol
→ graceful close or verified recycle
```

Startup failure terminates the spawned process, closes both pipe endpoints and deletes the staged directory. Normal shutdown requests a correlated `closed` response before escalation. Recycling is triggered by crash, timeout, protocol failure, tainted transaction, point budget, age, cancellation or lease loss. Pool generation increments when a handle is replaced, preserving provenance for the old and new Worker.

AspenOps only terminates a process it created and still verifies as owned. On Windows, Job Object supervision supplies the primary ownership boundary; process fingerprints and descendant checks provide the fallback. Unrelated simulator processes are never legitimate cleanup targets.

## Semantic registry

The registry is both an API schema and a capability boundary. A semantic node defines access, unit, quantity, bounds, identifiers, candidate paths or locators, backend and verification status. Agent-provided identifiers are restricted to safe characters and cannot contain path separators or template syntax.

The registry hash participates in cache identity. Changing a path, bound, unit or meaning invalidates cached results.

## Cache identity, accounting, deduplication and singleflight

One cache key binds:

```text
runtime schema and AspenOps version
+ backend and stable simulator runtime identity
+ model SHA-256
+ semantic registry SHA-256
+ physical request identity
```

`ResultCache` combines a bounded memory LRU with SQLite WAL persistence. Invalid JSON or non-object payloads are discarded rather than returned. Bulk reads and writes remain under the SQLite parameter budget.

Retained performance changes preserve the same identity and transaction model:

- `_pending_hit_total` makes flush-threshold checks O(1) instead of rescanning all pending keys;
- SQLite key batches are yielded instead of preallocated;
- JSON storage uses compact separators but remains deterministic and `allow_nan=False`;
- `PRAGMA optimize` runs after schema initialization while WAL and `synchronous=NORMAL` remain intact;
- the memory LRU retains compact JSON snapshots, so duplicate keys in one `get_many` call decode once and memory hits open no SQLite connection;
- independent values across calls are produced by the standard-library C JSON decoder.

A structured-object LRU using generic `deepcopy()` was implemented as a candidate and then rolled back after representative same-interpreter measurement showed that zero decode count did not imply lower execution cost.

`CasePool` provides additional duplicate-work controls:

- exact repeated references to the same immutable request object reuse one cache-key computation inside a batch;
- physically equivalent but distinct request objects are still independently canonicalized and converge to the same content key;
- identical points inside one batch collapse to one task and receive deeply isolated results marked `same_batch_dedup`;
- concurrent identical single-point calls share one `_InflightEvaluation`; one leader executes while cancellable followers wait and receive `inflight_singleflight` provenance;
- one cacheable solve creates one canonical result dictionary; duplicate result objects use deep cloning rather than repeated dataclass serialization.

Persistent cache and singleflight reduce solver work without weakening runtime, model, registry or request identity. Failed or warm-start results enter cache only when explicit cache policy allows them. Model and registry SHA-256 remain byte-derived; mtime/size shortcuts are rejected.

## Budgeted constrained optimization

Optimization parses a finite problem contract before any solver call:

- continuous, integer, categorical and ordinal variables;
- minimize or maximize objectives with positive weights;
- unique variable names, targets and objective keys;
- finite bounds, choices, population, generation and evaluation budgets;
- optional checkpoint paths constrained to state or allowed roots.

```text
validated OptimizationProblem
→ seeded differential-evolution population
→ governed CasePool batch evaluations
→ independent communication / convergence / feasibility / balance evidence
→ atomic checkpoint and cancellation handling
→ best candidate and Pareto evidence
```

DE performs one batch evaluation per generation and keeps the same evaluation budget. Index selection samples `range(population_size - 1)` and maps around the target index, avoiding one population-sized exclusion list per target.

Pareto processing performs ordered exact deduplication before dominance work. If a feasible point exists, infeasible points are removed before pairwise comparison. If every point is infeasible, only minimum-violation points remain. Pairwise objective comparisons are limited to feasible unique points while Deb feasibility ordering is preserved.

Checkpoints use a temporary file followed by `os.replace`. Cancellation returns a terminal optimization document rather than silently accepting a partial best point. Mock output is control-plane evidence only; real backend output remains pending licensed runtime and human engineering review.

## Performance evidence architecture

Performance qualification has two channels.

### Deterministic operation contracts

`scripts/measure_operation_counts.py` records:

```text
100 repeated request references
→ 1 cache-key computation
→ 1 solver call
→ 1 canonical serialization
→ 99 same_batch_dedup results
→ deep nested isolation

1024 cache hits
→ threshold flush
→ pending_hit_total == 0

3 memory hits across 2 calls
→ 2 compact-JSON decodes
→ 0 SQLite connections
→ deep nested isolation

1000 identical Pareto points
→ exact dedup
→ dominance_calls == 0
```

`scripts/measure_job_store_queries.py` separately records:

```text
1000 durable jobs, recent limit 20
→ 1 SQLite connection
→ 1 SELECT
→ 20 returned records
→ idx_jobs_recent_created_job used
→ no USE TEMP B-TREE
```

These counts are hard regression contracts and are executed through tests included in Linux, public Windows and pre-licensed-COM software gates.

### Environment-sensitive diagnostics

`scripts/measure_cli_startup.py` records warmups, repeated trials, median, P95, min/max, coefficient of variation and same-environment bootstrap/full-CLI comparisons. A separate `-X importtime` process records import diagnostics without contaminating normal startup samples.

The operation-count probe separately records cProfile, tracemalloc and RSS. Profiler overhead is explicitly labelled; wall time on shared runners is evidence rather than a narrow hard gate.

The quality benchmark step produces:

```text
var/ci/cli-startup.json
var/ci/operation-counts.json
var/ci/job-store-query-plan.json
```

All three carry environment and commit identity. None is licensed Aspen solve evidence.

## Runtime compatibility

Aspen Plus registrations are discovered from both Windows registry views. Versioned `Apwn.Document.*` candidates are sorted by numeric suffix and tried newest-first, followed by `Apwn.Document`. HYSYS uses the corresponding `HYSYS.Application.*` strategy.

No marketing-version mapping is assumed. The actual successful ProgID and exposed application attributes are captured as runtime evidence.

## Independent validity state

One evaluation returns independent gates:

```text
communication_ok
engine_ok
converged
feasible
constraint diagnostics
balance_residuals
finite JSON evidence
```

`ok` is the conjunction of communication, engine return, convergence and feasibility. Feasibility includes constraints, material/energy balances and evidence-quality failures.

Finite inputs are not sufficient: multiplication, summation, residual subtraction and normalization can overflow. AspenOps checks observed and derived values. Non-finite required outputs become JSON `null` with a reason label. Non-finite or non-numeric constraints emit `constraint_non_finite` or `constraint_non_numeric` plus `constraint_failed`. Non-finite balance terms or derived residuals emit `balance_non_finite` plus `balance_failed`.

Backend diagnostics and runtime identity are recursively normalized to JSON-safe values. A required conversion is recorded as `backend_diagnostics_not_json_safe` and makes the result infeasible. This keeps `allow_nan=False` evidence writing reliable without pretending sanitized diagnostics are trustworthy.

Process-IR benchmark evidence adds independent topology, compiler availability, execution-attempted, convergence, material/energy closure, repair-iteration and human-intervention fields. A skipped or unavailable backend cannot declare convergence.

## Persistence and read-query boundary

`JobStore` uses SQLite WAL for durable request, lease, event and result state. The CLI responsibilities remain:

```text
submit     → validate, pin paths and create a pending durable record
scheduler  → long-lived lease, heartbeat, execute and commit service
job        → read durable state only
cancel     → request cancellation and set the owned-worker grace deadline
```

A short-lived submission process and a long-lived scheduler may have different working directories. `pin_durable_request_paths()` resolves relative `model_path` and `registry_path` values against the submission working directory, stores absolute paths and records `submission_cwd`. CLI and MCP durable submission surfaces call this shared helper before entering the Scheduler. The CLI response exposes `paths_pinned=true`.

Direct Python callers that invoke `BackgroundScheduler.submit()` should supply absolute paths or call `pin_durable_request_paths()` first. Real backends still reapply allowed-root and realpath policy.

This separation prevents a short-lived `submit` process from pretending that its daemon thread can continue after process exit. Cancellation of a pending or retry-waiting job is immediate; active work transitions to `cancelling`, and only the matching owned Worker may be terminated after the grace deadline.

Recovery follows the actual state machine:

- cancellation requested during restart or lease expiry → `cancelled`;
- active work with attempts remaining → `retry_wait`;
- active work after the final attempt → `dead_letter`;
- completed results remain bound to an idempotent commit token and evidence bundle.

The compatibility Python method `JobStore.list_recent()` still retains its historical ID-plus-`get()` implementation. The product-facing MCP `list_recent_jobs` surface uses `job_queries.list_recent_job_records()` instead:

```text
bounded limit
→ one connection
→ lazily committed idx_jobs_recent_created_job
→ one SELECT of public job fields
→ ORDER BY created_at DESC, job_id DESC
→ shared row decoder
```

Request bodies are not selected. Index creation is idempotent, explicitly committed and followed by bounded `PRAGMA optimize`. This read optimization does not alter creation, claim, heartbeat, retry, cancellation, recovery, event or idempotent commit transactions. Migrating the compatibility method itself remains a future consolidation step after the same query-plan and legacy-call tests are applied to that API.

## Evidence integrity and authenticity

Evidence bundles use bounded ZIP processing and JSON serialization with `allow_nan=False`. `request.json`, `results.json` and `environment.json` are declared in the manifest with exact byte size and SHA-256. The manifest additionally binds request, results, model and registry hashes plus runtime schema and AspenOps version.

Verification rejects missing, extra, reserved, malformed or oversized members before trusting content. Member declarations are validated before each digest and size is recomputed. Archive path, compression and total-size limits are enforced by `ArchiveLimits` and `validate_archive()`.

Unsigned bundles provide internal integrity checks only. A signed v2 bundle uses Ed25519 over canonical manifest bytes and records a bounded key ID. Authenticity exists only when verification uses the expected trusted public key. Integrity, authenticity, licensed runtime execution and human engineering acceptance remain separate levels of evidence.

A candidate to reuse canonical request/result hash bytes as archive members remains INCONCLUSIVE: it could remove repeated serialization, but it would change the readable member-byte representation and lacks current-HEAD CPU and archive-size evidence.
