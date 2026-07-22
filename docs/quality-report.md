# AspenOps 2.0 Quality Report

## Scope

This report records the portable and public-Windows evidence for the AspenOps 2.0
control plane. It does not certify licensed Aspen Plus or Aspen HYSYS physical
results.

## Latest verified portable gate

The authoritative complete portable matrix is GitHub Actions run
`29814739487`. It validated Python 3.11, 3.12 and 3.13 with:

- Ruff linting;
- Ruff formatting;
- strict mypy over `src`;
- pytest with branch coverage and `ResourceWarning` promoted to an error;
- source and wheel builds;
- portable Mock demo;
- benchmark smoke and committed stable-regression policy;
- MCP surface verification;
- clean Python 3.12 wheel installation, version command, demo and licensed CLI
  help smoke.

Observed Python 3.12 result:

```text
563 tests passed
combined branch-aware coverage: 94.9719800747198%
statement coverage: 96.23677786818551%
branch coverage: 90.84880636604774%
CI coverage floor: 94.5%
```

The coverage gate is measured with `--cov-branch`. No core module is omitted to
inflate the result, and the floor was not reduced during single-main
consolidation.

## Public Windows control-plane gate

The authoritative public-Windows run is `29814739334`. It validates:

- strict type and lint compatibility on Windows Python 3.12;
- Job Object setup and `KILL_ON_JOB_CLOSE` contracts;
- process fingerprint and descendant ownership checks;
- Fake Aspen Plus and HYSYS convergence adapters;
- Worker IPC and staged-model cleanup;
- durable Scheduler lease and owner-fencing contracts;
- bounded ZIP archive verification;
- PoolManager creation singleflight and license accounting.

This runner has no licensed Aspen installation. Its success is evidence about the
control plane, not simulator qualification.

## Safety-critical regression suites

### Convergence

Unknown, absent, contradictory or unstable evidence fails closed. Tests cover
positive and negative states, status access errors, timeouts and stable-idle
requirements.

### Transactions

Tests cover original-value capture, current-node rollback, numeric tolerance,
rollback verification failure and automatic recycling of a tainted Worker.

### Durable scheduling

Tests cover lease acquisition, heartbeat, expiration, final-attempt dead letter,
service restart, cancellation, owner fencing, idempotent commits, active-job
heartbeat and stale bundle cleanup.

### Worker lifecycle

Tests cover model-copy, Pipe and process startup failures; ready/result/close
protocol validation; send, poll and receive failures; hard timeout; graceful close;
and bounded fatal diagnostics.

### Archive safety

Tests cover archive and member size limits, member count, compression ratio, path
traversal, absolute and drive paths, duplicate and encrypted members, unsupported
compression, malformed JSON roots, malformed signing declarations and bounded
member reads.

### Optimization

Tests cover continuous, integer, categorical and ordinal variables; hard evaluation
budgets; non-finite inputs and outputs; Deb feasibility ordering; Pareto behavior;
checkpoint safety; cancellation; batch evaluation and interface limits.

## Performance evidence methodology

The full benchmark workflow compares an exact baseline ref with `main` using three
independent trials per scenario. It reports medians, raw samples and throughput CV
for:

- 1, 10, 100 and 1000 points;
- 1, 2, 4 and 8 Workers;
- duplicate ratios of 0%, 25% and 75%;
- cold and warm cache;
- non-convergence;
- ten sequential jobs with persistent-pool reuse.

A stable regression is gated only when both revisions have at least three trials,
throughput CV is at most 5%, and the scenario is not startup-sensitive. Stable
throughput loss above 5% or stable P95 growth above 5% fails the workflow.

P50/P95/P99 in the current matrix are evaluation/solve elapsed values recorded by
`EvaluationResult`; end-to-end batch wall time is represented by throughput. The
report must not describe those percentiles as queue-inclusive request latency.

All benchmark results are labeled `portable-mock-orchestration` and must not be
used as licensed Aspen solve-performance claims.

## Single-main repository evidence

`docs/single-main-audit.json` and `var/consolidation/final-main-manifest.json`
record that remote heads contain only `main`. The four authoritative long-lived
workflows are:

- `ci.yml`;
- `windows-control-plane.yml`;
- `generate-performance-evidence.yml`;
- `licensed-aspen-certification.yml`.

The full historical annotated-tag recovery gate remains blocked because the
acting GitHub App lacks `Workflows: write`. The blocker is documented separately
and does not invalidate the runtime, CI, Windows or performance results.

## Remaining qualification

```text
PENDING_REAL_ASPEN_CERTIFICATION
```

Certification requires a self-hosted Windows runner with approved Aspen Plus and
HYSYS releases, real COM servers, representative models and an available license
service. The procedure is documented in `docs/real-aspen-certification.md`.
