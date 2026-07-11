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

For MCP, configure `ASPENOPS_ALLOWED_ROOTS` using the platform path separator. An empty setting means no root restriction and is appropriate only for trusted local development.

## Semantic identifier policy

Identifiers such as stream and block names accept only letters, numbers, underscore, dot and hyphen. Backslashes and path-control characters are rejected to prevent semantic templates from becoming raw-path injection channels.

## Audit

Optional JSONL audit records include UTC timestamp, event and sanitized metadata. The default audit does not persist model contents or output arrays. Deployments should define retention, access control and redaction rules.

## Proprietary data

Do not commit or log customer cases, proprietary property data, private kinetics, credentials, license files or Aspen vendor documentation. `.bkp`, `.apw`, `.apwz` and `.his` are ignored by default.
