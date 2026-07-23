# AspenOps 2.0 Quality Report

## Scope

This report records automated-test, workflow-trust, runtime-policy, dependency-audit, Windows-bootstrap, performance-evidence, licensed-evidence and documentation hardening applied directly to `main`. It does not certify Aspen physics or approve an engineering model.

Historical detail is retained in [`automated-test-audit-2026-07-22.md`](automated-test-audit-2026-07-22.md).

## Verified archived baseline

Portable Actions run `29814739487`, at SHA `670e9523e915af309f16d959150cfadcd84219a6`, passed Python 3.11, 3.12 and 3.13 plus quality/build/smoke. Inspected Python 3.12 evidence:

```text
72 test modules
563 passed
0 failed / 0 errors / 0 skipped
16.73 seconds
combined branch-aware coverage: 94.9719800747198%
statement coverage: 96.23677786818551%
branch coverage: 90.84880636604774%
CI floor: 94.5%
```

Public Windows run `29814739334` recorded 104 passed in 2.06 seconds with no failures, errors or skips. These are archived validated baselines, not fresh current-head results.

## Current portable and Windows gates

`ci.yml` uses `ubuntu-24.04`, immutable Action SHAs and `uv 0.11.16`. It enforces read-only permissions, frozen dependencies, six Linux/Windows/Python dependency audits with complete evidence, Ruff/format/mypy, documentation contracts, source/Wheel build, Mock/README/MCP smoke and the full Python matrix with branch-aware floor 94.5%.

`windows-control-plane.yml` uses `windows-2025`, Python 3.12 and `uv 0.11.16`. It includes PowerShell AST and executable helper tests, dotenv safety, uv upgrade fallbacks, Job Object/IPC/recovery contracts, Fake Aspen Plus/HYSYS, archive/path/documentation contracts, CLI and Doctor smoke.

No new fixed count is claimed without a readable current JUnit artifact.

## Workflow governance

`tests/test_workflow_governance.py` locks:

- exactly four authoritative workflows;
- pinned runners, Actions and uv;
- no arbitrary write permissions, retained credentials or `pull_request_target`;
- frozen dependencies and fail-closed Bash;
- complete six-target dependency evidence;
- explicit failed guards for non-main performance and licensed dispatches;
- input refs and SHAs validated before detached checkout;
- separate baseline/candidate environments and runner-temporary performance artifacts;
- one global licensed-certification concurrency group;
- run-attempt-scoped external evidence through `LICENSED_EVIDENCE_DIR`;
- cleanup of Mock diagnostics, external evidence and workspace staging;
- run-attempt-qualified licensed artifact names;
- Windows helper and documentation contracts.

## Trusted and isolated performance evidence

The default baseline is:

```text
ebef32ee1f2be74df5d5c5489e7ca86d35ac7bb2
```

The first Ubuntu step records `dispatch-ref.txt` and `dispatch-guard.log` under `$RUNNER_TEMP/aspenops-performance-evidence`. A ref other than `refs/heads/main` exits with status 2. After the guard succeeds, the workflow validates candidate/baseline ancestry, creates two independent frozen environments and writes all current-run evidence only to runner temporary storage. The upload action uses `${{ runner.temp }}/aspenops-performance-evidence`.

Results remain portable Mock orchestration evidence, not licensed Aspen solve performance.

## Licensed evidence chain

A fixed `ubuntu-24.04` `dispatch-guard` job runs first. A non-main ref exits with status 2. The self-hosted `certify` job has `needs: dispatch-guard`, so invalid dispatches do not consume the licensed Aspen machine.

All real certification jobs share:

```text
concurrency group: licensed-aspen-certification
```

This group serializes all Aspen Plus and HYSYS certification runs.

External output is unique to the workflow attempt:

```text
ASPENOPS_STATE_DIR/licensed-certification/<GITHUB_RUN_ID>-<GITHUB_RUN_ATTEMPT>
```

The workflow removes and recreates this directory, exports `LICENSED_EVIDENCE_DIR`, and uses it for preflight, real execution, bundle verification, report inspection and workspace staging. The old fixed `$ASPENOPS_STATE_DIR/licensed-certification` output is no longer used.

Before Mock regression, `var/ci` is removed and recreated. Successful external evidence is revalidated and copied into clean `var/ci/licensed-evidence`. Artifact names include both `github.run_id` and `github.run_attempt`.

These controls prevent backend collisions, rerun contamination, stale report/bundle reuse and stale self-hosted workspace diagnostics. Software cannot self-grant `REAL_ASPEN_CERTIFIED`.

## Documentation contracts

`tests/test_documentation_contracts.py` derives the version from `pyproject.toml` and verifies package/README/CHANGELOG/title consistency, required documents, safe local links, frozen operating guides, portable `.env.example`, archived evidence boundaries, explicit dispatch failure documentation, per-attempt licensed evidence documentation, and absence of ChatGPT-internal citation or sandbox-link markup.

## Evidence boundary

The 563-test portable and 104-test Windows figures remain the inspected baseline. File inspection, YAML parsing, governance tests, Bash syntax checks and targeted tests supplement—but do not replace—a fresh complete Actions artifact.

Real certification still requires licensed Windows, an approved non-confidential model, verified semantics, constraints/balances, independent repeats, signing material and human engineering review.
