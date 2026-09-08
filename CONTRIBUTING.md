# Contributing to AspenOps 2.0

1. Never commit proprietary Aspen models, customer data, license files, vendor manuals, signing keys or confidential evidence.
2. Add or change semantic paths only through a case-specific registry, and document the tested Aspen backend and version scope.
3. Keep `main` as the only persistent branch. Maintainers must not publish long-lived feature branches or force-push. External contributors submit from forks; contributor branches are not retained in this repository after integration.
4. Before publication, run:

   ```bash
   uv lock --check
   uv sync --frozen --extra dev --extra agent --extra signing
   uv run ruff check .
   uv run ruff format --check .
   uv run mypy src
   uv run python -m compileall -q src scripts
   uv run python scripts/audit_source_tree.py
   uv run pytest -W error::ResourceWarning \
     --cov=aspenops_nexus \
     --cov-branch \
     --cov-fail-under=95.0
   uv build
   uv run python scripts/check_mcp.py
   uv run python scripts/check_wheel_metadata.py --dist-dir dist
   uv run aspenops --version
   uv run aspenops demo
   ```

   Add `--extra windows` on Windows. The authoritative CI also audits the frozen dependency graph for Linux and Windows across Python 3.11, 3.12 and 3.13, performs full-source compilation and deterministic AST auditing, runs exact Bandit `1.9.4` high/high analysis, and reruns the complete Python 3.12 suite in reverse and seeded-random order.
5. Update tests and user-facing documentation in the same change. Do not weaken workflow pinning, documentation contracts, dependency evidence, path policy or signed-evidence staging.
6. Real Aspen claims require the protected self-hosted Windows certification workflow, an exact trusted-`main` commit, a non-confidential qualification case and human engineering review.
7. A change may not weaken process isolation, COM ownership, semantic allowlists, unit and bounds validation, rollback verification, convergence classification, conservation checks, license limits, evidence integrity or the `PENDING_REAL_ASPEN_CERTIFICATION` boundary.
