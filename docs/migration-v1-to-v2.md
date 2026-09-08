# Migrating AspenOps v1 to v2

## Compatibility policy

Existing batch JSON, CLI commands and narrow MCP tools remain supported unless a
v2 safety rule requires explicit evidence. The largest behavioral change is
that ambiguous simulator state now fails closed.

## Result changes

`EvaluationResult` adds `cache_source` while retaining `cache_hit` for
compatibility.

```text
computed
persistent_cache
same_batch_dedup
inflight_singleflight
```

Consumers should prefer `cache_source`. `cache_hit` remains true for every
non-computed source.

Worker diagnostics can include:

```json
{
  "worker_recycled": true,
  "recycle_reason": "tainted",
  "old_generation": 0,
  "new_generation": 1
}
```

## Convergence behavior

v1 releases could infer success when status evidence was absent. v2 requires an
explicit `convergence_state == "converged"`. HYSYS production registries must
provide at least one project-owned convergence Spreadsheet semantic variable.

Requests that previously returned success from implicit idle state may now
return `simulator_not_converged:unknown`. This is an intentional safety change.

## Persistent service behavior

Background and MCP service executions now retain CasePools across jobs. Review:

```text
ASPENOPS_LICENSE_SLOTS
ASPENOPS_MAX_WORKERS
ASPENOPS_MAX_RESIDENT_CASES
ASPENOPS_POOL_IDLE_TIMEOUT_S
ASPENOPS_JOB_LEASE_S
ASPENOPS_CANCELLATION_GRACE_S
ASPENOPS_JOB_MAX_ATTEMPTS
```

A service restart may replay leased work under at-least-once semantics. Use
request hashes and result commit tokens for reconciliation.

## Job states

Clients that assumed only `pending/running/completed/failed` must accept:

```text
claimed
cancelling
cancelled
retry_wait
dead_letter
```

`job_result` can return retained partial results for cancelled work.

## Evidence bundles

v2 writes `aspenops.integrity-bundle/v2`. Unsigned valid bundles report
`unsigned-valid`. Optional Ed25519 signatures report `signed-valid` only when a
trusted public key is supplied. Do not describe unsigned bundles as immutable or
tamper-proof.

Legacy v1 bundles remain readable as `legacy-unsigned-valid` when their internal
request/result hashes match.

## Optimization

A v2 optimization document adds an `optimization` object to an otherwise valid
batch request. Existing `differential_evolution()` remains available as a
compatibility wrapper, while production workflows should use the batch-oriented
optimization interfaces.

## Deployment sequence

1. Run portable CI and dry-run existing requests.
2. Update HYSYS registries with convergence nodes.
3. Start with one license slot and one Worker.
4. Verify cancelled/restarted job handling.
5. Re-certify an approved Aspen case on Windows.
6. Increase Worker count only after measuring throughput, memory and license
   behavior.
