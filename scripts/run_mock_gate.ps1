$ErrorActionPreference = "Stop"
uv sync --extra dev --extra agent
uv run ruff check .
uv run mypy src
uv run pytest --cov=aspenops_nexus --cov-report=term-missing
uv build
uv run aspenops demo
uv run aspenops benchmark --points 12 --workers 1,2,4
