# AspenOps 2.0 Automated Test Audit

Date: 2026-07-22  
Repository: `SUNHAOJUN22/AspenOps-Agent`  
Branch policy: direct updates to the existing `main`; no new branch was created.

## Scope

This audit covers:

- portable Python tests and branch coverage;
- Linux and Windows quality gates;
- build, wheel, CLI, MCP and README command smoke tests;
- performance-regression evidence;
- licensed Aspen workflow sequencing and safeguards;
- GitHub Actions supply-chain and input handling;
- Windows bootstrap behavior;
- dependency reproducibility;
- pytest failure policy;
- documentation accuracy.

## Executive conclusion

The existing runtime had a broad, validated automated-test baseline and did not justify a speculative rewrite. The audit found and corrected repository-governance, setup and workflow issues around that runtime:

1. dependency sync was not consistently frozen;
2. third-party Actions used movable major tags;
3. public Windows checks lacked format, JUnit and several certification-interface tests;
4. licensed execution did not first run a same-commit software regression gate;
5. pytest configuration did not fail closed on unknown config, unexpected XPASS or resource leaks;
6. README did not distinguish archived evidence, current workflow status and real Aspen certification;
7. the Windows bootstrap copied `.env` but did not load it;
8. installing `uv` did not reliably refresh the current process PATH;
9. PATH refresh risked discarding process-specific entries;
10. manual workflow inputs were interpolated directly into Shell or PowerShell bodies;
11. performance refs were used before conversion to immutable commit SHAs;
12. user-controlled refs appeared in artifact names;
13. the licensed plan path was not canonicalized and persisted across steps;
14. licensed state output was not explicitly constrained to absolute allowed roots;
15. no repository-level test locked the workflow governance rules;
16. one Windows-path assertion could interpret `\v` as a Python escape and fail incorrectly.

All issues found in this static and evidence-backed audit were corrected directly on `main`.

## Verified baseline evidence

### Portable CI

Authoritative archived run: `29814739487`  
Head SHA: `670e9523e915af309f16d959150cfadcd84219a6`

Jobs passed for Python 3.11, 3.12, 3.13 and the quality/build/smoke job.

The Python 3.12 artifact was downloaded and independently inspected through its JUnit, coverage JSON and pytest log:

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

Authoritative archived run: `29814739334`  
Head SHA: `670e9523e915af309f16d959150cfadcd84219a6`

```text
104 passed
0 failed
0 errors
0 skipped
2.06 seconds
```

The public Windows runner had no licensed Aspen installation. These results prove control-plane contracts, not real process-model validity.

## Coverage assessment

The aggregate gate is strong but has only about 0.47 percentage points of margin above the configured floor. Primary future targets remain:

| Source module | Archived branch-aware coverage | Reason to prioritize |
|---|---:|---|
| `scheduler.py` | 85.95% | lease, retry, restart and terminal-transition complexity |
| `pool.py` | 87.28% | lifecycle, timeout and recovery branches |
| `backends/mock.py` | 88.00% | small module with material uncovered branches |
| `worker.py` | 89.20% | spawn, IPC and fatal-error handling |
| `provenance.py` | 90.40% | malformed bundle and filesystem paths |
| `batch.py` | 91.12% | resource limits and orchestration edges |
| `convergence.py` | 91.20% | contradictory and inaccessible evidence |
| `pool_manager.py` | 94.49% | already near the repository threshold |

The floor remains 94.5%. Raising it without first adding targeted tests would create a brittle gate rather than better evidence.

## Current automated gates

### `ci.yml`

Triggers on `main` push, pull request and manual dispatch. It enforces:

- full-SHA pinned Actions;
- read-only contents permission;
- non-persistent checkout credentials;
- `uv lock --check` and frozen dependency sync;
- Ruff lint and format;
- strict mypy;
- source and wheel build;
- Mock end-to-end demo;
- README command-path smoke tests;
- benchmark smoke and stable-regression policy;
- exact 14-tool MCP surface;
- clean-wheel CLI smoke;
- full tests on Python 3.11, 3.12 and 3.13;
- branch coverage floor 94.5%;
- JUnit, coverage JSON, durations and diagnostic artifacts.

### `windows-control-plane.yml`

Triggers on `main` push, pull request and manual dispatch. It enforces on Windows Python 3.12:

- the same immutable and frozen dependency policy;
- Ruff lint and format;
- strict mypy;
- Windows Job Object and process-ownership rules;
- Worker IPC, timeout, recovery and singleflight;
- Scheduler active leases;
- convergence and Fake Aspen Plus/HYSYS adapters;
- archive and evidence-bundle safety;
- licensed certification CLI, workflow and signed-bundle contracts;
- repository-wide workflow-governance tests;
- CLI and Doctor smoke;
- JUnit and diagnostic artifacts.

