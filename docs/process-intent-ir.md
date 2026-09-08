# Simulator-neutral Process Intent IR

## Purpose

AspenOps separates process understanding from simulator execution. The Process Intent IR is a deterministic, simulator-neutral graph that can be produced by a human, an image/text interpretation Agent or a future synthesis/search system without granting that producer access to COM, arbitrary Python, Shell, VBA or raw Aspen Tree Paths.

The current schema is:

```text
aspenops.flowsheet/v1
```

This release implements parsing, normalization, validation, capability declarations, benchmark records and visual evidence. It does **not** claim that an Aspen Plus, HYSYS, DWSIM, IDAES or Modelica flowsheet compiler is implemented.

## Core graph

```text
ProcessIntent
├── components[]
├── units[]
│   ├── ports[]: in | out
│   ├── parameters[]: finite scalar + optional unit
│   └── metadata
├── streams[]
│   ├── source: unit + output port
│   ├── target: unit + input port
│   ├── components[]
│   ├── parameters[]
│   └── metadata
├── property_package
└── metadata
```

Identifiers are restricted to stable alphanumeric forms. Unknown fields fail closed. Parameters accept finite JSON scalar values only. Metadata rejects keys associated with executable code or simulator-private path injection.

## Validation

`validate_process_intent()` reports deterministic error and warning codes for:

- duplicate component, unit, stream, port or parameter identifiers;
- unknown component, unit or port references;
- source/target port-direction mismatch;
- required but unconnected ports;
- self-connections;
- duplicate endpoint pairs and implicit fan-out/fan-in on one port;
- noncanonical unit kinds;
- missing property packages;
- directed recycle cycles;
- resource limits.

Recycle cycles are warnings by default because recycles are valid process structures. Callers may set `allow_recycles=False` to make cycles an error for synthesis stages that are not yet allowed to generate recycles.

## Determinism

`ProcessIntent.canonical_json()` sorts components, units, ports, parameters, streams and component references. `ProcessIntent.digest()` computes SHA-256 over that canonical representation. Equivalent graphs with different input ordering therefore have the same identity.

## Backend capability boundary

Execution and IR compilation are separate claims:

| Backend | Existing execution | Process IR compiler |
|---|---|---|
| Mock | available | planned |
| Aspen Plus | available, licensed Windows | planned |
| HYSYS | available, licensed Windows | planned |
| DWSIM | planned | planned |
| IDAES | planned | planned |
| Modelica/FMI | planned | planned |

`require_ir_compiler()` raises `BackendUnavailableError` until a compiler is explicitly implemented and tested. Planned adapters cannot be mistaken for operational capability.

## Bounded Agent pipeline

```text
Knowledge
→ Concept / topology
→ Parameter declaration
→ Validated execution request
→ Bounded repair proposal
→ Convergence, balance and human-review gate
```

Each stage has a declared responsibility and permitted output. The concept, parameter and repair stages may emit only the Process Intent IR, not executable simulator code.

## Local validation

```bash
uv run python scripts/validate_process_ir.py \
  examples/process-intent.example.json \
  --canonical-output var/ci/process-intent-canonical.json \
  --report-output var/ci/process-intent-report.json

uv run python scripts/render_process_ir_dashboard.py \
  --input var/ci/process-intent-report.json \
  --output-html var/ci/process-ir-dashboard.html \
  --output-svg var/ci/process-ir-dashboard.svg
```

Use `--disallow-recycles` when validating a feed-forward-only generation stage. Use `--capabilities-only` to inspect the declared Agent pipeline and backend capability matrix without reading a flowsheet.

## Benchmark evidence

`FlowsheetBenchmarkRecord` separates:

- topology validity;
- compiler availability;
- whether execution was attempted;
- convergence;
- material and energy balance closure;
- repair iterations;
- human intervention.

A non-attempted execution cannot declare convergence or balance results. This prevents planned backends and skipped simulator runs from being counted as successful simulations.
