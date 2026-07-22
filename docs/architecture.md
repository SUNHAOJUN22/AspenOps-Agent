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

## Persistence

The scheduler uses SQLite in WAL mode. Jobs survive process restarts as durable records. A job left in `running` during service restart is moved to `interrupted`, because silent resumption would violate execution identity.

The result cache is also SQLite WAL. Cache keys bind runtime schema/version, backend, model SHA-256, registry SHA-256 and solver-relevant request content.
