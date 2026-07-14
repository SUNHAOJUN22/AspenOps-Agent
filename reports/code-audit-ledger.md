# AspenOps 1.4 Mathematical and Database Audit Ledger

> Status: **IN PROGRESS**  
> Base: `8283744093a210c07da16ffe006968776dff9547` (`main`)  
> Target branch: `agent/aspenops-1.4-mathematical-database-hardening`  
> Real Aspen physical certification: **BLOCKED**

## Truthfulness boundary

Unread files are not marked reviewed. Linter output is separate from manual logic review. Mock/Fake COM evidence is not real Aspen evidence. `Run2()` returning is not convergence, and convergence is not physical credibility.

## Task status

| Task | Status | Evidence |
|---|---|---|
| 00 Execution discipline | COMPLETE | Explicit truth boundaries in baseline and ledger |
| 01 Remote baseline | COMPLETE WITH CONNECTOR LIMITATION | `reports/repository-baseline.json`; complete tags/releases listing unavailable through the connected action surface |
| 02 Audit ledger | INITIALIZED | JSON and Markdown ledgers; inventory remains partial |
| 03 File inventory | IN PROGRESS | Current canonical package is `src/aspenops_nexus`; rejected incomplete 1.2 package migration documented |
| 04 Static logic audit | IN PROGRESS | Units, hashing, cache, scheduler, packaging and workflows reviewed |
| 05–55 | NOT COMPLETE | No completion claim |

## Critical findings

1. **Database state transitions are not protected.** `fail()` can rewrite terminal jobs; `complete()` ignores stale transitions; every `JobStore` construction rewrites all `running` rows to `interrupted`.
2. **Cache misses are not single-flight.** Concurrent identical requests may launch duplicate Aspen instances, and existing cache payloads can be overwritten.
3. **Unit semantics are incomplete.** Non-finite values, unsupported same-unit strings and one-sided missing units can bypass validation; absolute/delta temperature and absolute/gauge pressure are not separated.
4. **Canonical hashing accepts non-standard numeric JSON.** `NaN` and `Infinity` are currently permitted.
5. **Portable CI is below the requested gate.** The current line-only gate is 63% and lacks format, branch coverage, database/state/evidence validators and full wheel smoke commands.
6. **Real Aspen workflow is not a complete certification activity.** It lacks the `licensed` runner label and several mandatory evidence and fault-injection stages.
7. **The open 1.2 candidate was rejected as a parent baseline.** Its GitHub Actions run failed at Ruff on all Python jobs and its package migration references missing modules.

## Reviewed files

| Path | Classification | Risk |
|---|---|---:|
| `pyproject.toml` | REFACTOR | High |
| `src/aspenops_nexus/units.py` | REFACTOR | High |
| `src/aspenops_nexus/hashing.py` | REFACTOR | High |
| `src/aspenops_nexus/cache.py` | REFACTOR | Critical |
| `src/aspenops_nexus/scheduler.py` | REFACTOR | Critical |
| `tests/test_units.py` | REFACTOR | High |
| `.github/workflows/ci.yml` | REFACTOR | High |
| `.github/workflows/windows-aspen-certification.yml` | REFACTOR | High |

The machine-readable ledger contains line ranges, finding IDs, classifications, tests, commits and final-validation fields.
