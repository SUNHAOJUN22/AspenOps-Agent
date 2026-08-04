# AspenOps single-main qualification

## Decision

`PASS_CONTROL_PLANE_AND_BUILD_CONTRACTS`

## Validated scope

- branch policy: `MAIN_ONLY`;
- validated source commit: `c66300e38a5d3ce2d595c01398ba912627dfe90c`;
- standard Linux CI run: `30938876928`;
- standard Windows control-plane run: `30938874028`;
- six-target frozen dependency audit: `PASS`;
- locked signing dependency: `cryptography 50.0.0`;
- real commercial Aspen Plus/HYSYS runtime: `NOT_EXECUTED`;
- certification status: `PENDING_REAL_ASPEN_CERTIFICATION`.

## Python matrix

| Python | Passed | Failed | Errors | Skipped | Branch coverage |
|---|---:|---:|---:|---:|---:|
| 3.11 | 1186 | 0 | 0 | 0 | 95.20% |
| 3.12 | 1186 | 0 | 0 | 0 | 95.20% |
| 3.13 | 1186 | 0 | 0 | 0 | 95.20% |

Python 3.12 reverse-order and fixed-seed order-independence gates passed. Ruff, exact
formatter, strict mypy, source-tree audit, high/high Bandit, dependency audit,
distribution build, clean Wheel installation, CLI demo, MCP surface and Windows
control-plane contracts passed.

## Software capability boundary

The validated repository includes immutable execution artifacts, typed process
requirements and ProcessDesignIR v2, deterministic engineering rules, offline
Aspen Plus/HYSYS 14/15 compilation contracts, signed runtime qualification,
fresh execution authorization, chained revocation policies and an independent
short-lived witness receipt.

It does **not** yet include a production native builder that can take arbitrary natural
language and safely create any Aspen Plus/HYSYS flowsheet. No licensed Aspen Plus V15 or
HYSYS V15 Golden Case, native topology/layout roundtrip, commercial solver result or
human engineering acceptance was executed by these public workflows.
