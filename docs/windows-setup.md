# Windows Setup

## Scope

This guide covers deterministic Windows installation, the public Windows control-plane gate, the first real Aspen Plus or Aspen HYSYS case, and the protected licensed-certification workflow.

Mock and Fake-COM validation are not real Aspen physical certification.

## Prerequisites

- native 64-bit Windows;
- Python 3.11–3.13;
- `winget` or `uv >= 0.11.16`;
- licensed Aspen Plus and/or Aspen HYSYS for real execution;
- a known license-seat limit;
- a non-confidential model already convergent in the GUI;
- a verified case-specific semantic registry or HYSYS Spreadsheet Contract;
- non-empty, absolute, existing directories in `ASPENOPS_ALLOWED_ROOTS`;
- absolute state, model, registry, output and evidence paths inside those roots.

Real-backend `Settings` construction fails immediately when allowed roots are absent, relative, or do not contain the state directory. Unsafe configuration does not reach preflight or create runtime state.

## Recommended bootstrap

```powershell
powershell -ExecutionPolicy Bypass -File scripts/setup_windows.ps1
```

The script is fail-closed and:

1. enables strict PowerShell behavior;
2. installs `uv` through winget when it is missing;
3. automatically upgrades an older `uv` to at least `0.11.16`;
4. refreshes machine and user PATH while preserving the process PATH;
5. checks `uv.lock` and performs a frozen install of `windows + agent + dev + signing`;
6. creates `.env` from `.env.example` when absent;
7. validates and imports `.env` into the current process;
8. rejects duplicate variable names and unbalanced quoted values;
9. reports `.env` failures by line number without echoing raw values that may contain secrets;
10. runs `aspenops doctor --probe` with the loaded backend and checks native exit codes.

A newly copied `.env` uses `ASPENOPS_BACKEND=mock`, an empty allowlist and a repository-local state directory. Edit it to `aspen_plus` or `hysys`, configure real absolute paths, and rerun the script before using a real model.

## Manual equivalent

```powershell
uv lock --check
uv sync --frozen --extra windows --extra dev --extra agent --extra signing
Copy-Item .env.example .env
# Edit and import .env into the current process before Doctor.
uv run aspenops doctor --probe
```

Copying `.env` alone does not load it into PowerShell. The repository bootstrap performs that import explicitly.

## Recommended real-backend configuration

```text
ASPENOPS_BACKEND=aspen_plus
ASPENOPS_MODE=default
ASPENOPS_ALLOWED_ROOTS=D:/AspenModels;D:/AspenResults
ASPENOPS_STATE_DIR=D:/AspenResults/aspenops-state
ASPENOPS_LICENSE_SLOTS=1
ASPENOPS_MAX_WORKERS=1
ASPENOPS_MAX_RESIDENT_CASES=2
ASPENOPS_TIMEOUT_S=1200
ASPENOPS_STARTUP_TIMEOUT_S=90
ASPENOPS_WORKER_MAX_POINTS=200
ASPENOPS_WORKER_MAX_AGE_S=14400
ASPENOPS_POOL_IDLE_TIMEOUT_S=1800
ASPENOPS_CACHE_FAILURES=0
ASPENOPS_VISIBLE=0
```

The complete resource limits are documented in [`.env.example`](../.env.example).

Use `ASPENOPS_PROGID` or `ASPENOPS_HYSYS_PROGID` only to pin a registration already verified on the host. Otherwise AspenOps performs newest-first discovery and retains an unversioned fallback.

## Diagnose

```powershell
uv run aspenops doctor --probe
```

Confirm native Windows and expected bitness, `pywin32`, allowed roots, state placement, Automation Server candidates and license-aware Worker limits. Doctor does not prove that an approved model opens, solves or is physically valid.

## Public Windows control-plane gate

Authoritative workflow: `windows-control-plane.yml`.

It runs on pinned `windows-2025`, Python 3.12 and exact `uv 0.11.16`, without licensed Aspen. It enforces:

- immutable Action SHAs and read-only checkout;
- checked frozen dependencies;
- Ruff lint/format and strict mypy;
- PowerShell AST and workflow-governance contracts;
- documentation links, tool versions, runner names and first-run configuration contracts;
- Windows Job Object and process-ownership boundaries;
- Worker IPC, timeout, recovery and singleflight;
- Scheduler active leases;
- Fake Aspen Plus/HYSYS convergence adapters;
- archive and evidence-bundle safety;
- direct `Settings`, backend-escalation, CLI-output and realpath policy tests;
- licensed CLI, workflow and signed-bundle interfaces;
- Windows CLI, Doctor smoke, JUnit and diagnostics.

