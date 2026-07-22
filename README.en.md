<div align="center">

# AspenOps 2.0

## A deterministic, isolated and auditable control plane for Aspen Plus, Aspen HYSYS and AI coding agents

**Codex / Claude Code / MCP → typed process intent → isolated workers → Aspen solve → engineering verification → reproducible evidence**

[中文](README.md) · [Architecture](docs/architecture.md) · [Windows Setup](docs/windows-setup.md) · [Performance](docs/performance.md) · [Certification](docs/certification.md) · [Test Audit](docs/automated-test-audit-2026-07-22.md) · [Security](SECURITY.md)

[![CI main push](https://github.com/SUNHAOJUN22/AspenOps-Agent/actions/workflows/ci.yml/badge.svg?branch=main&event=push)](https://github.com/SUNHAOJUN22/AspenOps-Agent/actions/workflows/ci.yml?query=branch%3Amain+event%3Apush)
[![Windows main push](https://github.com/SUNHAOJUN22/AspenOps-Agent/actions/workflows/windows-control-plane.yml/badge.svg?branch=main&event=push)](https://github.com/SUNHAOJUN22/AspenOps-Agent/actions/workflows/windows-control-plane.yml?query=branch%3Amain+event%3Apush)
![Python](https://img.shields.io/badge/Python-3.11--3.13-3776AB)
![Version](https://img.shields.io/badge/version-2.0.0-111827)
![License](https://img.shields.io/badge/license-Apache--2.0-0F766E)

</div>

---

## Authoritative status

| Item | Status |
|---|---|
| Default and only long-lived branch | `main` |
| Package | `aspenops-nexus 2.0.0` |
| Public test matrix | Python 3.11, 3.12 and 3.13 |
| Archived portable baseline | Actions run `29814739487` |
| Python 3.12 baseline | 72 test modules, 563 passed, 0 failed, 0 skipped, 16.73 s |
| Combined branch-aware coverage | 94.9719800747198% |
| Statement / branch coverage | 96.23677786818551% / 90.84880636604774% |
| CI coverage floor | 94.5% |
| Archived public Windows gate | Actions run `29814739334`, 104 passed, 2.06 s |
| MCP tools | 14 |
| Licensed Aspen certification | Workflow implemented; licensed Windows, approved case and engineering review still required |

The numbers above come from archived JUnit, coverage JSON and logs. The badges are explicitly scoped to `main` push runs. Public CI validates the AspenOps control plane; it does not certify a commercial Aspen installation or an engineering model.

Evidence:

- [`docs/automated-test-audit-2026-07-22.md`](docs/automated-test-audit-2026-07-22.md)
- [`docs/quality-report.md`](docs/quality-report.md)
- [`docs/single-main-audit.json`](docs/single-main-audit.json)
- [`var/consolidation/final-main-manifest.json`](var/consolidation/final-main-manifest.json)

---

## What AspenOps is

AspenOps is not a thin `win32com` wrapper and not a natural-language GUI macro. It is the deterministic execution layer between an AI coding agent and a stateful, version-sensitive, license-constrained process simulator.

```text
The agent decides what experiment to run.
Aspen solves thermodynamics and flowsheet equations.
AspenOps decides whether the operation is authorized, dimensionally valid,
converged, feasible, balanced, reproducible and auditable.
```

A simple COM script does not by itself provide process isolation, hard cancellation, semantic authorization, unit safety, convergence evidence, conservation checks, license-aware concurrency, repeatability or provenance. AspenOps makes those requirements explicit.

---

## Architecture

```text
┌────────────────────────────────────────────────────────────────────┐
│ Codex / Claude Code / MCP Client / Python                          │
│ typed variables, DOE, constraints, objectives and result requests  │
└──────────────────────────────┬─────────────────────────────────────┘
                               │ MCP / CLI / JSON
                               ▼
┌────────────────────────────────────────────────────────────────────┐
│ AspenOps Control Plane                                             │
│ policy · registry · units · bounds · dry run · scheduler · audit   │
│ cache · evidence · certification · optimization                    │
└──────────────────────────────┬─────────────────────────────────────┘
                               │ one batched RPC per point
                               ▼
┌────────────────────────────────────────────────────────────────────┐
│ Persistent CasePool                                                │
│ private process · COM STA · private model copy · one session       │
└──────────────┬───────────────────┬──────────────────────┬───────────┘
               ▼                   ▼                      ▼
          Aspen Plus          Aspen HYSYS             Mock backend
```

### Non-negotiable invariants

1. One COM object belongs to one spawned Windows process and one STA apartment.
2. Agents use semantic variables and never invent raw Aspen tree paths.
3. Every Worker opens a private staged model copy.
4. Reset, bulk write, solve, bulk read and verification cross IPC once per point.
5. Hard timeout terminates only AspenOps-owned and ownership-verified processes.
6. Transport, engine return, convergence, feasibility and balance closure are separate states.
7. Mock CI validates the control plane, never real Aspen physics.
8. Licensed results still require process-engineering review.

---

## Validity contract

A point is valid only when:

```text
communication_ok
AND engine_ok
AND converged
AND feasible
AND balances_passed
```

Results retain constraint values, thresholds, tolerances and violation magnitudes, plus absolute and normalized conservation residuals. `Run2()` returning is only one layer of evidence.

---

## Quick start without Aspen

```bash
git clone https://github.com/SUNHAOJUN22/AspenOps-Agent.git
cd AspenOps-Agent
uv lock --check
uv sync --frozen --extra dev --extra agent --extra signing

uv run aspenops demo
uv run aspenops dry-run examples/batch-request.example.json
uv run aspenops benchmark --points 24 --workers 1,2,4
uv run aspenops certify examples/batch-request.example.json --repeats 3
```

---

## Complete local quality gate

```bash
uv lock --check
uv sync --frozen --extra dev --extra agent --extra signing

uv run ruff check .
uv run ruff format --check .
uv run mypy src

uv run pytest \
  --cov=aspenops_nexus \
  --cov-branch \
  --cov-report=term-missing \
  --cov-report=json:var/coverage.json \
  --junitxml=var/junit.xml \
  --durations=20 \
  --cov-fail-under=94.5

uv build
uv run python scripts/check_mcp.py
uv run aspenops --version
uv run aspenops --help
uv run aspenops demo
```

Repository pytest policy requires pytest 8.3+, strict markers, strict configuration, strict xfail and `ResourceWarning` as an error.

---

## Automated workflows

Only four authoritative long-lived workflows remain:

| Workflow | Trigger | Environment | Scope |
|---|---|---|---|
| `ci.yml` | `main` push, PR, manual | Ubuntu; Python 3.11/3.12/3.13 | Full tests, branch coverage, Ruff, format, mypy, build, Mock, MCP, wheel and README command smoke |
| `windows-control-plane.yml` | `main` push, PR, manual | `windows-latest`; Python 3.12 | Windows Job, process ownership, IPC, scheduler, archives, fake Aspen/HYSYS and workflow governance |
| `generate-performance-evidence.yml` | Manual | Ubuntu; Python 3.12 | Exact baseline/candidate, independent trials and stable regression policy |
| `licensed-aspen-certification.yml` | Protected manual | Self-hosted licensed Windows | Exact SHA, software regression, preflight, real COM, signed evidence and human-review boundary |

### Workflow governance

Automated tests enforce:

- third-party Actions pinned to full commit SHAs;
- read-only repository permissions and non-persistent checkout credentials;
- no `pull_request_target`, `contents: write` or silent `continue-on-error`;
- `uv lock --check` and frozen dependency installation everywhere;
- manual inputs passed through environment variables, never interpolated into shell blocks;
- performance baselines resolved to immutable commit SHAs before worktree creation;
- licensed plan paths constrained to one repository-relative line, canonicalized and checked against workspace escape;
- artifact names based on `github.run_id`, not arbitrary string inputs;
- Windows bootstrap loading `.env`, refreshing PATH after installation and checking every external exit code;
- repository-wide rules locked by `tests/test_workflow_governance.py` and licensed-workflow tests.

---

## Windows with Aspen Plus or HYSYS

Prerequisites:

- native 64-bit Windows;
- Python 3.11–3.13 and `uv`;
- Aspen Plus and/or Aspen HYSYS with a valid license;
- an approved, non-confidential, convergent model;
- a case-specific registry verified with Variable Explorer or the HYSYS Spreadsheet Contract;
- model and result directories inside configured allowed roots.

Recommended bootstrap:

```powershell
git clone https://github.com/SUNHAOJUN22/AspenOps-Agent.git
cd AspenOps-Agent
powershell -ExecutionPolicy Bypass -File scripts/setup_windows.ps1
```

The script installs or locates `uv`, refreshes PATH, verifies the lockfile, performs a frozen install, creates and loads `.env`, and runs Doctor with the loaded backend. A newly copied `.env` uses the Mock backend; edit it to `aspen_plus` or `hysys` and rerun before real work.

First real case:

```powershell
uv run aspenops dry-run D:/AspenModels/request.json
uv run aspenops run-batch D:/AspenModels/request.json `
  --output D:/AspenResults/results.json `
  --bundle D:/AspenResults/run-bundle.zip
uv run aspenops verify-bundle D:/AspenResults/run-bundle.zip
```

Start with one Worker and one known convergent point. Increase concurrency only after constraints, balances, repeatability, memory and license behavior are stable.

---

## Version-adaptive compatibility

AspenOps does not hardcode one `Apwn.Document.N.0` as the latest release. It honors explicit pins, scans both Windows registry views, discovers versioned Aspen Plus and HYSYS Automation Servers, sorts numeric registrations newest-first, creates isolated instances with `DispatchEx`, retains unversioned fallbacks and records the actual successful ProgID and exposed application version.

Discovery is not certification. Formal compatibility still requires the target Aspen version, a valid license, an approved case and engineering review.

---

## CLI

| Command | Purpose |
|---|---|
| `aspenops demo` | Portable Mock end-to-end example |
| `aspenops doctor --probe` | Host, policy and Automation Server diagnostics |
| `aspenops dry-run REQUEST` | Validate paths, semantics, units, bounds and worker caps without Aspen |
| `aspenops run-batch REQUEST` | Execute a batch and write an integrity bundle |
| `aspenops submit REQUEST` | Submit a durable background job |
| `aspenops job JOB_ID` | Read durable job state and results |
| `aspenops benchmark` | Benchmark portable orchestration |
| `aspenops optimize REQUEST` | Run budgeted constrained optimization |
| `aspenops certify REQUEST` | Run repeatability checks without granting real certification |
| `aspenops certification-preflight PLAN` | Validate a licensed plan without opening COM |
| `aspenops certify-licensed PLAN` | Execute an approved plan on a licensed host |
| `aspenops verify-licensed-bundle BUNDLE` | Verify a signed licensed bundle |
| `aspenops verify-bundle BUNDLE` | Verify a normal run bundle |
| `aspenops mcp` | Start the local STDIO MCP server |

---

## MCP surface

The server exposes exactly 14 narrow tools:

```text
system_info
list_semantic_variables
dry_run_request
run_batch_sync
submit_batch
submit_optimization
optimization_status
optimization_result
cancel_optimization
job_status
job_result
list_recent_jobs
cancel_job
verify_evidence_bundle
```

There is no arbitrary shell, Python, VBA, `eval`, unrestricted COM call or raw tree-path mutation tool.

---

## Performance model

```text
T_naive ≈ N × (T_start + T_open + T_solve + T_read)

T_pool ≈ W × (T_start + T_open)
       + N_unique / W × (T_solve + T_verify)
       + T_IPC + T_schedule

W_effective = min(W_configured, W_license, W_memory, W_stability)
```

Gains come from persistent sessions, batched IPC, deduplication, content-addressed caching, dynamic task claiming, private-model parallelism and Worker recycling. Portable Mock benchmarks must not be presented as licensed Aspen solve-performance evidence.

---

## Three certification levels

1. **Control-plane certification** on the deterministic Mock backend.
2. **Licensed-simulator runtime certification** on native Windows with Aspen, a valid license and an approved case.
3. **Engineering model validation** owned by the process engineer.

The protected licensed workflow executes:

```text
exact approved SHA
→ frozen dependencies
→ isolated Mock software regression
→ canonical plan-path validation
→ preflight
→ explicit human approval
→ real COM execution
→ signed-bundle verification
→ engineering review
```

The runtime must remain `PENDING_REAL_ASPEN_CERTIFICATION`; software cannot self-grant final engineering certification.

---

## Security and data boundary

Never commit customer Aspen models, proprietary kinetics or property parameters, production DCS data, license files, sensitive license-server information, credentials, tokens, internal hosts, confidential evidence bundles or signing private keys.

Keep allowed roots narrow, concurrency license-aware and all secrets, licenses, proprietary models and confidential evidence outside the repository.

---

## Repository layout

```text
src/aspenops_nexus/        runtime, control plane, adapters and optimization
tests/                     unit, integration, fault-boundary and workflow-governance tests
examples/                  Mock, request, registry and certification-plan examples
docs/                      architecture, performance, quality, certification and deployment
scripts/                   Windows setup, benchmark and interface verification
.github/workflows/         four authoritative long-lived workflows
```

---

## Honest boundary

Public automation does not prove that any commercial Aspen version starts on a given host, that an arbitrary model converges, that property methods and equipment assumptions are correct, that Mock performance equals real Aspen performance, or that software can replace process-engineering judgment.

---

## License

Apache-2.0. Aspen products, model files, databases, vendor documentation and licenses remain governed by their respective terms. AspenOps does not include Aspen software, licenses or proprietary models.
