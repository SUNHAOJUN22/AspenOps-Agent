<div align="center">

# AspenOps 2.0

## A deterministic, isolated and auditable execution control plane for Aspen Plus, Aspen HYSYS and AI coding agents

**Codex / Claude Code / MCP → typed process intent → isolated workers → Aspen solve → engineering verification → reproducible evidence**

[中文](README.md) · [Architecture](docs/architecture.md) · [Windows Setup](docs/windows-setup.md) · [Performance](docs/performance.md) · [Certification](docs/certification.md) · [Test Audit](docs/automated-test-audit-2026-07-22.md) · [Security](SECURITY.md)

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
| Archived portable run | Actions run `29814739487`, SHA `670e9523e915af309f16d959150cfadcd84219a6` |
| Python 3.12 evidence | 72 test modules, 563 passed, 0 failed, 0 skipped, 16.73 s |
| Combined branch-aware coverage | 94.9719800747198% |
| Statement / branch coverage | 96.23677786818551% / 90.84880636604774% |
| CI coverage floor | 94.5% |
| Archived public Windows gate | Actions run `29814739334`, 104 passed, 2.06 s |
| MCP tools | 14 |
| Licensed real-Aspen certification | Workflow implemented; approved case, licensed Windows host and engineering review still required |

Those values were independently checked from archived JUnit, coverage JSON and log artifacts. They are not inferred from the README. Every push to current `main` triggers the hardened portable and public-Windows gates; the badges above are the latest status entry points.

Evidence and audit records:

- [`docs/automated-test-audit-2026-07-22.md`](docs/automated-test-audit-2026-07-22.md)
- [`docs/quality-report.md`](docs/quality-report.md)
- [`docs/single-main-audit.json`](docs/single-main-audit.json)
- [`var/consolidation/final-main-manifest.json`](var/consolidation/final-main-manifest.json)

Portable tests validate the AspenOps control plane. They do not impersonate licensed Aspen thermodynamic, flowsheet or engineering-model certification.

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
2. Agents use semantic variables and never invent raw Aspen tree paths.
3. Every worker opens a private staged copy of the source model.
4. Reset, bulk write, solve, bulk read and verification cross IPC once per point.
5. A hard timeout terminates only the worker created by AspenOps.
6. Transport, engine return, convergence, feasibility and balance closure are separate states.
7. Portable Mock CI validates the control plane and never claims real Aspen physical certification.
8. A licensed runtime result still requires process-engineering review of the model and qualification case.

A result is valid only when:

```text
communication_ok
AND engine_ok
AND converged
AND feasible
AND balances_passed
```

AspenOps records actual constraint values, thresholds, tolerances, violation magnitudes and both absolute and normalized conservation residuals. `Run2()` returning is only one layer of evidence.

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

### Version-adaptive compatibility

AspenOps does not hardcode one `Apwn.Document.N.0` as “the latest release.” It:

1. honors explicit `ASPENOPS_PROGID` or `ASPENOPS_HYSYS_PROGID` pins;
2. scans both Windows registry views;
3. discovers versioned `Apwn.Document.*` and `HYSYS.Application.*` servers;
4. sorts numeric registrations newest-first;
5. creates isolated instances with `DispatchEx`;
6. retains unversioned ProgIDs as fallbacks;
7. records the successful ProgID and application-exposed version in evidence.

Runtime discovery is not verified support. Formal compatibility still requires the licensed Windows certification workflow with an approved case.

---

## Quick start without Aspen

### Install from the committed lockfile

```bash
git clone https://github.com/SUNHAOJUN22/AspenOps-Agent.git
cd AspenOps-Agent
uv lock --check
uv sync --frozen --extra dev --extra agent --extra signing
```

`uv lock --check` requires project metadata and `uv.lock` to agree. `uv sync --frozen` prevents the test environment from rewriting the lockfile.

### Run the portable end-to-end example

```bash
uv run aspenops demo
```

### Run the portable benchmark and repeatability gate

