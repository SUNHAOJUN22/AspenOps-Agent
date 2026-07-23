<div align="center">

# AspenOps 2.0

## A deterministic control plane for Aspen Plus, Aspen HYSYS and AI agents

**Agent / CLI / Python → typed process intent → isolated execution → Aspen solve → engineering decision → reproducible evidence**

[中文](README.md) · [Architecture](docs/architecture.md) · [Process Intent IR](docs/process-intent-ir.md) · [External Agent Integration](docs/external-agent-integration.md) · [Windows Setup](docs/windows-setup.md) · [Performance](docs/performance.md) · [Certification](docs/certification.md) · [Test Audit](docs/automated-test-audit-2026-07-22.md) · [Quality Report](docs/quality-report.md) · [Security](SECURITY.md) · [Contributing](CONTRIBUTING.md)

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
| `ci.yml` | `ubuntu-24.04`; Python 3.11/3.12/3.13 | full tests, coverage, Ruff, mypy, six dependency audits, build, Wheel, Mock, MCP, Process IR and visual dashboards |
| `windows-control-plane.yml` | `windows-2025`; Python 3.12 | Windows Jobs, IPC, Fake Aspen/HYSYS, PowerShell, paths, Process IR, governance and dashboards |
| `generate-performance-evidence.yml` | `ubuntu-24.04`; Python 3.12 | explicit non-main failure, trusted comparison, two frozen environments and stable-regression evidence |
| `licensed-aspen-certification.yml` | `ubuntu-24.04` guard → licensed Windows | dispatch-SHA binding, Process IR software gate, Mock dashboards, isolated evidence and real COM |

Hosted runners, third-party Actions and `uv 0.11.16` are pinned. Workflows grant only `contents: read`; governance rejects arbitrary `*: write`, `write-all`, retained checkout credentials, `pull_request_target` and silent `continue-on-error`.

### Six frozen dependency audits

```text
Linux and Windows × Python 3.11, 3.12 and 3.13
```

Each target retains JSON and stderr logs and validates the JSON. One failure does not prevent the remaining evidence from being collected; the quality job fails once after all six finish.

### Rerun-safe, fail-closed artifacts

Every artifact name contains `github.run_id` and `github.run_attempt`; matrix artifacts also include the Python version or backend. Every upload uses `if-no-files-found: error`, so missing evidence cannot be represented as success.

```text
ci-evidence-quality-<run_id>-<run_attempt>
ci-evidence-python-<python>-<run_id>-<run_attempt>
windows-control-plane-diagnostics-<run_id>-<run_attempt>
performance-evidence-<run_id>-<run_attempt>
licensed-<backend>-<run_id>-<run_attempt>
```

### Visual test dashboards

`scripts/render_test_dashboard.py` uses only the Python standard library to turn each job's JUnit XML and coverage JSON into self-contained HTML and SVG. Missing evidence is `INCOMPLETE`, failures are `FAIL`, and no state can become a false PASS.

```text
test-dashboard-quality.html / .svg
test-dashboard-python-3.11.html / .svg
test-dashboard-python-3.12.html / .svg
test-dashboard-python-3.13.html / .svg
test-dashboard-windows.html / .svg
test-dashboard-licensed.html / .svg
```

---

## Simulator-neutral Process Intent IR and multi-backend roadmap

AspenOps absorbed compatible architecture patterns from public Text-to-Flowsheet, Sketch2Simulation, multi-Agent process design, DWSIM, IDAES, Modelica and Aspen Python automation projects. It did **not** copy external source code, proprietary prompts or commercial simulator documentation. See [External Agent Integration](docs/external-agent-integration.md).

The new schema is:

```text
aspenops.flowsheet/v1
```

It represents components, property package, unit operations, typed input/output ports, streams, scalar parameters and metadata. The implementation provides:

- deterministic normalization, canonical JSON and SHA-256 graph identity;
- duplicate-ID, unknown-reference, port-direction, self-connection, required-port and implicit multi-connection checks;
- configurable recycle-cycle validation;
- rejection of `code`, `script`, `shell`, `vba`, raw Tree Path and other executable/private-path injection;
- a Knowledge → Concept → Parameter → Execution → Repair → Review Agent contract;
- benchmark fields for topology validity, compiler availability, execution, convergence, material/energy closure, repair iterations and human intervention.

Execution and automatic IR compilation are separate capability claims:

| Backend | Current execution | Automatic IR compiler |
|---|---|---|
| Mock | available | planned |
| Aspen Plus | available on licensed Windows | planned |
| HYSYS | available on licensed Windows | planned |
| DWSIM | planned | planned |
| IDAES | planned | planned |
| Modelica/FMI | planned | planned |

