# AspenOps Agent Contract

AspenOps is the only permitted execution path for Aspen automation in this repository.

## Mandatory sequence

1. Call `system_info` and record the discovered backend/ProgID.
2. Inspect the case-specific registry with `list_semantic_variables`.
3. Run `dry_run_request` before every new batch definition.
4. Use `submit_batch` for more than 16 points or any long solve.
5. Accept a point only when `ok=true`; do not collapse transport, engine, convergence, constraints or balances.
6. Preserve and verify the evidence bundle before reporting final results.

## Prohibited behavior

- Do not generate a parallel raw `win32com` script.
- Do not invent Aspen tree paths or HYSYS object chains.
- Do not bypass `ASPENOPS_ALLOWED_ROOTS`.
- Do not overwrite the master model.
- Do not increase concurrency beyond license evidence.
- Do not claim latest-version qualification from registry discovery alone.
- Do not claim physical Aspen validation from the Mock backend.

## Engineering expectations

Every production request should include units, bounds, required outputs, at least one domain constraint, and conservation checks whenever the model exposes the required terms.
