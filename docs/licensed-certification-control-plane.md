# Licensed Aspen certification control plane

## Purpose

This document defines the executable governance boundary for real Aspen Plus and
Aspen HYSYS qualification. Portable CI, public Windows Fake COM contracts and
Mock performance evidence are prerequisites, not substitutes for licensed
simulator certification.

AspenOps deliberately separates four decisions:

1. **Plan validity** — the JSON document is complete, narrow and unambiguous.
2. **Preflight readiness** — the approved machine, commit, artifacts, licenses,
   engineering tolerances and signing key are present before COM is opened.
3. **Runtime gate** — the exact plan executes on independent staged copies and
   produces repeatable, scoped runtime evidence.
4. **Certification decision** — qualified humans review physical validity,
   process containment, failure injection, license behavior, signed evidence and
   known exclusions.

No code path in AspenOps can perform step 4 automatically.

## Status vocabulary

| Status | Meaning |
|---|---|
| `CONTROL_PLANE_VERIFIED` | Portable Mock/Fake orchestration passed. No real simulator claim. |
| `PENDING_ENGINEERING_ACCEPTANCE` | Required tolerances or engineering approval are absent; real COM is not opened. |
| `PENDING_REAL_ASPEN_CERTIFICATION` | A plan may be ready or its runtime gate may have passed, but independent human certification remains incomplete. |
| `REAL_ASPEN_CERTIFIED` | External governance status. AspenOps never writes this value itself. |

A signed bundle proves origin and integrity of the scoped evidence. It does not
prove physical correctness and does not grant `REAL_ASPEN_CERTIFIED`.

## Required roles

The same person should not silently approve every boundary.

- **Process/model owner** approves the exact model and Registry digests.
- **Qualified engineer** approves output, balance, repeatability and acceptance
  tolerances for the stated scope.
- **License/IT owner** approves Runner identity, COM installation, license server,
  feature names and slot limit.
- **Security/key owner** provisions an Ed25519 private key outside the repository
  workspace and publishes its trusted public key and key identifier.
- **Release reviewer** reviews signed evidence, known exclusions and the exact Git
  commit before changing any external certification register.

## Plan schema

Plans use:

```text
aspenops.licensed-certification-plan/v1
```

The plan binds all of the following:

- case identifier;
- exact 40-character Git commit;
- backend (`aspen_plus` or `hysys`);
- complete batch request;
- model and Registry SHA-256 digests;
- independent repeat count and Worker matrix;
- default and per-output tolerances;
- engineering reviewer, timestamp and scope;
- approved COM ProgIDs and narrow version patterns;
- license server identity, features and slots;
- approved self-hosted Runner names and architecture;
- required Ed25519 key identifier.

The loader rejects unknown fields, Boolean numeric fields, non-finite values,
duplicate Worker counts, Worker counts above approved license slots, wildcard
ProgID/Runner/feature scopes, malformed digests, timezone-free approvals and
broad or invalid version patterns.

`examples/licensed-certification-plan.example.json` is a template. Its zero
hashes and placeholder identities are intentionally incapable of passing
preflight.

## Preflight

Run:

```powershell
uv run aspenops certification-preflight `
  examples\approved-plan.json `
  --output C:\AspenOps\state\licensed-certification\preflight.json
```

Preflight does not open COM. It emits structured `blockers`, `warnings` and
`evidence` and fails closed when any blocker exists.

It verifies:

- native Windows;
- `RUNNER_ENVIRONMENT=self-hosted`;
- approved Runner name and architecture;
- exact checked-out commit;
- backend and explicit `ASPENOPS_ALLOWED_ROOTS`;
- model and Registry existence, location and SHA-256;
- approved engineering status and explicit finite tolerances;
- exact license slot count, server identity and feature set;
- a genuinely registered approved ProgID (compatibility fallbacks do not count);
- writable state directory;
- mounted Ed25519 key outside `GITHUB_WORKSPACE` with matching key ID;
- normal AspenOps dry-run validation.

Only `ready=true` permits the licensed execution command. Readiness authorizes
execution of the narrow plan; it is not certification.

