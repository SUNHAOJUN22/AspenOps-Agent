param(
  [Parameter(Mandatory=$false)][string]$CasePath
)
$ErrorActionPreference = "Stop"
uv sync --extra windows --extra dev
uv run aspenops doctor --probe
if ($CasePath) {
  $env:ASPENOPS_TEST_CASE = (Resolve-Path $CasePath).Path
  uv run pytest -m aspen_integration -s
}
