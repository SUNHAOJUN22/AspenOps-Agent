# AspenOps V3 Implementation Report

## Execution identity

- Repository: `SUNHAOJUN22/AspenOps-Agent`
- Frozen base commit: `0d240f16c3706705f4a304f09eac22ceaf301631`
- Working branch: `feature/aspenops-natural-language-flowsheet-v3`
- Draft pull request: `#103`
- Source task: AspenOps-Agent 3.0 terminal modification package

## Current phase

This report covers **Phase 0 only**. The branch is deliberately fail-closed and must not be represented as a completed natural-language Aspen V15 flowsheet builder.

Current admissible status before the final CI and reverse-audit gates complete:

`FAIL_CLOSED`

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
- Real simulator workers now require successful Windows Job Object supervision before COM is opened.
- Normal shutdown, startup failure, hard abort and recycling remove the private staging directory.

### Pool and cache fencing

- `CasePool` binds all Workers and recycled Workers to one model/registry digest pair.
- `PoolManager` verifies that a newly created `CasePool` still matches the lookup digests captured before pool construction.
- Cache identity includes verified model and registry digests and stable runtime identity.
- A result is cacheable only when its execution identity matches the pool identity.

### Result and evidence identity

- Every Worker result receives a parent-verified `execution_identity`.
- Runtime-generated bundles use `aspenops.integrity-bundle/v3`.
- V3 manifests bind model digest, registry digest, backend and stable runtime-identity digest.
- V3 verification compares the result documents with the manifest execution identity.
- Bundle writing rejects mixed execution identities.
- Legacy callers without Worker identity continue to produce a V2 self-checking bundle; V2 is not represented as proof of the actual simulator-opened bytes.

### Access and transaction contracts

- Read, constraint and balance plans reject `access="write"` nodes before Worker/COM execution.
- All backend writes now require read-after-write verification.
- Boolean and string values require exact type/value equality.
- Numeric values use bounded absolute/relative comparison.
- Any failed write verification initiates rollback.
- Failed rollback verification marks the transaction tainted so the Worker is recycled.

### Strict serialization and signatures

- Evidence JSON rejects duplicate keys and non-finite constants.
- CLI request loading rejects duplicate keys and `NaN`/`Infinity`.
- Ed25519 key IDs are fixed public-key fingerprints.
- Human-readable arbitrary key IDs are rejected.
- CLI `verify-bundle` accepts an optional trusted public key.
- MCP accepts only a 32-character key fingerprint and resolves it inside an administrator-configured absolute trust directory.
- MCP does not accept arbitrary public-key file paths.
- MCP runtime compatibility is enforced as `mcp>=1.9,<2` rather than any 1.x release.

### CLI corrections

- `aspenops verify-bundle` can verify signed ordinary bundles with `--public-key`.
- Optimization output defaults to `settings.state_dir` when `--output` is omitted.

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

## CI execution history

### Round 1

- Dependency lock and audit: passed.
- Ruff: failed on seven formatting/style findings in newly added code.
- Findings were corrected without lowering any rule.

### Round 2

- Ruff rules: passed.
- Ruff formatting: identified two files requiring formatter-normalized layout.
- The repository-pinned Ruff version formatted those files through a one-time workflow.
- The workflow deleted itself in the same formatting commit; it is not present in the branch.

### Current round

A fresh complete Linux and Windows PR run is required after the report commits. Final pass/fail counts will be recorded only from the completed GitHub Actions runs.

## Not yet implemented

The following terminal-task items remain outside this Phase 0 PR and must not be claimed as complete:

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

## Compatibility decisions

- The existing 14-tool MCP surface is retained in Phase 0; a future high-level design surface must be introduced only after deterministic IR and engineering rules exist.
- V2 evidence bundles remain readable for compatibility but carry an explicit weaker boundary.
- No external repository source has been copied.
- No source Aspen model is overwritten.
- The branch remains a draft PR and is not merged automatically.

## Phase 0 exit criteria

Phase 0 may move from `FAIL_CLOSED` to `PASS_CONTROL_PLANE` only when all of the following are evidenced on the final branch head:

- Ruff and Ruff format pass;
- strict mypy passes;
- Bandit policy passes;
- full Python 3.11, 3.12 and 3.13 suites pass with required branch coverage;
- test-order gate passes;
- build and Wheel smoke pass;
- MCP surface check passes;
- Windows control-plane contracts pass;
- no temporary workflow remains;
- reverse audit contains no unresolved Phase 0 software blocker.

Even after those gates, real Aspen status remains `PENDING_REAL_ASPEN_CERTIFICATION`.
