# AspenOps V3 Phase 0 Reverse Audit

## Audit boundary and decision

This audit challenges only the Phase 0 controls implemented in draft PR #103. It does not certify natural-language flowsheet construction or licensed Aspen V15 engineering behavior.

Current decision for the implemented Phase 0 control-plane scope:

`PASS_CONTROL_PLANE`

This decision is supported by successful Linux quality/build/Wheel/MCP gates, 947 passing tests on each of Python 3.11, 3.12 and 3.13, complete-suite order-independence on Python 3.12, and the Windows control-plane contract workflow.

Real licensed simulator status remains:

`PENDING_REAL_ASPEN_CERTIFICATION`

## Attack and failure matrix

### 1. Source model changes after PoolManager digest capture

**Attack:** Replace the source model after `PoolManager.acquire()` computes its lookup digest but before a Worker copies the file.

**Control:** `CasePool` computes its own approval digest; `PoolManager` compares the resulting pool identity with the lookup digest. Worker staging separately compares the copied model with the expected digest.

**Expected result:** Pool creation fails, staged files are removed, no lease or cache entry is created.

**Coverage:** Dedicated PoolManager mismatch test plus CasePool source-change test.

### 2. Source registry changes after identity capture

**Attack:** Replace the semantic registry after approval but before the Worker loads it.

**Control:** Registry is copied into the private Worker directory, copied digest is compared with the approved digest, and `NodeRegistry.sha256` must still match after parsing.

**Expected result:** Startup fails before simulator use.

**Coverage:** Dedicated registry source-change and staged-identity tests.

### 3. Private staged artifact is modified

**Attack:** Change the staged model or registry after the parent copies it.

**Control:** The child recomputes both digests before backend creation. The model is checked again after simulator open; registry parser digest must match the child digest.

**Expected result:** Fatal Worker startup, parent cleanup and no execution.

**Remaining limitation:** No operating-system read-only ACL is applied to the staging directory. Digest checks detect changes at defined boundaries but do not make the files physically immutable. Windows ACL/file-handle hardening remains follow-up work.

### 4. Worker forges a ready digest

**Attack:** A compromised or defective Worker returns a digest different from the parent-approved digest.

**Control:** `_validate_ready_message()` compares both model and registry digests.

**Expected result:** Startup rejected and Worker terminated.

**Coverage:** Forged-ready-message test.

### 5. Worker result contains a forged execution identity

**Attack:** Child result payload includes a different model or registry identity.

**Control:** Parent `evaluate_on_worker()` and the live `CasePool` dispatch path replace/bind result execution identity with trusted pool and `WorkerHandle` values before cacheability or evidence creation.

**Expected result:** Child-supplied identity cannot become authoritative.

### 6. Cache lookup uses old bytes for new execution

**Attack:** Register a pool under digest A while actual Workers run artifact B.

**Control:** PoolManager-to-CasePool digest comparison, Worker handshake, live parent result binding, result identity check in `_cacheable()`, and stable runtime identity in the cache key.

**Expected result:** Mismatch fails or result is not cacheable.

### 7. Evidence bundle hashes a later source file

**Attack:** Run model A, then replace the original source with model B before evidence creation.

**Control:** Runtime results create V3 bundles whose artifact identity comes from the verified Worker result, not from the source request path.

**Expected result:** Manifest continues to bind model A.

**Coverage:** Source-replacement-after-execution test.

### 8. Recalculate result/member hashes after changing execution identity

**Attack:** Rewrite result execution identity and update ordinary member and result hashes without updating the V3 manifest identity.

**Control:** V3 semantic verification independently derives execution identity from results and compares it with manifest fields.

**Expected result:** `content-invalid`.

**Coverage:** Rewritten-result-identity test.

### 9. Mix results from different runtimes or artifacts

**Attack:** Place results from different model snapshots or runtime identities in one evidence bundle.

**Control:** Bundle writer requires one identical derived execution identity across all results.

**Expected result:** Bundle creation rejected.

### 10. Read a write-only semantic node

**Attack:** Place `access="write"` node in an output, constraint or balance.

**Control:** Evaluation-plan read resolution rejects any node not marked `read` or `readwrite`.

**Expected result:** Dry-run/plan compilation fails before Worker or COM startup.

**Coverage:** Three path-specific tests.

### 11. Backend silently ignores a write

**Attack:** COM setter returns without applying a numeric or string value.

**Control:** Base transaction performs read-after-write for every item.

**Expected result:** Verification error and verified rollback.

**Coverage:** Ignored numeric and string write tests.

### 12. Backend coerces Boolean to integer

**Attack:** Backend stores `True` as integer `1`.