The archived run contains 104 passing tests. No new fixed count is claimed for the expanded selected suite until a current JUnit artifact is readable.

### `generate-performance-evidence.yml`

The protected manual benchmark workflow now:

- binds baseline and candidate inputs through environment variables;
- never interpolates manual inputs into shell bodies;
- uses a checked and frozen candidate environment;
- resolves the baseline ref to a full immutable commit SHA;
- records exact baseline and candidate SHAs;
- creates the baseline worktree from the resolved SHA rather than raw input;
- runs independent benchmark trials;
- compares medians and coefficient of variation;
- fails stable throughput or P95 regressions above policy;
- checks benchmark scripts with Ruff, format, mypy and smoke execution;
- names artifacts with `github.run_id` rather than user-controlled refs.

This remains portable Mock orchestration evidence, not licensed Aspen solve-performance evidence.

### `licensed-aspen-certification.yml`

The protected workflow now requires:

- exact approved lowercase 40-character commit SHA;
- pinned Actions, read-only permissions and no retained checkout credentials;
- manual inputs bound through environment variables;
- a one-line repository-relative plan path;
- canonical plan path constrained to the checked-out workspace;
- a one-line absolute certification state directory;
- one-line semicolon-separated absolute allowed roots;
- certification state output inside an allowed root;
- canonical plan/state paths persisted through `GITHUB_ENV`;
- checked, frozen `dev + windows + agent + signing` dependencies;
- an isolated Mock software-regression gate before preflight;
- explicit human approval before real COM execution;
- signed-bundle verification;
- a final status that remains `PENDING_REAL_ASPEN_CERTIFICATION`;
- artifacts named with trusted backend choice plus `github.run_id`.

Software cannot self-grant final engineering certification.

## Workflow governance tests

`tests/test_workflow_governance.py` fails if the repository regresses to any of the following:

- extra long-lived workflow files;
- unpinned third-party Actions;
- writable contents permissions;
- checkout credentials retained;
- `pull_request_target` or silent `continue-on-error`;
- unfrozen dependency installation;
- direct manual-input interpolation into shell blocks;
- raw baseline refs passed to `git worktree`;
- artifact names based on arbitrary inputs;
- licensed plan or state paths without canonical handoff;
- state directories outside allowed roots;
- Windows bootstrap that does not load `.env`, preserve PATH or check exit codes.

`tests/test_licensed_certification_workflow.py` separately locks the licensed workflow’s exact sequencing, dependency extras, Mock isolation, path checks, signed evidence and no-self-certification boundary.

## Windows bootstrap audit

`scripts/setup_windows.ps1` now:

- enables strict PowerShell behavior;
- installs `uv` only when missing;
- accepts required winget agreements noninteractively;
- refreshes machine and user PATH while retaining the original process PATH;
- verifies `uv` after installation;
- checks `uv.lock` and performs frozen sync;
- creates `.env` only when absent;
- validates and imports `.env` into the current process;
- runs Doctor with the loaded backend;
- checks every native command exit code;
- avoids printing secret values.

## pytest failure policy

```toml
minversion = "8.3"
addopts = "-q --strict-markers --strict-config"
xfail_strict = true
filterwarnings = ["error::ResourceWarning"]
```

Unknown pytest configuration, unregistered markers, unexpected XPASS and resource leaks therefore fail rather than silently pass.

## Documentation audit

The Chinese and English READMEs now:

- scope badges to `main` push runs;
- label 563/104 results as archived validated baselines;
- provide frozen local installation and quality commands;
- document the four authoritative workflows;
- explain workflow input, ref, artifact and path safeguards;
- describe the actual Windows bootstrap behavior;
- separate control-plane, licensed runtime and engineering-model validation;
- avoid claiming current green status when the latest push run is not observable through the available connector.

`docs/windows-setup.md`, `docs/quality-report.md`, `.env.example` and the workflow files use the same terminology and boundaries.

## Remaining external limits

1. The latest hardened `main` requires a fresh readable Actions artifact before a new passing test count or coverage value can replace the archived baseline.
2. Public automation cannot instantiate proprietary Aspen Automation Servers.
3. Real certification requires a native self-hosted Windows runner, a valid license, an approved non-confidential model, verified semantic paths, signing keys and human engineering review.
4. This audit cannot logically guarantee the absence of every future defect; it resolves all issues found through repository inspection, archived evidence, workflow tracing and static regression rules.

## Final decision

Retain the existing AspenOps 2.0 runtime as the authoritative `main`. The correct remediation was to harden reproducibility, workflow security, Windows setup, evidence production and documentation—not replace a validated runtime or inflate coverage beyond observed evidence.
