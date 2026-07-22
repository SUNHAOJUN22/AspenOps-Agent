# Windows Setup

## Scope

This guide covers:

1. local AspenOps installation and control-plane diagnostics on Windows;
2. the first approved Aspen Plus or Aspen HYSYS run;
3. the self-hosted licensed certification workflow.

Portable Mock validation is not real Aspen physical certification.

## Prerequisites

- native 64-bit Windows;
- Python 3.11–3.13;
- `uv`;
- licensed Aspen Plus and/or Aspen HYSYS installation;
- an available and known license-seat limit;
- a project-owned, non-confidential, convergent model;
- a case-specific semantic registry verified with Aspen Variable Explorer or an approved HYSYS Spreadsheet Contract;
- writable model/result directories inside configured allowed roots.

## Install

Recommended bootstrap:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/setup_windows.ps1
```

Manual equivalent:

```powershell
uv sync --extra windows --extra dev --extra agent --extra signing
Copy-Item .env.example .env
uv run aspenops doctor --probe
```

## Configure

Recommended starting values:

```text
ASPENOPS_BACKEND=aspen_plus
ASPENOPS_MODE=default
ASPENOPS_ALLOWED_ROOTS=D:/AspenModels;D:/AspenResults
ASPENOPS_LICENSE_SLOTS=1
ASPENOPS_MAX_WORKERS=1
ASPENOPS_TIMEOUT_S=1200
ASPENOPS_STARTUP_TIMEOUT_S=90
ASPENOPS_WORKER_MAX_POINTS=200
ASPENOPS_WORKER_MAX_AGE_S=14400
ASPENOPS_MAX_RESIDENT_CASES=2
ASPENOPS_POOL_IDLE_TIMEOUT_S=1800
ASPENOPS_CACHE_FAILURES=0
ASPENOPS_VISIBLE=0
```

Use `ASPENOPS_PROGID` or `ASPENOPS_HYSYS_PROGID` only to pin a known registration. Otherwise AspenOps discovers versioned registrations newest-first and retains the unversioned server as fallback.

## Diagnose

```powershell
uv run aspenops doctor --probe
```

Confirm:

- the process is running on native Windows;
- `pywin32` is installed;
- allowed roots are configured;
- at least one expected Automation Server candidate is registered;
- the effective worker cap does not exceed the license-seat limit;
- any explicit ProgID pin is actually instantiable.

## First real case

1. Copy a non-confidential, already convergent model into an allowed root.
2. Build and manually verify the case-specific semantic registry.
3. Validate the request without opening Aspen:

   ```powershell
   uv run aspenops dry-run D:/AspenModels/request.json
   ```

4. Run one point with one worker. Enable visible mode only while troubleshooting.
5. Add at least one meaningful process constraint and one available mass, energy or elemental balance.
6. Verify the generated integrity bundle:

   ```powershell
   uv run aspenops run-batch D:/AspenModels/request.json `
     --output D:/AspenResults/results.json `
     --bundle D:/AspenResults/run-bundle.zip

   uv run aspenops verify-bundle D:/AspenResults/run-bundle.zip
   ```

7. Run independent repeats from private model copies.
8. Increase concurrency only after stability, memory and license behavior are measured.

## Licensed certification plan

A licensed certification plan must identify:

- backend (`aspen_plus` or `hysys`);
- exact approved request and model locations;
- semantic registry;
- required input perturbations and outputs;
- convergence evidence;
- constraints and balances;
- repeat count and per-output tolerances;
- expected host/license identity where policy requires it;
- signing and public-key locations outside the repository.

Validate the plan without opening COM:

```powershell
uv run aspenops certification-preflight D:/AspenModels/licensed-plan.json `
  --output D:/AspenResults/preflight.json
```

Execute only after the plan, model and exact commit have been approved:

```powershell
uv run aspenops certify-licensed D:/AspenModels/licensed-plan.json `
  --output-dir D:/AspenResults/licensed-certification
```

Verify the signed bundle with a trusted public key:

```powershell
uv run aspenops verify-licensed-bundle `
  D:/AspenResults/licensed-certification/licensed-certification-bundle.zip `
  --public-key D:/AspenKeys/aspenops-certification-public.pem
```

The runtime intentionally leaves the status as `PENDING_REAL_ASPEN_CERTIFICATION`; engineering approval is a separate human responsibility.

## Self-hosted GitHub Actions runner

The authoritative workflow is:

```text
.github/workflows/licensed-aspen-certification.yml
```

Required runner labels:

```text
self-hosted, windows, x64, aspen-licensed
```

Configure the protected GitHub environment `licensed-aspen-certification` and provide the repository/environment variables and secrets referenced by the workflow, including allowed roots, certification state directory, license metadata, signing-key path and public-key path.

Manual dispatch requires:

- repository-relative certification plan path;
- exact approved 40-character commit SHA;
- backend selection;
- explicit `approve_real_execution=true` authorization.

The workflow checks out the exact approved SHA, runs preflight, requires explicit execution approval, executes the scoped plan, verifies the signed bundle and uploads the evidence artifact. It never self-grants final engineering certification.

## Troubleshooting

### No COM server is found

Check Aspen installation, Python/Aspen bitness, Windows registry registration and any explicit ProgID pin.

### Paths are rejected

Move models, registries and output bundles into `ASPENOPS_ALLOWED_ROOTS`. Do not disable path policy as a workaround.

### Aspen returns but the point fails

Inspect convergence evidence, constraint violations, balance residuals and Aspen error/status nodes. Engine return alone is not success.

### More workers reduce throughput

Lower concurrency and measure license waiting, memory pressure, model stability and worker aging. Effective concurrency is bounded by licenses, memory and stability, not only the configured maximum.
