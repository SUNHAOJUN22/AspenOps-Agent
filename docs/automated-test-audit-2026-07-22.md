# AspenOps 2.0 Automated Test Audit

Date: 2026-07-22  
Repository: `SUNHAOJUN22/AspenOps-Agent`  
Scope: automated tests, quality gates, Windows contracts, performance evidence, licensed-Aspen certification safeguards, dependency reproducibility and README accuracy.

## Executive conclusion

The validated AspenOps runtime already has a broad and unusually strong portable test suite. The audit did not find evidence that the core runtime needed a speculative rewrite. It did find reproducibility and governance gaps around the suite:

- CI environments could re-resolve `uv.lock` because dependency installation was not frozen;
- GitHub Actions were referenced by movable major-version tags rather than immutable commit SHAs;
- the public Windows gate lacked a format check, JUnit evidence and several Windows-relevant licensed-certification contract tests;
- the licensed self-hosted workflow could proceed from dependency installation to preflight without first running the exact checked-out commit's software regression tests;
- pytest configuration enforced strict markers but not strict configuration, strict xfail behavior or repository-wide `ResourceWarning` failure;
- README described a local quality command but did not explain the complete automated-test hierarchy or the exact evidence boundary.

These gaps were corrected without changing the validated AspenOps runtime modules.

## Evidence inspected

### Portable CI

Authoritative recorded run: `29814739487`  
Head SHA: `670e9523e915af309f16d959150cfadcd84219a6`

All jobs completed successfully:

- Python 3.11 tests;
- Python 3.12 tests;
- Python 3.13 tests;
- quality, build and smoke.

The Python 3.12 artifact was downloaded and independently parsed from:

- `junit-3.12.xml`;
- `coverage-3.12.json`;
- `pytest-3.12.log`.

