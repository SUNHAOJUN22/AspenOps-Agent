$ErrorActionPreference = "Stop"

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    winget install --id astral-sh.uv -e
}

uv lock --check
uv sync --frozen --extra windows --extra agent --extra dev --extra signing

if (-not (Test-Path .env)) {
    Copy-Item .env.example .env
}

uv run aspenops doctor --probe

Write-Host "Setup complete. Edit .env, keep signing keys outside the repository, and validate a non-confidential Aspen case before production use."
