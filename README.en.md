<div align="center">

# AspenOps 2.0

## A deterministic control plane for Aspen Plus, Aspen HYSYS and AI agents

### Agent / CLI / Python → typed process intent → isolated execution → Aspen solve → engineering decision → reproducible evidence

**AspenOps is not a GUI macro and does not expose arbitrary COM to an LLM.**  
**It enforces authorization, paths, units, convergence, constraints, balances, concurrency, audit and evidence.**

[中文](README.md) · [Architecture](docs/architecture.md) · [Windows Setup](docs/windows-setup.md) · [Performance](docs/performance.md) · [Certification](docs/certification.md) · [Test Audit](docs/automated-test-audit-2026-07-22.md) · [Quality Report](docs/quality-report.md) · [Security](SECURITY.md) · [Contributing](CONTRIBUTING.md)

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
| Archived Python 3.12 result | 72 modules, 563 passed, 0 failed, 0 skipped, 16.73 s |
| Combined branch-aware coverage | 94.9719800747198% |
| Statement / branch coverage | 96.23677786818551% / 90.84880636604774% |
| CI coverage floor | 94.5% |
| Archived public Windows run | Actions run `29814739334`, 104 passed, 2.06 s |
| MCP tools | 14 |
| Licensed Aspen status | `PENDING_REAL_ASPEN_CERTIFICATION` |

These values are an **archived validated baseline** extracted from inspected JUnit, coverage JSON and logs. They are **not an automatic claim** about every later commit. The badges report current `main` push status; historical evidence is never substituted for a fresh Actions result.

Public CI validates the control plane, path policy, process isolation, scheduling, archives and interfaces. It cannot certify a commercial Aspen installation, a license, a property method or an engineering model.

---

## Architecture and validity contract

```text
Agent / CLI / Python
        │ typed MCP / JSON
        ▼
AspenOps Control Plane
Policy · Registry · Units · Scheduler · Cache · Evidence · Audit
        │ one batched RPC per point
        ▼
Private Worker Process · COM STA · Private Model Copy
        │
        ├─ Aspen Plus
        ├─ Aspen HYSYS
        └─ Mock backend
```

Non-negotiable invariants:

1. One COM object belongs to one spawned Windows process and one STA apartment.
2. Agents use semantic variables and never invent arbitrary Aspen Tree Paths.
3. Every Worker opens a private model copy and never overwrites the source model.
4. Hard timeout terminates only ownership-verified AspenOps processes.
5. Transport, engine return, convergence, feasibility and balance closure remain separate gates.
6. Mock CI proves control-plane behavior, never licensed Aspen physics.

A result is accepted only when:

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

`.env.example` defaults to the Mock backend, an empty allowlist and a repository-local state directory. It does not impose Windows-only absolute paths on a first Linux or macOS run.

---

## Complete local quality gate

```bash
uv lock --check
uv sync --frozen --extra dev --extra agent --extra signing
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
uv run aspenops --version
uv run aspenops demo
```

Add `--extra windows` on Windows.

pytest uses strict markers, strict configuration, strict xfail and treats `ResourceWarning` as an error.

---

## Four authoritative workflows

| Workflow | Trigger | Pinned environment | Responsibility |
|---|---|---|---|
| `ci.yml` | `main` push, PR, manual | `ubuntu-24.04`; Python 3.11/3.12/3.13 | full tests, coverage, Ruff, format, mypy, six dependency audits, build, Mock, MCP, Wheel and README commands |
| `windows-control-plane.yml` | `main` push, PR, manual | `windows-2025`; Python 3.12 | Windows Jobs, ownership, IPC, Fake Aspen/HYSYS, PowerShell helpers, path, documentation and workflow governance |
| `generate-performance-evidence.yml` | manual | `ubuntu-24.04`; Python 3.12 | trusted-`main` baseline/candidate, independent trials and stable-regression evidence |
| `licensed-aspen-certification.yml` | protected manual | `self-hosted, windows, x64, aspen-licensed` | trusted-`main` SHA, Mock regression, realpath, real COM, signed evidence and human review |

Hosted runners, third-party Actions and `uv 0.11.16` are pinned. Every workflow grants only `contents: read`; governance tests reject any `*: write`, `write-all`, retained checkout credentials, `pull_request_target` or silent `continue-on-error`.

