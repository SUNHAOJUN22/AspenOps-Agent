# AspenOps 2.0 Automated Test Audit

Date: 2026-07-22  
Repository: `SUNHAOJUN22/AspenOps-Agent`  
Scope: automated tests, quality gates, frozen-dependency vulnerability scanning, Windows contracts, performance evidence, licensed-Aspen safeguards, runtime path policy and README accuracy.

## Executive conclusion

The validated AspenOps runtime already had a broad portable suite. This audit retained that runtime and corrected reproducibility, workflow-security, path-policy, dependency-audit, Windows-bootstrap and documentation gaps directly on `main`; no new branch was created.

Final fail-closed layers:

1. `Settings` environment loading;
2. direct `Settings(...)` construction;
3. batch/request backend policy;
4. CLI output policy;
5. licensed commit trust and realpath gates;
6. workflow and documentation governance;
7. Windows bootstrap AST and executable helper behavior;
8. preflight, signed evidence and human engineering review.

## Verified archived evidence

### Portable baseline

Actions run `29814739487`, head SHA `670e9523e915af309f16d959150cfadcd84219a6`:

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

Python 3.11, 3.12 and 3.13 jobs and quality/build/smoke completed successfully in that archived run.

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

`ci.yml`:

- uses pinned `ubuntu-24.04`;
- pins third-party Actions to full SHAs;
- pins `uv 0.11.16`;
- checks `uv.lock` and performs frozen sync;
- audits the complete frozen graph for Linux and Windows on Python 3.11, 3.12 and 3.13—six combinations;
- executes all six combinations even when an earlier target fails;
- stores separate JSON and stderr evidence for every target;
- explicitly enables `json-output`, validates each JSON document and fails once after evidence collection when any target failed;
- runs Ruff, format, strict mypy and documentation contracts before build/smoke;
- verifies README commands and the 14-tool MCP surface;
- runs the full suite on Python 3.11, 3.12 and 3.13;
- enforces branch-aware coverage floor 94.5%;
- uploads JUnit, coverage, dependency-audit and diagnostic evidence.

`tests/test_dependency_audit_workflow.py` locks the evidence-preserving loop and aggregated final failure.

The Wheel gate exports hash-pinned runtime requirements from `uv.lock`, synchronizes a clean environment with `--require-hashes`, installs the Wheel offline with `--no-deps`, runs `uv pip check`, then exercises critical CLI surfaces.

### Public Windows control plane

`windows-control-plane.yml`:

- uses pinned `windows-2025`, Python 3.12 and `uv 0.11.16`;
- parses `scripts/setup_windows.ps1` through the PowerShell AST;
- loads helpers through non-installing `-LibraryMode` and executes behavior contracts;
- verifies valid dotenv import, case-insensitive duplicate rejection, unbalanced-quote rejection and secret-safe error messages;
- mocks an old uv sequence and verifies self-update → winget upgrade → winget install fallback order with an actual version check after each attempt;
- runs lint, format and strict mypy;
- tests Job Objects, ownership, Worker IPC/recovery, Scheduler leases, convergence, archive safety and Fake Aspen/HYSYS adapters;
- runs backend-escalation, direct-settings, CLI-output, licensed realpath, documentation and workflow-governance tests;
- uploads JUnit and diagnostics.

### Performance evidence

`generate-performance-evidence.yml`:

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

`licensed-aspen-certification.yml`:

