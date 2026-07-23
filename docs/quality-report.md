# AspenOps 2.0 Quality Report

## Scope

This report records the inspected portable and public-Windows baseline and the automated-test, workflow-trust, runtime-policy, dependency-audit, Windows-bootstrap, performance-evidence, licensed-evidence and documentation hardening applied directly to `main`. It does not certify licensed Aspen physics or approve an engineering model.

Detailed historical evidence is retained in [`automated-test-audit-2026-07-22.md`](automated-test-audit-2026-07-22.md).

## Verified archived baseline

Portable Actions run `29814739487`, at SHA `670e9523e915af309f16d959150cfadcd84219a6`, passed Python 3.11, 3.12 and 3.13 plus quality/build/smoke. Inspected Python 3.12 evidence recorded:

```text
72 test modules
563 passed
0 failed / 0 errors / 0 skipped
16.73 seconds
combined branch-aware coverage: 94.9719800747198%
statement coverage: 96.23677786818551%
branch coverage: 90.84880636604774%
CI coverage floor: 94.5%
```

Public Windows run `29814739334` recorded 104 passed, 0 failed, 0 errors and 0 skipped in 2.06 seconds.

These are archived validated baselines. They predate the latest hardening and must not be presented as a fresh current-head result.

## Current portable CI

`ci.yml` uses pinned `ubuntu-24.04`, immutable Action SHAs and exact `uv 0.11.16`. It enforces:

- strictly read-only workflow permissions and non-persistent checkout credentials;
- `uv lock --check` and frozen dependency sync;
- Linux/Windows audits for Python 3.11, 3.12 and 3.13—six combinations;
- separate JSON and stderr evidence per audit target;
- execution of all six targets before one aggregated fail-closed verdict;
- Ruff, formatting, strict mypy and documentation contracts;
- source/Wheel build, Mock Demo and README command smoke;
- benchmark policy and exactly 14 MCP tools;
- full Python 3.11/3.12/3.13 tests with branch-aware floor 94.5%;
- JUnit, coverage, dependency and diagnostic artifacts.

The Wheel gate exports hash-pinned runtime requirements from `uv.lock`, synchronizes with `--require-hashes`, installs the Wheel using `--offline --no-deps`, runs `uv pip check`, then exercises critical CLI surfaces.

## Current public Windows gate

`windows-control-plane.yml` uses pinned `windows-2025`, Python 3.12 and `uv 0.11.16`. It adds:

- PowerShell AST parsing and executable `-LibraryMode` helper tests;
- valid dotenv import, duplicate/unbalanced rejection and secret-safe errors;
- self-update → winget upgrade → winget install fallback tests;
- Windows Job Object, ownership, IPC, recovery and Scheduler contracts;
- Fake Aspen Plus/HYSYS convergence and archive/bundle safety;
- direct Settings, backend-escalation, CLI-output and realpath tests;
- documentation/version/link contracts;
- Windows CLI, Doctor smoke, JUnit and diagnostics.

No new fixed count is claimed without a readable current JUnit artifact.

## Runtime path policy

The same fail-closed real-backend policy applies to environment loading, direct `Settings(...)`, batch requests, CLI outputs and licensed certification:

- non-empty allowed roots are mandatory;
- roots and state must be explicitly absolute;
- state, model, registry, result, bundle and certification outputs remain inside resolved roots;
- request backend must match the configured real backend;
- traversal, symlink and junction escapes are rejected;
- unsafe configuration fails before Aspen opens or state is created.

## Workflow governance

`tests/test_workflow_governance.py` locks:

- exactly four authoritative workflows;
- pinned hosted runners, Actions and uv version;
- no block, commented, inline or `write-all` workflow permission;
- no retained checkout credentials, `pull_request_target` or silent `continue-on-error`;
- frozen dependencies and `set -euo pipefail` for Bash;
- input-injection scanning across literal, folded, inline and shorthand `run` forms;
- complete six-target dependency evidence;
- run-ID-scoped artifact names;
- trusted revision checks before candidate checkout or performance code execution;
- independent baseline/candidate lockfiles, virtual environments and benchmark scripts;
- trusted-main licensed SHA, realpath handoff and secret isolation;
- clean workspace-staged licensed evidence before upload;
- Windows bootstrap helper execution and documentation contracts.

## Trusted and isolated performance evidence

`generate-performance-evidence.yml` uses the validated main-history runtime below as its default baseline:

```text
ebef32ee1f2be74df5d5c5489e7ca86d35ac7bb2
```

It validates trust before setup, candidate checkout or Python execution:

```text
checkout current trusted main workflow revision
→ fetch trusted main history and tags
→ resolve candidate_ref and baseline_ref with --end-of-options
→ require both immutable SHAs to belong to main
→ require baseline to be an ancestor of candidate
→ detached checkout of validated candidate SHA
→ create detached baseline worktree
```

The manual candidate input is never passed directly to `actions/checkout`.

It then creates and records two independent frozen environments:

```text
candidate/uv.lock → candidate .venv → candidate benchmark script
baseline/uv.lock  → baseline .venv  → baseline benchmark script
```

Both lockfiles are checked independently, both environments synchronize with `--frozen`, and both revisions execute the benchmark script stored in their own repository. This prevents candidate input, dependencies, source or harness changes from contaminating the baseline. An incompatible baseline must fail explicitly rather than silently changing the comparison method.

Results remain portable Mock orchestration evidence, not licensed Aspen solve performance.

## Licensed evidence chain

`licensed-aspen-certification.yml` executes:

```text
trusted exact SHA
→ frozen sync and isolated Mock regression
→ realpath validation
→ preflight and explicit human approval
→ scoped real COM
→ signed-bundle verification
→ verify all evidence files are present and non-empty
→ clean and stage preflight/report/bundle in var/ci/licensed-evidence
→ upload workspace-local var/ci only
→ human engineering review
```

The upload step never expands an undefined external state path. Early failures can collect only workspace-local diagnostics. Software remains unable to self-grant `REAL_ASPEN_CERTIFIED`.

## Documentation contracts

`tests/test_documentation_contracts.py` derives the package version from `pyproject.toml` and verifies:

- README badge/package version, `__version__`, CHANGELOG and AspenOps titles agree;
- README, AGENTS, CLAUDE, CONTRIBUTING, CHANGELOG, Security and core docs exist;
- local links resolve and cannot escape the repository;
- current guides contain no stale uv, runner, workflow or product-title guidance;
- AGENTS and CONTRIBUTING require frozen quality gates;
- README documents all six audit targets;
- `.env.example` remains a portable Mock first-run configuration;
- archived evidence and `PENDING_REAL_ASPEN_CERTIFICATION` remain explicit.

## Evidence boundary

The 563-test portable result and 104-test Windows result remain the inspected baseline. File-level inspection, YAML parsing, governance tests, Bash syntax checks and targeted path tests supplement—but do not replace—a fresh complete Actions artifact for the current head.

Real certification still requires native licensed Windows, an approved non-confidential model, verified semantics, meaningful constraints and balances, independent repeats, signing material and human engineering review.
