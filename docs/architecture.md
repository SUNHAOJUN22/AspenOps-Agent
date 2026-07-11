# Architecture

## Responsibility split

AspenOps separates planning, execution and physics:

- agent/application: experiment intent, variables, objectives and reporting;
- AspenOps: policy, units, lifecycle, retries, batching, audit and evidence;
- Aspen Plus: property methods, unit operations and nonlinear flowsheet solution.

## Process model

`SessionManager` owns only serializable metadata and `WorkerClient` objects. Each `WorkerClient` starts a spawned process. The process creates exactly one backend and one semantic accessor. The Aspen backend initializes COM in STA mode and creates a document with `DispatchEx`.

No COM proxy is sent back to the parent. The pipe carries dictionaries containing primitives and Pydantic-validated payloads.

## One-point transaction

A pool evaluation uses one request:

1. validate all semantic writes;
2. resolve candidate tree paths;
3. snapshot original values;
4. apply writes;
5. rollback applied writes if a later write fails;
6. optionally reinitialize;
7. run the simulator;
8. read requested outputs only after convergence;
9. return run evidence, values and diagnosis.

This cuts IPC overhead and keeps the state transition inside the process that owns Aspen.

## Persistent pool

Each pool worker receives a private staged case copy and keeps it open. Points may be reordered by nearest-neighbor distance, but results are restored to original input order.

The number of workers is an operational decision constrained by license seats, RAM and stability. AspenOps does not attempt to bypass license controls.

## Failure boundaries

- validation error: request never reaches COM;
- node-resolution error: no candidate path exists;
- partial-write error: rollback is attempted before returning failure;
- solve failure: run report is `failed`, outputs are not represented as valid;
- deadline error: the owning Worker process is terminated;
- parent process remains alive and may create a fresh worker.

AspenOps does not issue global process-kill commands because they may terminate unrelated user sessions.
