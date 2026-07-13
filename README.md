# AspenOps Agent 1.0

<p align="center">
  <strong>A version-adaptive, process-isolated, testable automation runtime for Aspen Plus.</strong><br>
  Let the agent plan. Let Aspen solve. Let AspenOps enforce execution, units, convergence and evidence.
</p>

<p align="center">
  <a href="README.zh-CN.md">中文文档</a> ·
  <a href="docs/architecture.md">Architecture</a> ·
  <a href="docs/windows-setup.md">Windows Setup</a> ·
  <a href="docs/numerical-methods.md">Numerical Methods</a> ·
  <a href="docs/security.md">Security</a>
</p>

[![CI](https://github.com/SUNHAOJUN22/AspenOps-Agent/actions/workflows/ci.yml/badge.svg)](https://github.com/SUNHAOJUN22/AspenOps-Agent/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/Python-3.11--3.13-3776AB)](https://www.python.org/)
[![Version](https://img.shields.io/badge/version-1.0.0-111827)](CHANGELOG.md)
[![License](https://img.shields.io/badge/license-Apache--2.0-0F766E)](LICENSE)

> **Scope, stated precisely:** AspenOps Agent 1.0 automates **Aspen Plus steady-state cases** through the Windows COM Automation Server. It does not claim native support for Aspen HYSYS, Aspen Custom Modeler, Aspen Dynamics, arbitrary VBA, or unrestricted flowsheet topology editing.

## What this project is

AspenOps is not another thin `Tree.FindNode()` script. It is the runtime layer between an AI coding agent and a stateful proprietary nonlinear process simulator.

```text
Codex / Claude Code / MCP client / Python application
                         │
                  narrow typed tools
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ SessionManager                                              │
│ path policy · audit · typed requests · lifecycle            │
└──────────────────────────────┬──────────────────────────────┘
                               │ one batched RPC
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ Spawned Worker Process                                      │
│ one process · one COM apartment · one simulator document    │
│ semantic registry · unit checks · rollback · path cache     │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ Aspen Plus Automation Server                                │
│ local registered ProgID · case solve · thermodynamics       │
└─────────────────────────────────────────────────────────────┘
```

The separation is intentional:

- the LLM or application decides **what experiment to run**;
- Aspen Plus solves the thermodynamics and flowsheet equations;
- AspenOps decides **whether the requested operation is allowed, dimensionally valid, converged, physically admissible and auditable**.

## Design invariants

1. **One COM object belongs to one spawned Windows process and one STA apartment.** It is never passed across threads or processes.
2. **The newest installed Automation Server is discovered from the local machine.** No single `Apwn.Document.N.0` is hardcoded as the only supported release.
3. **Semantic keys are the default API.** Agents cannot freely concatenate arbitrary Aspen tree paths.
4. **Batch reads and writes cross IPC once.** A point evaluation performs write -> reinitialize -> run -> read in one worker request.
5. **Batch writes are rollback-capable.** If write 2 fails after write 1 succeeds, AspenOps attempts to restore the original values.
6. **Software completion, explicit Aspen convergence evidence and physical feasibility are different states.** Missing or unrecognized simulator status is `unknown`, never assumed converged.
7. **Worker death invalidates the logical session.** Recovery is explicit and reopens the original case path; unsaved in-memory state is not claimed to survive.
8. **Read-only mode fails closed.** Mutation and save are rejected, and unsupported read-only COM signatures do not fall back to writable opening.
9. **Public CI uses the same service, worker, registry and numerical code through a deterministic Mock backend.** Real Aspen validation remains an explicit licensed-Windows gate.

## Version-adaptive Aspen discovery

AspenOps does not infer an Aspen marketing version from memory. At runtime it:

1. checks `ASPENOPS_PROGID` when an operator explicitly pins a ProgID;
2. enumerates `Apwn.Document.*` registrations from both 64-bit and 32-bit Windows registry views;
3. parses numeric versions and tries them newest-first;
4. creates an isolated document through `DispatchEx`;
5. falls back to the unversioned `Apwn.Document` ProgID;
6. reports the ProgID and any version property exposed by the created document.

```powershell
uv run aspenops doctor --probe
```

This is the honest compatibility contract: **AspenOps adapts to the Automation Server actually registered on the target Windows host.** A new Aspen release is considered verified only after the repository's real integration test passes against that installed release and a representative case.

## High-performance execution model

The expensive operations are starting Aspen and opening a model. Repeating them for every design point wastes both time and licenses.

Naive execution:

\[
T_{naive} \approx N(T_{start}+T_{open}+T_{solve})
\]

Persistent CasePool execution:

\[
T_{pool} \approx W(T_{start}+T_{open}) + \frac{N}{W}T_{solve}+T_{IPC}
\]

where the effective worker count is bounded by:

\[
W_{effective}=\min(W_{configured},W_{license},W_{memory},W_{stable})
\]

AspenOps implements:

- one private staged case copy per worker;
- one open simulator document reused across many points;
- one batched IPC request per point;
- candidate-path caching after the first successful semantic-node resolution;
- range-normalized nearest-neighbor point ordering to reduce operating-condition jumps;
- hard worker deadlines; on timeout AspenOps terminates **its worker process**, never performs a machine-wide Aspen kill command;
- explicit worker replacement that reopens the staged case without silently retrying the failed point.

Start with one worker. Increase concurrency only after measuring license availability, RAM use and case stability.

## Semantic node registry

Agents write a semantic request:

```json
{
  "key": "stream.input.temperature",
  "identifiers": {"stream": "FEED"},
  "value": 95.0,
  "unit": "C"
}
```

The registry resolves ordered candidates such as:

```text
\Data\Streams\FEED\Input\TEMP\MIXED
\Data\Streams\FEED\Input\TEMP
```

Each node defines:

- access mode;
- engineering quantity and default unit;
- lower and upper bounds;
- integer policy where relevant;
- required identifiers;
- ordered candidate paths;
- verification status.

The bundled Aspen paths are **candidate templates, not universal truth**. Aspen tree paths vary with model, block type, specification mode, template and release. Production projects should maintain a case-specific registry validated with Aspen Variable Explorer.

## Engineering and numerical logic

Aspen solves an implicit nonlinear system:

\[
\mathbf{F}(\mathbf{z},\mathbf{x};\boldsymbol{\theta})=\mathbf{0}
\]

with manipulated variables \(\mathbf{x}\), internal states \(\mathbf{z}\), and model parameters \(\boldsymbol{\theta}\). AspenOps wraps this solve as:

\[
\mathbf{x}\rightarrow \text{validate}\rightarrow \text{Aspen solve}
\rightarrow (\mathbf{y},s,\boldsymbol{\varepsilon})
\]

where \(s\) is convergence state and \(\boldsymbol{\varepsilon}\) contains constraint and balance residuals.

For a configured balance:

\[
r_b=\sum_i a_i q_i,
\qquad
\varepsilon_b=\frac{|r_b|}{\max(\sum_i|a_iq_i|,q_{min})}
\]

For constrained optimization, failed, unknown, non-finite or infeasible points do not become attractive merely because an output is missing or numerically small. Candidate selection follows Deb-style feasibility ordering:

1. feasible dominates infeasible;
2. among feasible points, lower objective wins;
3. among infeasible points, lower total finite violation wins.

Included numerical components:

- Latin Hypercube, Halton, random and bounded grid designs;
- safe AST objective and constraint expressions - no `eval`, imports, attributes or arbitrary calls;
- finite-value validation for inputs, outputs, objectives, constraints and balances;
- absolute and relative conservation residuals;
- adaptive continuation for large condition changes;
- bounded `DE/best/1/bin` differential evolution;
- deterministic seeds for reproducibility.

## Installation

### Development and Mock validation on any OS

```bash
git clone https://github.com/SUNHAOJUN22/AspenOps-Agent.git
cd AspenOps-Agent
uv sync --extra dev
uv run aspenops demo
```

### Real Aspen Plus on Windows

```powershell
uv sync --extra windows --extra dev
uv run aspenops doctor --probe
uv run aspenops run-case "D:\AspenModels\case.bkp" --timeout-s 1200
```

### MCP server

Production MCP startup is fail-closed: configure both allowed model roots and a persistent audit destination.

```powershell
uv sync --extra windows --extra agent
$env:ASPENOPS_ALLOWED_ROOTS = "D:\AspenModels;D:\AspenResults"
$env:ASPENOPS_AUDIT_LOG = "D:\AspenResults\audit\aspenops.jsonl"
uv run aspenops-mcp
```

For isolated local Mock development only, `ASPENOPS_INSECURE_LOCAL_DEV=1` permits unrestricted paths and no persistent audit. Do not use that override for a remote or shared deployment.

Example MCP configuration:

```json
{
  "mcpServers": {
    "aspenops": {
      "command": "uv",
      "args": ["run", "--project", "D:/src/AspenOps-Agent", "aspenops-mcp"],
      "env": {
        "ASPENOPS_ALLOWED_ROOTS": "D:/AspenModels;D:/AspenResults",
        "ASPENOPS_AUDIT_LOG": "D:/AspenResults/audit/aspenops.jsonl"
      }
    }
  }
}
```

Exposed tools are deliberately narrow:

- `system_info`
- `open_session`
- `recover_session`
- `close_session`
- `get_values`
- `set_values`
- `reinitialize`
- `run_simulation`
- `diagnose_session`
- `save_case`

There is no universal `execute_code`, unrestricted `call_com_method`, arbitrary shell, VBA or raw-path mutation tool.

## Quality gate

Run the complete local gate:

```bash
uv sync --extra dev --extra agent
uv run ruff check .
uv run mypy src/aspenops
uv run pytest
uv build
uv run aspenops demo
```

Current local Linux evidence for 1.0.0:

- Ruff: passed;
- strict mypy over all 22 source modules: passed;
- Pytest: 34 passed, 1 licensed-Windows integration test skipped by condition;
- measured coverage for cross-platform executable modules: 86.75%;
- wheel and source distribution: built successfully after the final documentation pass;
- real Aspen Plus: **not physically available in the build environment**.

The GitHub CI matrix repeats lint, typing, tests and packaging on Python 3.11, 3.12 and 3.13. A separate manual workflow targets a self-hosted licensed Windows runner.

## Real Aspen validation

On a licensed Windows node:

```powershell
uv sync --extra windows --extra dev
uv run aspenops doctor --probe
$env:ASPENOPS_TEST_CASE = "D:\AspenModels\integration.bkp"
uv run pytest -m aspen_integration -s
```

The integration case should be non-confidential, deterministic, already convergent in Aspen, and configured with project-specific semantic paths.

## Known boundaries

- Aspen Plus Automation is a Windows-only proprietary dependency.
- This repository cannot test a real Aspen installation from public Linux CI.
- The bundled registry is a safe starting point; it is not a substitute for validating a project's actual tree.
- Worker termination may leave a vendor process to be cleaned up by COM or Windows; AspenOps deliberately avoids broad `taskkill` commands that could terminate another engineer's session.
- Explicit session recovery reloads the configured case path; it cannot restore unsaved state from a terminated process.
- Semi-batch kinetics, population balances and full transient reactor trajectories require an external ODE/PBE layer, Aspen Custom Modeler, or Aspen Dynamics. The v1.0 backend is steady-state.
- HYSYS, ACM and Dynamics require separate adapters and separate validation evidence.

## Repository map

```text
src/aspenops/
  accessor.py          semantic validation, unit conversion, rollback, path cache
  compat.py            local Aspen ProgID discovery and probe
  worker.py            spawned worker and deadline-enforced RPC
  pool.py              persistent staged-case worker pool
  backends/            Aspen Plus COM backend and deterministic Mock backend
  evaluation.py        safe expressions, constraints, balances, feasibility
  design.py            DOE generators and locality ordering
  continuation.py      adaptive operating-point continuation
  optimizer.py         bounded differential evolution
  service.py           session lifecycle, path policy and audit
  mcp_server.py        optional narrow MCP surface
  data/nodes/          allowlisted semantic registry

tests/                 deterministic unit, failure-injection and integration tests
docs/                  architecture, compatibility, mathematics and Windows setup
examples/              Mock case and recipe examples
```

## License and proprietary-data policy

Code is Apache-2.0. Aspen Plus, model files, property databases and vendor documentation remain subject to their respective licenses. Do not commit customer `.bkp`, `.apw`, `.apwz`, `.his`, credentials, license files or proprietary kinetic data.
