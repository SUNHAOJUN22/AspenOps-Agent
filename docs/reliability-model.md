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

## Worker recycle reasons

- `tainted`
- `timeout`
- `protocol_error`
- `crash`
- `age`
- `point_budget`
- `cancel_deadline`

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

Every claim creates a lease. The active Scheduler renews the lease with a
heartbeat. An expired non-cancelled lease returns to `retry_wait` while attempts
remain. A cancelled expired lease becomes `cancelled`.

## Delivery semantics

AspenOps deliberately implements:

```text
at-least-once execution
+ stable point identity
+ idempotent result commit token
+ incremental progress persistence
```

It does not claim exactly-once simulator execution. A service crash can replay a
point; stable request identity and result commits prevent silent duplication in
the durable result.

## Cancellation

- Pending/retry-wait work is cancelled immediately.
- Between points, `cancel_check` prevents additional simulator calls.
- During a blocking simulator call, a deadline watcher force-recycles only the
  active AspenOps Worker generation.
- Completed points and the final cancelled integrity bundle are retained.

## Retry classification

Transient classes such as license waits, startup timeout and transport failure
may retry within a bounded attempt budget. Invalid requests and deterministic
engineering infeasibility are not blindly retried.

## Process ownership

Windows Job Object supervision is the primary process-tree boundary. The
fallback never treats a global process-name/PID difference as ownership. Manual
cleanup requires matching fingerprint and descendant evidence at the moment of
termination, including the second check before a forced kill.

## Cache and singleflight

Cache entries require content/runtime/physical-request identity. Sources are
reported separately:

- `computed`
- `persistent_cache`
- `same_batch_dedup`
- `inflight_singleflight`

Concurrent identical cold single-point calls share one leader execution. Other
external calls are serialized per CasePool so a Pipe or COM Worker cannot be
used concurrently by unrelated callers.

## Unverified boundary

The reliability model is covered by portable Mock/Fake tests. Actual Aspen COM
behavior, license-service failure modes and Windows Job Object containment must
be certified on a licensed self-hosted Windows runner.