### Six frozen-dependency audits

CI audits Linux and Windows for Python 3.11, 3.12 and 3.13: **six** combinations.

```text
linux   × 3.11 / 3.12 / 3.13
windows × 3.11 / 3.12 / 3.13
```

Each target writes separate JSON and error logs and validates the JSON. All six targets run even after an individual failure; the quality job fails only after complete diagnostic evidence has been collected.

### Locked-dependency Wheel verification

CI exports hash-pinned runtime requirements from `uv.lock`, creates a clean environment with `uv pip sync --require-hashes`, installs the built Wheel using `--offline --no-deps`, runs `uv pip check`, then exercises critical CLI surfaces. Dependency versions are not re-resolved during Wheel verification.

### Documentation and operating contracts

`tests/test_documentation_contracts.py` derives the package version from `pyproject.toml` and checks that:

- README badges, package version, `__version__`, CHANGELOG and AspenOps titles agree;
- README, AGENTS, CLAUDE, CONTRIBUTING, Security, Architecture, Performance, Windows, quality, audit and certification documents exist;
- repository-local Markdown links resolve and cannot escape the repository;
- AGENTS and CONTRIBUTING require the frozen quality gate;
- `.env.example` remains a portable Mock first-run configuration;
- archived evidence and real-certification boundaries remain explicit.

---

## Trusted performance evidence

Before installing tools or executing Python, `generate-performance-evidence.yml` performs:

```text
checkout candidate
→ fetch trusted main history
→ resolve immutable candidate and baseline SHAs
→ require both SHAs to belong to main
→ require baseline to be an ancestor of candidate
→ create a detached baseline worktree
→ install frozen candidate dependencies
→ run independent trials and stable-regression policy
```

Unmerged, unrelated or reverse-ordered commits cannot produce evidence that looks authoritative. Mock results describe orchestration performance only, not licensed Aspen solve speed.

---

## Windows with Aspen Plus or HYSYS

```powershell
git clone https://github.com/SUNHAOJUN22/AspenOps-Agent.git
cd AspenOps-Agent
powershell -ExecutionPolicy Bypass -File scripts/setup_windows.ps1
```

The bootstrap safely installs or upgrades `uv >= 0.11.16`, preserves the current PATH, installs `windows + agent + dev + signing` frozen, strictly imports `.env`, rejects duplicate variables and unbalanced quotes, reports only line numbers rather than secret values, and runs `doctor --probe` with the imported configuration.

Real backends require non-empty absolute `ASPENOPS_ALLOWED_ROOTS`. State, model, registry, result and evidence paths must resolve inside those roots. realpath checks reject `..`, symlink and Windows junction escapes.

---

## Licensed Aspen certification

```text
checkout exact approved SHA
→ verify SHA belongs to trusted main
→ frozen dependencies and isolated Mock regression
→ plan/root/state realpath validation
→ preflight
→ explicit human approval
→ scoped real COM execution
→ signed-bundle verification
→ verify every evidence file exists and is non-empty
→ copy evidence into var/ci/licensed-evidence
→ upload workspace-local var/ci only
→ final human engineering review
```

On an early failure, the upload action never expands an undefined external state path; only workspace-local diagnostics are eligible. On success, the preflight report, certification report and signed bundle are copied into the workspace before upload.

Software can emit only `PENDING_REAL_ASPEN_CERTIFICATION`. A signature proves origin and integrity; it does not approve property methods, reactions, equipment assumptions or engineering applicability.

---

## CLI and MCP

Primary CLI surfaces: `demo`, `doctor`, `dry-run`, `run-batch`, `submit`, `job`, `benchmark`, `optimize`, `certify`, `certification-preflight`, `certify-licensed`, `verify-licensed-bundle`, `verify-bundle`, `mcp`.

The MCP server exposes exactly 14 narrow tools and provides no arbitrary Shell, Python, VBA, `eval`, unrestricted COM method or raw Tree Path mutation surface.

---

## What automated tests do not prove

Public automation does not prove that every commercial Aspen version starts, every model converges, property/reaction/equipment assumptions are correct, Mock throughput equals real Aspen performance, or software can replace an engineer or self-grant engineering certification.

The code is Apache-2.0. Never commit customer models, proprietary properties or kinetics, production DCS data, license files, private keys, tokens, internal hosts or evidence containing commercial data.
