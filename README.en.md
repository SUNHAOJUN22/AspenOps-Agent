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

These values come from inspected JUnit, coverage JSON and logs. They are an archived validated baseline—not an automatic claim about every later commit. The badges are scoped to current `main` push runs.

Current `main` additionally enforces:

- real-backend environment loading and direct `Settings(...)` construction fail when `ASPENOPS_ALLOWED_ROOTS` is absent;
- state, model, registry, CLI-output and evidence paths remain inside resolved allowed roots;
- licensed targets use realpath resolution to reject `..`, symlink and junction escapes;
- the approved certification commit must belong to trusted `main` history;
- real signing keys are absent from dependency setup and isolated Mock regression;
- both Windows gates run direct-settings, backend-escalation, CLI-output and realpath tests;
- CI audits the frozen Python 3.12 dependency graph for both Linux and Windows and stores JSON vulnerability evidence.

Public CI validates the control plane. It does not certify a commercial Aspen installation or an engineering model.

---

## What AspenOps is

AspenOps is not a thin `win32com` wrapper or a natural-language GUI macro. It is the deterministic execution layer between an AI coding agent and a stateful, version-sensitive, license-constrained simulator.

```text
The agent decides what experiment to run.
Aspen solves thermodynamics and flowsheet equations.
AspenOps decides whether the action is authorized, dimensionally valid,
converged, feasible, balanced, reproducible and auditable.
```

Non-negotiable invariants:

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
┌────────────────────────────────────────────────────────────────────┐
│ Codex / Claude Code / MCP Client / Python                          │
│ typed variables, DOE, constraints, objectives and result requests  │
└──────────────────────────────┬─────────────────────────────────────┘
                               │ MCP / CLI / JSON
                               ▼
┌────────────────────────────────────────────────────────────────────┐
│ AspenOps Control Plane                                             │
│ policy · registry · units · scheduler · cache · evidence · audit   │
│ certification · optimization                                      │
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

