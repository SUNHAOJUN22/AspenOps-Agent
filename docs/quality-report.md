# AspenOps 2.0 Quality Report

## Scope

This report records portable and public-Windows evidence for the AspenOps 2.0 control plane and the automated-test hardening applied on 2026-07-22. It does not certify licensed Aspen Plus or Aspen HYSYS physical results or approve an engineering model.

The detailed module inventory, artifact inspection and coverage review are retained in `docs/automated-test-audit-2026-07-22.md`.

## Authoritative verified portable baseline

GitHub Actions run `29814739487`, head SHA `670e9523e915af309f16d959150cfadcd84219a6`, validated Python 3.11, 3.12 and 3.13 with:

- Ruff linting;
- Ruff formatting;
- strict mypy over `src`;
- pytest with branch coverage and `ResourceWarning` promoted to an error;
- source and wheel builds;
- portable Mock demo;
- benchmark smoke and committed stable-regression policy;
- MCP surface verification;
- clean Python 3.12 wheel installation, version command, demo and licensed CLI help smoke.

The Python 3.12 JUnit, coverage JSON and pytest log artifacts were downloaded and inspected. Observed result:

```text
72 test modules
563 passed
0 failed
0 errors
0 skipped
16.73 seconds
4916 statements
185 missing statements
1508 branches
114 partial branches
combined branch-aware coverage: 94.9719800747198%
statement coverage: 96.23677786818551%
branch coverage: 90.84880636604774%
CI coverage floor: 94.5%
```

The gate is measured with `--cov-branch`. No core runtime module is omitted to inflate the result, and the floor was not reduced during single-main consolidation.

## Public Windows control-plane baseline

The authoritative public-Windows run is `29814739334`, also at head SHA `670e9523e915af309f16d959150cfadcd84219a6`.

Its diagnostic artifact was downloaded and inspected:

```text
104 passed
0 failed
0 errors
0 skipped
2.06 seconds
```

It validated:

- strict type and lint compatibility on Windows Python 3.12;
- Job Object setup and `KILL_ON_JOB_CLOSE` contracts;
- process fingerprint and descendant ownership checks;
- Fake Aspen Plus and HYSYS convergence adapters;
- Worker IPC and staged-model cleanup;
- durable Scheduler lease and owner-fencing contracts;
- bounded ZIP archive verification;
- PoolManager creation singleflight and license accounting.

This runner has no licensed Aspen installation. Its success is evidence about the control plane, not simulator or engineering-model qualification.

## Coverage review

The aggregate result is strong but has approximately 0.47 percentage points of headroom above the 94.5% floor. The primary future targets are:

| Module | Combined branch-aware coverage |
|---|---:|
| `scheduler.py` | 85.95% |
| `pool.py` | 87.28% |
| `backends/mock.py` | 88.00% |
| `worker.py` | 89.20% |
| `provenance.py` | 90.40% |
| `batch.py` | 91.12% |
| `convergence.py` | 91.20% |
| `pool_manager.py` | 94.49% |

The current floor should not be raised merely for appearance. New tests should first cover lease transitions, worker recovery, timeout/IPC failures, provenance I/O failures and remaining convergence contradictions.

## Safety-critical regression suites

### Convergence

Unknown, absent, contradictory or unstable evidence fails closed. Tests cover positive and negative states, status-access errors, timeouts and stable-idle requirements.

### Transactions

Tests cover original-value capture, current-node rollback, numeric tolerance, rollback-verification failure and automatic recycling of a tainted Worker.

### Durable scheduling

Tests cover lease acquisition, heartbeat, expiration, final-attempt dead letter, service restart, cancellation, owner fencing, idempotent commits, active-job heartbeat and stale-bundle cleanup.

### Worker lifecycle

Tests cover model-copy, Pipe and process startup failures; ready/result/close protocol validation; send, poll and receive failures; hard timeout; graceful close; and bounded fatal diagnostics.

### Archive safety

Tests cover archive and member-size limits, member count, compression ratio, path traversal, absolute and drive paths, duplicate and encrypted members, unsupported compression, malformed JSON roots, malformed signing declarations and bounded member reads.

### Optimization

Tests cover continuous, integer, categorical and ordinal variables; hard evaluation budgets; non-finite inputs and outputs; Deb feasibility ordering; Pareto behavior; checkpoint safety; cancellation; batch evaluation and interface limits.

### Licensed-certification governance

Tests cover plan validation, exact commit binding, approved host/license metadata, signing-key boundaries, CLI behavior, signed-bundle integrity, workflow ordering and the prohibition against software self-granting final engineering certification.

## Automated gate hardening applied on 2026-07-22

### Portable CI

`.github/workflows/ci.yml` now enforces:

