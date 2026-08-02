# AspenOps V3 Phase 6 Implementation Report

## Status

- Phase status: `PASS_BUILD_CONTRACTS`
- Qualification scope: `SIGNED_CHAINED_REVOCATION_POLICY_CONTRACTS`
- Execution scope: software authorization contracts only
- Real simulator status: `PENDING_REAL_ASPEN_CERTIFICATION`
- Pull request: draft PR #109
- Qualified implementation head: `eefb01d8659fba19e4b31ce0272e4c17aea6dcd9`

## Objective

Phase 6 replaces the unsigned administrator-controlled runtime revocation file
introduced in Phase 5 with an independently signed, chained and
checkpoint-validated revocation-policy contract.

The objective is to prevent an attacker or accidental local edit from silently
changing revocation contents, and to detect replay of an older policy or
replacement of the current policy at the same sequence.

## Signed Revocation Policy

`src/aspenops_nexus/signed_revocation_policy.py` defines:

- signed statement schema
  `aspenops.signed-runtime-revocation-statement/v1`;
- signed envelope schema
  `aspenops.signed-runtime-revocation-policy/v1`;
- checkpoint schema `aspenops.runtime-revocation-checkpoint/v1`;
- `SignedRevocationPolicyStatement`;
- `VerifiedSignedRevocationPolicy`;
- `RevocationPolicyCheckpoint`;
- Ed25519 signing and verification;
- trusted-directory loading and path confinement;
- checkpoint validation and advancement.

The signed statement contains:

1. a positive monotonic sequence number;
2. the previous signed-policy evidence SHA-256, except for sequence 1;
3. the complete strict `RuntimeRevocationPolicy` from Phase 5.

The signature is created by a revocation authority whose public key is stored
separately from runtime-qualification keys under:

`revocation-authorities/<key_id>.pem`

The active signed policy and checkpoint are stored as:

- `revocations.signed.json`;
- `revocation-checkpoint.json`.

Legacy unsigned `revocations.json` is not accepted by the execution path.

## Checkpoint and Rollback Rules

The checkpoint records:

- accepted sequence;
- accepted signed-policy evidence SHA-256;
- accepted revocation-authority key ID.

Validation accepts only:

- the exact currently accepted policy at the accepted sequence; or
- exactly the next sequence whose signed predecessor equals the currently
  accepted policy evidence SHA-256.

It rejects:

- an older sequence;
- a different policy at the same sequence;
- a different authority at the same sequence;
- a skipped sequence;
- a next policy with an incorrect predecessor;
- an initial policy whose sequence is not 1;
- a non-initial policy without a predecessor.

## Runtime Authorization Integration

`FreshRuntimeAuthorization` is updated to schema
`aspenops.fresh-runtime-authorization/v2` and now records:

- signed revocation-policy evidence SHA-256;
- revocation-authority key ID;
- signed policy sequence;
- checkpoint SHA-256.

Fresh runtime authorization now requires successful signed-policy verification,
policy time validation, checkpoint validation and the Phase 5 revocation checks
before any native adapter access.

`NativeBuildExecutionRecord` carries the same policy authority, sequence and
checkpoint identities so that each execution record is attributable to the
specific signed revocation state used at authorization time.

## Adversarial Tests

`tests/test_signed_revocation_policy.py` covers:

- deterministic signing and verification;
- signed-statement strict round-trip parsing;
- content tampering;
- wrong revocation-authority key;
- invalid sequence/predecessor combinations;
- initial checkpoint creation;
- exactly-next policy advancement;
- same-sequence policy replacement;
- old-sequence rollback;
- skipped sequence;
- incorrect predecessor chain;
- authority change at the accepted sequence;
- missing checkpoint;
- missing authority key;
- relative trust-root rejection;
- checkpoint unknown fields and invalid values.

The Phase 5 runtime authorization and native builder tests are migrated to
install an independent revocation authority, signed policy and matching
checkpoint. They retain all expiration, key-removal, six-dimensional
revocation, profile-substitution, qualification-substitution and
authorization-before-adapter-access checks.

## Qualification Evidence

Final standard validation on head
`eefb01d8659fba19e4b31ce0272e4c17aea6dcd9`:

- Linux quality, build and smoke job: passed;
- Ruff lint and exact formatter: passed;
- strict mypy: passed;
- Python source compilation and source audit: passed;
- Bandit security analysis: passed;
- dependency audit: passed;
- documentation, artifact and workflow governance: passed;
- distributions, portable demo, performance policy, MCP surface, wheel install
  and CLI smoke: passed;
- Python 3.11: 1168 passed, 95.12% branch coverage;
- Python 3.12: 1168 passed, 95.12% branch coverage;
- Python 3.13: 1168 passed, 95.14% branch coverage;
- Python 3.12 reverse and fixed-seed order-independence gate: passed for all
  1168 tests;
- Windows control-plane workflow: passed.

Workflow evidence:

- Linux CI run: `30762188501`;
- Windows run: `30762188513`.

## Explicit Non-Claims

Phase 6 does not claim or provide:

- externally anchored monotonic storage;
- a transparency service or distributed append-only log;
- protection if both the signed policy and local checkpoint are rolled back
  together to an earlier mutually consistent pair;
- production revocation-authority keys;
- operating-system ACL or hardware-backed trust-root deployment;
- an Aspen Plus or HYSYS native adapter;
- commercial simulator execution;
- real Golden Case or licensed repeatability evidence;
- human engineering acceptance;
- `REAL_ASPEN_CERTIFIED` status.

The local checkpoint is trusted state. Rollback detection remains effective
only while the checkpoint itself is protected from rollback by external
administrative, filesystem or hardware controls.
