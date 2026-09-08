# AspenOps V3 Phase 3 Reverse Audit

## Decision

`PASS_BUILD_CONTRACTS` for `SIGNED_RUNTIME_QUALIFICATION_CONTRACTS`.

Real simulator status remains `PENDING_REAL_ASPEN_CERTIFICATION`.

## Adversarial checks

The implemented tests reject:

- duplicate or non-finite qualification JSON;
- malformed statement or envelope shapes;
- wrong signature algorithm;
- invalid base64 or invalid Ed25519 signature;
- document tampering after signing;
- wrong trusted public key;
- not-yet-valid or expired qualifications;
- naive verification time without timezone;
- failed or duplicate Golden Cases;
- missing required Golden Cases;
- profile ID, hash, simulator, version or adapter-contract mismatch;
- revoked profiles;
- blocked base compilation plans;
- plain base-plan execution even when its profile enum says verified;
- adapter profile-ID or profile-hash substitution;
- adapter-code hash substitution;
- runtime-identity hash substitution;
- missing mandatory readback;
- topology or layout mismatch.

## Remaining trust boundary

Python code executing inside the trusted AspenOps process is part of the trusted computing base. The signed qualification API prevents untrusted request documents and ordinary serialized data from authorizing execution; it is not a sandbox against a malicious administrator who can replace Python modules, trusted keys or adapter code. Production qualification must therefore bind signed evidence to an immutable release, exact adapter code, exact runtime identity and controlled trust store.

## Remaining external gates

No production qualification exists. No licensed Aspen Plus/HYSYS native adapter or commercial-runtime Golden Case was executed. Human engineering acceptance remains mandatory.