**Control:** Discrete comparison requires identical types and values.

**Expected result:** Verification failure. If rollback is also coerced and cannot restore exact type, Worker becomes tainted.

**Coverage:** Boolean coercion/tainted rollback test.

### 13. Evidence JSON contains NaN, Infinity or duplicate keys

**Attack:** Place non-standard constants or duplicate object keys in bundle members.

**Control:** Strict JSON loader rejects non-finite constants and duplicate keys; semantic exceptions return structured invalid status.

**Expected result:** `structure-invalid`, not an unhandled exception.

**Coverage:** Non-finite evidence test; CLI duplicate/non-finite request tests.

### 14. Signed bundle uses a friendly but unrelated key ID

**Attack:** Sign with one key while assigning `production-key` or another arbitrary label as the key ID.

**Control:** The writer requires the supplied ID, when present, to equal the derived Ed25519 public-key fingerprint. The verifier checks the manifest ID, ID member and trusted public key.

**Expected result:** Writer rejects mismatch or verifier rejects the bundle.

### 15. MCP client supplies an arbitrary verification-key path

**Attack:** Agent passes a path outside administrator control.

**Control:** MCP accepts only a lowercase 32-character key fingerprint. File location is derived inside absolute `ASPENOPS_TRUSTED_KEY_DIR` and checked for containment.

**Expected result:** Path-like input rejected before filesystem access.

### 16. Unsupported MCP 1.x version

**Attack:** Run with MCP 1.0 or 1.8 and rely on major-only compatibility.

**Control:** Runtime parser requires major 1 and minor at least 9; 2.x and malformed versions are rejected while existing public constants and diagnostics remain compatible.

**Expected result:** Server refuses startup with an actionable dependency error.

### 17. Job Object setup fails for a real simulator

**Attack/failure:** Windows Job Object cannot manage the Worker, leaving COM child processes outside guaranteed kill-on-close containment.

**Control:** Non-Mock Worker startup requires `job_scope.managed` before backend open.

**Expected result:** Real simulator is not opened.

**Compatibility impact:** Hosts where nested Job Objects are prohibited fail closed. This is intentional and must still be validated on the approved licensed self-hosted runner.

### 18. Scheduler lease is lost during execution

**Existing control:** Heartbeat failure forces pool recycling and owner-fenced job-store updates.

**Phase 0 interaction:** Forced recycling removes private staged model and registry copies.

**Expected result:** Lost owner cannot commit a successful result.

### 19. Cancellation races completion

**Existing control:** Completion/final-cancellation updates require a valid owner and unexpired lease. Bundle adoption is checked; an unadopted bundle is deleted.

**Phase 0 interaction:** Cancel deadline can force Worker recycling without leaving staged artifacts.

### 20. Legacy V2 evidence is mistaken for execution-bound V3 evidence

**Risk:** Compatibility callers without Worker identity can still create V2 bundles.

**Control:** V2 manifest includes `execution_identity_bound=false`; V3 has a distinct format and semantic identity checks.

**Remaining policy requirement:** Downstream policy must require V3 for any claim about the bytes actually opened by a simulator.

## CI evidence

The implemented controls passed the governed PR matrix:

- Python 3.11: 947 passed, 95.22% branch coverage;
- Python 3.12: 947 passed, 95.24% branch coverage;
- Python 3.13: 947 passed, 95.24% branch coverage;
- reverse and fixed-seed complete-suite order gates passed on Python 3.12;
- Ruff, formatter, strict mypy, Bandit, dependency audit and source audit passed;
- build, Wheel installation, dependency check, CLI and MCP smoke passed;
- Windows control-plane contracts passed.

## Remaining follow-up and external gates

The following do not overturn `PASS_CONTROL_PLANE`, but they block stronger conclusions:

1. Aspen Plus still has a base/strict adapter split that should be consolidated.
2. Backend polling environment variables have not yet been migrated into strict `Settings` fields.
3. Licensed-certification preflight and execution should be bound through one persistent approved snapshot, not only normal pool revalidation.
4. Windows staging ACL/read-only hardening is not implemented.
5. ProcessRequirement, ProcessDesignIR v2, equipment contracts, deterministic compilers, topology roundtrip and natural-language design layers are not implemented.
6. No licensed Aspen Plus V15 or HYSYS V15 Golden Case has executed.
7. No human engineering acceptance has been recorded.

Therefore this audit grants only:

`PASS_CONTROL_PLANE`

It does not grant `PASS_BUILD_CONTRACTS`, `PASS_REAL_V15_CASE_SCOPE`, `PASS_WITH_REMAINING_EXTERNAL_ENGINEERING_GATE` or `REAL_ASPEN_CERTIFIED`.
