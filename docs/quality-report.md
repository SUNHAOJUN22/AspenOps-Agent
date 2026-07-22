# AspenOps 2.0 Quality Report

## Scope

This report records the verified portable and public-Windows baseline plus the automated-test, workflow-security and Windows-bootstrap hardening applied directly to `main` on 2026-07-22. It does not certify licensed Aspen physics or approve an engineering model.

Detailed evidence is retained in `docs/automated-test-audit-2026-07-22.md`.

## Verified portable baseline

GitHub Actions run `29814739487`, head SHA `670e9523e915af309f16d959150cfadcd84219a6`, passed Python 3.11, 3.12 and 3.13 tests plus quality/build/smoke.

The Python 3.12 JUnit, coverage JSON and pytest log were independently inspected:

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

The gate uses branch coverage and does not omit core runtime modules to inflate the total.

## Verified public Windows baseline

GitHub Actions run `29814739334`, at the same baseline SHA, produced:

```text
104 passed
0 failed
0 errors
0 skipped
2.06 seconds
```

It validated Windows process ownership, Job Objects, Worker IPC, Fake Aspen Plus/HYSYS convergence, Scheduler leases, archive safety and PoolManager accounting. The runner had no licensed Aspen installation.

## Coverage position

The archived combined result is about 0.47 percentage points above the 94.5% floor. Priority modules before any future threshold increase are:

| Module | Archived branch-aware coverage |
|---|---:|
| `scheduler.py` | 85.95% |
| `pool.py` | 87.28% |
| `backends/mock.py` | 88.00% |
| `worker.py` | 89.20% |
| `provenance.py` | 90.40% |
| `batch.py` | 91.12% |
| `convergence.py` | 91.20% |
| `pool_manager.py` | 94.49% |

The floor remains unchanged because an unsupported increase would make the gate brittle without adding evidence.

## Current portable CI

`.github/workflows/ci.yml` enforces:

- immutable Action commit SHAs;
- read-only contents permission;
- non-persistent checkout credentials;
- checked, frozen dependencies;
- Ruff lint and format;
- strict mypy;
- source and wheel builds;
- Mock end-to-end execution;
- README version/help/dry-run/benchmark/certification command smoke;
- benchmark smoke and stable-regression policy;
- exactly 14 MCP tools;
- clean-wheel CLI smoke;
- full Python 3.11, 3.12 and 3.13 tests;
- branch-aware coverage floor 94.5%;
- JUnit, coverage JSON, durations and diagnostic artifacts.

## Current public Windows gate

`.github/workflows/windows-control-plane.yml` adds:

- checked frozen Windows dependencies;
- repository-wide lint and formatting;
- strict mypy;
- process ownership, Job Object, IPC, timeout and recovery contracts;
- Scheduler active leases;
- Fake Aspen Plus/HYSYS convergence;
- archive and evidence-bundle safety;
- licensed certification CLI, signed-bundle and workflow contracts;
- repository-wide workflow-governance tests;
- Windows CLI and Doctor smoke;
- run-specific JUnit and diagnostic artifacts.

No new fixed selected-test count is claimed until a current JUnit artifact is readable.

## Workflow governance and supply-chain controls

`tests/test_workflow_governance.py` locks the following repository rules:

- exactly four long-lived workflows;
- all external Actions pinned to full SHAs;
- no writable contents permission;
- no retained checkout credentials;
- no `pull_request_target` or silent `continue-on-error`;
- `uv lock --check` and `uv sync --frozen` everywhere;
- no manual `${{ inputs.* }}` interpolation inside Shell or PowerShell blocks;
- performance baseline resolved to an immutable commit before worktree creation;
- artifact names based on `github.run_id`, not arbitrary inputs;
- canonical licensed plan and state-path handoff;
- licensed state directory constrained to absolute allowed roots;
- Windows bootstrap loading `.env`, preserving PATH and checking exit codes.

## Performance evidence workflow

`.github/workflows/generate-performance-evidence.yml` now:

- binds manual refs through environment variables;
- resolves the baseline to a full commit SHA;
- records exact baseline and candidate SHAs;
- creates the worktree from the resolved SHA;
- uses a frozen candidate environment;
- runs independent trials and stable-regression policy;
- checks benchmark tooling with Ruff, format, mypy and smoke execution;
- uploads run-ID-named evidence.

Results remain `portable-mock-orchestration` evidence and cannot be presented as real Aspen solve performance.

## Licensed Aspen workflow

`.github/workflows/licensed-aspen-certification.yml` executes:

```text
exact approved SHA checkout
→ canonical plan/state-path validation
→ lockfile validation and frozen dependency sync
→ isolated Mock software regression
→ licensed preflight
→ explicit human execution approval
→ scoped real COM execution
→ signed-bundle verification
→ pending human engineering review
```

It additionally enforces:

- manual inputs bound through environment variables instead of injected into PowerShell;
- one-line repository-relative plan path inside the workspace;
- one-line absolute certification state path;
- one-line semicolon-separated absolute allowed roots;
- state output located inside an allowed root;
- canonical plan and state paths passed through `GITHUB_ENV`;
- `dev + windows + agent + signing` dependencies;
- Mock isolation before any real COM preflight;
- run-ID-based artifact names;
- final status `PENDING_REAL_ASPEN_CERTIFICATION`.

Software cannot self-grant engineering certification.

## Windows bootstrap

`scripts/setup_windows.ps1` now:

- uses strict PowerShell behavior;
- installs `uv` only when missing;
- accepts winget agreements noninteractively;
- refreshes machine/user PATH while preserving process PATH;
- verifies `uv` is callable;
- checks the lock and performs frozen sync;
- creates and imports `.env`;
- runs Doctor with the loaded backend;
- checks native exit codes;
- avoids printing secrets.

`.env.example` now exposes the runtime’s request, batch, semantic-operation and optimization resource budgets as well as licensed-state placement rules.

## pytest failure policy

```toml
minversion = "8.3"
addopts = "-q --strict-markers --strict-config"
xfail_strict = true
filterwarnings = ["error::ResourceWarning"]
```

Unknown configuration, unregistered markers, unexpected XPASS and resource leaks fail closed.

## Single-main status

The repository remains governed directly on `main`; no new branch was created for this audit. The authoritative long-lived workflows are:

- `ci.yml`;
- `windows-control-plane.yml`;
- `generate-performance-evidence.yml`;
- `licensed-aspen-certification.yml`.

## Evidence boundary

The 563-test portable result and 104-test Windows result remain the inspected, verified baseline. They predate the latest hardening commits. A fresh current Actions artifact is required before replacing those numbers or describing the newest head as newly green.

## Remaining qualification

```text
PENDING_REAL_ASPEN_CERTIFICATION
```

Real certification requires a native self-hosted Windows runner, licensed Aspen Plus or HYSYS, an approved non-confidential model, verified semantic paths, meaningful constraints and balances, independent repeats, signing keys and human engineering review.
