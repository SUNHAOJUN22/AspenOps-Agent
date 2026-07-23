# Certification Contract

## Principle

AspenOps keeps software-control evidence, licensed simulator evidence and engineering-model approval separate. A lower level must never be represented as a higher one.

## Certification levels

1. **Control plane:** public Mock CI validates policy, paths, units, isolation, scheduling, convergence classification, constraints, balances, evidence, CLI, MCP and governance.
2. **Licensed runtime:** native Windows validates the exact installed Aspen runtime, approved model and signed evidence.
3. **Engineering model:** the responsible engineer approves thermodynamics, reactions, equipment assumptions, operating range, closure, uncertainty and intended use.

The runtime can produce only `PENDING_REAL_ASPEN_CERTIFICATION`; it cannot self-grant engineering approval.

## Local commands

```powershell
uv run aspenops certification-preflight D:/AspenModels/licensed-plan.json `
  --output D:/AspenResults/preflight.json
uv run aspenops certify-licensed D:/AspenModels/licensed-plan.json `
  --output-dir D:/AspenResults/licensed-certification
uv run aspenops verify-licensed-bundle `
  D:/AspenResults/licensed-certification/licensed-certification-bundle.zip `
  --public-key D:/AspenKeys/aspenops-certification-public.pem
```

Direct CLI use remains subject to Settings, backend and allowed-root policy.

## Protected workflow

```text
.github/workflows/licensed-aspen-certification.yml
```

```text
ubuntu-24.04 dispatch guard
→ self-hosted, windows, x64, aspen-licensed certification job
```

A non-main dispatch exits with status 2. The licensed job has `needs: dispatch-guard`, so invalid dispatches never occupy the Aspen host.

## Dispatch-SHA binding

`expected_head_sha` must equal the `GITHUB_SHA` associated with the current `refs/heads/main` workflow dispatch. The workflow verifies:

```text
actions/checkout initial HEAD == GITHUB_SHA
expected_head_sha == GITHUB_SHA
GITHUB_SHA is a commit and an ancestor of origin/main
detached checkout remains exactly GITHUB_SHA
```

This prevents current safety workflow definitions from certifying an arbitrary older main ancestor whose runtime, tests or `validate_licensed_paths.py` may predate current controls.

## Pre-checkout artifact isolation

Before `actions/checkout`, the self-hosted job removes and recreates a run-attempt-specific directory:

```text
$RUNNER_TEMP/aspenops-licensed-artifact-<GITHUB_RUN_ID>-<GITHUB_RUN_ATTEMPT>
```

`run-metadata.txt` records the run ID, attempt, ref, `GITHUB_SHA` and `expected_head_sha` before checkout. The Mock regression JUnit file is written directly to this directory. Successful licensed evidence is copied into its `licensed-evidence` child directory, and the final `job_status` is appended through an `if: always()` step.

The final artifact upload reads only:

```text
${{ runner.temp }}/aspenops-licensed-artifact-${{ github.run_id }}-${{ github.run_attempt }}
```

It uses `if-no-files-found: error`. A checkout, setup or validation failure therefore cannot upload stale `var/ci` data from the persistent self-hosted workspace.

## Run-attempt external evidence isolation

All licensed jobs share the fixed concurrency group `licensed-aspen-certification`, which serializes Aspen Plus and HYSYS certifications.

External evidence is unique to the workflow attempt:

```text
ASPENOPS_STATE_DIR/licensed-certification/<GITHUB_RUN_ID>-<GITHUB_RUN_ATTEMPT>
```

The directory is deleted and recreated, exported as `LICENSED_EVIDENCE_DIR`, and used for preflight, real execution, bundle verification, status inspection and runner-temp staging. Artifact names contain both `github.run_id` and `github.run_attempt`.

These controls prevent stale report/bundle reuse, backend collisions, retry ambiguity and persistent self-hosted workspace contamination.

## Full protected sequence

```text
Ubuntu guard requires GITHUB_REF == refs/heads/main
→ create and clean the run-attempt runner-temp artifact directory
→ checkout this dispatch's GITHUB_SHA
→ verify expected_head_sha == GITHUB_SHA
→ verify initial HEAD and main ancestry
→ detached checkout the same GITHUB_SHA
→ validate the plan path
→ frozen dependencies and Mock regression with JUnit in runner temp
→ create the run-attempt external evidence directory
→ realpath validation → preflight → explicit approval → real COM
→ signed-bundle verification → require non-empty evidence
→ copy evidence into runner-temp/licensed-evidence
→ record job_status → upload only runner temp → human engineering review
```

The realpath gate rejects traversal, symlink and junction escapes. Signing secrets are absent from setup and Mock regression.

## Release rule

Licensed compatibility may be stated only for the exact Aspen version, backend, model class and evidence scope executed and reviewed. Broad claims covering all Aspen versions or models are prohibited.