uv audit --frozen --python-platform linux --python-version 3.12
uv audit --frozen --python-platform windows --python-version 3.12
uv build
uv run python scripts/check_mcp.py
uv run aspenops --version
uv run aspenops --help
uv run aspenops demo
```

Repository pytest policy requires pytest 8.3+, strict markers/configuration/xfail and treats `ResourceWarning` as an error.

---

## Automated workflows

Only four authoritative workflows remain:

| Workflow | Trigger | Pinned environment | Responsibility |
|---|---|---|---|
| `ci.yml` | `main` push, PR, manual | `ubuntu-24.04`; Python 3.11/3.12/3.13 | full tests, branch coverage, Ruff, formatting, mypy, frozen-dependency vulnerability audit, build, Mock, MCP, locked-dependency Wheel and README commands |
| `windows-control-plane.yml` | `main` push, PR, manual | `windows-2025`; Python 3.12 | Windows Jobs, ownership, IPC, scheduling, archives, Fake Aspen/HYSYS, PowerShell AST, path and workflow governance |
| `generate-performance-evidence.yml` | manual | `ubuntu-24.04`; Python 3.12 | immutable baseline, independent trials and stable-regression policy |
| `licensed-aspen-certification.yml` | protected manual | `self-hosted, windows, x64, aspen-licensed` | trusted-main SHA, realpath gate, Mock regression, preflight, real COM, signed evidence and human review |

Hosted runners, third-party Actions and `uv` are pinned. Workflows and Windows setup require **uv 0.11.16**, which provides the JSON audit output used by CI. Installation always checks `uv.lock` and uses `--frozen`.

### Workflow governance

Automated tests require:

- third-party Actions pinned to full 40-character commit SHAs;
- exact `uv 0.11.16`, with a regression assertion that JSON dependency auditing cannot be paired with an older tool;
- read-only repository permission and non-persistent checkout credentials;
- no `pull_request_target`, `contents: write` or silent `continue-on-error`;
- `set -euo pipefail` in every Bash step;
- input-injection scanning for literal, folded, inline and shorthand `run` syntax;
- no direct workflow-dispatch input interpolation inside shell commands;
- a fixed performance concurrency group and immutable baseline SHA resolution;
- artifact names based on `github.run_id`, not arbitrary input;
- licensed commits restricted to trusted `main` ancestry;
- state, model, registry, output and evidence targets restricted to resolved absolute roots;
- realpath checks against traversal, symlink and junction escapes;
- signing secrets excluded from dependency setup and Mock regression;
- PowerShell AST parsing of `scripts/setup_windows.ps1`;
- both Windows gates running direct-settings, backend-policy and realpath tests.

### Locked-dependency Wheel smoke

Portable CI exports hash-pinned runtime requirements from `uv.lock`, synchronizes a clean environment with `uv pip sync --require-hashes`, installs the built Wheel with `--offline --no-deps`, runs `uv pip check`, then exercises version, help, Demo and critical CLI surfaces. It does not re-resolve runtime dependencies during Wheel verification.

### Coverage policy

The archived aggregate has about 0.47 percentage points of margin over the 94.5% floor. Future tests should prioritize `scheduler.py`, `pool.py`, `worker.py`, `provenance.py`, `batch.py` and `convergence.py` before raising the global floor.

---

## Windows with Aspen Plus or HYSYS

Prerequisites:

- native 64-bit Windows;
- Python 3.11–3.13;
- `uv >= 0.11.16`;
- licensed Aspen Plus and/or Aspen HYSYS;
- a known license-seat limit;
- a non-confidential case already convergent in the GUI;
- a verified case-specific semantic registry;
- non-empty absolute existing allowed roots;
- absolute state, model, registry, result and evidence paths inside those roots.

Real-backend configuration fails during `Settings` construction if allowed roots are absent or the state directory is outside them. It does not reach Aspen preflight or create state files.

```powershell
git clone https://github.com/SUNHAOJUN22/AspenOps-Agent.git
cd AspenOps-Agent
powershell -ExecutionPolicy Bypass -File scripts/setup_windows.ps1
```

The script installs or validates `uv >= 0.11.16`, preserves the process PATH, checks the lock, performs a frozen `windows + agent + dev + signing` install, creates and loads `.env`, then runs `doctor --probe` with the loaded configuration.

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

## CLI and MCP

Primary CLI commands: `demo`, `doctor`, `dry-run`, `run-batch`, `submit`, `job`, `benchmark`, `optimize`, `certify`, `certification-preflight`, `certify-licensed`, `verify-licensed-bundle`, `verify-bundle` and `mcp`.

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

There is no arbitrary shell, Python, VBA, `eval`, unrestricted COM method or raw tree-path mutation tool.

---

## Performance and certification boundary

```text
T_naive ≈ N × (T_start + T_open + T_solve + T_read)
T_pool ≈ W × (T_start + T_open)
       + N_unique / W × (T_solve + T_verify)
       + T_IPC + T_schedule
W_effective = min(W_configured, W_license, W_memory, W_stability)
```

Portable Mock benchmarks must never be described as licensed Aspen solve performance.

Three levels remain distinct:

1. **Control-plane certification** through deterministic Mock infrastructure.
2. **Licensed-simulator runtime certification** on native licensed Windows with an approved case.
3. **Engineering-model validation** owned by the process engineer.

Licensed sequence:

```text
exact approved SHA belonging to trusted main history
→ frozen dependencies
→ isolated Mock regression without real signing secrets
→ realpath and symlink-escape validation
→ preflight
→ explicit human authorization
→ scoped real COM execution
→ signed-bundle verification
→ human engineering review
```

The runtime can only emit `PENDING_REAL_ASPEN_CERTIFICATION`; it cannot self-grant engineering certification.

---

## Security and data boundary

Never commit customer Aspen cases, proprietary kinetics/property data, production DCS data, license material, credentials, internal host information, confidential evidence bundles or signing private keys. Use the narrowest allowed roots, license seats and Worker limits.

## License

Code is Apache-2.0. Aspen products, model files, databases, vendor documentation and licenses remain subject to their own terms. AspenOps does not include Aspen software, licenses or proprietary cases.
