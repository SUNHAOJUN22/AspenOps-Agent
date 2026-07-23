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

## Main-ref-only manual workflows

GitHub permits `workflow_dispatch` to target a branch or tag, and the workflow definition is loaded from the selected event ref. The authoritative performance and licensed jobs therefore now include:

```text
if: github.ref == refs/heads/main
```

This prevents an older tag or non-main branch from supplying the workflow definition used to produce authoritative evidence.

## Trusted and isolated performance evidence

The default baseline is the validated main-history runtime:

```text
ebef32ee1f2be74df5d5c5489e7ca86d35ac7bb2
```

The workflow now:

```text
load workflow definition from refs/heads/main
→ checkout current trusted main workflow revision
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

This fixes candidate input/dependency/source/harness contamination of the baseline.

### Runner-context defect found and fixed

A temporary implementation placed `${{ runner.temp }}` in `jobs.<job_id>.env`, where the `runner` context is unavailable. The final workflow:

- uses `$RUNNER_TEMP/aspenops-performance-evidence` inside Shell steps;
- uses `${{ runner.temp }}/aspenops-performance-evidence` only in upload `with.path`;
- keeps job-level `env` limited to supported `inputs` values.

### Stale benchmark evidence defect found and fixed

The repository tracks historical `var/benchmarks` files. The final workflow writes every current-run SHA, log, JSON result and report only to the runner temporary directory and uploads only that directory. Candidate-workspace historical files cannot enter the artifact.

## Licensed evidence and checkout trust chain

The approved SHA was previously passed directly to `actions/checkout`, with validation occurring afterward. The final protected workflow runs only from `refs/heads/main` and uses:

```text
checkout current trusted main workflow revision
→ validate approved SHA format
→ fetch trusted main
→ verify SHA identifies a commit and is a main ancestor
→ detached checkout validated SHA
→ verify HEAD equals approved SHA
→ validate the plan path in that checkout
→ frozen Mock regression → realpath validation
→ preflight and explicit approval → scoped real COM
→ signed-bundle verification → require non-empty source evidence
→ clean var/ci/licensed-evidence → copy and revalidate
→ upload workspace var/ci only → human review
```

This prevents manual SHA input from controlling checkout before trust validation, and prevents missing evidence, undefined external upload paths and stale self-hosted staging. The software remains `PENDING_REAL_ASPEN_CERTIFICATION` and cannot emit `REAL_ASPEN_CERTIFIED`.

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
- performance or licensed manual jobs not restricted to `refs/heads/main`;
- candidate or approved SHA input passed directly to checkout;
- unsupported runner context in job-level env;
- untrusted/reverse performance refs;
- shared performance environments or candidate-workspace artifacts;
- untrusted licensed commits, missing realpath/secret isolation or stale evidence staging;
- deletion of Windows helper, path or documentation contracts.

## Documentation contracts

`tests/test_documentation_contracts.py` derives the package version from `pyproject.toml` and checks README/package/CHANGELOG/title consistency, required docs, safe local links, frozen operating instructions, portable `.env.example`, archived evidence boundaries, main-ref manual-workflow trust documentation, and absence of ChatGPT-internal citation or sandbox-link markup.

## Executed targeted checks

The final validation reconstructs the current workflows and governance files in an isolated directory, parses YAML, compiles Python tests, checks the repository line-length convention, validates Linux Bash blocks, and runs the workflow-governance and licensed-workflow contract tests. These checks supplement, but do not replace, a fresh full Actions artifact.

## Remaining external limits

1. A readable current Actions artifact is required before replacing archived counts or coverage.
2. Public automation cannot instantiate proprietary Aspen Automation Servers.
3. Real certification requires licensed Windows, an approved model, verified semantics, signing material and human engineering review.
4. No finite audit proves the absence of every future defect; it resolves observed defects and installs regression guards.
