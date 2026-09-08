# Security

AspenOps treats an LLM as an untrusted planner, not as a trusted COM operator.

- Raw Aspen paths are denied unless enhanced mode and an operator-approved registry explicitly allows them.
- Model and output paths must remain under `ASPENOPS_ALLOWED_ROOTS`.
- Source models are copied to per-worker staging directories and are never overwritten.
- Write-capable operations are audited with exact request hashes.
- The server exposes no arbitrary Python, shell, VBA or COM method execution tool.
- Timeout recovery terminates only the worker process and PIDs identified as created by that worker.

Report vulnerabilities privately through GitHub Security Advisories.
