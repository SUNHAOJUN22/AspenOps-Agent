from aspenops_nexus.optimizer import differential_evolution


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