## Runner configuration

The protected GitHub environment is named:

```text
licensed-aspen-certification
```

The Runner must carry all labels:

```text
self-hosted, windows, x64, aspen-licensed
```

Repository/environment variables:

```text
ASPENOPS_ALLOWED_ROOTS
ASPENOPS_CERT_STATE_DIR
ASPENOPS_LICENSE_SLOTS
ASPENOPS_LICENSE_SERVER_IDENTITY
ASPENOPS_LICENSE_FEATURES
ASPENOPS_CERT_PUBLIC_KEY_PATH
```

Protected secret:

```text
ASPENOPS_CERT_SIGNING_KEY_PATH
```

The secret value is a path to a Runner-local mounted private key. It is not PEM
content. The key must be outside the checkout and must never be uploaded as an
artifact.

## Manual workflow

`.github/workflows/licensed-aspen-certification.yml` is `workflow_dispatch` only.
It requires:

- repository-relative plan path;
- exact approved commit SHA;
- backend;
- explicit Boolean authorization for real execution.

The job checks out the exact SHA without persistent write credentials, runs in
the protected environment, performs preflight before the licensed command,
verifies the resulting signed bundle with a trusted public key and asserts that
the report status remains `PENDING_REAL_ASPEN_CERTIFICATION`.

The workflow cannot merge the PR, push code, modify certification status or
upload the private key.

## Runtime gate

Run directly only on the approved Runner:

```powershell
uv run aspenops certify-licensed `
  examples\approved-plan.json `
  --output-dir C:\AspenOps\state\licensed-certification
```

For each approved Worker count, AspenOps runs independent model copies using the
approved repeat count and tolerances. It compares:

- transport, engine, convergence and feasibility states;
- units, violations and request identity;
- required output values;
- balance residual details;
- actual runtime ProgID and exposed version evidence.

A matching numerical result from an unapproved ProgID or out-of-scope version
fails the runtime gate.

The report always remains:

```text
PENDING_REAL_ASPEN_CERTIFICATION
```

## Signed evidence bundle

The bundle schema is:

```text
aspenops.licensed-certification-bundle/v1
```

It contains:

- `manifest.json`;
- `plan.json`;
- `preflight.json`;
- `report.json`;
- `environment.json` with an explicit safe allowlist;
- `manifest.sig`;
- `signing-key-id.txt`.

Every content member has a SHA-256 and byte size in the manifest. The canonical
manifest is signed with Ed25519. Verification applies the same ZIP path,
compression-ratio, member-count and bounded-read protections as normal AspenOps
integrity bundles.

Verify independently:

```powershell
uv run aspenops verify-licensed-bundle `
  C:\AspenOps\state\licensed-certification\licensed-certification-bundle.zip `
  --public-key C:\AspenOps\keys\trusted-public.pem
```

Only `signed-valid` is acceptable for certification review.

## Human certification review

A release reviewer must separately confirm:

- approved Aspen/HYSYS versions and actual runtime identity;
- external Aspen process protection and timeout cleanup;
- rollback, taint and generation replacement behavior;
- license denial/recovery and concurrency matrix;
- service restart, cancellation and stale-owner behavior;
- engineering acceptance of physical values and balances;
- repeated real-simulator performance with queue, solve and end-to-end timing
  separated;
- signed bundle validity and evidence digests;
- exclusions and unsupported releases.

Only an external certification register maintained by authorized humans may
record `REAL_ASPEN_CERTIFIED` together with the exact versions, model/Registry
digests, commit, Runner, date, evidence digests and exclusions.

## Failure policy

- Blocked preflight: do not open COM.
- Runtime failure: preserve signed evidence and remain pending.
- Signature failure: evidence is unacceptable; do not reinterpret it as an
  unsigned pass.
- Missing engineering tolerance: return `PENDING_ENGINEERING_ACCEPTANCE`.
- Missing licensed Runner: continue portable improvements, but do not fabricate a
  real run.
- Any source change after certification execution invalidates the commit scope and
  requires the affected real tests to be repeated.
