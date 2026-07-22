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
| Public matrix | Python 3.11, 3.12 and 3.13 |
| Archived portable baseline | Actions run `29814739487` |
| Python 3.12 baseline | 72 modules, 563 passed, 0 failed, 0 skipped, 16.73 s |
| Combined branch-aware coverage | 94.9719800747198% |
| Statement / branch coverage | 96.23677786818551% / 90.84880636604774% |
| Coverage floor | 94.5% |
| Archived public Windows baseline | Actions run `29814739334`, 104 passed, 2.06 s |
| MCP tools | 14 |
| Licensed Aspen certification | Licensed Windows, approved case and engineering review still required |

These values come from inspected JUnit, coverage JSON and logs. They are an archived validated baseline—not an automatic claim about every later commit. The badges are scoped to `main` push runs.

The current workflow surface was also validated in isolation:

```text
15/15 workflow-governance and licensed-workflow tests passed
4/4 GitHub Actions YAML files parsed
all Bash run blocks passed bash -n syntax checks
PowerShell AST parsing is enforced by the Windows workflow
```

Public CI validates the AspenOps control plane. It does not certify a commercial Aspen installation or an engineering model.

---

## What AspenOps is

AspenOps is not a thin `win32com` wrapper or a natural-language GUI macro. It is the deterministic execution layer between an AI coding agent and a stateful, version-sensitive, license-constrained process simulator.

```text
The agent decides what experiment to run.
Aspen solves thermodynamics and flowsheet equations.
AspenOps decides whether the action is authorized, dimensionally valid,
converged, feasible, balanced, reproducible and auditable.
```

### Non-negotiable invariants

1. One COM object belongs to one spawned Windows process and one STA apartment.
2. Agents use semantic variables and never invent raw Aspen tree paths.
3. Every Worker opens a private staged model copy.
4. Reset, bulk write, solve, bulk read and verification cross IPC once per point.
5. Hard timeout terminates only ownership-verified AspenOps processes.
6. Transport, engine return, convergence, feasibility and balance closure are separate states.
7. Mock CI validates the control plane, never licensed Aspen physics.
8. Licensed results still require process-engineering review.

A point is accepted only when:

```text
communication_ok
AND engine_ok
AND converged
AND feasible
AND balances_passed
```

---

## Architecture

```text
Agent / CLI / Python
        │ typed semantic requests
        ▼
AspenOps Control Plane
policy · registry · units · bounds · scheduler · cache · evidence
        │ one batched RPC per point
        ▼
Persistent CasePool
private process · COM STA · private model copy
        │
        ├── Aspen Plus
        ├── Aspen HYSYS
        └── deterministic Mock backend
```

Core capabilities include process isolation, semantic authorization, engineering-unit algebra, hard timeouts, license-aware concurrency, content-addressed caching, durable SQLite-WAL jobs, evidence bundles, DOE, constrained optimization and repeatability gates.

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

| Workflow | Trigger | Environment | Responsibility |
|---|---|---|---|
| `ci.yml` | `main` push, PR, manual | Ubuntu; Python 3.11/3.12/3.13 | full tests, branch coverage, Ruff, format, mypy, build, Mock, MCP, wheel and README command smoke |
| `windows-control-plane.yml` | `main` push, PR, manual | `windows-latest`; Python 3.12 | process ownership, Job Objects, IPC, scheduler, archives, fake Aspen/HYSYS, PowerShell AST and workflow governance |
| `generate-performance-evidence.yml` | manual | Ubuntu; Python 3.12 | immutable baseline, independent trials and stable regression policy |
| `licensed-aspen-certification.yml` | protected manual | self-hosted licensed Windows | exact SHA, path gates, software regression, preflight, real COM, signed evidence and human review |

### Workflow governance

Tests enforce:

- third-party Actions pinned to full 40-character commit SHAs;
- read-only contents permission and non-persistent checkout credentials;
- no `pull_request_target`, writable contents or silent `continue-on-error`;
- checked and frozen dependencies everywhere;
- both named `uses:` steps and shorthand `- uses:` steps audited;
- no direct manual-input interpolation inside shell bodies;
- a fixed trusted performance concurrency group;
- baseline refs resolved to immutable commits before worktree creation;
- artifact names based on `github.run_id` rather than arbitrary inputs;
- a one-line repository-relative licensed plan path constrained to the workspace;
- a one-line absolute licensed state directory inside absolute allowed roots;
- canonical paths passed through `GITHUB_ENV`;
- PowerShell AST parsing of `scripts/setup_windows.ps1` on Windows;
- Windows bootstrap loading `.env`, preserving process PATH and checking exit codes.

Coverage is above the floor but has limited headroom. Future tests should prioritize `scheduler.py`, `pool.py`, `worker.py`, `provenance.py`, `batch.py` and `convergence.py` before raising the threshold.

---

## Windows with Aspen Plus or HYSYS

Prerequisites include native 64-bit Windows, Python 3.11–3.13, licensed Aspen, an approved non-confidential convergent model, a verified semantic registry and absolute allowed model/result roots.

```powershell
git clone https://github.com/SUNHAOJUN22/AspenOps-Agent.git
cd AspenOps-Agent
powershell -ExecutionPolicy Bypass -File scripts/setup_windows.ps1
```

The bootstrap:

1. enables strict PowerShell behavior;
2. installs `uv` only when missing;
3. refreshes machine/user PATH while retaining process PATH;
4. verifies `uv`;
5. checks `uv.lock`;
6. performs a frozen `windows + agent + dev + signing` install;
7. creates and imports `.env`;
8. runs Doctor with the loaded backend;
9. checks native command exit codes.

A newly copied `.env` uses Mock. Change it to `aspen_plus` or `hysys` and rerun before real work.

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

AspenOps honors explicit ProgID pins, scans both Windows registry views, discovers versioned Aspen Plus and HYSYS Automation Servers, sorts numeric registrations newest-first, creates isolated instances with `DispatchEx`, retains unversioned fallbacks and records the actual successful ProgID and application version.

Discovery is not certification. Formal compatibility still requires the target Aspen version, a valid license, an approved case and engineering review.

---

## CLI and MCP

The CLI supports Demo, Doctor, dry-run, batch execution, durable submission/status, benchmark, optimization, repeatability, licensed preflight/execution and normal/signed bundle verification.

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

It exposes no arbitrary shell, Python, VBA, `eval`, unrestricted COM call or raw tree-path mutation tool.

---

## Performance

```text
T_naive ≈ N × (T_start + T_open + T_solve + T_read)

T_pool ≈ W × (T_start + T_open)
       + N_unique / W × (T_solve + T_verify)
       + T_IPC + T_schedule

W_effective = min(W_configured, W_license, W_memory, W_stability)
```

Gains come from persistent sessions, batched IPC, deduplication, caching, dynamic task claiming, private-model parallelism and Worker recycling. Portable Mock results must not be represented as licensed Aspen solve performance.

---

## Three certification levels

1. **Control-plane certification** on the deterministic Mock backend.
2. **Licensed-simulator runtime certification** on native Windows with Aspen, a valid license and an approved case.
3. **Engineering model validation** owned by the process engineer.

The protected licensed workflow performs:

```text
exact approved SHA
→ canonical plan and state paths
→ frozen dependencies
→ isolated Mock software regression
→ preflight
→ explicit human approval
→ real COM execution
→ signed bundle verification
→ engineering review
```

The runtime remains `PENDING_REAL_ASPEN_CERTIFICATION`; software cannot self-grant engineering certification.

---

## Security and honest boundary

Never commit customer Aspen models, proprietary kinetics or property parameters, production DCS data, license files, sensitive license-server information, credentials, internal hosts, confidential evidence bundles or signing private keys.

Public automation does not prove that any commercial Aspen version starts on a given host, that an arbitrary model converges, that property methods and equipment assumptions are correct, that Mock performance equals real Aspen performance, or that software can replace process-engineering judgment.

---

## License

Apache-2.0. Aspen products, models, databases, vendor documentation and licenses remain governed by their respective terms. AspenOps does not include Aspen software, licenses or proprietary models.
