# CLOSED LOOP VALIDATION — Research P0

**Decision: FAIL**

Every listed gate must return zero. Missing evidence is not a pass.

| Gate | Result | Exit code |
|---|---:|---:|
| `lock-check` | PASS | 0 |
| `sync-312` | PASS | 0 |
| `dependency-audit` | PASS | 0 |
| `ruff` | FAIL | 1 |
| `ruff-format` | FAIL | 1 |
| `mypy` | FAIL | 1 |
| `compileall` | PASS | 0 |
| `source-audit` | PASS | 0 |
| `bandit` | PASS | 0 |
| `p0-contract` | PASS | 0 |
| `full-312` | PASS | 0 |
| `order-312` | PASS | 0 |
| `full-311` | PASS | 0 |
| `full-313` | PASS | 0 |
| `restore-312` | PASS | 0 |
| `process-ir` | PASS | 0 |
| `mcp` | PASS | 0 |
| `build` | PASS | 0 |
| `wheel-metadata` | PASS | 0 |
| `demo` | PASS | 0 |
| `wheel-smoke` | PASS | 0 |

Boundary: P0 validates immutable research manifests and scientific evidence relationships only. It does not open Aspen, estimate parameters, run dynamic studies, or train machine-learning models.
