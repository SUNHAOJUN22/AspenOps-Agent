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
- applied the same fail-closed backend, mode, Boolean, `Path` and finite-resource validation to environment loading and direct Python `Settings(...)` construction;
- required backend run flags to be real Boolean values, routed Aspen Plus and HYSYS public execution through explicit COM running-state normalization, and kept unknown simulator states fail closed;
- rejected non-numeric, non-finite and derived-overflow constraint or balance evidence, sanitized backend diagnostics to JSON-safe values and preserved `allow_nan=False` evidence writing;
- made the numeric/protocol smoke execute in Linux, public Windows and the pre-licensed-COM software gate;
- made run-bundle `all_ok` use literal Boolean semantics, recomputed it during verification and rejected invalid or multiline Ed25519 key IDs before writing;
- routed the installed `aspenops` command through a lightweight bootstrap so version and help paths avoid execution-control-plane imports while real commands delegate once to the full CLI;
- made cache hit-threshold accounting O(1), yielded SQLite key batches lazily, stored compact JSON and executed bounded `PRAGMA optimize` without changing WAL or transaction durability;
- reused cache-key computation for repeated references to the same immutable request object and reduced one cacheable solve to one canonical result serialization while preserving deep result isolation;
- removed one population-sized exclusion-list allocation per differential-evolution target and reduced Pareto work through ordered exact deduplication and feasibility filtering without changing evaluation budgets;
- added same-environment CLI startup evidence, Python `-X importtime`, cProfile, tracemalloc, RSS and deterministic operation-count artifacts;
- added hard performance contracts for cache-key calls, solver calls, serialization calls, same-batch deduplication, cache flush state, compact-JSON clone counts and Pareto dominance calls across Linux, public Windows and pre-licensed-COM gates;
- routed the MCP `list_recent_jobs` product surface through one bounded SQLite connection and one indexed SELECT of public job fields, without changing request creation, lease, recovery, cancellation or commit transactions;
- added `idx_jobs_recent_created_job`, a shared recent-job row decoder, explicit index commit, bounded `PRAGMA optimize`, and deterministic `EXPLAIN QUERY PLAN` evidence;
- added `job-store-query-plan.json` with 1000-record, one-connection, one-SELECT, indexed-order and no-temporary-sort contracts to existing performance artifacts and all three software gates;
- implemented and then rolled back a structured-object ResultCache memory LRU after representative measurement showed generic `deepcopy()` could be slower than C `json.loads`; the retained compact-JSON strategy keeps zero SQLite memory hits and deep isolation;
- kept request/result evidence-member byte reuse inconclusive because it would change readable archive members without current-HEAD CPU and size evidence;
- kept Python 3.14 qualification, replacement SQLite bindings, global bytecode compilation and CI cache pruning deferred until their Windows/Wheel/COM or same-environment trade-offs are measured;
- retained uv `0.11.16`, MCP stable v1 with `<2`, and the current lockfile rather than refreshing dependencies for version-number reasons alone;
- replaced stale benchmark-report branch wording with real commit identity or an explicit artifact label;
- added formal evidence-locked performance audits with retained, rolled-back, rejected, deferred and inconclusive decisions;
- rebuilt the bilingual README as a complete installation, configuration, validity, workflow, scheduling, caching, optimization, performance, Worker-ownership, evidence-integrity, industrial-use and troubleshooting guide;
- expanded the governed visual system to twenty-two original, self-contained and repository-local SVG capability diagrams, including validity gates, Worker ownership/recycling, evidence integrity/authenticity, performance hotspots and startup evidence;
- bound every added diagram and performance claim to real implementation markers and retained exact inventory, accessibility, renderer-portability and resource-safety contracts in Linux, Windows and pre-licensed-COM quality gates;
- documented external process-Agent architecture patterns without copying third-party code or proprietary prompts;
- retained DWSIM, IDAES, Modelica and automatic Aspen/HYSYS flowsheet compilers as planned, not implemented, capabilities;
- deferred migration of the compatibility Python `JobStore.list_recent()` method and further claim/cancellation/event indexes until their legacy-call and query-plan contracts are complete;
- rejected mtime/size digest shortcuts, unmeasured shared memory, default Worker inflation and new heavy numerical dependencies because they would weaken identity or lack current workload evidence.

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
