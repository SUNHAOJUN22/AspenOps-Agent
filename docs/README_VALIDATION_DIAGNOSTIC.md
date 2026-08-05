# README validation diagnostic

- source SHA: `c157f8ae5f5fd4125f872ad186e0c25a3efb91e2`;
- matching Actions runs: 3.

## CI — `completed` / `failure`

- run ID: `30964716489`;
- workflow path: `.github/workflows/ci.yml`;
- job `Python 3.12 tests`: `completed` / `failure`, failed steps: Pytest with branch coverage.
- job `Quality, build and smoke`: `completed` / `failure`, failed steps: Ruff.
- job `Python 3.13 tests`: `completed` / `failure`, failed steps: Pytest with branch coverage.
- job `Python 3.11 tests`: `completed` / `failure`, failed steps: Pytest with branch coverage.

## Validate refreshed README on single main — `completed` / `failure`

- run ID: `30964716516`;
- workflow path: `.github/workflows/validate-readme-main-once.yml`;
- job `Python 3.11 full tests`: `completed` / `failure`, failed steps: Test.
- job `Windows control-plane contracts`: `completed` / `failure`, failed steps: Prepare and validate.
- job `Linux quality build wheel and MCP`: `completed` / `failure`, failed steps: Prepare governed source tree.
- job `Python 3.12 full tests and order gate`: `completed` / `failure`, failed steps: Test and order independence.
- job `Python 3.13 full tests`: `completed` / `failure`, failed steps: Test.
- job `Record README qualification and clean workflow`: `completed` / `failure`, failed steps: Finalize source and evidence.

## Windows control-plane contracts — `completed` / `failure`

- run ID: `30964716436`;
- workflow path: `.github/workflows/windows-control-plane.yml`;
- job `windows-contracts`: `completed` / `failure`, failed steps: Ruff.

