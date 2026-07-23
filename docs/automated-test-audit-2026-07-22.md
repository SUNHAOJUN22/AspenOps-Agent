# AspenOps 2.0 Automated Test Audit

Date: 2026-07-22  
Repository: `SUNHAOJUN22/AspenOps-Agent`  
Scope: automated tests, workflow trust, frozen dependencies, Windows contracts, performance evidence, licensed evidence, path policy and documentation accuracy.

## Executive conclusion

The repository already had a broad portable suite. This audit retained the validated runtime and corrected reproducibility, workflow security, path policy, dependency auditing, Windows bootstrap, performance evidence, licensed evidence and documentation directly on `main`; no new branch was created.

## Verified archived evidence

Portable Actions run `29814739487`, SHA `670e9523e915af309f16d959150cfadcd84219a6`:

```text
72 test modules
563 passed
0 failed / 0 errors / 0 skipped
16.73 seconds
combined branch-aware coverage: 94.9719800747198%
statement coverage: 96.23677786818551%
branch coverage: 90.84880636604774%
floor: 94.5%
```

Python 3.11, 3.12 and 3.13 plus quality/build/smoke passed in that archived run. Public Windows run `29814739334` recorded 104 passed in 2.06 seconds. These are archived validated baselines, not current-head claims.

## Portable and Windows public gates

`ci.yml` enforces pinned `ubuntu-24.04`, immutable Actions, `uv 0.11.16`, read-only permissions, frozen dependencies, six complete dependency audits, Ruff/format/mypy, build, Mock, README smoke, 14 MCP tools and full Python tests.

`windows-control-plane.yml` uses pinned `windows-2025`, Python 3.12 and `uv 0.11.16`. It executes PowerShell AST/helper contracts, dotenv safety, uv upgrade fallbacks, Job Objects, IPC/recovery, Fake Aspen Plus/HYSYS, archives, paths, documentation, CLI and Doctor.

## Explicit manual-dispatch failure guards

The current performance workflow writes `dispatch-ref.txt` and `dispatch-guard.log` before checkout. A ref other than `refs/heads/main` exits with status 2 instead of producing an all-skipped run.

The licensed workflow uses an `ubuntu-24.04` `dispatch-guard` job. The self-hosted `certify` job has `needs: dispatch-guard`; an invalid ref therefore fails before the licensed Aspen machine is occupied.

Each run uses the workflow version present in its selected ref. These guards protect current authoritative definitions and cannot retroactively rewrite old tags or branches. The available connector did not provide an authoritative tag inventory, so this audit does not claim that every historical ref contains the current guard.

## Trusted and isolated performance evidence

Default baseline:

```text
ebef32ee1f2be74df5d5c5489e7ca86d35ac7bb2
```

After the guard, candidate and baseline refs are resolved with `--end-of-options`, checked against `main`, ordered by ancestry, and checked out only by validated SHA. Candidate and baseline each use their own `uv.lock`, `.venv` and benchmark script.

All current-run SHA, guard, lock, sync, JSON, Markdown and smoke evidence is written only to `$RUNNER_TEMP/aspenops-performance-evidence`; upload reads `${{ runner.temp }}/aspenops-performance-evidence`. Tracked `var/benchmarks` files cannot enter the artifact.

## Licensed checkout and evidence trust chain

The approved SHA is never passed directly to `actions/checkout`. After the Ubuntu guard succeeds, the workflow validates SHA format, commit existence and main ancestry before detached checkout and HEAD verification.

### Global serialization

All licensed Aspen Plus and HYSYS certification jobs share:

```text
concurrency group: licensed-aspen-certification
```

This prevents backend-specific runs from writing concurrently into one state space.

### Run-attempt external evidence

The previous fixed output directory could retain a prior attempt's report or bundle on a persistent self-hosted machine. The final workflow creates:

```text
ASPENOPS_STATE_DIR/licensed-certification/<GITHUB_RUN_ID>-<GITHUB_RUN_ATTEMPT>
```

The directory is removed and recreated, exported as `LICENSED_EVIDENCE_DIR`, and used consistently by preflight, `certify-licensed`, bundle verification, status inspection and workspace staging. The old fixed `$ASPENOPS_STATE_DIR/licensed-certification` path is no longer used for files.

Before the Mock software regression, `var/ci` is removed and recreated. Successful external evidence is revalidated and copied into clean `var/ci/licensed-evidence`. Artifact names include both `github.run_id` and `github.run_attempt`.

These changes prevent backend collisions, rerun contamination, stale report/bundle reuse, stale diagnostics and ambiguous retry artifacts. The software remains `PENDING_REAL_ASPEN_CERTIFICATION` and cannot emit `REAL_ASPEN_CERTIFIED`.

## Workflow governance

`tests/test_workflow_governance.py` rejects:

- extra workflows, drifting runners, unpinned Actions or uv;
- arbitrary write permissions, retained credentials or `pull_request_target`;
- unfrozen dependencies, weak Bash or incomplete dependency evidence;
- job-level ref conditions that turn invalid dispatches into skipped jobs;
- missing performance guard evidence or missing licensed Ubuntu guard dependency;
- direct checkout from candidate/approved inputs;
- unsupported runner context in job-level env;
- shared performance environments or candidate-workspace artifacts;
- backend-specific licensed concurrency groups;
- missing run-attempt evidence scope or `LICENSED_EVIDENCE_DIR` handoff;
- fixed shared licensed output file paths;
- licensed artifact names without `github.run_attempt`;
- missing realpath, secret isolation, cleanup or Windows helper contracts.

## Documentation contracts

`tests/test_documentation_contracts.py` derives the package version from `pyproject.toml` and checks README/package/CHANGELOG/title consistency, required docs, safe links, frozen instructions, portable `.env.example`, archived evidence boundaries, explicit dispatch failure documentation, run-attempt licensed evidence documentation, and absence of ChatGPT-internal citation or sandbox-link markup.

## Executed and external validation boundary

The final targeted validation reconstructs current workflows and governance files in an isolated directory, parses YAML, compiles Python tests, checks line length, validates Linux Bash blocks, and runs workflow-governance/licensed-workflow contract tests.

These checks supplement, but do not replace, a fresh full Actions artifact. Public automation cannot instantiate proprietary Aspen Automation Servers, and real certification still requires licensed Windows, an approved model, verified semantics, signing material and human engineering review.
