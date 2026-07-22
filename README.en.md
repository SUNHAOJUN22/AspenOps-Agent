<div align="center">

# AspenOps 2.0

## A deterministic, isolated and auditable execution control plane for Aspen Plus, Aspen HYSYS and AI coding agents

**Codex / Claude Code / MCP → typed process intent → isolated workers → Aspen solve → engineering verification → reproducible evidence**

[中文](README.md) · [Architecture](docs/architecture.md) · [Windows Setup](docs/windows-setup.md) · [Performance](docs/performance.md) · [Certification](docs/certification.md) · [Security](SECURITY.md)

[![CI](https://github.com/SUNHAOJUN22/AspenOps-Agent/actions/workflows/ci.yml/badge.svg)](https://github.com/SUNHAOJUN22/AspenOps-Agent/actions/workflows/ci.yml)
[![Windows control plane](https://github.com/SUNHAOJUN22/AspenOps-Agent/actions/workflows/windows-control-plane.yml/badge.svg)](https://github.com/SUNHAOJUN22/AspenOps-Agent/actions/workflows/windows-control-plane.yml)
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
| Python | 3.11, 3.12 and 3.13 |
| Latest recorded portable gate | PASS: 563 tests, 94.97198% combined branch-aware coverage |
| CI coverage floor | 94.5% |
| Public Windows control plane | PASS |
| MCP tools | 14 |
| Licensed real-Aspen certification | Workflow implemented; approved model and licensed Windows host still required |

Evidence is retained in `docs/single-main-audit.json`, `docs/quality-report.md`, `var/consolidation/final-main-manifest.json` and `var/consolidation/branch-archive-manifest.json`.

Portable tests validate the AspenOps control plane. They do not impersonate real Aspen thermodynamic or flowsheet certification.

---

## What AspenOps is

AspenOps is not a thin `win32com` wrapper and not a natural-language GUI macro. It is the deterministic execution layer between an AI coding agent and a stateful, version-sensitive, license-constrained nonlinear process simulator.

```text
The agent decides what experiment to run.
Aspen solves thermodynamics and flowsheet equations.
AspenOps decides whether the operation is allowed, dimensionally valid,
converged, feasible, balanced, reproducible and auditable.
```

A typical COM snippet can open a case, write a tree node and call `Run2()`. It does not by itself solve process isolation, hard cancellation, license-aware concurrency, semantic authorization, unit safety, convergence evidence, conservation checks, repeatability or provenance. AspenOps makes those concerns explicit.

---

## Core invariants

1. One COM object belongs to one spawned Windows process and one STA apartment.
2. Agents use semantic variables and do not invent raw Aspen tree paths.
3. Every worker opens a private staged copy of the source model.
4. Reset, bulk write, solve, bulk read and verification cross IPC once per point.
5. Hard timeout terminates only the worker created by AspenOps.
6. Transport, engine return, convergence, feasibility and balance closure are separate states.
7. Portable Mock CI validates the control plane and never claims real Aspen physical certification.
8. A licensed runtime result still requires process-engineering review of the model and qualification case.

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
│ policy · semantic registry · units · bounds · dry run · scheduler  │
│ cache · evidence · certification · optimization                    │
└──────────────────────────────┬─────────────────────────────────────┘
                               │ one batched RPC per point
                               ▼
┌────────────────────────────────────────────────────────────────────┐
│ Persistent CasePool                                                │
│ private process · COM STA · private model copy · one Aspen session │
└──────────────┬───────────────────┬──────────────────────┬──────────┘
               ▼                   ▼                      ▼
          Aspen Plus          Aspen HYSYS             Mock backend
```

### Validity contract

A result is valid only when:

```text
communication_ok
AND engine_ok
AND converged
AND feasible
AND balances_passed
```

AspenOps records the actual constraint value, threshold, tolerance and violation magnitude. Conservation checks retain both absolute and normalized residuals. `Run2()` returning is only one layer of evidence.

---

## Version-adaptive compatibility

AspenOps does not hardcode one `Apwn.Document.N.0` as “the latest release.” It:

1. honors explicitly pinned `ASPENOPS_PROGID` or `ASPENOPS_HYSYS_PROGID` values;
2. scans both Windows registry views;
3. discovers versioned `Apwn.Document.*` and `HYSYS.Application.*` servers;
4. sorts numeric registrations newest-first;
5. creates isolated instances with `DispatchEx`;
6. retains unversioned ProgIDs as fallback;
7. records the successfully instantiated ProgID and exposed application version in evidence.

Runtime discovery is not the same as verified support. Formal compatibility still requires the licensed Windows certification workflow with an approved case.

---

## Quick start without Aspen

```bash
git clone https://github.com/SUNHAOJUN22/AspenOps-Agent.git
cd AspenOps-Agent
uv sync --extra dev --extra agent --extra signing

uv run aspenops demo
uv run aspenops benchmark --points 24 --workers 1,2,4
uv run aspenops certify examples/batch-request.example.json --repeats 3
```

Complete portable quality gate:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest -W error::ResourceWarning \
  --cov=aspenops_nexus \
  --cov-branch \
  --cov-report=term-missing \
  --cov-fail-under=94.5
uv build
uv run python scripts/check_mcp.py
```

---

## Windows with Aspen Plus or HYSYS

Prerequisites:

- native 64-bit Windows;
- Python 3.11–3.13 and `uv`;
- licensed Aspen Plus and/or Aspen HYSYS;
- an approved non-confidential convergent model;
- a case-specific semantic registry verified through Variable Explorer or the HYSYS Spreadsheet Contract;
- model and result directories inside configured allowed roots;
- a known license-seat limit.

Install and diagnose:

```powershell
git clone https://github.com/SUNHAOJUN22/AspenOps-Agent.git
cd AspenOps-Agent
powershell -ExecutionPolicy Bypass -File scripts/setup_windows.ps1
```

Manual equivalent:

```powershell
uv sync --extra windows --extra dev --extra agent --extra signing
Copy-Item .env.example .env
uv run aspenops doctor --probe
```

Recommended starting configuration:

```text
ASPENOPS_BACKEND=aspen_plus
ASPENOPS_MODE=default
ASPENOPS_ALLOWED_ROOTS=D:/AspenModels;D:/AspenResults
ASPENOPS_LICENSE_SLOTS=1
ASPENOPS_MAX_WORKERS=1
ASPENOPS_TIMEOUT_S=1200
ASPENOPS_STARTUP_TIMEOUT_S=90
ASPENOPS_WORKER_MAX_POINTS=200
ASPENOPS_WORKER_MAX_AGE_S=14400
ASPENOPS_MAX_RESIDENT_CASES=2
ASPENOPS_POOL_IDLE_TIMEOUT_S=1800
ASPENOPS_CACHE_FAILURES=0
ASPENOPS_VISIBLE=0
```

First real run:

```powershell
uv run aspenops doctor --probe
uv run aspenops dry-run D:/AspenModels/request.json
uv run aspenops run-batch D:/AspenModels/request.json `
  --output D:/AspenResults/results.json `
  --bundle D:/AspenResults/run-bundle.zip
uv run aspenops verify-bundle D:/AspenResults/run-bundle.zip
```

Start with one worker. Increase concurrency only after one-point, constraint, balance and repeatability checks are stable.

---

## CLI surface

| Command | Purpose |
|---|---|
| `aspenops demo` | Portable nonlinear Mock end-to-end example |
| `aspenops doctor --probe` | Host, policy and COM discovery diagnostics |
| `aspenops dry-run REQUEST` | Validate paths, units, semantics, bounds and worker caps without Aspen |
| `aspenops run-batch REQUEST` | Execute a batch and write an integrity bundle |
| `aspenops submit REQUEST` | Submit a durable background job |
| `aspenops job JOB_ID` | Read durable job state and result |
| `aspenops benchmark` | Benchmark the portable scheduler |
| `aspenops optimize REQUEST` | Run budgeted constrained optimization |
| `aspenops certify REQUEST` | Run repeatability checks; never grants real-Aspen certification |
| `aspenops certification-preflight PLAN` | Validate a licensed plan without opening COM |
| `aspenops certify-licensed PLAN` | Execute an approved plan on a licensed host |
| `aspenops verify-licensed-bundle BUNDLE` | Verify a signed licensed evidence bundle |
| `aspenops verify-bundle BUNDLE` | Verify a normal run bundle |
| `aspenops mcp` | Start the local STDIO MCP server |

```bash
uv run aspenops --help
uv run aspenops <command> --help
```

---

## MCP, Codex and Claude Code

The repository includes `.codex/config.toml`, `.mcp.json` and `CLAUDE.md`.

The MCP server exposes exactly 14 narrow tools:

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

Recommended sequence:

```text
system_info
→ list_semantic_variables
→ dry_run_request
→ submit_batch / submit_optimization
→ job_status / optimization_status
→ job_result / optimization_result
→ verify_evidence_bundle
```

There is no arbitrary shell, Python, VBA, `eval`, unrestricted COM method or raw tree-path mutation tool.

---

## Performance model

Naive point-by-point startup:

```text
T_naive ≈ N × (T_start + T_open + T_solve + T_read)
```

Persistent CasePool:

```text
T_pool ≈ W × (T_start + T_open)
       + N_unique / W × (T_solve + T_verify)
       + T_IPC + T_schedule
```

Throughput gains come from persistent sessions, one batched RPC per point, request deduplication, content-addressed caching, dynamic task claiming, private model parallelism and worker recycling.

Effective concurrency is bounded by:

```text
W_effective = min(W_configured, W_license, W_memory, W_stability)
```

Portable Mock benchmarks must not be presented as licensed Aspen solve-performance claims.

---

## Certification contract

Certification has three distinct levels:

1. **Control-plane certification** on the deterministic Mock backend.
2. **Licensed-simulator runtime certification** on native Windows with Aspen, a valid license and an approved qualification case.
3. **Engineering model validation** owned by the process engineer.

The authoritative licensed workflow is:

```text
.github/workflows/licensed-aspen-certification.yml
```

It requires an exact approved 40-character commit SHA, plan path, backend selection and explicit authorization before real COM execution. The runtime can generate a signed `PENDING_REAL_ASPEN_CERTIFICATION` evidence bundle; it cannot self-grant engineering certification.

---

## Security and data boundary

Never commit:

- customer `.bkp`, `.apw`, `.apwz` or `.hsc` files;
- proprietary kinetics, property parameters or production DCS data;
- license files or sensitive license-server information;
- credentials, tokens, internal hosts or private paths;
- confidential result bundles;
- signing private keys.

Keep allowed roots narrow, concurrency license-aware, qualification cases non-confidential and signing keys outside the repository.

---

## Repository layout

```text
src/aspenops_nexus/
  batch.py
  compat.py
  registry.py
  units.py
  worker.py
  pool.py
  pool_manager.py
  scheduler.py
  evaluation.py
  cache.py
  certification.py
  licensed_certification.py
  provenance.py
  optimization.py
  optimizer.py
  design.py
  mcp_server.py
  backends/
    aspen_plus.py
    hysys.py
    mock.py

tests/
examples/
docs/
scripts/
.github/workflows/
  ci.yml
  windows-control-plane.yml
  generate-performance-evidence.yml
  licensed-aspen-certification.yml
```

---

## Honest boundary

AspenOps 2.0 provides a steady-state Aspen Plus COM control plane, a controlled HYSYS Spreadsheet Bridge, CLI/Python/MCP interfaces, durable batches, caching, concurrency, timeout, verification, optimization and evidence workflows.

It does not claim that public Linux CI has executed proprietary Aspen software; that every Aspen version, module or model is compatible without qualification; that `Run2()` proves engineering correctness; that the full HYSYS object model is uniformly wrapped; or that an LLM replaces property-method selection, reaction engineering, equipment design and process review.

## License

Apache-2.0. Aspen products, models, databases and vendor documentation remain governed by their respective licenses. AspenOps does not distribute Aspen software, licenses or proprietary cases.
