# Changelog

## Unreleased

- added simulator-neutral `aspenops.flowsheet/v1` Process Intent IR;
- added deterministic normalization, SHA-256 identity and fail-closed topology validation;
- added explicit execution-versus-compiler capability declarations for Mock, Aspen Plus, HYSYS, DWSIM, IDAES and Modelica;
- added bounded knowledge, concept, parameter, execution, repair and review Agent contracts;
- added flowsheet benchmark records that separate topology, compiler, execution, convergence, balances, repair and human intervention;
- added Process IR validation commands, HTML/SVG visual evidence and Linux/Windows/licensed-Mock CI contracts;
- added a real `aspenops scheduler` service so CLI `submit` durably enqueues work instead of relying on a daemon thread that ends with the submitting process;
- centralized durable request identity in `durable_request.py`, with CLI and MCP pinning relative model and registry paths before scheduling;
- persisted `submission_cwd`, documented the direct Python helper contract, and made public queued execution independent of Scheduler working directory;
- added `aspenops cancel` with immediate pending/retry cancellation, active-job grace deadlines and owned-Worker termination boundaries;
- made CLI `job` read durable state without constructing an unused PoolManager or Worker fabric;
- added a portable constrained-optimization example and made the optimization tests execute that published document directly;
- added source, durable queue lifecycle and locked-Wheel smoke for scheduler, cancellation and the published optimization workflow;
- constrained the packaged `agent` extra to `mcp>=1.9,<2`, kept the frozen runtime on `mcp 1.28.1`, and added a fail-closed SDK major-version gate;
- bound Scheduler startup and Worker/PoolManager cleanup to FastMCP lifespan instead of leaving an unowned service fabric after server shutdown;
- made source tests, actual built-Wheel `METADATA` inspection, locked-Wheel smoke and three-platform governance verify MCP package metadata, version and lifecycle contracts;
- applied the same fail-closed backend, mode, Boolean, path and finite-resource validation to environment loading and direct Python `Settings(...)` construction;
- rebuilt the bilingual README as a complete installation, configuration, workflow, scheduling, caching, optimization, industrial-use and troubleshooting guide;
- expanded the governed visual system to seventeen original, self-contained and repository-local SVG capability diagrams, including configuration/path policy, optimization lifecycle and cache/singleflight views;
- bound the new diagrams to their real implementation markers and retained fail-closed inventory, accessibility, renderer-portability and resource-safety contracts in Linux, Windows and pre-licensed-COM quality gates;
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
