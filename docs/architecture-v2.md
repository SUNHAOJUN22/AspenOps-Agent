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
Owner-fenced leased Scheduler ----- Bounded Integrity Bundle Service
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
8. Resident and creating Worker counts are bounded by the configured license
   budget.
9. Cold-state and warm-start evaluations have distinct cache semantics.
10. A durable job mutation requires the current, unexpired lease owner.
11. Archive verification is bounded before decompression or JSON parsing.
12. Mock/Fake tests never represent licensed Aspen physical qualification.

## Evaluation compilation

`EvaluationPlanCompiler` is the single validation and execution compiler. It
resolves writes, outputs, constraints and balances before the simulator is
called. Nodes referenced by several checks are read once and reused in memory.
The plan records declared and unique read counts so COM-call reduction is
observable. Duplicate writes to one resolved semantic target fail during
compilation rather than relying on write order.

Request-size, point-count, semantic-operation and optimization-budget limits are
checked before a Worker or COM server is started. Aspen Plus and HYSYS execution
also fails closed when no allowed model root is configured.

## Persistent execution

`PoolManager` retains `CasePool` instances across jobs. Pools are keyed by
content and compatibility rather than file location. It supports:

- content-based model and registry identity;
- global resident and in-creation license-slot accounting;
- maximum resident cases;
- idle timeout and LRU eviction;
- per-pool serialization of external calls;
- cross-call singleflight for identical cold requests;
- per-CaseKey creation singleflight;
- concurrent startup for different CaseKeys when the license budget allows;
- creation-failure propagation to every waiter;
- Worker generation recycling.

Creation statistics expose active creations, creating Worker count, waiting
callers, failures and peak startup parallelism. A manager closed during startup
waits for the creation outcome and closes an unpublished pool rather than
leaking it.

## Worker IPC and process supervision

A Worker handshake and every result/close response carry an explicit protocol,
request correlation and Worker generation. Malformed payloads are classified as
protocol failures. Startup failures at model copy, Pipe creation, process start,
ready polling or ready decoding close all handles and delete the staged model.
A valid close response is given a graceful-exit window before termination.
Fatal diagnostics are bounded.

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

Every running job is registered as active immediately after `mark_running`, not
only while a CasePool is bound. The watcher therefore renews the lease during
pool creation, simulator execution, result serialization and evidence writing.
Progress, completion, cancellation and failure commits require the current owner
and an unexpired lease. A stale Scheduler cannot overwrite a newer owner's
state. Owner-qualified bundle names prevent two attempts from sharing an output
path; an uncommitted bundle is removed.

## Evidence

A v2 run bundle is a self-checking integrity bundle. Every declared member has
SHA-256 and size metadata. Before any member is read, verification enforces
limits for archive bytes, member count, per-member and total uncompressed size,
compression ratio and supported compression methods. Absolute paths, traversal,
duplicate names and encrypted members are rejected. JSON roots, member
declarations and signing metadata are type-checked before semantic hashes or
signatures are evaluated.

Optional Ed25519 signing proves manifest authenticity only when verified against
a trusted public key. Unsigned bundles are explicitly reported as
`unsigned-valid`, not immutable or tamper-proof.

## Qualification boundary

Portable Linux CI validates orchestration, state machines, numerical ordering,
cache semantics and Mock/Fake backends. Public Windows CI validates process,
IPC, Job Object, scheduler, archive and backend contracts without a licensed
simulator. Real Aspen qualification remains:

```text
PENDING_REAL_ASPEN_CERTIFICATION
```
