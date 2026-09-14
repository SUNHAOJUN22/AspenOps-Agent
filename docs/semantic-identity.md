# Semantic identity admission

## Structural references and display labels

The public result label `pressure:block=R1` can be produced by either the key
`pressure` with `{"block": "R1"}` or a literal key `pressure:block=R1` with no
identifiers. They are different registry references and must not share a resolved
node, a constraint value, a balance term or a previously cached success.

`validate_request_identities()` checks the semantic key and complete sorted
identifier mapping for every write, read, constraint and balance term. It rejects
conflicting structural references with `RegistryError: Ambiguous semantic identity`.
This runs before plan compilation performs backend actions, and before `CasePool`
computes a cache key or returns persistent cached results. It is not a replacement
for registry, backend, identifier, unit, bound or policy validation.

## Compatibility and recovery

Unambiguous public labels, serialized requests and cache keys are unchanged.
Repeated references to the same structural node still share one read. A literal
key containing a colon remains supported when it does not collide with another
reference in the same request. Historical cache rows are retained, not rewritten.

For an ambiguous request, rename the conflicting registry key and its references,
or submit the independent references in separate requests. Changing the registry
continues to change the registry digest used by the cache. Do not reuse a legacy
success as proof that a rejected ambiguous request is valid.

## Verification scope

The regression suite in `tests/test_evaluation_plan.py` covers cross-role and
reversed-order collisions, unknown keys, malformed identifiers, rejection before
backend state changes, single/batch cached-result admission and compatible read
reuse. Synthetic Mock and SQLite cases validate software behavior only; they do
not establish real Aspen execution or engineering acceptance.
