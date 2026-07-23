# Certification Contract

## Principle

AspenOps keeps software-control evidence, licensed simulator evidence and engineering model approval separate. A lower level must never be represented as a higher one.

## Level 1: control-plane certification

The deterministic Mock backend validates request/backend/path policy, semantic units, process isolation, IPC, timeout/recovery, scheduling, constraints, balances, provenance, bundles, MCP, CLI, documentation and workflow governance.

Public Linux or Windows CI proves control-plane behavior, not proprietary Aspen physics.

## Level 2: licensed-simulator runtime certification

Runs on native Windows with licensed Aspen Plus and/or HYSYS, an approved non-confidential model, verified semantic registry, exact approved main-history commit, absolute allowed roots, configured constraints/balances/tolerances, and signing material outside the repository.

It validates Automation Server discovery, actual ProgID/version, private model staging, semantic writes/readback, solver execution, convergence evidence, outputs, constraints, balances, independent repeats and signed evidence integrity.

The runtime can produce only `PENDING_REAL_ASPEN_CERTIFICATION`; it cannot self-grant engineering approval.

## Level 3: engineering model validation

Owned by the process engineer and responsible technical authority. It covers property methods, components, reactions, kinetics, equipment assumptions, operating ranges, closure, comparison with plant/pilot/experimental evidence, uncertainty and intended-use acceptance.

Software tests cannot replace this review.

## Qualification-case requirements

- non-confidential and repository-safe, or supplied outside Git;
- deterministic and convergent in the Aspen GUI;
- bounded representative inputs;
- semantic paths verified through Variable Explorer or Spreadsheet bindings;
- meaningful process constraints and available mass/energy/elemental balances;
- independent repeats from private model copies;
- model, registry, request and result hashes;
- actual Aspen ProgID/version, host and license identity;
- output-specific absolute and relative tolerances.

## Repeated-state test

For output `k`, repeat `r` passes when:

\[
|y_k^{(r)}-y_k^{(0)}|\le\tau_{abs}
\quad\lor\quad
\frac{|y_k^{(r)}-y_k^{(0)}|}{\max(|y_k^{(r)}|,|y_k^{(0)}|,1)}\le\tau_{rel}.
\]

Every point must also have `ok=true`, requiring communication, engine return, convergence, feasibility and configured balances.

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

Runner labels:

```text
self-hosted, windows, x64, aspen-licensed
```

The workflow accepts manual dispatch only when the event ref is `refs/heads/main`. Inputs provide a repository-relative plan path, exact lowercase 40-character approved SHA, backend and explicit execution authorization.

The approved SHA is never passed directly to `actions/checkout`. The actual sequence is:

```text
run the workflow definition from refs/heads/main
→ checkout the trusted main workflow revision
→ validate the input SHA format
→ fetch trusted main
→ verify the SHA identifies a commit and is a main ancestor
→ detached checkout of the validated SHA
→ verify HEAD equals the approved SHA
→ validate the repository-relative plan in that checkout
→ lock check and frozen dependencies
→ isolated Mock regression without real secrets
→ Python realpath validation for plan, roots and state
→ licensed preflight
→ explicit human approval
→ scoped real COM execution
→ signed-bundle verification
→ require all source evidence files to exist and be non-empty
→ clean and rebuild var/ci/licensed-evidence
→ copy and revalidate preflight/report/bundle
→ upload workspace-local var/ci only
→ human engineering review
```

The realpath gate rejects traversal, symlink and junction escapes. Signing secrets are absent from dependency setup and Mock regression. Canonical paths pass through `GITHUB_ENV`, and artifact names use `github.run_id`.

Early failures never expand an undefined external state path. Successful external evidence is copied into a clean workspace staging directory before upload; stale self-hosted-runner staging is removed first.

## Release rule

A portable release may state only the public control-plane gates actually observed. Licensed compatibility may be stated only for the exact Aspen version, backend, model class and evidence scope executed and reviewed. Broad claims covering all Aspen versions or models are prohibited.
