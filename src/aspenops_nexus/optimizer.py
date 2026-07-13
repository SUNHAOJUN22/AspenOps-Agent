from __future__ import annotations

import random
from collections.abc import Callable, Sequence
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Candidate:
    x: tuple[float, ...]
    objective: float
    violation: float

    @property
    def feasible(self) -> bool:
        return self.violation <= 0.0


def better(a: Candidate, b: Candidate) -> Candidate:
    if a.feasible and not b.feasible:
        return a
    if b.feasible and not a.feasible:
        return b
    if a.feasible and b.feasible:
        return a if a.objective <= b.objective else b
    return a if a.violation <= b.violation else b


def differential_evolution(
    evaluate: Callable[[tuple[float, ...]], tuple[float, float]],
    bounds: Sequence[tuple[float, float]],
    *,
    population_size: int = 20,
    generations: int = 40,
    mutation: float = 0.8,
    crossover: float = 0.9,
    seed: int = 0,
) -> Candidate:
    if population_size < 4:
        raise ValueError("population_size must be at least 4")
    rng = random.Random(seed)

    def random_vector() -> tuple[float, ...]:
        return tuple(rng.uniform(lower, upper) for lower, upper in bounds)

    def score(x: tuple[float, ...]) -> Candidate:
        objective, violation = evaluate(x)
        return Candidate(x, float(objective), max(0.0, float(violation)))

    population = [score(random_vector()) for _ in range(population_size)]
    for _ in range(generations):
        next_population: list[Candidate] = []
        for i, target in enumerate(population):
            candidates = [j for j in range(population_size) if j != i]
            a_i, b_i, c_i = rng.sample(candidates, 3)
            a, b, c = population[a_i].x, population[b_i].x, population[c_i].x
            forced = rng.randrange(len(bounds))
            trial_values: list[float] = []
            for dimension, (lower, upper) in enumerate(bounds):
                mutant = a[dimension] + mutation * (b[dimension] - c[dimension])
                value = (
                    mutant
                    if rng.random() < crossover or dimension == forced
                    else target.x[dimension]
                )
                trial_values.append(min(upper, max(lower, value)))
            trial = score(tuple(trial_values))
            next_population.append(better(trial, target))
        population = next_population
    best = population[0]
    for candidate in population[1:]:
        best = better(candidate, best)
    return best
