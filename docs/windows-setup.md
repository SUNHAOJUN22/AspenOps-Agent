# Windows Setup

## Scope

This guide covers deterministic Windows installation, the public Windows control-plane gate, first real Aspen Plus or HYSYS execution, and the protected licensed-certification workflow. Mock and Fake-COM validation are not real Aspen physical certification.

## Prerequisites

- native 64-bit Windows;
- Python 3.11–3.13;
- `winget` or `uv >= 0.11.16`;
- licensed Aspen Plus and/or Aspen HYSYS for real execution;
- known license-seat limits;
- a non-confidential model already convergent in the GUI;
- a verified semantic registry or HYSYS Spreadsheet Contract;
- non-empty absolute existing `ASPENOPS_ALLOWED_ROOTS`;
- absolute state, model, registry, output and evidence paths inside those roots.

Real-backend `Settings` construction fails immediately when roots are absent, relative, or do not contain the state directory.

## Recommended bootstrap

```powershell
powershell -ExecutionPolicy Bypass -File scripts/setup_windows.ps1
```

The fail-closed script:

1. enables strict PowerShell behavior;
2. installs missing `uv` through winget;
3. tries `uv self update` for an old standalone installation with PATH modification disabled;
4. falls back to winget upgrade and install;
5. rechecks the actual version after each attempt and requires `uv >= 0.11.16`;
6. refreshes machine/user PATH while preserving current process PATH;
7. checks `uv.lock` and installs `windows + agent + dev + signing` with `--frozen`;
8. creates, validates and imports `.env`;
9. rejects duplicate variables and unbalanced quotes;
10. reports failures by line number without echoing raw values that may contain secrets;
11. runs `aspenops doctor --probe` with the imported backend;
12. checks native exit codes.

A new `.env` uses Mock, an empty allowlist and repository-local state. Edit it before real Aspen use.

```powershell
uv lock --check
uv sync --frozen --extra windows --extra agent --extra dev --extra signing
Copy-Item .env.example .env
# Edit and import .env before Doctor.
uv run aspenops doctor --probe
```

## Recommended real-backend configuration

```text
ASPENOPS_BACKEND=aspen_plus
ASPENOPS_MODE=default
ASPENOPS_ALLOWED_ROOTS=D:/AspenModels;D:/AspenResults
ASPENOPS_STATE_DIR=D:/AspenResults/aspenops-state
ASPENOPS_LICENSE_SLOTS=1
ASPENOPS_MAX_WORKERS=1
ASPENOPS_MAX_RESIDENT_CASES=2
ASPENOPS_CACHE_FAILURES=0
ASPENOPS_VISIBLE=0
```

The complete resource limits are documented in [`.env.example`](../.env.example).

## Public Windows control-plane gate

Authoritative workflow: `windows-control-plane.yml`.

It uses pinned `windows-2025`, Python 3.12 and `uv 0.11.16` without licensed Aspen. It enforces immutable Actions, read-only checkout, frozen dependencies, Ruff/format/mypy, PowerShell AST and executable helper contracts, documentation/version/link contracts, Job Objects, process ownership, IPC/recovery, Scheduler leases, Fake Aspen Plus/HYSYS, archive/bundle safety, real-backend path policy, CLI and Doctor smoke.

The archived public Windows baseline recorded 104 passing tests. No current fixed count is claimed without a readable JUnit artifact.

## First real case

1. Place a non-confidential, already convergent model inside an allowed root.
2. Verify the case-specific registry.
3. Start with one Worker.
4. Run `uv run aspenops dry-run D:/AspenModels/request.json`.
5. Run one point and verify its evidence bundle.
6. Add meaningful constraints and available balances.
7. Repeat from private model copies.
8. Increase concurrency only after stability, memory and license behavior are measured.

## Protected licensed certification

Authoritative workflow: `licensed-aspen-certification.yml`.

```text
ubuntu-24.04 dispatch guard
→ self-hosted, windows, x64, aspen-licensed certification job
```

A lightweight Ubuntu job checks `GITHUB_REF`. A ref other than `refs/heads/main` exits with status 2, marks the workflow failed, and does not consume the Aspen license machine. The self-hosted job has `needs: dispatch-guard`.

The input SHA is never passed directly to checkout:

```text
Ubuntu guard requires GITHUB_REF == refs/heads/main
→ checkout trusted main workflow revision
→ validate SHA format, commit existence and main ancestry
→ detached checkout validated SHA
→ verify HEAD and plan path
→ lock check and frozen Mock regression
→ realpath → preflight → explicit approval → real COM
→ signed-bundle verification → human engineering review
```

### Per-run-attempt evidence

All real certification jobs use one fixed concurrency group:

```text
licensed-aspen-certification
```

This serializes Aspen Plus and HYSYS certifications. The external output directory is unique to the workflow attempt:

```text
ASPENOPS_STATE_DIR/licensed-certification/<GITHUB_RUN_ID>-<GITHUB_RUN_ATTEMPT>
```

The workflow removes and recreates this directory, exports `LICENSED_EVIDENCE_DIR`, and uses it for preflight, real execution, signature verification and report validation. This prevents a rerun from reading an earlier attempt's report or bundle.

Before the Mock regression, `var/ci` is removed and recreated. Successful external evidence is copied into a clean `var/ci/licensed-evidence` directory. The artifact name includes both `github.run_id` and `github.run_attempt`, and upload reads only workspace-local `var/ci`.

Security properties:

- invalid manual refs fail rather than becoming skipped runs;
- `needs: dispatch-guard` protects the licensed host;
- all real certification jobs are serialized;
- per-attempt external evidence is cleaned before use;
- traversal, symlink and junction escapes are rejected;
- signing secrets are absent from setup and Mock regression;
- software cannot self-grant final certification.

## Troubleshooting

### `uv lock --check` fails

Review `pyproject.toml` and `uv.lock`; never remove `--frozen` to hide drift.

### `uv` is too old

Rerun `scripts/setup_windows.ps1`. It tries self-update, then winget upgrade/install, and verifies the result.

### `.env` is rejected

Fix the reported line. Remove duplicate variables, invalid names or unbalanced quotes. The script does not print raw values.

### Real backend is rejected before Doctor

Set non-empty absolute roots and an absolute state directory inside one root. This early failure is intentional.

### Aspen returns but a point fails

Inspect convergence evidence, constraints, balance residuals and Aspen status/error nodes. Engine return alone is not success.
