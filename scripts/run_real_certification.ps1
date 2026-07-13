param(
    [Parameter(Mandatory=$true)][string]$Request,
    [string]$Output = "var/real-aspen-certification-report.json",
    [int]$Repeats = 3
)

$ErrorActionPreference = "Stop"
uv sync --extra windows --extra dev --extra agent
uv run aspenops doctor --probe
uv run aspenops dry-run $Request
uv run aspenops certify $Request --output $Output --repeats $Repeats
Write-Host "Certification report generated at $Output. Release only if passed=true and the qualification case is approved."
