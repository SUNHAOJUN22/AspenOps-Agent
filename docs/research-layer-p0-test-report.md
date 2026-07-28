# AspenOps Research Platform P0 Test Report

- Overall: **FAIL**
- Qualified source: `28abeb1f5a79e4e4e1cbe859b7762f24710769e5`
- P0 tests: `68`
- Python 3.12 full tests: `877`

| Gate | Result | Exit code |
|---|---:|---:|
| `lock-check` | PASS | 0 |
| `sync-312` | PASS | 0 |
| `dependency-audit` | PASS | 0 |
| `ruff-fix` | PASS | 0 |
| `format-fix` | PASS | 0 |
| `ruff` | PASS | 0 |
| `ruff-format` | PASS | 0 |
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

## Boundary

P0 validates immutable research manifests and scientific evidence relationships only. It does not open Aspen, estimate parameters, run dynamic studies, or train machine-learning models.
