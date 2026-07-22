<div align="center">

# AspenOps 2.0

## A deterministic, isolated and auditable control plane for Aspen Plus, Aspen HYSYS and AI coding agents

### Codex / Claude Code / MCP → typed process intent → isolated execution → Aspen solve → engineering decision → reproducible evidence

**AspenOps is not a GUI macro and does not expose arbitrary COM to an LLM.**  
**It enforces authorization, paths, units, convergence, constraints, balances, concurrency, audit and evidence.**

[中文](README.md) · [Architecture](docs/architecture.md) · [Windows Setup](docs/windows-setup.md) · [Performance](docs/performance.md) · [Certification](docs/certification.md) · [Test Audit](docs/automated-test-audit-2026-07-22.md) · [Quality Report](docs/quality-report.md) · [Security](SECURITY.md)

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
| Archived portable run | Actions run `29814739487` |
| Archived Python 3.12 result | 72 test modules, 563 passed, 0 failed, 0 skipped, 16.73 s |
| Combined branch-aware coverage | 94.9719800747198% |
| Statement / branch coverage | 96.23677786818551% / 90.84880636604774% |
| CI coverage floor | 94.5% |
| Archived public Windows run | Actions run `29814739334`, 104 passed, 2.06 s |
| MCP tools | 14 |
| Licensed Aspen status | `PENDING_REAL_ASPEN_CERTIFICATION` |

These numbers are an **archived validated baseline** extracted from inspected JUnit, coverage JSON and logs. They are **not an automatic claim** about every later commit. The badges show the platform status of current `main` pushes; historical evidence is never substituted for a fresh Actions result.

Public CI validates the control plane, path policy, process isolation, scheduling, archives and interfaces. It cannot certify a commercial Aspen installation, a license, a property method or an engineering model.

---

## Definition

> AspenOps turns a stateful, blocking, version-sensitive and license-constrained desktop simulator into a deterministic execution engine for agents, CLI users and Python workflows.

```text
The agent decides what experiment to run.
Aspen solves thermodynamics and flowsheet equations.
AspenOps decides whether the action is authorized, dimensionally valid,
converged, feasible, balanced, reproducible and auditable.
```

---

## Architecture

```text
┌────────────────────────────────────────────────────────────────────┐
│ Codex / Claude Code / MCP Client / Python                          │
│ typed variables, DOE, constraints, objectives and result requests  │
└──────────────────────────────┬─────────────────────────────────────┘
                               │ typed MCP / CLI / JSON
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

Non-negotiable invariants:

1. One COM object belongs to one spawned Windows process and one STA apartment.
2. Agents use semantic variables instead of inventing raw Aspen tree paths.
3. Every Worker opens a private model copy and never overwrites the master model.
4. Each point crosses IPC once for reset, bulk write, solve, bulk read and verification.
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

## Quick start without Aspen

Requirements: Python 3.11–3.13 and `uv >= 0.11.16`.

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

The first-run `.env.example` uses the Mock backend, an empty allowlist and a repository-local state directory, so copying it does not impose Windows paths on Linux or macOS.

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

UV_PREVIEW_FEATURES=json-output uv audit --frozen \
  --python-platform linux --python-version 3.11 --output-format json
UV_PREVIEW_FEATURES=json-output uv audit --frozen \
  --python-platform windows --python-version 3.11 --output-format json

uv build
uv run python scripts/check_mcp.py
uv run aspenops --version
uv run aspenops --help
uv run aspenops demo
```

CI audits Linux and Windows for Python 3.11, 3.12 and 3.13: **six** supported combinations. All six execute even when one reports a vulnerability or service failure. Each combination retains JSON and stderr evidence, JSON is validated, and the quality job fails once collection is complete if any target failed.

Repository pytest policy requires pytest 8.3+, strict markers, strict configuration and strict xfail, and treats `ResourceWarning` as an error.

---

## Four authoritative workflows

