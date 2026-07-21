<div align="center">

# AspenOps 2.0

## A deterministic execution fabric for Aspen Plus, Aspen HYSYS and coding agents

**Codex / Claude Code → typed process intent → isolated workers → Aspen solve → engineering verification → reproducible evidence**

[中文](README.md) · [Architecture](docs/architecture.md) · [Windows Setup](docs/windows-setup.md) · [Performance](docs/performance.md) · [Certification](docs/certification.md)

</div>

AspenOps is not a thin `win32com` wrapper. It is the control plane between an AI coding agent and a stateful, version-sensitive, license-constrained nonlinear process simulator.

The agent decides what experiment to run. Aspen solves thermodynamics and flowsheet equations. AspenOps decides whether the operation is allowed, dimensionally valid, converged, physically admissible and reproducible.

## Core invariants

1. One COM object belongs to one spawned Windows process and one STA apartment.
2. Agents use semantic variables; they never invent raw Aspen tree paths.
3. Every worker opens a private staged copy of the source model.
4. Reset, bulk write, solve, bulk read and verification cross IPC once per point.
5. A hard timeout terminates only the worker created by AspenOps.
6. Transport, engine return, convergence, feasibility and balance closure are separate states.
7. Portable Mock CI validates the control plane; it never claims real Aspen physics certification.

## Version-adaptive compatibility

AspenOps does not hardcode one `Apwn.Document.N.0` as “the latest release.” It scans both Windows registry views, discovers all registered `Apwn.Document.*` and `HYSYS.Application.*` servers, sorts numeric registrations newest-first, creates isolated instances with `DispatchEx`, and retains unversioned ProgIDs as fallback.

This makes the runtime forward-adaptive to a newly installed Aspen release that preserves the Automation Server contract. Verified support still requires the licensed Windows certification workflow with an approved case.

## Validity contract

For one evaluation:

\[
S_{valid}=S_{transport}\land S_{engine}\land S_{convergence}\land S_{constraints}\land S_{balances}.
\]

`ok=true` is emitted only when every gate passes. `Run2()` returning by itself is never treated as proof of a valid process solution.

For a configured conservation relation:

\[
r_b=\sum_i a_iq_i-q_{expected},
\qquad
\varepsilon_{rel}=\frac{|r_b|}{\max(\sum_i|a_iq_i|,q_{floor})}.
\]

The result records absolute and normalized residuals, tolerances and pass/fail evidence.

## Performance model

Naive point-by-point startup:

\[
T_{naive}\approx N(T_{start}+T_{open}+T_{solve}).
\]

Persistent CasePool:

\[
T_{pool}\approx W(T_{start}+T_{open})+\frac{N_{unique}}{W}(T_{solve}+T_{verify})+T_{IPC}.
\]

The effective worker count is bounded by configured concurrency, license seats, memory and model stability. AspenOps uses dynamic task claiming, content-addressed cache keys, duplicate elimination and worker recycling.

## Quick start

```bash
uv sync --extra dev --extra agent
uv run aspenops demo
uv run aspenops benchmark --points 24 --workers 1,2,4
uv run aspenops certify examples/batch-request.example.json --repeats 3
```

Quality gate:

```bash
uv run ruff check .
uv run mypy src
uv run pytest --cov=aspenops_nexus --cov-report=term-missing
uv build
uv run python scripts/check_mcp.py
```

Real Aspen Plus on Windows:

```powershell
uv sync --extra windows --extra dev --extra agent
uv run aspenops doctor --probe
uv run aspenops dry-run D:/AspenModels/request.json
uv run aspenops run-batch D:/AspenModels/request.json `
  --output D:/AspenResults/results.json `
  --bundle D:/AspenResults/run-bundle.zip
```

## Agent surface

The MCP server exposes a deliberately narrow tool set:

```text
system_info
list_semantic_variables
dry_run_request
run_batch_sync
submit_batch
job_status
job_result
list_recent_jobs
cancel_job
verify_evidence_bundle
```

There is no arbitrary shell, Python, VBA, `eval`, raw COM method or unrestricted tree-path mutation tool.

## Honest boundary

Public CI cannot validate proprietary Aspen executables. Real compatibility is certified through the separate self-hosted Windows workflow using a licensed host, an approved non-confidential case, case-specific semantic paths, process constraints and conservation checks.

## License

Apache-2.0. Aspen products, model files, databases and vendor documentation remain governed by their respective licenses. Never commit customer models, license files, proprietary kinetics or confidential run bundles.
