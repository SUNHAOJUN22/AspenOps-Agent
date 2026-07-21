# AspenOps 2.0 Final Implementation Report

## Executive summary

AspenOps 2.0 is a deterministic, semantic control plane for running bounded Aspen
Plus and Aspen HYSYS operations through isolated Worker processes. The release
replaces optimistic simulator status, path-based identity and per-job process
churn with failure-closed convergence, compiled evaluation plans, persistent pools,
durable leases, owner-fenced commits and auditable evidence.

The portable and public-Windows control plane is implemented and heavily tested.
Licensed simulator qualification remains a separate release gate.

## Implemented architecture

```text
CLI / MCP / Python
        |
        v
Policy + resource limits
        |
        v
EvaluationPlanCompiler
        |
        v
Durable leased Scheduler ------ bounded integrity-bundle verifier
        |
        v
PoolManager (content-keyed, license bounded)
        |
        v
CasePool (cache + dedup + singleflight)
        |
        v
Supervised Worker process / one COM STA / private model copy
```

## Correctness changes

- Convergence is an explicit state and missing evidence is `unknown`, not success.
- Aspen Plus and HYSYS require stable idle evidence and declared semantic status.
- The same immutable compilation path is used for dry-run and execution.
- Semantic outputs, constraints and balances share one unique node read plan.
- Duplicate physical write targets are rejected before startup.
- Required outputs must be finite before a point is valid.
- Transport, engine return, convergence, feasibility and balances remain independent
  diagnostics.

## Transaction and recovery changes

- Every original value is captured before the first mutation.
- The node whose write partially fails is included in rollback.
- Numeric rollback verification uses absolute or relative tolerance.
- Failed or uncertain rollback produces `TAINTED`.
- Tainted, timed-out, crashed or protocol-invalid Workers are replaced and their
  generation is incremented.

## Worker and process changes

- Worker startup validates protocol, identity, generation and runtime shape.
- All startup failure paths close Pipe endpoints, stop child processes and remove
  staged directories.
- Result and close messages are correlated by request ID and protocol.
- Valid close acknowledgement is followed by a grace period for backend cleanup;
  termination is only the fallback.
- Fatal diagnostics are bounded.
- Windows Job Objects are the primary process-tree boundary.
- Manual cleanup requires a matching process fingerprint and descendant chain.

## Pool and cache changes

- Pools persist across jobs and are keyed by backend, runtime identity, model digest,
  registry digest and compatibility profile.
- Identical case creation is singleflight; distinct cases can start in parallel.
- Creating Workers count against the global license budget.
- LRU and idle eviction bound resident cases.
- Cache keys are based on content and physical request identity, not display paths.
- Persistent, same-batch and in-flight cache sources are reported separately.
- Corrupt SQLite cache rows are deleted in isolation.
- Batch reads/writes and a bounded memory layer reduce SQLite connection churn.

## Durable scheduling changes

- Jobs use at-least-once delivery, leases, heartbeat and bounded attempts.
- The complete execution window is heartbeated, including startup and evidence
  creation before a CasePool is visible.
- Progress and result commits require the current owner and an unexpired lease.
- A stale Scheduler cannot complete, cancel, retry or fail another owner's attempt.
- Opening a second JobStore does not recover another process's valid lease.
- Only expired or truly unleased records are recovered.
- Final-attempt lease expiry transitions to `dead_letter`.
- Cancellation racing with result commit is finalized immediately as cancelled.
- Bundle paths include the Scheduler owner, and unadopted duplicate or stale bundles
  are deleted.

## Optimization changes

- Differential evolution evaluates the initial population and each trial population
  as a batch.
- Continuous, integer, categorical and ordinal variables are supported.
- The implementation enforces a deterministic seed, hard call budget and bounded
  problem dimensions.
- Feasibility uses Deb ordering; multi-objective output includes a Pareto archive.
- Checkpoints are atomically replaced and restricted to approved paths.
- Missing/non-finite simulator outputs receive direction-correct finite penalties.
- CLI, MCP and durable Scheduler use the same optimization implementation.

## Evidence changes

- A v2 bundle records SHA-256 and size for every declared member.
- Optional Ed25519 signing covers the canonical manifest.
- Unsigned bundles are self-checking only and are explicitly labeled unsigned.
- Verification has bounded archive size, member count, member size, total expanded
  size and compression ratio.
- Unsafe paths, duplicate or encrypted members and unsupported compression fail
  closed.
- JSON roots and signing metadata are type checked before semantic verification.
- Members are read in bounded chunks.

## Agent and compatibility surface

Existing commands remain available, and `aspenops optimize` is added. The MCP
server exposes 14 bounded tools through `AspenOpsTools`; transport registration and
business logic are tested independently.

The legacy `cache_hit` field remains for compatibility and is derived from the new
`cache_source` value. Legacy unsigned v1 bundles remain verifiable and are labeled
as legacy unsigned.

## Verification status

Portable and public Windows evidence is summarized in `docs/quality-report.md`.
The latest verified portable matrix contains 424 passing tests with a 94% combined
coverage floor. Full performance evidence is produced by
`.github/workflows/generate-performance-evidence.yml` and is explicitly scoped to
Mock orchestration.

## Known boundary and next release gate

The following remains intentionally unresolved by portable CI:

```text
PENDING_REAL_ASPEN_CERTIFICATION
```

The final gate must execute real Aspen Plus and HYSYS models on a licensed,
self-hosted Windows machine and verify release identity, convergence, process
ownership, timeout cleanup, cancellation, balances, constraints, repeatability,
license-slot scaling and signed evidence.
