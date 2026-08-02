# AspenOps V3 Phase 5 Implementation Report

## Status

- Phase status: `PASS_BUILD_CONTRACTS`
- Qualification scope: `FRESH_RUNTIME_AUTHORIZATION_CONTRACTS`
- Execution scope: software authorization contracts only
- Real simulator status: `PENDING_REAL_ASPEN_CERTIFICATION`
- Pull request: draft PR #108
- Qualified implementation head: `3314813f24fb53161b370d7e6d5f349a9cc8eb2d`

## Objective

Phase 5 closes the post-verification reuse gap in the Phase 3 signed runtime
qualification. A qualification that was valid when a
`RuntimeQualifiedCompilationPlan` was created must not remain usable after the
qualification expires, its trusted key is removed, its profile changes, or an
administrator revokes any load-bearing identity.

The native execution boundary now performs a fresh authorization immediately
before reading any adapter property or executing any compilation step.

## Implemented Contracts

### Runtime revocation policy

`src/aspenops_nexus/runtime_execution_authorization.py` defines the strict
schema `aspenops.runtime-revocations/v1` and the immutable
`RuntimeRevocationPolicy` model.

The policy binds:

- policy ID;
- issued-at and expires-at times;
- revoked qualification signing-key IDs;
- revoked qualification-evidence SHA-256 values;
- revoked profile IDs;
- revoked profile SHA-256 values;
- revoked adapter-code SHA-256 values;
- revoked runtime-identity SHA-256 values.

The policy parser requires the exact field set, timezone-aware times, a positive
validity interval, bounded arrays, unique entries, strict digest/key shapes and
an absolute trusted-key directory. The policy must exist as
`revocations.json` inside the trusted-key directory and must be current at the
execution time.

### Fresh runtime authorization

`authorize_runtime_execution()` now:

1. rejects blocked or non-qualified plans;
2. rejects a currently revoked capability profile;
3. confirms that the qualified plan still matches the current profile;
4. canonicalizes the required Golden Case set;
5. reloads the original signed qualification through the current trusted-key
   directory;
6. re-verifies the Ed25519 signature, signing-key fingerprint, issued-at time,
   expiration time and required Golden Cases;
7. requires exact equality with the qualification embedded in the qualified
   compilation plan;
8. rechecks qualification evidence, signing key, adapter code and runtime
   identity against the plan;
9. loads the current revocation policy;
10. rejects every revoked identity;
11. produces an immutable `FreshRuntimeAuthorization` whose expiration is the
    earlier of the qualification expiration and policy expiration.

### Native execution boundary

`execute_compilation_plan()` now requires the current capability profile,
original signed qualification source and trusted-key directory. Fresh
authorization occurs before any adapter property or operation is accessed.

The execution record now includes:

- fresh runtime-authorization SHA-256;
- revocation-policy SHA-256;
- authorization time;
- authorization expiration time;
- revalidated qualification evidence, adapter code, runtime identity and
  profile hashes.

A plain `CompilationPlan` is rejected before authorization arguments are
required. A legitimate runtime-qualified plan without fresh authorization
inputs is also rejected explicitly.

## Adversarial Tests

`tests/test_runtime_execution_authorization.py` covers:

- deterministic authorization and expiration bounding;
- a qualification that was previously valid but is expired at execution;
- a future qualification;
- removal of the current trusted key;
- missing revocation policy;
- future and expired revocation policies;
- revocation of the signing key;
- revocation of qualification evidence;
- revocation of profile ID and profile hash;
- revocation of adapter code;
- revocation of runtime identity;
- current profile revocation and profile substitution;
- additional execution-time Golden Case requirements;
- substitution with another independently valid signed envelope;
- exact fields, unique entries, bounded arrays, timezone handling and trusted
  directory confinement.

`tests/test_native_builder_contract.py` additionally proves that authorization
failure occurs before any adapter property is read and retains all topology,
layout, profile, code, runtime and mandatory-readback failures.

## Qualification Evidence

Final standard validation on head
`3314813f24fb53161b370d7e6d5f349a9cc8eb2d`:

- Linux quality, build and smoke job: passed;
- Ruff lint and exact formatter: passed;
- strict mypy: passed;
- Python source compilation and source audit: passed;
- Bandit security analysis: passed;
- dependency audit: passed;
- documentation, artifact and workflow governance: passed;
- distributions, portable demo, performance policy, MCP surface, wheel install
  and CLI smoke: passed;
- Python 3.11: 1157 passed, 95.29% branch coverage;
- Python 3.12: 1157 passed, 95.29% branch coverage;
- Python 3.13: 1157 passed, 95.31% branch coverage;
- Python 3.12 reverse and fixed-seed order-independence gate: passed for all
  1157 tests;
- Windows control-plane workflow: passed.

Workflow evidence:

- Linux CI run: `30761479757`;
- Windows run: `30761479730`.

## Explicit Non-Claims

Phase 5 does not claim or provide:

- an Aspen Plus or HYSYS native adapter;
- commercial simulator execution;
- a production trusted-key directory or production revocation policy;
- production signing or qualification keys;
- real Golden Case execution;
- native topology/layout readback;
- native save, close or reopen operations;
- licensed runtime repeatability evidence;
- human engineering acceptance;
- `REAL_ASPEN_CERTIFIED` status.

The policy file is an administrator-controlled local trust input. Its digest is
recorded in execution evidence, but operating-system permissions and trusted
administrative deployment remain required for production use.
