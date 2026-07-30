from __future__ import annotations

import random

import pytest

import aspenops_nexus.optimizer as optimizer_module
import aspenops_nexus.units as units_module
from aspenops_nexus.optimizer import ParetoPoint, dominates, pareto_front
from aspenops_nexus.units import convert


def _reference_front(points: list[ParetoPoint]) -> tuple[ParetoPoint, ...]:
    unique = tuple(dict.fromkeys(points))
    if not unique:
        return ()
    feasible = tuple(point for point in unique if point.feasible)
    if not feasible:
        minimum_violation = min(point.violation for point in unique)
        return tuple(point for point in unique if point.violation == minimum_violation)
    return tuple(
        candidate
        for candidate in feasible
        if not any(
            dominates(existing, candidate)
            for existing in feasible
            if existing is not candidate
        )
    )


@pytest.mark.parametrize("dimensions", [1, 2, 3, 5])
def test_specialized_pareto_matches_pairwise_reference(dimensions: int) -> None:
    rng = random.Random(20260730 + dimensions)
    points = [
        ParetoPoint(
            (float(index),),
            tuple(rng.uniform(-5.0, 5.0) for _ in range(dimensions)),
            0.0 if index % 7 else 0.25,
        )
        for index in range(120)
    ]
    assert pareto_front(points) == _reference_front(points)


def test_two_objective_sweep_avoids_pairwise_dominance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    points = [
        ParetoPoint((float(index),), (float(index), float(2000 - index)), 0.0)
        for index in range(2000)
    ]
    calls = 0
    original = optimizer_module.dominates

    def counted(left: ParetoPoint, right: ParetoPoint) -> bool:
        nonlocal calls
        calls += 1
        return original(left, right)

    monkeypatch.setattr(optimizer_module, "dominates", counted)
    assert pareto_front(points) == tuple(points)
    assert calls == 0


def test_two_objective_sweep_preserves_ties_and_input_order() -> None:
    points = [
        ParetoPoint((0.0,), (1.0, 2.0)),
        ParetoPoint((1.0,), (1.0, 2.0)),
        ParetoPoint((2.0,), (2.0, 1.0)),
        ParetoPoint((3.0,), (2.0, 3.0)),
    ]
    assert pareto_front(points) == tuple(points[:3])


def test_pareto_rejects_mixed_objective_dimensions() -> None:
    with pytest.raises(ValueError, match="equal dimensions"):
        pareto_front(
            [
                ParetoPoint((0.0,), (1.0,)),
                ParetoPoint((1.0,), (1.0, 2.0)),
            ]
        )


def test_precomputed_unit_pairs_match_original_affine_formula() -> None:
    values = (-273.15, -1.0, 0.0, 1.0, 25.0, 100.0, 1e6)
    for source, source_spec in units_module._UNITS.items():
        for target, target_spec in units_module._UNITS.items():
            if source_spec.dimension != target_spec.dimension:
                continue
            for value in values:
                expected = (
                    value
                    if source == target
                    else target_spec.from_base(source_spec.to_base(value))
                )
                assert convert(value, source, target) == expected


def test_supported_units_returns_an_independent_snapshot() -> None:
    first = units_module.supported_units()
    first.clear()
    assert units_module.supported_units()
