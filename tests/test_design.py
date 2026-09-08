from aspenops_nexus.design import bounded_grid, latin_hypercube, nearest_neighbor_order


def test_lhs_is_deterministic() -> None:
    a = latin_hypercube([(0, 1), (10, 20)], 8, seed=7)
    b = latin_hypercube([(0, 1), (10, 20)], 8, seed=7)
    assert a == b
    assert len(a) == 8


def test_grid() -> None:
    assert len(bounded_grid([(0, 1), (0, 1)], [3, 2])) == 6


def test_nearest_neighbor_order() -> None:
    order = nearest_neighbor_order([[0.0], [10.0], [1.0], [2.0]])
    assert order == [0, 2, 3, 1]
