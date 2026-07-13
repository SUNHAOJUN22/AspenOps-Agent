# Windows Setup

## Prerequisites

- native 64-bit Windows Python 3.11–3.13;
- `uv`;
- licensed Aspen Plus and/or Aspen HYSYS installation;
- project-owned model and semantic registry;
- writeable result directory;
- known license-seat limit.

## Install

```powershell
uv sync --extra windows --extra dev --extra agent
```

## Configure

```powershell
Copy-Item .env.example .env
```

Recommended production variables:

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
ASPENOPS_VISIBLE=0
```

Use `ASPENOPS_PROGID` only to pin a known registration. Otherwise AspenOps discovers versioned registrations newest-first.

## Diagnose

```powershell
uv run aspenops doctor --probe
```

Confirm:

- native Windows host;
- pywin32 present;
- allowed roots configured;
- at least one registered Automation Server candidate;
- expected worker/license cap.

## First real case

1. Copy a non-confidential convergent model into an allowed root.
2. Build a case-specific semantic registry from Variable Explorer.
3. Run `dry-run`.
4. Run one point with one worker and visible mode if troubleshooting.
5. Add constraints and balances.
6. Run independent certification.
7. Only then increase concurrency.

## Self-hosted runner

Label the runner `Windows` and `Aspen`, set `ASPENOPS_CERT_REQUEST` to the approved request outside the repository, then manually dispatch `windows-aspen-certification.yml`.
