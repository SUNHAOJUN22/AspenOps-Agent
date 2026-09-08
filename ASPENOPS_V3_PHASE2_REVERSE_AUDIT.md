# AspenOps V3 Phase 2 Reverse Audit

## Audit boundary and decision

This audit challenges the Phase 2 simulator-neutral compilation contracts in draft PR #105. It does not inspect or certify any licensed Aspen Plus or Aspen HYSYS runtime because no native adapter is implemented and no commercial-runtime execution occurred.

Current decision:

`PASS_BUILD_CONTRACTS`

Qualification scope:

`OFFLINE_COMPILATION_CONTRACTS`

Real simulator status:

`PENDING_REAL_ASPEN_CERTIFICATION`

## Attack and failure matrix

### 1. Offline profile is represented as executable

**Attack:** Use a built-in Aspen Plus or HYSYS 14/15 profile to authorize COM execution.

**Control:** Every built-in profile is `OFFLINE_CONTRACT_ONLY`; `SimulatorCapabilityProfile.executable` is false and the compilation plan is `PLAN_ONLY` when no engineering error exists.

**Expected result:** `CompilationPlan.assert_executable()` fails before a native adapter is called.

### 2. Profile target does not match the design

**Attack:** Compile an Aspen Plus 15 design with a HYSYS profile or a different marketing version.

**Control:** `assert_matches_design()` and `profile.target_mismatch` bind simulator family and marketing version.

**Expected result:** Plan status `BLOCKED`; no steps are emitted.

### 3. Profile ID is substituted at execution time

**Attack:** Present an adapter with a different `profile_id` while retaining the plan.

**Control:** `execute_compilation_plan()` requires exact `profile_id` equality.

**Expected result:** `NativeBuildError` before the first step.

### 4. Profile bytes or capability declarations are substituted

**Attack:** Present an adapter with a profile whose ID matches but whose capability contents differ.

**Control:** Execution requires exact `profile_hash` equality.

**Expected result:** `NativeBuildError` before the first step.

### 5. Design contains an unsupported equipment kind

**Attack:** Introduce an equipment kind absent from the capability profile.

**Control:** Compiler emits `capability.equipment_missing`.

**Expected result:** Plan status `BLOCKED` and zero steps.

### 6. Profile explicitly marks equipment unsupported

**Attack:** Attempt to use an equipment kind marked `UNSUPPORTED`.

**Control:** Compiler emits `capability.equipment_unsupported`.

**Expected result:** Plan status `BLOCKED`.

### 7. Equipment uses an undeclared port domain

**Attack:** Add material, energy or information ports outside the profile contract.

**Control:** Compiler compares observed port domains with declared profile domains.

**Expected result:** `capability.port_domain` and plan status `BLOCKED`.

### 8. Equipment uses an undeclared parameter or design specification

**Attack:** Add a parameter name for which no adapter contract exists.

**Control:** Every equipment parameter and design specification is checked against the profile.

**Expected result:** `capability.parameter_missing` and plan status `BLOCKED`.

### 9. Stream kind is unsupported

**Attack:** Introduce a stream kind outside the profile stream contract.

**Control:** Compiler checks every stream kind.

**Expected result:** `capability.stream_kind` and plan status `BLOCKED`.

### 10. Invalid engineering design reaches compilation

**Attack:** Pass a design with broken endpoints, ports, required connections, equipment specifications, reactions or recycles.

**Control:** Phase 1 engineering validation is executed before capability compilation. Hard errors and engineering blockers are translated to compilation errors.

**Expected result:** Plan status `BLOCKED` and zero steps.

### 11. Compilation order changes with input list order

**Attack/failure:** Reorder equipment and stream arrays and obtain a different plan.

**Control:** Equipment creation uses deterministic topological ordering; components, parameters, streams, reactions and recycles are sorted by stable IDs.

**Expected result:** Identical plan digest for equivalent normalized design content.

### 12. Recycle is solved before tear initialization

**Attack/failure:** Enable a recycle without initialization or open-loop stabilization.

**Control:** Plan order is: configure recycle, initialize tear stream, solve open loop, then solve closed loop.

**Expected result:** Closed-loop step contains explicit preconditions and cannot precede initialization in the deterministic plan.

### 13. Save occurs without topology or layout verification

**Attack/failure:** Persist a case after a solver return but before verifying the native graph.

**Control:** `save_case` requires `topology_verified` and `layout_verified` preconditions.

**Expected result:** A compliant adapter cannot represent a successful save before both readbacks.

### 14. Save/reopen changes the flowsheet

**Attack/failure:** Native topology or layout changes during save, close or reopen.

**Control:** The plan requires second topology and layout readbacks after reopen.

**Expected result:** Any post-reopen mismatch raises `NativeBuildError`.

### 15. Native runtime omits a node

**Attack/failure:** A native equipment object is missing.

**Control:** `compare_topology()` reports `node.missing`.

**Expected result:** Build fails before evidence can claim completion.

