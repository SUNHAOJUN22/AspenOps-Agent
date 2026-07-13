# Contributing

1. Never commit proprietary Aspen models, customer data, license files or vendor manuals.
2. Add or change semantic paths through a case-specific registry and document the Aspen version.
3. Run `uv sync --extra dev --extra agent`, then `uv run ruff check .`, `uv run mypy src`, and `uv run pytest`.
4. Real Aspen claims require the self-hosted Windows certification workflow and a non-confidential qualification case.
5. Submit changes through a branch and pull request. Keep `main` releasable.
