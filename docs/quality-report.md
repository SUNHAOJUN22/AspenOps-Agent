# AspenOps 2.0 Quality Report

## Scope

This report records the inspected portable and public-Windows baseline plus the automated-test, runtime-policy, workflow-security, dependency-audit, Windows-bootstrap and documentation hardening applied directly to `main` on 2026-07-22. It does not certify licensed Aspen physics or approve an engineering model.

Detailed evidence remains in [`automated-test-audit-2026-07-22.md`](automated-test-audit-2026-07-22.md).

## Verified archived baseline

Portable Actions run `29814739487`, head SHA `670e9523e915af309f16d959150cfadcd84219a6`, passed Python 3.11, 3.12 and 3.13 plus quality/build/smoke.

Inspected Python 3.12 evidence:

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

Public Windows Actions run `29814739334`, at the same baseline SHA, recorded:

```text
104 passed
0 failed
0 errors
0 skipped
2.06 seconds
```

These are archived validated baselines. They predate the latest hardening commits and must not be represented as a fresh result for the current head.

## Coverage position

The archived aggregate is about 0.47 percentage points above the 94.5% floor. Priority modules before any future threshold increase are `scheduler.py`, `pool.py`, `backends/mock.py`, `worker.py`, `provenance.py`, `batch.py`, `convergence.py` and `pool_manager.py`.

The floor remains unchanged because an unsupported increase would make the gate brittle without adding evidence.

## Current portable CI

`ci.yml` uses pinned `ubuntu-24.04`, immutable Action SHAs and exact `uv 0.11.16`. It enforces:

- read-only repository permission and non-persistent checkout credentials;
- `uv lock --check` and frozen dependency sync;
- vulnerability auditing for Linux and Windows on Python 3.11, 3.12 and 3.13—six supported combinations;
- execution of all six combinations even when an earlier target fails;
- separate JSON and stderr evidence for each target, JSON validation, and one final fail-closed verdict;
- explicit `json-output` preview enablement;
- Ruff lint and formatting;
- strict mypy;
- documentation-contract tests before build and smoke;
- source and Wheel builds;
- Mock end-to-end execution;
- README command smoke;
- benchmark smoke and stable-regression policy;
- exactly 14 MCP tools;
- full Python 3.11, 3.12 and 3.13 tests;
- branch-aware coverage floor 94.5%;
- JUnit, coverage JSON, durations, dependency reports and diagnostic artifacts.

`tests/test_dependency_audit_workflow.py` independently locks the six-target loop, per-target error logs, JSON validation and final aggregated failure.

### Locked-dependency Wheel gate

CI exports hash-pinned runtime requirements from `uv.lock`, synchronizes a clean environment with `uv pip sync --require-hashes`, installs the Wheel with `--offline --no-deps`, runs `uv pip check`, then exercises version, help, Demo and critical CLI surfaces. Runtime dependencies are not re-resolved during Wheel verification.

## Current public Windows gate

`windows-control-plane.yml` uses pinned `windows-2025`, Python 3.12 and exact `uv 0.11.16`. It adds:

- checked frozen Windows dependencies;
- PowerShell AST parsing of `scripts/setup_windows.ps1`;
- executable bootstrap-helper contracts through the non-installing `-LibraryMode`;
- real tests for valid dotenv import, duplicate-variable rejection, unbalanced-quote rejection and secret-safe errors;
- a mocked old-version sequence that verifies self-update → winget upgrade → winget install fallback order and version rechecks;
- repository-wide lint, formatting and strict mypy;
- documentation links, versions, titles, runner names, workflow names and first-run configuration contracts;
- process ownership, Job Object, IPC, timeout and recovery contracts;
- Scheduler active leases;
- Fake Aspen Plus/HYSYS convergence;
- archive and evidence-bundle safety;
- direct `Settings` policy, request-backend escalation, CLI-output and realpath tests;
- licensed CLI, signed-bundle and workflow contracts;
- Windows CLI and Doctor smoke;
- run-specific JUnit and diagnostics.

No new fixed selected-test count is claimed until a current JUnit artifact is readable.

## Runtime path policy

The same real-backend policy applies to environment loading, direct Python construction, batch requests, CLI outputs and licensed certification:

- real backends require non-empty `ASPENOPS_ALLOWED_ROOTS`;
- roots and state directory must be explicitly absolute;
- state directory must resolve inside one root;
- request backend must match the configured real backend;
- model, registry, result, bundle and certification outputs remain inside roots;
- realpath rejects traversal, symlink and junction escapes;
- unsafe configuration fails before Aspen preflight or state creation.

## Workflow governance and supply-chain controls

`tests/test_workflow_governance.py` locks:

