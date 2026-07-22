# AspenOps 2.0 Automated Test Audit

Date: 2026-07-22  
Repository: `SUNHAOJUN22/AspenOps-Agent`  
Scope: automated tests, quality gates, Windows contracts, performance evidence, dependency vulnerability scanning, licensed-Aspen safeguards, runtime path policy and README accuracy.

## Executive conclusion

The validated AspenOps runtime already had a broad portable suite. The audit retained that runtime and corrected reproducibility, workflow-security, path-policy, dependency-audit, Windows-bootstrap and documentation gaps directly on `main`; no new branch was created.

Final fail-closed layers:

1. `Settings` environment loading;
2. direct `Settings(...)` construction;
3. batch/request backend policy;
4. CLI output policy;
5. licensed commit trust and realpath gates;
6. preflight, signed evidence and human engineering review.

## Verified archived evidence

### Portable baseline

Actions run `29814739487`, head SHA `670e9523e915af309f16d959150cfadcd84219a6`.

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

Python 3.11, 3.12 and 3.13 jobs and quality/build/smoke all completed successfully in that archived run.

### Public Windows baseline

Actions run `29814739334`, at the same SHA:

```text
104 passed
0 failed
0 errors
0 skipped
2.06 seconds
```

This proves Windows control-plane contracts, not licensed Aspen physics.

## Coverage review

The archived aggregate has about 0.47 percentage points of margin above the 94.5% floor. Future tests should prioritize `scheduler.py`, `pool.py`, `backends/mock.py`, `worker.py`, `provenance.py`, `batch.py`, `convergence.py` and `pool_manager.py` before raising the global threshold.

## Authoritative workflows

The repository contains exactly four long-lived workflows.

### Portable CI

`.github/workflows/ci.yml`:

- uses pinned `ubuntu-24.04`;
- pins third-party Actions to full SHAs;
- pins `uv 0.11.16`;
- checks `uv.lock` and performs frozen sync;
- audits the frozen Python 3.12 dependency graph for Linux and Windows, saving JSON evidence;
- runs Ruff, format, strict mypy, build and Mock Demo;
- verifies README commands and the 14-tool MCP surface;
- runs the full suite on Python 3.11, 3.12 and 3.13;
- enforces branch-aware coverage floor 94.5%;
- uploads JUnit, coverage JSON, durations and logs.

The Wheel gate exports hash-pinned runtime requirements from `uv.lock`, synchronizes a clean environment with `--require-hashes`, installs the Wheel offline with `--no-deps`, runs `uv pip check`, then exercises critical CLI surfaces.

### Public Windows control plane

`.github/workflows/windows-control-plane.yml`:

- uses pinned `windows-2025`, Python 3.12 and `uv 0.11.16`;
- parses `scripts/setup_windows.ps1` through the PowerShell AST;
- runs lint, format and strict mypy;
- tests Job Objects, ownership, Worker IPC/recovery, Scheduler leases, convergence, archive safety and Fake Aspen/HYSYS adapters;
- runs backend-escalation, direct-settings, CLI-output, licensed realpath and workflow-governance tests;
- uploads JUnit and diagnostics.

### Performance evidence

`.github/workflows/generate-performance-evidence.yml`:

- uses pinned `ubuntu-24.04` and `uv 0.11.16`;
- binds manual refs through environment variables;
- resolves the baseline to a full immutable SHA;
- creates the worktree from that SHA;
- records exact baseline/candidate revisions;
- uses a fixed trusted concurrency group;
- runs repeated portable Mock matrices and stable-regression policy;
- validates benchmark scripts with Ruff, format, mypy and smoke execution;
- names artifacts with `github.run_id`.

Performance results remain portable orchestration evidence, not licensed Aspen solve-performance evidence.

### Licensed Aspen certification

`.github/workflows/licensed-aspen-certification.yml`:

```text
exact approved SHA checkout
→ verify SHA belongs to trusted main history
→ lockfile check and frozen sync
→ isolated Mock regression without real secrets
→ realpath validation for plan, roots and state
→ licensed preflight
→ explicit human execution approval
→ scoped real COM execution
→ signed-bundle verification
→ pending human engineering review
```