```text
exact approved SHA checkout
→ verify SHA belongs to trusted main history
→ lockfile check and frozen sync
→ isolated Mock regression without real secrets
→ documentation, backend, output and workflow contracts
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

CI briefly combined `uv audit --output-format json` with `uv 0.11.14`. JSON audit output was introduced after that version, so the gate could have failed before tests ran. All four workflows, the Windows bootstrap and governance tests now use `uv 0.11.16`; CI explicitly enables `UV_PREVIEW_FEATURES=json-output`.

The audit was expanded from Python 3.12-only checks to:

```text
linux   × Python 3.11
linux   × Python 3.12
linux   × Python 3.13
windows × Python 3.11
windows × Python 3.12
windows × Python 3.13
```

All six targets execute. Each retains a JSON result and stderr log. Invalid JSON and nonzero audit status are accumulated, and CI fails only after all evidence has been collected.

## Workflow-governance tests

`tests/test_workflow_governance.py` fails on:

- extra long-lived workflows;
- unpinned runners, Actions or uv version;
- incomplete dependency-audit targets;
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
- missing direct-settings, realpath or documentation tests from either Windows gate;
- deletion of PowerShell AST or executable helper contracts;
- Windows bootstrap that does not load `.env`, preserve PATH, verify update fallbacks or check exits;
- `.env` error handling that echoes raw entries or accepts duplicate/unbalanced values.

## Documentation-contract tests

`tests/test_documentation_contracts.py` verifies:

- README, README.en, Security, Architecture, Performance, Windows setup, quality, audit and certification files exist;
- local Markdown links resolve and cannot escape the repository;
- stale uv, runner, deleted workflow and AspenOps 1.0 guidance do not return;
- both READMEs list all workflows and six audit combinations;
- `.env.example` remains a portable Mock first-run configuration;
- Windows documentation records self-update, winget fallbacks, duplicate/unbalanced rejection and secret-safe errors;
- archived evidence and `PENDING_REAL_ASPEN_CERTIFICATION` boundaries remain explicit.

This contract runs in portable CI, public Windows CI and the isolated licensed regression gate.

## Windows bootstrap audit

`scripts/setup_windows.ps1`:

- enables strict PowerShell behavior;
- installs missing uv through winget;
- first attempts `uv self update` for old standalone installations with PATH modification disabled;
- falls back to winget upgrade and install, re-reading the actual version after each attempt;
- accepts winget agreements noninteractively;
- preserves process PATH while refreshing machine/user PATH;
- checks the lock and performs frozen sync;
- creates, validates and imports `.env`;
- rejects duplicate variables and unbalanced quotes;
- reports failures by line number without echoing raw `.env` values;
- runs Doctor with the loaded backend;
- checks native exit codes;
- exposes `-LibraryMode` solely for non-installing Windows CI helper tests.

## Executed static and targeted checks

For the current hardened workflow surface, the audit executed:

```text
4/4 workflow YAML files parsed
14/14 workflow-governance tests passed
20/20 Linux Bash run blocks passed bash -n
9/9 licensed realpath and symlink-escape tests passed
new Python governance files compiled successfully
100-character line checks passed for new Python governance files
```

PowerShell AST and helper behavior are executed by the `windows-2025` workflow; the local Linux container does not contain PowerShell.

## pytest failure policy

```toml
minversion = "8.3"
addopts = "-q --strict-markers --strict-config"
xfail_strict = true
filterwarnings = ["error::ResourceWarning"]
```

Unknown configuration, unregistered markers, unexpected XPASS and resource leaks fail closed.

## Documentation audit

The Chinese and English READMEs, Windows guide, certification guide and quality report:

- scope badges to `main` push runs;
- label 563/104 results as archived baselines;
- document pinned runners, Actions and `uv 0.11.16`;
- document all six frozen-lock audits and evidence-preserving failure behavior;
- provide frozen local quality commands;
- describe all four authoritative workflows;
- document Settings, request, CLI-output and licensed realpath safeguards;
- describe standalone self-update, winget fallback and secret-safe dotenv validation;
- separate control-plane, licensed-runtime and engineering-model validation;
- avoid claiming current green status when the latest push artifact is not observable.

## Remaining external limits

1. The newest hardened `main` requires a fresh readable Actions artifact before new passing counts or coverage values replace the archived baseline.
2. Public automation cannot instantiate proprietary Aspen Automation Servers.
3. Real certification requires self-hosted Windows, a valid license, an approved case, verified semantics, signing keys and human engineering review.
4. No finite audit can logically guarantee the absence of every future defect; this audit resolves all issues found through code inspection, archived evidence, official tool documentation, targeted execution and regression rules.

## Final decision

Retain AspenOps 2.0 as the authoritative single-main runtime. The appropriate remediation was to harden runtime policy, reproducibility, complete dependency evidence, workflow trust, executable Windows bootstrap contracts, evidence production and documentation—not replace a validated runtime or inflate coverage beyond observed evidence.
