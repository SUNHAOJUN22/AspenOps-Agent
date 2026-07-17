from __future__ import annotations

from pathlib import Path

from aspenops_nexus.config import Settings
from aspenops_nexus.optimization import OptimizationProblem, run_optimization_document
from aspenops_nexus.pool_manager import PoolManager

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "src/aspenops_nexus/data/mock-case.json"
REGISTRY = ROOT / "src/aspenops_nexus/data/node-registry.json"


def document() -> dict:
    return {
        "backend": "mock",
        "model_path": str(MODEL),
        "registry_path": str(REGISTRY),
        "workers": 2,
        "base_writes": [
            {
                "key": "stream.input.pressure",
                "identifiers": {"stream": "FEED"},
                "value": 5,
                "unit": "bar",
            },
            {
                "key": "stream.input.mass_flow",
                "identifiers": {"stream": "FEED"},
                "value": 120,
                "unit": "kg/h",
            },
            {
                "key": "block.input.stages",
                "identifiers": {"block": "COL1"},
                "value": 24,
                "unit": "1",
            },
        ],
        "reads": [
            {
                "key": "stream.output.purity",
                "identifiers": {"stream": "PRODUCT"},
                "unit": "fraction",
            },
            {
                "key": "block.output.reboiler_duty",
                "identifiers": {"block": "COL1"},
                "unit": "kW",
            },
        ],
        "constraints": [
            {
                "name": "minimum_purity",
                "key": "stream.output.purity",
                "identifiers": {"stream": "PRODUCT"},
                "operator": ">=",
                "value": 0.82,
                "unit": "fraction",
            }
        ],
        "optimization": {
            "variables": [
                {
                    "name": "temperature",
                    "key": "stream.input.temperature",
                    "identifiers": {"stream": "FEED"},
                    "kind": "continuous",
                    "lower": 60,
                    "upper": 120,
                    "unit": "C",
                },
                {
                    "name": "reflux",
                    "key": "block.input.reflux_ratio",
                    "identifiers": {"block": "COL1"},
                    "kind": "ordinal",
                    "choices": [1.5, 2.0, 2.5, 3.0],
                    "unit": "1",
                },
            ],
            "objectives": [
                {
                    "output_key": "block.output.reboiler_duty:block=COL1",
                    "direction": "minimize",
                },
                {
                    "output_key": "stream.output.purity:stream=PRODUCT",
                    "direction": "maximize",
                    "weight": 0.1,
                },
            ],
            "budget": {
                "population_size": 4,
                "generations": 1,
                "max_evaluations": 8,
                "seed": 7,
            },
        },
    }


def test_problem_decodes_mixed_variables() -> None:
    problem = OptimizationProblem.from_document(document())
    assert problem.decode((90.5, 2.2)) == {
        "temperature": 90.5,
        "reflux": 2.5,
    }
    assert problem.bounds() == ((60.0, 120.0), (0.0, 3.0))


def test_optimization_runs_batches_and_returns_pareto_archive(tmp_path: Path) -> None:
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
