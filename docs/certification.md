# Certification Contract

## Principle

AspenOps keeps software-control evidence, licensed simulator evidence and engineering model approval separate. A lower level must never be presented as a higher one.

## Level 1: control-plane certification

Runs on the deterministic Mock backend and validates:

- request and path policy;
- semantic registry and unit logic;
- worker isolation, IPC and timeout behavior;
- scheduler leases, retries, cancellation and recovery;
- cache keys and duplicate elimination;
- constraints and conservation residuals;
- provenance and bundle verification;
- independent repeated-state determinism;
- MCP and CLI contracts.

This level can run on public Linux or Windows CI. It proves AspenOps control-plane behavior, not proprietary Aspen physics.

## Level 2: licensed-simulator runtime certification

Runs on a native Windows host with:

- Aspen Plus and/or Aspen HYSYS installed;
- a valid and available license;
- an approved non-confidential qualification model;
- a case-specific semantic registry or HYSYS Spreadsheet Contract;
- an exact approved AspenOps commit;
- configured constraints, balances and repeatability tolerances;
- signing material stored outside the repository.

It validates:

- Automation Server discovery and instantiation;
- actual ProgID and exposed application version/build;
- private model staging and opening;
- semantic writes and readback;
- solver execution and explicit convergence evidence;
- output reads, constraints and balances;
- independent repeats from fresh model copies and COM instances;
- signed evidence-bundle integrity.

The runtime can produce `PENDING_REAL_ASPEN_CERTIFICATION` evidence. It is not allowed to self-grant final engineering certification.

## Level 3: engineering model validation

Owned by the process engineer and the responsible technical authority. It covers:

- property methods and component definitions;
- reactions, kinetics and thermodynamic assumptions;
- equipment models and specifications;
- operating ranges and extrapolation boundaries;
- mass, energy and elemental closure;
- comparison with plant, pilot or experimental evidence;
- uncertainty, repeatability and intended-use acceptance.

Software tests cannot replace this review.

## Qualification case requirements

- non-confidential and repository-safe, or supplied outside Git;
- deterministic and convergent in the Aspen GUI;
- representative but bounded input ranges;
- semantic paths verified with Variable Explorer or Spreadsheet bindings;
- at least one meaningful process constraint;
- at least one mass, energy or elemental balance where variables are exposed;
- independent repeats from private model copies;
- recorded model, registry, request and result hashes;
- recorded Aspen ProgID, application version, host and license identity;
- explicit output-specific absolute and relative tolerances.

## Repeated-state test

For output `k`, repeat `r` passes when:

\[
|y_k^{(r)}-y_k^{(0)}|\le\tau_{abs}
\quad\lor\quad
\frac{|y_k^{(r)}-y_k^{(0)}|}{\max(|y_k^{(r)}|,|y_k^{(0)}|,1)}\le\tau_{rel}.
\]

Every point in every repeat must also have `ok=true`, meaning transport, engine return, convergence, feasibility and configured balances all pass.

## Portable repeatability command

This command is useful for control-plane and model-repeatability checks, but never grants real Aspen certification by itself:

```powershell
uv run aspenops certify D:/AspenModels/qualification-request.json `
  --output D:/AspenResults/certification.json `
  --repeats 3
```

## Licensed certification commands

Preflight without opening COM:

```powershell
uv run aspenops certification-preflight D:/AspenModels/licensed-plan.json `
  --output D:/AspenResults/preflight.json
```

Execute an approved plan on a licensed host:

```powershell
uv run aspenops certify-licensed D:/AspenModels/licensed-plan.json `
  --output-dir D:/AspenResults/licensed-certification
```

Verify the signed evidence bundle:

```powershell
uv run aspenops verify-licensed-bundle `
  D:/AspenResults/licensed-certification/licensed-certification-bundle.zip `
  --public-key D:/AspenKeys/aspenops-certification-public.pem
```

## Authoritative GitHub Actions workflow

```text
.github/workflows/licensed-aspen-certification.yml
```

It runs on a self-hosted runner labeled:

```text
self-hosted, windows, x64, aspen-licensed
```

Manual dispatch requires the plan path, exact approved 40-character commit SHA, backend and explicit authorization for real COM execution. The workflow checks out the exact commit, runs preflight, executes only after approval, verifies the signed bundle and uploads the evidence artifact.

## Release rule

A portable release may state that the control plane passed its public quality gates. A release may state licensed Aspen compatibility only for the exact Aspen version, backend, model class and evidence scope actually executed and reviewed. No broad “all Aspen versions/models supported” claim is permitted.
