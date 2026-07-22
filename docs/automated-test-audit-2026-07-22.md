# AspenOps 2.0 Automated Test Audit

Date: 2026-07-22  
Repository: `SUNHAOJUN22/AspenOps-Agent`  
Scope: automated tests, quality gates, Windows contracts, performance evidence, licensed-Aspen safeguards, runtime path policy, dependency reproducibility and README accuracy.

## Executive conclusion

The AspenOps 2.0 runtime already had a broad validated portable suite. The audit retained that runtime and corrected reproducibility, workflow-security, path-policy, Windows-bootstrap and documentation gaps directly on `main`; no new branch was created.

The final design fails closed at several independent layers:

1. `Settings` environment loading;
2. direct `Settings(...)` construction;
3. batch/request backend policy;
4. CLI output policy;
5. licensed workflow trust and realpath gates;
6. preflight, signed evidence and human engineering review.

## Verified evidence inspected

### Portable baseline

Actions run: `29814739487`  
Head SHA: `670e9523e915af309f16d959150cfadcd84219a6`

Inspected Python 3.12 JUnit, coverage JSON and pytest log:

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
configured floor: 94.5%
```

Python 3.11, 3.12 and 3.13 jobs and the quality/build/smoke job all completed successfully in that archived run.

### Public Windows baseline

Actions run: `29814739334`  
Head SHA: `670e9523e915af309f16d959150cfadcd84219a6`

```text
104 passed
0 failed
0 errors
0 skipped
2.06 seconds
```

This proves Windows control-plane contracts, not licensed Aspen physics.

## Coverage review

The archived aggregate has about 0.47 percentage points of margin above the 94.5% floor.

| Source module | Archived branch-aware coverage | Priority |
|---|---:|---|
| `scheduler.py` | 85.95% | lease, retry and terminal transitions |
| `pool.py` | 87.28% | worker lifecycle and recovery |
| `backends/mock.py` | 88.00% | remaining deterministic branches |
| `worker.py` | 89.20% | spawn, IPC and fatal paths |
| `provenance.py` | 90.40% | file-system and malformed-bundle paths |
| `batch.py` | 91.12% | orchestration/resource limits |
| `convergence.py` | 91.20% | contradictory/inaccessible evidence |
| `pool_manager.py` | 94.49% | near current global floor |

The global floor was not raised merely for appearance.

## Authoritative workflows

The repository contains exactly four long-lived workflows.

### Portable CI

`.github/workflows/ci.yml`

- triggers on `main` push, pull requests and manual dispatch;
- uses pinned `ubuntu-24.04`;
- pins third-party Actions to full commit SHAs;
- pins `uv 0.11.14`;
- checks `uv.lock` and performs frozen sync;
- runs Ruff, format, strict mypy, build and Mock Demo;
- verifies README command paths and the 14-tool MCP surface;
- runs the complete test suite on Python 3.11, 3.12 and 3.13;
- enforces branch-aware coverage floor 94.5%;
- uploads JUnit, coverage JSON, durations and logs.

The Wheel smoke exports hash-pinned runtime requirements from `uv.lock`, synchronizes a clean environment with `--require-hashes`, installs the Wheel offline with `--no-deps`, runs `uv pip check`, then exercises critical CLI surfaces.

### Public Windows control plane

`.github/workflows/windows-control-plane.yml`

- uses pinned `windows-2025` and Python 3.12;
- pins exact Action and `uv` versions;
- parses `scripts/setup_windows.ps1` through the PowerShell AST;
- runs lint, format and strict mypy;
- tests Job Objects, process ownership, Worker IPC/recovery, Scheduler leases, convergence, archive safety and Fake Aspen/HYSYS adapters;
- runs backend-escalation, direct-settings, CLI-output, licensed realpath and workflow-governance tests;
- uploads JUnit and diagnostics.

### Performance evidence

`.github/workflows/generate-performance-evidence.yml`

- uses pinned `ubuntu-24.04`;
- binds manual refs through environment variables;
- resolves the baseline to a full immutable commit SHA;
- creates the baseline worktree from that SHA;
- records exact baseline and candidate revisions;
- uses a fixed trusted concurrency group;
- runs repeated portable Mock matrices and stable-regression policy;
- validates benchmark scripts with Ruff, format, mypy and smoke execution;
- names artifacts with `github.run_id`.

Performance results remain portable orchestration evidence, not licensed Aspen solve-performance evidence.

### Licensed Aspen certification

`.github/workflows/licensed-aspen-certification.yml`

```text
exact approved SHA checkout
→ verify SHA belongs to trusted main history
→ lockfile check and frozen sync
→ isolated Mock software regression without real secrets
→ realpath validation for plan, roots and state target
→ licensed preflight
→ explicit human execution approval
→ scoped real COM execution
→ signed-bundle verification
→ pending human engineering review
```

The workflow:

- runs only on `self-hosted, windows, x64, aspen-licensed`;
- uses a protected environment;
- keeps signing secrets out of dependency setup and Mock regression;
- accepts a repository-relative single-line plan path;
- requires absolute existing allowed roots and an absolute state directory inside them;
- rejects traversal, symlink and junction escapes through `scripts/validate_licensed_paths.py`;
- persists canonical paths through `GITHUB_ENV`;
- runs direct-settings, backend-escalation, CLI-output and realpath regression tests before real execution;
- names artifacts with trusted backend choice plus `github.run_id`;
- cannot emit `REAL_ASPEN_CERTIFIED`.

## Runtime path-policy audit

The final runtime policy is consistent across all entry points:

- real backends require non-empty `ASPENOPS_ALLOWED_ROOTS`;
- environment loading and direct `Settings(...)` construction reject rootless real configurations;
- roots and state path must be explicitly absolute;
- state path must resolve inside an allowed root;
- request backend must match configured backend;
- model, registry, CLI output, result bundle and certification output paths remain inside allowed roots;
- realpath resolution rejects parent traversal, symlink and junction escape;
- unsafe configuration fails before Aspen preflight or state-directory creation.

Targeted local execution of the latest Settings/root/realpath cases passed. This supplements but does not replace the complete Actions matrix.

## Workflow-governance regression tests

`tests/test_workflow_governance.py` fails on:

- extra long-lived workflows;
- unpinned hosted runner images, Actions or `uv` version;
- writable contents permission or retained checkout credentials;
- `pull_request_target` or silent `continue-on-error`;
- unfrozen dependency installation;
- direct dispatch-input interpolation in shell blocks;
- raw baseline refs used for worktree execution;
- arbitrary-input artifact names;
- untrusted licensed commit ancestry;
- missing realpath/canonical-path handoff;
- secrets exposed to setup or Mock regression;
- missing direct-settings and realpath tests from either Windows gate;
- Windows bootstrap that does not load `.env`, preserve PATH, enforce minimum `uv` or check exit codes.

`tests/test_licensed_certification_workflow.py` separately locks exact trust ordering, secret scope, dependency extras, path gate, signed evidence and no-self-certification behavior.

## Windows bootstrap audit

`scripts/setup_windows.ps1`:

- enables strict PowerShell behavior;
- installs `uv` through winget only when missing;
- accepts package/source agreements noninteractively;
- refreshes machine/user PATH while retaining process PATH;
- enforces `uv >= 0.11.14`;
- checks the lock and performs frozen sync;
- creates, validates and imports `.env`;
- runs Doctor with the loaded backend;
- checks native-command exit codes;
- avoids printing secrets.

## pytest failure policy

```toml
minversion = "8.3"
addopts = "-q --strict-markers --strict-config"
xfail_strict = true
filterwarnings = ["error::ResourceWarning"]
```

Unknown configuration, unregistered markers, unexpected XPASS and resource leaks fail rather than silently pass.

## Documentation audit

The Chinese and English READMEs, Windows setup guide and quality report now:

- scope badges to `main` push runs;
- label 563/104 results as archived validated baselines;
- document pinned runners, Actions and `uv`;
- provide frozen local installation and quality commands;
- describe all four authoritative workflows;
- document Settings, request, CLI-output and licensed realpath safeguards;
- describe the actual Windows bootstrap behavior;
- separate control-plane, licensed-runtime and engineering-model validation;
- avoid claiming current green status when the latest push artifact is not observable through the available connector.

## Remaining external limits

1. The newest hardened `main` requires a fresh readable Actions artifact before a new passing count or coverage value replaces the archived baseline.
2. Public automation cannot instantiate proprietary Aspen Automation Servers.
3. Real certification requires native self-hosted Windows, a valid license, an approved non-confidential model, verified semantic paths, signing keys and human engineering review.
4. No audit can logically guarantee absence of every future defect; this audit resolves all issues found through code inspection, archived evidence, targeted execution and regression rules.

## Final decision

Retain AspenOps 2.0 as the authoritative single-main runtime. The correct remediation was to harden runtime policy, reproducibility, workflow trust, Windows setup, evidence production and documentation—not replace a validated runtime or inflate coverage beyond observed evidence.
