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
