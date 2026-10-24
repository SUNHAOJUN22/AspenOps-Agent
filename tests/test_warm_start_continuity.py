from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from aspenops_nexus.models import EvaluationRequest
from aspenops_nexus.pool import CasePool
from aspenops_nexus.scheduler import BackgroundScheduler

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "src/aspenops_nexus/data/mock-case.json"
REGISTRY = ROOT / "src/aspenops_nexus/data/node-registry.json"
FLOW = "stream.input.mass_flow:stream=FEED"


def request(step: int, *, flow: float | None = None, cold: bool = False) -> EvaluationRequest:
    writes: list[dict[str, Any]] = []
    if flow is not None:
        writes.append(
            {
                "key": "stream.input.mass_flow",
                "identifiers": {"stream": "FEED"},
                "value": flow,
                "unit": "kg/h",
            }
        )
    return EvaluationRequest.from_dict(
        {
            "model_path": str(MODEL),
            "registry_path": str(REGISTRY),
            "backend": "mock",
            "reset_mode": "reinitialize" if cold else "warm_start",
            "metadata": {"warm_start_session": "continuation", "warm_start_step": step},
            "writes": writes,
            "reads": [
                {
                    "key": "stream.input.mass_flow",
                    "identifiers": {"stream": "FEED"},
                    "unit": "kg/h",
                }
            ],
        }
    )


def pool_at(tmp_path: Path, *, points: int = 20) -> CasePool:
    return CasePool(
        backend_name="mock",
        model_path=MODEL,
        registry_path=REGISTRY,
        workers=1,
        visible=False,
        cache_path=tmp_path / "cache.sqlite3",
        worker_max_points=points,
    )


def test_uninterrupted_warm_start_retains_inputs_across_batch_and_calls(tmp_path: Path) -> None:
    with pool_at(tmp_path) as pool:
        results = pool.evaluate_many([request(0, flow=200), request(1)])
        results.extend(pool.evaluate_many([request(2)]))
        assert all(item.ok and item.values[FLOW] == 200 for item in results)
        assert all(not item.cache_hit for item in results)
        assert pool.cache.stats()["entries"] == 0


def test_point_budget_cannot_silently_restart_warm_start(tmp_path: Path) -> None:
    with pool_at(tmp_path, points=1) as pool:
        first, second = pool.evaluate_many([request(0, flow=200), request(1)])
        assert first.ok and first.values[FLOW] == 200
        assert not second.ok
        assert "warm_start_state_lost" in second.violations
        assert second.values == {}
        assert BackgroundScheduler._last_completed_point([first.to_dict(), second.to_dict()]) == 0


@pytest.mark.parametrize("disruption", ["force_recycle", "crash", "age", "close"])
def test_warm_start_detects_lost_state_between_calls(tmp_path: Path, disruption: str) -> None:
    with pool_at(tmp_path) as pool:
        assert pool.evaluate_many([request(0, flow=200)])[0].ok
        if disruption == "force_recycle":
            pool.force_recycle_all()
        elif disruption == "crash":
            pool._handles[0].process.terminate()
            pool._handles[0].process.join(timeout=5)
        elif disruption == "age":
            pool._handles[0].started_monotonic -= pool.worker_max_age_s + 1
        else:
            pool.close()
        result = pool.evaluate_many([request(1)])[0]
        assert not result.ok
        assert "warm_start_state_lost" in result.violations
        assert result.values == {}


def test_cached_cold_result_does_not_restore_state_but_new_cold_solve_does(tmp_path: Path) -> None:
    with pool_at(tmp_path) as pool:
        cold = request(0, flow=200, cold=True)
        assert pool.evaluate_many([cold])[0].ok
        pool.force_recycle_all()
        cached = pool.evaluate_many([cold])[0]
        assert cached.ok and cached.cache_hit
        blocked = pool.evaluate_many([request(1)])[0]
        assert not blocked.ok and "warm_start_state_lost" in blocked.violations
        actual = pool.evaluate_many([request(0, flow=250, cold=True)])[0]
        assert actual.ok and not actual.cache_hit
        continued = pool.evaluate_many([request(1)])[0]
        assert continued.ok and continued.values[FLOW] == 250


def test_nonconverged_solve_can_recover_if_live_state_is_retained(tmp_path: Path) -> None:
    bad = request(0, flow=200).to_dict()
    bad["writes"].append(
        {
            "key": "stream.input.temperature",
            "identifiers": {"stream": "FEED"},
            "value": 250,
            "unit": "C",
        }
    )
    recovery = request(1).to_dict()
    recovery["writes"].append(
        {
            "key": "stream.input.temperature",
            "identifiers": {"stream": "FEED"},
            "value": 100,
            "unit": "C",
        }
    )
    with pool_at(tmp_path) as pool:
        first, second = pool.evaluate_many(
            [EvaluationRequest.from_dict(bad), EvaluationRequest.from_dict(recovery)]
        )
        assert not first.ok and not first.converged
        assert second.ok and second.values[FLOW] == 200
        assert pool._handles[0].evaluations == 2


def test_constraint_failure_does_not_discard_a_converged_state(tmp_path: Path) -> None:
    constrained = request(0, flow=200).to_dict()
    constrained["constraints"] = [
        {
            "key": "stream.input.mass_flow",
            "identifiers": {"stream": "FEED"},
            "operator": "<=",
            "value": 100,
            "unit": "kg/h",
        }
    ]
    with pool_at(tmp_path) as pool:
        first, second = pool.evaluate_many([EvaluationRequest.from_dict(constrained), request(1)])
        assert not first.ok and first.converged
        assert second.ok and second.values[FLOW] == 200


def test_executed_cold_recovery_separates_state_from_constraint_acceptance(tmp_path: Path) -> None:
    constrained = request(0, flow=250, cold=True).to_dict()
    constrained["constraints"] = [
        {
            "key": "stream.input.mass_flow",
            "identifiers": {"stream": "FEED"},
            "operator": "<=",
            "value": 100,
            "unit": "kg/h",
        }
    ]
    with pool_at(tmp_path) as pool:
        pool.force_recycle_all()
        first = pool.evaluate_many([EvaluationRequest.from_dict(constrained)])[0]
        assert not first.ok and first.converged
        second = pool.evaluate_many([request(1)])[0]
        assert second.ok and second.values[FLOW] == 250
