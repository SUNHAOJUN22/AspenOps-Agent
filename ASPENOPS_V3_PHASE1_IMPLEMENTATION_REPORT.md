# AspenOps V3 Phase 1 Implementation Report

## Scope

Phase 1 adds the deterministic simulator-neutral engineering design layer required before any natural-language request can reach Aspen Plus or Aspen HYSYS.

- Branch: `feature/aspenops-process-requirement-ir-v2`
- Stacked draft PR: `#104`
- Base: `feature/aspenops-natural-language-flowsheet-v3`
- Current status: `FAIL_CLOSED_PENDING_CI`
- Real simulator status: `PENDING_REAL_ASPEN_CERTIFICATION`

This phase contains no COM calls and makes no claim that an Aspen Plus V15 or HYSYS V15 native flowsheet has been built.

## Implemented artifacts

### Process requirement schema

`aspenops.process-requirement/v1` records:

- project, target simulator, target version and language;
- process objective;
- feeds, components, composition basis and operating conditions;
- products and required specifications;
- required process sections;
- approved property method;
- accepted and unresolved assumptions;
- requested outputs and bounded metadata.

Every critical scalar or composition item carries one of:

- `USER_PROVIDED`;
- `APPROVED_DEFAULT`;
- `INFERRED_PENDING_APPROVAL`;
- `UNKNOWN`.

The readiness gate returns only:

- `READY_FOR_DESIGN`; or
- `NEEDS_ENGINEERING_INPUT`.

Pending assumptions, unknown feed conditions, unapproved composition, missing products or an unapproved property method block design readiness.

### ProcessDesignIR v2

`aspenops.flowsheet/v2` provides strong typed definitions for:

- components and target-simulator identifiers;
- property method, simulator version scope and rationale;
- equipment, vendor type, ports and design specifications;
- material, energy, information, feed, product, waste, utility and tear streams;
- reactions and stoichiometry;
- recycle and tear-stream convergence contracts.

Internal object identifiers must use bounded ASCII. User-facing display names are NFC-normalized Unicode and reject NUL, replacement characters, control characters and bidirectional override characters.

Target simulator and version are allowlisted. Unknown simulator names, unknown version scopes and unsupported equipment contracts fail closed.

### Requirement-to-design identity

`ProcessDesignIR` must contain the exact SHA-256 of the approved `ProcessRequirementDocument`.

The cross-document contract checks:

- requirement digest;
- simulator and target version;
- required component scope;
- feed boundary IDs;
- product boundary IDs;
- approved property method.

A topologically valid design cannot detach itself from the user-approved requirement.

### Deterministic engineering rules

The engineering rule engine classifies findings as:

- `HARD_ERROR`;
- `ENGINEERING_BLOCKER`;
- `WARNING`;
- `INFORMATION`.

Implemented deterministic checks include:

- property-method approval, vendor and version scope;
- component approval and vendor mapping;
- port existence, direction and material/energy/information domain;
- required and multiple connection rules;
- material component scope;
- unknown or pending parameters;
- feed, product, mixer, splitter, heater, cooler, flash, separator, pump, compressor, valve, column and reactor contracts;
- efficiency ranges;
- column stage, feed-stage and independent specification requirements;
- reaction approval, component references and reactant/product direction;
- material cycles, recycle declarations and tear-stream ownership.

Unknown equipment kinds are engineering blockers, not permissive warnings.

### Plant template catalogue

Ten governed template definitions are included:

1. Heater–Flash;
2. Mixer–Heater–Separator;
3. Compression–Cooling–Separation;
4. Reactor–Cooler–Flash–Recycle;
5. Two-column sequence;
6. Absorber–Regenerator;
7. Gas dehydration;
8. Distillation column;
9. Reaction–Separation–Recycle;
10. HYSYS natural-gas pretreatment.

Templates declare simulator/version scope, equipment and connection skeletons, required engineering inputs, balance scopes, initialization sequence and unsupported conditions.

Instantiation remains `NEEDS_ENGINEERING_INPUT` until every required input is explicitly approved. A complete input set produces only `PLAN_ONLY`, never simulator execution.

### Deterministic preview

The preview layer emits:

- canonical graph JSON;
- stable equipment coordinates;
- layout hash;
- escaped SVG.

The preview is explicitly marked as an external design preview. It does not prove that Aspen Plus or HYSYS contains the same native objects, ports, connections or layout.

## Added examples

- `examples/process-requirement-v1.example.json`
- `examples/process-design-v2.example.json`

These describe a governed Heater–Flash design draft with ASCII internal IDs and a Chinese display label. The design is not a real Aspen model and is not qualified physical evidence.

## Added tests

The Phase 1 tests cover:

- requirement roundtrip and readiness;
- composition and component scope;
- Unicode and internal-ID safety;
- resource limits before large-list materialization;
- ProcessDesignIR roundtrip and digest stability;
- port direction/domain failures;
- pending parameters;
- property-method version scope;
- column degrees of freedom;
- unknown reaction components;
- recycle/tear contracts;
- unsupported simulator/version/equipment targets;
- template scope and approval gates;
- deterministic layout, graph and escaped SVG;
- exact requirement-to-design identity.

## Explicitly not implemented

Phase 1 does not implement:

- a natural-language parser;
- an LLM planner;
- Aspen Plus or HYSYS COM calls;
- native equipment placement;
- native stream connection;
- native simulator topology readback;
- property-method selection from official V15 capability profiles;
- component, elemental or energy balance calculations from simulator results;
- convergence orchestration;
- bounded repair execution;
- save, close, reopen or rerun qualification;
- licensed V15 Golden Cases.

## Phase exit criteria

Phase 1 can advance to `PASS_BUILD_CONTRACTS` only when the stacked PR completes:

- Ruff and formatter;
- strict mypy;
- full Python 3.11, 3.12 and 3.13 tests with the existing branch-coverage floors;
- complete-suite order-independence;
- build and Wheel smoke;
- MCP and CLI governance checks;
- Windows control-plane contracts;
- source-tree and workflow-governance checks;
- Phase 1 reverse audit with no unresolved design-layer software blocker.

Until then, status remains `FAIL_CLOSED_PENDING_CI`.
