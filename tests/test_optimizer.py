from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import pytest

from aspenops_nexus.optimizer import (
    ParetoPoint,
    differential_evolution,
    differential_evolution_batch,
    pareto_front,
)


def test_differential_evolution_finds_quadratic_minimum() -> None:
    best = differential_evolution(
        lambda x: ((x[0] - 2.0) ** 2, 0.0),
        [(-5.0, 5.0)],
        population_size=12,
        generations=30,
        seed=4,
    )
    assert abs(best.x[0] - 2.0) < 0.1
    assert best.feasible


def test_batch_differential_evolution_calls_once_per_generation() -> None:
    batch_sizes: list[int] = []

    def evaluate_many(
        vectors: Sequence[tuple[float, ...]],
    ) -> Sequence[tuple[float, float]]:
        batch_sizes.append(len(vectors))
        return [((vector[0] - 1.0) ** 2, 0.0) for vector in vectors]

    result = differential_evolution_batch(
        evaluate_many,
        [(-5.0, 5.0)],
        population_size=8,
        generations=10,
        max_evaluations=24,
        seed=3,
    )
    assert batch_sizes == [8, 8, 8]
    assert result.evaluations == 24
    assert result.generations == 2
    assert result.best.feasible


def test_pareto_front_respects_feasibility_and_nondominance() -> None:
    points = [
        ParetoPoint((0.0,), (1.0, 3.0), 0.0),
        ParetoPoint((1.0,), (2.0, 2.0), 0.0),
        ParetoPoint((2.0,), (3.0, 1.0), 0.0),
        ParetoPoint((3.0,), (4.0, 4.0), 0.0),
        ParetoPoint((4.0,), (0.0, 0.0), 1.0),
    ]
    front = pareto_front(points)
    assert {point.x for point in front} == {(0.0,), (1.0,), (2.0,)}


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("population_size", True),
        ("population_size", 4.0),
        ("population_size", float("nan")),
        ("population_size", float("inf")),
        ("generations", True),
        ("generations", 1.5),
        ("generations", float("nan")),
        ("generations", float("inf")),
        ("generations", "2"),
        ("max_evaluations", True),
        ("max_evaluations", 4.5),
        ("max_evaluations", float("nan")),
        ("max_evaluations", float("inf")),
        ("max_evaluations", "8"),
    ],
)
def test_invalid_counts_fail_before_evaluation_or_checkpoint(field: str, value: Any) -> None:
    evaluated: list[tuple[float, ...]] = []
    checkpoints: list[int] = []

    def evaluate_many(vectors: Sequence[tuple[float, ...]]) -> list[tuple[float, float]]:
        evaluated.extend(vectors)
        return [(0.0, 0.0) for _ in vectors]

    options: dict[str, Any] = {"population_size": 4, "generations": 2}
    options[field] = value
    with pytest.raises(ValueError, match=field):
        differential_evolution_batch(
            evaluate_many,
            [(0.0, 1.0)],
            checkpoint=lambda generation, population, count: checkpoints.append(generation),
            **options,
        )
    assert evaluated == []
    assert checkpoints == []


def test_unrepresentable_bound_width_fails_before_evaluation() -> None:
    evaluated: list[tuple[float, ...]] = []

    def evaluate_many(vectors: Sequence[tuple[float, ...]]) -> list[tuple[float, float]]:
        evaluated.extend(vectors)
        return [(0.0, 0.0) for _ in vectors]

    with pytest.raises(ValueError, match="bound"):
        differential_evolution_batch(
            evaluate_many,
            [(-1e308, 1e308)],
            population_size=4,
            generations=0,
        )
    assert evaluated == []


@pytest.mark.parametrize(
    ("generations", "budget", "expected"),
    [(0, 4, 4), (5, 4, 4), (5, 9, 8)],
)
def test_valid_integer_budgets_preserve_batch_accounting(
    generations: int, budget: int, expected: int
) -> None:
    evaluated: list[tuple[float, ...]] = []

    def evaluate_many(vectors: Sequence[tuple[float, ...]]) -> list[tuple[float, float]]:
        evaluated.extend(vectors)
        return [(vector[0] ** 2, 0.0) for vector in vectors]

    result = differential_evolution_batch(
        evaluate_many,
        [(-1.0, 1.0)],
        population_size=4,
        generations=generations,
        max_evaluations=budget,
    )
    assert result.evaluations == expected == len(evaluated)
    assert result.generations == expected // 4 - 1
