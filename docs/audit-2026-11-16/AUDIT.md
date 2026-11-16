# Execution-state review and automated validation — 2026-11-16

## Scope and baseline

Baseline: `c72d42ec3d54bdd89546b39af500a88e87cfab0c`, on `main`.
The coordinator verified that the remote repository had only `main` and no open
pull requests. This review used a different reviewer from the preceding write
readback audit and focused on whether an evaluation result actually belongs to
the declared simulator state.

| Assessed code paths | Reasoning and outcome |
| --- | --- |
| `evaluation.py`, `evaluation_plan.py` | Traced plan admission, simulator mutation, engine/convergence evidence, required outputs, constraints and balances. Found an incomplete mutation-failure boundary. |
| `pool.py`, `worker.py` | Traced state reuse, immutable model identity, cold/warm requests, cache keys, generation replacement and warm-continuation invalidation. Found independent cold points could inherit native inputs. |
| Native Aspen/HYSYS and Mock backends | Compared reset behavior, input persistence, write rollback and runtime metadata. Found private model locations being treated as simulator identity. |
| `units.py` and balance evaluation | Reviewed unit dimensions, affine conversions, accumulation/sign conventions, finite arithmetic and explicit tolerance floors; retained existing scientific guards. |
| Batch, provenance and acceptance boundaries | Checked per-point success semantics and evidence identity. Batch completion still does not establish physical convergence or engineering acceptance. |
| Frozen quality/build gates | Executed the complete `AGENTS.md` gate with the unchanged `uv.lock`. |

## Confirmed defects and corrections

### 1. Exceptions during reset could leave an uncertain live worker reusable

Evaluation previously set `worker_tainted` only after the `writes_committed`
trace entry. A HYSYS solver could accept `CanSolve=False`, then raise while being
enabled again. The call failed before any write-commit marker, leaving an alive
worker with changed state and no recycling signal. An unclassified bulk-write
exception had the same gap.

The mutation boundary now begins before entering a reset or write. An unexpected
exception after that point taints the worker, so the existing pool replacement
path increments its generation before reuse. Plan rejection before backend
access remains harmless; explicit write-transaction states, including verified
rollback, retain their prior behavior.

The initial regression run produced **4 failures and 1 passing negative control**.
It demonstrated both the actual HYSYS adapter's partial setter failure with a
controlled object and the pool retaining generation zero after a failed reset.

### 2. Native cold requests did not establish a pristine input baseline

Mock's reset restores its initial input dictionary. The native adapters invoke
solver reset operations without explicitly restoring every earlier input. A
controlled HYSYS cell test shows that toggling the solver can leave a previously
written value at `95`. A pool fixture with retained input state then showed a
later nominally independent cold request inheriting `95`, instead of the model's
baseline `60`. The old cache identity could replay such a result.

For Aspen/HYSYS, an uncached `reinitialize` point now replaces a worker that has
already evaluated a point. Replacement uses the established ownership, shutdown,
staging and model/registry SHA-256 verification path to reopen the immutable
model. The new `model_baseline` recycle reason records the transition. The native
cold cache identity is versioned so that old solver-reset-only results are not
reused. Explicit warm requests preserve live state; Mock retains its complete
reset and worker reuse.

The cold-state/cache regression initially reported **4 failures and 3 passes**.
Its controls verify that warm continuation preserves both input and generation.
The correction trades startup/model-opening cost for independent native cold
semantics. Actual licensed-case startup cost has not been measured here.

### 3. Staged filenames caused false native runtime mismatches

An augmented fixture using the actual adapters' `runtime_identity()` methods
exposed another failure: `exposed.FullName` (Aspen) and `exposed.case.FullName`
(HYSYS) included each worker's private model path. Replacement and multiworker
identity checks therefore treated identical simulator versions as different
runtimes. This yielded **4 remaining failures and 5 passes** before its correction.

Native runtime metadata no longer duplicates the case's private filename in
`exposed`. It retains `model_path` for diagnostics, simulator versions, case name,
HYSYS application identity and model/registry content hashes. Different-version
controls remain unequal. Evidence-bundle hashing and verification rules were not
changed, preserving verification of previously produced bundles.

The two new regression files contain **14 cases**. The final focused lifecycle,
adapter, warm-state, ownership and provenance suite passed **76 tests**.

## Executed frozen validation

Linux CPython **3.12.14** was used. The complete gate was rerun after the final
native runtime correction; no production-source changes followed that run.
Exact commands, return codes, coverage totals and source hashes are recorded in
[validation.json](validation.json).

| Gate | Observed result |
| --- | --- |
| `uv lock --check` and frozen dev/agent/signing synchronization | Passed; dependency lock unchanged |
| `uv run ruff check .` / `ruff format --check .` | Passed; **290 Python files** formatted |
| `uv run mypy src` | Passed, **78 source files** |
| Compileall and source-tree audit | Passed; source audit found no forbidden constructs |
| Full pytest with `ResourceWarning` as errors and branch coverage | **2,171 passed**, **95.36% combined coverage**, above the 95% gate |
| `uv build` | Source distribution and wheel built |
| MCP and wheel metadata checks | Passed; **14 MCP tools**, SDK **1.30.0** |
| Example Process Intent IR | Valid, zero issues |
| CLI version and Mock demo | Passed; demo returned cached historical Mock results |

Raw logs are retained outside the repository. The durable report contains only
concise findings and structured validation evidence.

## Limits and operational implications

No licensed Aspen or HYSYS instance was started. Controlled adapter objects and
Mock fixtures validate Python state/identity handling, not native physics,
licensing, native COM behavior in a real installation or engineering acceptance.
Real qualification remains `PENDING_REAL_ASPEN_CERTIFICATION` until the protected
Windows workflow and an engineer accept its evidence. Native cold requests now
pay worker/model startup cost; explicit warm trajectories retain reuse with their
existing state-loss safeguards. The remote matrix remains responsible for other
Python versions, Windows, frozen dependency audits and test-order perturbations.
