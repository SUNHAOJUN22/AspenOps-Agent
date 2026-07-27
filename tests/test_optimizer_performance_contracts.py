from __future__ import annotations

import pytest

import aspenops_nexus.optimizer as optimizer
from aspenops_nexus.optimizer import ParetoPoint, pareto_front


def test_pareto_front_deduplicates_before_dominance_work(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    point = ParetoPoint((1.0,), (1.0, 2.0), 0.0)
    calls = 0
    original = optimizer.dominates

    def counted(left: ParetoPoint, right: ParetoPoint) -> bool:
        nonlocal calls
        calls += 1
        return original(left, right)

    monkeypatch.setattr(optimizer, "dominates", counted)
    assert pareto_front([point] * 1000) == (point,)
    assert calls == 0


def test_all_infeasible_pareto_front_keeps_only_minimum_violation() -> None:
    points = [
        ParetoPoint((0.0,), (1.0, 1.0), 2.0),
        ParetoPoint((1.0,), (9.0, 9.0), 0.5),
        ParetoPoint((2.0,), (5.0, 5.0), 0.5),
        ParetoPoint((3.0,), (0.0, 0.0), 1.0),
    ]
    front = pareto_front(points)
    assert [point.x for point in front] == [(1.0,), (2.0,)]


def test_empty_pareto_front_remains_empty() -> None:
    assert pareto_front([]) == ()
