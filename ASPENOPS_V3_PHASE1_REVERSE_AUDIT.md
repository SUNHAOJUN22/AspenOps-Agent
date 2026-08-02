# AspenOps V3 Phase 1 Reverse Audit

## Boundary

This audit covers only the simulator-neutral requirement, ProcessDesignIR, engineering-rule, plant-template and external-preview layers in stacked draft PR #104.

Current status:

`FAIL_CLOSED_PENDING_CI`

Real simulator status:

`PENDING_REAL_ASPEN_CERTIFICATION`

## Attack and failure cases

### Natural-language output attempts to inject a COM path

The Phase 1 schemas contain no COM path or method field. Unknown fields are rejected. A future natural-language layer may emit only these schemas, not raw Aspen/HYSYS object paths.

### LLM invents an equipment type

An unknown equipment `kind` is an `ENGINEERING_BLOCKER`. It cannot pass deterministic design validation merely because its ports appear plausible.

### LLM invents a simulator or version

`ProcessDesignIR` accepts only the governed simulator and version allowlists. Unsupported targets fail during parsing before any compilation plan can exist.

### Design detaches from the approved requirement

The design must carry the exact requirement SHA-256. Cross-document validation also checks target simulator, version, components, feed/product boundary IDs and property method.

### Pending inference is represented as approved input

Every critical requirement and design scalar carries a source status. `INFERRED_PENDING_APPROVAL` and `UNKNOWN` block readiness or engineering validation.

### Unicode or display-name confusion

Internal IDs are bounded ASCII. Display text and string scalar values are NFC-normalized and reject NUL, replacement characters, control characters and bidirectional overrides. Canonical IDs remain distinct from display labels.

### Duplicate or colliding IDs

Components, equipment, streams, reactions, recycles, ports, parameters and design specifications require unique IDs within their governed scope.

### Material stream is connected to an energy port

Streams derive a domain from their type. Source and target ports must match both direction and domain. Domain mismatch is a hard error.

### Required port is left unconnected

Every required port must have a connection. A non-multiple port cannot accept more than one connection.

### Device has insufficient or contradictory specifications

Equipment contracts require bounded specifications. Examples include heater/cooler thermal specifications, separator flash conditions, pressure-device targets and column stage/specification closure. Missing approved values are engineering blockers.

### Column appears connected but degrees of freedom remain open

Columns require an approved stage count and at least two independent design specifications. A connected column with insufficient specifications cannot pass.

### Reaction references undeclared chemistry

Reaction component IDs must exist in the design. Governed stoichiometric, kinetic and equilibrium reactions require stoichiometry containing at least one reactant and one product. Pending reactions or parameters block validation.

### A material cycle exists without a recycle contract

Directed material cycles require a governed recycle contract and declared tear stream. Tear streams not owned by a recycle contract are blockers.

### Template is treated as an executable Aspen model

Templates contain only governed metadata and topology skeletons. Missing inputs yield `NEEDS_ENGINEERING_INPUT`; complete inputs yield only `PLAN_ONLY`. No adapter or COM execution is called.

### External SVG is treated as proof of Aspen native topology

The preview includes an explicit boundary statement. It is a deterministic graph visualization, not native simulator evidence. Future adapter phases must read the actual simulator topology back and compare hashes.

### Oversized input exhausts memory before validation

Feeds, products, components, equipment, streams, ports, reactions, recycles, parameters and metadata are bounded before full semantic processing.

### NaN or Infinity enters an engineering parameter

Qualified and design scalars reject non-finite floats. Canonical JSON uses `allow_nan=False`.

### List reordering changes design identity

ProcessDesignIR canonicalization sorts components, equipment, streams, reactions and recycles by stable internal ID before hashing. Equivalent outer ordering produces the same design digest.

## Known limitations and remaining gates

1. The current equipment contracts cover an initial finite vocabulary, not every Aspen/HYSYS operation.
2. Vendor equipment types and property methods are not yet resolved against official, versioned V15 capability profiles.
3. The rule engine does not yet perform full chemical elemental balance or simulator degrees-of-freedom introspection.
4. Template topology is metadata and has not been compiled into native Aspen/HYSYS objects.
5. The external preview does not validate native simulator coordinates or label rendering.
6. No save–close–reopen topology roundtrip has executed.
7. No licensed V15 solve or engineering acceptance has occurred.
8. CI and order-independence must complete on the final Phase 1 head before this phase can advance.

Because of these limitations, the audit cannot grant `PASS_REAL_V15_CASE_SCOPE` or any engineering certification.
