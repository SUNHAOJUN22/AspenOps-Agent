import pytest

from aspenops.design import (
    Variable,
    grid_design,
    halton_design,
    latin_hypercube,
    nearest_neighbor_order,
    random_design,
)
from aspenops.errors import ValidationError


def test_designs_are_deterministic_and_bounded() -> None:
    variables = [Variable("x", 0, 10), Variable("n", 1, 5, integer=True)]
    lhs = latin_hypercube(variables, 8, seed=7)
    assert lhs == latin_hypercube(variables, 8, seed=7)
    for point in lhs + random_design(variables, 4, seed=9) + halton_design(variables, 4):
        assert 0 <= point["x"] <= 10
        assert 1 <= point["n"] <= 5
        assert point["n"].is_integer()


def test_grid_cap_and_nearest_neighbor_order() -> None:
    variables = [Variable("x", 0, 1), Variable("y", 0, 1)]
    assert len(grid_design(variables, 3)) == 9
    with pytest.raises(ValidationError):
        grid_design(variables, 101, max_points=100)
    points = [{"x": 0.0}, {"x": 10.0}, {"x": 1.0}, {"x": 2.0}]
    assert nearest_neighbor_order(points) == [0, 2, 3, 1]


def test_variable_and_design_validation() -> None:
    with pytest.raises(ValidationError, match="no feasible integer"):
        Variable("n", 0.2, 0.8, integer=True)
    with pytest.raises(ValidationError, match="unique"):
        latin_hypercube([Variable("x", 0, 1), Variable("x", 2, 3)], 2)
    with pytest.raises(ValidationError, match="non-negative"):
        halton_design([Variable("x", 0, 1)], 2, skip=-1)
    with pytest.raises(ValidationError, match="identical"):
        nearest_neighbor_order([{"x": 0.0}, {"y": 1.0}])


def test_nearest_neighbor_distance_is_range_normalized() -> None:
    points = [
        {"large": 0.0, "small": 0.0},
        {"large": 900.0, "small": 0.0},
        {"large": 100.0, "small": 1.0},
    ]
    assert nearest_neighbor_order(points) == [0, 1, 2]


def test_integer_projection_remains_inside_fractional_bounds() -> None:
    variable = Variable("n", 0.2, 1.8, integer=True)
    assert variable.project(0.2) == 1.0
    assert variable.project(1.8) == 1.0
