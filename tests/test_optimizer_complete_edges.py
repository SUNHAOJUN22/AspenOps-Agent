from __future__ import annotations

from collections.abc import Sequence

import pytest

from aspenops_nexus import optimizer as optimizer_module
from aspenops_nexus.optimizer import (
    Candidate,
    ParetoPoint,
    better,
    differential_evolution,
    differential_evolution_batch,
    dominates,
    pareto_front,
)


def test_candidate_and_pareto_feasibility_boundaries() -> None:
    assert Candidate((0.0,), 1.0, 0.0).feasible is True
    assert Candidate((0.0,), 1.0, -1.0).feasible is True
    assert Candidate((0.0,), 1.0, 1e-12).feasible is False
    assert ParetoPoint((0.0,), (1.0,), 0.0).feasible is True
    assert ParetoPoint((0.0,), (1.0,), 1.0).feasible is False


def test_better_exercises_all_deb_ordering_branches() -> None:
    feasible_low = Candidate((0.0,), 1.0, 0.0)
    feasible_high = Candidate((1.0,), 2.0, 0.0)
    infeasible_low = Candidate((2.0,), -100.0, 1.0)
    infeasible_high = Candidate((3.0,), -200.0, 2.0)

    assert better(feasible_low, infeasible_low) is feasible_low
    assert better(infeasible_low, feasible_high) is feasible_high
    assert better(feasible_low, feasible_high) is feasible_low
    assert better(feasible_high, feasible_low) is feasible_low
    assert better(infeasible_low, infeasible_high) is infeasible_low
    assert better(infeasible_high, infeasible_low) is infeasible_low


def test_dominates_exercises_feasible_infeasible_and_equal_points() -> None:
    feasible = ParetoPoint((0.0,), (2.0, 2.0), 0.0)
    infeasible_low = ParetoPoint((1.0,), (0.0, 0.0), 1.0)
    infeasible_high = ParetoPoint((2.0,), (-1.0, -1.0), 2.0)
    better_point = ParetoPoint((3.0,), (1.0, 2.0), 0.0)
    tradeoff = ParetoPoint((4.0,), (3.0, 1.0), 0.0)
    equal = ParetoPoint((5.0,), (2.0, 2.0), 0.0)

    assert dominates(feasible, infeasible_low) is True
    assert dominates(infeasible_low, feasible) is False
    assert dominates(infeasible_low, infeasible_high) is True
    assert dominates(infeasible_high, infeasible_low) is False
    assert dominates(better_point, feasible) is True
    assert dominates(feasible, tradeoff) is False
    assert dominates(feasible, equal) is False
    with pytest.raises(ValueError):
        dominates(
            ParetoPoint((0.0,), (1.0,), 0.0),
            ParetoPoint((1.0,), (1.0, 2.0), 0.0),
        )


def test_pareto_front_removes_dominated_and_duplicate_points() -> None:
    duplicate = ParetoPoint((0.0,), (1.0, 1.0), 0.0)
    points = [
        duplicate,
        duplicate,
        ParetoPoint((1.0,), (2.0, 2.0), 0.0),
        ParetoPoint((2.0,), (0.0, 0.0), 1.0),
    ]
    assert pareto_front(points) == (duplicate,)
    assert pareto_front([]) == ()


