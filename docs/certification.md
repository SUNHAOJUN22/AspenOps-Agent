# Certification Contract

## Principle

AspenOps keeps software-control evidence, licensed simulator evidence and engineering-model approval separate. A lower level must never be represented as a higher one.

## Level 1: control-plane certification

The deterministic Mock backend validates request/backend/path policy, semantic units, process isolation, IPC, timeout/recovery, scheduling, constraints, balances, provenance, bundles, MCP, CLI, documentation and workflow governance.

Public Linux or Windows CI proves control-plane behavior, not proprietary Aspen physics.

## Level 2: licensed-simulator runtime certification

This level requires native Windows, licensed Aspen Plus and/or HYSYS, an approved non-confidential model, verified semantics, an exact approved main-history commit, absolute allowed roots, constraints/balances/tolerances and signing material outside the repository.

The runtime can produce only `PENDING_REAL_ASPEN_CERTIFICATION`; it cannot self-grant engineering approval.

## Level 3: engineering-model validation

The process engineer and responsible technical authority own property methods, reactions, kinetics, equipment assumptions, operating ranges, closure, comparison evidence, uncertainty and intended-use acceptance. Software tests cannot replace this review.

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

Direct CLI use is subject to the same Settings, backend and allowed-root policy. A rootless or out-of-root real backend fails before preflight or state creation.

## Authoritative protected workflow

```text
.github/workflows/licensed-aspen-certification.yml
```

```text
ubuntu-24.04 dispatch guard
→ self-hosted, windows, x64, aspen-licensed certification job
```

A lightweight Ubuntu guard always runs first. When `GITHUB_REF` is not `refs/heads/main`, it exits with status 2 and the workflow fails explicitly. The self-hosted job has `needs: dispatch-guard`, so an invalid dispatch never occupies the licensed machine.

The approved SHA is never passed directly to `actions/checkout`:

```text
Ubuntu guard requires GITHUB_REF == refs/heads/main
→ checkout the trusted main workflow revision
→ validate SHA format, commit existence and main ancestry
→ detached checkout of the validated SHA and verify HEAD
→ validate the repository-relative plan
→ lock check and frozen Mock regression
→ realpath validation → preflight → explicit approval → real COM
→ signed-bundle verification → human engineering review
```

## Run-attempt evidence isolation

All real certification jobs share the fixed concurrency group:

```text
licensed-aspen-certification
```

This serializes Aspen Plus and HYSYS certification jobs so they cannot write concurrently into the same state space.

The external evidence directory is unique to the workflow run attempt:

```text
ASPENOPS_STATE_DIR/licensed-certification/<GITHUB_RUN_ID>-<GITHUB_RUN_ATTEMPT>
```

The workflow deletes and recreates this directory before use, exports it as `LICENSED_EVIDENCE_DIR`, and uses it for:

- `preflight.json`;
- `licensed-certification-report.json`;
- `licensed-certification-bundle.zip`;
- bundle verification and final status inspection;
- copying into clean workspace staging.

This prevents a rerun from accepting a previous attempt's report or bundle and prevents Aspen Plus/HYSYS runs from sharing one fixed output directory. The Mock diagnostics directory `var/ci` is also deleted and recreated before the licensed software regression.

Successful evidence is revalidated and copied into `var/ci/licensed-evidence`. The uploaded artifact name includes both `github.run_id` and `github.run_attempt`; upload reads only workspace-local `var/ci`.

The realpath gate rejects traversal, symlink and junction escapes. Signing secrets are absent from dependency setup and Mock regression. Canonical paths pass through `GITHUB_ENV`.

## Release rule

A portable release may state only the public control-plane gates actually observed. Licensed compatibility may be stated only for the exact Aspen version, backend, model class and evidence scope executed and reviewed. Broad claims covering all Aspen versions or models are prohibited.
