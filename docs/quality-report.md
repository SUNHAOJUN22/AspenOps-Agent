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

Public Windows run `29814739334` recorded 104 passed in 2.06 seconds with no failures, errors or skips.

These are archived validated baselines, not fresh current-head results.

## Current portable and Windows gates

`ci.yml` uses `ubuntu-24.04`, immutable Action SHAs and `uv 0.11.16`. It enforces read-only permissions, frozen dependencies, six Linux/Windows/Python dependency audits with complete evidence, Ruff/format/mypy, documentation contracts, source/Wheel build, Mock/README/MCP smoke and the full Python matrix with branch-aware floor 94.5%.

`windows-control-plane.yml` uses `windows-2025`, Python 3.12 and `uv 0.11.16`. It includes PowerShell AST and executable helper tests, dotenv safety, uv upgrade fallbacks, Job Object/IPC/recovery contracts, Fake Aspen Plus/HYSYS, archive/path/documentation contracts, CLI and Doctor smoke.

No new fixed count is claimed without a readable current JUnit artifact.

## Runtime path policy

Real backends require non-empty absolute allowed roots. State, model, registry, result, bundle and certification outputs must resolve inside those roots. Backend mismatch, traversal, symlink and junction escapes fail before Aspen opens or state is created.

## Workflow governance

`tests/test_workflow_governance.py` locks:

- exactly four authoritative workflows;
- pinned runners, Actions and uv;
- no block, commented, inline or `write-all` permissions;
- no retained credentials, `pull_request_target` or silent `continue-on-error`;
- frozen dependencies and fail-closed Bash;
- dispatch-input isolation;
- complete six-target dependency evidence;
- explicit failed guards for non-main performance and licensed dispatches;
- performance guard evidence written before checkout;
- a lightweight Ubuntu licensed guard before the self-hosted Aspen job;
- input refs and SHAs validated before detached checkout;
- separate baseline/candidate lockfiles, environments and scripts;
- performance artifacts isolated in the runner temporary directory;
- trusted licensed SHA, realpath, secret isolation and clean evidence staging;
- Windows helper and documentation contracts.

## Trusted and isolated performance evidence

The default baseline is:

```text
ebef32ee1f2be74df5d5c5489e7ca86d35ac7bb2
```

The first Ubuntu step always records `dispatch-ref.txt` and `dispatch-guard.log` under `$RUNNER_TEMP/aspenops-performance-evidence`. A ref other than `refs/heads/main` exits with status 2, so an invalid manual dispatch fails rather than becoming an all-skipped run.

After the guard succeeds, the workflow loads the trusted main revision, resolves candidate and baseline with `--end-of-options`, requires both in `main`, requires baseline ancestry, and only then performs detached candidate checkout and baseline worktree creation.

It creates two independent frozen environments:

```text
candidate/uv.lock → candidate .venv → candidate script
baseline/uv.lock  → baseline .venv  → baseline script
```

All current-run SHAs, logs, JSON and reports are written only to `$RUNNER_TEMP/aspenops-performance-evidence`. The upload action uses `${{ runner.temp }}/aspenops-performance-evidence`; job-level `env` does not use the runner context. Tracked `var/benchmarks` files cannot enter the artifact.

Results remain portable Mock orchestration evidence, not licensed Aspen solve performance.

## Licensed evidence chain

A fixed `ubuntu-24.04` `dispatch-guard` job runs first. A non-main ref exits with status 2 and marks the workflow failed. The self-hosted `certify` job declares `needs: dispatch-guard`, so an invalid dispatch never consumes the licensed Aspen machine.

The approved SHA is not passed directly to checkout:

```text
Ubuntu guard explicitly requires GITHUB_REF == refs/heads/main
→ checkout the trusted main workflow revision
→ validate SHA format, commit existence and main ancestry
→ detached checkout of the validated SHA and verify HEAD
→ validate the plan in that checkout
→ frozen Mock regression → realpath → preflight and approval
→ real COM → signed-bundle verification → require non-empty evidence
→ clean var/ci/licensed-evidence staging → upload workspace var/ci only
→ human review
```

Early failures cannot expand an undefined external state path, and stale self-hosted-runner staging is removed before copying. Software cannot self-grant `REAL_ASPEN_CERTIFIED`.

## Documentation contracts

`tests/test_documentation_contracts.py` derives the version from `pyproject.toml` and verifies package/README/CHANGELOG/title consistency, required documents, safe local links, frozen operating guides, portable `.env.example`, archived evidence boundaries, explicit manual-dispatch failure documentation, and absence of ChatGPT-internal citation or sandbox-link markup.

## Evidence boundary

The 563-test portable and 104-test Windows figures remain the inspected baseline. File inspection, YAML parsing, governance tests, Bash syntax checks and targeted tests supplement—but do not replace—a fresh complete Actions artifact.

Real certification still requires licensed Windows, an approved non-confidential model, verified semantics, constraints/balances, independent repeats, signing material and human engineering review.
