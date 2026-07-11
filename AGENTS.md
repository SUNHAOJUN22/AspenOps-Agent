# Agent Engineering Contract

AspenOps controls a stateful proprietary process simulator. Every coding agent must preserve the following invariants.

## Non-negotiable architecture

1. Keep `client -> SessionManager -> spawned Worker RPC -> SimulatorBackend` boundaries.
2. A real Aspen COM document belongs to one spawned process and one STA apartment.
3. Never pass COM objects through queues, pipes, threads or serialized public models.
4. Never expose arbitrary Python, shell, VBA, unrestricted `getattr`, raw COM dispatch or generic code execution as an MCP tool.
5. Keep semantic keys allowlisted. Raw paths, if ever added, must be a separately gated expert capability.
6. Discover locally registered `Apwn.Document.*` ProgIDs. Do not declare one marketing release number universally correct.
7. Distinguish transport success, COM-call success, Aspen convergence and physical feasibility.
8. Failed simulations must be dominated by converged feasible points in optimization.
9. Public tests must run without Aspen through MockBackend; real Aspen tests remain opt-in and licensed-Windows only.
10. Never commit proprietary models, vendor documents, license files, customer data or private kinetics.

## Definition of done

```bash
uv sync --extra dev --extra agent
uv run ruff check .
uv run mypy src/aspenops
uv run pytest
uv build
uv run aspenops demo
```

A change is complete only when:

- request and result models remain JSON serializable;
- access, units, identifiers and bounds are validated before a write;
- batch-write failure tests prove rollback behavior;
- worker deadlines remain enforced;
- no timeout path uses a machine-wide Aspen kill command;
- numerical methods have deterministic seeds and mathematical documentation;
- README claims match implemented and tested behavior;
- real-Aspen verification status is stated explicitly.

## Adding a semantic node

1. Add an ordered candidate list to the YAML registry.
2. Define access mode, quantity, unit, bounds and status.
3. Add validation and resolution tests.
4. Validate against the target case using Variable Explorer.
5. Mark it project-specific until real-case evidence exists.

## Adding an optimizer or DOE method

- use typed bounded variables;
- preserve deterministic seeds;
- cap points and workers;
- use the common feasibility result;
- make failures finite for transport but worst under feasibility ordering;
- test on MockBackend before a licensed Aspen case.
