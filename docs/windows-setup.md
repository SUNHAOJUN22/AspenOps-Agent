# Windows Setup

## Scope

This guide covers deterministic Windows installation, the public Windows control-plane gate, the first real Aspen Plus or HYSYS case, and the protected licensed-certification workflow. Mock and Fake-COM validation are not real Aspen physical certification.

## Prerequisites

- native 64-bit Windows;
- Python 3.11–3.13;
- `winget` or `uv >= 0.11.16`;
- licensed Aspen Plus and/or Aspen HYSYS for real execution;
- a known license-seat limit;
- a non-confidential model already convergent in the GUI;
- a verified semantic registry or HYSYS Spreadsheet Contract;
- non-empty absolute existing directories in `ASPENOPS_ALLOWED_ROOTS`;
- absolute state, model, registry, output and evidence paths inside those roots.

Real-backend `Settings` construction fails immediately when roots are absent, relative, or do not contain the state directory. Unsafe configuration does not reach preflight or create runtime state.

## Recommended bootstrap

```powershell
powershell -ExecutionPolicy Bypass -File scripts/setup_windows.ps1
```

The script:

1. enables strict PowerShell behavior;
2. installs missing `uv` through winget;
3. attempts `uv self update` for an old standalone installation while disabling PATH modification;
4. falls back to winget `upgrade` and then `install`;
5. rechecks the actual version after every attempt and requires `uv >= 0.11.16`;
6. refreshes machine/user PATH while preserving the process PATH;
7. checks `uv.lock` and installs `windows + agent + dev + signing` with `--frozen`;
8. creates `.env` from `.env.example` when absent;
9. validates and imports `.env`;
10. rejects duplicate variables and unbalanced quoted values;
11. reports errors by line number without echoing raw values;
12. runs `aspenops doctor --probe` with the imported backend and checks native exit codes.

A newly copied `.env` uses Mock, an empty allowlist and a repository-local state directory. Configure real absolute paths before changing the backend to `aspen_plus` or `hysys`.

`-LibraryMode` is reserved for Windows CI helper tests. It loads functions without installing dependencies or running Doctor.

## Manual equivalent

```powershell
uv lock --check
uv sync --frozen --extra windows --extra dev --extra agent --extra signing
Copy-Item .env.example .env
# Edit and import .env before Doctor.
uv run aspenops doctor --probe
```

Copying `.env` alone does not load it into PowerShell.

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

## Public Windows control-plane gate

Authoritative workflow: `windows-control-plane.yml`.

It runs on pinned `windows-2025`, Python 3.12 and exact `uv 0.11.16`, without licensed Aspen. It enforces:

- immutable Action SHAs, read-only permissions and non-persistent checkout credentials;
- checked frozen dependencies, Ruff, format and strict mypy;
- PowerShell AST parsing and executable bootstrap-helper contracts;
- valid dotenv import, duplicate/unbalanced rejection and secret-safe errors;
- self-update → winget upgrade → winget install fallback behavior;
- documentation, version, link, runner and workflow contracts;
- Job Objects, process ownership, Worker IPC/recovery and Scheduler leases;
- Fake Aspen Plus/HYSYS convergence, archive safety and bundle integrity;
- direct Settings, backend-escalation, CLI-output and realpath policy tests;
- Windows CLI, Doctor smoke, JUnit and diagnostics.

The archived Windows run recorded 104 passing tests. No new fixed count is claimed without a readable current JUnit artifact.

## First real case

1. Put a non-confidential, already convergent model in an allowed root.
2. Build and manually verify the semantic registry.
3. Start with one Worker.
4. Run `uv run aspenops dry-run D:/AspenModels/request.json`.
5. Execute one known point and verify its bundle:

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

Configure the protected environment with absolute allowed roots, an absolute state directory inside them, license metadata, a signing-key path secret and a trusted public-key path variable.

Manual dispatch requires a repository-relative plan, an exact lowercase 40-character SHA belonging to trusted `main`, backend selection and explicit execution approval.

```text
exact SHA checkout and trusted-main verification
→ frozen dependencies
→ isolated Mock regression without real secrets
→ documentation, backend and path governance
→ plan/root/state realpath validation
→ licensed preflight
→ explicit human approval
→ scoped real COM execution
→ signed-bundle verification
→ verify every required evidence file is present and non-empty
→ copy preflight/report/bundle to var/ci/licensed-evidence
→ upload workspace-local var/ci only
→ pending human engineering review
```

The upload action never expands an undefined external state path. Earlier failures collect only workspace-local diagnostics. Successful runs stage external certification files inside the checkout before upload.

Security properties:

- manual inputs are environment-bound rather than injected into PowerShell bodies;
- the approved commit belongs to trusted `main` history;
- realpath rejects traversal, symlink and junction escapes;
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

The runtime remains `PENDING_REAL_ASPEN_CERTIFICATION`; final engineering acceptance is human-owned.

## Troubleshooting

- **Lock mismatch:** update and review `uv.lock`; never remove `--frozen` to hide it.
- **Old uv:** rerun the bootstrap; it tries standalone self-update, then winget fallbacks, and verifies the resulting version.
- **Rejected `.env`:** fix the reported line; do not print a potentially secret-bearing file in CI logs.
- **Real backend rejected:** configure non-empty absolute roots and an absolute state directory inside one root.
- **Doctor still reports Mock:** edit and import `.env`, then rerun the bootstrap.
- **No COM server:** check Aspen installation, bitness, Registry registration and explicit ProgID pins.
- **Point fails after engine return:** inspect convergence evidence, constraint violations and balance residuals; engine return alone is not success.