The archived pre-hardening Windows run recorded 104 passing tests. No new fixed selected-test count is claimed until a current JUnit artifact is readable.

## First real case

1. Put a non-confidential, already convergent model in an allowed root.
2. Build and manually verify the semantic registry.
3. Start with one Worker.
4. Validate without opening Aspen:

   ```powershell
   uv run aspenops dry-run D:/AspenModels/request.json
   ```

5. Run one known point and verify its integrity bundle:

   ```powershell
   uv run aspenops run-batch D:/AspenModels/request.json `
     --output D:/AspenResults/results.json `
     --bundle D:/AspenResults/run-bundle.zip

   uv run aspenops verify-bundle D:/AspenResults/run-bundle.zip
   ```

6. Add meaningful constraints and available mass, energy or elemental balances.
7. Run independent repeats from private model copies.
8. Increase concurrency only after convergence, repeatability, memory and license behavior are measured.

## Licensed certification

Authoritative workflow: `licensed-aspen-certification.yml`.

Required runner labels:

```text
self-hosted, windows, x64, aspen-licensed
```

Configure the protected environment `licensed-aspen-certification` with absolute allowed roots, an absolute state directory inside those roots, license metadata, a signing-key path secret and a trusted public-key path variable.

Manual dispatch requires a repository-relative plan, exact lowercase 40-character commit SHA, backend selection and explicit execution approval.

```text
exact SHA checkout and trusted-main ancestry check
→ lockfile check and frozen sync
→ isolated Mock software regression without real secrets
→ documentation, path and workflow governance contracts
→ realpath validation for plan, roots and state target
→ licensed preflight
→ explicit human execution approval
→ scoped real COM execution
→ signed-bundle verification
→ pending human engineering review
```

Security properties:

- manual inputs are environment-bound instead of injected into PowerShell bodies;
- the approved commit must belong to trusted `main` history;
- the plan resolves inside the checkout;
- roots and state are explicitly absolute;
- realpath rejects traversal, symlink and junction escapes;
- canonical paths pass through `GITHUB_ENV`;
- signing secrets are absent from setup and Mock regression;
- artifact names use `github.run_id`;
- software cannot self-grant final certification.

## Local licensed commands

```powershell
uv run aspenops certification-preflight D:/AspenModels/licensed-plan.json `
  --output D:/AspenResults/preflight.json

uv run aspenops certify-licensed D:/AspenModels/licensed-plan.json `
  --output-dir D:/AspenResults/licensed-certification

uv run aspenops verify-licensed-bundle `
  D:/AspenResults/licensed-certification/licensed-certification-bundle.zip `
  --public-key D:/AspenKeys/aspenops-certification-public.pem
```

The runtime deliberately remains `PENDING_REAL_ASPEN_CERTIFICATION`; final engineering acceptance is human-owned.

## Troubleshooting

### `uv lock --check` fails

`pyproject.toml` and `uv.lock` disagree. Update and review the lockfile explicitly; do not remove `--frozen`.

### `uv` is too old

Rerun `scripts/setup_windows.ps1`. It automatically requests a winget upgrade and verifies that the resulting version is at least `0.11.16`.

### `.env` is rejected

The script reports the failing line number without printing the raw value. Remove duplicate variable names, fix invalid names or balance surrounding quotes. Do not print the file in CI logs when it may contain secrets.

### Real backend is rejected before Doctor

Set non-empty absolute existing `ASPENOPS_ALLOWED_ROOTS` and an absolute `ASPENOPS_STATE_DIR` inside one root. This early failure is intentional.

### Doctor still reports Mock

Edit `.env` and rerun `scripts/setup_windows.ps1`. Copying `.env` without importing it does not alter the current process.

### No COM server is found

Check Aspen installation, Python/Aspen bitness, Registry registration and any explicit ProgID pin.

### Paths are rejected

Move models, registries, state, outputs and bundles into configured absolute roots. Do not disable path policy.

### Aspen returns but the point fails

Inspect convergence evidence, constraint violations, balance residuals and Aspen status/error nodes. Engine return alone is not success.

### More Workers reduce throughput

Lower concurrency and measure license waiting, memory pressure, model stability and Worker aging. Effective concurrency is bounded by licenses, memory and stability.
