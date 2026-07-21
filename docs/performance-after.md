# Portable performance after AspenOps v2 changes

Candidate revision: `agent/aspenops-v2-reliability-performance`.

These measurements characterize portable orchestration only. They are not Aspen Plus/HYSYS performance or physical-validation evidence.

| Scenario | Points | Workers | Duplicate ratio | Cache | Trials | Throughput | CV | Throughput change | P95 change | Stability | Assessment |
|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---|---|
| cache | 100 | 4 | 0% | cold | 3 | 151.820 | 0.01% | +11.15% | +0.46% | stable | none |
| cache | 100 | 4 | 0% | warm | 3 | 17334.613 | 0.30% | +1977.22% | +0.41% | stable | none |
| duplicate_ratio | 100 | 4 | 0% | cold | 3 | 151.715 | 0.06% | +11.51% | +0.44% | stable | none |
| duplicate_ratio | 100 | 4 | 25% | cold | 3 | 198.910 | 0.10% | +12.64% | +0.39% | stable | none |
| duplicate_ratio | 100 | 4 | 75% | cold | 3 | 525.721 | 0.21% | +23.08% | +0.36% | stable | none |
| nonconvergence | 20 | 2 | 0% | cold | 3 | 76.781 | 0.24% | +2.10% | +0.25% | stable | none |
| worker_matrix | 1 | 1 | 0% | cold | 3 | 34.066 | 0.80% | -1.63% | +0.42% | startup-sensitive | none |
| worker_matrix | 1 | 2 | 0% | cold | 3 | 34.361 | 0.15% | -1.27% | +0.44% | startup-sensitive | none |
| worker_matrix | 1 | 4 | 0% | cold | 3 | 34.103 | 0.04% | -2.56% | +0.57% | startup-sensitive | none |
| worker_matrix | 1 | 8 | 0% | cold | 3 | 34.155 | 0.90% | -2.33% | +0.33% | startup-sensitive | none |
| worker_matrix | 10 | 1 | 0% | cold | 3 | 38.122 | 0.06% | +6.80% | +0.45% | stable | none |
| worker_matrix | 10 | 2 | 0% | cold | 3 | 74.998 | 0.14% | +8.78% | +0.29% | stable | none |
| worker_matrix | 10 | 4 | 0% | cold | 3 | 121.564 | 0.15% | +9.38% | +0.41% | stable | none |
| worker_matrix | 10 | 8 | 0% | cold | 3 | 178.431 | 0.36% | +10.77% | +0.40% | startup-sensitive | none |
| worker_matrix | 100 | 1 | 0% | cold | 3 | 38.549 | 0.10% | +9.53% | +0.35% | stable | none |
| worker_matrix | 100 | 2 | 0% | cold | 3 | 76.839 | 0.14% | +9.70% | +0.19% | stable | none |
| worker_matrix | 100 | 4 | 0% | cold | 3 | 151.905 | 0.03% | +11.94% | +0.40% | stable | none |
| worker_matrix | 100 | 8 | 0% | cold | 3 | 287.048 | 0.17% | +16.02% | +0.35% | stable | none |
| worker_matrix | 1000 | 1 | 0% | cold | 3 | 37.884 | 0.18% | +6.49% | +0.36% | stable | none |
| worker_matrix | 1000 | 2 | 0% | cold | 3 | 75.235 | 0.14% | +7.95% | +0.41% | stable | none |
| worker_matrix | 1000 | 4 | 0% | cold | 3 | 146.062 | 0.11% | +9.47% | +0.36% | stable | none |
| worker_matrix | 1000 | 8 | 0% | cold | 3 | 300.792 | 0.12% | +15.88% | +0.27% | stable | none |

## Regression gate

Stable regressions above 5%: `0`.
Noise-sensitive observations above 5%: `0`.

Stable regressions fail the performance workflow when `--fail-on-stable-regression` is enabled. Startup-sensitive, high-CV, or insufficient-trial observations remain visible but are not treated as steady-state evidence.

### Stable regressions

None.

### Noise-sensitive observations

None.

## Persistent sequential-job execution

```json
{
  "scenario": "ten_sequential_jobs",
  "available": true,
  "elapsed_s": 0.3606278280000197,
  "pool_stats": {
    "resident_cases": 1,
    "resident_workers": 2,
    "license_slots": 2,
    "created_pools": 1,
    "reused_leases": 9,
    "evicted_pools": 0,
    "creating_cases": 0,
    "creating_workers": 0,
    "creation_waiters": 0,
    "creation_failures": 0,
    "startup_parallelism_peak": 1,
    "cases": [
      {
        "backend": "mock",
        "runtime_identity_hash": "29ae40fd230d8b31b4412f9a256b00e07242b486ba42ff6d30d80740c5530239",
        "model_digest": "81014103f90d552706a99a94ffc250a0952a8d14f04bc5288215963e6b7a6cbc",
        "registry_digest": "92e384ea697639f2ac8126ad70f93c423712d5ff9074d0c6d4ca0d17d67e7366",
        "workers": 2,
        "leases": 0
      }
    ]
  }
}
```

## Interpretation boundary

A positive portable throughput change is evidence about Python orchestration, deduplication, cache and persistent Worker reuse only. Licensed Aspen performance must be measured separately on an approved Windows host.
