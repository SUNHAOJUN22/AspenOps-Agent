from __future__ import annotations

from decimal import Decimal
from fractions import Fraction
from typing import Any

import pytest

from aspenops_nexus.optimizer import ParetoPoint, differential_evolution_batch, pareto_front


@pytest.mark.parametrize("score_index", [0, 1])
@pytest.mark.parametrize(
    "value",
    [
        True,
        "0.5",
        b"0.5",
        None,
        complex(1, 0),
        10**400,
        float("inf"),
        Decimal("NaN"),
        Decimal("1e-10000"),
        Fraction(1, 10**1000),
    ],
)
def test_invalid_scores_cannot_become_candidates_or_checkpoints(
    value: Any, score_index: int
) -> None:
    score = [1.0, 0.0]
    score[score_index] = value
    checkpoints: list[int] = []
    with pytest.raises(ValueError, match="score"):
        differential_evolution_batch(
            lambda vectors: [tuple(score) for _ in vectors],
            [(0.0, 1.0)],
            population_size=4,
            generations=0,
            checkpoint=lambda generation, population, count: checkpoints.append(generation),
        )
    assert checkpoints == []


@pytest.mark.parametrize("field", ["lower", "upper", "mutation", "crossover"])
@pytest.mark.parametrize(
    "value", [True, "0.5", None, 10**400, Decimal("1e-10000"), Fraction(1, 10**1000)]
)
def test_invalid_parameters_fail_before_simulator_evaluation(field: str, value: Any) -> None:
    evaluated: list[tuple[float, ...]] = []
    checkpoints: list[int] = []
    options: dict[str, Any] = {"population_size": 4, "generations": 0}
    bounds = [(-1.0, 1.0)]
    if field == "lower":
        bounds = [(value, 1.0)]
    elif field == "upper":
        bounds = [(-1.0, value)]
    else:
        options[field] = value

    def evaluate(vectors: Any) -> Any:
        evaluated.extend(vectors)
        return [(1.0, 0.0) for _ in vectors]

    with pytest.raises(ValueError, match="bound|mutation|crossover"):
        differential_evolution_batch(
            evaluate,
            bounds,
            checkpoint=lambda generation, population, count: checkpoints.append(generation),
            **options,
        )
    assert evaluated == []
    assert checkpoints == []


def test_representable_decimal_and_fraction_inputs_match_float_run() -> None:
    options: dict[str, Any] = {
        "bounds": [(Decimal("-1"), Fraction(1))],
        "mutation": Decimal("0.5"),
        "crossover": Fraction(1, 2),
    }
    actual = differential_evolution_batch(
        lambda vectors: [(Decimal("1.25"), Fraction(1, 4)) for _ in vectors],
        population_size=4,
        generations=1,
        seed=5,
        **options,
    )
    expected = differential_evolution_batch(
        lambda vectors: [(1.25, 0.25) for _ in vectors],
        [(-1.0, 1.0)],
        population_size=4,
        generations=1,
        mutation=0.5,
        crossover=0.5,
        seed=5,
    )
    assert actual == expected


def test_smallest_positive_binary64_violation_stays_infeasible() -> None:
    violation = float.fromhex("0x0.0000000000001p-1022")
    result = differential_evolution_batch(
        lambda vectors: [(1.0, violation) for _ in vectors],
        [(0.0, 1.0)],
        population_size=4,
        generations=0,
    )
    assert result.best.violation == violation
    assert not result.best.feasible


@pytest.mark.parametrize("value", [Decimal("NaN"), Decimal("sNaN")])
@pytest.mark.parametrize("field", ["x", "objectives", "violation"])
def test_pareto_decimal_nan_is_a_validation_error(value: Decimal, field: str) -> None:
    values: dict[str, Any] = {"x": (0.0,), "objectives": (1.0,), "violation": 0.0}
    values[field] = value if field == "violation" else (value,)
    with pytest.raises(ValueError, match="Pareto points require finite"):
        pareto_front([ParetoPoint(**values)])


def test_pareto_preserves_finite_decimal_and_fraction_coordinates() -> None:
    point = ParetoPoint((Decimal("1e-10000"),), (Fraction(1, 3),), Decimal("1e-10000"))
    front = pareto_front([point])
    assert front == (point,)
    assert front[0] is point
    assert not front[0].feasible
