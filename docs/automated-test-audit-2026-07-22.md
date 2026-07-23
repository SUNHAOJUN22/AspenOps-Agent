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

Python 3.11, 3.12 and 3.13 plus quality/build/smoke passed in that archived run. Public Windows run `29814739334` recorded 104 passed in 2.06 seconds.

These are archived validated baselines, not current-head claims.

## Portable CI

`ci.yml` enforces pinned `ubuntu-24.04`, immutable Actions, `uv 0.11.16`, read-only permissions, frozen dependencies, Ruff/format/mypy, build, Mock, README command smoke, 14 MCP tools and full Python tests.

It audits Linux and Windows for Python 3.11, 3.12 and 3.13—six combinations. Each target preserves JSON and stderr evidence, validates JSON, and the job fails once after all targets finish.

The Wheel gate uses hash-pinned exported requirements, `uv pip sync --require-hashes`, offline/no-deps Wheel installation, `uv pip check` and CLI smoke.

## Windows control-plane gate

`windows-control-plane.yml` uses pinned `windows-2025`, Python 3.12 and `uv 0.11.16`. It runs PowerShell AST parsing and real helper behavior through `-LibraryMode`, including dotenv safety and self-update → winget upgrade → winget install fallback checks. It also covers Job Objects, process ownership, IPC/recovery, Fake Aspen Plus/HYSYS, archives, paths, documentation, CLI and Doctor.

## Trusted and isolated performance evidence

The default baseline is the validated main-history runtime:

```text
ebef32ee1f2be74df5d5c5489e7ca86d35ac7bb2
```

The workflow now:

```text
checkout current trusted main workflow revision
→ fetch main history and tags
→ resolve candidate_ref / baseline_ref with --end-of-options
→ require both SHAs in main
→ require baseline ancestry
→ detached checkout validated candidate
→ create detached baseline worktree
```

Candidate input is never sent directly to `actions/checkout`.

Two independent frozen environments are used:

```text
candidate/uv.lock → candidate .venv → candidate script
baseline/uv.lock  → baseline .venv  → baseline script
```

This fixes candidate dependency/source/harness contamination of the baseline.

### Runner-context defect found and fixed

A temporary implementation placed `${{ runner.temp }}` in `jobs.<job_id>.env`. GitHub's context-availability rules do not permit the `runner` context there. The final workflow instead:

- uses `$RUNNER_TEMP/aspenops-performance-evidence` inside Shell steps;
- uses `${{ runner.temp }}/aspenops-performance-evidence` only in the upload action's `with.path`, where the runner context is available;
- keeps job-level `env` limited to supported `inputs` values.

### Stale benchmark evidence defect found and fixed

The repository tracks historical `var/benchmarks` files for committed policy comparisons. Uploading from the candidate workspace could therefore publish old committed results after an early failure.

The final workflow writes every current-run SHA, log, JSON result and report only to the runner temporary directory and uploads only that directory. Candidate-workspace `var/benchmarks` files cannot enter the artifact.

## Licensed evidence chain

```text
trusted main SHA → frozen Mock regression → realpath validation
→ preflight and explicit approval → scoped real COM
→ signed-bundle verification → require non-empty source evidence
→ clean var/ci/licensed-evidence → copy and revalidate
→ upload workspace var/ci only → human review
```

This prevents missing evidence, undefined external upload paths and stale self-hosted staging. The software remains `PENDING_REAL_ASPEN_CERTIFICATION` and cannot emit `REAL_ASPEN_CERTIFIED`.

## Runtime path policy

Real backends require non-empty absolute allowed roots. State, models, registries, outputs and evidence must resolve inside them. Backend mismatch, traversal, symlink and Windows junction escapes fail before Aspen opens or state is created.

## Workflow governance

`tests/test_workflow_governance.py` rejects:

- extra workflows, drifting runners, unpinned Actions or uv;
- block, commented, inline or `write-all` permissions;
- retained checkout credentials, `pull_request_target` or silent `continue-on-error`;
- unfrozen dependencies or weak Bash;
- direct input interpolation in any `run` syntax;
- incomplete dependency-audit evidence;
- candidate input passed to checkout;
- unsupported runner context in job-level env;
- untrusted/reverse performance refs;
- shared performance environments or candidate-workspace artifacts;
- untrusted licensed commits, missing realpath/secret isolation or stale evidence staging;
- deletion of Windows helper, path or documentation contracts.

## Documentation contracts

`tests/test_documentation_contracts.py` derives the package version from `pyproject.toml` and checks README/package/CHANGELOG/title consistency, required docs, safe local links, frozen operating instructions, portable `.env.example`, archived evidence boundaries, and absence of ChatGPT-internal citation or sandbox-link markup.

## Executed targeted checks

The current performance workflow was parsed as YAML and all six Bash `run` blocks passed `bash -n`. The rebuilt governance test compiled under Python, had no lines above the repository's 100-character limit, and its performance-specific pytest passed.

These checks supplement, but do not replace, a fresh full Actions artifact.

## Remaining external limits

1. A readable current Actions artifact is required before replacing archived counts or coverage.
2. Public automation cannot instantiate proprietary Aspen Automation Servers.
3. Real certification requires licensed Windows, an approved model, verified semantics, signing material and human engineering review.
4. No finite audit proves the absence of every future defect; it resolves observed defects and installs regression guards.
