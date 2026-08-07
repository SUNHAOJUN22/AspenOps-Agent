<div align="center">

# AspenOps 2.0

## Deterministic engineering control plane for Aspen Plus, Aspen HYSYS, and AI agents

**Governed requirement → typed process intent → engineering rules → verifiable compilation → isolated execution → engineering decision → auditable evidence → deterministic handover**

[中文](README.md) · [Architecture](docs/architecture.md) · [Delivery Acceptance](docs/delivery-acceptance.md) · [Delivery Bundle](docs/delivery-bundle.md) · [Windows Setup](docs/windows-setup.md) · [Certification](docs/certification.md) · [Quality Report](docs/quality-report.md)

[![CI main push](https://github.com/SUNHAOJUN22/AspenOps-Agent/actions/workflows/ci.yml/badge.svg?branch=main&event=push)](https://github.com/SUNHAOJUN22/AspenOps-Agent/actions/workflows/ci.yml?query=branch%3Amain+event%3Apush)
[![Windows main push](https://github.com/SUNHAOJUN22/AspenOps-Agent/actions/workflows/windows-control-plane.yml/badge.svg?branch=main&event=push)](https://github.com/SUNHAOJUN22/AspenOps-Agent/actions/workflows/windows-control-plane.yml?query=branch%3Amain+event%3Apush)
![Python](https://img.shields.io/badge/Python-3.11--3.13-3776AB)
![Version](https://img.shields.io/badge/version-2.0.0-111827)
![License](https://img.shields.io/badge/license-Apache--2.0-0F766E)

</div>

![AspenOps architecture](docs/assets/readme/hero-architecture.svg)

> **Acceptance boundary:** AspenOps can qualify its software control plane, typed process intent, isolated runtime, cache/scheduler/optimization behavior, evidence chain, and deterministic handover. It cannot self-grant licensed Aspen engineering certification without the real commercial solver, licence, fixed model, Golden Cases, hardware fingerprint, and approved tolerances. The real-environment status must remain `PENDING_REAL_ASPEN_CERTIFICATION`.

## Acceptance status

| Item | Current rule |
|---|---|
| Long-lived branch | `main` only |
| Python package | `aspenops-nexus 2.0.0` |
| Historical full software baseline | `1224 passed`, 0 failed, 0 errors, 95.03% branch coverage |
| Order gates | reverse-order PASS; seed `20260728` PASS |
| Delivery-surface verifier | `python scripts/verify_delivery.py` |
| Exact-tree qualification | `python scripts/verify_delivery.py --require-current-qualification` |
| Deterministic handover | `scripts/build_delivery_bundle.py` |
| Licensed Aspen/HYSYS | `PENDING_REAL_ASPEN_CERTIFICATION` |

Archived qualification evidence proves only the source identity recorded in that evidence. It does not automatically qualify later commits. If the acceptance decision requires exact-tree qualification rather than delivery-surface completeness, provide `docs/DELIVERY_QUALIFICATION.json` and use `--require-current-qualification`.

---

## AI and engineering visual atlas

All figures are repository-local. The four figures under `docs/assets/ai/` are AI-assisted acceptance illustrations grounded in implemented contracts.

| Architecture and intent | Runtime and safety | Evidence and engineering |
|---|---|---|
| ![hero](docs/assets/readme/hero-architecture.svg) | ![agent pipeline](docs/assets/readme/agent-pipeline.svg) | ![process IR](docs/assets/readme/process-intent-ir.svg) |
| ![backend](docs/assets/readme/backend-capabilities.svg) | ![adapter](docs/assets/readme/adapter-conformance.svg) | ![math](docs/assets/ai/mathematical-contracts.svg) |
| ![com isolation](docs/assets/readme/com-isolation.svg) | ![worker recycle](docs/assets/readme/worker-ownership-recycle.svg) | ![native failure isolation](docs/assets/ai/native-failure-isolation.svg) |
| ![validity](docs/assets/readme/validity-gates.svg) | ![warm start](docs/assets/ai/warm-start-trajectory.svg) | ![optimization](docs/assets/readme/optimization-lifecycle.svg) |
| ![scheduler](docs/assets/readme/scheduler-lifecycle.svg) | ![durable path](docs/assets/readme/durable-path-portability.svg) | ![cache](docs/assets/readme/cache-singleflight.svg) |
| ![evidence chain](docs/assets/readme/evidence-chain.svg) | ![evidence integrity](docs/assets/readme/evidence-integrity.svg) | ![licensed certification](docs/assets/readme/licensed-certification.svg) |
| ![cli mcp](docs/assets/readme/cli-mcp-workflow.svg) | ![mcp lifecycle](docs/assets/readme/mcp-runtime-lifecycle.svg) | ![path safety](docs/assets/readme/policy-path-safety.svg) |
| ![performance](docs/assets/readme/performance-hotspot-map.svg) | ![startup](docs/assets/readme/cold-warm-startup.svg) | ![test matrix](docs/assets/readme/test-matrix.svg) |
| ![industry](docs/assets/readme/industrial-scenarios.svg) | ![delivery](docs/assets/ai/delivery-acceptance.svg) | ![roadmap](docs/assets/readme/roadmap.svg) |

---

## Product position

AspenOps is not a wrapper that allows a model to emit arbitrary COM, VBA, Python, or shell code. It converts agent/human intent into typed contracts and governed execution:

```text
Human / Agent
→ ProcessRequirementDocument
→ ProcessDesignIR
→ Engineering Rules
→ Simulator Capability Profile
→ Compilation / Evaluation Plan
→ CasePool / Scheduler
→ Process-isolated Worker
→ Aspen Plus / HYSYS / Mock
→ Readback + Constraints + Balances
→ Evidence Bundle
→ Deterministic Handover
```

Core responsibilities:

- typed process intent and semantic variables;
- engineering rules, units, ranges, degrees of freedom, recycle/tear validation;
- semantic reads/writes against approved Aspen Plus/HYSYS models;
- one Windows child process and COM STA per real simulator ownership boundary;
- `CasePool`, persistent cache, batch execution, singleflight, scheduler, and optimization;
- native-adapter conformance and failure isolation;
- run evidence, hashes, signatures, revocation, and reproducible handover;
- Mock/offline qualification for software behavior without pretending to produce real thermodynamic or equipment results.

---

## Mathematical and engineering contracts

![Mathematical contracts](docs/assets/ai/mathematical-contracts.svg)

### 1. Component material balance

For component \(i\):

```math
\frac{dN_i}{dt}
=
\sum_{s\in\mathcal I}\dot n_{i,s}
-
\sum_{s\in\mathcal O}\dot n_{i,s}
+
\sum_{r\in\mathcal R}\nu_{i,r}r_rV
```

At steady state:

```math
0
=
\sum_{s\in\mathcal I}\dot n_{i,s}
-
\sum_{s\in\mathcal O}\dot n_{i,s}
+
\sum_{r\in\mathcal R}\nu_{i,r}r_rV
```

Solver success is not balance success. Non-finite balance evidence is represented separately as `balance_non_finite`; out-of-tolerance residuals produce `balance_failed`.

### 2. Energy balance

```math
\frac{dU}{dt}
=
\dot Q-\dot W
+
\sum_{s\in\mathcal I}\dot n_s\hat h_s
-
\sum_{s\in\mathcal O}\dot n_s\hat h_s
```

Real projects must still approve the enthalpy basis, heat loss, shaft work, heat of reaction, and phase-equilibrium assumptions.

### 3. Independent validity gates

```math
OK =
C_{comm}
\land C_{engine}
\land C_{conv}
\land C_{finite}
\land C_{constraint}
\land C_{balance}
```

Constraint violation:

```math
V(x)
=
\sum_j \max(0,g_j(x)-\varepsilon_j)
+
\sum_k \max(0,|h_k(x)|-\varepsilon_k)
```

`NaN`, Infinity, textual numeric aliases, and Boolean numeric aliases fail closed. Non-finite constraint evidence is exposed as `constraint_non_finite`. Evidence JSON uses `allow_nan=False`.

### 4. Units and affine conversion

```math
x_t=(x_s+a_s)\frac{m_s}{m_t}-a_t
```

Absolute temperature:

```math
T_K>0
```

Parameter contracts validate numeric type, finiteness, physical dimension, integrality, fractional range, and positive ranges.

### 5. Recycle graph and tear edges

For a directed material graph \(G=(V,E)\) and tear-edge set \(T\):

```math
\forall C\in cycles(G),\qquad C\cap T\neq\varnothing
```

A generic recycle declaration cannot suppress an unrelated directed cycle. A tear edge must belong to the actual cycle it resolves.

### 6. Distillation degrees of freedom

```math
DOF=N_c-N_s
```

\(N_c\) is the number of independent controllable/manipulated variables and \(N_s\) the number of independent specifications. Capability profiles must expose independent design specifications consistent with engineering rules.

### 7. Cache identity

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

Display metadata does not change physical identity. Model, registry, backend, runtime, or verification semantics do.

### 8. Warm-start trajectory

![Warm-start trajectory](docs/assets/ai/warm-start-trajectory.svg)

```math
x_{k+1}=F(x_k,u_k),\qquad y_k=G(x_k)
```

Warm-start is path dependent, so:

- one Worker owns one trajectory;
- persistent cache is disabled;
- same-batch deduplication is disabled;
- `inflight_singleflight` is disabled;
- explicit session/step metadata participates in trajectory identity;
- optimization uses `reset_mode='reinitialize'` so objective values do not depend on prior candidates.

### 9. Constrained optimization

```math
\min_x J(x)=\sum_{m=1}^{M}w_m f_m(x)
```

With a penalty:

```math
J_p(x)=J(x)+\lambda V(x),\qquad \lambda\ge0
```

Operational rule: qualify feasibility and engineering gates before comparing objectives. Do not use penalty tuning to hide convergence, balance, or non-finite failures.

### 10. Licence-aware concurrency

A conservative bound is:

```math
C_{\max}\le \min(L,W)
```

where \(L\) is available licence slots and \(W\) is the configured Worker budget. Memory, model residency, and Windows process limits may reduce usable concurrency further.

### 11. Evidence binding

```math
H_{bundle}
=
SHA256(
H_{request}
\Vert H_{results}
\Vert H_{model}
\Vert H_{registry}
\Vert H_{environment}
)
```

Ed25519 authenticates canonical manifest bytes under a trusted key. It cannot elevate software evidence into licensed Aspen engineering certification.

---

## Process Intent IR and engineering rules

![Process Intent IR](docs/assets/readme/process-intent-ir.svg)

Process Intent IR expresses:

```text
units
streams
connections
parameters
tears
constraints
design intent
```

Recommended strategy:

1. Validate topology, units, parameter contracts, and capability profiles with Mock/offline compilation first.
2. Select tear edges explicitly for recycle graphs.
3. Use only approved semantic keys and approved model roots against real Aspen installations.
4. Apply unit-specific contracts for distillation, reactors, heat exchangers, and pumps/compressors.
5. Keep “the model can run” separate from “the engineering result is approved.”

---

## Native adapter conformance

![Adapter conformance](docs/assets/readme/adapter-conformance.svg)

Before native writes, the adapter must bind:

- capability profile;
- profile SHA-256;
- adapter contract and code identity;
- operation/`adapter_key` coverage;
- topology/layout readback;
- save/reopen;
- failure isolation;
- fresh authorization.

## Native failure isolation

![Native failure isolation](docs/assets/ai/native-failure-isolation.svg)

Two enforceable strategies:

```text
PRIVATE_CASE_DISCARD
step failure
→ discard_private_case()
→ discarded == True
```

```text
TRANSACTIONAL_ROLLBACK
token = begin_transaction()
→ steps
→ commit_transaction(token)
or
→ rollback_transaction(token)
```

Missing cleanup methods, cleanup values other than literal `True`, rollback/discard failure, and post-write exceptions taint the Worker and trigger recycling.

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

Mock is a control-plane/software-qualification backend; it is not evidence for real Aspen Plus/HYSYS thermodynamics, properties, equipment, or convergence.

---

## Configuration and path safety

```dotenv
ASPENOPS_BACKEND=mock
ASPENOPS_MODE=default
ASPENOPS_ALLOWED_ROOTS=
ASPENOPS_STATE_DIR=var/aspenops-state
ASPENOPS_LICENSE_SLOTS=1
ASPENOPS_MAX_WORKERS=1
ASPENOPS_MAX_RESIDENT_CASES=2
```

Real-backend example:

```dotenv
ASPENOPS_BACKEND=aspen_plus
ASPENOPS_ALLOWED_ROOTS=C:/AspenModels;C:/AspenResults
ASPENOPS_STATE_DIR=C:/AspenResults/aspenops-state
```

![Path safety](docs/assets/readme/policy-path-safety.svg)

Rules:

- real backends cannot use an empty allowlist;
- only absolute approved roots are valid;
- `..`, symlink, junction, and realpath escapes are rejected;
- unknown backend/mode values fail closed;
- truthy strings and non-finite resource budgets are rejected;
- private keys, tokens, licence secrets, customer models, and production data do not belong in the repository.

---

## Batch, cache, and singleflight strategy

![Cache and singleflight](docs/assets/readme/cache-singleflight.svg)

For `reinitialize` requests, AspenOps may use:

- memory LRU;
- SQLite WAL persistent cache;
- same-batch deduplication;
- `inflight_singleflight`.

Warm-start requests use none of those cross-request reuse paths.

Recommendations:

1. Reuse results only for deterministic, reinitialized requests.
2. Cache failures only under explicit policy.
3. Bind cache identity to backend/runtime/model/registry/physical request.
4. Reject non-standard JSON constants and non-object cache roots.
5. Return deeply isolated result objects.

---

## Worker ownership and durable scheduling

![Worker ownership](docs/assets/readme/worker-ownership-recycle.svg)

One Worker owns:

```text
spawned process
+ COM STA
+ Automation Server
+ private case
+ sequential command stream
+ process-ownership supervision
```

![Scheduler lifecycle](docs/assets/readme/scheduler-lifecycle.svg)

Scheduler states include:

```text
pending
→ claimed
→ running
→ completed | failed | cancelling
→ retry_wait | dead_letter | cancelled
```

Expired leases enter `retry_wait` while retry budget remains; exhausted jobs enter `dead_letter`. Owner fencing and idempotent commit tokens prevent stale Workers from publishing results.

---

## Common operating strategies

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

### Optimization

```bash
uv run aspenops optimize examples/optimization-request.example.json \
  --output var/aspenops-state/optimization-result.json
```

Optimization should use reinitialize. Do not treat warm-start state as a stateless objective-function cache.

### MCP

```bash
uv run aspenops mcp
```

The MCP surface does not expose arbitrary shell, Python, VBA, COM, or Aspen Tree Path access.

### Evidence

```bash
uv run aspenops verify-bundle var/aspenops-state/run-bundle.zip
```

---

## Performance strategy

![Performance hotspot map](docs/assets/readme/performance-hotspot-map.svg)

Performance work follows:

```text
correctness qualification
→ deterministic operation-count evidence
→ same-environment timing
→ optimization
→ regression gate
```

Repository measurement entry points:

```text
scripts/measure_cli_startup.py
scripts/measure_operation_counts.py
scripts/measure_job_store_queries.py
```

A speedup claim requires the same workload, environment, repetitions, and statistical rule.

---

## Deterministic delivery bundle

Software acceptance should not end with an unbound source directory. `scripts/build_delivery_bundle.py` converts one exact Git SHA into a reproducible handover.

```bash
rm -rf var/delivery
uv build

uv run python scripts/build_delivery_bundle.py \
  --source-sha "$(git rev-parse HEAD)" \
  --source-date-epoch 0 \
  --include-dist \
  --output-dir var/delivery
```

Artifacts:

```text
aspenops-source-<sha12>.zip
aspenops-sbom-<sha12>.spdx.json
aspenops-evidence-index-<sha12>.json
aspenops-delivery-manifest-<sha12>.json
SHA256SUMS
aspenops-handover-<sha12>.zip
aspenops-handover-<sha12>.zip.sha256
wheel / source distribution
```

The SBOM is `SPDX-2.3`.

For each artifact \(A_i\):

```math
h_i=SHA256(A_i)
```

Checksum set:

```math
S=\operatorname{sort}\{(h_i,\operatorname{name}(A_i))\}
```

Final package:

```math
B=
ZIP_{deterministic}
(A_1,\ldots,A_n,Manifest,SHA256SUMS)
```

External checksum:

```math
h_B=SHA256(B)
```

The builder uses fixed ZIP timestamps, sorted members, normalized file modes, strict JSON, and `allow_nan=False`. Symlinks, path escape, non-empty output directories, malformed Git SHAs, forged real-Aspen status, and unrelated distribution files fail closed.

Verification:

```bash
cd var/delivery
sha256sum -c SHA256SUMS
sha256sum -c aspenops-handover-*.zip.sha256
```

---

## Delivery acceptance

![Delivery acceptance](docs/assets/ai/delivery-acceptance.svg)

### A. Delivery-surface completeness

```bash
python scripts/verify_delivery.py \
  --output var/ci/delivery-acceptance.json
```

This verifies:

- bilingual README contracts;
- 27 governed/AI-assisted figures;
- deterministic bundle surface;
- SBOM/manifest/SHA-256 documentation;
- qualification writer;
- exactly four permanent read-only workflows;
- no temporary workflow/running-heartbeat residue;
- historical software qualification baseline;
- the `PENDING_REAL_ASPEN_CERTIFICATION` boundary.

### B. Exact-tree qualification

After a full qualification process creates `docs/DELIVERY_QUALIFICATION.json`:

```bash
python scripts/verify_delivery.py \
  --require-current-qualification \
  --output var/ci/delivery-acceptance-current.json
```

Recommended software gates:

```bash
uv lock --check
uv sync --frozen --extra dev --extra agent --extra signing
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run python -m compileall -q src scripts tests
uv run python scripts/audit_source_tree.py
uv run pytest --cov=aspenops_nexus --cov-branch --cov-fail-under=95
uv run python scripts/run_test_order_gate.py --seed 20260728 --output-dir var/ci
uv build
```

`write_delivery_qualification.py` writes `aspenops.delivery-qualification/v2` only after a complete suite reports no failures, no errors, **no skipped tests**, at least 1200 passed tests, at least 95% branch coverage, and a PASS delivery-verifier report.

---

## Repository structure

```text
src/aspenops_nexus/     control plane, Worker, Pool, cache, scheduler, optimization, evidence
scripts/                audits, benchmarks, delivery verifier, deterministic bundle builder
tests/                  software contracts, regressions, order independence, delivery governance
examples/               Mock, batch, optimization, Process Intent IR
docs/                   architecture, acceptance, certification, delivery bundle, visuals
.github/workflows/      four permanent read-only qualification workflows
```

---

## External inputs for real Aspen qualification

Licensed engineering qualification requires at least:

1. Aspen Plus/HYSYS product, exact version, bitness, and ProgID;
2. valid licence features and permitted concurrency;
3. fixed approved model, registry, inputs, and output list;
4. Windows, Python, CPU, memory, and runner fingerprints;
5. engineering/scientific reference values for each Golden Case;
6. absolute/relative tolerances, repeat count, and pass rule;
7. topology/layout/save-reopen/readback evidence;
8. process, property, equipment, and safety approval.

Without those inputs:

```text
PENDING_REAL_ASPEN_CERTIFICATION
```

must remain unchanged.

---

## License

Apache-2.0 covers this repository only. Aspen Plus, Aspen HYSYS, Windows, licence servers, customer models, and process data remain subject to their own licences, confidentiality requirements, and safety controls.
