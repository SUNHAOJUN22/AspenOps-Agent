param(
    [Parameter(Mandatory=$true)]
    [string]$Repository,
    [string]$Branch = "agent/aspenops-1.0-production-runtime",
    [switch]$PushTag
)

$ErrorActionPreference = "Stop"
if (-not (Test-Path ".git")) { throw "Run this command from the AspenOps Git repository root." }

uv run ruff check .
uv run mypy src
uv run pytest --cov=aspenops_nexus --cov-report=term --cov-fail-under=63
uv build --clear
uv run aspenops demo
uv run python scripts/check_mcp.py

if (-not (git remote | Select-String -SimpleMatch "origin")) {
    git remote add origin $Repository
} else {
    git remote set-url origin $Repository
}

git switch -C $Branch
git add -A
git commit -m "release AspenOps 1.0 production runtime"
git push -u origin $Branch

if ($PushTag) {
    git tag -f v1.0.0
    git push origin v1.0.0 --force
}
