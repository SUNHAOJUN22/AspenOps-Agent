from __future__ import annotations

import json
from pathlib import Path

from aspenops_nexus.config import Settings
from aspenops_nexus.optimization import OptimizationProblem, run_optimization_document
from aspenops_nexus.pool_manager import PoolManager

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "optimization-request.example.json"


def document() -> dict:
    value = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_problem_decodes_mixed_variables() -> None:
    problem = OptimizationProblem.from_document(document())
    assert problem.decode((90.5, 2.2)) == {
        "temperature": 90.5,
        "reflux": 2.5,
    }
    assert problem.bounds() == ((60.0, 120.0), (0.0, 3.0))


def test_published_example_runs_batches_and_returns_pareto_archive(tmp_path: Path) -> None:
    settings = Settings(state_dir=tmp_path, max_workers=2, license_slots=2)
    with PoolManager(
        cache_path=tmp_path / "cache.sqlite3",
        license_slots=2,
        max_resident_cases=1,
    ) as pool_manager:
        result = run_optimization_document(
            document(),
            settings,
            pool_manager=pool_manager,
        )
        stats = pool_manager.stats()
    assert result["status"] == "completed"
    assert result["evaluations"] == 8
    assert result["generations"] == 1
    assert result["best"] is not None
    assert result["pareto"]
    assert result["qualification"] == "control-plane-only"
    assert result["real_aspen_status"] == "PENDING_REAL_ASPEN_CERTIFICATION"
    assert stats["created_pools"] == 1
    assert stats["reused_leases"] >= 1
