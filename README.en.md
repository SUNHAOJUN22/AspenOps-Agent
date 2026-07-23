<div align="center">

# AspenOps 2.0

## A deterministic control plane for Aspen Plus, Aspen HYSYS and AI agents

**Agent / CLI / Python → typed process intent → isolated execution → Aspen solve → engineering decision → reproducible evidence**

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
| Archived Python 3.12 result | 72 test modules, 563 passed, 0 failed, 0 skipped, 16.73 s |
| Combined branch-aware coverage | 94.9719800747198% |
| Statement / branch coverage | 96.23677786818551% / 90.84880636604774% |
| Coverage floor | 94.5% |
| Archived public Windows run | Actions run `29814739334`, 104 passed, 2.06 s |
| MCP tools | 14 |
| Licensed Aspen status | `PENDING_REAL_ASPEN_CERTIFICATION` |

These figures are an **archived validated baseline** extracted from inspected JUnit, coverage JSON and logs. They are **not an automatic claim** about every later commit. The badges show current `main` push status; historical numbers never replace fresh Actions evidence.

Public CI validates the control plane, path policy, process isolation, scheduling, archives and interfaces. It cannot certify a commercial Aspen installation, a license, a property method or an engineering model.

---

## Core invariants

```text
Agent / CLI / Python
        │ typed MCP / JSON
        ▼
AspenOps Control Plane
Policy · Registry · Units · Scheduler · Cache · Evidence · Audit
        │ one batched RPC per point
        ▼
Private Worker · COM STA · Private Model Copy
        ├─ Aspen Plus
        ├─ Aspen HYSYS
        └─ Mock
```

1. A COM object belongs to one Windows child process and one STA apartment.
2. Agents use semantic variables and never construct arbitrary Aspen Tree Paths.
3. Every Worker uses a private model copy and never overwrites the master model.
4. Hard timeout recovery terminates only AspenOps-owned processes.
5. Communication, engine return, convergence, feasibility and balances remain separate gates.
6. Mock CI never impersonates licensed Aspen physics certification.

A result is `ok=true` only when all gates pass:

```text
communication_ok
AND engine_ok
AND converged
AND feasible
AND balances_passed
```

---

## Quick start and complete local gate

Requirements: Python 3.11–3.13 and `uv >= 0.11.16`.

```bash
git clone https://github.com/SUNHAOJUN22/AspenOps-Agent.git
cd AspenOps-Agent
uv lock --check
uv sync --frozen --extra dev --extra agent --extra signing
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest -W error::ResourceWarning \
  --cov=aspenops_nexus --cov-branch --cov-fail-under=94.5
uv build
uv run python scripts/check_mcp.py
uv run aspenops demo
uv run aspenops dry-run examples/batch-request.example.json
```

Add `--extra windows` on Windows. `.env.example` defaults to Mock, an empty allowlist and a repository-local state directory, keeping first use portable.

---

## Four authoritative workflows

| Workflow | Pinned environment | Responsibility |
|---|---|---|
| `ci.yml` | `ubuntu-24.04`; Python 3.11/3.12/3.13 | full tests, coverage, Ruff, mypy, six dependency audits, build, Wheel, Mock, MCP and README commands |
| `windows-control-plane.yml` | `windows-2025`; Python 3.12 | Windows Jobs, IPC, Fake Aspen/HYSYS, PowerShell helpers, path, documentation and governance contracts |
| `generate-performance-evidence.yml` | `ubuntu-24.04`; Python 3.12 | explicit non-main failure, trusted comparison, two frozen environments, repeated trials and stable-regression evidence |
| `licensed-aspen-certification.yml` | `ubuntu-24.04` guard → `self-hosted, windows, x64, aspen-licensed` | explicit non-main failure, trusted SHA, realpath, real COM, signed evidence and human review |

Hosted runners, third-party Actions and `uv 0.11.16` are pinned. Workflows grant only `contents: read`; governance rejects block, commented or inline `*: write`, `write-all`, retained checkout credentials, `pull_request_target` and silent `continue-on-error`.

### Six frozen dependency audits

CI audits Linux and Windows for Python 3.11, 3.12 and 3.13: **six** combinations.

```text
Linux and Windows × Python 3.11, 3.12 and 3.13
```

Each target retains JSON and stderr logs and validates the JSON. One failure does not prevent the remaining evidence from being collected; the quality job fails once after all six finish.

### Locked-dependency Wheel

