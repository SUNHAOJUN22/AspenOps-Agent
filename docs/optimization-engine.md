# AspenOps v2 Optimization Engine

## Design objective

The optimizer is budgeted, constraint-aware and batch-oriented. It does not
allow an evolutionary or learning loop to invoke Aspen without an explicit
maximum evaluation count, Worker cap and simulator timeout.

## Problem model

An optimization document declares:

- semantic variables;
- variable kinds: continuous, integer, categorical, ordinal;
- one or more objectives;
- objective direction: minimize or maximize;
- optional scalar weights used by the search algorithm;
- process constraints and conservation checks in the normal batch request;
- population, generation, mutation, crossover and evaluation budget;
- deterministic seed and optional checkpoint path.

Categorical and ordinal variables are encoded as bounded indexes and decoded
before semantic writes are generated. Integer variables are rounded within
their declared bounds.

## Batch differential evolution

The implemented search is bounded `DE/rand/1/bin` with Deb-style feasibility
ordering. The initial population and every generation are submitted with one
`evaluate_many` call:

```text
initial population -> one Aspen batch
generation 1 trials -> one Aspen batch
...
generation G trials -> one Aspen batch
```

This allows the persistent CasePool to use all licensed Workers and prevents a
serial Python optimizer from leaving simulator instances idle.

## Feasibility ordering

For scalar candidates:

1. feasible dominates infeasible;
2. between feasible candidates, lower minimized scalar objective wins;
3. between infeasible candidates, lower aggregate violation wins.

Transport and convergence failures receive finite but severe violation values.
They remain sortable without becoming competitive with physically valid points.

## Multi-objective results

Original objective values are retained for reporting. Maximization objectives
are sign-normalized only for internal minimization. The result includes a
non-dominated Pareto archive evaluated under feasibility-first dominance.

For one objective the archive is extracted with a linear minimum filter. For
two objectives AspenOps uses an exact stable sweep with `O(n log n)` sorting and
linear scanning. Higher-dimensional objective sets retain exact incremental
dominance filtering. These paths preserve input ordering and duplicate-removal
semantics while avoiding unnecessary pairwise work in the common one- and
two-objective cases.

The scalar weighted score guides the current DE search; it is not presented as
a universal replacement for Pareto decision analysis.

## Checkpointing

An optional checkpoint is written atomically after the initial population and
each completed generation. It contains generation number, evaluation count and
population state. Checkpoint persistence does not imply that a proprietary
simulator call itself is replay-free.

## Interfaces

- CLI: `aspenops optimize request.json`
- MCP: `submit_optimization`, `optimization_status`,
  `optimization_result`, `cancel_optimization`
- Python: `run_optimization_document`

Durable optimization jobs use the same leased Scheduler, cancellation deadlines
and PoolManager as batch simulations.

## Qualification

Mock optimization results are labelled `control-plane-only`. A real Aspen
optimization remains `PENDING_REAL_ASPEN_CERTIFICATION` until candidate points,
constraints, property method and final optima are independently reviewed and
repeated on an approved licensed model.
