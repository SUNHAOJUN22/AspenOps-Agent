<div align="center">

# AspenOps 2.0

## Deterministic control plane for Aspen Plus, Aspen HYSYS and AI agents

**Agent / CLI / Python → validated process intent → isolated execution → nonlinear solve → engineering decision → reproducible evidence**

[中文](README.md) · [Architecture](docs/architecture.md) · [Process Intent IR](docs/process-intent-ir.md) · [External Agent Integration](docs/external-agent-integration.md) · [Windows Setup](docs/windows-setup.md) · [Performance](docs/performance.md) · [Certification](docs/certification.md) · [Test Audit](docs/automated-test-audit-2026-07-22.md) · [Quality Report](docs/quality-report.md) · [Security](SECURITY.md) · [Contributing](CONTRIBUTING.md)

[![CI main push](https://github.com/SUNHAOJUN22/AspenOps-Agent/actions/workflows/ci.yml/badge.svg?branch=main&event=push)](https://github.com/SUNHAOJUN22/AspenOps-Agent/actions/workflows/ci.yml?query=branch%3Amain+event%3Apush)
[![Windows main push](https://github.com/SUNHAOJUN22/AspenOps-Agent/actions/workflows/windows-control-plane.yml/badge.svg?branch=main&event=push)](https://github.com/SUNHAOJUN22/AspenOps-Agent/actions/workflows/windows-control-plane.yml?query=branch%3Amain+event%3Apush)
![Python](https://img.shields.io/badge/Python-3.11--3.13-3776AB)
![Version](https://img.shields.io/badge/version-2.0.0-111827)
![License](https://img.shields.io/badge/license-Apache--2.0-0F766E)

</div>

![AspenOps architecture](docs/assets/readme/hero-architecture.svg)

> The nine diagrams in this README are original AI-generated SVG assets created for AspenOps. They visualize implemented contracts and explicitly labelled roadmap items; planned capabilities are never presented as available.

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

These figures are an **archived validated baseline** extracted from inspected JUnit, coverage JSON and logs. They are **not an automatic claim** about any later commit. Badges represent the current `main` push state; historical figures never replace fresh Actions evidence.

Public CI validates the control plane, path policy, process isolation, scheduling, archives, interfaces and Process Intent contracts. It cannot certify a commercial Aspen installation, licence, property method or engineering model.

---

## Product position

AspenOps is not a wrapper that lets a model emit arbitrary COM scripts. It is deterministic infrastructure for Aspen Plus, Aspen HYSYS and process-simulation agents:

- semantic variables, validated Process Intent IR and narrow MCP tools instead of arbitrary Tree Paths, shell, VBA or raw COM;
- OS-process isolation, STA ownership, private model copies and licence-slot controls;
- independent transport, engine, convergence, feasibility, balance and human-approval gates;
- frozen dependencies, exact trusted SHA, run-attempt artifacts, hashes, signatures and visual evidence;
- selected architectural lessons from Text-to-Flowsheet, Sketch2Simulation, DWSIM, IDAES, Modelica and Aspen Python automation without copying proprietary code or prompts.

---

## Industrial safety invariants

![Windows COM process isolation](docs/assets/readme/com-isolation.svg)

1. One COM object belongs to one Windows child process and one STA apartment.
2. Agents use semantic variables or `aspenops.flowsheet/v1`, never arbitrary Aspen Tree Paths.
3. Every Worker uses a private staged model copy.
4. Hard timeout recovery terminates only the AspenOps-owned Worker.
5. Concurrency is capped by licence evidence and `ASPENOPS_LICENSE_SLOTS`.
6. Communication, engine return, convergence, feasibility and balances remain independent gates.
7. Mock, Fake COM and public CI never impersonate licensed Aspen physics certification.
8. Missing DWSIM, IDAES, Modelica or flowsheet compilers fail closed.

A result is `ok=true` only when:

```text
communication_ok
AND engine_ok
AND converged
AND feasible
AND balances_passed
```

---

## Process Intent IR

![Process Intent IR](docs/assets/readme/process-intent-ir.svg)

The simulator-neutral schema is:

```text
aspenops.flowsheet/v1
```

It represents components, property method, unit operations, ports, streams, parameters and safe metadata. It provides deterministic ordering, canonical JSON, SHA-256 graph identity, topology validation, quantity budgets, cycle policy and rejection of executable or private-path keys such as `code`, `script`, `shell`, `python`, `vba`, `command` and raw Tree Paths.

Validate and render it locally:

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

`process-ir-dashboard.html` exposes issues, backend declarations and the agent pipeline. Details are in [Process Intent IR](docs/process-intent-ir.md).

---

## Layered process agents

![Layered process agents](docs/assets/readme/agent-pipeline.svg)

```text
Knowledge
→ Concept
→ Parameter
→ Execution
→ Repair
→ Physics / Engineering Review
```

Knowledge is read-only. Concept and Parameter may output only validated `aspenops.flowsheet/v1`. Execution can use only declared available backends and narrow tools. Repair is bounded by iteration, time and solve budgets. Review independently evaluates physics, convergence, constraints, balances and human approval. No stage may emit arbitrary Python, Shell, VBA, raw COM or raw Aspen Tree Paths.

---

## Multi-simulator capability declaration

![Backend capability matrix](docs/assets/readme/backend-capabilities.svg)

Execution and IR-compilation capability are independent:

| Backend | Current execution | IR compiler | Boundary |
|---|---|---|---|
| Mock | available | planned | Cross-platform deterministic software testing, no Aspen physics |
| Aspen Plus | available on licensed Windows | planned | Existing approved-model execution |
| HYSYS | available on licensed Windows | planned | Existing approved-model execution |
| DWSIM | planned | planned | **No adapter claimed** |
| IDAES | planned | planned | **No adapter claimed** |
| Modelica/FMI | planned | planned | **No adapter claimed** |

**planned ≠ implemented; compiler ≠ executor; a signature ≠ engineering approval.**

---

## CLI, scheduling, optimization and MCP

Primary CLI commands:

```text
demo
doctor
dry-run
run-batch
submit
job
benchmark
optimize
certify
certification-preflight
certify-licensed
verify-licensed-bundle
verify-bundle
mcp
```

The MCP server exposes exactly 14 narrow tools for discovery, planning, submission, observation, optimization and evidence verification. It exposes no arbitrary shell, Python, VBA, `eval`, unrestricted COM method or raw Tree Path write.

The scheduler uses SQLite WAL, leases, heartbeats, cancellation deadlines and idempotent commits. CasePool reuse is bound to backend, model, registry, concurrency and visibility; cache identity binds runtime, model, registry and physical request.

---

## Automated tests and visual evidence

![Automated test matrix](docs/assets/readme/test-matrix.svg)

The four authoritative workflows are:

| Workflow | Pinned environment | Responsibility |
|---|---|---|
| `ci.yml` | `ubuntu-24.04`; Python 3.11/3.12/3.13 | Ruff, format, strict mypy, six dependency audits, full tests, branch coverage, build, Wheel, Mock, MCP, Process IR and dashboards |
| `windows-control-plane.yml` | `windows-2025`; Python 3.12 | Windows Job, IPC, Fake Aspen/HYSYS, PowerShell, paths, IR and governance |
| `generate-performance-evidence.yml` | `ubuntu-24.04`; Python 3.12 | trusted baseline/candidate, two frozen environments and stable-regression evidence |
| `licensed-aspen-certification.yml` | `ubuntu-24.04` guard → licensed Windows | main guard, SHA binding, Mock/IR software gates, evidence isolation and real COM |

Frozen audits cover:

```text
Linux and Windows × Python 3.11, 3.12 and 3.13
```

That is six audit targets. Hosted runners, third-party Actions and `uv 0.11.16` are pinned; workflow permission is `contents: read`.

Artifact names contain both `github.run_id` and `github.run_attempt`; uploads use `if-no-files-found: error`. Current-job evidence is written under `$RUNNER_TEMP` and upload reads through `${{ runner.temp }}`. Missing JUnit or an early failure renders `INCOMPLETE`; any failure/error renders `FAIL`.

Complete local quality gate:

```bash
uv lock --check
uv sync --frozen --extra dev --extra agent --extra signing
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest -W error::ResourceWarning \
  --cov=aspenops_nexus \
  --cov-branch \
  --cov-fail-under=94.5
uv build
uv run python scripts/check_mcp.py
uv run python scripts/validate_process_ir.py examples/process-intent.example.json
uv run aspenops --version
uv run aspenops demo
uv run aspenops dry-run examples/batch-request.example.json
```

Add `--extra windows` on Windows. `.env.example` defaults to Mock, an empty allowlist and a repository-local state directory.

---

## Reproducible evidence

![Reproducible evidence chain](docs/assets/readme/evidence-chain.svg)

```text
validated intent
→ exact trusted main SHA
→ isolated Worker execution
→ convergence / feasibility / balances
→ run_id + run_attempt artifact
→ hashes and optional signature
→ qualified human acceptance
```

Performance dispatch verifies `GITHUB_REF == refs/heads/main`. A non-main dispatch writes `dispatch-ref.txt` and `dispatch-guard.log`, then **fails explicitly with exit code 2** instead of becoming all-skipped. `actions/checkout` loads the trusted workflow revision, candidate and baseline refs are resolved with `--end-of-options`, ancestry is checked, and the validated candidate is used through detached checkout.

Default performance baseline:

```text
ebef32ee1f2be74df5d5c5489e7ca86d35ac7bb2
```

Mock performance is orchestration evidence, not licensed Aspen solve speed.

---

## Licensed Aspen certification

![Licensed certification](docs/assets/readme/licensed-certification.svg)

The protected workflow:

1. checks `refs/heads/main` in a fixed `ubuntu-24.04` guard;
2. requires `expected_head_sha == GITHUB_SHA`;
3. verifies the initial `actions/checkout` and then uses detached checkout;
4. creates `$RUNNER_TEMP/aspenops-licensed-artifact-<GITHUB_RUN_ID>-<GITHUB_RUN_ATTEMPT>` before checkout;
5. records run identity in `run-metadata.txt`;
6. stores Mock JUnit, dashboards, evidence copies and final `job_status` in that run directory;
7. uses `LICENSED_EVIDENCE_DIR` at `ASPENOPS_STATE_DIR/licensed-certification/<GITHUB_RUN_ID>-<GITHUB_RUN_ATTEMPT>`;
8. serializes all real runs with concurrency group `licensed-aspen-certification`;
9. uploads only the current `${{ runner.temp }}` directory using `if-no-files-found: error`.

Software can emit only:

```text
PENDING_REAL_ASPEN_CERTIFICATION
```

Real certification still requires licensed Windows, a valid licence, an approved model, signing material and qualified human engineering acceptance.

---

## Roadmap

![AspenOps roadmap](docs/assets/readme/roadmap.svg)

### Implemented

- Process Intent IR, strict validation, canonical JSON and SHA-256 graph identity;
- Aspen Plus/HYSYS existing-model control plane;
- Mock, Fake COM, Windows Job Object, scheduling, optimization and MCP;
- frozen CI, visual dashboards, evidence bundles and licensed-certification boundaries.

### Next

- IR → Mock non-executable plan compiler;
- open DWSIM process backend;
- Text/Image → IR benchmark and data contracts;
- bounded simulation-feedback repair loops;
- human review and visual-diff UI.

### Evidence-gated later work

- Aspen/HYSYS automatic flowsheet compiler;
- IDAES symbolic backend;
- Modelica/FMI co-simulation;
- image/PFD understanding;
- industrial model and version qualification.

No capability moves from planned to available without **code + tests + evidence**.

---

## AI-generated visual assets

The following original SVGs are stored under `docs/assets/readme/` and load no external images:

1. `hero-architecture.svg`
2. `process-intent-ir.svg`
3. `agent-pipeline.svg`
4. `backend-capabilities.svg`
5. `com-isolation.svg`
6. `test-matrix.svg`
7. `evidence-chain.svg`
8. `licensed-certification.svg`
9. `roadmap.svg`

They contain no fabricated run result, customer model or proprietary simulator content.

---

## Documentation and security boundary

`tests/test_documentation_contracts.py` derives the version from `pyproject.toml`, validates README, `__version__`, CHANGELOG, AGENTS, CLAUDE, CONTRIBUTING and core documents, and rejects repository-escaping links or conversation-internal markup.

- [Architecture](docs/architecture.md)
- [Process Intent IR](docs/process-intent-ir.md)
- [External Agent Integration](docs/external-agent-integration.md)
- [Windows Setup](docs/windows-setup.md)
- [Performance](docs/performance.md)
- [Certification](docs/certification.md)
- [Test Audit](docs/automated-test-audit-2026-07-22.md)
- [Quality Report](docs/quality-report.md)

Automation does not prove that every Aspen version starts, every model converges or that property methods, reactions and equipment assumptions are engineering-correct. It cannot replace a process engineer or self-grant real certification.

The code is Apache-2.0. Never commit customer models, proprietary thermodynamics or kinetics, production DCS data, licences, private keys, tokens, internal hosts or commercial evidence bundles.
