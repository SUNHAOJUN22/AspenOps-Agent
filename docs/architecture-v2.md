# AspenOps v2 Architecture

## Purpose

AspenOps v2 is a deterministic control plane between an AI/coding client and a
stateful Aspen Plus or Aspen HYSYS simulator. It does not expose unrestricted
COM, shell, Python, VBA, or raw Tree Path execution.

```text
MCP / CLI / Python client
          |
          v
Policy + EvaluationPlanCompiler
          |
          v
Leased Job Scheduler ------ Integrity Bundle Service
          |
          v
Persistent PoolManager
  CaseKey = backend + runtime + model digest + registry digest + profile
          |
          v
CasePool -> supervised Worker processes -> one COM STA per Worker
```

## Non-negotiable invariants

1. A COM object belongs to one spawned Worker process and one STA apartment.
2. COM objects never cross a thread, pipe, queue, or public data model.
3. A client writes semantic variables declared by a case-owned registry.
4. Every Worker opens a private staged model copy.
5. Unknown convergence evidence fails closed.
6. Transport, engine return, convergence, feasibility and balances remain
   separate states.
7. A Worker with unverified rollback, protocol state, timeout, or crash is
   recycled before receiving another point.
8. Resident Worker count is bounded by the configured license budget.
9. Cold-state and warm-start evaluations have distinct cache semantics.
10. Mock/Fake tests never represent licensed Aspen physical qualification.

## Evaluation compilation

`EvaluationPlanCompiler` is the single validation and execution compiler. It
resolves writes, outputs, constraints and balances before the simulator is
called. Nodes referenced by several checks are read once and reused in memory.
The plan records declared and unique read counts so COM-call reduction is
observable.

## Persistent execution

`PoolManager` retains `CasePool` instances across jobs. Pools are keyed by
content and compatibility rather than file location. It supports:

- content-based model and registry identity;
- global resident license-slot accounting;
- maximum resident cases;
- idle timeout and LRU eviction;
- per-pool serialization of external calls;
- cross-call singleflight for identical cold requests;
- Worker generation recycling.

## Process supervision

On Windows, a Worker attempts to join a Job Object configured with
`KILL_ON_JOB_CLOSE` before COM initialization. If Job Object supervision is not
available, Aspen Plus cleanup requires a matching PID, process creation time,
executable path and verified descendant chain. An unproven process is not
terminated.

## Durable scheduling

Jobs use at-least-once execution with idempotent result commits. SQLite records
leases, heartbeat, attempt count, cancellation deadline, last completed point,
commit token, error class and an append-only event stream. The system does not
claim exactly-once simulator execution.

## Evidence

A v2 run bundle is a self-checking integrity bundle. Every declared member has
SHA-256 and size metadata. Optional Ed25519 signing proves manifest
Authenticity only when verified against a trusted public key. Unsigned bundles
are explicitly reported as `unsigned-valid`, not immutable or tamper-proof.

## Qualification boundary

Portable Linux CI validates orchestration, state machines, numerical ordering,
cache semantics and Fake/Mock backends. Real Aspen qualification remains:

```text
PENDING_REAL_ASPEN_CERTIFICATION
```