It runs only on `self-hosted, windows, x64, aspen-licensed`, uses a protected environment, requires absolute existing roots and state placement inside them, rejects traversal/symlink/junction escapes, persists canonical paths through `GITHUB_ENV`, keeps signing secrets out of setup/Mock regression, and cannot emit `REAL_ASPEN_CERTIFIED`.

## Runtime path-policy audit

The final policy is consistent across every entry point:

- real backends require non-empty `ASPENOPS_ALLOWED_ROOTS`;
- environment loading and direct `Settings(...)` reject rootless real configurations;
- roots and state path must be explicitly absolute;
- state path must resolve inside an allowed root;
- request backend must match configured backend;
- model, registry, CLI output, result bundle and certification paths remain inside roots;
- realpath rejects parent traversal, symlink and junction escape;
- unsafe configuration fails before preflight or state creation.

Targeted execution of the latest Settings/root/realpath cases passed. This supplements but does not replace the complete Actions matrix.

## Dependency-audit compatibility issue found

During the audit, CI briefly combined `uv audit --output-format json` with `uv 0.11.14`. JSON audit output was introduced after that version, so the gate could have failed before tests ran. All four workflows, the Windows bootstrap and governance tests were aligned to `uv 0.11.16`, and regression tests now require a JSON-capable version whenever JSON audit output is configured.

## Workflow-governance tests

`tests/test_workflow_governance.py` fails on:

- extra long-lived workflows;
- unpinned runners, Actions or uv version;
- JSON audit paired with an incapable uv version;
- writable contents permission or retained checkout credentials;
- `pull_request_target` or silent `continue-on-error`;
- unfrozen dependency installation;
- weak Bash mode;
- direct dispatch-input interpolation through literal, folded, inline or shorthand `run` syntax;
- raw baseline refs used for worktree execution;
- arbitrary-input artifact names;
- untrusted licensed commit ancestry;
- missing realpath/canonical-path handoff;
- secrets exposed to setup or Mock regression;
- missing direct-settings/realpath tests from either Windows gate;
- Windows bootstrap that does not load `.env`, preserve PATH, enforce minimum uv or check exit codes.

## Windows bootstrap audit

`scripts/setup_windows.ps1`:

- enables strict PowerShell behavior;
- installs `uv` only when missing;
- accepts winget agreements noninteractively;
- preserves process PATH while refreshing machine/user PATH;
- enforces `uv >= 0.11.16`;
- checks the lock and performs frozen sync;
- creates, validates and imports `.env`;
- runs Doctor with the loaded backend;
- checks native exit codes;
- avoids printing secrets.

## pytest failure policy

```toml
minversion = "8.3"
addopts = "-q --strict-markers --strict-config"
xfail_strict = true
filterwarnings = ["error::ResourceWarning"]
```

Unknown configuration, unregistered markers, unexpected XPASS and resource leaks fail closed.

## Documentation audit

The Chinese and English READMEs, Windows guide, certification guide and quality report now:

- scope badges to `main` push runs;
- label 563/104 results as archived baselines;
- document pinned runners, Actions and `uv 0.11.16`;
- document Linux/Windows frozen-lock vulnerability auditing;
- provide frozen local quality commands;
- describe all four authoritative workflows;
- document Settings, request, CLI-output and licensed realpath safeguards;
- describe the actual Windows bootstrap behavior;
- separate control-plane, licensed-runtime and engineering-model validation;
- avoid claiming current green status when the latest push artifact is not observable through the available connector.

## Remaining external limits

1. The newest hardened `main` requires a fresh readable Actions artifact before new passing counts or coverage values replace the archived baseline.
2. Public automation cannot instantiate proprietary Aspen Automation Servers.
3. Real certification requires self-hosted Windows, a valid license, an approved case, verified semantics, signing keys and human engineering review.
4. No finite audit can logically guarantee the absence of every future defect; this audit resolves all issues found through code inspection, archived evidence, official tool documentation, targeted execution and regression rules.

## Final decision

Retain AspenOps 2.0 as the authoritative single-main runtime. The appropriate remediation was to harden runtime policy, reproducibility, dependency auditing, workflow trust, Windows setup, evidence production and documentation—not replace a validated runtime or inflate coverage beyond observed evidence.
