<div align="center">

# AspenOps 2.0

## Deterministic engineering control plane for Aspen Plus, Aspen HYSYS and AI agents

**Governed requirements → typed flowsheet → verifiable compilation → process-isolated execution → engineering decision → auditable evidence**

[中文](README.md) · [Architecture](docs/architecture.md) · [Delivery Acceptance](docs/delivery-acceptance.md) · [Windows Setup](docs/windows-setup.md) · [Certification](docs/certification.md) · [Quality Report](docs/quality-report.md)

[![CI main push](https://github.com/SUNHAOJUN22/AspenOps-Agent/actions/workflows/ci.yml/badge.svg?branch=main&event=push)](https://github.com/SUNHAOJUN22/AspenOps-Agent/actions/workflows/ci.yml?query=branch%3Amain+event%3Apush)
[![Windows main push](https://github.com/SUNHAOJUN22/AspenOps-Agent/actions/workflows/windows-control-plane.yml/badge.svg?branch=main&event=push)](https://github.com/SUNHAOJUN22/AspenOps-Agent/actions/workflows/windows-control-plane.yml?query=branch%3Amain+event%3Apush)
![Python](https://img.shields.io/badge/Python-3.11--3.13-3776AB)
![Version](https://img.shields.io/badge/version-2.0.0-111827)
![License](https://img.shields.io/badge/license-Apache--2.0-0F766E)

</div>

![AspenOps architecture](docs/assets/readme/hero-architecture.svg)

> This README uses twenty-three governed AspenOps SVGs plus four new AI-assisted acceptance diagrams. They explain implemented software contracts or explicitly planned work only. Mock, Fake COM, hashes, signatures, public CI and offline compilation do not replace licensed Aspen engineering certification.

## Acceptance statement

| Item | Current result |
|---|---|
| Only long-lived branch | `main` |
| Package | `aspenops-nexus 2.0.0` |
| Public software qualification baseline | 1224 passed, 0 failed, 0 errors, 95.03% branch coverage |
| Order independence | reverse order PASS; seed `20260728` PASS |
| Delivery verifier | `python scripts/verify_delivery.py --output var/ci/delivery-acceptance.json` |
| Licensed Aspen/HYSYS | `PENDING_REAL_ASPEN_CERTIFICATION` |
| Arbitrary native flowsheet construction | not claimed as production capability |
| Process, safety, property and equipment approval | required from project authorities |

Machine evidence lives in `docs/ACCEPTANCE_HARDENING_QUALIFICATION.json` and permanent GitHub Actions. Archived qualification proves only its cited source and run.

## AI visual atlas

| Intent and compilation | Execution and mathematics | Evidence and delivery |
|---|---|---|
| ![hero-architecture](docs/assets/readme/hero-architecture.svg) | ![agent-pipeline](docs/assets/readme/agent-pipeline.svg) | ![process-intent-ir](docs/assets/readme/process-intent-ir.svg) |
| ![backend-capabilities](docs/assets/readme/backend-capabilities.svg) | ![adapter-conformance](docs/assets/readme/adapter-conformance.svg) | ![mathematical-contracts](docs/assets/ai/mathematical-contracts.svg) |
| ![com-isolation](docs/assets/readme/com-isolation.svg) | ![worker-ownership-recycle](docs/assets/readme/worker-ownership-recycle.svg) | ![native-failure-isolation](docs/assets/ai/native-failure-isolation.svg) |
| ![validity-gates](docs/assets/readme/validity-gates.svg) | ![warm-start-trajectory](docs/assets/ai/warm-start-trajectory.svg) | ![optimization-lifecycle](docs/assets/readme/optimization-lifecycle.svg) |
| ![scheduler-lifecycle](docs/assets/readme/scheduler-lifecycle.svg) | ![durable-path-portability](docs/assets/readme/durable-path-portability.svg) | ![cache-singleflight](docs/assets/readme/cache-singleflight.svg) |
| ![evidence-chain](docs/assets/readme/evidence-chain.svg) | ![evidence-integrity](docs/assets/readme/evidence-integrity.svg) | ![licensed-certification](docs/assets/readme/licensed-certification.svg) |
| ![cli-mcp-workflow](docs/assets/readme/cli-mcp-workflow.svg) | ![mcp-runtime-lifecycle](docs/assets/readme/mcp-runtime-lifecycle.svg) | ![policy-path-safety](docs/assets/readme/policy-path-safety.svg) |
| ![performance-hotspot-map](docs/assets/readme/performance-hotspot-map.svg) | ![cold-warm-startup](docs/assets/readme/cold-warm-startup.svg) | ![test-matrix](docs/assets/readme/test-matrix.svg) |
| ![industrial-scenarios](docs/assets/readme/industrial-scenarios.svg) | ![delivery-acceptance](docs/assets/ai/delivery-acceptance.svg) | ![roadmap](docs/assets/readme/roadmap.svg) |

---

## Product position

AspenOps is not a wrapper that lets a model emit arbitrary COM, Python, VBA or Shell. It connects agents, CLI, Python, Aspen Plus and HYSYS to one governed plane:

```text
Human / Agent
→ ProcessRequirementDocument
→ ProcessDesignIR
→ Engineering Rules
→ Capability Profile
→ Compilation Plan
→ Isolated Worker
→ Solver / Readback
→ Constraints + Balances
→ Evidence Bundle
```

Implemented software boundaries:

- semantic reads/writes, batching, cache, scheduling, optimization and evidence for approved models;
- one real simulator owner per Windows child process and COM STA;
- agent-facing semantic keys and typed documents, not arbitrary Tree Paths;
- write readback and rollback, with tainted Worker recycling on cleanup, protocol, timeout or post-write failures;
- Aspen Plus/HYSYS 14/15 capability profiles, offline compilation contracts and native adapter conformance;
- licensed solver, licence, Golden Cases, reference values and engineering tolerances remain external qualification inputs.

---

## Mathematical and engineering contracts

![Mathematical contracts](docs/assets/ai/mathematical-contracts.svg)

### 1. Dynamic material balance

For component \(i\):

```math
\frac{dN_i}{dt}
=
\sum_{s\in\mathcal I} \dot n_{i,s}
-
\sum_{s\in\mathcal O} \dot n_{i,s}
+
\sum_{r\in\mathcal R} \nu_{i,r} r_r V
```

At steady state:

```math
0=
\sum_{s\in\mathcal I} \dot n_{i,s}
-
\sum_{s\in\mathcal O} \dot n_{i,s}
+
\sum_{r\in\mathcal R} \nu_{i,r} r_r V
```

Solver success is not balance success. Residuals stay independent in `balance_residuals`; non-finite terms produce `balance_non_finite` and `balance_failed`.

### 2. Energy balance

```math
\frac{dU}{dt}
=
\dot Q-\dot W
+
\sum_{s\in\mathcal I} \dot n_s \hat h_s
-
\sum_{s\in\mathcal O} \dot n_s \hat h_s
```

The project must still approve enthalpy reference, heat loss, shaft work, reaction heat and phase-equilibrium assumptions.

### 3. Constraint violation

For \(g_j(x)\le0\) and \(h_k(x)=0\):

```math
V(x)
=
\sum_j \max(0,g_j(x)-\varepsilon_j)
+
\sum_k \max(0,|h_k(x)|-\varepsilon_k)
```

Independent validity gates:

```math
OK =
C_{comm}
\land C_{engine}
\land C_{conv}
\land C_{finite}
\land C_{constraint}
\land C_{balance}
```

`NaN`, Infinity, text aliases and Boolean numeric aliases fail closed. Evidence uses `allow_nan=False`.

### 4. Units and dimensions

```math
x_t=(x_s+a_s)m_s/m_t-a_t
```

Absolute temperature must satisfy:

```math
T_K>0
```

Parameter contracts enforce numeric type, finiteness, dimension, integrality, fraction range and positive range.

### 5. Cache identity

```math
K =
SHA256(
schema
\Vert version
\Vert backend
\Vert runtime
\Vert model
\Vert registry
\Vert request_{physical}
)
```

Display metadata does not change physical identity. Model, registry, backend, runtime or verification semantics do.

### 6. Warm-start trajectory

![Warm-start trajectory](docs/assets/ai/warm-start-trajectory.svg)

```math
x_{k+1}=F(x_k,u_k),\qquad y_k=G(x_k)
```

Warm-start is path dependent:

- one Worker per trajectory;
- no persistent cache, same-batch dedup or inflight singleflight;
- explicit session/step identity;
- optimization requires `reset_mode='reinitialize'`.

### 7. Constrained optimization

```math
\min_x\;J(x)=\sum_{m=1}^M w_m f_m(x)
```

Subject to variable bounds and all validity gates. Differential evolution is seeded and budgeted. Pareto construction performs exact deduplication, feasibility filtering and nondominance.

### 8. Evidence identity and signature

```math
H_{bundle}
=
SHA256(
H_{request}\Vert
H_{results}\Vert
H_{model}\Vert
H_{registry}\Vert
H_{environment}
)
```

Ed25519 authenticates canonical manifest bytes under a trusted key. It cannot self-grant licensed Aspen engineering status.

---

## Native adapter conformance gate

![Native adapter conformance gate](docs/assets/readme/adapter-conformance.svg)

Before any native write, `aspenops.native-adapter-manifest/v1` must bind profile, profile hash, adapter contract, code hash and runtime identity; cover every operation and `adapter_key`; and declare topology, layout, save/reopen and failure-isolation capabilities. Authorization remains fresh at execution boundaries.

## Native failure isolation

![Native failure isolation](docs/assets/ai/native-failure-isolation.svg)

```text
PRIVATE_CASE_DISCARD
step failure → discard_private_case() → discarded=true

TRANSACTIONAL_ROLLBACK
begin_transaction()
→ steps
→ commit_transaction(token)
or rollback_transaction(token)
```

Missing cleanup methods, malformed cleanup evidence or cleanup failure raises `NativeBuildError`.

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
python scripts/verify_delivery.py --output var/ci/delivery-acceptance.json
```

Real Windows backends:

```powershell
uv sync --frozen --extra windows --extra dev --extra agent --extra signing
uv run aspenops doctor --probe
```

MCP Wheel contract:

```text
mcp>=1.9,<2
```

Mock is control-plane evidence, not Aspen Plus/HYSYS physical evidence.

## Configuration boundaries

```dotenv
ASPENOPS_BACKEND=mock
ASPENOPS_MODE=default
ASPENOPS_ALLOWED_ROOTS=
ASPENOPS_STATE_DIR=var/aspenops-state
ASPENOPS_LICENSE_SLOTS=1
ASPENOPS_MAX_WORKERS=1
ASPENOPS_MAX_RESIDENT_CASES=2
```

Real backends require absolute roots:

```dotenv
ASPENOPS_BACKEND=aspen_plus
ASPENOPS_ALLOWED_ROOTS=C:/AspenModels;C:/AspenResults
ASPENOPS_STATE_DIR=C:/AspenResults/aspenops-state
```

Rules:

1. Real backends cannot use an empty allowlist.
2. `..`, symlinks, junctions and realpath escapes are rejected.
3. `license_slots` and `max_workers` jointly bound concurrency.
4. Unknown backend/mode, truthy strings, non-finite and non-positive budgets fail at construction.
5. Private keys, tokens, licence secrets, customer models and production data do not belong in the repository.

## Configuration and path safety

![Configuration and path safety](docs/assets/readme/policy-path-safety.svg)

```text
Environment / Python API
→ Type Gate
→ Backend and Mode Allowlist
→ Absolute Root Policy
→ resolve()
→ relative_to(approved root)
→ Operation Gate
```

Unknown authority modes cannot inherit default permissions.

## Independent validity gates

![Independent validity gates](docs/assets/readme/validity-gates.svg)

```text
communication_ok
AND engine_ok
AND converged
AND feasible
AND finite evidence
AND constraints passed
AND balances passed
```

Aspen Plus/HYSYS running flags accept explicit booleans, supported COM numeric values and bounded known strings; they never rely on `bool("False")`.

## Common workflows

### Batch

```bash
uv run aspenops run-batch examples/batch-request.example.json \
  --output var/aspenops-state/results.json \
  --bundle var/aspenops-state/run-bundle.zip
```

### Durable scheduler

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

Responses expose `paths_pinned=true` and absolute `submission_cwd`.

### Optimization

```bash
uv run aspenops optimize examples/optimization-request.example.json \
  --output var/aspenops-state/optimization-result.json
```

### Evidence verification

```bash
uv run aspenops verify-bundle var/aspenops-state/run-bundle.zip
```

### MCP

```bash
uv run aspenops mcp
```

## MCP compatibility and server lifecycle

![MCP lifecycle](docs/assets/readme/mcp-runtime-lifecycle.svg)

```text
FastMCP lifespan enter
→ SDK compatibility gate
→ scheduler.start()
→ 14 constrained tools
→ scheduler.stop()
→ Pool / Worker cleanup
```

MCP exposes no arbitrary Shell, COM, Python, VBA or Aspen Tree Path.

## Constrained optimization lifecycle

![Constrained optimization](docs/assets/readme/optimization-lifecycle.svg)

Usage strategy:

- validate structure, budgets and evidence with Mock first;
- start licensed runs with small populations and low concurrency;
- use reinitialize for every optimization point;
- never hide constraint or balance failures with penalty tuning;
- keep checkpoints inside state/allowed roots;
- retain `PENDING_REAL_ASPEN_CERTIFICATION` until engineering approval.

## Scheduling and recovery

![Scheduler lifecycle](docs/assets/readme/scheduler-lifecycle.svg)

```text
pending
→ claimed
→ running
→ completed | failed | cancelling
→ retry_wait | dead_letter | cancelled
```

Expired leases enter `retry_wait` while attempts remain; exhausted attempts enter `dead_letter`. Owner fencing and idempotent commit tokens protect result publication.

## Cache, batch deduplication and singleflight

![Cache and singleflight](docs/assets/readme/cache-singleflight.svg)

- reinitialized requests may use memory LRU, SQLite WAL, `same_batch_dedup` and `inflight_singleflight`;
- warm-start requests use none of those reuse paths;
- failed results are cached only under explicit policy;
- cache reads reject nonstandard JSON constants and non-object payloads;
- returned objects are deeply isolated.

## Worker ownership and recycling

![Worker ownership](docs/assets/readme/worker-ownership-recycle.svg)

One Worker owns one spawned process, COM STA, Automation Server, private model/registry snapshot, sequential command stream and Windows Job Object or verified process-ownership boundary. Timeout, crash, protocol error, tainted transaction, lifecycle budget and post-write exception trigger recycling.

## Performance engineering and evidence

![Performance hotspot map](docs/assets/readme/performance-hotspot-map.svg)

Correctness precedes performance claims. The repository uses:

```text
scripts/measure_cli_startup.py
scripts/measure_operation_counts.py
scripts/measure_job_store_queries.py
```

Outputs:

```text
cli-startup.json
operation-counts.json
job-store-query-plan.json
```

`Performance Audit V2` separates deterministic operation-count contracts from environment-sensitive wall time. Any speedup claim requires the same environment, input, repetitions and statistics.

## Industrial use cases

![Industrial scenarios](docs/assets/readme/industrial-scenarios.svg)

Suitable for approved-model parameter sweeps, DOE, sensitivity studies, constrained screening, bounded optimization, durable multi-model scheduling, licence-slot control and evidence archiving.

Not suitable for inventing property methods, kinetics or equipment specifications without engineering input; bypassing licences; self-approving safety/design; or claiming unverified arbitrary native flowsheet construction.

## Evidence bundle integrity and authenticity

![Evidence integrity](docs/assets/readme/evidence-integrity.svg)

ZIP path, compression ratio, member count, member size and total expansion are bounded. Manifest declarations bind exact byte length and SHA-256. Integrity, signature authenticity, licensed runtime execution and human engineering approval remain separate evidence levels.

## Delivery acceptance

![Delivery acceptance](docs/assets/ai/delivery-acceptance.svg)

```bash
python scripts/verify_delivery.py --output var/ci/delivery-acceptance.json
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest --cov=aspenops_nexus --cov-branch --cov-fail-under=95
uv run python scripts/run_test_order_gate.py --seed 20260728 --output-dir var/ci
uv build
```

The verifier checks bilingual README contracts, twenty-three governed SVGs and four new AI acceptance diagrams; qualification schema, test count, coverage and order gates; four permanent workflows with no one-time/finalizer residue; package version, licence and external hold; and absence of false licensed-certification claims.

## Repository structure

```text
src/aspenops_nexus/     control plane, Worker, Pool, cache, scheduler, optimization, evidence
scripts/                audits, benchmarks, delivery verification and rendering
tests/                  software contracts, regressions, order independence and governance
examples/               Mock, batch, optimization and Process IR examples
docs/                   architecture, qualification, performance, certification and acceptance
.github/workflows/      four permanent read-only qualification workflows
```

## Troubleshooting

| Symptom | Action |
|---|---|
| `doctor --probe` finds no Aspen | verify Windows, bitness, ProgID and licence; do not substitute Mock |
| path rejected | use absolute allowed roots and inspect symlink/junction/realpath |
| `constraint_non_finite` | inspect solver output, unit conversion and derived arithmetic |
| `balance_non_finite` | inspect flow, enthalpy, coefficients and residual normalization |
| warm-start rejected | use one Worker and explicit session/step; use reinitialize for optimization |
| Worker recycled | inspect timeout, protocol, taint, post-write exception and runtime identity |
| evidence verification fails | inspect member list, SHA-256, sizes, trusted key and `allow_nan=False` |
| licensed status remains HOLD | provide solver, fixed inputs, hardware fingerprint, references and tolerances |

## Licence and compliance

Apache-2.0 covers this repository only. Aspen Plus, Aspen HYSYS, Windows, licence servers, customer models and process data remain subject to their own licences and confidentiality requirements. Do not bypass licences, access controls or safety review.

## External qualification intake

Licensed qualification requires, at minimum:

1. solver product, exact version, bitness and ProgID;
2. valid licence features and permitted concurrency;
3. approved fixed model, registry, inputs and output list;
4. CPU, memory, Windows, Python and runner fingerprints;
5. scientific/engineering reference values for every Golden Case;
6. absolute/relative tolerances, repeat count and pass rule;
7. topology/layout/save-reopen/readback evidence;
8. signed process, safety, property and equipment approval.

Until those inputs exist, status remains `PENDING_REAL_ASPEN_CERTIFICATION`.
