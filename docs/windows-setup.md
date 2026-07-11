# Windows Setup and Real Aspen Validation

## Prerequisites

- supported Windows workstation or server;
- Aspen Plus installed and manually launchable;
- valid Aspen license;
- Python 3.11-3.13;
- `uv`;
- repository checkout on a local disk;
- a non-confidential convergent integration case.

## Install

```powershell
winget install --id astral-sh.uv -e
cd D:\src\AspenOps-Agent
uv sync --extra windows --extra dev --extra agent
```

## Probe Automation

```powershell
uv run aspenops doctor --probe
```

Confirm the returned ProgID and version correspond to the intended Aspen installation. To pin during qualification:

```powershell
$env:ASPENOPS_PROGID = "Apwn.Document.<registered-version>"
uv run aspenops doctor --probe
```

Do not copy a ProgID from another machine; enumerate the target host.

## Run a case

```powershell
uv run aspenops run-case "D:\AspenModels\integration.bkp" --timeout-s 1200
```

## Integration test

```powershell
$env:ASPENOPS_TEST_CASE = "D:\AspenModels\integration.bkp"
uv run pytest -m aspen_integration -s
```

## Self-hosted GitHub runner

Label the runner `self-hosted`, `Windows`, and `aspen-plus`. Define repository variable `ASPENOPS_TEST_CASE` with the local path. The manual workflow never uploads the model as an artifact.

## Troubleshooting order

1. launch the case manually in Aspen;
2. verify license availability;
3. run `doctor --probe`;
4. confirm Python and Aspen bitness/registration views;
5. validate semantic paths in Variable Explorer;
6. run one worker and one known operating point;
7. inspect returned status/messages;
8. increase worker count only after the baseline is stable.
