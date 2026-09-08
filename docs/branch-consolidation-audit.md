# Branch consolidation audit

## Repository state

The repository default branch is `main`. GitHub Actions Issue #28 performed a fresh remote-head enumeration, deleted every non-main branch and verified that only `refs/heads/main` remained.

PR #18 supplied the reviewed AspenOps 2.0 consolidation. Historical parallel PRs, including #17, #15 and #8, are closed. Temporary PR #20 was closed without merge. No required production capability remains on another branch.

## Validation basis

`docs/single-main-audit.json` records:

- Linux CI run `29814739487`: PASS;
- Windows control-plane run `29814739334`: PASS;
- 563 tests passed on Python 3.12;
- 94.9719800747198% combined branch-aware coverage;
- build, wheel, MCP and stable benchmark regression gates: PASS;
- final branch state: `MAIN_ONLY`;
- real simulator state: `PENDING_REAL_ASPEN_CERTIFICATION`.

A Git diff from audited runtime SHA `ebef32ee1f2be74df5d5c5489e7ca86d35ac7bb2` to the subsequent consolidation work found no changes under `src`, `tests`, `pyproject.toml`, `uv.lock`, `scripts` or `examples`; later changes were limited to workflows and audit evidence.

## Branch classifications

- `MERGED_SOURCE`: the reviewed AspenOps 2.0 branch merged through PR #18.
- `ALREADY_IN_MAIN`: historical heads whose relevant implementation is already represented by main.
- `SUPERSEDED`: bootstrap, materializer, staging, 1.x and runtime-safety branches replaced by stronger tested AspenOps 2.0 contracts.
- `UNIQUE_EXPERIMENTAL_ARCHIVED`: the 1.4 approval/drift/surrogate/twin work. It is not a production feature.

## Recovery-reference audit

Two earlier audit tags are verified and retained:

- `archive/retired-branch/audit-single-main-final-20260721/20260721/670e9523e915`;
- `archive/retired-branch/automation-final-main-evidence-trigger/20260721/f4968e3209d4`.

The remaining planned annotated tags could not be created because the acting GitHub App lacks `Workflows: write`. REST ref creation returned HTTP 403 in Actions run `29817700557`; Git push returned an explicit workflow-permission rejection in run `29818039586`.

This is a recovery-reference blocker, not a runtime correctness failure. The full exact tag plan is preserved in `var/consolidation/branch-archive-manifest.json`.
