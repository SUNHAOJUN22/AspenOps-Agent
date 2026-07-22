# AspenOps 2.0 Agent Contract

AspenOps is the only permitted execution path for Aspen automation in this repository.

## Repository topology

- `main` is the only persistent branch in this repository.
- Do not create or publish another remote branch and do not open a parallel implementation PR.
- Use a local temporary worktree only when isolation is required; validate fully, then commit atomic changes directly to `main` without force-pushing.
- Never rewrite unknown history.
- External contributors work from forks; their branches are not retained in this repository.

## Mandatory simulator sequence

1. Call `system_info` and record the discovered backend and ProgID.
2. Inspect the case-specific registry with `list_semantic_variables`.
3. Run `dry_run_request` before every new batch definition.
4. Use `submit_batch` for more than 16 points or any long solve.
5. Accept a point only when `ok=true`; transport, engine, convergence, constraints and balances remain separate gates.
6. Preserve and verify the evidence bundle before reporting final results.

## Prohibited behavior

- Do not generate a parallel raw `win32com` script.
- Do not invent Aspen tree paths or HYSYS object chains.
- Do not bypass `ASPENOPS_ALLOWED_ROOTS`.
- Do not overwrite the master model.
- Do not increase concurrency beyond license evidence.
- Do not claim latest-version qualification from registry discovery alone.
- Do not claim physical Aspen validation from the Mock backend.
- Do not create a second runtime package, duplicate scheduler, duplicate pool manager or competing MCP surface.

## Engineering expectations

Every production request should include units, bounds, required outputs, at least one domain constraint, and conservation checks whenever the model exposes the required terms.

Before changing `main`, run the frozen quality gate:

```bash
uv lock --check
uv sync --frozen --extra dev --extra agent --extra signing
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest -W error::ResourceWarning \
  --cov=aspenops_nexus \
  --cov-branch \
  --cov-fail-under=94.5
uv build
uv run python scripts/check_mcp.py
uv run aspenops --version
uv run aspenops demo
```

On Windows, include `--extra windows`. The authoritative CI additionally audits the frozen lock for Linux and Windows across Python 3.11, 3.12 and 3.13.

Real Aspen certification remains `PENDING_REAL_ASPEN_CERTIFICATION` until the protected licensed self-hosted Windows workflow produces complete signed evidence and a human engineer accepts the scoped result.
