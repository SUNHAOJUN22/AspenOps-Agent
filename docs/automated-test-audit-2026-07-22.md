# AspenOps 2.0 Automated Test Audit

Date: 2026-07-22  
Repository: `SUNHAOJUN22/AspenOps-Agent`  
Scope: automated tests, workflow trust, frozen dependencies, Windows contracts, performance evidence, licensed evidence, path policy and documentation accuracy.

## Executive conclusion

The repository already had a broad portable suite. This audit retained the validated runtime and corrected reproducibility, workflow security, path policy, dependency auditing, Windows bootstrap, performance evidence, licensed evidence and documentation directly on `main`; no new branch was created.

## Verified archived evidence

Portable Actions run `29814739487`, SHA `670e9523e915af309f16d959150cfadcd84219a6`, passed Python 3.11, 3.12 and 3.13. Python 3.12 recorded 563 passed in 16.73 seconds, combined branch-aware coverage 94.9719800747198%, statement coverage 96.23677786818551% and branch coverage 90.84880636604774% against a 94.5% floor.

Public Windows run `29814739334` recorded 104 passed in 2.06 seconds. These are archived validated baselines, not current-head claims.

## Public gates

`ci.yml` enforces pinned `ubuntu-24.04`, immutable Actions, `uv 0.11.16`, read-only permissions, frozen dependencies, six dependency audits, Ruff/format/mypy, build, Mock, README smoke, 14 MCP tools and full Python tests.

`windows-control-plane.yml` uses pinned `windows-2025`, Python 3.12 and `uv 0.11.16`. It executes PowerShell AST/helper tests, dotenv safety, uv upgrade fallbacks, Job Objects, IPC/recovery, Fake Aspen Plus/HYSYS, archives, paths, documentation, CLI and Doctor.

## Explicit dispatch guards

The performance workflow writes `dispatch-ref.txt` and `dispatch-guard.log`; a non-main ref exits with status 2 instead of creating an all-skipped run.

The licensed workflow uses an Ubuntu `dispatch-guard`; the self-hosted job has `needs: dispatch-guard`. Invalid refs fail before the licensed host is occupied.

Each run uses the workflow file in its selected ref. Current guards cannot retroactively rewrite old tags or branches, and the available connector did not provide an authoritative tag inventory.

## Performance evidence

Default baseline: `ebef32ee1f2be74df5d5c5489e7ca86d35ac7bb2`.

Candidate and baseline are resolved with `--end-of-options`, validated against main ancestry and executed with independent lockfiles, `.venv`s and scripts. All current-run evidence is written to `$RUNNER_TEMP/aspenops-performance-evidence`; upload uses `${{ runner.temp }}/aspenops-performance-evidence`. Candidate-workspace `var/benchmarks` files cannot enter the artifact.

## Licensed checkout trust

A critical issue was found: allowing any main ancestor as `expected_head_sha` could execute an old runtime, old tests and an old path validator under the current protected workflow.

The final workflow binds approval to the dispatch revision:

```text
expected_head_sha == GITHUB_SHA
initial actions/checkout HEAD == GITHUB_SHA
GITHUB_SHA is an ancestor of origin/main
detached checkout remains exactly GITHUB_SHA
```

This keeps the workflow definition, runtime code, tests and `validate_licensed_paths.py` on one commit and prevents rollback to an earlier main ancestor.

## Licensed artifact and evidence isolation

A second critical issue was found on the persistent self-hosted runner: checkout could fail before workspace `var/ci` was cleaned, while an `if: always()` upload could still read stale diagnostics from a previous run.

The final job creates and cleans a run-attempt-specific artifact directory before checkout:

```text
$RUNNER_TEMP/aspenops-licensed-artifact-<GITHUB_RUN_ID>-<GITHUB_RUN_ATTEMPT>
```

`run-metadata.txt` records run/ref/SHA data before checkout. Mock JUnit is written directly to this directory. Successful evidence is copied into its `licensed-evidence` child, and `job_status` is recorded in an always-running step. Upload reads only `${{ runner.temp }}/aspenops-licensed-artifact-${{ github.run_id }}-${{ github.run_attempt }}` and uses `if-no-files-found: error`. The licensed workflow no longer reads or uploads `var/ci`.

All real certification jobs share the fixed concurrency group `licensed-aspen-certification`, serializing Aspen Plus and HYSYS runs.

```text
ASPENOPS_STATE_DIR/licensed-certification/<GITHUB_RUN_ID>-<GITHUB_RUN_ATTEMPT>
```

The external directory is deleted and recreated, exported as `LICENSED_EVIDENCE_DIR`, and used by preflight, real execution, bundle verification, report inspection and runner-temp staging. The old fixed output paths are prohibited.

These controls prevent old-code rollback, checkout-failure contamination, backend collisions, rerun contamination, stale evidence reuse and persistent self-hosted diagnostics. The software remains `PENDING_REAL_ASPEN_CERTIFICATION` and cannot emit `REAL_ASPEN_CERTIFIED`.

## Workflow governance

Tests reject:

- extra workflows, drifting runners, unpinned Actions or uv;
- arbitrary write permissions, retained credentials or `pull_request_target`;
- unfrozen dependencies, weak Bash or incomplete audit evidence;
- skipped non-main manual dispatches instead of explicit failed guards;
- candidate input passed directly to performance checkout;
- licensed approval not equal to `GITHUB_SHA`;
- initial checkout/runtime/path-validator commit mismatch;
- shared performance environments or candidate-workspace artifacts;
- backend-specific licensed concurrency groups;
- missing run-attempt external evidence scope or `LICENSED_EVIDENCE_DIR`;
- licensed artifacts created only after checkout;
- Mock JUnit or final upload paths pointing at workspace `var/ci`;
- missing `run-metadata.txt`, `job_status` or runner-temp upload;
- artifact names without `github.run_attempt`;
- missing cleanup, realpath, secret-isolation or Windows helper contracts.

## Documentation contracts

Documentation tests check package/version/title consistency, safe links, frozen instructions, portable `.env.example`, six audits, explicit dispatch failure behavior, `GITHUB_SHA` binding, pre-checkout runner-temp artifacts, per-attempt external evidence, archived certification boundaries, and absence of chat-internal citation or sandbox-link markup.

## Validation boundary

Targeted validation reconstructs current workflow and governance files in an isolated directory, parses YAML, compiles Python, checks line length, validates Bash blocks and runs focused contract tests. These checks supplement, but do not replace, a fresh complete Actions artifact.

Public automation cannot instantiate proprietary Aspen servers. Real certification still requires licensed Windows, an approved model, verified semantics, signing material and human engineering review.
