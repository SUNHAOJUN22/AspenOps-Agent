# AspenOps 2.0 performance audit — 2026-07-27

## Scope and evidence boundary

This audit started from `main` commit:

```text
5696d57b7f14e6e9d0b7ab3b1c37627d3369cf78
```

The audit covers portable Python orchestration, CLI startup, cache accounting, same-batch deduplication, singleflight result cloning, differential-evolution allocation, Pareto filtering, performance evidence and CI governance.

It does **not** claim licensed Aspen Plus or Aspen HYSYS model-open, nonlinear-solve, convergence or engineering-performance improvement. Those claims require an approved model, a licensed Windows host, a fixed simulator runtime and qualified engineering review.

Historical `var/benchmarks/baseline.json` and `var/benchmarks/after.json` remain archived portable Mock evidence. They are useful context but are not automatic evidence for this audit's final commit.

## Primary-source research

The implementation and rejected alternatives were reviewed against these primary sources:

- [Python profiling documentation](https://docs.python.org/3/library/profile.html): deterministic profiling and `cProfile` usage.
- [Python tracemalloc documentation](https://docs.python.org/3/library/tracemalloc.html): traced allocation current/peak measurements and snapshots.
- [Python command-line documentation](https://docs.python.org/3/using/cmdline.html): `-X importtime` and import profiling.
- [Python multiprocessing documentation](https://docs.python.org/3/library/multiprocessing.html): spawn semantics, process startup and IPC termination risks.
- [SQLite WAL documentation](https://sqlite.org/wal.html): write-ahead logging behaviour and concurrency boundary.
- [SQLite PRAGMA optimize documentation](https://sqlite.org/pragma.html#pragma_optimize): bounded query-planner maintenance.
- [uv GitHub Actions guide](https://docs.astral.sh/uv/guides/integration/github/): cache use and `uv cache prune --ci` guidance.
- [uv environment documentation](https://docs.astral.sh/uv/reference/environment/): `UV_COMPILE_BYTECODE` installation/startup trade-off.
- [SciPy differential_evolution documentation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.differential_evolution.html): workers, deferred updating and vectorized evaluation trade-offs.

Secondary blog advice was not used as authority for code changes.

## Measurement design

### Environment-sensitive evidence

`scripts/measure_cli_startup.py` records:

- same-interpreter bootstrap/full-CLI control pairs;
- warmup and trial counts;
- median, P95, minimum, maximum and coefficient of variation;
- Python, executable, platform, machine, CPU, memory and commit identity;
- a separate Python `-X importtime` diagnostic process;
- explicit separation between normal wall-time samples and import-profiler overhead.

The output is:

```text
var/ci/cli-startup.json
```

Shared-runner wall time is evidence but is not a narrow hard gate.

### Deterministic low-noise evidence

`scripts/measure_operation_counts.py` records:

- cache-key calls;
- governed solver calls;
- canonical result serializations;
- same-batch deduplicated result count;
- deep result isolation;
- pending cache-hit count after the flush threshold;
- Pareto dominance calls after exact deduplication;
- cProfile function/call summary;
- tracemalloc peak and current bytes;
- process RSS before/after.

The output is:

```text
var/ci/operation-counts.json
```

Operation counts are the hard performance contracts. Profile and memory data are diagnostics with their overhead explicitly labelled.

## Optimization decision table

| ID | Module | Hotspot | Baseline evidence | Root cause | Candidate optimization | Risk | Implementation | Current evidence | Decision |
|---|---|---|---|---|---|---|---|---|---|
| PERF-001 | CLI | `--version` and help imported the execution control plane | Static import graph plus same-environment full-CLI control | `cli.py` imported batch, scheduler, pool, optimization, certification and evidence modules at module load | lightweight parser/bootstrap and delayed full CLI import | parser drift or double parse | implemented in `cli_bootstrap.py`; Wheel entrypoint changed; parser equivalence and import-boundary tests added | `cli-startup.json`, isolated module-import tests | retained |
| PERF-002 | CLI | real commands would be parsed by bootstrap and full CLI | control-flow audit | naïve bootstrap delegation can duplicate argparse work | delegate executed commands directly; parse only help/version in bootstrap | invalid argument handling could diverge | `_handled_without_control_plane()` plus full-parser equivalence tests | deterministic delegation test | retained |
| PERF-003 | ResultCache | hit threshold recalculated with `sum(Counter.values())` | source hot-path audit | O(k) scan over pending unique keys on each hit batch | O(1) `_pending_hit_total` | counter drift on discard/flush | implemented with explicit reset/decrement tests | 1024-hit deterministic contract | retained |
| PERF-004 | ResultCache | all SQLite chunks allocated before query | source allocation audit | `_chunks()` returned a complete list | yield chunks lazily | iterator misuse | implemented and existing >900-key test retained | chunked cache tests | retained |
| PERF-005 | ResultCache | verbose JSON stored unnecessary whitespace | persistent payload inspection | default separators add bytes | compact separators with identical JSON semantics | compatibility | implemented; roundtrip and stored-string tests | compact persistence test | retained |
| PERF-006 | ResultCache | planner statistics had no initialization maintenance | SQLite schema audit | no `PRAGMA optimize` after schema creation | execute bounded `PRAGMA optimize` while preserving WAL and NORMAL sync | unexpected write or blocking | implemented only at initialization | cache construction tests; SQLite official boundary | retained |
| PERF-007 | CasePool | repeated identical object references recomputed cache keys | low-noise call-count probe | cache key recomputed for every list entry | reuse key by exact object identity within one batch | equality/identity confusion | implemented for identical immutable object instances only; content identity unchanged | 100 repeated references → one key call | retained |
| PERF-008 | CasePool | one solve result was repeatedly converted through dataclass dictionaries | serialization call-count probe | cache and duplicate copies each requested a canonical payload | produce one payload only when cacheable; use deep clones for result copies | nested object aliasing | implemented with nested-isolation tests | 100 points → one serialization and 99 dedup results | retained |
| PERF-009 | Singleflight | followers rebuilt results from a shared shallow nested payload | concurrency review | shallow nested reconstruction could alias diagnostics | keep an isolated leader result and `deepcopy` per follower | memory cost | implemented; correctness takes priority over micro-allocation | concurrent nested-isolation test | retained |
| PERF-010 | DE | each target built a population-sized exclusion list to sample three indices | complexity audit | O(P²) list allocation per generation | sample `range(P-1)` and map around the excluded index | changed random sequence or DE semantics | implemented; batch/evaluation budget unchanged | existing fixed-seed convergence test plus source contract | retained |
| PERF-011 | Pareto | duplicate points still performed pairwise dominance checks | deterministic dominance-call probe | dedup occurred after O(n²) comparisons | ordered exact dedup, feasibility split, minimum-violation fast path | ordering or Deb-feasibility drift | implemented with duplicate, all-infeasible and empty-front tests | 1000 equal points → zero dominance calls | retained |
| PERF-012 | Benchmark reports | candidate document contained a stale temporary branch label | report audit | hard-coded historical name | read real revision/environment commit, otherwise say artifact | none | implemented | generated report contract | retained |
| PERF-013 | Performance evidence | wall time lacked import/profile/memory separation | prompt and evidence audit | one noisy metric cannot explain change | same-machine controls, importtime, cProfile, tracemalloc, RSS and operation counts | profiler overhead | implemented with explicit overhead labels | two machine-readable artifacts | retained |
| PERF-014 | JobStore | `list_recent()` opens one query then calls `get()` for every row | source SQL audit | N+1 query and connection pattern | one SELECT plus shared row decoder and composite indexes | critical lease/recovery state regression | not implemented through a parallel subclass or monkeypatch | documented P1 migration | deferred |
| PERF-015 | model/registry hashing | large model files are read for SHA-256 when a pool is created | identity review | content identity requires reading bytes | cache digest by mtime/size | stale identity and evidence weakening | rejected | no code change | rejected |
| PERF-016 | parallel execution | more processes may appear faster | Python spawn and simulator cost-model review | Windows spawn, COM STA, licence slots and cheap Mock objectives have different economics | increase Worker count, shared memory or process parallelism by default | overhead, lifecycle leak, licence violation | rejected without workload benchmark | no code change | rejected |
| PERF-017 | dependencies | vectorized or compiled optimizer could reduce Python overhead | SciPy/NumPy review | heavy optional dependencies affect Wheel, install and cold start | add SciPy/NumPy/Numba/Rust | portability and startup cost | rejected until profile proves pure-Python work dominates real evaluation | no code change | rejected |
| PERF-018 | uv installation | bytecode compilation may improve CLI startup | uv official guidance | compile work moves from startup to installation | enable `--compile-bytecode` globally | longer sync, entire environment compilation | not adopted without same-environment install/startup evidence | documented | deferred |
| PERF-019 | CI cache | CI cache can be reduced with `uv cache prune --ci` | uv official guidance | cache contains data not beneficial between jobs | prune after all build/Wheel operations | pruning too early can slow later steps | not inserted before remaining quality steps | documented | deferred |

## Preserved invariants

Every retained optimization preserves these contracts:

1. one COM object belongs to one Worker process and STA apartment;
2. private staged model copies remain mandatory;
3. Windows Job Object and PID fingerprint boundaries remain intact;
4. licence-slot and Worker-count limits remain intact;
5. configuration and path policy remain fail closed;
6. model and registry hashes remain content-derived;
7. cache identity still binds runtime, model, registry and physical request;
8. same-batch and singleflight result objects remain deeply isolated;
9. scheduler lease, recovery, cancellation and atomic commit semantics are unchanged;
10. non-finite evidence, Wheel metadata, MCP lifecycle and bundle integrity gates remain intact;
11. Mock performance is never promoted to licensed Aspen performance.

## Automated regression contracts

The following deterministic expectations are executed by tests that already participate in Linux, public Windows and pre-licensed-COM software gates:

```text
100 repeated request references
→ 1 cache-key computation
→ 1 governed solver call
→ 1 canonical result serialization
→ 99 same_batch_dedup results
→ deep nested result isolation

1024 cache hits
→ threshold flush
→ pending_hit_total == 0

1000 identical Pareto points
→ ordered exact dedup
→ dominance_calls == 0
```

CLI help/version tests additionally require that Pool, Scheduler, optimization, certification, evidence and MCP modules are absent from `sys.modules` on the lightweight path. The bootstrap and full parser help surfaces must remain identical.

## Commands

```bash
uv lock --check
uv sync --frozen --extra dev --extra agent --extra signing

uv run python scripts/measure_cli_startup.py \
  --output var/ci/cli-startup.json \
  --trials 7 \
  --warmups 2

uv run python scripts/measure_operation_counts.py \
  --output var/ci/operation-counts.json

uv run python scripts/run_benchmark_matrix.py \
  --repo-root . \
  --output var/ci/benchmark-smoke.json \
  --smoke

uv run python scripts/compare_benchmarks.py \
  --baseline var/benchmarks/baseline.json \
  --after var/benchmarks/after.json \
  --baseline-doc var/ci/performance-baseline.md \
  --after-doc var/ci/performance-after.md \
  --fail-on-stable-regression
```

Full qualification still requires:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest -W error::ResourceWarning \
  --cov=aspenops_nexus \
  --cov-branch \
  --cov-fail-under=94.5
uv build
```

## Current verification boundary

Current-HEAD wall-time values must come from Actions or an equivalent full checkout using the exact commit and environment fingerprint. No percentage improvement is recorded in this document before that evidence exists.

The connected environment used for this audit could not complete a full repository clone because GitHub DNS resolution was unavailable. Therefore this document does not claim that current-HEAD Ruff, format, strict mypy, full pytest, branch coverage, build or Wheel installation has passed. The committed tests and CI workflows are the execution path for those claims.

## Licensed Aspen follow-up

Portable results may justify a licensed performance campaign, but they cannot replace it. A real campaign must bind:

- exact AspenOps commit;
- installed Aspen product/build and successful ProgID;
- approved model and registry hashes;
- licence server and feature identity;
- model-open time, solve time, convergence, constraint and balance status;
- Worker count and licence slots;
- repeated trials and environmental metadata;
- qualified human engineering acceptance.
