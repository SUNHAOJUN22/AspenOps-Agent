# Windows Setup

## Scope

This guide covers:

1. deterministic AspenOps installation on Windows;
2. public Windows control-plane testing without licensed Aspen;
3. the first approved Aspen Plus or Aspen HYSYS case;
4. the protected self-hosted licensed certification workflow.

Mock and Fake-COM validation are not real Aspen physical certification.

## Prerequisites

- native 64-bit Windows;
- Python 3.11–3.13;
- `winget` or a preinstalled `uv`;
- licensed Aspen Plus and/or Aspen HYSYS for real execution;
- a known license-seat limit;
- a non-confidential model already convergent in the Aspen GUI;
- a case-specific semantic registry verified with Variable Explorer or an approved HYSYS Spreadsheet Contract;
- non-empty absolute existing directories in `ASPENOPS_ALLOWED_ROOTS`;
- an absolute state directory, models, registries, outputs and evidence inside those roots.

Real-backend `Settings` construction fails immediately when allowed roots are absent, relative, or do not contain the state directory. Unsafe configuration does not reach preflight or create runtime state.

## Recommended bootstrap

```powershell
powershell -ExecutionPolicy Bypass -File scripts/setup_windows.ps1
```

The script is fail-closed and:

1. enables strict PowerShell behavior;
2. installs `uv` through `winget` only when missing;
3. refreshes machine and user PATH while preserving the process PATH;
4. verifies `uv >= 0.11.14`;
5. runs `uv lock --check`;
6. installs `windows`, `agent`, `dev` and `signing` with `uv sync --frozen`;
7. creates `.env` from `.env.example` when absent;
8. parses and imports `.env` into the current process;
9. runs `aspenops doctor --probe` with the loaded backend;
10. checks native-command exit codes.

A newly copied `.env` uses `ASPENOPS_BACKEND=mock`. Edit it to `aspen_plus` or `hysys`, then rerun the script before using a real model.

## Manual equivalent

```powershell
uv lock --check
uv sync --frozen --extra windows --extra dev --extra agent --extra signing
Copy-Item .env.example .env
# Edit and import .env into the current process before Doctor.
uv run aspenops doctor --probe
```

Copying `.env` alone does not load it into PowerShell. The repository bootstrap performs that import explicitly.

## Recommended configuration

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

The complete fail-closed resource limits are documented in `.env.example`.

Use `ASPENOPS_PROGID` or `ASPENOPS_HYSYS_PROGID` only to pin a registration already verified on the target host. Otherwise AspenOps performs newest-first discovery and retains the unversioned server as fallback.

## Diagnose

```powershell
uv run aspenops doctor --probe
```

Confirm:

- native Windows and expected Python bitness;
- `pywin32` availability;
- non-empty absolute allowed roots;
- state directory inside those roots;
- at least one expected Automation Server candidate;
- effective Workers do not exceed license seats;
- any explicit ProgID pin is instantiable.

Doctor enumerates registrations and policy readiness. It does not prove that an approved model opens, solves or is physically valid.

## Public Windows control-plane gate

```text
.github/workflows/windows-control-plane.yml
```

It runs on pinned `windows-2025`, Python 3.12, without licensed Aspen. It enforces:

- immutable Action SHAs and exact `uv` version;
- read-only repository permissions and non-persistent checkout credentials;
- checked, frozen dependencies;
- Ruff lint and formatting;
- strict mypy;
- PowerShell AST and workflow-governance contracts;
- Windows Job Object and process-ownership boundaries;
- Worker IPC, timeout, recovery and singleflight;
- Scheduler active leases;
- convergence and Fake Aspen Plus/HYSYS adapters;
- archive and evidence-bundle safety;
- rootless direct `Settings`, request-backend escalation, CLI-output and realpath policy tests;
- licensed certification CLI, workflow and signed-bundle interfaces;
- Windows CLI and Doctor smoke;
- JUnit and diagnostic artifacts.

The archived pre-hardening Windows run recorded 104 passing tests. The current selected suite is intentionally not assigned a new fixed count until a current workflow artifact is available.

