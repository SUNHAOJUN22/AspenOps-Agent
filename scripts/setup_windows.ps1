$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RequiredUvVersion = [version]"0.11.16"

function Refresh-ProcessPath {
    $machinePath = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    $currentPath = $env:Path
    $env:Path = @($machinePath, $userPath, $currentPath) -join ";"
}

function Get-UvVersion {
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
        return $null
    }

    $versionText = (& uv --version 2>&1 | Out-String).Trim()
    if ($LASTEXITCODE -ne 0) {
        throw "uv --version failed"
    }
    $match = [regex]::Match($versionText, '^uv\s+(\d+\.\d+\.\d+)')
    if (-not $match.Success) {
        throw "Unable to determine the installed uv version"
    }
    return [version]$match.Groups[1].Value
}

function Install-Or-Upgrade-Uv {
    param(
        [switch]$Upgrade
    )

    $verb = if ($Upgrade) { "upgrade" } else { "install" }
    $arguments = @(
        $verb,
        "--id", "astral-sh.uv",
        "-e",
        "--accept-package-agreements",
        "--accept-source-agreements"
    )
    & winget @arguments | Out-Host
    if ($LASTEXITCODE -ne 0) {
        throw "winget failed to $verb uv"
    }
    Refresh-ProcessPath
}

function Import-DotEnv {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    $lineNumber = 0
    $seen = [System.Collections.Generic.HashSet[string]]::new(
        [System.StringComparer]::OrdinalIgnoreCase
    )

    foreach ($line in Get-Content -LiteralPath $Path) {
        $lineNumber += 1
        $entry = $line.Trim()
        if (-not $entry -or $entry.StartsWith("#")) {
            continue
        }

        $separator = $entry.IndexOf("=")
        if ($separator -lt 1) {
            throw "Invalid .env entry at line $lineNumber"
        }

        $name = $entry.Substring(0, $separator).Trim()
        $value = $entry.Substring($separator + 1).Trim()
        if ($name -notmatch '^[A-Za-z_][A-Za-z0-9_]*$') {
            throw "Invalid environment variable name at line $lineNumber"
        }
        if (-not $seen.Add($name)) {
            throw "Duplicate environment variable at line $lineNumber"
        }

        $startsDouble = $value.StartsWith('"')
        $endsDouble = $value.EndsWith('"')
        $startsSingle = $value.StartsWith("'")
        $endsSingle = $value.EndsWith("'")
        $hasQuoteBoundary = $startsDouble -or $endsDouble -or $startsSingle -or $endsSingle
        $matchingQuotes = ($startsDouble -and $endsDouble) -or ($startsSingle -and $endsSingle)
        if ($hasQuoteBoundary) {
            if ($value.Length -lt 2 -or -not $matchingQuotes) {
                throw "Unbalanced quoted value at line $lineNumber"
            }
            $value = $value.Substring(1, $value.Length - 2)
        }

        [Environment]::SetEnvironmentVariable($name, $value, "Process")
    }
}

$ObservedUvVersion = Get-UvVersion
if ($null -eq $ObservedUvVersion) {
    Install-Or-Upgrade-Uv
    $ObservedUvVersion = Get-UvVersion
} elseif ($ObservedUvVersion -lt $RequiredUvVersion) {
    Install-Or-Upgrade-Uv -Upgrade
    $ObservedUvVersion = Get-UvVersion
}

if ($null -eq $ObservedUvVersion) {
    throw "uv is unavailable after installation or upgrade"
}
if ($ObservedUvVersion -lt $RequiredUvVersion) {
    throw "uv remains below the required version after upgrade"
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
