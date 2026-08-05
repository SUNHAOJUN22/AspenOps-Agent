# AspenOps single-main qualification

## Decision

`PASS_CONTROL_PLANE_AND_BUILD_CONTRACTS`

## Validated scope

- branch policy: `MAIN_ONLY`;
- workflow-free tested source: `974a7f125fad6f7a5628295cc2c4157d22a41ad4`;
- qualification orchestration commit: `5757ac51254b21480068166e5c7fbca87415d765`;
- qualification run: `30967716901`;
- six-target frozen dependency audit: `PASS`;
- locked signing dependency: `cryptography 50.0.0`;
- real commercial Aspen Plus/HYSYS runtime: `NOT_EXECUTED`;
- certification status: `PENDING_REAL_ASPEN_CERTIFICATION`.

Each decisive job removed the temporary qualification workflow before validation. The
validated working tree therefore matched the workflow-free source commit above.

## Python and Windows matrix

| Target | Passed | Failed | Errors | Skipped | Branch coverage |
|---|---:|---:|---:|---:|---:|
| Python 3.11 | 1186 | 0 | 0 | 0 | 95.20% |
| Python 3.12 | 1186 | 0 | 0 | 0 | 95.20% |
| Python 3.13 | 1186 | 0 | 0 | 0 | 95.20% |
| Windows 2025 / Python 3.12 | 1186 | 0 | 0 | 0 | not collected |

Python 3.12 reverse-order and fixed-seed (`20260728`) order-independence gates passed for
all 1186 tests.

## Quality gates

The following gates passed:

- six-target frozen dependency audit for Linux and Windows on Python 3.11–3.13;
- Ruff lint and exact formatter;
- strict mypy across 76 source files;
- Python source compilation and source-tree audit;
- high-severity/high-confidence Bandit analysis;
- distribution build and clean Wheel installation;
- CLI demo and MCP compatibility smoke;
- Windows 2025 full control-plane suite.

## README visual contract

The Chinese and English README files use twenty-two repository-local, self-contained,
AI-assisted SVG diagrams. A twelve-diagram visual atlas provides the primary navigation.
The assets contain no remote scripts, external fonts or remote images and remain bound to
implemented software contracts or clearly labelled planned scope.

## Software capability boundary

The validated repository includes immutable execution artifacts, typed process
requirements and ProcessDesignIR v2, deterministic engineering rules, offline Aspen
Plus/HYSYS 14/15 compilation contracts, signed runtime qualification, fresh execution
authorization, chained revocation policies and an independent short-lived witness receipt.

It does **not** yet include a production native builder that can take arbitrary natural
language and safely create any Aspen Plus/HYSYS flowsheet. No licensed Aspen Plus V15 or
HYSYS V15 Golden Case, native topology/layout roundtrip, commercial solver result or human
engineering acceptance was executed by these public workflows.