@pytest.mark.parametrize(
    ("bounds", "population_size", "generations", "mutation", "crossover", "message"),
    [
        ([], 4, 1, 0.8, 0.9, "bounds must not be empty"),
        ([(0.0, 1.0)], 3, 1, 0.8, 0.9, "population_size"),
        ([(0.0, 1.0)], 4, -1, 0.8, 0.9, "generations"),
        ([(0.0, 1.0)], 4, 1, 0.0, 0.9, "mutation"),
        ([(0.0, 1.0)], 4, 1, float("nan"), 0.9, "mutation"),
        ([(0.0, 1.0)], 4, 1, 0.8, -0.1, "crossover"),
        ([(0.0, 1.0)], 4, 1, 0.8, float("nan"), "crossover"),
        ([(1.0, 1.0)], 4, 1, 0.8, 0.9, "bound"),
        ([(2.0, 1.0)], 4, 1, 0.8, 0.9, "bound"),
        ([(float("nan"), 1.0)], 4, 1, 0.8, 0.9, "bound"),
        ([(0.0, float("inf"))], 4, 1, 0.8, 0.9, "bound"),
    ],
)
def test_validate_parameters_fails_closed(
    bounds: list[tuple[float, float]],
    population_size: int,
    generations: int,
    mutation: float,
    crossover: float,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        optimizer_module._validate_parameters(
            bounds,
            population_size,
            generations,
            mutation,
            crossover,
        )


def test_explicit_zero_budget_is_rejected_instead_of_using_default() -> None:
    with pytest.raises(ValueError, match="initial population"):
        differential_evolution_batch(
            lambda vectors: [(0.0, 0.0) for _ in vectors],
            [(0.0, 1.0)],
            population_size=4,
            generations=1,
            max_evaluations=0,
        )


def test_batch_score_count_must_match_population() -> None:
    with pytest.raises(ValueError, match="different number of scores"):
        differential_evolution_batch(
            lambda vectors: [(0.0, 0.0)],
            [(0.0, 1.0)],
            population_size=4,
            generations=0,
        )


@pytest.mark.parametrize(
    "score",
    [
        (float("nan"), 0.0),
        (float("inf"), 0.0),
        (0.0, float("nan")),
        (0.0, float("inf")),
    ],
)
def test_batch_rejects_nonfinite_scores(score: tuple[float, float]) -> None:
    with pytest.raises(ValueError, match="non-finite score"):
        differential_evolution_batch(
            lambda vectors: [score for _ in vectors],
            [(0.0, 1.0)],
            population_size=4,
            generations=0,
        )


def test_negative_violations_are_clamped_and_checkpointed() -> None:
    events: list[tuple[int, int, int]] = []

    def evaluate_many(
        vectors: Sequence[tuple[float, ...]],
    ) -> Sequence[tuple[float, float]]:
        return [(sum(value * value for value in vector), -1.0) for vector in vectors]

    def checkpoint(
        generation: int,
        population: tuple[Candidate, ...],
        evaluations: int,
    ) -> None:
        events.append((generation, len(population), evaluations))

    result = differential_evolution_batch(
        evaluate_many,
        [(-1.0, 1.0), (-2.0, 2.0)],
        population_size=4,
        generations=2,
        max_evaluations=8,
        seed=3,
        checkpoint=checkpoint,
    )
    assert result.evaluations == 8
    assert result.generations == 1
    assert events == [(0, 4, 4), (1, 4, 8)]
    assert all(candidate.violation == 0.0 for candidate in result.population)
    assert result.best.feasible is True
    assert all(-1.0 <= candidate.x[0] <= 1.0 for candidate in result.population)
    assert all(-2.0 <= candidate.x[1] <= 2.0 for candidate in result.population)


def test_default_budget_runs_requested_generations() -> None:
    calls: list[int] = []

    def evaluate_many(
        vectors: Sequence[tuple[float, ...]],
    ) -> Sequence[tuple[float, float]]:
        calls.append(len(vectors))
        return [(vector[0], 0.0) for vector in vectors]

    result = differential_evolution_batch(
        evaluate_many,
        [(0.0, 1.0)],
        population_size=4,
        generations=2,
        seed=2,
    )
    assert calls == [4, 4, 4]
    assert result.evaluations == 12
    assert result.generations == 2


def test_scalar_compatibility_wrapper_returns_best_candidate() -> None:
    seen: list[tuple[float, ...]] = []

    def evaluate(vector: tuple[float, ...]) -> tuple[float, float]:
        seen.append(vector)
        return (abs(vector[0] - 0.25), 0.0)

    best = differential_evolution(
        evaluate,
        [(0.0, 1.0)],
        population_size=4,
        generations=0,
        seed=5,
    )
    assert len(seen) == 4
    assert best in [Candidate(vector, abs(vector[0] - 0.25), 0.0) for vector in seen]
