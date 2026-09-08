# Real Aspen Certification Protocol

## Current status

```text
PENDING_REAL_ASPEN_CERTIFICATION
```

Portable Linux CI and Mock/Fake COM tests do not certify Aspen Plus, HYSYS,
property methods, kinetic models or process feasibility.

## Required environment

- self-hosted Windows runner;
- licensed target Aspen Plus or Aspen HYSYS release;
- recorded ProgID and product build;
- approved non-confidential qualification model;
- case-owned semantic registry verified against the model;
- known-stable GUI reference run;
- documented license-slot and memory limits.

## Required tests

### Runtime and isolation

- registered COM discovery and explicit runtime identity;
- one STA and one private model copy per Worker;
- source model remains unchanged;
- Job Object supervision status is recorded;
- external manually started Aspen process survives timeout and shutdown;
- Worker-owned process tree is removed after timeout.

### Convergence

- clearly converged reference case;
- explicit non-converged case;
- `Run2` return with negative status evidence;
- missing status evidence returns `unknown`;
- HYSYS convergence Spreadsheet contract;
- stable-idle sample and timeout behavior.

### Repeatability

- at least three independent cold-state repetitions;
- output absolute and relative tolerances;
- request/model/registry/runtime hashes retained;
- hidden warm-start dependence is tested separately;
- stale-cache and model-change invalidation.

### Engineering validity

- at least one product or equipment constraint;
- at least one material or energy balance;
- finite required outputs;
- property method and component set reviewed by a qualified engineer;
- failure regions represented in the test matrix.

### Performance

For Worker counts permitted by the license, record:

- startup and model-open time;
- queue delay;
- P50/P95/P99 solve time;
- throughput;
- peak memory per Worker;
- license wait/failure rate;
- recycle count and reason;
- long-run stability and throughput knee.

Mock measurements must not be substituted for these values.

### Cancellation and recovery

- cancel between points;
- cancel while Aspen is blocked;
- only the current Worker generation is recycled;
- completed points are retained;
- service restart and lease recovery;
- idempotent final result commit.

## Approval record

A certification report must include:

```text
AspenOps commit
AspenOps runtime schema
Windows build
Python build
Aspen/HYSYS build and ProgID
license environment
model SHA-256 and dependency inventory
registry SHA-256
request SHA-256
repeatability statistics
performance matrix
known limitations
reviewer and approval date
```

Only this report can move a release from
`PENDING_REAL_ASPEN_CERTIFICATION` to an explicitly scoped certified status.
