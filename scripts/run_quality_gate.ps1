$ErrorActionPreference = "Stop"
uv sync --extra dev --extra agent
uv run ruff check .
uv run mypy src/aspenops
uv run pytest
uv build
uv run aspenops demo
