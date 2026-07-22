# Certification Contract

## Principle

AspenOps keeps software-control evidence, licensed simulator evidence and engineering model approval separate. A lower level must never be presented as a higher one.

## Level 1: control-plane certification

Runs on the deterministic Mock backend and validates:

- request, backend and path policy;
- semantic registry and unit logic;
- worker isolation, IPC and timeout behavior;
- scheduler leases, retries, cancellation and recovery;
- cache keys and duplicate elimination;
- constraints and conservation residuals;
- provenance and bundle verification;
- independent repeated-state determinism;
- MCP, CLI and workflow-governance contracts.

This level can run on public Linux or Windows CI. It proves AspenOps control-plane behavior, not proprietary Aspen physics.

## Level 2: licensed-simulator runtime certification

Runs on native Windows with:

- Aspen Plus and/or Aspen HYSYS installed;
- a valid available license;
- an approved non-confidential qualification model;
- a case-specific semantic registry or HYSYS Spreadsheet Contract;
- an exact approved AspenOps commit belonging to trusted `main` history;
- non-empty absolute allowed roots and an absolute state directory inside them;
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

The runtime can produce `PENDING_REAL_ASPEN_CERTIFICATION` evidence. It cannot self-grant final engineering certification.

## Level 3: engineering model validation

Owned by the process engineer and responsible technical authority. It covers:

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

This is useful for control-plane and model-repeatability checks, but never grants real Aspen certification by itself:

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

Execute an approved plan:

```powershell
uv run aspenops certify-licensed D:/AspenModels/licensed-plan.json `
  --output-dir D:/AspenResults/licensed-certification
```

Verify the signed bundle:

```powershell
uv run aspenops verify-licensed-bundle `
  D:/AspenResults/licensed-certification/licensed-certification-bundle.zip `
  --public-key D:/AspenKeys/aspenops-certification-public.pem
```

Direct CLI use is subject to the same Settings, backend and allowed-root policy as the GitHub workflow. A real backend without allowed roots is rejected before preflight or state creation.

## Authoritative GitHub Actions workflow

```text
.github/workflows/licensed-aspen-certification.yml
```

Runner labels:

```text
self-hosted, windows, x64, aspen-licensed
```

Manual dispatch requires a repository-relative plan path, exact lowercase 40-character commit SHA, backend and explicit authorization.

```text
exact SHA checkout
→ verify SHA belongs to trusted main history
→ check lockfile and freeze dependencies
→ run isolated Mock regression without real secrets
→ resolve plan, roots and state target through the Python realpath gate
→ run licensed preflight
→ require explicit human execution approval
→ execute scoped real COM plan
→ verify signed bundle
→ retain pending human engineering review
```

The realpath gate rejects traversal, symlink and junction escapes. Signing secrets are not exposed to setup or Mock regression. Canonical paths are passed through `GITHUB_ENV`; artifacts use `github.run_id` rather than arbitrary input.

## Release rule

A portable release may state that the control plane passed its public quality gates. Licensed compatibility may be stated only for the exact Aspen version, backend, model class and evidence scope actually executed and reviewed. No broad “all Aspen versions/models supported” claim is permitted.
