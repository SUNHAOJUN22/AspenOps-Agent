# AspenOps V3 Phase 3 Implementation Report

## Scope and result

Phase 3 introduces signed runtime-profile qualification contracts on top of the Phase 2 offline compilation contracts.

Current status:

`PASS_BUILD_CONTRACTS`

Qualification scope:

`SIGNED_RUNTIME_QUALIFICATION_CONTRACTS`

Real simulator status remains:

`PENDING_REAL_ASPEN_CERTIFICATION`

## Implemented contracts

- strict qualification statement and signed-envelope schemas;
- duplicate-key and non-finite JSON rejection;
- Ed25519 signatures and public-key fingerprint binding;
- issued-at and expires-at validation;
- capability profile ID and SHA-256 binding;
- simulator, marketing version and adapter-contract binding;
- adapter-code SHA-256 binding;
- runtime-identity SHA-256 binding;
- passed Golden Case evidence digests and required-case checks;
- signed approver identity and approval scope;
- administrator-controlled trusted-key directory;
- `RuntimeQualifiedCompilationPlan` wrapper over the unchanged Phase 2 base plan;
- native execution restricted to the signed wrapper type;
- exact adapter profile, code and runtime-identity checks before the first native step;
- qualification evidence identity carried into the native execution record.

## Security conclusion

Merely changing a capability profile enum to `VERIFIED_ON_TARGET_RUNTIME` is insufficient. A plain `CompilationPlan`, including one whose in-memory profile enum was altered, is rejected by the native execution boundary. Execution requires a verified signed qualification and the resulting runtime-qualified wrapper.

## Validation

The Phase 3 qualification matrix completed Linux quality/build gates, Python 3.11/3.12/3.13 full suites with required branch coverage, Python 3.12 reverse and fixed-seed order independence, and the Windows full test suite.

## Explicit boundary

All signing tests use synthetic temporary Ed25519 keys and synthetic Golden Case digests. No production trust key, licensed runtime qualification, native Aspen Plus/HYSYS adapter, commercial solver run, save/reopen roundtrip or human engineering approval was created in this phase.

Therefore Phase 3 does not grant `PASS_REAL_V15_CASE_SCOPE`, `PASS_WITH_REMAINING_EXTERNAL_ENGINEERING_GATE` or `REAL_ASPEN_CERTIFIED`.
