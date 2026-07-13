# Claude Code operating contract for AspenOps 1.0

Use only the project `aspenops` MCP server for simulator operations.

Required order:

`system_info → list_semantic_variables → dry_run_request → submit_batch → job_status → job_result → verify_evidence_bundle`

Do not create raw COM, GUI automation, VBA, shell-based process killing, arbitrary Tree Path writes, or alternate Aspen drivers. Treat `Run2()` returning as engine evidence only. Report a point as valid only when AspenOps returns `ok=true`, and disclose any implicit convergence evidence, constraint violation or balance residual.
