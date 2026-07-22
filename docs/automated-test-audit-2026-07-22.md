# AspenOps 2.0 Automated Test Audit

Date: 2026-07-22  
Repository: `SUNHAOJUN22/AspenOps-Agent`

## Executive conclusion

The validated AspenOps runtime already had a broad portable suite. The audit retained that runtime and corrected reproducibility, workflow trust, runtime path policy, dependency evidence, Windows bootstrap behavior, performance evidence, licensed evidence staging and documentation drift directly on `main`. No branch or parallel PR was created.

## Verified archived evidence

Portable Actions run `29814739487`, at SHA `670e9523e915af309f16d959150cfadcd84219a6`, recorded:

```text
Python 3.11 / 3.12 / 3.13: passed
Python 3.12: 72 modules, 563 passed, 0 failed, 0 errors, 0 skipped
16.73 seconds
combined branch-aware coverage: 94.9719800747198%
statement coverage: 96.23677786818551%
branch coverage: 90.84880636604774%
coverage floor: 94.5%
```

Public Windows run `29814739334` recorded 104 passed, 0 failed, 0 errors and 0 skipped in 2.06 seconds.

These are archived validated baselines, not a current-head green claim.

## Final fail-closed layers

1. environment-loaded and directly constructed `Settings`;
2. request backend and allowed-root policy;
3. CLI output and evidence paths;
4. Worker/process ownership and scheduler fencing;
5. six-target frozen dependency audit;
6. workflow supply-chain and input governance;
7. documentation/version/operating contracts;
8. trusted performance revision ancestry;
9. licensed commit trust and realpath validation;
10. executable Windows bootstrap helper contracts;
11. signed-evidence validation and workspace staging;
12. human engineering review.

## Portable CI

`ci.yml` uses pinned `ubuntu-24.04`, full Action SHAs and exact `uv 0.11.16`. It enforces:

- strict read-only permissions and non-persistent checkout credentials;
- checked frozen dependencies;
- Linux/Windows × Python 3.11/3.12/3.13 audits—six combinations;
- separate JSON and stderr evidence for every audit target;
- execution of every target before one aggregated failure;
- Ruff, format, strict mypy and documentation contracts;
- build, Mock Demo, README commands and benchmark policy;
- exactly 14 MCP tools;
- Python 3.11/3.12/3.13 full tests with branch floor 94.5%;
- hash-pinned locked-dependency Wheel installation and CLI smoke;
- JUnit, coverage, dependency and diagnostic artifacts.

## Windows control-plane gate

`windows-control-plane.yml` uses pinned `windows-2025`, Python 3.12 and `uv 0.11.16`. It adds:

- PowerShell AST parsing;
- non-installing `-LibraryMode` helper execution;
- valid dotenv import, duplicate/unbalanced rejection and secret-safe errors;
- self-update → winget upgrade → winget install fallback tests;
- Job Object, ownership, IPC, recovery and Scheduler contracts;
- Fake Aspen Plus/HYSYS convergence;
- archive/bundle safety and realpath tests;
- documentation/version/link contracts;
- Windows CLI, Doctor smoke, JUnit and diagnostics.

## Trusted performance evidence

The performance workflow originally accepted arbitrary refs and synchronized candidate dependencies before proving the candidate belonged to the authoritative branch. It now performs trust validation before tool setup or Python execution:

```text
checkout candidate
→ fetch trusted main
→ resolve immutable candidate and baseline SHAs
→ require candidate in main history
→ require baseline in main history
→ require baseline to be an ancestor of candidate
→ create detached baseline worktree
→ frozen candidate environment
→ repeated matrices and stable-regression policy
```

Unmerged, unrelated or reverse-ordered commits cannot produce evidence that appears authoritative. Performance remains portable Mock orchestration evidence, not licensed Aspen solve performance.

## Licensed evidence chain

The protected licensed workflow now uses:

```text
exact trusted-main SHA
→ frozen sync and isolated Mock regression
→ plan/root/state realpath validation
→ preflight and explicit human approval
→ scoped real COM
→ signed-bundle verification
→ verify every required source file exists and is non-empty
→ copy preflight/report/bundle to var/ci/licensed-evidence
→ verify staged files
→ upload workspace-local var/ci only
→ human engineering review
```

This fixes two evidence risks:

- missing required files cannot silently pass as a successful certification run;
- an early failure cannot expand an undefined external state path in the upload action.

The software cannot emit `REAL_ASPEN_CERTIFIED`; the status remains `PENDING_REAL_ASPEN_CERTIFICATION` pending human review.

## Workflow governance

`tests/test_workflow_governance.py` rejects:

- additional long-lived workflows;
- drifting runners, unpinned Actions or uv versions;
- `permissions: write-all` and any arbitrary `*: write` permission;
- retained checkout credentials, `pull_request_target` and silent `continue-on-error`;
- unfrozen dependencies or weak Bash mode;
- direct dispatch-input interpolation in literal, folded, inline or shorthand `run` syntax;
- incomplete dependency-audit evidence;
- untrusted or reverse-ordered performance refs;
- arbitrary-input artifact names;
- untrusted licensed commits, missing realpath handoff or exposed signing secrets;
- licensed uploads reading external state paths;
- deletion of Windows helper, path or documentation contracts.

## Runtime path policy

The same rules cover environment loading, direct `Settings(...)`, batch requests, CLI output and certification:

- real backends require non-empty absolute allowed roots;
- state, model, registry, result, bundle and certification paths remain inside resolved roots;
- request backend must match the configured backend;
- traversal, symlink and Windows junction escapes are rejected;
- unsafe configuration fails before Aspen opens or state is created.

## Windows bootstrap

`scripts/setup_windows.ps1`:

- installs missing uv with winget;
- tries standalone `uv self update` with PATH modification disabled;
- falls back to winget upgrade/install and rechecks the actual version;
- requires `uv >= 0.11.16`;
- preserves process PATH and uses frozen dependencies;
- strictly parses `.env`;
- rejects duplicate variables and unbalanced quotes;
- reports only failing line numbers, not raw secret-bearing values;
- exposes `-LibraryMode` only for CI helper tests.

## Documentation contracts

`tests/test_documentation_contracts.py` reads the package version from `pyproject.toml` and verifies:

- README badges, package version, `__version__`, CHANGELOG and AspenOps titles agree;
- README, AGENTS, CLAUDE, CONTRIBUTING, CHANGELOG, Security and core docs exist;
- local links resolve and cannot escape the repository;
- operational guides use frozen quality commands;
- stale runner, uv, workflow and product-title guidance does not return;
- both READMEs describe all six audits;
- `.env.example` remains a portable Mock first run;
- archived evidence and real-certification boundaries remain explicit.

## Executed static and targeted checks

During the audit, the current workflow surface was repeatedly checked with:

```text
4/4 workflow YAML files parsed
workflow-governance tests passed after each final rule update
all Linux workflow run blocks passed bash -n
licensed realpath and symlink-escape tests passed
new Python governance files compiled
100-character checks passed for new Python governance files
```

The local execution environment could not clone GitHub reliably and did not provide the licensed Windows/Aspen infrastructure. Therefore these checks supplement, but do not replace, a fresh readable complete Actions artifact for the final current head.

## Evidence boundary

A fresh readable Actions artifact is required before replacing the archived 563/104 counts or publishing new coverage values. Public automation cannot instantiate proprietary Aspen servers or approve engineering assumptions.

Real certification requires licensed self-hosted Windows, an approved non-confidential model, verified semantics, meaningful constraints and balances, signing material and human engineering acceptance.