| Workflow | Trigger | Pinned environment | Responsibility |
|---|---|---|---|
| `ci.yml` | `main` push, PR, manual | `ubuntu-24.04`; Python 3.11/3.12/3.13 | full tests, coverage, Ruff, formatting, mypy, six dependency audits, build, Mock, MCP, Wheel and README commands |
| `windows-control-plane.yml` | `main` push, PR, manual | `windows-2025`; Python 3.12 | Windows Jobs, ownership, IPC, scheduling, archives, Fake Aspen/HYSYS, PowerShell AST and executable helper contracts, path, documentation and workflow governance |
| `generate-performance-evidence.yml` | manual | `ubuntu-24.04`; Python 3.12 | immutable baseline, independent trials and stable-regression policy |
| `licensed-aspen-certification.yml` | protected manual | `self-hosted, windows, x64, aspen-licensed` | trusted-main SHA, Mock regression, realpath gate, preflight, real COM, signed evidence and human review |

Hosted runner images, third-party Actions and `uv 0.11.16` are pinned. Every install first checks `uv.lock` and then uses `uv sync --frozen`.

### Automated governance

The repository rejects:

- third-party Actions not pinned to full commit SHAs;
- drifting runner labels such as generic latest images;
- writable repository permission, retained checkout credentials or `pull_request_target`;
- silent `continue-on-error`;
- unfrozen dependency installation;
- Bash steps without `set -euo pipefail`;
- direct manual-input interpolation in literal, folded, inline or shorthand `run` syntax;
- raw baseline refs used for worktree execution;
- arbitrary user input in artifact names;
- incomplete six-target audits, missing stderr evidence, invalid JSON or failure before all targets run;
- stale tool versions, runner names, workflow names, AspenOps titles or broken local documentation links;
- removal of required path, backend and documentation tests from either Windows gate;
- removal of the Windows `LibraryMode` helper behavior gate while leaving only static string checks.

### Locked-dependency Wheel verification

Portable CI exports hash-pinned runtime dependencies from `uv.lock`, synchronizes a clean environment with `uv pip sync --require-hashes`, installs the built Wheel with `--offline --no-deps`, runs `uv pip check`, then exercises critical CLI surfaces. The Wheel gate does not re-resolve dependency versions from the network.

### Documentation contracts

`tests/test_documentation_contracts.py` checks that:

- the Chinese and English READMEs, Security, Architecture, Performance, Windows guide, quality report, test audit and certification guide exist;
- repository-local Markdown links resolve and cannot escape the repository;
- `uv 0.11.16`, `ubuntu-24.04`, `windows-2025`, AspenOps 2.0 titles and all four workflow names stay synchronized;
- obsolete workflow names and drifting runner labels do not return;
- both READMEs describe all six dependency-audit targets;
- `.env.example` remains a portable Mock first-run configuration;
- archived evidence and real-certification boundaries remain explicit.

---

## Windows with Aspen Plus or HYSYS

Prerequisites:

- native 64-bit Windows;
- Python 3.11–3.13;
- `uv >= 0.11.16`;
- Aspen Plus and/or Aspen HYSYS;
- a valid license and known seat limit;
- a non-confidential case already convergent in the GUI;
- a verified case-specific semantic registry;
- non-empty, absolute, existing allowed roots;
- absolute state, model, registry, result and evidence paths inside those roots.

A real backend without `ASPENOPS_ALLOWED_ROOTS`, or with a state directory outside them, fails during `Settings` construction. It does not reach Aspen preflight and does not create state files.

```powershell
git clone https://github.com/SUNHAOJUN22/AspenOps-Agent.git
cd AspenOps-Agent
powershell -ExecutionPolicy Bypass -File scripts/setup_windows.ps1
```

The bootstrap:

