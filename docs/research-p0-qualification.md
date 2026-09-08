# AspenOps Research Platform P0 Qualification

This document records the qualification boundary for the P0 scientific-governance layer.

The P0 implementation defines immutable Study, Dataset, Target, Parameter, Assumption,
Calibration, Validation, and Claim contracts; nine strict JSON Schemas; source-contradiction
tracking; calibration/validation isolation; and the evidence-driven model-qualification state
machine.

P0 does not open Aspen, compile runtime requests, estimate parameters, run dynamic studies,
or train machine-learning models. The Aspen execution control plane remains unchanged.

Acceptance requires the repository's permanent CI gates to pass on the current `main` commit:
Ruff, Ruff format, strict MyPy, compileall, deterministic source audit, Bandit, focused and full
pytest suites, branch-aware coverage, reverse and seeded-random order runs, Process IR, MCP,
build, Wheel metadata, and demo smoke tests. Missing current evidence is not a pass.
