from __future__ import annotations

import math
import random
import sys
from pathlib import Path
from typing import Any

import pytest

import aspenops_nexus.pool as pool_module
from aspenops_nexus.evaluation import _constraint_violation, _safe_fsum
from aspenops_nexus.models import ConstraintSpec, EvaluationRequest, EvaluationResult
from aspenops_nexus.optimizer import ParetoPoint, _pareto_front_general, pareto_front
from aspenops_nexus.pool import CasePool
from aspenops_nexus.units import convert, supported_units
from aspenops_nexus.worker import WorkerHandle


def _request() -> EvaluationRequest:
    return EvaluationRequest.from_dict(
        {
            "model_path": "model.bkp",
            "registry_path": "registry.json",
            "backend": "mock",
            "writes": [],
            "reads": [],
        }
    )


def _result(handle: WorkerHandle) -> EvaluationResult:
    return EvaluationResult(
        ok=True,
        communication_ok=True,
        engine_ok=True,
        converged=True,
        feasible=True,
        values={"value": 1.0},
        units={"value": "1"},
        violations=[],
        diagnostics={"nested": {"value": 1}},
        elapsed_s=0.0,
        worker_id=handle.worker_id,
    )


def test_safe_fsum_recovers_exact_cancellation_after_intermediate_overflow() -> None:
    maximum = sys.float_info.max
    assert _safe_fsum([maximum, maximum, -maximum, -maximum]) == 0.0


def test_safe_fsum_preserves_true_overflow_sign() -> None:
    maximum = sys.float_info.max
    positive = _safe_fsum([maximum, maximum])
    negative = _safe_fsum([-maximum, -maximum])
    assert math.isinf(positive) and positive > 0.0
    assert math.isinf(negative) and negative < 0.0


def test_constraint_tolerance_semantics_are_consistent() -> None:
    def spec(operator: str) -> ConstraintSpec:
        return ConstraintSpec.from_dict(
            {
                "key": "x",
                "operator": operator,
                "value": 10.0,
                "tolerance": 0.5,
            }
        )

    assert _constraint_violation(spec("<"), 9.5) == 0.0
    assert _constraint_violation(spec("<"), 10.0) == 0.5
    assert _constraint_violation(spec("<="), 10.5) == 0.0
    assert _constraint_violation(spec(">"), 10.5) == 0.0
    assert _constraint_violation(spec(">"), 10.0) == 0.5
    assert _constraint_violation(spec(">="), 9.5) == 0.0
    assert _constraint_violation(spec("=="), 10.5) == 0.0
    assert _constraint_violation(spec("=="), 10.75) == 0.25


def test_supported_unit_conversions_round_trip() -> None:
    units = supported_units()
    grouped: dict[str, list[str]] = {}
    for unit, dimension in units.items():
        grouped.setdefault(dimension, []).append(unit)
    samples = (0.0, 1.0, 123.456)
    for compatible in grouped.values():
        for source in compatible:
            for target in compatible:
                for value in samples:
                    restored = convert(convert(value, source, target), target, source)
                    assert math.isclose(restored, value, rel_tol=1e-12, abs_tol=1e-9)
    assert math.isclose(convert(32.0, "F", "C"), 0.0, abs_tol=1e-12)
    assert math.isclose(convert(212.0, "F", "C"), 100.0, abs_tol=1e-12)
    assert math.isclose(convert(100.0, "%", "fraction"), 1.0, abs_tol=1e-15)


def test_two_objective_front_matches_general_definition() -> None:
    rng = random.Random(20260802)
    for _ in range(80):
        points = tuple(
            ParetoPoint(
                (float(index),),
                (float(rng.randrange(-8, 9)), float(rng.randrange(-8, 9))),
            )
            for index in range(40)
        )
        unique = tuple(dict.fromkeys(points))
        assert set(pareto_front(points)) == set(_pareto_front_general(unique))


def test_single_worker_dispatch_avoids_heavy_queue_and_thread(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class AliveProcess:
        def is_alive(self) -> bool:
            return True

    class Cache:
        def get_many(self, keys: list[str]) -> dict[str, dict[str, Any]]:
            del keys
            return {}

        def put_many(self, payloads: dict[str, dict[str, Any]]) -> None:
            assert not payloads

    pool = object.__new__(CasePool)
    pool._handles = [
        WorkerHandle(
            worker_id=0,
            process=AliveProcess(),
            connection=object(),  # type: ignore[arg-type]
            staged_model=Path("model.bkp"),
            runtime={"backend": "mock"},
        )
    ]
    pool.cache = Cache()  # type: ignore[assignment]
    pool.cache_failures = False
    pool._key_requests = lambda requests: [  # type: ignore[method-assign]
        (f"key-{index}", request) for index, request in enumerate(requests)
    ]
    pool._recycle_reason = lambda handle: None  # type: ignore[method-assign]
    pool._result_recycle_reason = (  # type: ignore[method-assign]
        lambda handle, active_result: None
    )
    pool._cacheable = lambda request, active_result: False  # type: ignore[method-assign]

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        del args, kwargs
        raise AssertionError("single-worker dispatch must not construct Queue or Thread")

    monkeypatch.setattr(pool_module.queue, "Queue", forbidden)
    monkeypatch.setattr(pool_module.threading, "Thread", forbidden)
    monkeypatch.setattr(pool_module, "evaluate_on_worker", lambda handle, request: _result(handle))

    results = pool._evaluate_many_locked([_request()] * 4, cancel_check=None)
    assert len(results) == 4
    assert [item.request_hash for item in results] == [f"key-{index}" for index in range(4)]
