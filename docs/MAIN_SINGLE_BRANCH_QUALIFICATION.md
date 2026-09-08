# AspenOps single-main qualification

## Decision

`PASS_CONTROL_PLANE_AND_BUILD_CONTRACTS`

## Validated scope

- branch policy: `MAIN_ONLY`;
- validated source: `0214fe417735c6162fd6f4317b2f0fc645cad552`;
- qualification run: `30992536823`;
- milestone: `NATIVE_ADAPTER_CONFORMANCE_PREFLIGHT`;
- real commercial Aspen Plus/HYSYS runtime: `NOT_EXECUTED`;
- certification status: `PENDING_REAL_ASPEN_CERTIFICATION`.

## Python and Windows matrix

| Target | Passed | Failed | Errors | Skipped | Branch coverage |
|---|---:|---:|---:|---:|---:|
| Python 3.11 | 1207 | 0 | 0 | 0 | 95.27% |
| Python 3.12 | 1207 | 0 | 0 | 0 | 95.27% |
| Python 3.13 | 1207 | 0 | 0 | 0 | 95.27% |
| Windows 2025 / Python 3.12 | 1207 | 0 | 0 | 0 | not collected |

Python 3.12 reverse-order and fixed-seed (`20260728`) gates passed.

## Native adapter conformance milestone

A strict manifest now proves profile, adapter-contract, code/runtime identity,
operation and adapter-key coverage, readback, save/reopen and failure-isolation
capabilities before the first native compilation step. The execution record binds
the manifest and conformance-report digests.

## Capability boundary

This is an offline preflight contract, not vendor certification. Licensed Aspen
Plus/HYSYS Golden Cases and human engineering acceptance remain mandatory.
