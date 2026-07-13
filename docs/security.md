# Security Model

## Default-deny surfaces

AspenOps does not expose:

- arbitrary Python or shell execution;
- VBA execution;
- generic COM method invocation;
- unrestricted `getattr` over Aspen objects;
- default raw tree-path writes;
- global process termination.

## Path policy

`SessionManager` may be configured with allowed roots. Case opening and save destinations outside those roots are rejected before worker creation or save.

The MCP server is fail-closed: `ASPENOPS_ALLOWED_ROOTS` must contain at least one root or startup fails. `ASPENOPS_INSECURE_ALLOW_ANY_ROOT=1` disables this restriction only for explicitly trusted local development. Empty roots no longer silently grant filesystem-wide access.

## Read-only sessions

A session opened with `read_only=true` rejects semantic writes, batched evaluations and saves in the service, worker and backend layers. If the installed Aspen Automation API cannot honor a read-only open call, opening fails instead of silently falling back to writable mode.

## Worker failure model

A timed-out or crashed worker is never restarted implicitly. A replacement process would not own the previously opened COM document, so the original session is marked dead and callers must close and reopen it. A `CasePool` becomes unusable after any worker failure and must be recreated.

## Convergence evidence

Missing or unrecognized Aspen status is classified as `unknown`, not `converged`. Downstream reads and feasibility calculations proceed only for explicitly converged runs. Non-finite engineering values, objectives, constraints and balance residuals are rejected or marked infeasible.

## Semantic identifier policy

Identifiers such as stream and block names accept only letters, numbers, underscore, dot and hyphen. Backslashes and path-control characters are rejected to prevent semantic templates from becoming raw-path injection channels.

## Audit

MCP deployments always create an append-only JSONL audit log. Set `ASPENOPS_AUDIT_LOG` to choose the path; otherwise it defaults to `.aspenops/audit.jsonl` under the first allowed root. Records include UTC timestamp, event and sanitized metadata, not model contents or output arrays. Deployments should define retention, access control and redaction rules.

## Proprietary data

Do not commit or log customer cases, proprietary property data, private kinetics, credentials, license files or Aspen vendor documentation. `.bkp`, `.apw`, `.apwz` and `.his` are ignored by default.