- immutable commit-SHA pins for third-party GitHub Actions;
- read-only contents permission and checkout without persistent credentials;
- `uv lock --check` and `uv sync --frozen`;
- Ruff lint and format, strict mypy, build and Mock demo;
- README command-path smoke for version, help, dry-run, benchmark and certification;
- benchmark smoke and committed stable-regression policy;
- the exact 14-tool MCP surface;
- clean-wheel version, help, Demo and critical CLI smoke;
- complete pytest suites on Python 3.11, 3.12 and 3.13;
- branch-aware coverage floor 94.5%;
- JUnit, JSON coverage, slowest-test and log artifacts.

### Public Windows gate

`.github/workflows/windows-control-plane.yml` now additionally enforces:

- manual dispatch as well as push and pull-request triggers;
- lockfile freshness and frozen Windows dependency installation;
- repository-wide Ruff format checking;
- licensed-bundle, licensed CLI and licensed-workflow contract tests;
- Windows CLI and Doctor smoke;
- JUnit and slowest-test evidence.

Based on the archived JUnit module inventory, the hardened selected Windows suite contains 127 tests. This is a selected-test count, not a fresh passing result, until the revised workflow completes.

### Performance evidence

`.github/workflows/generate-performance-evidence.yml` now uses pinned Actions, non-persistent checkout credentials, lockfile validation, frozen candidate dependencies and format checking for benchmark tooling. The benchmark remains `portable-mock-orchestration` evidence and must not be presented as licensed Aspen solve performance.

### Licensed Aspen certification

`.github/workflows/licensed-aspen-certification.yml` now performs this sequence:

```text
exact approved SHA checkout
→ lockfile validation and frozen dependency sync
→ isolated Mock software-regression gate
→ licensed preflight
→ explicit execution approval
→ scoped real COM execution
→ signed bundle verification
→ pending human engineering review
```

The isolated software-regression gate uses a workspace-local state directory and `ASPENOPS_BACKEND=mock`, so it cannot accidentally instantiate licensed COM before preflight. Its selected set contains 104 tests based on the archived JUnit inventory. The workflow still requires a protected self-hosted runner labeled `self-hosted, windows, x64, aspen-licensed`.

### Pytest fail-closed behavior

`pyproject.toml` now requires:

```text
pytest >= 8.3
strict markers
strict configuration
strict xfail
ResourceWarning = error
```

This prevents misspelled configuration from being silently ignored, unexpected XPASS results from passing harmlessly and resource leaks from becoming warnings only.

## Performance evidence methodology

The full benchmark workflow compares an exact baseline ref with a candidate ref using three independent trials per scenario. It reports medians, raw samples and throughput coefficient of variation for:

- 1, 10, 100 and 1000 points;
- 1, 2, 4 and 8 Workers;
- duplicate ratios of 0%, 25% and 75%;
- cold and warm cache;
- non-convergence;
- ten sequential jobs with persistent-pool reuse.

A stable regression is gated only when both revisions have at least three trials, throughput CV is at most 5%, and the scenario is not startup-sensitive. Stable throughput loss above 5% or stable P95 growth above 5% fails the workflow.

P50/P95/P99 in the current matrix are evaluation/solve elapsed values recorded by `EvaluationResult`; end-to-end batch wall time is represented by throughput. They must not be described as queue-inclusive request latency.

## Single-main repository evidence

`docs/single-main-audit.json` and `var/consolidation/final-main-manifest.json` record that remote heads contain only `main`, all required capabilities are already in `main`, and no parallel pull request is required for consolidation.

The authoritative long-lived workflows are:

- `ci.yml`;
- `windows-control-plane.yml`;
- `generate-performance-evidence.yml`;
- `licensed-aspen-certification.yml`.

Two retired temporary branches have verified archive tags. Additional annotated tags for older historical branch tips remain an optional history enhancement. Their source names and SHAs are preserved in `var/consolidation/branch-archive-manifest.json`; the permission limitation does not affect the runtime, single-main state or validated test baseline.

## Evidence boundary after hardening

The 563-test portable result and 104-test Windows result are the authoritative inspected runtime baseline. They predate the workflow-hardening commits.

The hardening changes affect workflows, pytest configuration, workflow-governance tests, setup scripts and documentation; they do not modify AspenOps runtime modules. Pushes to `main` trigger the revised portable and Windows workflows, but a fresh green run must be observed before the revised head is described as newly validated.

## Remaining qualification

```text
PENDING_REAL_ASPEN_CERTIFICATION
```

Licensed certification requires a self-hosted Windows runner with an approved Aspen Plus or HYSYS installation, real COM server, valid license, non-confidential qualification model, verified semantic registry, meaningful constraints and balances, independent repeats, signed evidence and human engineering review.

The authoritative workflow is `.github/workflows/licensed-aspen-certification.yml`; operational setup is documented in `docs/windows-setup.md` and the certification boundaries are defined in `docs/certification.md`.
