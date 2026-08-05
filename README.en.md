<div align="center">

# AspenOps 2.0

## Deterministic control plane for Aspen Plus, Aspen HYSYS and AI agents

**Agent / CLI / Python → validated process intent → isolated execution → nonlinear solve → engineering decision → reproducible evidence**

[中文](README.md) · [Architecture](docs/architecture.md) · [Process Intent IR](docs/process-intent-ir.md) · [Adapter Conformance](docs/native-adapter-conformance.md) · [Windows Setup](docs/windows-setup.md) · [Performance](docs/performance.md) · [Performance Audit V1](docs/performance-audit-2026-07-27.md) · [Performance Audit V2](docs/performance-audit-2026-07-27-v2.md) · [Certification](docs/certification.md) · [Quality Report](docs/quality-report.md) · [Security](SECURITY.md) · [Contributing](CONTRIBUTING.md)

[![CI main push](https://github.com/SUNHAOJUN22/AspenOps-Agent/actions/workflows/ci.yml/badge.svg?branch=main&event=push)](https://github.com/SUNHAOJUN22/AspenOps-Agent/actions/workflows/ci.yml?query=branch%3Amain+event%3Apush)
[![Windows main push](https://github.com/SUNHAOJUN22/AspenOps-Agent/actions/workflows/windows-control-plane.yml/badge.svg?branch=main&event=push)](https://github.com/SUNHAOJUN22/AspenOps-Agent/actions/workflows/windows-control-plane.yml?query=branch%3Amain+event%3Apush)
![Python](https://img.shields.io/badge/Python-3.11--3.13-3776AB)
![Version](https://img.shields.io/badge/version-2.0.0-111827)
![License](https://img.shields.io/badge/license-Apache--2.0-0F766E)

</div>

![AspenOps architecture](docs/assets/readme/hero-architecture.svg)

> This README uses twenty-three original AI-generated SVG capability diagrams. They describe implemented contracts and explicitly labelled planned work; Mock, Fake COM, software tests, portable performance, signatures, compatibility checks and integrity hashes are never presented as licensed Aspen engineering certification.


<!-- AI_VISUAL_GALLERY:START -->

## AI visual atlas

The twelve diagrams below provide a fast visual index. The complete README references twenty-three original, AI-assisted, self-contained SVG assets.

| Process intent and compilation | Execution isolation and validity | Scheduling, cache and evidence |
|---|---|---|
| ![Agent pipeline](docs/assets/readme/agent-pipeline.svg) | ![COM isolation](docs/assets/readme/com-isolation.svg) | ![Scheduler lifecycle](docs/assets/readme/scheduler-lifecycle.svg) |
| ![Process intent IR](docs/assets/readme/process-intent-ir.svg) | ![Validity gates](docs/assets/readme/validity-gates.svg) | ![Cache singleflight](docs/assets/readme/cache-singleflight.svg) |
| ![Backend capabilities](docs/assets/readme/backend-capabilities.svg) | ![Worker ownership](docs/assets/readme/worker-ownership-recycle.svg) | ![Evidence chain](docs/assets/readme/evidence-chain.svg) |
| ![Policy and paths](docs/assets/readme/policy-path-safety.svg) | ![Optimization lifecycle](docs/assets/readme/optimization-lifecycle.svg) | ![Licensed certification](docs/assets/readme/licensed-certification.svg) |

> These visuals explain software contracts only. Flowsheets, signatures, hashes, Mock, Fake COM and public CI do not replace licensed Aspen engineering validation.

<!-- AI_VISUAL_GALLERY:END -->

---

## Authoritative status

| Item | Status |
|---|---|
| Default and only long-lived branch | `main` |
| Package | `aspenops-nexus 2.0.0` |
| Phase 0–1 | Execution identity and governed design contracts implemented |
| Phase 2 | Offline simulator compilation contracts only |
| Phase 3–7 | Signed qualification and revocation controls implemented |
| Native new-flowsheet builder | **Not implemented for production scope** |
| Licensed Aspen status | `PENDING_REAL_ASPEN_CERTIFICATION` |

<!-- MAIN_SINGLE_BRANCH_QUALIFICATION:START -->

### Latest single-main automated qualification

- Validated source commit: `0214fe417735c6162fd6f4317b2f0fc645cad552`;
- Linux CI: `30992536823`; Windows: `30992536823`;
- Python 3.11: 1207 passed; 95.27% branch coverage;
- Python 3.12: 1207 passed; 95.27% branch coverage;
- Python 3.13: 1207 passed; 95.27% branch coverage;
- Python 3.12 reverse and fixed-seed order gates passed;
- Real Aspen/HYSYS: `PENDING_REAL_ASPEN_CERTIFICATION`.

<!-- MAIN_SINGLE_BRANCH_QUALIFICATION:END -->

Archived validated baseline evidence proves only the cited source commit and Actions runs. It is not an automatic claim about arbitrary later commits.
Public CI validates software contracts; it does not certify a commercial Aspen installation, property method, equipment selection, flowsheet or engineering result.

---

## Product position

AspenOps is not a wrapper that lets a model emit arbitrary COM scripts. It connects Aspen Plus, Aspen HYSYS, CLI, Python and AI agents to one deterministic control plane:

- agents submit semantic variables or validated `aspenops.flowsheet/v1`;
- each real Automation Server belongs to an isolated Windows child process and STA apartment;
- every Worker uses a private model copy;
- concurrency is bounded by licence slots, resource budgets and lifecycle policy;
- communication, engine return, convergence, constraints, balances and human approval remain independent gates;
- non-finite values, invalid Boolean protocols and non-serializable diagnostics cannot silently become valid evidence;
- accepted results bind request, model, registry, commit and evidence hashes;
- DWSIM, IDAES, Modelica/FMI and automatic flowsheet compilers remain `planned`; unavailable execution fails closed.

---

## Native adapter conformance gate

![Native adapter conformance gate](docs/assets/readme/adapter-conformance.svg)

Before any native write, the executor now requires a strict
`aspenops.native-adapter-manifest/v1`. The conformance gate binds the profile, adapter
contract, code hash and runtime identity, then proves coverage of every operation and
`adapter_key` required by the base compilation plan. Missing topology readback, layout
readback, save/reopen or failure-isolation capabilities fail closed before the first plan
step instead of being discovered after a commercial case has been partially mutated.

The native execution record binds both the manifest digest and the conformance-report
digest. This remains an offline contract gate: vendor objects, ports, save/reopen fidelity
and solver behavior still require licensed Windows Golden Cases and human engineering
review.

---

## Quick start

Requirements: Python 3.11–3.13 and `uv >= 0.11.16`.

```bash
git clone https://github.com/SUNHAOJUN22/AspenOps-Agent.git
cd AspenOps-Agent

uv lock --check
uv sync --frozen --extra dev --extra agent --extra signing

uv run aspenops --version
uv run aspenops demo
uv run aspenops dry-run examples/batch-request.example.json
```

Add `--extra windows` for real Windows backends:

```powershell
uv sync --frozen --extra windows --extra dev --extra agent --extra signing
uv run aspenops doctor --probe
```

The first run defaults to Mock. Mock is portable software evidence, not Aspen Plus/HYSYS physical evidence.

When installing the `agent` extra outside the repository, Wheel metadata constrains the MCP Python SDK to the supported 1.x line:

```bash
python -m pip install "aspenops-nexus[agent]"
python -m pip show mcp
```

Valid range:

```text
mcp>=1.9,<2
```

---

## Configuration boundaries

Portable defaults come from `.env.example`:

```dotenv
ASPENOPS_BACKEND=mock
ASPENOPS_MODE=default
ASPENOPS_ALLOWED_ROOTS=
ASPENOPS_STATE_DIR=var/aspenops-state
ASPENOPS_LICENSE_SLOTS=1
ASPENOPS_MAX_WORKERS=1
ASPENOPS_MAX_RESIDENT_CASES=2
```

Real Aspen requires absolute allowed roots and a state directory inside them:

```dotenv
ASPENOPS_BACKEND=aspen_plus
ASPENOPS_ALLOWED_ROOTS=C:/AspenModels;C:/AspenResults
ASPENOPS_STATE_DIR=C:/AspenResults/aspenops-state
```

Rules:

1. Mock may use an empty allowlist; real Aspen/HYSYS may not.
2. `..`, symlinks, Windows junctions and realpath escapes are rejected.
3. `ASPENOPS_LICENSE_SLOTS` and `ASPENOPS_MAX_WORKERS` jointly bound concurrency.
4. Duplicate `.env` variables, unbalanced quotes and potential secret echoing are rejected.
5. Environment loading and direct Python `Settings(...)` construction share one fail-closed boundary.
6. Unknown backend/mode values, truthy string booleans, non-finite numbers, zero/negative budgets and non-`Path` arguments are rejected during construction.
7. Private keys, tokens, licence secrets, customer model paths and production data do not belong in the repository.

See [Windows Setup](docs/windows-setup.md).

---

## Configuration and path safety

![Configuration and path safety](docs/assets/readme/policy-path-safety.svg)

```text
environment or Python API
→ backend / mode / Boolean / budget validation
→ real backend absolute-root validation
→ expanduser + resolve
→ relative_to approved root
→ readonly / default / enhanced operation gate
```

Truthy strings such as `visible="false"` and `cache_failures="false"` are not accepted as booleans. A real backend without approved roots, with an escaping state directory, or with an output path outside policy fails before Worker, COM or evidence creation.

---

## Industrial safety invariants

![Windows COM process isolation](docs/assets/readme/com-isolation.svg)

1. One COM object belongs to one Windows child process and one STA apartment.
2. Agents cannot construct arbitrary Aspen Tree Paths or execute arbitrary Python, Shell or VBA.
3. Workers use private model copies; hard timeout kills only an AspenOps-owned process.
4. Cache identity binds runtime, backend, model, registry and physical request.
5. Failed writes roll back; tainted Workers are recycled.
6. Mock, Fake COM, public Windows tests and signatures cannot self-grant engineering certification.

---

## Independent validity gates

![Independent simulation validity gates](docs/assets/readme/validity-gates.svg)

```text
communication_ok
AND engine_ok
AND converged
AND feasible
AND constraints_passed
AND balances_passed
AND finite_json_evidence
```

`NaN`, positive or negative Infinity, non-numeric values and derived arithmetic overflow fail closed with `constraint_non_finite`, `balance_non_finite` and related structured codes. Results remain JSON-safe under `allow_nan=False`. Aspen Plus and HYSYS running state accepts explicit booleans, COM `-1/0/1` and supported strings; it never relies on `bool("False")` truthiness.

---

## Process Intent IR

![Process Intent IR](docs/assets/readme/process-intent-ir.svg)

The simulator-neutral representation is:

```text
aspenops.flowsheet/v1
```

It models components, property methods, equipment, ports, streams, parameters and safe metadata. It provides deterministic ordering, canonical JSON, SHA-256 graph identity, connection checks, cycle policy and quantity budgets, and rejects `code`, `script`, `shell`, `python`, `vba`, `command` and raw Tree Paths.

```bash
uv run python scripts/validate_process_ir.py \
  examples/process-intent.example.json \
  --canonical-output var/ci/process-intent-canonical.json \
  --report-output var/ci/process-intent-report.json

uv run python scripts/render_process_ir_dashboard.py \
  --input var/ci/process-intent-report.json \
  --output-html var/ci/process-ir-dashboard.html \
  --output-svg var/ci/process-ir-dashboard.svg
```

`process-ir-dashboard.html` presents issue, backend-capability and Agent-pipeline views. DWSIM, IDAES, Modelica and automatic Aspen/HYSYS flowsheet compilers remain planned and not implemented.

---

## CLI, Python and MCP

![Unified CLI, Python and MCP surface](docs/assets/readme/cli-mcp-workflow.svg)

| Surface | Main use | Boundary |
|---|---|---|
| CLI | demos, diagnostics, batches, scheduling, optimization and certification | parameterized commands, no arbitrary code |
| Python | embedded batch, scheduler, optimization and evidence workflows | same policy and data models |
| MCP | Agent discovery, planning, submission, query and verification | exactly 14 narrow tools, no arbitrary Shell/COM/Tree Path |

Primary commands:

```text
demo
doctor
dry-run
run-batch
submit
job
cancel
scheduler
benchmark
optimize
certify
certification-preflight
certify-licensed
verify-licensed-bundle
verify-bundle
mcp
```

---

## MCP compatibility and server lifecycle

![MCP compatibility and Scheduler lifecycle](docs/assets/readme/mcp-runtime-lifecycle.svg)

Project metadata and built Wheel `Requires-Dist` require `mcp>=1.9,<2`; the frozen environment resolves `mcp 1.28.1`. Runtime validates the SDK before importing `FastMCP`, and built Wheel METADATA is parsed again so `<20` cannot masquerade as `<2`.

```text
server startup → scheduler.start()
serve 14 constrained tools
server shutdown → scheduler.stop() → Worker / PoolManager cleanup
```

MCP `list_recent_jobs` no longer calls the compatibility N+1 `JobStore.list_recent()` method. It uses one governed connection and one indexed SELECT over public job fields, without selecting request bodies. Creation, claim, heartbeat, retry, cancellation, recovery and idempotent result transactions remain unchanged.

---

## Common workflows

### 1. Validate before executing a batch

```bash
uv run aspenops dry-run examples/batch-request.example.json
uv run aspenops run-batch examples/batch-request.example.json \
  --output var/aspenops-state/results.json \
  --bundle var/aspenops-state/run-bundle.zip
```

### 2. Run durable background work

Terminal 1:

```bash
uv run aspenops scheduler
```

Terminal 2:

```bash
JOB_ID=$(
  uv run aspenops submit examples/batch-request.example.json |
  python -c 'import json,sys; print(json.load(sys.stdin)["job_id"])'
)
uv run aspenops job "$JOB_ID"
uv run aspenops cancel "$JOB_ID" --grace-s 2
```

### 3. Run budgeted constrained optimization

```bash
uv run aspenops optimize examples/optimization-request.example.json \
  --output var/aspenops-state/optimization-result.json
```

### 4. Verify an evidence bundle

```bash
uv run aspenops verify-bundle var/aspenops-state/run-bundle.zip
```

### 5. Start the local MCP stdio server

```bash
uv run aspenops mcp
```

---

## Constrained optimization lifecycle

![Constrained optimization lifecycle](docs/assets/readme/optimization-lifecycle.svg)

```text
validate mixed variables and objectives
→ enforce finite optimization budget
→ seeded differential-evolution batches
→ CasePool / Worker evaluation
→ communication + convergence + constraints + balances
→ atomic checkpoint + cancellation
→ best candidate + Pareto evidence
```

DE retains one batch evaluation per generation and the same evaluation budget while avoiding a full exclusion list for every target. Pareto calculation performs ordered exact deduplication, filters infeasible points when feasible points exist, and retains minimum violation when all points are infeasible. Mock output is `control-plane-only`; real Aspen output remains `licensed-runtime-pending-engineering-review` and `PENDING_REAL_ASPEN_CERTIFICATION`.

---

## Cross-process path pinning

![Durable queue path portability](docs/assets/readme/durable-path-portability.svg)

```text
submission working directory
→ resolve model_path and registry_path
→ pin absolute identities
→ persist in SQLite
→ scheduler may run from another directory
```

CLI submission reports:

```text
paths_pinned = true
submission_cwd = absolute submission directory
```

Real backends reapply allowed-root and realpath policy. Direct callers of low-level `BackgroundScheduler.submit()` should pass absolute paths or call `pin_durable_request_paths()` first.

---

## Scheduling and recovery

![Durable scheduler lifecycle](docs/assets/readme/scheduler-lifecycle.svg)

```text
validate
→ persist pending
→ claim lease
→ heartbeat running
→ isolated Worker
→ atomic completed / failed / cancelled
```

- expired leases with attempts remaining enter `retry_wait`;
- exhausted attempts enter `dead_letter`;
- cancellation requested during recovery enters `cancelled`;
- cancellation may terminate only the verified owned Worker;
- final state and evidence commit atomically.

---

## Cache, batch deduplication and singleflight

![Cache, batch deduplication and singleflight](docs/assets/readme/cache-singleflight.svg)

```text
canonical physical identity
→ memory LRU / SQLite WAL lookup
→ same-batch duplicate collapse
→ concurrent single-point leader + followers
→ one governed solver call
→ computed / persistent_cache / inflight_singleflight provenance
```

Cache identity binds runtime schema, package version, backend, stable runtime identity, model SHA-256, registry SHA-256 and physical request identity. Hit threshold accounting is O(1), key chunks respect the SQLite parameter budget, persistent JSON is compact, and bounded `PRAGMA optimize` runs after schema initialization.

The same immutable request object reuses cache-key work inside one batch; one cacheable solve result produces one canonical dictionary. Same-batch and singleflight results use deep clones to preserve nested isolation. The memory LRU keeps compact JSON snapshots: duplicate keys in one `get_many` call decode once, memory hits open no SQLite connection, and C JSON decoding provides independent nested values across calls. A structured-object zero-decode candidate using generic `deepcopy` was measured and rolled back.

---

## Worker ownership and recycling

![Worker ownership and recycling](docs/assets/readme/worker-ownership-recycle.svg)

```text
source model
→ private worker-generation copy
→ spawned child process + one simulator owner
→ correlated IPC request
→ hard deadline and ownership supervision
→ graceful close or verified recycle
```

Recycle reasons include timeout, crash, protocol error, tainted write, point budget, worker age, cancellation and lease ownership loss. Recycling applies only to an AspenOps-owned Worker or supervised descendant. The source model is never overwritten.

---

## Performance engineering and evidence

![Performance hotspot and evidence map](docs/assets/readme/performance-hotspot-map.svg)

![Cold and warm startup evidence](docs/assets/readme/cold-warm-startup.svg)

AspenOps separates performance evidence into:

1. **low-noise hard contracts**: cache-key, solver, serialization, dedup, cache flush, JSON clone, SQLite connection/SELECT and Pareto dominance counts;
2. **environment-sensitive diagnostics**: wall time, median, P95, min/max, CV, Python `-X importtime`, cProfile, tracemalloc and RSS.

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

`measure_cli_startup.py` automatically emits three colocated artifacts:

```text
cli-startup.json
operation-counts.json
job-store-query-plan.json
```

Current deterministic contracts:

```text
100 identical request references
→ 1 cache key
→ 1 solver call
→ 1 canonical serialization
→ 99 same_batch_dedup results

1024 cache hits
→ pending_hit_total == 0

3 memory hits across 2 calls
→ 2 compact JSON decodes
→ 0 SQLite connections
→ deep nested isolation

1000 identical Pareto points
→ 0 dominance calls

1000 durable jobs, limit 20
→ 1 connection
→ 1 SELECT
→ idx_jobs_recent_created_job
→ no USE TEMP B-TREE
```

Shared-runner wall time remains evidence, not a narrow hard threshold. Historical benchmark files are archived portable Mock orchestration evidence and do not automatically represent the current HEAD or licensed Aspen solve speed. Model and registry SHA-256 remain content-derived; no mtime/size shortcut is used. See [Performance Audit V2](docs/performance-audit-2026-07-27-v2.md).

---

## Industrial use cases

![Industrial use cases](docs/assets/readme/industrial-scenarios.svg)

| Use case | AspenOps can | It cannot replace |
|---|---|---|
| Parameter sweeps | evaluate bounded semantic temperature, pressure, flow and reflux changes | engineer-approved operating ranges |
| Constrained optimization | report feasibility and Pareto evidence within a budget | equipment, control and safety review |
| Regression and qualification | compare baseline/candidate repeatability and tolerances | a licensed simulator and physical certification |
| Operating decision support | perform what-if analysis on an approved model | production DCS control or automatic closed-loop writes |

AspenOps does not connect to or write a production DCS. It produces governed simulation evidence for qualified human decisions.

---

## Layered chemical-engineering agents

![Layered chemical-engineering agents](docs/assets/readme/agent-pipeline.svg)

```text
Knowledge
→ Concept
→ Parameter
→ Execution
→ Repair
→ Physics / Engineering Review
```

Knowledge is read-only; Concept and Parameter output validated IR only; Execution calls declared available backends; Repair has round, time and solve budgets; Review independently checks physics, convergence, constraints, balances and human approval.

---

## Multi-simulator capability declarations

![Multi-simulator capability matrix](docs/assets/readme/backend-capabilities.svg)

| Backend | Current execution | IR compiler | Current boundary |
|---|---|---|---|
| Mock | available | planned | portable software evidence, not Aspen physics |
| Aspen Plus | available on licensed Windows | planned | approved existing models; strict engine-running parsing |
| HYSYS | available on licensed Windows | planned | approved existing models; strict solver-running parsing |
| DWSIM | planned | planned | **not implemented, no adapter** |
| IDAES | planned | planned | **not implemented, no adapter** |
| Modelica/FMI | planned | planned | **not implemented, no adapter** |

**planned is not implemented; compiler is not executor; signature is not engineering approval.**

---

## Automated tests and quality gates

![Automated test matrix](docs/assets/readme/test-matrix.svg)

Four authoritative workflows:

| Workflow | Pinned environment | Purpose |
|---|---|---|
| `ci.yml` | `ubuntu-24.04`; Python 3.11/3.12/3.13 | Ruff, format, strict mypy, six dependency audits, full tests, branch coverage, build, Wheel, Mock, MCP, IR, configuration, cache, optimization, performance evidence and durable queue smoke |
| `windows-control-plane.yml` | `windows-2025`; Python 3.12 | Windows Job, IPC, Fake Aspen/HYSYS, PowerShell, configuration, path, low-noise performance, IR and governance contracts |
| `generate-performance-evidence.yml` | `ubuntu-24.04`; Python 3.12 | trusted baseline/candidate, two frozen environments and stable regression evidence |
| `licensed-aspen-certification.yml` | `ubuntu-24.04` guard → licensed Windows | main guard, SHA binding, Mock/IR/performance software gate, evidence isolation and real COM |

Frozen dependency auditing covers Linux and Windows across Python 3.11, 3.12 and 3.13: six combinations. Hosted runners, third-party Actions and `uv 0.11.16` are pinned; permissions remain `contents: read`.

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
uv run python scripts/check_mcp.py
uv run python scripts/validate_process_ir.py examples/process-intent.example.json
uv run aspenops demo
```

Artifact names include both `github.run_id` and `github.run_attempt`. Current-job evidence is written under `$RUNNER_TEMP` and uploaded through `${{ runner.temp }}` with `if-no-files-found: error`. Missing JUnit or early termination reports `INCOMPLETE`; a failure or error reports `FAIL`.

Test visualization is generated by `scripts/render_test_dashboard.py`; governed outputs include `test-dashboard-quality.html`, `test-dashboard-windows.html` and `test-dashboard-licensed.html`.

---

## Reproducible evidence

![Reproducible evidence chain](docs/assets/readme/evidence-chain.svg)

```text
validated intent
→ exact trusted main SHA
→ isolated Worker execution
→ convergence / feasibility / balances
→ run_id + run_attempt artifact
→ hashes and optional signature
→ qualified human acceptance
```

Performance dispatch first verifies `GITHUB_REF == refs/heads/main`. A non-main dispatch writes `dispatch-ref.txt` and `dispatch-guard.log`, then **fails explicitly with exit code 2** instead of becoming all-skipped. `actions/checkout` reads the trusted workflow revision; candidate and baseline use `--end-of-options`, ancestry checks and verified detached checkout.

Default performance baseline:

```text
ebef32ee1f2be74df5d5c5489e7ca86d35ac7bb2
```

Mock performance measures orchestration only, not real Aspen solve speed.

---

## Evidence bundle integrity and authenticity

![Evidence bundle integrity and authenticity](docs/assets/readme/evidence-integrity.svg)

`write_run_bundle()` writes `request.json`, `results.json` and `environment.json` under `allow_nan=False`. The manifest binds request, result, model and registry hashes, runtime schema/version, plus each member's SHA-256 and size.

```text
bounded ZIP structure
→ exact required members
→ member size + SHA-256 declarations
→ request / result / model / registry hashes
→ optional Ed25519 manifest signature
→ trusted-key verification
```

An unsigned bundle provides internal integrity only. Ed25519 provides origin authenticity only when the public key is trusted. Hashes, signatures and software PASS do not prove property-method, kinetic or flowsheet validity. Reusing canonical hash bytes as archive members remains INCONCLUSIVE because current-HEAD CPU/size evidence does not yet justify changing the readable member-byte contract.

---

## Licensed Aspen certification

![Licensed certification flow](docs/assets/readme/licensed-certification.svg)

Key contracts:

1. A pinned `ubuntu-24.04` guard requires `refs/heads/main`.
2. `expected_head_sha` must equal the dispatched `GITHUB_SHA`.
3. Initial `actions/checkout` must match that SHA, followed by a verified detached checkout.
4. Before checkout, create `$RUNNER_TEMP/aspenops-licensed-artifact-<GITHUB_RUN_ID>-<GITHUB_RUN_ATTEMPT>`.
5. `run-metadata.txt` records run, ref, SHA and approving identity.
6. Mock JUnit, dashboard, evidence copies and final `job_status` remain in this run's runner-temp directory.
7. Real execution uses `LICENSED_EVIDENCE_DIR=ASPENOPS_STATE_DIR/licensed-certification/<GITHUB_RUN_ID>-<GITHUB_RUN_ATTEMPT>`.
8. The fixed `licensed-aspen-certification` concurrency group runs serially.
9. Upload reads only `${{ runner.temp }}`, includes `github.run_attempt`, and uses `if-no-files-found: error`.

Software can only report:

```text
PENDING_REAL_ASPEN_CERTIFICATION
```

Real certification still requires licensed Windows, an available licence seat, an approved model, signing material and qualified process-engineering acceptance.

---

## Repository structure

```text
.github/workflows/       four authoritative automation workflows
docs/                    architecture, Windows, performance, certification and quality docs
docs/assets/readme/      twenty-three test-governed README SVGs
examples/                batch, optimization and Process Intent examples
scripts/                 validators, dashboards, benchmarks, performance probes and Windows setup
src/aspenops_nexus/      control plane, backends, Workers, scheduler, cache, optimization, evidence and MCP
tests/                   Linux, Windows, workflow, documentation, security and performance contracts
var/                     reproducible baselines, audit inventory and local state
```

---

## Troubleshooting

| Symptom | Check first | Principle |
|---|---|---|
| `doctor --probe` is not ready | Python bitness, COM ProgID, licence and allowed roots | do not bypass preflight or hard-code raw COM |
| direct `Settings(...)` construction fails | backend, mode, Boolean fields, budgets and `Path` types | correct the input; do not bypass construction validation |
| a path is rejected | `ASPENOPS_ALLOWED_ROOTS` and realpath | place model, registry, state and output inside approved absolute roots |
| scheduler starts elsewhere after submission | `paths_pinned` and `submission_cwd` | resubmit with the current version; durable paths should be absolute |
| MCP reports an incompatible SDK major | `python -m pip show mcp` | install `mcp>=1.9,<2`; do not bypass the gate |
| Workers remain after MCP shutdown | lifespan, Scheduler stop and process ownership | shutdown must call `scheduler.stop()` |
| a batch returns `ok=false` | communication, engine, convergence, constraints and balances | diagnose each gate; Run2 return is not convergence |
| `constraint_non_finite` appears | node value, unit conversion and derived overflow | fix the model or scale; do not relax the gate |
| `balance_non_finite` appears | terms, coefficients, units and residuals | use structured diagnostics |
| startup evidence is noisy | `coefficient_of_variation`, runner, Python and CPU | treat wall time as environment evidence; rely on import and operation-count contracts |
| an operation count changes | cache-key, solver, serialization, dedup, SQL or Pareto path | treat it as a deterministic regression; do not hide it with reruns |
| recent jobs use a temporary sort | `job-store-query-plan.json` and index inventory | require `idx_jobs_recent_created_job`; reject `USE TEMP B-TREE` |
| a job remains `pending` | whether `aspenops scheduler` is running | start the durable service |
| a background job remains running | lease, heartbeat, Worker PID and cancellation deadline | let Scheduler recover owned work; do not kill an unknown simulator |
| cached output looks wrong | cache key, model/registry hashes and corrupt records | corrupt records are discarded and recomputed |
| dashboard reports `INCOMPLETE` | whether this job produced JUnit/coverage | never reuse old evidence or treat missing evidence as PASS |
| README SVG does not render | filename case, XML, fonts and resource-safety tests | use repository-local self-contained SVGs without embedded CJK text |
| licensed workflow does not run | ref, `expected_head_sha`, environment approval and runner labels | execute only on protected `main` and the licensed host |

---

## Roadmap

![AspenOps roadmap](docs/assets/readme/roadmap.svg)

### Implemented

- Process Intent IR, strict validation, canonical JSON and SHA-256 graph identity;
- existing-model Aspen Plus/HYSYS control plane;
- one fail-closed Settings and path policy for environment and Python API construction;
- independent communication, engine, convergence, constraint, balance and finite-evidence gates;
- Mock, Fake COM, Windows Job Object, durable scheduling, cancellation, cache, singleflight, optimization and MCP;
- lightweight CLI bootstrap plus operation-count, import-time, cProfile, memory and SQLite query-plan evidence;
- MCP recent-jobs reads using one connection, one SELECT and a persistent ordering index;
- MCP 1.x dependency/Wheel/runtime gates and FastMCP lifecycle cleanup;
- frozen CI, dashboards, evidence bundles and licensed-certification boundaries.

### Next

- migrate the compatibility Python `JobStore.list_recent()` method itself to the shared single-query decoder;
- add query-plan evidence for claim, cancellation-deadline and event access patterns before adding more indexes;
- IR → Mock non-executing plan compiler;
- open-source DWSIM real-process backend;
- Text/Image → IR benchmarks and data contracts;
- budgeted simulator-feedback Repair loop;
- human review and diff visualization.

### After sufficient evidence

- Aspen/HYSYS automatic flowsheet compilers;
- IDAES symbolic backend;
- Modelica/FMI co-simulation;
- PFD/sketch understanding;
- industrial model and version qualification.

No capability moves from planned to available without **code + tests + evidence**.

---

## AI-generated visual asset inventory

The following twenty-three original, self-contained SVGs live in `docs/assets/readme/`:

1. `hero-architecture.svg`
2. `policy-path-safety.svg`
3. `validity-gates.svg`
4. `process-intent-ir.svg`
5. `agent-pipeline.svg`
6. `backend-capabilities.svg`
7. `com-isolation.svg`
8. `worker-ownership-recycle.svg`
9. `cli-mcp-workflow.svg`
10. `mcp-runtime-lifecycle.svg`
11. `optimization-lifecycle.svg`
12. `durable-path-portability.svg`
13. `scheduler-lifecycle.svg`
14. `cache-singleflight.svg`
15. `performance-hotspot-map.svg`
16. `cold-warm-startup.svg`
17. `industrial-scenarios.svg`
18. `test-matrix.svg`
19. `evidence-chain.svg`
20. `evidence-integrity.svg`
21. `licensed-certification.svg`
22. `roadmap.svg`

`tests/test_readme_visual_assets.py` checks bilingual references, the exact inventory, XML, size, path safety, accessibility, renderer portability, scripts, events, remote resources, Data URIs, source-capability binding and integration with all three software gates.

---

## Documentation, contribution and security boundary

- [Architecture](docs/architecture.md)
- [Process Intent IR](docs/process-intent-ir.md)
- [External Agent Integration](docs/external-agent-integration.md)
- [Windows Setup](docs/windows-setup.md)
- [Performance](docs/performance.md)
- [Performance Audit V1](docs/performance-audit-2026-07-27.md)
- [Performance Audit V2](docs/performance-audit-2026-07-27-v2.md)
- [Certification](docs/certification.md)
- [Test Audit](docs/automated-test-audit-2026-07-22.md)
- [Quality Report](docs/quality-report.md)
- [Contributing](CONTRIBUTING.md)
- [Security](SECURITY.md)

Automation does not prove that every Aspen version starts, every model converges, or any property, reaction, equipment or control assumption is physically correct. The code is Apache-2.0; do not commit customer models, proprietary property/kinetic data, production DCS data, licences, private keys, tokens, internal hosts or commercial evidence bundles.
