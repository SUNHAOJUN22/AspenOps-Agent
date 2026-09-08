# AspenOps single-main consolidation report

## Result

`SINGLE_MAIN_CONSOLIDATION_BLOCKED`

The runtime and repository topology have been consolidated successfully, but the full historical annotated-tag recovery gate is blocked by the acting GitHub App token's missing `Workflows: write` permission.

## Completed gates

- Default branch: `main`.
- Remote heads: only `main`.
- Validated runtime SHA: `ebef32ee1f2be74df5d5c5489e7ca86d35ac7bb2`.
- Last code-bearing main SHA before evidence-only commits: `9522eaf7faaa68074eaa26bebd07f8070edd97db`.
- Package version: 2.0.0.
- Python 3.11, 3.12 and 3.13: PASS.
- Tests on Python 3.12: 563 passed.
- Combined branch-aware coverage: 94.9720% with a 94.5% enforced floor.
- Statement coverage: 96.2368%.
- Branch coverage: 90.8488%.
- Ruff, Ruff format and strict mypy: PASS.
- Build, clean-wheel installation, Demo and licensed CLI help smoke: PASS.
- MCP surface: 14 bounded tools.
- Portable benchmark smoke and committed stable-regression policy: PASS.
- Public Windows control-plane contracts: PASS.
- Parallel historical PRs: closed.
- Temporary trigger branches: deleted.
- Real simulator status: `PENDING_REAL_ASPEN_CERTIFICATION`.

The authoritative validation runs are CI `29814739487` and Windows control-plane `29814739334`. The final branch cleanup was independently confirmed by GitHub Actions Issue #28: remote heads contain only `main`.

## Archive-tag blocker

Creating the annotated tag object succeeded, but creating its Git ref through REST failed with HTTP 403 in run `29817700557`:

```text
Resource not accessible by integration
```

Creating the same annotated tag through Git push failed in run `29818039586`:

```text
refusing to allow a GitHub App to create or update workflow .github/workflows/ci.yml without workflows permission
```

Consequently, the complete historical annotated-tag gate cannot be marked PASS under the current credentials. The exact planned tag names, branch classifications and commit SHAs are retained in `var/consolidation/branch-archive-manifest.json`.

## Capability decision

All production-validated AspenOps 2.0 runtime, Worker, process-ownership, convergence, transaction, caching, PoolManager, Scheduler, optimization, evidence and licensed-certification-control-plane capabilities are on `main`.

The 1.4 `approval`, `drift`, `surrogate` and `twin` modules are classified `UNIQUE_EXPERIMENTAL_ARCHIVED`. They are not shipped and must not be described as production capability because their source branch failed its production Ruff gate and exposed no accepted bounded CLI, MCP or Scheduler integration.

## Completion action

A repository maintainer must create the planned annotated tags using a token or GitHub App installation with both `Contents: write` and `Workflows: write`, then verify that each peeled tag resolves to its recorded commit SHA. No runtime, test, coverage, performance or certification gate should be changed while completing that action.