Observed result:

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
configured CI floor: 94.5%
```

### Public Windows control plane

Authoritative recorded run: `29814739334`  
Head SHA: `670e9523e915af309f16d959150cfadcd84219a6`

The Windows artifact was downloaded and its contract log inspected.

Observed result:

```text
104 passed
0 failed
0 errors
0 skipped
2.06 seconds
```

This public runner validates Windows process, scheduler, archive and fake-backend contracts. It does not contain licensed Aspen and is not real process-model certification.

## Test-module inventory from the authoritative Python 3.12 JUnit artifact

| Test module | Cases |
|---|---:|
| `test_archive_safety_complete.py` | 37 |
| `test_aspen_open_order.py` | 1 |
| `test_aspen_process_ownership.py` | 3 |
| `test_backend_adapter_edges.py` | 21 |
| `test_backends_convergence.py` | 6 |
| `test_batch.py` | 3 |
| `test_batch_resource_limits.py` | 18 |
| `test_benchmark_comparison_policy.py` | 5 |
| `test_benchmark_repeated_trials.py` | 5 |
| `test_benchmark_scripts.py` | 9 |
| `test_cache.py` | 4 |
| `test_certification.py` | 1 |
| `test_certification_failure_edges.py` | 3 |
| `test_certification_v2.py` | 13 |
| `test_cli.py` | 10 |
| `test_compat.py` | 3 |
| `test_compat_evaluation_edges.py` | 12 |
| `test_config_registry_edge_cases.py` | 19 |
| `test_config_resource_budgets.py` | 10 |
| `test_convergence.py` | 8 |
| `test_design.py` | 3 |
| `test_doctor.py` | 1 |
| `test_evaluation.py` | 3 |
| `test_evaluation_plan.py` | 5 |
| `test_evaluation_plan_write_conflicts.py` | 3 |
| `test_factory_policy_benchmark.py` | 13 |
| `test_hysys_convergence_contracts.py` | 28 |
| `test_job_store.py` | 4 |
| `test_job_store_lease_recovery.py` | 5 |
| `test_job_store_lease_strictness.py` | 3 |
| `test_job_store_owner_fencing.py` | 4 |
| `test_licensed_bundle_integrity.py` | 10 |
| `test_licensed_certification.py` | 31 |
| `test_licensed_certification_cli.py` | 8 |
| `test_licensed_certification_governance.py` | 2 |
| `test_licensed_certification_remaining_edges.py` | 12 |
| `test_licensed_certification_validation_edges.py` | 27 |
| `test_licensed_certification_workflow.py` | 5 |
| `test_mcp.py` | 1 |
| `test_mcp_tools.py` | 5 |
| `test_models.py` | 3 |
| `test_models_strict_contracts.py` | 16 |
| `test_optimization.py` | 2 |
| `test_optimization_contracts.py` | 6 |
| `test_optimization_edge_cases.py` | 6 |
| `test_optimization_interfaces.py` | 2 |
| `test_optimization_validation_complete.py` | 13 |
| `test_optimizer.py` | 3 |
| `test_optimizer_complete_edges.py` | 24 |
| `test_pool_cache_efficiency.py` | 4 |
| `test_pool_manager.py` | 4 |
| `test_pool_manager_creation.py` | 5 |
| `test_provenance.py` | 5 |
| `test_provenance_edge_cases.py` | 4 |
| `test_provenance_zip_absolute_path.py` | 1 |
| `test_provenance_zip_safety.py` | 6 |
| `test_registry.py` | 5 |
| `test_result_protocol_contracts.py` | 17 |
| `test_scheduler.py` | 2 |
| `test_scheduler_active_leases.py` | 4 |
| `test_scheduler_claimed_lease_fencing.py` | 1 |
| `test_scheduler_edge_cases.py` | 5 |
| `test_scheduler_multiprocess_races.py` | 8 |
| `test_scheduler_restart_fencing.py` | 4 |
| `test_singleflight.py` | 1 |
| `test_small_logic_edges.py` | 10 |
| `test_units.py` | 4 |
| `test_v2_reliability.py` | 5 |
| `test_windows_job.py` | 4 |
| `test_windows_job_edges.py` | 4 |
| `test_worker_contracts.py` | 11 |
| `test_worker_protocol_hardening.py` | 10 |

## Coverage review

The aggregate coverage gate is strong, but it has approximately 0.47 percentage points of headroom above the configured floor. The following modules are the primary future test targets:

| Source module | Branch-aware coverage | Audit interpretation |
|---|---:|---|
| `scheduler.py` | 85.95% | Highest remaining state, lease, retry and terminal-transition complexity |
| `pool.py` | 87.28% | Worker lifecycle, timeout and recovery branches remain expensive to reproduce |
| `backends/mock.py` | 88.00% | Small module; a few uncovered branches materially affect its percentage |
| `worker.py` | 89.20% | Spawn, IPC and fatal-error paths are intentionally defensive and branch-heavy |
| `provenance.py` | 90.40% | File-system and malformed-bundle error paths remain the main gap |
| `batch.py` | 91.12% | Resource-limit and orchestration edges remain |
| `convergence.py` | 91.20% | Contradictory or inaccessible convergence evidence remains branch-heavy |
| `pool_manager.py` | 94.49% | Essentially at the repository coverage threshold |

These are not release blockers for the validated baseline. They are the prioritized locations for future tests before raising the global coverage floor.

## Automated gates after hardening

### `.github/workflows/ci.yml`

Triggers:

- push to `main`;
- pull requests;
- manual dispatch.

Enforces:

- immutable action SHAs;
- read-only repository permissions and non-persistent checkout credentials;
- `uv lock --check`;
- frozen dependency synchronization;
- Ruff lint and format;
- strict mypy;
- source and wheel build;
- portable Mock demo;
- README command-path smoke tests;
- benchmark smoke and committed stable-regression policy;
- 14-tool MCP surface verification;
- clean-wheel CLI smoke;
- full pytest suite on Python 3.11, 3.12 and 3.13;
- branch coverage floor 94.5%;
- JUnit, JSON coverage, slowest-test and log artifacts.

### `.github/workflows/windows-control-plane.yml`

Triggers:

- push to `main`;
- pull requests;
- manual dispatch.

Enforces on Windows Python 3.12:

- frozen lockfile installation;
- Ruff lint and format;
- strict mypy;
- process ownership and Windows Job Object contracts;
- convergence and fake-backend contracts;
- worker protocol and singleflight behavior;
- scheduler active-lease behavior;
- archive and provenance ZIP safety;
- licensed-bundle, licensed-CLI and licensed-workflow contracts;
- Windows CLI and Doctor smoke;
- JUnit and diagnostics artifacts.

The expanded selected suite contains 127 tests based on the authoritative JUnit inventory. The exact count remains evidence only after the hardened workflow completes successfully.

### `.github/workflows/generate-performance-evidence.yml`

Manual workflow that:

- accepts exact baseline and candidate refs;
- verifies the candidate lockfile;
- uses a frozen candidate environment;
- creates an exact baseline worktree;
- runs independent benchmark trials;
- compares medians and variation;
- fails on stable throughput or P95 regressions above policy thresholds;
- lints, formats, type-checks and smoke-tests benchmark tooling;
- uploads the full comparison evidence.

This is portable Mock orchestration evidence, not licensed Aspen solve-performance evidence.

### `.github/workflows/licensed-aspen-certification.yml`

Manual protected workflow that:

- requires a full approved commit SHA;
- checks out that exact commit without persistent write credentials;
- verifies the lockfile and uses frozen dependencies;
- runs 104 targeted software-regression tests before preflight;
- validates the certification plan without opening COM;
- requires explicit approval before real execution;
- executes only on `self-hosted, windows, x64, aspen-licensed`;
- verifies the signed evidence bundle;
- prevents software from self-granting final engineering certification;
- uploads JUnit, preflight, report and signed bundle evidence.

The runtime must continue to report `PENDING_REAL_ASPEN_CERTIFICATION` until human engineering review is complete.

## Pytest fail-closed configuration

The repository configuration now enforces:

```toml
minversion = "8.3"
addopts = "-q --strict-markers --strict-config"
xfail_strict = true
filterwarnings = ["error::ResourceWarning"]
```

This prevents unknown configuration from being silently ignored, prevents unexpected XPASS results from being treated as harmless and promotes resource leaks to test failures in both CI and ordinary local runs.

## Remaining limitations

1. The authoritative 563-test and 104-test results predate the hardening commits and remain the validated runtime baseline.
2. GitHub push-triggered runs for the new workflow revisions must complete before those revisions can claim a fresh green result.
3. Public CI cannot instantiate proprietary Aspen Automation Servers or prove a process model is physically valid.
4. The licensed workflow requires external Windows infrastructure, a valid license, an approved non-confidential model, verified semantic paths, signing keys and human engineering approval.
5. A future coverage-floor increase should be preceded by targeted tests in `scheduler.py`, `pool.py`, `worker.py` and `provenance.py`; the current margin is too small for an unsupported threshold increase.

## Audit decision

The automated-test architecture is comprehensive enough to retain the AspenOps 2.0 runtime as the authoritative `main` implementation. The appropriate action was to harden reproducibility, evidence production and certification sequencing rather than rewrite validated runtime code or inflate the coverage threshold beyond observed evidence.
