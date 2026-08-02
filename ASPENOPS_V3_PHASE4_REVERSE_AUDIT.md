# AspenOps V3 Phase 4 Reverse Audit

## Audit Question

Can a generated, runtime-qualified compilation plan and an existing licensed
certification plan be presented as one approved evidence chain without proving
that they refer to the same profile, adapter, runtime, model, registry,
topology, layout, Golden Cases and approved commit?

## Result

No. Phase 4 introduces a deterministic offline binding contract that makes each
of those identities explicit and recomputable. The contract is qualified only
as `OFFLINE_BINDING_ONLY`; it cannot authorize execution and cannot grant real
Aspen certification.

## Threat Review

### 1. Substituting a different licensed model

**Attack:** retain the same case name while changing the approved model file or
its digest.

**Control:** the link stores both the complete licensed-plan canonical hash and
the approved model SHA-256. `assert_matches()` reconstructs the link and detects
both fields.

**Result:** blocked.

### 2. Substituting a different registry

**Attack:** keep the model but change the approved registry and therefore the
permitted Aspen/HYSYS paths.

**Control:** the registry SHA-256 and complete licensed-plan hash are bound.

**Result:** blocked.

### 3. Reusing approval on another Git revision

**Attack:** run code from a different commit while retaining the approved case
and artifact digests.

**Control:** the full approved 40-character Git SHA is included in the link and
in the complete licensed-plan digest.

**Result:** blocked by link comparison; runtime preflight remains separately
responsible for checking the actually checked-out commit.

### 4. Switching Aspen Plus and HYSYS

**Attack:** use a qualified Aspen Plus compilation plan with a HYSYS licensed
plan, or the reverse.

**Control:** licensed-plan backend must equal capability-profile simulator. The
runtime qualification must independently match the same profile.

**Result:** blocked.

### 5. Profile substitution

**Attack:** replace the capability profile after qualification while retaining
similar equipment support.

**Control:** profile ID, profile SHA-256 and adapter contract are all bound. The
signed qualification must match the supplied profile before a link can be
created.

**Result:** blocked.

### 6. Adapter implementation substitution

**Attack:** retain the same adapter-contract name while changing the adapter
implementation.

**Control:** adapter-code SHA-256 from the signed runtime qualification is
bound in the link.

**Result:** blocked by link comparison and, later, by the Phase 3 native
execution boundary.

### 7. Runtime substitution

**Attack:** reuse qualification evidence on a different simulator installation,
runner image or licensed runtime identity.

**Control:** runtime-identity SHA-256 is bound from the signed qualification.
The existing licensed certification plan separately constrains runner,
architecture, ProgID, version patterns, license server and license features.

**Result:** offline substitution is detectable. Real-runtime proof remains an
unexecuted gate.

### 8. Qualification-evidence substitution

**Attack:** replace the signed qualification with another statement that uses
the same profile but different Golden Cases, adapter code or runtime identity.

**Control:** the qualification evidence SHA-256 and qualification signing-key ID
are both bound, in addition to the adapter, runtime and Golden Case identities.

**Result:** blocked.

### 9. Qualified-plan substitution

**Attack:** retain the same signed qualification while changing process design,
compilation order, topology or layout.

**Control:** the runtime-qualified plan digest, deterministic base-plan digest,
expected topology digest and expected layout digest are all bound.

**Result:** blocked.

### 10. Missing Golden Case coverage

**Attack:** certify a licensed case that was not included in the signed runtime
qualification, or silently remove an additionally required case.

**Control:** the licensed case ID is mandatory in the passed Golden Case set.
All required case IDs are canonicalized, stored and revalidated.

**Result:** blocked.

### 11. Forging an executable state in JSON

**Attack:** edit a serialized link from `OFFLINE_BINDING_ONLY` to `EXECUTABLE`.

**Control:** strict parsing accepts only `OFFLINE_BINDING_ONLY`; the real
simulator state must remain `PENDING_REAL_ASPEN_CERTIFICATION`.

**Result:** blocked.

### 12. Adding ignored fields

**Attack:** add an alternative digest, override or approval field that a loose
parser might ignore.

**Control:** `from_dict()` requires the exact dataclass field set and rejects
both missing and unknown fields.

**Result:** blocked.

### 13. Hash-shape ambiguity

**Attack:** use truncated, uppercase, malformed or non-SHA identifiers.

**Control:** all SHA-256 values, commit IDs and key IDs are parsed with strict
lowercase fixed-length patterns.

**Result:** blocked.

### 14. Claiming execution or certification from an offline link

**Attack:** treat a successful link as evidence that Aspen Plus/HYSYS executed,
converged, saved or passed engineering review.

**Control:** the schema fixes execution scope to `OFFLINE_BINDING_ONLY`; the
real status remains pending. The implementation report explicitly separates
software-contract qualification from commercial-runtime evidence.

**Result:** blocked by data model and governance language.

## Residual Risks and Required Future Evidence

The following risks are intentionally not represented as solved:

1. no native Aspen Plus or HYSYS build adapter exists in this phase;
2. no real simulator installation has supplied the bound runtime identity;
3. no real adapter binary/source package has supplied the bound adapter-code
   digest under a production key;
4. no generated native model has been saved, closed and reopened;
5. no native topology or layout has been read back;
6. no commercial solver convergence or physical-balance acceptance occurred;
7. no production Golden Case bundle exists;
8. no licensed repeatability matrix was run;
9. no independent human engineering acceptance occurred;
10. no transition to `REAL_ASPEN_CERTIFIED` is authorized.

## Qualification Conclusion

The Phase 4 software contract and its adversarial tests satisfy the offline
binding objective. Qualification status is therefore:

- `PASS_BUILD_CONTRACTS` for the implemented software contract;
- `QUALIFIED_LICENSED_BINDING_CONTRACTS` for the evidence-link scope;
- `OFFLINE_BINDING_ONLY` for execution scope;
- `PENDING_REAL_ASPEN_CERTIFICATION` for all commercial-runtime claims.
