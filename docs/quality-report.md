# AspenOps 2.0 Quality Report

## Scope

This report records the verified portable and public-Windows baseline plus the automated-test, workflow-security, path-policy and Windows-bootstrap hardening applied directly to `main` on 2026-07-22. It does not certify licensed Aspen physics or approve an engineering model.

Detailed evidence is retained in `docs/automated-test-audit-2026-07-22.md`.

## Verified portable baseline

GitHub Actions run `29814739487`, head SHA `670e9523e915af309f16d959150cfadcd84219a6`, passed Python 3.11, 3.12 and 3.13 tests plus quality/build/smoke.

The inspected Python 3.12 artifacts recorded:

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

`.github/workflows/ci.yml` uses pinned `ubuntu-24.04`, immutable Action SHAs and exact `uv 0.11.14`. It enforces:

- read-only repository permission and non-persistent checkout credentials;
- `uv lock --check` and frozen dependencies;
- Ruff lint and formatting;
- strict mypy;
- source and wheel builds;
- Mock end-to-end execution;
- README version/help/dry-run/benchmark/certification command smoke;
- benchmark smoke and stable-regression policy;
- exactly 14 MCP tools;
- full Python 3.11, 3.12 and 3.13 tests;
- branch-aware coverage floor 94.5%;
- JUnit, coverage JSON, durations and diagnostic artifacts.

### Locked-dependency Wheel gate

The Wheel smoke does not resolve dependencies from the network ad hoc. It exports hash-pinned runtime requirements from `uv.lock`, synchronizes a clean environment with `uv pip sync --require-hashes`, installs the built Wheel with `--offline --no-deps`, runs `uv pip check`, then exercises version, help, Demo and critical CLI surfaces.

## Current public Windows gate

`.github/workflows/windows-control-plane.yml` uses pinned `windows-2025`, Python 3.12 and exact `uv 0.11.14`. It adds:

- checked frozen Windows dependencies;
- PowerShell AST parsing of `scripts/setup_windows.ps1`;
- repository-wide lint, formatting and strict mypy;
- process ownership, Job Object, IPC, timeout and recovery contracts;
- Scheduler active leases;
- Fake Aspen Plus/HYSYS convergence;
- archive and evidence-bundle safety;
- direct `Settings` path policy, request-backend escalation, CLI-output and realpath tests;
- licensed certification CLI, signed-bundle and workflow contracts;
- Windows CLI and Doctor smoke;
- run-specific JUnit and diagnostic artifacts.

No new fixed selected-test count is claimed until a current JUnit artifact is readable.

## Runtime path policy

The same real-backend policy is enforced across environment loading, direct Python construction, batch requests, CLI output paths and licensed certification:

- real backends require non-empty `ASPENOPS_ALLOWED_ROOTS`;
- roots and state directory must be explicitly absolute;
- state directory must resolve inside one of the roots;
- request backend must match configured real backend;
- model, registry, result, bundle and certification output paths remain inside roots;
- realpath resolution rejects `..`, symlink and junction escapes;
- unsafe configuration fails before Aspen preflight or state-directory creation.

## Workflow governance and supply-chain controls

`tests/test_workflow_governance.py` locks:

- exactly four long-lived workflows;
- hosted runner images pinned to `ubuntu-24.04` and `windows-2025`;
- all external Actions pinned to full SHAs;
- exact `uv 0.11.14` in every setup step;
- no writable contents permission;
- no retained checkout credentials;
- no `pull_request_target` or silent `continue-on-error`;
- checked frozen dependencies everywhere;
- no manual `${{ inputs.* }}` interpolation inside Shell or PowerShell blocks;
- fixed performance concurrency and immutable baseline SHA resolution;
- artifact names based on `github.run_id`;
- licensed commits restricted to trusted `main` ancestry;
- canonical realpath handoff for licensed plan and state paths;
- signing secrets absent from setup and Mock regression;
- Windows bootstrap loading `.env`, preserving PATH, checking minimum `uv` and native exit codes;
- both Windows gates running direct-settings and realpath policy tests.

## Performance evidence workflow

`.github/workflows/generate-performance-evidence.yml` uses pinned `ubuntu-24.04`, binds manual refs through environment variables, resolves the baseline to a full commit SHA, records baseline/candidate SHAs, creates the worktree from the resolved SHA, uses a frozen candidate environment, runs independent trials and stable-regression policy, validates benchmark tooling, and uploads run-ID-named evidence.

Results remain `portable-mock-orchestration` evidence and cannot be presented as real Aspen solve performance.

## Licensed Aspen workflow

`.github/workflows/licensed-aspen-certification.yml` executes:

```text
exact approved SHA checkout
→ trusted-main ancestry verification
→ lockfile validation and frozen dependency sync
→ isolated Mock software regression without real secrets
→ realpath validation for plan, allowed roots and state target
→ licensed preflight
→ explicit human execution approval
→ scoped real COM execution
→ signed-bundle verification
→ pending human engineering review
```

It additionally enforces:

- manual inputs bound through environment variables rather than injected into PowerShell;
- one-line repository-relative plan path inside the checkout;
- absolute existing allowed-root directories;
- absolute state output inside an allowed root;
- traversal, symlink and junction escape rejection;
- canonical paths passed through `GITHUB_ENV`;
- `dev + windows + agent + signing` dependencies;
- Mock isolation before any real COM preflight;
- signing secrets scoped only to preflight and real execution;
- run-ID-based artifact names;
- final status `PENDING_REAL_ASPEN_CERTIFICATION`.

Software cannot self-grant engineering certification.

## Windows bootstrap

`scripts/setup_windows.ps1`:

- uses strict PowerShell behavior;
- installs `uv` only when missing;
- accepts winget agreements noninteractively;
- refreshes machine/user PATH while preserving process PATH;
- verifies `uv >= 0.11.14`;
- checks the lock and performs frozen sync;
- creates and imports `.env`;
- runs Doctor with the loaded backend;
- checks native exit codes;
- avoids printing secrets.

`.env.example` exposes request, batch, semantic-operation and optimization resource budgets plus licensed-state placement rules.

## pytest failure policy

```toml
minversion = "8.3"
addopts = "-q --strict-markers --strict-config"
xfail_strict = true
filterwarnings = ["error::ResourceWarning"]
```

Unknown configuration, unregistered markers, unexpected XPASS and resource leaks fail closed.

## Single-main status

The repository remains governed directly on `main`; no new branch was created for this audit. The authoritative workflows are:

- `ci.yml`;
- `windows-control-plane.yml`;
- `generate-performance-evidence.yml`;
- `licensed-aspen-certification.yml`.

## Evidence boundary

The 563-test portable result and 104-test Windows result remain the inspected, verified baseline. They predate the latest hardening commits. A fresh current Actions artifact is required before replacing those numbers or describing the newest head as newly green.

Targeted local execution for the latest root and realpath policy changes passed. It supplements, but does not replace, the full Actions matrix.

## Remaining qualification

```text
PENDING_REAL_ASPEN_CERTIFICATION
```

Real certification requires a native self-hosted Windows runner, licensed Aspen Plus or HYSYS, an approved non-confidential model, verified semantic paths, meaningful constraints and balances, independent repeats, signing keys and human engineering review.