Runtime requirements are exported from `uv.lock` with hashes, synchronized with `uv pip sync --require-hashes`, and the Wheel is installed with `--offline --no-deps`. CI then runs `uv pip check` and critical CLI smoke without re-resolving versions.

---

## Trusted, isolated and stale-proof performance evidence

The first performance step runs on Ubuntu and checks the event ref. A ref other than `refs/heads/main` writes the observed ref and guard log into runner-temporary evidence, then **fails explicitly with exit code 2** instead of appearing as skipped. The default baseline is the validated main-history runtime:

```text
ebef32ee1f2be74df5d5c5489e7ca86d35ac7bb2
```

```text
explicitly verify GITHUB_REF == refs/heads/main
→ checkout the current trusted main workflow revision
→ fetch main history and tags
→ resolve candidate_ref / baseline_ref with --end-of-options
→ require both SHAs to belong to main
→ require baseline to be an ancestor of candidate
→ detached checkout of the validated candidate SHA
→ create a detached baseline worktree
```

The manual candidate input is never passed directly to `actions/checkout`. Both lockfiles are checked independently, both environments use `uv sync --frozen`, and each revision runs its own repository script:

```text
candidate/uv.lock → candidate .venv → candidate benchmark script
baseline/uv.lock  → baseline .venv  → baseline benchmark script
```

Every current-run log, JSON result and report is written only to `$RUNNER_TEMP/aspenops-performance-evidence`; upload reads it through the supported `${{ runner.temp }}` context and never reads tracked `var/benchmarks` files from the candidate workspace.

Mock performance is orchestration evidence, not licensed Aspen solve speed.

---

## Windows and real backends

```powershell
powershell -ExecutionPolicy Bypass -File scripts/setup_windows.ps1
```

The bootstrap safely installs or upgrades `uv >= 0.11.16`, preserves PATH, installs `windows + agent + dev + signing` frozen, strictly imports `.env`, rejects duplicate variables and unbalanced quotes, reports line numbers without echoing possible secrets, and runs `doctor --probe`.

Real backends require non-empty absolute `ASPENOPS_ALLOWED_ROOTS`. State, model, registry, result and evidence paths must resolve inside those roots. Realpath checks reject `..`, symlink and Windows junction escapes.

---

## Licensed Aspen certification

The licensed workflow first runs a fixed `ubuntu-24.04` guard job. A non-main dispatch fails explicitly and never occupies the self-hosted Aspen license machine. Only after the guard succeeds does the `certify` job enter `self-hosted, windows, x64, aspen-licensed`. The approved input SHA is never passed directly to `actions/checkout`.

```text
Ubuntu guard explicitly verifies GITHUB_REF == refs/heads/main
→ checkout the current trusted main workflow revision
→ validate SHA format, commit existence and main ancestry
→ detached checkout of the validated approved SHA and verify HEAD
→ validate the plan path in that checkout
→ frozen dependencies and isolated Mock regression
→ realpath → preflight → explicit human approval → real COM
→ signed-bundle verification → require all evidence files to be non-empty
→ clean staging in var/ci/licensed-evidence
→ upload workspace var/ci only → engineering review
```

Early failures never expand an undefined external state path; successful evidence first enters a clean workspace staging directory. Software can produce only `PENDING_REAL_ASPEN_CERTIFICATION`; a signature is not engineering approval.

---

## Documentation, CLI and MCP contracts

`tests/test_documentation_contracts.py` derives the version from `pyproject.toml` and checks README, `__version__`, CHANGELOG, AGENTS, CLAUDE, CONTRIBUTING and core documents. Local links cannot escape the repository, operating guides must use frozen quality gates, and chat-internal citation or `sandbox:/` markup cannot enter repository Markdown.

Primary CLI commands: `demo`, `doctor`, `dry-run`, `run-batch`, `submit`, `job`, `benchmark`, `optimize`, `certify`, `certification-preflight`, `certify-licensed`, `verify-licensed-bundle`, `verify-bundle`, and `mcp`.

MCP exposes exactly 14 narrow tools. It does not expose arbitrary Shell, Python, VBA, `eval`, unrestricted COM methods or raw Tree Path writes.

---

## What automation does not prove

Automation does not prove that every Aspen version starts, every model converges, or property methods, reactions and equipment assumptions are engineering-correct. It cannot replace a process engineer or self-grant real certification.

The code is Apache-2.0. Never commit customer models, proprietary thermodynamics or kinetics, production DCS data, licenses, private keys, tokens, internal hosts or commercial evidence bundles.
