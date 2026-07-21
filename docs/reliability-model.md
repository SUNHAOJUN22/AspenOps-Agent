# AspenOps v2 Reliability Model

## Validity gate

A point is valid only when all required gates pass:

```text
transport_ok
AND engine_returned
AND convergence_state == converged
AND constraints_passed
AND balances_passed
AND required_outputs_finite
```

`unknown`, missing evidence, a status-read exception, or an unstable idle state
cannot produce a valid point.

## Write transaction states

```text
PREPARED -> APPLYING -> VERIFIED
                   \-> ROLLED_BACK
                   \-> ROLLBACK_FAILED -> TAINTED
```

All original values are captured before mutation. The currently failing node is
included in rollback. Numeric verification uses absolute-or-relative tolerance;
strings and booleans use exact equality. A `TAINTED` Worker is recycled.

## Worker protocol and recycle states

Worker startup validates protocol, Worker ID, generation and runtime identity.
Every evaluation response validates protocol, request correlation, response kind
and result shape. Copy, Pipe, process-start, ready-poll and ready-receive failures
close connections, terminate the process when necessary and remove the staged
model. A valid close acknowledgement receives a graceful-exit window; only a
non-exiting Worker is terminated.

Recycle reasons include:

- `tainted`
- `timeout`
- `protocol_error`
- `crash`
- `age`
- `point_budget`
- `cancel_deadline`
- `lease_lost`

A recycle event records the reason and old/new generations. Expected-handle
checks prevent an older dispatcher from recycling a newer generation.

## Job states

```text
pending -> claimed -> running -> completed
                   |        \-> cancelling -> cancelled
                   |        \-> retry_wait -> claimed
                   |        \-> failed
                   |        \-> dead_letter
```

Every claim creates a lease. After `mark_running`, the job is registered as
active for its entire execution window, including CasePool creation, simulator
execution, result serialization and evidence writing. The watcher renews every
active job, not only jobs with an attached pool.

An expired non-cancelled lease returns to `retry_wait` while attempts remain and
becomes `dead_letter` after the final attempt. A cancelled expired lease becomes
`cancelled`. A cancellation deadline without an active pool remains pending;
it is not cleared until the pool can be recycled or cooperative cancellation
finishes.

## Owner fencing and delivery semantics

AspenOps deliberately implements:

```text
at-least-once execution
+ stable point identity
+ unexpired lease-owner fencing
+ idempotent result commit token
+ incremental progress persistence
```

Progress, completion, cancellation, retry and failure updates require the
current owner and an unexpired lease. A stale Scheduler cannot overwrite a
newer's progress or result. Repeating the same completed commit token remains
idempotent. Attempt history is retained in the append-only event table.

The system does not claim exactly-once simulator execution. A service crash can
replay a point; stable request identity, owner fencing and result commit tokens
prevent silent duplication in the durable result.

## Cancellation

- Pending/retry-wait work is cancelled immediately.
- Between points, `cancel_check` prevents additional simulator calls.
- During a blocking simulator call, a deadline watcher force-recycles only the
  active AspenOps Worker generation owned by the current Scheduler.
- A lost heartbeat recycles an attached pool and unregisters the active job.
- Completed points and a successfully committed cancelled integrity bundle are
  retained.
- Bundles use owner-qualified names; an attempt that loses its lease deletes an
  uncommitted bundle.

## Retry classification

Transient classes such as license waits, startup timeout and transport failure
may retry within a bounded attempt budget. Invalid requests and deterministic
engineering infeasibility are not blindly retried.

## Process ownership

Windows Job Object supervision is the primary process-tree boundary. The
fallback never treats a global process-name/PID difference as ownership. Manual
cleanup requires matching fingerprint and descendant evidence at the moment of
termination, including the second check before a forced kill.

## Pool creation and license accounting

Pool creation uses per-CaseKey singleflight. Identical concurrent requests wait
for one startup and receive the same outcome. Different CaseKeys may start in
parallel when the license budget allows. Both resident Workers and Workers under
creation count against `license_slots`.

Creation failure wakes every waiter with the same error. Closing a manager while
a pool is starting waits for the startup outcome and closes any unpublished
pool. Idle eviction cannot remove a creating or leased pool. Metrics expose
creation count, waiting callers, failures and peak startup parallelism.

## Cache and singleflight

Cache entries require content/runtime/physical-request identity. Sources are
reported separately:

- `computed`
- `persistent_cache`
- `same_batch_dedup`
- `inflight_singleflight`

Concurrent identical cold single-point calls share one leader execution. Other
external calls are serialized per CasePool so a Pipe or COM Worker cannot be
used concurrently by unrelated callers. Corrupt cache entries are isolated and
removed instead of failing the entire batch.

## Evidence verification

The v2 bundle verifier fails before extraction when archive byte size, member
count, member size, total uncompressed size or compression ratio exceeds the
configured bound. It rejects traversal, absolute or drive paths, backslashes,
NULs, duplicate names, encryption and unsupported compression methods. Members
are streamed with a byte limit. JSON root types, member hashes/sizes and signing
metadata are validated before semantic acceptance.

Unsigned bundles prove only self-consistency. `signed-valid` additionally proves
that the canonical manifest verifies against the supplied trusted Ed25519 public
key.

## Unverified boundary

The reliability model is covered by portable Mock/Fake tests and public Windows
control-plane contracts. Actual Aspen COM behavior, license-service failure
modes and physical model correctness must be certified on a licensed
self-hosted Windows runner:

```text
PENDING_REAL_ASPEN_CERTIFICATION
```
