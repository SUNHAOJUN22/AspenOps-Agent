<div align="center">

# AspenOps 2.0

## Deterministic engineering control plane for Aspen Plus, Aspen HYSYS, and AI agents

**Governed requirement → typed process intent → engineering rules → verified compilation → isolated execution → engineering gates → auditable evidence → deterministic delivery**

[中文](README.md) · [Final Acceptance](README_ACCEPTANCE.md) · [Architecture](docs/architecture.md) · [Delivery Acceptance](docs/delivery-acceptance.md) · [Delivery Bundle](docs/delivery-bundle.md) · [Windows Setup](docs/windows-setup.md) · [Certification](docs/certification.md) · [Quality Report](docs/quality-report.md)

![version-2.0.0-delivery](https://img.shields.io/badge/version-2.0.0-111827)
![Python](https://img.shields.io/badge/Python-3.11--3.13-3776AB)
![Platforms](https://img.shields.io/badge/platforms-Windows%20%7C%20Linux-2563EB)
![License](https://img.shields.io/badge/license-Apache--2.0-0F766E)

</div>

![AspenOps final acceptance architecture](docs/assets/acceptance/final-acceptance-map.svg)

> **Qualification boundary:** `aspenops-nexus 2.0.0` can qualify the software control plane, process intent, isolated execution, cache, scheduler, optimization, evidence chain, and deterministic delivery. Without a real commercial solver, license, fixed model, Golden Case, hardware fingerprint, engineering tolerances, and signed review, it cannot self-certify Aspen engineering performance. External status remains `PENDING_REAL_ASPEN_CERTIFICATION`.

## Acceptance status

| Item | Delivery contract |
|---|---|
| Authoritative long-lived branch | `main` |
| Qualified platforms | Linux and Windows; real Aspen COM remains licensed-Windows only |
| Python | Python 3.11, 3.12 and 3.13 across six Linux/Windows software combinations |
| Archived qualification | `1224 passed`, zero failures, 95.03% branch coverage |
| Current runtime regression | 1247+ tests and 95.03% branch coverage; latest `main` CI is authoritative |
| Lock and package boundary | `uv 0.11.16`, `uv lock --check`, `mcp>=1.9,<2` |
| External-engine qualification | `PENDING_REAL_ASPEN_CERTIFICATION` |

The published result is an **archived validated baseline**, not an automatic claim for arbitrary later commits. Every changed tree must pass the permanent read-only workflows again; a historical PASS cannot override a new failure.

## AI-assisted visual system

The following twenty-three repository-owned SVGs describe implemented software contracts. They do not depend on external image hosting and are not flowsheet data, Golden Cases, experimental evidence, or proof of commercial-solver execution.

| Architecture and intent | Execution and safety | Evidence and engineering |
|---|---|---|
| ![hero architecture](docs/assets/readme/hero-architecture.svg) | ![agent pipeline](docs/assets/readme/agent-pipeline.svg) | ![process intent](docs/assets/readme/process-intent-ir.svg) |
| ![backend capabilities](docs/assets/readme/backend-capabilities.svg) | ![adapter conformance](docs/assets/readme/adapter-conformance.svg) | ![COM isolation](docs/assets/readme/com-isolation.svg) |
| ![worker recycle](docs/assets/readme/worker-ownership-recycle.svg) | ![validity gates](docs/assets/readme/validity-gates.svg) | ![optimization lifecycle](docs/assets/readme/optimization-lifecycle.svg) |
| ![scheduler lifecycle](docs/assets/readme/scheduler-lifecycle.svg) | ![durable paths](docs/assets/readme/durable-path-portability.svg) | ![cache singleflight](docs/assets/readme/cache-singleflight.svg) |
| ![evidence chain](docs/assets/readme/evidence-chain.svg) | ![evidence integrity](docs/assets/readme/evidence-integrity.svg) | ![licensed certification](docs/assets/readme/licensed-certification.svg) |
| ![CLI MCP workflow](docs/assets/readme/cli-mcp-workflow.svg) | ![MCP lifecycle](docs/assets/readme/mcp-runtime-lifecycle.svg) | ![path safety](docs/assets/readme/policy-path-safety.svg) |
| ![performance hotspot](docs/assets/readme/performance-hotspot-map.svg) | ![cold warm startup](docs/assets/readme/cold-warm-startup.svg) | ![test matrix](docs/assets/readme/test-matrix.svg) |
| ![industrial scenarios](docs/assets/readme/industrial-scenarios.svg) | ![roadmap](docs/assets/readme/roadmap.svg) |  |

## System position

AspenOps is not a loose wrapper that lets an LLM emit arbitrary COM, VBA, or Python. It compiles human or agent intent into validated contracts:

```text
Human / Agent
  → ProcessRequirementDocument
  → ProcessDesignIR / aspenops.flowsheet/v1
  → engineering rules + units + degrees of freedom
  → simulator capability profile
  → compilation / evaluation plan
  → CasePool / scheduler / optimizer
  → isolated Windows Worker + owned COM session
  → Aspen Plus / HYSYS / Mock
  → readback + convergence + constraints + balances
  → evidence bundle + deterministic handover
```

DWSIM and IDAES remain `planned`; there is currently **no adapter** for either engine. The `aspenops.flowsheet/v1` contract reports unavailable capabilities explicitly instead of treating product awareness as executable support.

## Mathematical and engineering contracts

### 1. Component material balance

For component \(i\):

\[
\frac{dN_i}{dt}=\sum_{s\in\mathcal I}\dot n_{i,s}
-\sum_{s\in\mathcal O}\dot n_{i,s}
+\sum_{r\in\mathcal R}\nu_{i,r}r_rV.
\]

Steady residual:

\[
R_i=\sum_s\dot n_{i,s}^{in}-\sum_s\dot n_{i,s}^{out}
+\sum_r\nu_{ir}r_rV,
\qquad |R_i|\le\tau_i.
\]

A non-finite balance produces `balance_non_finite`; a finite residual outside tolerance produces `balance_failed`. A zero exit code, COM response, or cache hit cannot replace the balance gate.

### 2. Energy balance

\[
\frac{dU}{dt}=\dot Q-\dot W
+\sum_{s\in\mathcal I}\dot n_s\hat h_s
-\sum_{s\in\mathcal O}\dot n_s\hat h_s.
\]

A real project still requires approved enthalpy references, phase equilibrium, reaction heats, heat losses, shaft work, and equipment models.

### 3. Independent validity gates

\[
OK=C_{comm}\land C_{engine}\land C_{conv}\land C_{finite}
\land C_{constraint}\land C_{balance}.
\]

Constraint violation:

\[
V(x)=\sum_j\max(0,g_j(x)-\varepsilon_j)
+\sum_k\max(0,|h_k(x)|-\varepsilon_k).
\]

`NaN`, `Infinity`, numeric-looking strings, and Boolean numeric aliases fail closed. Non-finite constraints use `constraint_non_finite`. Evidence JSON is serialized with `allow_nan=False`.

### 4. Unit and affine conversion

\[
x_t=(x_s+a_s)\frac{m_s}{m_t}-a_t,
\qquad T_K>0.
\]

Parameter contracts validate finite type, dimension, integer semantics, fraction ranges, and positive-domain constraints.

### 5. Recycle graph and tear edges

For a directed graph \(G=(V,E)\) and tear-edge set \(T\):

\[
\forall C\in cycles(G),\qquad C\cap T\neq\varnothing.
\]

A tear edge must belong to an actual cycle; declaring a generic recycle cannot suppress unrelated topology defects.

### 6. Distillation degrees of freedom

\[
DOF=N_c-N_s.
\]

\(N_c\) is the number of independent manipulated variables and \(N_s\) the number of independent specifications. Capability profiles and engineering rules must agree to prevent under- or over-specification.

### 7. Cache identity

\[
K=SHA256(schema\Vert version\Vert backend\Vert runtime
\Vert model\Vert registry\Vert request_{physical}).
\]

Presentation metadata does not change physical identity. Model, registry, backend, runtime, or validation-semantics changes must change the cache key.

### 8. Warm-start trajectory

\[
x_{k+1}=F(x_k,u_k),\qquad y_k=G(x_k).
\]

Warm start is path dependent. One trajectory is pinned to one Worker and executed serially; persistent cache, same-batch deduplication, and `inflight_singleflight` are disabled; session and step enter identity; optimization defaults to `reset_mode='reinitialize'`.

### 9. Constrained optimization

\[
\min_x J(x)=\sum_{m=1}^{M}w_m f_m(x),
\qquad J_p(x)=J(x)+\lambda V(x),\quad\lambda\ge0.
\]

Feasibility, convergence, and engineering gates precede objective ranking. A large penalty cannot hide solver failure or a non-finite result.

### 10. License-limited concurrency

\[
W_{effective}=\min(W_{configured},W_{license},W_{memory},W_{stable}).
\]

Pooled cost model:

\[
T_{pool}\approx W(T_{start}+T_{open})+
\frac{N_{unique}}{W_{effective}}(T_{solve}+T_{verify})+T_{IPC}.
\]

More processes are not automatically faster. Windows spawn, commercial licenses, memory, recycle convergence, and model stability jointly limit concurrency.

## Configuration boundaries

Permanent quality jobs use `ubuntu-24.04`; Windows control-plane and real-COM preflight use `windows-2025`. Python 3.11, 3.12 and 3.13 form six Linux and Windows software-audit combinations. Real Aspen Plus/HYSYS still requires a licensed Windows host.

```bash
git clone https://github.com/SUNHAOJUN22/AspenOps-Agent.git
cd AspenOps-Agent
uv lock --check
uv sync --frozen --extra dev --extra agent --extra signing
```

The pinned toolchain is `uv 0.11.16`; the MCP boundary is `mcp>=1.9,<2`.

## Configuration and path safety

`.env.example` defaults to Mock. Real model, registry, state, and output paths must remain inside explicit allowed roots. Durable submission pins `paths_pinned` and `submission_cwd`, preventing later reinterpretation of relative paths. Duplicate JSON keys, non-finite values, path escape, and unbalanced configuration fail closed.

## Native adapter conformance gate

A native adapter must pass manifest, input/output Schema, unit, failure-isolation, and deterministic-reference checks. Adapter PASS qualifies the software interface, not a customer model or engineering conclusion.

```bash
uv run aspenops doctor --probe
uv run python scripts/validate_process_ir.py examples/process-intent.example.json
```

The generated `process-ir-dashboard.html` visualizes the contract; it is not simulation evidence.

## Quick start

```bash
uv run aspenops demo
uv run aspenops dry-run examples/request.example.json
uv run aspenops run-batch examples/request.example.json --output var/results.json --bundle var/run-bundle.zip
uv run aspenops verify-bundle var/run-bundle.zip
```

## Independent validity gates

Each point records communication, engine, convergence, finite, constraint, and balance status independently. No aggregate score or solver success string can override a failed gate.

## Common workflows

```bash
uv run aspenops submit examples/request.example.json
JOB_ID=$(uv run aspenops submit examples/request.example.json | python -c "import json,sys; print(json.load(sys.stdin)['job_id'])")
uv run aspenops job "$JOB_ID"
uv run aspenops cancel "$JOB_ID" --grace-s 2
uv run aspenops scheduler
uv run aspenops optimize examples/optimization-request.example.json
```

## MCP compatibility and server lifecycle

```bash
uv run aspenops mcp
```

The MCP lifespan owns scheduler startup, shutdown, and exception cleanup. The MCP surface never exposes licensed Aspen certification or a bypass around explicit execution authorization.

## Constrained optimization lifecycle

The optimizer preserves evaluation budgets, atomic checkpoints, feasibility ordering, and a Pareto archive. Solver failure, non-finite objectives, or engineering-gate failure cannot be hidden by a favorable objective value.

## Scheduling and recovery

Durable states include `retry_wait` and `dead_letter`. Leases, heartbeats, cancellation deadlines, worker crashes, idempotent commits, and recovery have transaction boundaries. Warm-start trajectories remain serial on one Worker.

## Cache, batch deduplication and singleflight

Identical immutable requests may use same-batch deduplication, persistent cache, and `inflight_singleflight`. Identity binds runtime, model, registry, and physical request. Failures are not cached by default and returned objects remain deeply isolated.

## Worker ownership and recycling

Each Windows Worker owns one COM session, private model snapshot, and job scope. Point budget, age, timeout, protocol error, taint, or cancellation deadline triggers verified recycling.

## Performance engineering and evidence

```bash
uv run python scripts/measure_cli_startup.py --output var/ci/cli-startup.json
uv run python scripts/measure_operation_counts.py --output var/ci/operation-counts.json
uv run python scripts/measure_job_store_queries.py --output var/ci/job-store-query-plan.json
uv run python scripts/render_test_dashboard.py --input-dir var/ci --output-html var/ci/test-dashboard.html --output-svg var/ci/test-dashboard.svg
```

Governed artifacts are `cli-startup.json`, `operation-counts.json`, and `job-store-query-plan.json`; interpretation rules are documented in Performance Audit V2. Current-run evidence is isolated under `RUNNER_TEMP`/`${{ runner.temp }}`. Artifact names include `github.run_id` and `github.run_attempt`, so an early failure cannot publish stale files.

## Industrial use cases

The software supports batch parameter scans, constrained optimization, grade transitions, failure replay, and governed digital-twin handoff. It does not replace process engineering, HAZOP/LOPA/SIL, licensing, customer-model approval, or plant authorization.

## Evidence bundle integrity and authenticity

Permanent workflows are `ci.yml`, `windows-control-plane.yml`, `generate-performance-evidence.yml`, and `licensed-aspen-certification.yml`. Manual evidence production accepts only `refs/heads/main`; the dispatch guard runs before `actions/checkout` and **fails explicitly with exit code 2** instead of producing an all-skipped false green. Candidate and baseline revisions are then validated in `detached` worktrees.

The licensed environment requires `expected_head_sha == GITHUB_SHA` and records `GITHUB_RUN_ID`, `GITHUB_RUN_ATTEMPT`, `LICENSED_EVIDENCE_DIR`, `run-metadata.txt`, `job_status`, and `aspenops-licensed-artifact`. Uploads use `if-no-files-found: error`, live under `runner.temp`, and real Aspen tasks remain serial. Without a new licensed run and signed review, status remains `PENDING_REAL_ASPEN_CERTIFICATION`.

## Repository structure

- `src/aspenops_nexus/`: control plane, process IR, scheduler, cache, optimization, evidence, and adapters;
- `tests/`: numerical, concurrency, file-safety, documentation, artifact, and workflow contracts;
- `scripts/`: audits, performance probes, dashboards, Process IR, and delivery bundles;
- `.github/workflows/`: four permanent read-only/governed workflows;
- `docs/assets/readme/`: twenty-three deterministic SVGs.

## Troubleshooting

Run `uv run aspenops doctor --probe`, then inspect allowed roots, registry SHA, model identity, licenses, worker generation, state database, and evidence bundle. Never suppress a failing test, relax a tolerance, or reinterpret non-convergence as success.

## Final acceptance commands

```bash
python scripts/final_acceptance_preflight.py --root . --json
uv lock --check
uv sync --frozen --extra dev --extra agent --extra signing
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run python -m compileall -q src scripts
uv run python scripts/audit_source_tree.py
uv run pytest -W error::ResourceWarning --cov=aspenops_nexus --cov-branch --cov-fail-under=95.0
uv build
```

## License

Apache-2.0 covers this repository only. Aspen Plus, Aspen HYSYS, Windows, license services, customer models, and process data remain subject to their own licenses, confidentiality, and safety controls.
