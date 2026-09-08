# AspenOps V3 Phase 5 Reverse Audit

## Audit Question

Can a runtime qualification that was valid when a compilation plan was wrapped
continue to authorize native execution after it expires, its trusted key is
removed, its profile changes, or an administrator revokes a load-bearing
identity?

## Result

No. Phase 5 requires a fresh authorization immediately before any native
adapter access. The original signed qualification is reloaded through the
current trusted-key directory, reverified at the current execution time and
checked against a current administrator-controlled revocation policy.

## Threat Review

### 1. Reusing an expired qualification

**Attack:** create a qualified compilation plan while a qualification is valid,
then execute the plan after the signed qualification expires.

**Control:** every execution re-runs Ed25519 verification and the signed
issued-at/expiration checks using the current execution time.

**Result:** blocked. A dedicated test constructs a qualification that was valid
at wrapper creation but expired at execution.

### 2. Reusing a not-yet-valid qualification

**Attack:** validate or store a future-dated qualification and execute it before
its issued-at time.

**Control:** fresh qualification loading rejects a current time before
`issued_at`.

**Result:** blocked.

### 3. Removing a formerly trusted key

**Attack:** continue using a wrapper after an administrator removes its public
key from the trusted-key directory.

**Control:** the key is looked up again by the signed key fingerprint for every
execution.

**Result:** blocked when the current key is unavailable.

### 4. Replacing the current trusted key

**Attack:** place another public key under the same intended qualification
context.

**Control:** the public-key fingerprint must equal the key ID inside the signed
envelope, and the signature must verify.

**Result:** blocked.

### 5. Missing revocation policy

**Attack:** remove or omit revocation state so old authorizations silently
continue.

**Control:** `revocations.json` is mandatory for native execution.

**Result:** fail-closed.

### 6. Stale revocation policy

**Attack:** retain an old policy indefinitely after administrators stop
maintaining it.

**Control:** the policy contains issued-at and expires-at values and must be
current at execution.

**Result:** future and expired policies are blocked.

### 7. Signing-key revocation

**Attack:** use a still-cryptographically-valid qualification after its signing
key is administratively compromised or withdrawn.

**Control:** the current policy can revoke the qualification signing-key ID.

**Result:** blocked.

### 8. Qualification-evidence revocation

**Attack:** continue using a specific signed qualification after its evidence is
withdrawn without revoking every key signed by the same authority.

**Control:** the policy can revoke the exact qualification-evidence SHA-256.

**Result:** blocked.

### 9. Profile revocation or substitution

**Attack:** execute with a profile that has been revoked, or substitute a
modified profile after the wrapper was created.

**Control:** execution rejects a current profile whose state is `REVOKED`,
requires exact plan/profile ID and SHA-256 equality, revalidates the signed
qualification against the profile and supports revocation by profile ID or
profile SHA-256.

**Result:** blocked.

### 10. Adapter-code revocation

**Attack:** continue using a qualified adapter implementation after a defect or
security issue is discovered.

**Control:** the current policy can revoke the adapter-code SHA-256 bound in the
signed qualification.

**Result:** blocked.

### 11. Runtime-identity revocation

**Attack:** continue using a particular simulator installation or runner image
after it is withdrawn.

**Control:** the current policy can revoke the runtime-identity SHA-256.

**Result:** blocked.

### 12. Substituting another valid qualification

**Attack:** present another independently valid envelope for the same profile at
execution, potentially with different approval scope, adapter code, runtime or
Golden Cases.

**Control:** the freshly verified qualification must exactly equal the
qualification embedded in the runtime-qualified compilation plan. Evidence,
key, adapter and runtime identities are also rechecked individually.

**Result:** blocked.

### 13. Weakening Golden Case scope after wrapper creation

**Attack:** execute without a newly required Golden Case or omit an originally
required case.

**Control:** execution recomputes the union of the wrapper's required cases and
any additional execution-time requirements, then revalidates all cases against
the signed qualification.

**Result:** blocked.

### 14. Touching the adapter before authorization

**Attack:** allow adapter startup, profile lookup or another side effect before
revocation and expiry checks complete.

**Control:** fresh authorization occurs before reading `profile_id`,
`profile_hash`, adapter-code identity, runtime identity or applying any step.

**Result:** a test uses an adapter whose first property access raises an
assertion and confirms missing policy fails before that access.

### 15. Omitting new authorization inputs

**Attack:** call the native execution function through an older path that does
not provide the current profile, signed envelope or trusted-key directory.

**Control:** a legitimate runtime-qualified plan without those inputs receives
an explicit fail-closed error. A plain base plan is rejected even earlier,
before argument validation can replace the intended security error with a
Python `TypeError`.

**Result:** blocked.

### 16. Tampering with revocation policy after execution

**Attack:** alter the policy after an execution and make it difficult to prove
which policy was used.

**Control:** the canonical revocation-policy SHA-256 and fresh-authorization
SHA-256 are recorded in the execution record, together with authorization and
expiration times.

**Result:** retrospective drift is detectable from the recorded identity. The
policy file itself is not a signed transparency log.

## Residual Risks and Required Future Evidence

The following are intentionally not represented as solved:

1. `revocations.json` is trusted through administrator-controlled filesystem
   deployment; the policy is not itself signed in Phase 5;
2. operating-system ACLs, protected deployment and backup of the trust directory
   remain external operational controls;
3. there is no centralized revocation distribution or transparency service;
4. there is no native Aspen Plus or HYSYS adapter;
5. there is no real simulator runtime identity or adapter-code package under a
   production qualification;
6. there is no commercial solver execution, native persistence or native
   topology/layout readback;
7. there is no real Golden Case or licensed repeatability evidence;
8. there is no independent human engineering acceptance;
9. no transition to `REAL_ASPEN_CERTIFIED` is authorized.

## Qualification Conclusion

The Phase 5 software authorization and revocation contracts satisfy the
post-verification freshness objective. Qualification status is therefore:

- `PASS_BUILD_CONTRACTS` for the implemented software contract;
- `FRESH_RUNTIME_AUTHORIZATION_CONTRACTS` for qualification scope;
- `SOFTWARE_AUTHORIZATION_ONLY` for execution scope;
- `PENDING_REAL_ASPEN_CERTIFICATION` for all commercial-runtime claims.
