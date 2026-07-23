# AspenOps 2.0 Architecture

## Design objective

Aspen Automation is a stateful COM interface around a proprietary nonlinear solver. The runtime must therefore preserve COM apartment ownership, simulator lifecycle, model identity, license limits and engineering evidence. AspenOps treats these as first-class invariants rather than incidental implementation details.

## Control plane and data plane

The control plane performs policy, schema validation, semantic resolution, unit conversion, queueing, caching, provenance and certification. The data plane consists of spawned workers. Each worker owns:

- one OS process;
- one COM STA;
- one simulator Automation Server;
- one private staged model copy;
- one semantic registry instance;
- one sequential command stream.

No COM proxy crosses a process boundary.

## Simulator-neutral intent plane

The Process Intent plane sits above the existing control plane. It accepts a constrained graph rather than executable simulator code:

```text
Human / text / image / search Agent
→ aspenops.flowsheet/v1
→ deterministic validation and digest
→ future backend compiler
→ existing execution control plane
```

The graph declares components, property package, units, typed ports, streams and finite scalar parameters. Unknown fields, executable metadata keys, raw Tree Paths, invalid references and unsafe connection structures fail closed.

Process understanding is therefore separated from simulator execution. A concept, parameter or repair Agent may produce only validated Process Intent IR. It cannot directly own COM, write arbitrary Python/VBA/Shell or call unrestricted simulator methods.

## Compiler boundary

Backend execution and automatic flowsheet compilation are independent capabilities. Aspen Plus and HYSYS execution already exist for approved models on licensed Windows, but their IR compilers are still planned. DWSIM, IDAES and Modelica/FMI are declared roadmap backends only; no adapter is claimed until a compiler conformance suite and execution tests exist.

```text
IR valid
AND compiler available
AND backend execution available
AND policy approved
```

Only then may an IR-driven model construction request enter the execution control plane.

## Bounded Agent pipeline

```text
Knowledge
→ Concept / topology
→ Parameter declaration
→ Validated execution request
→ Bounded repair proposal
→ Convergence, balance and human-review gate
```

Every stage has a declared responsibility and permitted output. Simulator feedback may propose bounded IR edits, but it cannot silently rewrite the execution policy or self-grant engineering approval.

## Evaluation transaction

```text
RECEIVED
  → VALIDATED
  → REINITIALIZED | WARM_START
  → WRITES_COMMITTED
  → ENGINE_RETURNED
  → OUTPUTS_READ
  → VERIFIED | FAILED
```

A batched transaction is sent over one duplex pipe message with a correlation ID. The worker validates and executes the complete point. The parent process enforces the hard deadline. If the worker does not respond, only that worker is terminated and later replaced.

## Semantic registry

The registry is both an API schema and a capability boundary. A semantic node defines access, unit, quantity, bounds, identifiers, candidate paths or locators, backend and verification status. Agent-provided identifiers are restricted to safe characters and cannot contain path separators or template syntax.

The registry hash participates in cache identity. Changing a path, bound, unit or meaning invalidates cached results.

## Runtime compatibility

Aspen Plus registrations are discovered from both Windows registry views. Versioned `Apwn.Document.*` candidates are sorted by numeric suffix and tried newest-first, followed by `Apwn.Document`. HYSYS uses the corresponding `HYSYS.Application.*` strategy.

No marketing-version mapping is assumed. The actual successful ProgID and exposed application attributes are captured as runtime evidence.

## Validity state

One evaluation returns independent gates:

```text
communication_ok
engine_ok
converged
feasible
balance_residuals
```

`ok` is the conjunction of those gates. This prevents software completion from being confused with a valid process solution.

Process-IR benchmark evidence adds independent topology, compiler availability, execution-attempted, convergence, material/energy closure, repair-iteration and human-intervention fields. A skipped or unavailable backend cannot declare convergence.

## Persistence

The scheduler uses SQLite in WAL mode. Jobs survive process restarts as durable records. A job left in `running` during service restart is moved to `interrupted`, because silent resumption would violate execution identity.

The result cache is also SQLite WAL. Cache keys bind runtime schema/version, backend, model SHA-256, registry SHA-256 and solver-relevant request content. Process Intent uses its own canonical JSON SHA-256 identity before compilation.
