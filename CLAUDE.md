# Claude Code operating contract for AspenOps 2.0

Use only the project `aspenops` MCP server for simulator operations. Do not create a second execution path, remote branch or parallel implementation PR.

For process synthesis or repair, produce only `aspenops.flowsheet/v1` Process Intent IR. Validate it with `scripts/validate_process_ir.py` before any backend request. Do not generate arbitrary Python, Shell, VBA, COM calls or raw Aspen Tree Paths. A planned DWSIM, IDAES, Modelica or Aspen/HYSYS IR compiler is not an available adapter.

Required simulator order:

```text
validated Process Intent when synthesis is involved
→ system_info
→ list_semantic_variables
→ dry_run_request
→ submit_batch / submit_optimization
→ job_status / optimization_status
→ job_result / optimization_result
→ verify_evidence_bundle
```

Do not create raw COM, GUI automation, VBA, shell-based process killing, arbitrary Tree Path writes or alternate Aspen drivers. Treat `Run2()` returning as engine evidence only. Report a point as valid only when AspenOps returns `ok=true`, and disclose convergence evidence, constraint violations and balance residuals.

Before changing `main`, use the frozen lockfile, run Ruff, formatting, strict mypy, the branch-coverage pytest gate, build, MCP surface checks, Process Intent validation and the portable Demo. Keep the public-control-plane result separate from licensed Aspen runtime evidence and human engineering acceptance.

Real Aspen certification remains `PENDING_REAL_ASPEN_CERTIFICATION` until the protected licensed workflow produces complete workspace-staged signed evidence for an exact trusted-`main` commit and a qualified engineer accepts the scoped result.
