from __future__ import annotations

import math
import random
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Literal

ObjectiveDirection = Literal["minimize", "maximize"]


@dataclass(frozen=True, slots=True)
class Candidate:
    x: tuple[float, ...]
    objective: float
    violation: float

    def __post_init__(self) -> None:
        if not self.x or not all(math.isfinite(value) for value in self.x):
            raise ValueError("Candidate coordinates must be a non-empty finite vector")
        if not math.isfinite(self.objective):
            raise ValueError("Candidate objective must be finite")
        if not math.isfinite(self.violation) or self.violation < 0.0:
            raise ValueError("Candidate violation must be finite and nonnegative")

    @property
    def feasible(self) -> bool:
        return self.violation <= 0.0


def _rank(candidate: Candidate, direction: ObjectiveDirection) -> tuple[object, ...]:
    if candidate.feasible:
        objective = candidate.objective if direction == "minimize" else -candidate.objective
        return (0, objective, candidate.x)
    return (1, candidate.violation, candidate.x)


def better(
    a: Candidate,
    b: Candidate,
    direction: ObjectiveDirection = "minimize",
) -> Candidate:
    if direction not in {"minimize", "maximize"}:
        raise ValueError(f"Unsupported objective direction: {direction}")
    return a if _rank(a, direction) <= _rank(b, direction) else b


def differential_evolution(
    evaluate: Callable[[tuple[float, ...]], tuple[float, float]],
    bounds: Sequence[tuple[float, float]],
    *,
    population_size: int = 20,
    generations: int = 40,
    mutation: float = 0.8,
    crossover: float = 0.9,
    seed: int = 0,
    objective_direction: ObjectiveDirection = "minimize",
    integer_indices: Sequence[int] = (),
    stall_generations: int | None = None,
) -> Candidate:
    if isinstance(population_size, bool) or population_size < 4:
        raise ValueError("population_size must be an integer of at least 4")
    if isinstance(generations, bool) or generations < 0:
        raise ValueError("generations must be a nonnegative integer")
    if not bounds:
        raise ValueError("bounds must contain at least one dimension")
    normalized_bounds: list[tuple[float, float]] = []
    for index, pair in enumerate(bounds):
        if len(pair) != 2:
            raise ValueError(f"Bound {index} must contain exactly lower and upper")
        lower, upper = float(pair[0]), float(pair[1])
        if not math.isfinite(lower) or not math.isfinite(upper):
            raise ValueError(f"Bound {index} must be finite")
        if lower > upper:
            raise ValueError(f"Bound {index} has lower > upper")
        normalized_bounds.append((lower, upper))
    if not math.isfinite(mutation) or not 0.0 <= mutation <= 2.0:
        raise ValueError("mutation must be finite and in [0, 2]")
    if not math.isfinite(crossover) or not 0.0 <= crossover <= 1.0:
        raise ValueError("crossover must be finite and in [0, 1]")
    if objective_direction not in {"minimize", "maximize"}:
        raise ValueError(f"Unsupported objective direction: {objective_direction}")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("seed must be an integer")
    if stall_generations is not None and (
        isinstance(stall_generations, bool) or stall_generations < 1
    ):
        raise ValueError("stall_generations must be a positive integer when provided")
    integers = frozenset(int(index) for index in integer_indices)
    if any(index < 0 or index >= len(normalized_bounds) for index in integers):
        raise ValueError("integer_indices contains an out-of-range dimension")
    for index in integers:
        lower, upper = normalized_bounds[index]
        if math.ceil(lower) > math.floor(upper):
            raise ValueError(f"Integer dimension {index} contains no feasible integer")

    rng = random.Random(seed)

    def project(values: Sequence[float]) -> tuple[float, ...]:
        projected: list[float] = []
        pairs = zip(values, normalized_bounds, strict=True)
        for index, (value, (lower, upper)) in enumerate(pairs):
            bounded = min(upper, max(lower, float(value)))
            if index in integers:
                bounded = float(min(math.floor(upper), max(math.ceil(lower), round(bounded))))
            projected.append(bounded)
        return tuple(projected)

    def random_vector() -> tuple[float, ...]:
        values: list[float] = []
        for index, (lower, upper) in enumerate(normalized_bounds):
            if index in integers:
                values.append(float(rng.randint(math.ceil(lower), math.floor(upper))))
            else:
                values.append(rng.uniform(lower, upper))
        return tuple(values)

    def score(x: tuple[float, ...]) -> Candidate:
        objective, violation = evaluate(x)
        objective_value = float(objective)
        violation_value = float(violation)
        if not math.isfinite(objective_value) or not math.isfinite(violation_value):
            raise ValueError("evaluate must return finite objective and violation values")
        return Candidate(x, objective_value, max(0.0, violation_value))

    population = [score(random_vector()) for _ in range(population_size)]
    best = min(population, key=lambda candidate: _rank(candidate, objective_direction))
    stall_count = 0
    for _ in range(generations):
        next_population: list[Candidate] = []
        for target_index, target in enumerate(population):
            candidates = [index for index in range(population_size) if index != target_index]
            a_index, b_index, c_index = rng.sample(candidates, 3)
            a, b, c = population[a_index].x, population[b_index].x, population[c_index].x
            forced = rng.randrange(len(normalized_bounds))
            trial_values: list[float] = []
            for dimension_index, _bound in enumerate(normalized_bounds):
                mutant = a[dimension_index] + mutation * (
                    b[dimension_index] - c[dimension_index]
                )
                value = (
                    mutant
                    if rng.random() < crossover or dimension_index == forced
                    else target.x[dimension_index]
                )
                trial_values.append(value)
            trial = score(project(trial_values))
            next_population.append(better(trial, target, objective_direction))
        population = next_population
        next_best = min(population, key=lambda candidate: _rank(candidate, objective_direction))
        if _rank(next_best, objective_direction) < _rank(best, objective_direction):
            best = next_best
            stall_count = 0
        else:
            stall_count += 1
            best = better(next_best, best, objective_direction)
        if stall_generations is not None and stall_count >= stall_generations:
            break
    return best
