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

MCP operation is fail-closed. Production startup requires `ASPENOPS_ALLOWED_ROOTS`, using the platform path separator, and `ASPENOPS_AUDIT_LOG`. An empty root list or missing audit destination raises a configuration error before any session can be used.

For isolated local development only, `ASPENOPS_INSECURE_LOCAL_DEV=1` explicitly permits unrestricted paths and disables persistent audit. Do not use this override on a shared workstation, service account, remote MCP endpoint or production host.

## Worker and session recovery

A worker timeout or transport death marks the logical session as `dead`. AspenOps never starts a fresh worker behind the same session ID and pretends the simulator document survived. The client must call `recover_session`, which reopens the original case path. Unsaved in-memory modifications from the terminated process are not recoverable.

## Read-only policy

A read-only session cannot call `set_values` or `save_case`. The Aspen backend also rejects direct mutation and save operations. If the installed Aspen Automation interface cannot open a case with an explicit read-only argument, opening fails rather than silently falling back to writable mode.

## Convergence policy

Missing or unrecognized Aspen status is reported as `unknown`, not `converged`. Only explicit success evidence produces the converged state; explicit failure evidence always dominates success text.

## Semantic identifier policy

Identifiers such as stream and block names accept only letters, numbers, underscore, dot and hyphen. Backslashes and path-control characters are rejected to prevent semantic templates from becoming raw-path injection channels.

## Audit

JSONL audit records include UTC timestamp, event and sanitized metadata. MCP deployments must configure `ASPENOPS_AUDIT_LOG`. The audit does not persist model contents or output arrays by default. Deployments should define retention, access control, integrity protection and redaction rules.

## Proprietary data

Do not commit or log customer cases, proprietary property data, private kinetics, credentials, license files or Aspen vendor documentation. `.bkp`, `.apw`, `.apwz` and `.his` are ignored by default.
