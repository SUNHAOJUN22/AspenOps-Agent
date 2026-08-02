# AspenOps V3 Implementation Report

## Execution identity

- Repository: `SUNHAOJUN22/AspenOps-Agent`
- Frozen base commit: `0d240f16c3706705f4a304f09eac22ceaf301631`
- Phase 0 validated code head: `8ad74ec98444060263b47a100dcb0a07630b5e53`
- Working branch: `feature/aspenops-natural-language-flowsheet-v3`
- Draft pull request: `#103`
- Source task: AspenOps-Agent 3.0 terminal modification package

## Current phase and admissible status

This report covers the implemented **Phase 0 control-plane scope only**. It must not be represented as a completed natural-language Aspen V15 flowsheet builder.

Current admissible software status:

`PASS_CONTROL_PLANE`

This means the implemented portable and Windows control-plane contracts passed their governed CI gates. It does **not** mean that flowsheet generation, Aspen Plus V15 compilation, HYSYS V15 compilation, engineering acceptance or licensed simulator physics have passed.

Real licensed simulator status remains:

`PENDING_REAL_ASPEN_CERTIFICATION`

## Implemented Phase 0 changes

### Immutable execution artifacts

- Model and semantic registry are copied together into each Worker's private staging directory.
- Parent and child independently compute SHA-256 digests.
- Worker startup rejects a model or registry that changed between approval and staging.
- Worker startup rejects a staged file that changes while being loaded or opened.
- Worker `ready` messages include the staged paths and artifact digests.
- Parent-side startup validates the returned artifact identity.
- Real simulator workers require successful Windows Job Object supervision before COM is opened.
- Normal shutdown, startup failure, hard abort and recycling remove the private staging directory.

### Pool and cache fencing

- `CasePool` binds all live Workers and recycled Workers to one model/registry digest pair.
- `PoolManager` verifies that a newly created `CasePool` still matches the lookup digests captured before pool construction.
- Cache identity includes verified model and registry digests and stable runtime identity.
- The live dispatch path writes parent-trusted execution identity into each result before cacheability is evaluated.
- Results carrying an execution identity are cacheable only when it matches the pool identity.

### Result and evidence identity

- Every live Worker result receives a parent-verified `execution_identity`.
- Runtime-generated bundles use `aspenops.integrity-bundle/v3`.
- V3 manifests bind model digest, registry digest, backend and stable runtime-identity digest.
- V3 verification compares the result documents with the manifest execution identity.
- Bundle writing rejects mixed execution identities.
- Legacy callers without Worker identity continue to produce a V2 self-checking bundle; V2 is not represented as proof of the actual simulator-opened bytes.

### Access and transaction contracts

- Read, constraint and balance plans reject `access="write"` nodes before Worker/COM execution.
- All backend writes require read-after-write verification.
- Boolean and string values require exact type/value equality.
- Numeric values use bounded absolute/relative comparison.
- Any failed write verification initiates rollback.
- Failed rollback verification marks the transaction tainted so the Worker is recycled.

### Strict serialization and signatures

- Evidence JSON rejects duplicate keys and non-finite constants.
- CLI request loading rejects duplicate keys and `NaN`/`Infinity`.
- Ed25519 key IDs written by AspenOps are fixed public-key fingerprints.
- A caller cannot substitute an unrelated human-readable ID for the signing-key fingerprint.
- CLI `verify-bundle` accepts an optional trusted public key.
- MCP accepts only a 32-character key fingerprint and resolves it inside an administrator-configured absolute trust directory.
- MCP does not accept arbitrary public-key file paths.
- MCP runtime compatibility is enforced as `mcp>=1.9,<2`, while retaining the existing public compatibility constant and diagnostics.

### CLI corrections

- `aspenops verify-bundle` can verify signed ordinary bundles with `--public-key`.
- The historical optimize parser default is retained for compatibility, but execution maps that default into governed `settings.state_dir`.
- Lightweight bootstrap and full CLI surfaces remain synchronized.

## Added regression coverage

New tests exercise:

