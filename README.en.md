# AspenOps 2.0

**Turn a process proposal into a dimensioned, bounded execution request; judge every point using convergence, constraints, balances and original evidence.**

[简体中文](README.md) · [Implementation guide](docs/implementation-guide.en.md) · [Windows setup](docs/windows-setup.md) · [Delivery acceptance](docs/delivery-acceptance.md)

![version-2.0.0-delivery](https://img.shields.io/badge/version-2.0.0-111827)
![Python 3.11–3.13](https://img.shields.io/badge/Python-3.11--3.13-3776AB)
![Apache 2.0](https://img.shields.io/badge/license-Apache--2.0-0F766E)

`aspenops-nexus 2.0.0` is the Python control plane for Aspen Plus / Aspen HYSYS. It unifies CLI, MCP, a durable queue and isolated workers. Thermodynamic properties, equipment models and flowsheet solutions remain the responsibility of the external licensed simulator and reviewed user model.

## Execution architecture

![AI-generated AspenOps architecture: declare, govern, isolate execution and verify independent gates](docs/assets/ai-generated/architecture.png)

**Figure 1 · AI-generated schematic.** Requests pass path, registry, unit and resource checks before controlled execution. Search candidates are not automatically feasible. The illustrated plant and records explain software relationships; they are not Aspen results, measurements or engineering certification.

| Work to perform | Implementation | Operating boundary |
|---|---|---|
| Bind model variables to dimensioned inputs and outputs | [registry](src/aspenops_nexus/registry.py), [evaluation_plan](src/aspenops_nexus/evaluation_plan.py) | Confirm actual model nodes and access rights |
| Run batches and isolate failures | [batch](src/aspenops_nexus/batch.py), [worker](src/aspenops_nexus/worker.py), [scheduler](src/aspenops_nexus/scheduler.py) | Private snapshots, declared licenses, timeouts and cancellation |
| Sample and optimize | [design](src/aspenops_nexus/design.py), [optimizer](src/aspenops_nexus/optimizer.py) | LHS, grids and bounded DE; feasibility first, no global-optimum guarantee |
| Validate process intent and engineering rules | [process_ir](src/aspenops_nexus/process_ir.py), [engineering_rules](src/aspenops_nexus/engineering_rules.py) | Valid IR does not authorize arbitrary execution |
| Bind identity and preserve failed evidence | [provenance](src/aspenops_nexus/provenance.py), [archive_safety](src/aspenops_nexus/archive_safety.py) | Assess digest integrity, signer trust and engineering applicability separately |

There is **no adapter** for DWSIM, IDAES or Modelica/FMI execution. These adapters and general `aspenops.flowsheet/v1` compilers remain `planned`. Existing v2 plan objects and native-build protocols still require adapter qualification and conformance tests.

Real engineering status remains **`PENDING_REAL_ASPEN_CERTIFICATION`**. Mock regressions do not qualify real Aspen; finding a ProgID does not certify the commercial version. Real acceptance needs the fixed Windows host, license, model and registry, Golden Cases, engineering tolerances, signed evidence and engineer acceptance.


## Quick start

Run from the repository root. Use **uv 0.11.16** and Python 3.12 to match the primary CI environment; the project supports Python 3.11, 3.12 and 3.13.

```bash
git clone https://github.com/SUNHAOJUN22/AspenOps-Agent.git
cd AspenOps-Agent
uv lock --check
uv sync --frozen --extra dev --extra agent --extra signing
uv run aspenops --version
uv run aspenops doctor --probe
uv run aspenops demo
uv run aspenops dry-run examples/guarded-mock-batch.example.json
uv run aspenops run-batch examples/guarded-mock-batch.example.json \
  --output var/guarded-results.json --bundle var/guarded-run-bundle.zip
uv run aspenops verify-bundle var/guarded-run-bundle.zip
```

This [executable request](examples/guarded-mock-batch.example.json) contains three temperature/reflux points, required outputs, a purity constraint and a linear feed-setpoint consistency check. `declared_feed_setpoint` checks that the flow readback equals `120 kg/h`; **it is not a whole-plant mass-conservation proof**, because the Mock does not expose every outlet. The original [minimal batch](examples/batch-request.example.json) remains useful for connection and execution smoke checks.

`dry-run` opens no Aspen instance and reports paths, registry digest, effective workers and I/O budget. `run-batch` writes per-point JSON and an evidence ZIP; it exits with code `2` if any point has `ok=false`, while preserving diagnostics. `verify-bundle` checks the archive and hashes; an unsigned bundle supplies integrity evidence only. [CLI implementation](src/aspenops_nexus/cli.py)

Add `--extra windows` when synchronizing dependencies on Windows. Follow the [Windows guide](docs/windows-setup.md) for real environments. `.env.example` is a template: import its settings into the actual process environment.

## Concise technical route

![AI-generated AspenOps technical route: discover, bind, preflight, execute and verify evidence](docs/assets/ai-generated/roadmap.png)

**Figure 2 · AI-generated schematic.** `system_info` → `list_semantic_variables` → `dry_run_request` → `submit_batch` → `job_status` / `job_result` → `verify_evidence_bundle`. Use the background queue for more than 16 points or long solves; preflight every new batch definition.

$$
W_{\rm eff}=\min(W_{\rm request},W_{\max},L),\qquad
\mathrm{ok}=C\land E\land V\land F.
$$

$L$ is declared license capacity, not entitlement discovered by the program. $C,E,V,F$ denote communication, engine, convergence and declared constraint/balance qualification. A failed mandatory gate retains diagnostics and stops acceptance. Digests establish declared byte integrity; signatures also require externally trusted keys, and real engineering acceptance needs licensed execution and human review.


## Mathematical and engineering contracts

![AI-generated AspenOps algorithm figure: objective normalization, bounded DE, linear balances and evaluation budgets](docs/assets/ai-generated/algorithm.png)

**Figure 3 · AI-generated schematic.** These relations map to implemented code. The [implementation guide](docs/implementation-guide.en.md) retains full definitions, units, rejection paths and regression entry points.

### Admit interpretable inputs first

JSON rejects nonfinite values and nonzero decimals that parse to zero. A Python float already rounded to zero cannot reveal its original decimal value. Source units must come from the registry; conversion handles scale and offset together.

$$
y=\frac{a_sx+b_s-b_t}{a_t}.
$$

$a_s,a_t$ are scales to a common base unit; $b_s,b_t$ are offsets. Treat an absolute temperature reference and a difference scale separately: an absolute $20\,{}^\circ\mathrm C$ is $293.15\,\mathrm K$, whereas a $10\,{}^\circ\mathrm C$ difference remains $10\,\mathrm K$. [Unit implementation](src/aspenops_nexus/units.py)

### Establish numerical validity before applying balance tolerances

Each $q_i$ first enters the common `base_unit`; $c_i$ is finite and dimensionless, $b$ is the declared target, and $f$ is the scale floor:

$$
r=\operatorname{fsum}(c_1q_1,\ldots,c_nq_n,-b),\qquad
S=\max\left(\sum_i|c_iq_i|,f\right),\qquad \rho=|r|/S.
$$

$$
\mathrm{passed}\iff\mathrm{valid}\land
\left(|r|\le a_{\rm tol}\ \lor\ \rho\le r_{\rm tol}\right).
$$

`valid` includes finite-value, domain and underflow checks. $S$ excludes $|b|$. The quantities $r,S,f,a_{\rm tol}$ share one unit; $\rho,r_{\rm tol}$ are dimensionless, and $S=0$ is invalid. If a nonzero ratio underflows, the implementation uses the smallest positive float as a conservative upper bound and records `relative_upper_bound`. Actual mass or energy conservation needs complete material or power/enthalpy-flow terms. [Balance implementation](src/aspenops_nexus/evaluation.py)

### Separate candidates, feasibility and objective values

$$
z_j=\sigma_j\frac{y_j-r_j}{s_j},\qquad J=\sum_jw_jz_j,
\qquad s_j>0,\ w_j>0.
$$

$\sigma_j=+1$ means minimize and $-1$ means maximize; readbacks first enter the declared unit. Feasible points precede infeasible points. Compare objectives between feasible points and diagnostic violations between infeasible points. Violation is not an engineering loss in a single physical unit. DE/rand/1/bin uses

$$
v_d=a_d+F_m(b_d-c_d),\qquad x_d\in[\ell_d,h_d].
$$

For normal uncancelled execution, population $P\ge4$, budget $B\ge P$ and requested generations $G\ge0$ give

$$
G_* =\min\left(G,\left\lfloor\frac{B-P}{P}\right\rfloor\right),\qquad
N_{\rm eval}=P(1+G_*)\le B.
$$

A generation starts only if its whole population fits. These are candidate evaluations; caching may reduce physical solves. The population is not a thermodynamic ensemble. [Optimizer implementation](src/aspenops_nexus/optimizer.py)


## Seven-repository route and statistical-mechanics context

![AI-generated seven-repository roadmap: dotted proposed interfaces and canonical-equilibrium context](docs/assets/ai-generated/seven-repo-roadmap.png)

**Figure 4 · AI-generated schematic.** The repositories remain independent. Dotted links are proposed handoffs, not proof of an implemented end-to-end integration. For a canonical equilibrium system at fixed $N,V,T$ and $T>0$,

$$
\beta=\frac{1}{k_BT},\qquad Z=\sum_i e^{-\beta E_i},\qquad
p_i=\frac{e^{-\beta E_i}}{Z},\qquad F_{\rm Helmholtz}=-k_BT\ln Z.
$$

$E_i$ is a microstate energy and $k_B$ is Boltzmann's constant. These relations explain the theoretical competition between energy and entropy; AspenOps does not implement a partition-function or property-package solver. Open-process inlet, outlet, reaction and energy-transfer terms still require separate balances. DE candidates do not follow this Boltzmann distribution. [Tong's statistical-physics notes](https://www.damtp.cam.ac.uk/user/tong/statphys/statmechhtml/S1.html)

The four current scientific schematics retain [provenance and prompts](docs/assets/ai-generated/README.md). English in-image labels are shared, with localized Chinese and English captions. The original twenty-three engineering SVGs remain in the explicitly [historical gallery](docs/assets/README.md); the [earlier English hero](docs/assets/readme-vnext/hero.en.svg) is an ordinary historical link.


<details>
<summary>Operating, deployment and acceptance detail</summary>


## Configuration boundaries

| Environment variable | Default | Meaning |
|---|---|---|
| `ASPENOPS_BACKEND` | `mock` | `mock`, `aspen_plus`, or `hysys` |
| `ASPENOPS_MODE` | `default` | `readonly` rejects parameter writes; some extended operations require `enhanced` |
| `ASPENOPS_ALLOWED_ROOTS` | Empty | Semicolon-separated roots; real backends require absolute roots |
| `ASPENOPS_STATE_DIR` | `var` | Cache/job directory; real backends require an absolute path inside an allowed root |
| `ASPENOPS_LICENSE_SLOTS` / `ASPENOPS_MAX_WORKERS` | `1` / license slots | Administrator-declared concurrency limits; code does not prove license capacity |
| `ASPENOPS_TIMEOUT_S` / `ASPENOPS_STARTUP_TIMEOUT_S` | `1200` / `90` seconds | Default point-response budget / worker-startup budget |
| `ASPENOPS_WORKER_MAX_POINTS` / `ASPENOPS_WORKER_MAX_AGE_S` | `200` / `14400` seconds | Periodic recycling limits |
| `ASPENOPS_MAX_REQUEST_BYTES` / `ASPENOPS_MAX_BATCH_POINTS` | `10000000` / `10000` | Request size / batch size limits |
| `ASPENOPS_MAX_SEMANTIC_OPERATIONS` | `1000000` | Declared semantic-operation budget per batch |
| `ASPENOPS_MAX_OPTIMIZATION_EVALUATIONS` | `10000` | Optimization evaluation cap; additional caps are 64 variables and 16 objectives |

[Settings](src/aspenops_nexus/config.py) defines the remaining scheduler options and type checks. [Resource-budget](tests/test_config_resource_budgets.py) and [batch-limit](tests/test_batch_resource_limits.py) tests cover rejection paths.

## Configuration and path safety

Paths are expanded and resolved before allowed-root checks. Real backends reject empty or relative roots and state directories outside them. The master model supplies private snapshots; workers verify model/registry digests around startup. `readonly` rejects actual write requests. [Policy](src/aspenops_nexus/policy.py) · [Snapshot identity tests](tests/test_phase0_artifact_identity.py)

Durable submission pins model, registry and checkpoint locations to absolute paths, recording `paths_pinned` and `submission_cwd`. A scheduler started in another directory still uses the submitted locations; hashes continue to protect content identity. [Durable paths](src/aspenops_nexus/durable_request.py) · [CLI regressions](tests/test_cli_durable_queue.py)

`run-batch` limits regular-file size before parsing and checks canonical request size afterward. Duplicate JSON keys and invalid numbers are not silently rewritten. Keep output paths distinct from the master model; agents must not bypass the runtime through raw `win32com`, arbitrary Shell/VBA or unregistered simulator paths.

## Independent validity gates

Inspect `communication_ok`, `engine_ok`, `converged`, `feasible`, `violations`, and `balance_residuals` for each point. `constraint_non_finite` / `balance_non_finite` indicate invalid numerical evidence; `constraint_failed` / `balance_failed` indicate unsuccessful declared checks. A returned process, idle engine or `completed` job does not substitute for per-point `ok`.

Mock uses synthetic relationships to exercise software contracts. Its equations and unit conventions remain in the [implementation guide](docs/implementation-guide.en.md); they are not fitted properties or plant models.

## Common workflows

**Small batches:** run `doctor`, inspect the registry, then use `dry-run` and `run-batch`. Validate a few points' units, constraints and convergence evidence before expanding the range. Register confirmed model nodes; do not guess Aspen Tree Paths or HYSYS object chains.

**Durable batches:** start the service in terminal A and submit from terminal B with the same environment. Both processes must share `ASPENOPS_STATE_DIR`.

```bash
# Terminal A: keep running; stop with Ctrl+C
uv run aspenops scheduler
```

```bash
# Terminal B: Bash; submit exactly once
JOB_ID=$(uv run aspenops submit examples/guarded-mock-batch.example.json \
  | python -c "import json,sys; print(json.load(sys.stdin)['job_id'])")
uv run aspenops job "$JOB_ID"
# Only if cancellation is intended:
uv run aspenops cancel "$JOB_ID" --grace-s 2
```

In PowerShell, save the output of `uv run aspenops submit ... | ConvertFrom-Json` and read `.job_id`; do not copy the Bash assignment syntax. A successful submission does not mean the scheduler has executed the job. [Job guide](docs/agent-usage.md)

The [Python example](docs/implementation-guide.en.md) protects the process entry with `__main__`.

## MCP compatibility and server lifecycle

```bash
uv run aspenops mcp
```

Install the `agent` extra for local stdio MCP; the dependency contract is `mcp>=1.30.0,<2`. The service lifespan starts and stops one scheduler/PoolManager. [Implementation](src/aspenops_nexus/mcp_server.py) · [Compatibility check](scripts/check_mcp.py) · [Historical MCP lifecycle diagram](docs/assets/readme/mcp-runtime-lifecycle.svg)

Agent sequence: `system_info` → `list_semantic_variables` → `dry_run_request` → `submit_batch` → `job_status` / `job_result` → `verify_evidence_bundle`. `run_batch_sync` is capped at 16 points; long solves should use the background queue even with fewer points. Optimization tools are `submit_optimization`, `optimization_status`, `optimization_result`, and `cancel_optimization`. Accept only `ok=true` points and separately verify the evidence and engineering interpretation.

## Constrained optimization lifecycle

```bash
uv run aspenops optimize examples/optimization-request.example.json \
  --output var/optimization-result.json
```

The [example](examples/optimization-request.example.json) searches temperature and ordinal reflux choices with a minimum-purity constraint, explicit objective units and normalization scales. Establish the feasible domain before increasing population or generations; Settings still caps the budget. Results retain trace, candidates, feasible Pareto points, request identity and budget. Checkpoints are written atomically after initialization and each generation as review snapshots; the current CLI does not claim arbitrary checkpoint resumption of DE state. [Optimization guide](docs/optimization-engine.md)

## Process Intent and engineering design

```bash
uv run python scripts/validate_process_ir.py examples/process-intent.example.json \
  --canonical-output var/ci/process-intent-canonical.json \
  --report-output var/ci/process-intent-report.json
uv run python scripts/render_process_ir_dashboard.py \
  --input var/ci/process-intent-report.json \
  --output-html var/ci/process-ir-dashboard.html \
  --output-svg var/ci/process-ir-dashboard.svg
uv run python scripts/validate_process_design_v2.py \
  examples/process-requirement-v1.example.json examples/process-design-v2.example.json \
  --report-output var/ci/process-design-report.json
```

v1 validates components, equipment, ports, streams, references and resource caps; canonical ordering gives the same graph identity despite reordered input. `process-ir-dashboard.html` is a contract dashboard, not a simulation result. v2 adds requirement binding, parameters, composition, charge, mass and recycle contracts. [IR guide](docs/process-intent-ir.md)

## Native adapter conformance gate

v2 native construction requires the `NativeBuildAdapter` protocol, manifest, input/output schemas, units, failure isolation, transactions and topology/layout readback. Execution also binds adapter code, runtime identity, signed qualification, revocation policy and a valid witness. Plans missing this evidence are blocked; a declared compatible version is not certification of a commercial target. [Adapter gate](src/aspenops_nexus/native_adapter_conformance.py) · [Controlled execution](src/aspenops_nexus/native_builder.py) · [Guide](docs/native-adapter-conformance.md)

## Cache, batch deduplication and singleflight

Canonical JSON uses sorted keys and fixed separators for stable digests, with `allow_nan=False` rejecting nonfinite output. The request parser separately checks original decimal input. [Hashing implementation](src/aspenops_nexus/hashing.py)

Independent `reinitialize` requests can use persistent cache, `same_batch_dedup`, and `inflight_singleflight`. Failures are not cached by default; `ASPENOPS_CACHE_FAILURES` still excludes communication/engine failures and tainted workers. SQLite WAL and an in-memory LRU reduce repeat access; deep copies isolate callers' result mutations. [Cache](src/aspenops_nexus/cache.py) · [Regressions](tests/test_pool_cache_efficiency.py)

**a cache hit is an independent historical result**; it does not write parameters into the live worker. `warm_start` disables result caching and requires one worker, one session and increasing unique steps, with no cold points mixed into a pool call. The live pool retains its session and last dispatched step across calls and reused leases. A different session, repeated step or decreasing step is rejected before any parameter write or readback as `warm_start_session_mismatch` or `warm_start_step_not_increasing`; the existing trajectory remains unchanged.

A dispatched step consumes its number even if it does not converge; cancellation before dispatch does not consume it. Recover with a larger step in the same session, or actually execute a cold initialization before establishing another session. These labels are trajectory-order contracts, not user authentication. Closure, replacement, timeout, an unsuccessful cold reset or a cached cold request blocks continuation. Only an actual `reinitialize` on the current worker with successful communication/engine and convergence clears the old binding and restores eligibility. Constraint acceptance remains separate from live-state validity. [Warm-start regressions](tests/test_warm_start_continuity.py) · [Cross-call/lease binding regressions](tests/test_warm_start_session_binding.py)

## Worker ownership and recycling

Workers open private model snapshots and use IPC bound to protocol version, request ID and result schema. Real backends require Windows Job Object supervision. Cleanup checks PID, creation time, executable fingerprints and descendant relationships; independently opened user Aspen processes must not be terminated. [Worker](src/aspenops_nexus/worker.py) · [Supervision](src/aspenops_nexus/windows_job.py) · [Ownership tests](tests/test_aspen_process_ownership.py)

$$
R_{\rm periodic}=(n_{\rm evaluated}\ge n_{\max})\lor(t_{\rm age}\ge t_{\max}).
$$

Point counts and monotonic age are periodic conditions. Crashes, protocol errors, taint, timeouts and cancellation deadlines have additional recycle paths. Replacement increments generation; previous live state is not silently restored.

## Native failure isolation

`timeout_s` budgets the wait for a single worker response. It is not a total SLA for queuing, startup, replacement and evidence packaging. A timeout terminates the owned worker and returns `worker_timeout`; startup has a separate budget and termination/recycling take cleanup time. Responses with the wrong protocol or request ID cannot count as successful results. [IPC regressions](tests/test_worker_protocol_hardening.py) · [Polling boundaries](tests/test_polling_numeric_boundaries.py)

## Scheduling and recovery

The queue records owner, lease, heartbeat, completed position and cancellation state. Recoverable failures enter `retry_wait`; exhausted attempts enter `dead_letter`. Lease fencing prevents a previous executor from overwriting a reclaimed job. Cancellation first requests stopping and then recycles active workers when grace expires. Completed jobs still require per-point `ok` checks. [Implementation](src/aspenops_nexus/scheduler.py) · [Race tests](tests/test_scheduler_multiprocess_races.py) · [Lease regressions](tests/test_scheduler_claimed_lease_fencing.py)

## Evidence bundle integrity and authenticity

Bundles bind requests, results, model/registry and environment digests. Archive reading rejects unsafe paths, duplicate declarations, oversized members and digest mismatches. Ed25519 uses an externally trusted public key; a key inside a bundle cannot appoint itself the trust root. Evaluate integrity, authenticity and model applicability separately. [Provenance](src/aspenops_nexus/provenance.py) · [Archive tests](tests/test_provenance_zip_safety.py)

Core quality and execution workflows include `ci.yml`, `windows-control-plane.yml`, `generate-performance-evidence.yml`, and `licensed-aspen-certification.yml`. Quality uses `ubuntu-24.04`; Windows control-plane jobs use `windows-2025`. The frozen dependency lock is audited for all six combinations of Linux and Windows with Python 3.11, 3.12 and 3.13; execution matrices are defined by their workflow files. An additional [EPDM public-source download workflow](.github/workflows/epdm-public-source-download.yml) retrieves original public documents and download receipts without executing a simulator.

Manual workflows require `refs/heads/main` and run a dispatch guard before `actions/checkout`; the guard **fails explicitly with exit code 2** on other refs. Candidate/baseline comparisons use `detached` worktrees. Licensed tasks run serially in a protected self-hosted Windows environment, require `expected_head_sha == GITHUB_SHA`, and record `GITHUB_RUN_ID`, `GITHUB_RUN_ATTEMPT`, `LICENSED_EVIDENCE_DIR`, `run-metadata.txt`, and `job_status`. Manual performance/licensed evidence uses `RUNNER_TEMP` / `${{ runner.temp }}`, with artifact names containing both `github.run_id` and `github.run_attempt` to distinguish runs and retries; licensed upload uses `aspenops-licensed-artifact` and `if-no-files-found: error`. [Licensed control plane](docs/licensed-certification-control-plane.md)

## Performance engineering and evidence

Measurements include cold/warm CLI startup, import time, node reads, cache calls, serialization counts, SQLite plans and peak memory. Single-worker synchronous dispatch avoids an extra dispatch thread while the simulator remains in its isolated process. Performance conclusions require the same environment and workload before and after a change; Mock timings are not Aspen speedups.

```bash
uv run aspenops benchmark --points 4 --workers 1,2
uv run python scripts/measure_cli_startup.py --output var/ci/cli-startup.json
uv run python scripts/measure_operation_counts.py --output var/ci/operation-counts.json
uv run python scripts/measure_job_store_queries.py --output var/ci/job-store-query-plan.json
```

Interpret `cli-startup.json`, `operation-counts.json`, and `job-store-query-plan.json` using [Performance Audit V2](docs/performance-audit-2026-07-27-v2.md). Historical reports are comparison evidence; delivery decisions use new records for the target commit.

## Industrial use cases

| Scenario | Usage strategy |
|---|---|
| Separation/reaction scans | Validate a few cold points before LHS/grid expansion; declare product constraints and complete stream terms first |
| Energy/quality tradeoffs | Fix units, reference scales, feasible domain and budget before interpreting Pareto candidates |
| Continuation or grade-transition studies | One worker and explicit session/step; rebuild controlled initial conditions after state loss |
| Failure reproduction/model handover | Fix digests, registry, runtime, seed and original outputs; retain failed points |
| Agent-generated process concepts | Produce restricted IR and cited assumptions; pass graph/engineering rules before authorized execution |

These are workflow applications. Actual design still requires approved models and engineering review; the code supplies no plant-level safety certification.

## Delivery acceptance

`main` is the only persistent branch. The **archived validated baseline** in the [quality report](docs/quality-report.md) is historical evidence, **not an automatic claim** about later commits. Acceptance must bind complete logs, JUnit, branch coverage, builds and artifact hashes to the target SHA. Collected tests, skipped tests and old screenshots do not establish passing tests.

Run the original frozen gate; add `--extra windows` to synchronization on Windows:

```bash
uv lock --check
uv sync --frozen --extra dev --extra agent --extra signing
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run python -m compileall -q src scripts
uv run python scripts/audit_source_tree.py
uv run pytest -W error::ResourceWarning \
  --cov=aspenops_nexus --cov-branch --cov-fail-under=95.0
uv build
uv run python scripts/check_mcp.py
uv run python scripts/check_wheel_metadata.py --dist-dir dist
uv run python scripts/validate_process_ir.py examples/process-intent.example.json
uv run aspenops --version
uv run aspenops demo
uv run python scripts/verify_delivery.py --root . --output var/ci/delivery-acceptance.json
```

CI additionally performs the six frozen dependency audits, Bandit `1.9.4` at high/high, and reversed/seeded-random Python 3.12 test order. `scripts/render_test_dashboard.py` builds dashboards from original evidence: `test-dashboard-quality.html` covers general software quality gates, `test-dashboard-windows.html` covers Windows software gates, and `test-dashboard-licensed.html` presents protected real-engine qualification evidence. Their platforms and evidence scopes differ; check the source SHA and original results when reading a dashboard. Extended stability runs must record actual active-test time, cycle outcomes and source identity; one regression run is not a six-hour completion attestation.

## Deterministic delivery bundle

`scripts/build_delivery_bundle.py` requires a clean Git tree and the actual current SHA, rejecting uncommitted files and mismatched identity. Outputs are `aspenops-source-<sha12>.zip`, `aspenops-handover-<sha12>.zip`, `aspenops-sbom-<sha12>.spdx.json`, and `SHA256SUMS`, using sorted members, canonical timestamps and an `SPDX-2.3` SBOM.

```bash
# Run on committed, verified, clean main using the actual SHA.
uv run python scripts/build_delivery_bundle.py \
  --root . --output-dir var/delivery --source-sha "$(git rev-parse HEAD)"
uv run python scripts/verify_delivery.py \
  --root . --require-current-qualification \
  --output var/ci/delivery-acceptance-current.json
```

`--require-current-qualification` requires an eligible record for the current source; creating a ZIP alone cannot grant PASS. Follow the [delivery guide](docs/delivery-acceptance.md) to write that record from original evidence and retain the real-engineering qualification boundary.

## Repository structure

| Path | Responsibility |
|---|---|
| `src/aspenops_nexus/` | One runtime: models, units, registry, execution, queue, optimization, IR, research and evidence |
| `examples/` | Mock, registry, optimization, process and research contract examples |
| `tests/` | Numerical, protocol, concurrency, file-safety, packaging, documentation and workflow regressions |
| `scripts/` | Audits, IR validation, benchmarks, dashboards and deterministic delivery |
| `.github/workflows/` | Software, Windows control-plane, performance and licensed workflows |
| `docs/assets/ai-generated/` | Four complete current AI-generated schematics with prompts and provenance |
| `docs/assets/README.md` | Historical gallery of twenty-three engineering SVGs and acceptance illustrations |

## Troubleshooting

| Symptom | Investigation |
|---|---|
| `dry-run` failure | Allowed paths, keys/identifiers, permissions, units, bounds and budgets |
| `worker_timeout` | Point budget, solver state and recycling; termination does not imply convergence |
| `warm_start_session_mismatch` / `warm_start_step_not_increasing` | Check the live session and last dispatched step; changing trajectory requires a completed cold initialization |
| `warm_start_state_lost` | Actually complete controlled `reinitialize` on the current worker; cache cannot restore state |
| `constraint_non_finite` / `balance_non_finite` | Original values, unit scale, missing terms and derived overflow |
| `balance_underflow` or zero-tolerance failure | Check scale and genuine error requirements; do not replace small nonzero values with zero |
| Persistent pending job | Confirm scheduler operation and matching submission/service state directories |
| Cache miss | Compare model, registry, runtime, request and arithmetic-semantics digests |
| License/signature failure | Trusted key, target SHA, validity, revocation state and original rejection evidence |

## License

[Apache-2.0](LICENSE) covers this repository. Aspen Plus, Aspen HYSYS, Windows, customer models and commercial process data remain subject to their own licensing and data-use requirements.

</details>

<!-- CURRENT_MAIN_ACCEPTANCE_V2:START -->
## Regenerable implementation index

This index is generated by `scripts/refresh_current_main_readme.py --write` and checked for a fixed point with `--check`. The mathematical definitions and executable workflows above are the primary usage guide; the source files and earlier concept diagram below remain traceable references.

[`src/aspenops_nexus/process_ir.py`](src/aspenops_nexus/process_ir.py) · [`src/aspenops_nexus/models.py`](src/aspenops_nexus/models.py) · [`src/aspenops_nexus/pool.py`](src/aspenops_nexus/pool.py)

[Earlier English code-contract diagram](docs/current-main/aspenops-current-main-en.svg)

Software gates are not licensed Aspen Plus/HYSYS engineering certification; the external state remains PENDING_REAL_ASPEN_CERTIFICATION.

<!-- CURRENT_MAIN_ACCEPTANCE_V2:END -->