## First real case

1. Put a non-confidential, already convergent model in an allowed root.
2. Build and manually verify the case-specific semantic registry.
3. Start with one Worker.
4. Validate without opening Aspen:

   ```powershell
   uv run aspenops dry-run D:/AspenModels/request.json
   ```

5. Run one known point and write an integrity bundle:

   ```powershell
   uv run aspenops run-batch D:/AspenModels/request.json `
     --output D:/AspenResults/results.json `
     --bundle D:/AspenResults/run-bundle.zip

   uv run aspenops verify-bundle D:/AspenResults/run-bundle.zip
   ```

6. Add at least one meaningful constraint and one available mass, energy or elemental balance.
7. Run independent repeats from private model copies.
8. Increase concurrency only after convergence, repeatability, memory and license behavior are measured.

## Licensed certification plan

A plan must identify:

- backend (`aspen_plus` or `hysys`);
- exact approved commit and request;
- model and semantic registry;
- meaningful perturbations and outputs;
- convergence evidence;
- constraints and balances;
- repeat count and output-specific tolerances;
- approved host and license metadata;
- signing and public-key locations outside the repository.

Local commands:

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

## Protected self-hosted workflow

```text
.github/workflows/licensed-aspen-certification.yml
```

Required labels:

```text
self-hosted, windows, x64, aspen-licensed
```

Configure the protected environment `licensed-aspen-certification` with:

- `ASPENOPS_ALLOWED_ROOTS`: one-line semicolon-separated absolute existing roots;
- `ASPENOPS_CERT_STATE_DIR`: one absolute directory inside those roots;
- license-seat and approved license metadata;
- signing-key path as a secret;
- trusted public-key path as a variable.

Manual dispatch requires:

- a repository-relative, single-line plan path;
- an exact lowercase 40-character commit SHA;
- backend selection;
- explicit `approve_real_execution=true`.

The workflow performs:

```text
exact SHA checkout and trusted-main ancestry check
→ lockfile check and frozen sync
→ isolated Mock software regression without real secrets
→ realpath validation for plan, roots and state target
→ licensed preflight
→ explicit human execution approval
→ scoped real COM execution
→ signed bundle verification
→ pending human engineering review
```

Security properties:

- manual inputs are bound through environment variables rather than injected into PowerShell bodies;
- the approved commit must belong to trusted `main` history;
- the plan resolves inside the checked-out workspace;
- allowed roots and state directory are explicitly absolute;
- realpath resolution rejects traversal, symlink and junction escapes;
- canonical paths pass to later steps through `GITHUB_ENV`;
- signing secrets are absent from dependency setup and Mock regression;
- artifact names use `github.run_id`, not arbitrary input;
- software cannot self-grant final certification.

## Troubleshooting

### `uv lock --check` fails

`pyproject.toml` and `uv.lock` disagree. Update and review the lockfile explicitly; do not remove `--frozen` to hide the mismatch.

### Real backend is rejected before Doctor

Set non-empty absolute existing `ASPENOPS_ALLOWED_ROOTS` and an absolute `ASPENOPS_STATE_DIR` inside one of those roots. This early failure is intentional.

### Bootstrap still cannot find `uv`

Open a new PowerShell session and rerun. The script already refreshes machine/user PATH while retaining the original process PATH, but some host policies defer executable discovery until a new process.

### Doctor still reports Mock

Edit `.env` and rerun `scripts/setup_windows.ps1`. Copying `.env` without importing it does not change the current process.

### No COM server is found

Check Aspen installation, Python/Aspen bitness, Windows Registry registration and any explicit ProgID pin.

### Paths are rejected

Move models, registries, state directories, outputs and bundles into configured absolute allowed roots. Do not disable path policy as a workaround.

### Aspen returns but the point fails

Inspect convergence evidence, constraint violations, balance residuals and Aspen error/status nodes. Engine return alone is not success.

### More Workers reduce throughput

Lower concurrency and measure license waiting, memory pressure, model stability and Worker aging. Effective concurrency is bounded by licenses, memory and stability—not only by the configured maximum.