- write-only node reads through outputs, constraints and balances;
- silently ignored numeric and string writes;
- Boolean-to-integer coercion;
- rollback success and tainted rollback failure;
- model/registry source modification after digest capture;
- forged Worker-ready digests;
- private artifact cleanup;
- PoolManager lookup-digest drift;
- source-file replacement after execution but before bundle verification;
- V3 manifest/result execution-identity mismatch;
- mixed runtime identities in one bundle;
- non-finite evidence JSON;
- CLI duplicate/non-finite request JSON;
- MCP SDK lower/upper version boundaries;
- administrator trust-store containment and signed-bundle verification.

## Final CI evidence for the validated code head

GitHub Actions PR validation completed successfully on the Phase 0 code head.

### Python matrix

| Runtime | Result | Branch coverage |
|---|---:|---:|
| Python 3.11 | 947 passed | 95.22% |
| Python 3.12 | 947 passed | 95.24% |
| Python 3.13 | 947 passed | 95.24% |

The Python 3.12 complete-suite order-independence gate passed in both reverse order and the fixed seeded order.

### Quality, build and packaging gates

The following completed successfully:

- frozen lockfile verification and dependency synchronization;
- locked dependency audits for Linux and Windows targets across supported Python versions;
- Ruff and Ruff format;
- strict mypy;
- Python source compilation;
- governed source-tree audit;
- high-confidence/high-severity Bandit policy;
- documentation, artifact, dashboard and Process IR contracts;
- Process IR canonical validation and rendering;
- source distribution and wheel build;
- portable Mock demo;
- durable CLI lifecycle smoke;
- committed performance policy;
- MCP surface check;
- clean wheel installation, dependency check and CLI smoke.

### Windows control-plane gate

The Windows 2025 contract workflow completed successfully, including:

- PowerShell parser and bootstrap contracts;
- Ruff, formatter and strict mypy;
- Python compilation and source audit;
- Windows Job Object, process ownership, scheduler, archive, backend, convergence, certification, Process IR and workflow-governance tests;
- Windows CLI smoke.

These public Windows tests qualify the control plane, not commercial Aspen physics.

## Not yet implemented

The following terminal-task items remain outside this Phase 0 control-plane PR and must not be claimed as complete:

- ProcessRequirementDocument schema;
- ProcessDesignIR v2;
- engineering rule engine and equipment contracts;
- SFILES2 import/export;
- plant-template catalogue;
- Aspen Plus V15 deterministic flowsheet compiler;
- HYSYS V15 deterministic flowsheet compiler;
- native simulator topology readback and graph-hash comparison;
- deterministic native flowsheet layout;
- component, elemental and energy balance engine for generated flowsheets;
- staged convergence orchestrator;
- bounded IR repair patches;
- natural-language design tools;
- licensed Aspen Plus V15 and HYSYS V15 golden-case execution.

## Remaining Phase 0 follow-up work

The implemented control-plane gate passes, but the wider terminal-task Phase 0 backlog still contains:

1. consolidate the Aspen Plus base/strict adapter split into one strict implementation;
2. migrate backend polling environment variables into strictly validated `Settings` fields;
3. bind licensed-certification preflight and execution through one persistent approved snapshot object;
4. add Windows staging ACL/read-only hardening in addition to digest boundary checks.

These items prevent a claim that the entire AspenOps V3 terminal package is complete. They do not invalidate the narrower `PASS_CONTROL_PLANE` result demonstrated by the completed CI matrix.

## Compatibility decisions

- The existing 14-tool MCP surface is retained in Phase 0; a future high-level design surface must be introduced only after deterministic IR and engineering rules exist.
- V2 evidence bundles remain readable for compatibility but carry an explicit weaker boundary.
- No external repository source has been copied.
- No source Aspen model is overwritten.
- The branch remains a draft PR and is not merged automatically.

## Final boundary

`PASS_CONTROL_PLANE` is the highest supported conclusion for this implementation stage.

The project must remain `PENDING_REAL_ASPEN_CERTIFICATION` until the separately scoped Aspen Plus/HYSYS V15 adapters, native topology roundtrip, Golden Cases, licensed Windows execution and human engineering acceptance have all been completed with signed evidence.