**DWSIM, IDAES, Modelica and automatic Aspen/HYSYS flowsheet compilers are not implemented. The project will not represent a planned adapter as available.**

Validate and render the example:

```bash
uv run python scripts/validate_process_ir.py \
  examples/process-intent.example.json \
  --canonical-output var/ci/process-intent-canonical.json \
  --report-output var/ci/process-intent-report.json

uv run python scripts/render_process_ir_dashboard.py \
  --input var/ci/process-intent-report.json \
  --output-html var/ci/process-ir-dashboard.html \
  --output-svg var/ci/process-ir-dashboard.svg
```

`process-ir-dashboard.html` switches between issues, backend capabilities and the bounded Agent pipeline; `process-ir-dashboard.svg` is suitable for reports and artifact previews. Linux, Windows and licensed Mock gates run `tests/test_process_ir.py`, `tests/test_process_ir_edges.py` and `tests/test_process_ir_dashboard.py`.

The full contract is in [Process Intent IR](docs/process-intent-ir.md).

### Locked-dependency Wheel

Runtime requirements are exported from `uv.lock` with hashes, synchronized with `uv pip sync --require-hashes`, and the Wheel is installed with `--offline --no-deps`. CI then runs `uv pip check`, critical CLI smoke and Process IR import smoke without re-resolving versions.

---

## Trusted and isolated performance evidence

The performance workflow explicitly rejects non-main dispatches, resolves candidate and baseline with `--end-of-options`, requires both commits in trusted main history and executes each revision with its own lockfile, environment and benchmark script.

Default baseline:

```text
ebef32ee1f2be74df5d5c5489e7ca86d35ac7bb2
```

All current-run evidence is written only to `$RUNNER_TEMP/aspenops-performance-evidence`; upload reads `${{ runner.temp }}` and does not read historical candidate-workspace benchmark files. Mock performance is orchestration evidence, not licensed Aspen solve speed.

---

## Windows and real backends

```powershell
powershell -ExecutionPolicy Bypass -File scripts/setup_windows.ps1
```

The bootstrap installs or upgrades `uv >= 0.11.16`, preserves PATH, installs frozen `windows + agent + dev + signing` dependencies, safely loads `.env`, rejects duplicate variables and unbalanced quotes, and runs `doctor --probe`.

Real backends require non-empty absolute `ASPENOPS_ALLOWED_ROOTS`. State, model, registry, result and evidence paths must resolve inside those roots. Realpath checks reject traversal, symlink and Windows junction escapes.

---

## Licensed Aspen certification

The licensed workflow first rejects non-main dispatches on fixed `ubuntu-24.04`. `expected_head_sha` must equal the dispatch `GITHUB_SHA`, and the initial and detached checkout must remain that trusted main commit.

Before checkout, the self-hosted job creates:

```text
$RUNNER_TEMP/aspenops-licensed-artifact-<GITHUB_RUN_ID>-<GITHUB_RUN_ATTEMPT>
```

Run metadata, Mock JUnit, the general dashboard, the Process IR dashboard, successful licensed-evidence copies and final `job_status` remain in this run-attempt directory. Real certification is serialized and uses a separate cleaned external directory:

```text
ASPENOPS_STATE_DIR/licensed-certification/<GITHUB_RUN_ID>-<GITHUB_RUN_ATTEMPT>
```

Software can produce only `PENDING_REAL_ASPEN_CERTIFICATION`; a signature or dashboard is not engineering approval.

---

## Documentation, CLI, MCP and security boundary

Documentation contracts derive the version from `pyproject.toml`, validate local links, frozen commands and certification wording, and reject chat-internal citation or `sandbox:/` markup.

Primary CLI commands: `demo`, `doctor`, `dry-run`, `run-batch`, `submit`, `job`, `benchmark`, `optimize`, `certify`, `certification-preflight`, `certify-licensed`, `verify-licensed-bundle`, `verify-bundle`, and `mcp`.

MCP exposes exactly 14 narrow tools. It does not expose arbitrary Shell, Python, VBA, `eval`, unrestricted COM methods or raw Tree Path writes.

Automation does not prove that every Aspen version starts, every model converges, or property methods, reactions and equipment assumptions are engineering-correct. It cannot replace a process engineer or self-grant real certification.

The code is Apache-2.0. Never commit customer models, proprietary thermodynamics or kinetics, production DCS data, licenses, private keys, tokens, internal hosts or commercial evidence bundles.
