# Windows Setup

## Scope

This guide covers deterministic Windows installation, the public Windows control-plane gate, first real Aspen Plus or HYSYS execution, and protected licensed certification. Mock and Fake-COM validation are not real Aspen physical certification.

## Prerequisites

- native 64-bit Windows;
- Python 3.11–3.13;
- `winget` or `uv >= 0.11.16`;
- licensed Aspen Plus and/or Aspen HYSYS for real execution;
- a known license-seat limit;
- a non-confidential model already convergent in the GUI;
- a verified semantic registry or HYSYS Spreadsheet Contract;
- non-empty absolute existing `ASPENOPS_ALLOWED_ROOTS`;
- absolute state, model, registry, output and evidence paths inside those roots.

Real-backend Settings fail before preflight when roots are missing, relative or do not contain the state directory.

## Bootstrap

```powershell
powershell -ExecutionPolicy Bypass -File scripts/setup_windows.ps1
```

The script enables strict PowerShell, installs or upgrades `uv`, rechecks the actual version, preserves PATH, checks `uv.lock`, runs frozen synchronization, imports `.env`, rejects duplicate variables and unbalanced quotes, reports failures without echoing raw secrets, and runs `doctor --probe`.

```powershell
uv lock --check
uv sync --frozen --extra windows --extra agent --extra dev --extra signing
```

## Public Windows gate

`windows-control-plane.yml` uses pinned `windows-2025`, Python 3.12 and `uv 0.11.16`. It validates PowerShell AST/helper behavior, dotenv safety, Job Objects, process ownership, IPC/recovery, Fake Aspen Plus/HYSYS, archives, path policy, documentation, CLI and Doctor.

The archived Windows baseline recorded 104 passing tests. No current count is claimed without readable JUnit evidence.

## Protected licensed certification

```text
ubuntu-24.04 dispatch guard
→ self-hosted, windows, x64, aspen-licensed certification job
```

A non-main dispatch exits with status 2. The licensed job has `needs: dispatch-guard`, so invalid dispatches never occupy the licensed host.

### Dispatch-SHA binding

`expected_head_sha` must equal this `refs/heads/main` dispatch's `GITHUB_SHA`. The workflow verifies the initial `actions/checkout` HEAD equals `GITHUB_SHA`, confirms the SHA remains an ancestor of `origin/main`, and detached-checks out the same SHA.

This keeps the workflow definition, runtime code, tests and path validator on one commit. An operator cannot select an older main ancestor to roll back current safety controls.

### Pre-checkout runner-temp artifact directory

Before checkout, the self-hosted job deletes and recreates:

```text
$RUNNER_TEMP/aspenops-licensed-artifact-<GITHUB_RUN_ID>-<GITHUB_RUN_ATTEMPT>
```

`run-metadata.txt` is created before checkout. It records the run ID, attempt, ref, `GITHUB_SHA` and `expected_head_sha`. The Mock JUnit file, copied licensed evidence and final `job_status` remain in this directory.

The final upload uses:

```text
${{ runner.temp }}/aspenops-licensed-artifact-${{ github.run_id }}-${{ github.run_attempt }}
```

It sets `if-no-files-found: error`. Checkout or setup failure therefore cannot upload stale `var/ci` from the persistent self-hosted workspace.

### Per-run-attempt external evidence

All real certification jobs use the fixed concurrency group `licensed-aspen-certification`, serializing Aspen Plus and HYSYS runs.

```text
ASPENOPS_STATE_DIR/licensed-certification/<GITHUB_RUN_ID>-<GITHUB_RUN_ATTEMPT>
```

The directory is removed and recreated, then exported as `LICENSED_EVIDENCE_DIR`. Preflight, real execution, bundle verification, report inspection and runner-temp staging all use that path. Artifact names contain `github.run_id` and `github.run_attempt`.

```text
Ubuntu guard requires GITHUB_REF == refs/heads/main
→ create and clean the run-attempt runner-temp artifact directory
→ actions/checkout this dispatch's GITHUB_SHA
→ verify expected_head_sha == GITHUB_SHA
→ verify initial HEAD and main ancestry
→ detached checkout the same GITHUB_SHA
→ run Mock regression with JUnit in runner temp
→ create run_id-run_attempt external evidence directory
→ realpath → preflight → approval → real COM
→ verify signed bundle and evidence files
→ copy evidence into runner-temp/licensed-evidence
→ record job_status → upload runner temp → human review
```

Security properties:

- invalid refs fail rather than becoming skipped;
- `needs: dispatch-guard` protects the licensed host;
- certification jobs are serialized;
- runner-temp and external evidence are isolated per attempt;
- checkout failures cannot expose stale workspace diagnostics;
- traversal, symlink and junction escapes are rejected;
- signing secrets are absent from setup and Mock regression;
- software cannot self-grant final certification.

## Troubleshooting

- Keep `uv lock --check` and `--frozen`; never hide lock drift.
- Rerun the bootstrap when `uv` is old.
- Fix the reported `.env` line without printing raw values.
- Configure absolute roots and a state path inside one root.
- Treat Aspen engine return as insufficient without convergence, constraints and balances.