```bash
uv run aspenops benchmark --points 24 --workers 1,2,4
uv run aspenops certify examples/batch-request.example.json --repeats 3
```

### Run the core local gate used by CI

```bash
mkdir -p var/ci

uv lock --check
uv sync --frozen --extra dev --extra agent --extra signing
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest -W error::ResourceWarning \
  --cov=aspenops_nexus \
  --cov-branch \
  --cov-report=term-missing \
  --cov-report=json:var/ci/coverage-local.json \
  --junitxml=var/ci/junit-local.xml \
  --durations=20 \
  --cov-fail-under=94.5
uv build
uv run python scripts/check_mcp.py
uv run aspenops dry-run examples/batch-request.example.json
uv run aspenops benchmark --points 4 --workers 1,2
uv run aspenops certify examples/batch-request.example.json \
  --output var/ci/readme-certification.json \
  --repeats 2
```

The repository pytest configuration also enforces:

```text
minimum pytest 8.3
strict markers
strict configuration
strict xfail
ResourceWarning = error
```

---

## Automated test and quality gates

AspenOps retains four long-lived workflows with distinct responsibilities. None should be described alone as “complete Aspen certification.”

| Workflow | Trigger | Environment | Scope | Evidence |
|---|---|---|---|---|
| `ci.yml` | main push, PR, manual | Ubuntu; Python 3.11/3.12/3.13 | full pytest, branch coverage, Ruff, formatting, mypy, build, Mock, MCP, wheel and README command smoke | JUnit, JSON coverage, logs and CLI outputs |
| `windows-control-plane.yml` | main push, PR, manual | `windows-latest`; Python 3.12 | Windows Job/process ownership, IPC, scheduler, archives, fake Aspen/HYSYS and licensed-certification interfaces | JUnit and Windows diagnostics |
| `generate-performance-evidence.yml` | manual | Ubuntu; Python 3.12 | exact baseline/candidate, independent trials and stable regression policy | raw samples and comparison reports |
| `licensed-aspen-certification.yml` | protected manual dispatch | self-hosted licensed Windows | exact SHA, software regression, preflight, real COM, signed evidence and human-review boundary | JUnit, preflight, signed report and ZIP |

### Portable CI requirements

- GitHub Actions are pinned to immutable commit SHAs.
- Checkout does not retain write credentials.
- `uv.lock` must be current and dependency sync is frozen.
- Python 3.11, 3.12 and 3.13 each run the complete test suite.
- `ResourceWarning` fails the run.
- Combined branch-aware coverage must remain at least 94.5%.
- JUnit, JSON coverage, the 20 slowest tests and logs are retained.
- The built wheel must pass version, help, Demo and key CLI smoke tests.
- README dry-run, benchmark and certification commands are exercised automatically.
- The MCP surface must remain exactly 14 controlled tools.
- Stable performance regressions beyond policy thresholds fail the gate.

### Public Windows control plane

The hardened selected suite covers:

- Windows Job Object and process-ownership boundaries;
- Worker protocol, timeout, taint recycling and singleflight behavior;
- active scheduler leases;
- convergence and fake Aspen Plus/HYSYS adapters;
- ZIP traversal, compression-bomb and evidence-bundle limits;
- licensed-certification CLI, workflow and signed-bundle interfaces;
- Windows CLI and Doctor smoke.

Based on the archived JUnit inventory, the hardened selection contains 127 tests. That becomes fresh execution evidence only after the revised workflow completes successfully.

### Coverage audit

The aggregate coverage is strong but has only about 0.47 percentage points of headroom over the current gate. Future tests should prioritize:

```text
scheduler.py
pool.py
worker.py
provenance.py
batch.py
convergence.py
```

The global floor should not be raised merely for appearance before the remaining branches in those high-complexity modules are covered. See the [automated test audit](docs/automated-test-audit-2026-07-22.md) for module-level data and the full 72-module inventory.

### What public automation does not prove

Public CI does not prove that:

