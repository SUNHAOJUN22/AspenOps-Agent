# Changelog

## Unreleased

- added simulator-neutral `aspenops.flowsheet/v1` Process Intent IR;
- added deterministic normalization, SHA-256 identity and fail-closed topology validation;
- added explicit execution-versus-compiler capability declarations for Mock, Aspen Plus, HYSYS, DWSIM, IDAES and Modelica;
- added bounded knowledge, concept, parameter, execution, repair and review Agent contracts;
- added flowsheet benchmark records that separate topology, compiler, execution, convergence, balances, repair and human intervention;
- added Process IR validation commands, HTML/SVG visual evidence and Linux/Windows/licensed-Mock CI contracts;
- documented external process-Agent architecture patterns without copying third-party code or proprietary prompts;
- retained DWSIM, IDAES, Modelica and automatic Aspen/HYSYS flowsheet compilers as planned, not implemented, capabilities.

## 2.0.0 - 2026-07-18

- fail-closed convergence evidence for Aspen Plus and HYSYS;
- verified write rollback with tainted Worker recycling;
- compiled unique-node evaluation plans and cache-source provenance;
- cross-call singleflight and persistent license-aware CasePools;
- leased durable jobs, heartbeats, cancellation deadlines and idempotent commits;
- Windows Job Object supervision with process-fingerprint fallback;
- member-level integrity manifests and optional Ed25519 signatures;
- budgeted batch constrained optimization with mixed variables and Pareto results;
- portable baseline/candidate benchmark evidence and expanded CI contracts.

## 1.0.0 - 2026-07-13

- Introduced runtime discovery of versioned Aspen Plus and HYSYS COM Automation Servers.
- Added process-isolated STA workers with private staged model copies and correlated IPC.
- Added persistent CasePool execution, dynamic task claiming, worker recycling and license caps.
- Added semantic registries, identifier injection protection, explicit units and engineering bounds.
- Added separate transport, engine, convergence, constraint and balance validity gates.
- Added content-addressed cache identity over runtime, backend, model, registry and physical request.
- Added SQLite WAL background jobs, restart interruption detection and cancellation state.
- Added immutable evidence bundles with request, result, model and registry SHA-256 values.
- Added independent repeated-state certification, Codex/Claude Code MCP integration and CI gates.
- Added Aspen Plus COM, HYSYS Spreadsheet, and deterministic cross-platform Mock backends.