1. enables strict PowerShell behavior;
2. installs missing `uv` through winget;
3. tries `uv self update` first for an old standalone installation, with PATH modification disabled;
4. falls back to winget upgrade and then winget install when self-update is unavailable or still leaves an old version;
5. re-reads the actual version after every attempt and requires `uv >= 0.11.16`;
6. refreshes machine and user PATH while preserving the current process PATH;
7. checks the lockfile and installs `windows + agent + dev + signing` frozen;
8. creates, validates and imports `.env`;
9. rejects duplicate variables and unbalanced quotes;
10. reports `.env` errors by line number without echoing possible secret values;
11. runs `doctor --probe` with the imported configuration;
12. checks native-command exit codes.

`-LibraryMode` is CI-only: it loads helper functions without installing dependencies or running Doctor. Windows CI executes valid dotenv import, case-insensitive duplicate rejection, unbalanced-quote rejection, secret-safe errors, and self-update → winget fallback order.

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

## Real-backend path policy

The same policy applies to environment loading, direct Python construction, batch requests, CLI outputs and licensed certification:

- real backends require non-empty `ASPENOPS_ALLOWED_ROOTS`;
- roots and state directory must be explicitly absolute;
- state must resolve inside an allowed root;
- request backend must match the configured real backend;
- model, registry, result, normal bundle and licensed output paths remain inside roots;
- realpath checks reject `..`, symlink and Windows junction escapes;
- unsafe configuration fails before Aspen is opened.

---

## Licensed Aspen certification

Authoritative workflow: `licensed-aspen-certification.yml`.

```text
checkout exact approved SHA
→ verify SHA belongs to trusted main history
→ check lockfile and install frozen dependencies
→ run Mock software regression without real keys
→ run documentation, backend, output and workflow contracts
→ validate plan, allowed roots and state with realpath
→ licensed preflight
→ explicit human execution approval
→ scoped real COM execution
→ signed evidence verification
→ final engineering review
```

Software can emit only `PENDING_REAL_ASPEN_CERTIFICATION`. A valid signature proves origin and integrity; it does not approve thermodynamics, reactions, equipment assumptions or intended engineering use.

---

## CLI and MCP

Main CLI surfaces:

| Command | Purpose |
|---|---|
| `aspenops demo` | portable Mock end-to-end demo |
| `aspenops doctor --probe` | host, policy and Automation Server diagnostics |
| `aspenops dry-run REQUEST` | validate paths, semantics, units and concurrency without Aspen |
| `aspenops run-batch REQUEST` | execute a batch and create an integrity bundle |
| `aspenops submit REQUEST` | submit a durable background job |
| `aspenops job JOB_ID` | inspect job state and result |
| `aspenops benchmark` | benchmark portable orchestration |
| `aspenops optimize REQUEST` | run budgeted optimization |
| `aspenops certify REQUEST` | repeatability gate; never grants real certification |
| `aspenops certification-preflight PLAN` | validate a licensed plan without opening COM |
| `aspenops certify-licensed PLAN` | execute an approved plan on a licensed host |
| `aspenops verify-licensed-bundle BUNDLE` | verify signed certification evidence |
| `aspenops verify-bundle BUNDLE` | verify a normal run bundle |
| `aspenops mcp` | start the local STDIO MCP server |

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

## Coverage policy

The archived aggregate is only about 0.47 percentage points above the 94.5% floor. Future tests should prioritize:

```text
scheduler.py
pool.py
worker.py
provenance.py
batch.py
convergence.py
```

The global threshold should not be raised for appearance before these complex boundaries receive stronger tests.

---

## What automation does not prove

Public automation does not prove that:

- every commercial Aspen version starts on a given host;
- every model converges;
- property, reaction and equipment assumptions are correct;
- Mock performance equals real Aspen solve performance;
- software replaces a process engineer;
- software can grant final engineering certification.

---

## Security and license

Do not commit customer models, proprietary properties or kinetics, production DCS data, license files, private keys, tokens, internal hosts, private paths or evidence containing commercial process data.

Code is licensed under Apache-2.0. Aspen products, model files, databases, vendor documentation and licenses remain subject to their own terms. AspenOps does not ship Aspen software, licenses or proprietary models.

<div align="center">

## Let agents design the experiment. Let Aspen solve the physics. Let AspenOps enforce the truth.

</div>
