# AspenOps V3 Phase 6 Reverse Audit

## Audit Question

Can a local administrator or attacker silently alter, replace or roll back the
runtime revocation policy used by Phase 5 fresh authorization while preserving
a superficially valid file layout?

## Result

Policy contents are now authenticated by an independent Ed25519 revocation
authority. A trusted checkpoint detects an older policy, a different policy at
the same sequence, a different authority at the same sequence, skipped
sequences and a broken predecessor chain.

The checkpoint remains local trusted state. Coordinated rollback of both the
signed policy and checkpoint to an older mutually consistent pair is outside
the protection supplied by this phase.

## Threat Review

### 1. Editing revocation contents

**Attack:** add or remove a revoked key, profile, qualification, adapter or
runtime identity in the local policy file.

**Control:** the complete strict revocation policy is included in an Ed25519
signed statement.

**Result:** signature verification fails.

### 2. Replacing the revocation authority key

**Attack:** install another public key and claim it is the authority for the
same signed policy.

**Control:** the envelope contains the authority key fingerprint, and the
loaded public key must produce the same key ID before signature verification.

**Result:** blocked.

### 3. Using qualification keys as policy-authority keys

**Attack:** place the revocation authority inside the qualification-key
namespace and blur authority responsibilities.

**Control:** revocation-authority keys are loaded only from the separate
`revocation-authorities/` subdirectory.

**Result:** trust namespaces are separated by contract and path.

### 4. Replaying an older sequence

**Attack:** replace the active policy with a correctly signed earlier policy.

**Control:** the checkpoint records the accepted sequence. A lower sequence is
explicitly rejected as rollback.

**Result:** blocked while the checkpoint is current.

### 5. Replacing the policy at the same sequence

**Attack:** sign a different policy with the same sequence, possibly using the
same authority.

**Control:** the current sequence must have the exact checkpointed policy
evidence SHA-256.

**Result:** blocked.

### 6. Replacing the authority at the same sequence

**Attack:** present a policy whose evidence is paired with another authority at
the currently accepted sequence.

**Control:** the checkpoint binds both policy evidence and authority key ID.

**Result:** blocked.

### 7. Skipping a policy sequence

**Attack:** move from sequence N directly to N+2 and conceal an intermediate
policy or revocation event.

**Control:** only the current sequence or exactly the next sequence is
accepted.

**Result:** blocked.

### 8. Breaking the predecessor chain

**Attack:** present sequence N+1 without linking it to the exact accepted
sequence-N policy evidence.

**Control:** the next statement contains a signed predecessor-policy SHA-256,
which must equal the checkpointed evidence digest.

**Result:** blocked.

### 9. Forging an initial checkpoint from a later policy

**Attack:** initialize trust directly at sequence greater than 1 and omit
history.

**Control:** initial checkpoint creation requires sequence 1 and no
predecessor.

**Result:** blocked.

### 10. Removing the checkpoint

**Attack:** delete the checkpoint and force the system to accept the current
signed policy without rollback context.

**Control:** both signed policy and checkpoint are mandatory for runtime
authorization.

**Result:** fail-closed.

### 11. Removing the revocation authority

**Attack:** remove the authority key and rely on cached or previously verified
state.

**Control:** the authority public key is reloaded on every fresh authorization.

**Result:** fail-closed.

### 12. Falling back to the Phase 5 unsigned file

**Attack:** provide `revocations.json` after deleting the signed policy.

**Control:** the runtime authorization loader accepts only
`revocations.signed.json` plus a matching checkpoint and authority key.

**Result:** blocked.

### 13. Tampering with checkpoint fields

**Attack:** add override fields, use malformed digests, use sequence zero or
change accepted authority identity.

**Control:** checkpoint parsing requires the exact field set, positive sequence,
strict SHA-256 and strict key-ID shapes.

**Result:** blocked.

### 14. Claiming global rollback protection

**Attack:** represent local checkpoint validation as protection against every
possible rollback.

**Control:** reports and data models explicitly limit the claim to a protected
current checkpoint.

**Result:** no global or hardware-backed non-rollback claim is made.

## Residual Risks and Required Future Evidence

The following risks remain intentionally open:

1. the local checkpoint can be rolled back together with the signed policy if
   an attacker controls all trusted-directory files and no external monotonic
   anchor exists;
2. the checkpoint is not itself stored in TPM/NVRAM, a protected database or an
   external append-only service;
3. no transparency log or independent witness records policy publication;
4. revocation-authority key rotation across sequences is not authorized by a
   separate root policy in this phase;
5. operating-system ACLs and protected deployment remain external controls;
6. no production keys or policies exist;
7. no native Aspen Plus or HYSYS adapter exists;
8. no commercial solver, native persistence, topology/layout readback, real
   Golden Case, repeatability or human engineering acceptance occurred;
9. no transition to `REAL_ASPEN_CERTIFIED` is authorized.

## Qualification Conclusion

The Phase 6 signed policy and local checkpoint contracts satisfy the scoped
content-authentication and protected-checkpoint rollback-detection objective.
Qualification status is therefore:

- `PASS_BUILD_CONTRACTS` for the implemented software contract;
- `SIGNED_CHAINED_REVOCATION_POLICY_CONTRACTS` for qualification scope;
- `SOFTWARE_AUTHORIZATION_ONLY` for execution scope;
- `PENDING_REAL_ASPEN_CERTIFICATION` for all commercial-runtime claims.
