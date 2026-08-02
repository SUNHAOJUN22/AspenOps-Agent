# AspenOps V3 Phase 2 Implementation Report

## Execution identity

- Repository: `SUNHAOJUN22/AspenOps-Agent`
- Stacked base: `feature/aspenops-process-requirement-ir-v2`
- Working branch: `feature/aspenops-v15-compilation-contracts`
- Draft pull request: `#105`
- Validated code head before report-only commits: `3d37a736b6ad1eda90194debd84fd42ee77f3587`
- Phase 1 dependency: draft PR `#104`, status `PASS_BUILD_CONTRACTS`

## Current admissible status

`PASS_BUILD_CONTRACTS`

Qualification scope:

`OFFLINE_COMPILATION_CONTRACTS`

This status means the versioned capability-profile schema, deterministic compilation plan, native-topology comparison contract and fail-closed adapter protocol passed the governed software matrix. It does **not** mean that Aspen Plus or Aspen HYSYS objects were created, connected, solved, saved or reopened on a licensed runtime.

Real simulator status remains:

`PENDING_REAL_ASPEN_CERTIFICATION`

## Implemented Phase 2 contracts

### Versioned simulator capability profiles

Schema identifier: `aspenops.simulator-capability-profile/v1`.

The branch provides built-in profiles for:

- Aspen Plus 14;
- Aspen Plus 15;
- Aspen HYSYS 14;
- Aspen HYSYS 15.

Every built-in profile is explicitly classified as:

`OFFLINE_CONTRACT_ONLY`

Therefore no built-in profile can authorize native execution. A profile becomes executable only after it is separately qualified as `VERIFIED_ON_TARGET_RUNTIME` by a future licensed-runtime evidence process.

Each profile records:

- simulator family and marketing version;
- expected private model extensions;
- adapter-contract identifier;
- supported stream kinds;
- equipment-kind capability declarations;
- abstract adapter keys;
- declared port domains;
- supported parameter names;
- qualification state and source boundary.

The profiles intentionally do not contain raw Aspen tree paths or unverified COM method names.

### Deterministic compilation plan

Schema identifier: `aspenops.compilation-plan/v1`.

The compiler combines a validated `ProcessDesignIR v2` with one versioned capability profile and returns one of:

- `BLOCKED` when engineering or capability errors exist;
- `PLAN_ONLY` when the design is valid but the profile is not runtime-qualified;
- `EXECUTABLE` only when the design is valid and the exact profile is `VERIFIED_ON_TARGET_RUNTIME`.

The deterministic plan contains ordered steps for:

1. profile and design identity checks;
2. private case-shell creation;
3. component definition;
4. property-method selection;
5. boundary and equipment creation;
6. equipment parameters and design specifications;
7. stream creation and connection;
8. reaction definition;
9. recycle and tear initialization;
10. open-loop solve;
11. closed-loop solve when recycles exist;
12. native topology readback;
13. native layout readback;
14. private-output save;
15. case close;
16. case reopen;
17. second native topology readback;
18. second native layout readback.

The plan carries the design hash, capability-profile hash, expected topology hash and expected deterministic preview-layout hash.

### Native topology contract

Schema identifier: `aspenops.native-topology/v1`.

The topology snapshot records:

- simulator family and marketing version;
- equipment IDs and kinds;
- stream IDs and kinds;
- source equipment and port;
- target equipment and port.

Topology identity excludes the descriptive `source` field, so the same graph read from `ProcessDesignIR` and a native runtime has one identity. Comparison reports fail on:

- simulator or version mismatch;
- missing or extra nodes;
- changed node kind;
- missing or extra edges;
- changed edge kind, endpoints or ports.

### Fail-closed native-builder boundary

The `NativeBuildAdapter` protocol and `execute_compilation_plan()` establish the mandatory execution boundary for future licensed adapters.

Execution requires:

- an `EXECUTABLE` plan;
- exact adapter `profile_id` equality;
- exact adapter `profile_hash` equality;
- object-shaped step results;
- every expected readback field and value;
- topology equality before save;
- layout-hash equality before save;
- topology equality after reopen;
- layout-hash equality after reopen.

Any mismatch raises `NativeBuildError` and stops the plan.

No Aspen Plus or HYSYS implementation of `NativeBuildAdapter` is included in this phase.

## Security and integrity properties

- No raw COM path is exposed to an LLM or user request.
- Capability gaps block compilation rather than silently falling back.
- Unsupported equipment, stream kinds, port domains and parameters are explicit errors.
- Built-in offline profiles cannot be executed.
- Profile-ID or profile-hash substitution is rejected.
- Adapter results must satisfy mandatory readback subsets.
- Topology and layout are checked both before save and after reopen.
- Topology hash does not drift when only descriptive source metadata changes.
- Source models are not overwritten by the compilation contract.

## Added regression coverage

The Phase 2 tests cover:

- all four built-in simulator/version profiles;
- profile schema roundtrip and digest stability;
- invalid schema, simulator, version, qualification and extensions;
- duplicate equipment and stream declarations;
- design/profile target mismatch;
- unsupported equipment;
- missing parameter adapters;
- unsupported port domains and stream kinds;
- deterministic equipment ordering and plan hashing;
- blocked, plan-only and executable states;
- recycle initialization and closed-loop steps;
- missing, extra and changed topology nodes;
- missing, extra and changed topology edges and ports;
- descriptive-source-independent topology identity;
- adapter profile forgery;
- non-object adapter responses;
- missing mandatory readback;
- topology mismatch;
- layout mismatch.

## Final CI evidence for the validated code head

### Python matrix

| Runtime | Result | Branch coverage |
|---|---:|---:|
| Python 3.11 | 1116 passed | 95.79% |
| Python 3.12 | 1116 passed | 95.77% |
| Python 3.13 | 1116 passed | 95.77% |

The Python 3.12 complete-suite order-independence gate passed in reverse order and with fixed seed `20260728`.

### Quality, build and packaging gates

The following completed successfully:

- frozen lockfile verification;
- dependency synchronization and audit;
- Ruff lint and exact Ruff formatting;
- strict mypy;
- Python source compilation;
- governed source-tree audit;
- Bandit security analysis;
- documentation and Process IR contracts;
- source distribution and wheel build;
- portable demo;
- durable CLI smoke;
- committed performance policy;
- MCP surface verification;
- clean wheel installation and CLI smoke.

### Windows control-plane gate

The Windows 2025 workflow completed successfully, including the full test suite and the long-path/8.3-file-identity regression contract inherited from Phase 1.

## Explicit non-goals and remaining external gates

The following are not implemented or not executed:

- Aspen Plus 14 native builder;
- Aspen Plus 15 native builder;
- HYSYS 14 native builder;
- HYSYS 15 native builder;
- verified native equipment and port mappings;
- licensed COM object creation;
- native stream connection;
- solver execution on a commercial runtime;
- native flowsheet layout control;
- save/close/reopen on `.bkp`, `.apw`, `.apwz` or `.hsc` files;
- native topology readback from Aspen Plus or HYSYS;
- native layout readback from Aspen Plus or HYSYS;
- signed runtime-qualified capability profiles;
- licensed V15 Golden Cases;
- independent engineering acceptance.

## Final boundary

The highest supported conclusion for this branch is:

`PASS_BUILD_CONTRACTS` for `OFFLINE_COMPILATION_CONTRACTS`.

It does not grant `PASS_REAL_V15_CASE_SCOPE`, `PASS_WITH_REMAINING_EXTERNAL_ENGINEERING_GATE` or `REAL_ASPEN_CERTIFIED`.
