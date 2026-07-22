$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RequiredUvVersion = [version]"0.11.16"

function Refresh-ProcessPath {
    $machinePath = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    $currentPath = $env:Path
    $env:Path = @($machinePath, $userPath, $currentPath) -join ";"
}

function Import-DotEnv {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    foreach ($line in Get-Content -LiteralPath $Path) {
        $entry = $line.Trim()
        if (-not $entry -or $entry.StartsWith("#")) {
            continue
        }

        $separator = $entry.IndexOf("=")
        if ($separator -lt 1) {
            throw "Invalid .env entry: $entry"
        }

        $name = $entry.Substring(0, $separator).Trim()
        $value = $entry.Substring($separator + 1).Trim()
        if ($name -notmatch '^[A-Za-z_][A-Za-z0-9_]*$') {
            throw "Invalid environment variable name in .env: $name"
        }

        if ($value.Length -ge 2) {
            $doubleQuoted = $value.StartsWith('"') -and $value.EndsWith('"')
            $singleQuoted = $value.StartsWith("'") -and $value.EndsWith("'")
            if ($doubleQuoted -or $singleQuoted) {
                $value = $value.Substring(1, $value.Length - 2)
            }
        }

        [Environment]::SetEnvironmentVariable($name, $value, "Process")
    }
}

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    winget install --id astral-sh.uv -e --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) {
        throw "winget failed to install uv"
    }
    Refresh-ProcessPath
}

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw "uv is not available after installation. Open a new PowerShell session and rerun this script."
}

$uvVersionText = (uv --version).Trim()
if ($LASTEXITCODE -ne 0) {
    throw "uv --version failed"
}
$uvVersionMatch = [regex]::Match($uvVersionText, '^uv\s+(\d+\.\d+\.\d+)')
if (-not $uvVersionMatch.Success) {
    throw "Unable to determine the installed uv version: $uvVersionText"
}
$ObservedUvVersion = [version]$uvVersionMatch.Groups[1].Value
if ($ObservedUvVersion -lt $RequiredUvVersion) {
    throw "uv $ObservedUvVersion is too old; AspenOps requires uv $RequiredUvVersion or newer"
}

uv lock --check
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

uv sync --frozen --extra windows --extra agent --extra dev --extra signing
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if (-not (Test-Path -LiteralPath .env)) {
    Copy-Item -LiteralPath .env.example -Destination .env
}

Import-DotEnv -Path .env
uv run aspenops doctor --probe
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if ($env:ASPENOPS_BACKEND -eq "mock") {
    Write-Host "Portable setup passed with the Mock backend. Edit .env for Aspen Plus or HYSYS, then rerun this script before a real case."
} else {
    Write-Host "Windows setup and configured backend diagnostics passed. Validate a non-confidential case with one worker before production use."
}

Write-Host "Keep signing keys, licenses, proprietary models, and confidential evidence outside the repository."
