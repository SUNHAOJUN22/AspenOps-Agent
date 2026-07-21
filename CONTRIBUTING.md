# Contributing

1. Never commit proprietary Aspen models, customer data, license files or vendor manuals.
2. Add or change semantic paths through a case-specific registry and document the Aspen version.
3. Run `uv sync --extra dev --extra agent`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy src`, the branch-coverage test gate, build, Demo, benchmark smoke and MCP surface checks before publication.
4. Real Aspen claims require the self-hosted Windows certification workflow and a non-confidential qualification case.
5. This repository keeps one persistent branch: `main`. Maintainers must not publish long-lived feature branches; use local-only worktrees or branches, validate fully, and commit atomic changes to `main` without force-pushing.
6. External contributors should submit from forks. After integration, no contributor branch is retained in this repository.
7. A change may not weaken process isolation, COM ownership, semantic allowlists, unit/bounds validation, rollback verification, convergence classification, conservation checks, license limits, evidence integrity or the `PENDING_REAL_ASPEN_CERTIFICATION` boundary.
