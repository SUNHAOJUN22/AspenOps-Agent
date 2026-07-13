# Certification Contract

## Levels

### Control-plane certification

Runs on the deterministic Mock backend. It validates worker isolation, IPC, scheduler, cache, unit logic, constraints, balances, provenance and repeated-state determinism.

### Licensed-simulator runtime certification

Runs on a native Windows host with Aspen, valid licenses and an approved qualification case. It validates Automation Server discovery, model opening, semantic paths, writes, solver execution, output reads and repeated numerical behavior.

### Engineering model validation

Owned by the process engineer. It validates property methods, components, reactions, equipment assumptions, operating ranges, balances, specifications and comparison with plant or experimental evidence.

These levels must not be conflated.

## Qualification case requirements

- non-confidential and repository-safe or supplied outside Git;
- deterministic and convergent in the Aspen GUI;
- case-specific registry verified with Variable Explorer or Spreadsheet bindings;
- representative input ranges;
- at least one process constraint;
- at least one mass or energy balance where possible;
- independent repeats from private model copies;
- recorded Aspen ProgID, exposed version, host and model/registry hashes.

## Repeated-state test

For output `k`, repeat `r` passes when:

\[
|y_k^{(r)}-y_k^{(0)}|\le\tau_{abs}
\quad\lor\quad
\frac{|y_k^{(r)}-y_k^{(0)}|}{\max(|y_k^{(r)}|,|y_k^{(0)}|,1)}\le\tau_{rel}.
\]

The report also requires every point in every repeat to have `ok=true`.

## Command

```powershell
uv run aspenops certify D:/AspenModels/qualification-request.json `
  --output D:/AspenResults/certification.json `
  --repeats 3
```
