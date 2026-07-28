# Research Study Layer

AspenOps Research Study Layer is the schema-only scientific-governance layer above the existing
execution control plane. Phase 1 defines research objects and validates their evidence graph. It does
not open Aspen, compile research plans into runtime requests, estimate parameters, or grant an
engineering qualification.

## Current milestone

```text
M1_SCHEMA_ONLY
RUNTIME_UNCHANGED
NO_NEW_EXECUTION_PATH
```

The canonical document schema marker is:

```text
aspenops.research-study/v1
```

A document contains one `Study` and collections of seven linked object types:

```text
Study
├── Dataset
├── Target
├── Parameter
├── Assumption
├── Calibration
├── Validation
└── Claim
```

The Python contract is implemented in `aspenops_nexus.research`. Draft 2020-12 JSON Schemas are
shipped as package data under `src/aspenops_nexus/data/research-*.schema.json`. A complete synthetic
fixture is available at `examples/research-study.example.json`.

## Scientific invariants

The validator fails closed when any of these boundaries are violated:

1. Calibration and Validation reuse the same Dataset, immutable data artifact, split group, or record
   set digest.
2. Calibration consumes a Dataset whose role is not `calibration`.
3. Validation consumes a Dataset whose role is not `validation` or `stress_test`.
4. Validation does not bind the exact immutable parameter snapshot produced by an accepted
   Calibration.
5. Validation model or Registry snapshots drift from the Study snapshots.
6. A Claim exceeds the Study or linked Validation maturity ceiling.
7. A Claim omits restrictions inherited from its Assumptions.
8. A licensed engineering Claim lacks a passed, engineer-approved, real-simulator Validation.
9. Research metadata contains raw simulator paths, executable-code fields, Shell, VBA, or unrestricted
   commands.
10. Study lifecycle state advances without the required accepted Calibration, passed Validation, or
    supported Claim.

## Claim maturity

```text
STRUCTURE_ONLY
SOURCE_CASE_REPRODUCED
CALIBRATED_IN_DOMAIN
VALIDATED_HELD_OUT
ROBUSTNESS_TESTED
LICENSED_ENGINEERING_REVIEWED
```

A source reproduction is not an industrial validation. Mock or Fake COM evidence cannot support
`LICENSED_ENGINEERING_REVIEWED`.

## Library usage

```python
from aspenops_nexus.research import ResearchStudyDocument

study = ResearchStudyDocument.load("examples/research-study.example.json")
report = study.validate()
if not report.ok:
    raise RuntimeError(report.to_dict())
```

The validator is pure Python and has no runtime dependency beyond the standard library. The JSON
Schemas are publication and interoperability contracts; the Python graph validator is authoritative for
cross-object rules that JSON Schema cannot prove, such as record leakage, accepted parameter snapshot
lineage, maturity ceilings, and Assumption restriction propagation.

## Deliberate non-capabilities

Phase 1 does not provide a CLI, MCP tool, Aspen Data Fit adapter, Design Specification adapter,
Sensitivity runner, GPC deconvolution engine, dynamic grade-transition runner, surrogate model, or
research evidence bundle. Those capabilities remain later milestones and must reuse the existing
AspenOps semantic Registry, `EvaluationRequest`, process isolation, constraints, balances,
provenance, and certification boundary.