### 16. Native runtime adds an unapproved node

**Attack/failure:** An unexpected native object appears.

**Control:** `compare_topology()` reports `node.extra`.

**Expected result:** Build fails.

### 17. Native node kind changes

**Attack/failure:** An approved equipment ID maps to the wrong native kind.

**Control:** `compare_topology()` reports `node.kind`.

**Expected result:** Build fails.

### 18. Native runtime omits or adds a stream

**Attack/failure:** A connection is missing or an extra connection is present.

**Control:** `compare_topology()` reports `edge.missing` or `edge.extra`.

**Expected result:** Build fails.

### 19. Native stream endpoints or ports change

**Attack/failure:** Stream ID exists but uses the wrong equipment endpoint or port.

**Control:** Full `TopologyEdge` equality includes kind, source equipment, source port, target equipment and target port.

**Expected result:** `edge.contract` and build failure.

### 20. Topology source label changes the identity

**Failure:** The expected snapshot says `ProcessDesignIR` while native readback says `native-readback`, creating a false mismatch.

**Control:** The descriptive `source` field is excluded from `identity_dict()` and the topology digest.

**Expected result:** Equal graph content has one topology hash regardless of source label.

### 21. Adapter returns a non-object result

**Attack/failure:** A native adapter returns text, a list or another unstructured value.

**Control:** Every ordinary step result must be a dictionary.

**Expected result:** `NativeBuildError`.

### 22. Adapter returns an object but omits mandatory readback

**Attack/failure:** Adapter reports success without the expected identity or parameter values.

**Control:** `_contains_expected()` recursively requires every expected key and value.

**Expected result:** `NativeBuildError` identifying the failing step.

### 23. Adapter reports a different layout hash

**Attack/failure:** Native layout differs from the approved deterministic layout contract.

**Control:** Both layout readback steps require exact layout-hash equality.

**Expected result:** `NativeBuildError`.

### 24. Adapter reports a different topology hash

**Attack/failure:** Native topology differs from the approved graph.

**Control:** Native snapshot is compared structurally; digest equality alone is not trusted.

**Expected result:** `NativeBuildError` with mismatch codes.

### 25. Raw COM paths are inserted into the profile

**Risk:** An LLM or request supplies vendor tree paths or arbitrary COM calls.

**Current control:** Built-in profiles contain only AspenOps-owned abstract adapter keys. No native adapter accepts request-provided paths in this phase.

**Remaining requirement:** Future native adapters must keep path/method mappings in reviewed project-owned code or signed runtime profiles and must never accept arbitrary LLM paths.

### 26. A verified profile label is assigned without licensed evidence

**Risk:** A caller constructs an in-memory profile with `VERIFIED_ON_TARGET_RUNTIME` and uses a fake adapter.

**Current control:** This phase proves only the software contract. Built-in profiles remain offline-only and no trusted profile loader or signed runtime-qualification bundle exists.

**Remaining external gate:** Before commercial use, runtime-qualified profiles must be loaded only from signed, approved evidence bound to exact simulator version, installed object model, adapter code and Golden Cases.

## CI evidence

The validated code head completed the governed PR matrix:

- Python 3.11: 1116 passed, 95.79% branch coverage;
- Python 3.12: 1116 passed, 95.77% branch coverage;
- Python 3.13: 1116 passed, 95.77% branch coverage;
- Python 3.12 reverse and fixed-seed order-independence gates passed;
- Ruff, exact formatter, strict mypy, Bandit, dependency audit and source-tree audit passed;
- build, wheel installation, CLI, MCP and performance gates passed;
- Windows control-plane workflow passed.

New-module coverage on the validated matrix included:

- `compilation_plan.py`: 95%;
- `native_builder.py`: 100%;
- `native_topology.py`: 98%;
- `simulator_capabilities.py`: 99%.

## Remaining external and implementation gates

The following block any stronger conclusion:

1. No Aspen Plus native builder exists.
2. No HYSYS native builder exists.
3. No official/version-specific COM mapping has been encoded and reviewed.
4. No licensed Aspen Plus 14 or 15 runtime has executed a plan.
5. No licensed HYSYS 14 or 15 runtime has executed a plan.
6. No native `.bkp`, `.apw`, `.apwz` or `.hsc` file has been created.
7. No native topology or layout has been read back.
8. No native save/close/reopen roundtrip has been executed.
9. No signed runtime-qualified capability profile exists.
10. No Phase 2 Golden Case has passed on a licensed self-hosted Windows runner.
11. No independent human engineering acceptance has been recorded.

## Audit conclusion

The audit grants only:

`PASS_BUILD_CONTRACTS` for `OFFLINE_COMPILATION_CONTRACTS`.

It does not grant:

- `PASS_REAL_V15_CASE_SCOPE`;
- `PASS_WITH_REMAINING_EXTERNAL_ENGINEERING_GATE`;
- `REAL_ASPEN_CERTIFIED`.