- exactly four long-lived workflows;
- hosted runners pinned to `ubuntu-24.04` and `windows-2025`;
- all external Actions pinned to full SHAs;
- exact `uv 0.11.16` in every setup step;
- all six dependency-audit targets and valid JSON evidence;
- no writable contents permission or retained checkout credentials;
- no `pull_request_target` or silent `continue-on-error`;
- checked frozen dependencies everywhere;
- `set -euo pipefail` for every Bash command;
- input-injection scanning for literal, folded, inline and shorthand `run` forms;
- fixed performance concurrency and immutable baseline resolution;
- run-ID-based artifact names;
- licensed commits restricted to trusted `main` ancestry;
- canonical realpath handoff for licensed plan and state paths;
- signing secrets absent from setup and Mock regression;
- both Windows gates running direct-settings, realpath and documentation tests;
- Windows bootstrap loading `.env`, preserving PATH, checking actual versions after self-update and winget fallbacks, and checking native exit codes;
- `.env` errors reported without echoing raw values;
- retention of the executable `LibraryMode` bootstrap-helper step in Windows CI.

## Documentation contracts

`tests/test_documentation_contracts.py` verifies:

- the Chinese/English READMEs, Security, Architecture, Performance, Windows guide, quality report, test audit and certification contract exist;
- local Markdown links resolve and cannot escape the repository;
- no stale `uv`, runner, product title or deleted workflow names return;
- both READMEs contain the four workflow names and all six audit combinations;
- `.env.example` remains a portable Mock first-run configuration;
- the Windows guide describes standalone self-update, winget fallback, duplicate/unbalanced dotenv rejection and secret-safe errors;
- archived evidence and `PENDING_REAL_ASPEN_CERTIFICATION` boundaries remain explicit.

The documentation contract runs in portable CI, the public Windows gate and the isolated licensed regression gate.

## Performance evidence workflow

`generate-performance-evidence.yml` uses pinned `ubuntu-24.04` and `uv 0.11.16`, binds manual refs through environment variables, resolves the baseline to a full commit SHA, records exact revisions, creates the worktree from the resolved SHA, runs repeated portable Mock matrices and stable-regression policy, validates benchmark tooling, and uploads run-ID-named evidence.

Results remain portable orchestration evidence, not licensed Aspen solve performance.

## Licensed Aspen workflow

`licensed-aspen-certification.yml` executes:

```text
exact approved SHA checkout
→ trusted-main ancestry verification
→ lockfile validation and frozen sync
→ isolated Mock regression without real secrets
→ documentation, backend, output and realpath contracts
→ realpath validation for plan, roots and state
→ licensed preflight
→ explicit human execution approval
→ scoped real COM execution
→ signed-bundle verification
→ pending human engineering review
```

It requires absolute existing roots, an absolute state directory inside them, canonical path handoff, signing-secret isolation and final status `PENDING_REAL_ASPEN_CERTIFICATION`. Software cannot self-grant engineering certification.

## Windows bootstrap

`scripts/setup_windows.ps1`:

- uses strict PowerShell behavior;
- installs missing uv through winget;
- tries `uv self update` for an old standalone installation with PATH modification disabled;
- falls back to winget upgrade and install, checking the actual version after each attempt;
- preserves process PATH while refreshing machine/user PATH;
- checks the lock and performs frozen sync;
- creates, validates and imports `.env`;
- rejects duplicate variables and unbalanced quotes;
- reports `.env` failures by line number without echoing raw values;
- runs Doctor with the loaded backend;
- checks native exit codes;
- exposes `-LibraryMode` only for non-installing CI helper tests.

## pytest failure policy

```toml
minversion = "8.3"
addopts = "-q --strict-markers --strict-config"
xfail_strict = true
filterwarnings = ["error::ResourceWarning"]
```

Unknown configuration, unregistered markers, unexpected XPASS and resource leaks fail closed.

## Single-main status

The audit modified only the existing `main`; no branch was created. The authoritative workflows remain `ci.yml`, `windows-control-plane.yml`, `generate-performance-evidence.yml` and `licensed-aspen-certification.yml`.

## Evidence boundary

The 563-test portable result and 104-test Windows result remain the inspected baseline. A fresh readable Actions artifact is required before replacing those counts, publishing new coverage values or describing the newest head as newly green.

Targeted Settings/root/realpath tests, YAML parsing, workflow-governance tests and Bash syntax checks supplement, but do not replace, the complete Actions matrix.

## Remaining qualification

```text
PENDING_REAL_ASPEN_CERTIFICATION
```

Real certification requires native self-hosted Windows, licensed Aspen, an approved non-confidential model, verified semantics, meaningful constraints and balances, independent repeats, signing keys and human engineering review.
