from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from aspenops_nexus.batch import run_batch_document
from aspenops_nexus.config import Settings
from aspenops_nexus.models import EvaluationRequest, EvaluationResult
from aspenops_nexus.pool import CasePool
from aspenops_nexus.pool_manager import PoolManager

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "src/aspenops_nexus/data/mock-case.json"
REGISTRY = ROOT / "src/aspenops_nexus/data/node-registry.json"
FLOW = "stream.input.mass_flow:stream=FEED"


def request(
    session: str,
    step: int,
    *,
    flow: float | None = None,
    temperature: float | None = None,
    cold: bool = False,
) -> EvaluationRequest:
    writes: list[dict[str, Any]] = []
    for value, key, unit in (
        (flow, "stream.input.mass_flow", "kg/h"),
        (temperature, "stream.input.temperature", "C"),
    ):
        if value is not None:
            writes.append(
                {"key": key, "identifiers": {"stream": "FEED"}, "value": value, "unit": unit}
            )
    return EvaluationRequest.from_dict(
        {
            "model_path": str(MODEL),
            "registry_path": str(REGISTRY),
            "backend": "mock",
            "reset_mode": "reinitialize" if cold else "warm_start",
            "metadata": {"warm_start_session": session, "warm_start_step": step},
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


def pool_at(tmp_path: Path) -> CasePool:
    return CasePool(
        backend_name="mock",
        model_path=MODEL,
        registry_path=REGISTRY,
        workers=1,
        visible=False,
        cache_path=tmp_path / "cache.sqlite3",
    )


def assert_rejected(result: EvaluationResult, reason: str) -> None:
    decoded = EvaluationResult.from_dict(json.loads(json.dumps(result.to_dict(), allow_nan=False)))
    assert not decoded.ok
    assert not decoded.communication_ok
    assert not decoded.cache_hit
    assert decoded.values == {}
    assert reason in decoded.violations


def test_another_session_cannot_read_or_overwrite_live_state(tmp_path: Path) -> None:
    with pool_at(tmp_path) as pool:
        assert pool.evaluate_many([request("A", 0, flow=200)])[0].ok
        worker = pool._handles[0]
        for foreign in (request("B", 0), request("B", 1, flow=300)):
            rejected = pool.evaluate_many([foreign])[0]
            assert_rejected(rejected, "warm_start_session_mismatch")
            assert worker.evaluations == 1
        continued = pool.evaluate_many([request("A", 1)])[0]
        assert continued.ok and continued.values[FLOW] == 200
        assert worker.evaluations == 2


@pytest.mark.parametrize("replayed_step", [0, 4, 5])
def test_duplicate_or_decreasing_step_is_rejected_before_writes(
    tmp_path: Path, replayed_step: int
) -> None:
    with pool_at(tmp_path) as pool:
        assert pool.evaluate_many([request("A", 5, flow=200)])[0].ok
        rejected = pool.evaluate_many([request("A", replayed_step, flow=300)])[0]
        assert_rejected(rejected, "warm_start_step_not_increasing")
        assert pool._handles[0].evaluations == 1
        continued = pool.evaluate_many([request("A", 6)])[0]
        assert continued.ok and continued.values[FLOW] == 200


@pytest.mark.parametrize(
    "points,match",
    [
        ([request("A", 1, flow=200), request("A", 0, flow=300)], "increasing"),
        ([request("A", 0, flow=200), request("B", 1, flow=300)], "one.*session"),
        ([request("A", 0, flow=200), request("A", 0, flow=300)], "unique"),
    ],
)
def test_invalid_direct_pool_trajectory_rejects_whole_batch_before_execution(
    tmp_path: Path, points: list[EvaluationRequest], match: str
) -> None:
    with pool_at(tmp_path) as pool:
        with pytest.raises(ValueError, match=match):
            pool.evaluate_many(points)
        assert pool._handles[0].evaluations == 0


def test_executed_cold_reset_allows_a_new_session_but_cached_reset_does_not(
    tmp_path: Path,
) -> None:
    with pool_at(tmp_path) as pool:
        assert pool.evaluate_many([request("A", 0, flow=200)])[0].ok
        cold = request("unused-for-cold", 0, flow=250, cold=True)
        reset = pool.evaluate_many([cold])[0]
        assert reset.ok and not reset.cache_hit
        continued = pool.evaluate_many([request("B", 0)])[0]
        assert continued.ok and continued.values[FLOW] == 250

        cached = pool.evaluate_many([cold])[0]
        assert cached.ok and cached.cache_hit
        assert_rejected(pool.evaluate_many([request("C", 0)])[0], "warm_start_state_lost")

        fresh = pool.evaluate_many([request("cold", 0, flow=350, cold=True)])[0]
        assert fresh.ok and not fresh.cache_hit
        continued = pool.evaluate_many([request("C", 0)])[0]
        assert continued.ok and continued.values[FLOW] == 350


def test_failed_cold_reset_cannot_leave_prior_trajectory_authorized(tmp_path: Path) -> None:
    with pool_at(tmp_path) as pool:
        assert pool.evaluate_many([request("A", 0, flow=200)])[0].ok
        failed = pool.evaluate_many([request("cold", 0, flow=300, temperature=250, cold=True)])[0]
        assert not failed.ok and not failed.converged
        assert_rejected(
            pool.evaluate_many([request("A", 1, temperature=100)])[0], "warm_start_state_lost"
        )
        assert pool._handles[0].evaluations == 2


def test_dispatched_failed_warm_step_is_consumed_but_can_recover_at_next_step(
    tmp_path: Path,
) -> None:
    with pool_at(tmp_path) as pool:
        failed = pool.evaluate_many([request("A", 0, flow=200, temperature=250)])[0]
        assert not failed.ok and not failed.converged
        assert_rejected(
            pool.evaluate_many([request("A", 0, temperature=100)])[0],
            "warm_start_step_not_increasing",
        )
        recovered = pool.evaluate_many([request("A", 1, temperature=100)])[0]
        assert recovered.ok and recovered.values[FLOW] == 200
        assert pool._handles[0].evaluations == 2


def test_cancelled_before_dispatch_does_not_consume_a_step(tmp_path: Path) -> None:
    with pool_at(tmp_path) as pool:
        assert pool.evaluate_many([request("A", 0, flow=200)])[0].ok
        cancelled = pool.evaluate_many([request("A", 1, flow=300)], cancel_check=lambda: True)[0]
        assert_rejected(cancelled, "batch_cancelled")
        retried = pool.evaluate_many([request("A", 1)])[0]
        assert retried.ok and retried.values[FLOW] == 200


def test_manager_reuse_cannot_cross_warm_session_boundary(tmp_path: Path) -> None:
    settings = Settings(state_dir=tmp_path)
    manager = PoolManager(cache_path=tmp_path / "cache.sqlite3", license_slots=1)

    def batch(session: str, flow: float | None) -> dict[str, Any]:
        point = request(session, 0, flow=flow).to_dict()
        writes = point.pop("writes")
        return {**point, "workers": 1, "points": [{"writes": writes}]}

    try:
        first = run_batch_document(batch("A", 200), settings, pool_manager=manager)[0]
        assert first["ok"]
        foreign = run_batch_document(batch("B", 300), settings, pool_manager=manager)[0]
        assert not foreign["ok"]
        assert "warm_start_session_mismatch" in foreign["violations"]
        assert foreign["values"] == {}
        assert manager.stats()["created_pools"] == 1
        assert manager.stats()["reused_leases"] == 1
    finally:
        manager.close()
