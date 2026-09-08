# Capability consolidation ledger

## Production main

The validated AspenOps 2.0 main tree contains:

- failure-closed Aspen Plus and HYSYS convergence;
- immutable evaluation plans and unique semantic reads;
- verified write transactions and rollback;
- `TAINTED` Worker generation replacement;
- strict IPC, lifecycle and Windows process ownership;
- content-addressed caching, deduplication and singleflight;
- persistent license-aware pools;
- durable Scheduler leases, heartbeats, fencing and cancellation;
- deterministic optimization and Pareto archives;
- bounded CLI and 14-tool MCP surfaces;
- archive safety and optional Ed25519 evidence;
- licensed certification plan, preflight and controlled workflow;
- portable and public-Windows evidence;
- committed portable performance evidence.

No required production capability remains unmerged.

## Experimental archive

The following source is classified `UNIQUE_EXPERIMENTAL_ARCHIVED`:

```text
agent/aspenops-1.4-mathematical-database-hardening
31464bbc8c2fb68ef18bc397dbc7ba3da1095087
```

Relevant experimental modules:

- `approval`;
- `drift`;
- `surrogate`;
- `twin`.

Decision: `ARCHIVED_NOT_SHIPPED`.

The branch failed its production Ruff gate and its modules were not connected to the accepted bounded CLI, MCP or Scheduler interfaces. They therefore must not be represented as production-ready digital-twin capability.

## Remaining blocker

The intended annotated recovery tag is recorded in `var/consolidation/branch-archive-manifest.json`, but creation is blocked because the acting integration lacks `Workflows: write`. This permission blocker does not change the runtime qualification boundary:

```text
PENDING_REAL_ASPEN_CERTIFICATION
```
