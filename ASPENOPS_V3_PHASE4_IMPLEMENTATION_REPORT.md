# AspenOps V3 Phase 4 Implementation Report

## Status

- Phase status: `PASS_BUILD_CONTRACTS`
- Qualification scope: `QUALIFIED_LICENSED_BINDING_CONTRACTS`
- Execution scope: `OFFLINE_BINDING_ONLY`
- Real simulator status: `PENDING_REAL_ASPEN_CERTIFICATION`
- Pull request: draft PR #107
- Qualified implementation head: `4f9b6951c30b95b4b1259b570a3cf57a6cbb1191`

## Objective

Phase 4 closes the offline evidence-chain gap between the Phase 3 signed
`RuntimeQualifiedCompilationPlan` and the existing licensed certification plan.
The phase does not execute a simulator and does not change the existing
approved-model licensed-certification path. It creates an immutable,
deterministic and independently recomputable link between the two contracts.

## Implemented Contract

The new module `src/aspenops_nexus/qualified_licensed_link.py` defines:

- schema `aspenops.qualified-licensed-link/v1`;
- fixed execution state `OFFLINE_BINDING_ONLY`;
- fixed real-runtime state `PENDING_REAL_ASPEN_CERTIFICATION`;
- `QualifiedLicensedCertificationLink`;
- strict `from_dict()` parsing with an exact field set;
- canonical serialization and SHA-256 digest generation;
- deterministic current-input comparison through `assert_matches()`;
- `link_qualified_compilation_to_licensed_plan()` as the only supported link
  constructor.

## Bound Identities

The link binds all of the following identities in one immutable document:

1. licensed certification plan canonical SHA-256;
2. licensed case ID;
3. approved full Git commit SHA;
4. simulator backend;
5. approved model SHA-256;
6. approved registry SHA-256;
7. licensed certification bundle signing-key ID;
8. runtime-qualified compilation-plan SHA-256;
9. underlying deterministic base-plan SHA-256;
10. signed runtime-qualification evidence SHA-256;
11. runtime-qualification signing-key ID;
12. capability-profile ID and SHA-256;
13. adapter contract;
14. adapter-code SHA-256;
15. runtime-identity SHA-256;
16. expected native-topology SHA-256;
17. expected layout SHA-256;
18. the complete required passed Golden Case set.

## Fail-Closed Rules

Link construction fails when:

- the licensed backend and capability-profile simulator differ;
- the qualified plan profile ID or profile hash differs from the supplied
  capability profile;
- the signed qualification does not match the capability profile;
- the licensed certification case is absent from the passed Golden Cases;
- any additional required Golden Case is absent;
- the qualified compilation plan is blocked;
- the capability profile is revoked;
- a serialized link contains an unknown or missing field;
- a digest, commit or key ID has an invalid shape;
- a serialized document attempts to change `execution_status` to an executable
  value;
- a serialized document attempts to change the real simulator status.

`assert_matches()` recomputes the complete link from the current licensed plan,
qualified plan and profile. It reports every field whose current value differs
from the stored link, including model, registry, commit, profile, qualification,
adapter, runtime, topology, layout and Golden Case identities.

## Tests Added

`tests/test_qualified_licensed_link.py` covers:

- deterministic construction, digest stability and strict round-trip parsing;
- binding of every load-bearing identity;
- backend substitution;
- profile and adapter-contract substitution;
- missing licensed-case Golden Case evidence;
- missing additional required Golden Cases;
- approved model and approved commit drift;
- malformed digest rejection;
- unknown-field rejection;
- forged executable-state rejection;
- canonical Golden Case ordering.

## Qualification Evidence

Final standard validation on head
`4f9b6951c30b95b4b1259b570a3cf57a6cbb1191`:

- Linux quality, build and smoke job: passed;
- Ruff lint and exact formatter: passed;
- strict mypy: passed;
- Python source compilation and source audit: passed;
- Bandit security analysis: passed;
- dependency audit: passed;
- documentation and artifact governance: passed;
- distributions, portable demo, performance policy, MCP surface, wheel install
  and CLI smoke: passed;
- Python 3.11: 1140 passed, 95.48% branch coverage;
- Python 3.12: 1140 passed, 95.46% branch coverage;
- Python 3.13: 1140 passed, 95.46% branch coverage;
- Python 3.12 reverse and fixed-seed order-independence gate: passed for all
  1140 tests;
- Windows control-plane workflow: passed.

Workflow evidence:

- Linux CI run: `30760860286`;
- Windows run: `30760860277`.

## Explicit Non-Claims

Phase 4 does not claim or provide:

- an Aspen Plus or HYSYS COM adapter;
- native case construction;
- native topology or layout readback;
- native save, close or reopen operations;
- a production runtime-qualification key;
- a production licensed-certification signing key;
- a real Golden Case execution;
- a licensed runtime repeatability run;
- human engineering acceptance;
- `REAL_ASPEN_CERTIFIED` status.

The link is an offline integrity and provenance contract only. It cannot
authorize native execution and cannot transition any certification status.