- a commercial Aspen release can be instantiated on a particular workstation;
- a specific `.bkp`, `.apwz` or `.hsc` model converges;
- property methods, reactions and equipment assumptions are engineering-correct;
- Mock orchestration performance equals real Aspen solve performance;
- software can self-grant final real-Aspen engineering certification.

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
uv lock --check
uv sync --frozen --extra windows --extra dev --extra agent --extra signing
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

Effective concurrency is bounded by:

```text
W_effective = min(W_configured, W_license, W_memory, W_stability)
```

Throughput gains come from persistent sessions, one batched RPC per point, request deduplication, content-addressed caching, dynamic task claiming, private model parallelism and worker recycling. Portable Mock benchmarks must not be presented as licensed Aspen solve-performance claims.

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

It requires:

- an exact approved 40-character commit SHA;
- a current lockfile and frozen dependency environment;
- 104 targeted licensed-certification and backend software tests before COM is opened;
- preflight validation;
- explicit authorization before real execution;
- signed evidence verification;
- `PENDING_REAL_ASPEN_CERTIFICATION` until human engineering review is complete.

Software cannot self-grant engineering certification.

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
src/aspenops_nexus/          runtime, adapters, scheduling, validation and evidence
tests/                       72 archived test modules; unit, integration and fault edges
examples/                    Mock, request, registry and certification-plan examples
docs/                        architecture, performance, quality, test audit and certification
scripts/                     setup, benchmark and interface verification utilities
.github/workflows/
  ci.yml
  windows-control-plane.yml
  generate-performance-evidence.yml
  licensed-aspen-certification.yml
```

---

## Troubleshooting

### `uv lock --check` fails

`pyproject.toml` and `uv.lock` disagree. Update and review the lockfile explicitly; do not remove `--frozen` from CI to hide the problem.

### Local tests pass but coverage fails in CI

Confirm that `--cov-branch` is enabled and inspect both JSON coverage and `term-missing`. The current gate is 94.5% combined branch-aware coverage, not statement coverage alone.

### `doctor --probe` cannot find Aspen

Check native 64-bit Windows, pywin32, Automation Server registration, Python/Aspen bitness and optional explicit ProgID pins.

### `Run2()` returns but `ok=false`

Inspect convergence evidence, constraint violations, conservation residuals and Aspen error nodes. Engine return is only one of five validity gates.

### More workers make the batch slower

Reduce concurrency and inspect license waiting, memory, model-open time, solve-time distribution and worker-recycling thresholds. More concurrency is not automatically more throughput.

### Public CI is green; is real Aspen certified?

No. Public CI proves the control plane. Real Aspen qualification requires `licensed-aspen-certification.yml` on a licensed self-hosted Windows host and process-engineering review.

---

## Honest boundary and roadmap

AspenOps 2.0 provides:

- an Aspen Plus steady-state COM automation control plane;
- a controlled HYSYS Spreadsheet Bridge;
- CLI, Python and local STDIO MCP surfaces;
- durable batch execution, caching, concurrency, timeout, validation, optimization and evidence;
- a licensed-certification plan, signed evidence bundle and human-review gate.

It does not claim that:

- public Linux CI has executed real Aspen;
- every Aspen version, module or model works without qualification;
- `Run2()` returning proves thermodynamic or engineering correctness;
- the entire HYSYS object model is uniformly wrapped;
- steady-state adapters cover Aspen Dynamics, ACM, every PBE or every dynamic model;
- an LLM replaces property-method selection, reaction modeling, equipment design or engineering review.

Priorities:

1. retain fresh green evidence for the hardened workflows;
2. add targeted branch tests for scheduler, pool, worker and provenance;
3. run licensed Aspen Plus and HYSYS qualification on approved non-confidential cases;
4. establish versioned qualification cases and semantic-registry evidence;
5. create reproducible real-license and real-hardware throughput baselines;
6. preserve one authoritative `main` branch and the minimal long-lived workflow set.

---

## License

Apache-2.0. Aspen Plus, Aspen HYSYS, model files, databases, vendor documentation and licenses remain governed by their respective terms. AspenOps does not include Aspen software, licenses or proprietary models.
