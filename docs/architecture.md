# AspenOps 2.0 Architecture

## Design objective

Aspen Automation is a stateful COM interface around a proprietary nonlinear solver. The runtime must therefore preserve COM apartment ownership, simulator lifecycle, model identity, license limits and engineering evidence. AspenOps treats these as first-class invariants rather than incidental implementation details.

## Control plane and data plane

The control plane performs policy, schema validation, semantic resolution, unit conversion, queueing, caching, optimization, provenance and certification. The data plane consists of spawned workers. Each worker owns:

- one OS process;
- one COM STA;
- one simulator Automation Server;
- one private staged model copy;
- one semantic registry instance;
- one sequential command stream.

No COM proxy crosses a process boundary.

## Configuration and path-policy boundary

Environment variables and direct Python `Settings(...)` construction enter the same fail-closed validation boundary. A configuration object is not valid merely because it can be instantiated by Python. Construction rejects:

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

The Process Intent plane sits above the existing control plane. It accepts a constrained graph rather than executable simulator code:

```text
Human / text / image / search Agent
→ aspenops.flowsheet/v1
→ deterministic validation and digest
→ future backend compiler
→ existing execution control plane
```

The graph declares components, property package, units, typed ports, streams and finite scalar parameters. Unknown fields, executable metadata keys, raw Tree Paths, invalid references and unsafe connection structures fail closed.

Process understanding is therefore separated from simulator execution. A concept, parameter or repair Agent may produce only validated Process Intent IR. It cannot directly own COM, write arbitrary Python/VBA/Shell or call unrestricted simulator methods.

## Compiler boundary

Backend execution and automatic flowsheet compilation are independent capabilities. Aspen Plus and HYSYS execution already exist for approved models on licensed Windows, but their IR compilers are still planned. DWSIM, IDAES and Modelica/FMI are declared roadmap backends only; no adapter is claimed until a compiler conformance suite and execution tests exist.

```text
IR valid
AND compiler available
AND backend execution available
AND policy approved
```

Only then may an IR-driven model construction request enter the execution control plane.

## Bounded Agent pipeline

```text
Knowledge
→ Concept / topology
→ Parameter declaration
→ Validated execution request
→ Bounded repair proposal
→ Convergence, balance and human-review gate
```

Every stage has a declared responsibility and permitted output. Simulator feedback may propose bounded IR edits, but it cannot silently rewrite the execution policy or self-grant engineering approval.

## MCP compatibility and ownership

AspenOps 2.0 uses the MCP Python SDK 1.x API. Project and built-Wheel metadata constrain the `agent` extra to `mcp>=1.9,<2`; the frozen environment currently resolves `mcp 1.28.1`. CI inspects the actual Wheel `Requires-Dist` entry after `uv build`. Before importing `FastMCP`, the runtime reads the installed distribution version and rejects missing, unparseable or non-1.x versions.

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

A batched transaction is sent over one duplex pipe message with a correlation ID. The worker validates and executes the complete point. The parent process enforces the hard deadline. If the worker does not respond, only that Worker is terminated and later replaced.

The backend run protocol is typed rather than truthy. `engine_returned` and `converged` must be actual Boolean fields, and `convergence_state` must be a non-empty string. HYSYS solver-running properties are normalized from explicit booleans, COM `-1/0/1` and bounded known strings. Unknown values become `None`, which preserves an unknown convergence state instead of guessing.

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

## Cache identity, deduplication and singleflight

One cache key binds:

```text
runtime schema and AspenOps version
+ backend and stable simulator runtime identity
+ model SHA-256
+ semantic registry SHA-256
+ physical request identity
```

`ResultCache` combines a bounded memory LRU with SQLite WAL persistence. Invalid JSON or non-object payloads are discarded rather than returned. Hit counters are batched, and bulk reads/writes remain under the SQLite parameter budget.

`CasePool` provides two additional duplicate-work controls:

- identical points inside one batch collapse to one task and receive cloned results marked `same_batch_dedup`;
- concurrent identical single-point calls share one `_InflightEvaluation`; one leader executes while cancellable followers wait and receive `inflight_singleflight` provenance.

Persistent cache and singleflight reduce solver work without weakening runtime, model, registry or request identity. Failed or warm-start results enter cache only when explicit cache policy allows them.

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

Checkpoints use a temporary file followed by `os.replace`. Cancellation returns a terminal optimization document rather than silently accepting a partial best point. Mock output is qualified as control-plane evidence only; real backend output remains pending licensed runtime and human engineering review.

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

Finite inputs are not sufficient: multiplication, summation, residual subtraction and normalization can overflow. AspenOps therefore checks both observed and derived values. Non-finite required outputs are replaced by JSON `null` with a reason label. Non-finite or non-numeric constraints emit `constraint_non_finite` or `constraint_non_numeric` plus `constraint_failed`. Non-finite balance terms or derived residuals emit `balance_non_finite` plus `balance_failed`.

Backend diagnostics and runtime identity are recursively normalized to JSON-safe values. A required conversion is recorded as `backend_diagnostics_not_json_safe` and makes the result infeasible. This keeps `allow_nan=False` evidence writing reliable without pretending sanitized diagnostics are trustworthy.

Process-IR benchmark evidence adds independent topology, compiler availability, execution-attempted, convergence, material/energy closure, repair-iteration and human-intervention fields. A skipped or unavailable backend cannot declare convergence.

## Persistence

`JobStore` uses SQLite WAL for durable request, lease, event and result state. The CLI has explicit responsibilities:

```text
submit     → validate, pin paths and create a pending durable record
scheduler  → long-lived lease, heartbeat, execute and commit service
job        → read durable state only
cancel     → request cancellation and set the owned-worker grace deadline
```

A short-lived submission process and a long-lived scheduler may have different working directories. `pin_durable_request_paths()` resolves relative `model_path` and `registry_path` values against the submission working directory, stores absolute paths, and records `submission_cwd`. CLI and MCP durable submission surfaces call this shared helper before entering the Scheduler. The CLI response exposes `paths_pinned=true`.

Direct Python callers that invoke `BackgroundScheduler.submit()` should supply absolute paths or call `pin_durable_request_paths()` first. Real backends still reapply allowed-root and realpath policy.

This separation prevents a short-lived `submit` process from pretending that its daemon thread can continue after process exit. Cancellation of a pending or retry-waiting job is immediate; active work transitions to `cancelling`, and only the matching owned Worker may be terminated after the grace deadline.

Recovery follows the actual state machine:

- cancellation requested during restart or lease expiry → `cancelled`;
- active work with attempts remaining → `retry_wait`;
- active work after the final attempt → `dead_letter`;
- completed results remain bound to an idempotent commit token and evidence bundle.

## Evidence integrity and authenticity

Evidence bundles use bounded ZIP processing and JSON serialization with `allow_nan=False`. `request.json`, `results.json` and `environment.json` are declared in the manifest with exact byte size and SHA-256. The manifest additionally binds request, results, model and registry hashes plus runtime schema and AspenOps version.

Verification rejects missing, extra, reserved, malformed or oversized members before trusting content. Member declarations are validated before each digest and size is recomputed. Archive path, compression and total-size limits are enforced by `ArchiveLimits` and `validate_archive()`.

Unsigned bundles provide internal integrity checks only. A signed v2 bundle uses Ed25519 over canonical manifest bytes and records a bounded key ID. Authenticity exists only when verification uses the expected trusted public key. Integrity, authenticity, licensed runtime execution and human engineering acceptance remain four separate levels of evidence.
