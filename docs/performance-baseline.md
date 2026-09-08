# Portable performance baseline

Baseline revision: `main`.

These measurements characterize portable orchestration only. They are not Aspen Plus/HYSYS performance or physical-validation evidence.

| Scenario | Points | Workers | Duplicate ratio | Cache | Trials | Throughput (points/s) | Throughput CV | P95 (s) | RSS delta | Stability |
|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---|
| worker_matrix | 1 | 1 | 0% | cold | 3 | 34.632 | 1.49% | 0.025220 | 16384 | startup-sensitive |
| worker_matrix | 1 | 2 | 0% | cold | 3 | 34.801 | 0.95% | 0.025287 | 0 | startup-sensitive |
| worker_matrix | 1 | 4 | 0% | cold | 3 | 35.000 | 0.19% | 0.025253 | 0 | startup-sensitive |
| worker_matrix | 1 | 8 | 0% | cold | 3 | 34.971 | 0.08% | 0.025272 | 0 | startup-sensitive |
| worker_matrix | 10 | 1 | 0% | cold | 3 | 35.694 | 0.42% | 0.025237 | 8192 | stable |
| worker_matrix | 10 | 2 | 0% | cold | 3 | 68.947 | 0.13% | 0.025271 | 12288 | stable |
| worker_matrix | 10 | 4 | 0% | cold | 3 | 111.137 | 0.22% | 0.025353 | 90112 | stable |
| worker_matrix | 10 | 8 | 0% | cold | 3 | 161.088 | 0.27% | 0.025326 | 45056 | startup-sensitive |
| worker_matrix | 100 | 1 | 0% | cold | 3 | 35.196 | 3.79% | 0.025247 | 81920 | stable |
| worker_matrix | 100 | 2 | 0% | cold | 3 | 70.048 | 0.27% | 0.025254 | 45056 | stable |
| worker_matrix | 100 | 4 | 0% | cold | 3 | 135.705 | 1.14% | 0.025250 | 32768 | stable |
| worker_matrix | 100 | 8 | 0% | cold | 3 | 247.409 | 0.08% | 0.025287 | 8192 | stable |
| worker_matrix | 1000 | 1 | 0% | cold | 3 | 35.575 | 0.22% | 0.025253 | 536576 | stable |
| worker_matrix | 1000 | 2 | 0% | cold | 3 | 69.694 | 0.21% | 0.025243 | 32768 | stable |
| worker_matrix | 1000 | 4 | 0% | cold | 3 | 133.429 | 0.04% | 0.025249 | 12288 | stable |
| worker_matrix | 1000 | 8 | 0% | cold | 3 | 259.569 | 0.30% | 0.025256 | 0 | stable |
| duplicate_ratio | 100 | 4 | 0% | cold | 3 | 136.055 | 0.08% | 0.025259 | 0 | stable |
| duplicate_ratio | 100 | 4 | 25% | cold | 3 | 176.596 | 0.07% | 0.025276 | 0 | stable |
| duplicate_ratio | 100 | 4 | 75% | cold | 3 | 427.121 | 0.08% | 0.025298 | 0 | stable |
| cache | 100 | 4 | 0% | cold | 3 | 136.590 | 0.28% | 0.025257 | 0 | stable |
| cache | 100 | 4 | 0% | warm | 3 | 834.510 | 4.20% | 0.025248 | 0 | stable |
| nonconvergence | 20 | 2 | 0% | cold | 3 | 75.201 | 0.09% | 0.025268 | 0 | stable |
