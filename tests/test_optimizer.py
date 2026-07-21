from __future__ import annotations

from collections.abc import Sequence

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
