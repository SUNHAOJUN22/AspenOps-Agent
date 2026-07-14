import math

import pytest

from aspenops_nexus.optimizer import Candidate, better, differential_evolution


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


def test_deb_rules_and_ties_are_deterministic() -> None:
    feasible = Candidate((2.0,), objective=100.0, violation=0.0)
    infeasible = Candidate((1.0,), objective=0.0, violation=0.1)
    assert better(feasible, infeasible) is feasible

    left = Candidate((1.0,), objective=2.0, violation=0.0)
    right = Candidate((2.0,), objective=2.0, violation=0.0)
    assert better(left, right) is left
    assert better(right, left) is left

    assert better(left, right, "maximize") is left


def test_maximization_direction_is_supported() -> None:
    best = differential_evolution(
        lambda x: (-(x[0] - 1.5) ** 2, 0.0),
        [(-5.0, 5.0)],
        objective_direction="maximize",
        population_size=16,
        generations=40,
        seed=7,
    )
    assert abs(best.x[0] - 1.5) < 0.15


def test_integer_projection_is_bounded_and_repeatable() -> None:
    first = differential_evolution(
        lambda x: ((x[0] - 3.0) ** 2, 0.0),
        [(0.2, 5.8)],
        integer_indices=[0],
        population_size=8,
        generations=20,
        seed=11,
    )
    second = differential_evolution(
        lambda x: ((x[0] - 3.0) ** 2, 0.0),
        [(0.2, 5.8)],
        integer_indices=[0],
        population_size=8,
        generations=20,
        seed=11,
    )
    assert first == second
    assert first.x == (3.0,)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"bounds": []},
        {"bounds": [(2.0, 1.0)]},
        {"bounds": [(0.0, math.inf)]},
        {"bounds": [(0.0, 1.0)], "mutation": math.nan},
        {"bounds": [(0.0, 1.0)], "crossover": 2.0},
        {"bounds": [(0.1, 0.9)], "integer_indices": [0]},
    ],
)
def test_invalid_optimizer_domains_are_rejected(kwargs: dict) -> None:
    bounds = kwargs.pop("bounds")
    with pytest.raises(ValueError):
        differential_evolution(lambda x: (x[0], 0.0), bounds, **kwargs)


def test_nonfinite_evaluator_outputs_are_rejected() -> None:
    with pytest.raises(ValueError, match="finite"):
        differential_evolution(
            lambda _x: (math.nan, 0.0),
            [(0.0, 1.0)],
            population_size=4,
            generations=0,
        )
