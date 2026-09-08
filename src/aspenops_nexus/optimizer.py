from __future__ import annotations

import math
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


@dataclass(frozen=True, slots=True)
class DifferentialEvolutionResult:
    best: Candidate
    population: tuple[Candidate, ...]
    evaluations: int
    generations: int


@dataclass(frozen=True, slots=True)
class ParetoPoint:
    x: tuple[float, ...]
    objectives: tuple[float, ...]
    violation: float = 0.0

    @property
    def feasible(self) -> bool:
        return self.violation <= 0.0


def better(a: Candidate, b: Candidate) -> Candidate:
    """Deb feasibility ordering followed by scalar objective minimization."""
    a_feasible = a.violation <= 0.0
    b_feasible = b.violation <= 0.0
    if a_feasible != b_feasible:
        return a if a_feasible else b
    if a_feasible:
        return a if a.objective <= b.objective else b
    return a if a.violation <= b.violation else b


def dominates(a: ParetoPoint, b: ParetoPoint) -> bool:
    if a.feasible and not b.feasible:
        return True
    if b.feasible and not a.feasible:
        return False
    if not a.feasible and not b.feasible:
        return a.violation < b.violation
    no_worse = all(left <= right for left, right in zip(a.objectives, b.objectives, strict=True))
    strictly_better = any(
        left < right for left, right in zip(a.objectives, b.objectives, strict=True)
    )
    return no_worse and strictly_better


def _pareto_front_general(feasible: tuple[ParetoPoint, ...]) -> tuple[ParetoPoint, ...]:
    frontier: list[ParetoPoint] = []
    for candidate in feasible:
        if any(dominates(existing, candidate) for existing in frontier):
            continue
        frontier = [existing for existing in frontier if not dominates(candidate, existing)]
        frontier.append(candidate)
    return tuple(frontier)


def _pareto_front_two_objectives(
    feasible: tuple[ParetoPoint, ...],
) -> tuple[ParetoPoint, ...]:
    ordered = sorted(
        enumerate(feasible),
        key=lambda item: (item[1].objectives[0], item[1].objectives[1]),
    )
    selected: set[int] = set()
    prior_min_second = math.inf
    index = 0
    while index < len(ordered):
        first = ordered[index][1].objectives[0]
        end = index + 1
        while end < len(ordered) and ordered[end][1].objectives[0] == first:
            end += 1
        group_min_second = ordered[index][1].objectives[1]
        if prior_min_second > group_min_second:
            for original_index, point in ordered[index:end]:
                if point.objectives[1] == group_min_second:
                    selected.add(original_index)
        prior_min_second = min(prior_min_second, group_min_second)
        index = end
    return tuple(
        point for original_index, point in enumerate(feasible) if original_index in selected
    )


def pareto_front(points: Sequence[ParetoPoint]) -> tuple[ParetoPoint, ...]:
    """Return the ordered unique feasibility-first nondominated front."""

    unique = tuple(dict.fromkeys(points))
    if not unique:
        return ()
    feasible = tuple(point for point in unique if point.feasible)
    if not feasible:
        minimum_violation = min(point.violation for point in unique)
        return tuple(point for point in unique if point.violation == minimum_violation)

    objective_count = len(feasible[0].objectives)
    if any(len(point.objectives) != objective_count for point in feasible[1:]):
        raise ValueError("Pareto objective vectors must have equal dimensions")
    if objective_count == 0:
        return feasible
    if not all(math.isfinite(value) for point in feasible for value in point.objectives):
        return _pareto_front_general(feasible)
    if objective_count == 1:
        minimum = min(point.objectives[0] for point in feasible)
        return tuple(point for point in feasible if point.objectives[0] == minimum)
    if objective_count == 2:
        return _pareto_front_two_objectives(feasible)
    return _pareto_front_general(feasible)


def _validate_parameters(
    bounds: Sequence[tuple[float, float]],
    population_size: int,
    generations: int,
    mutation: float,
    crossover: float,
) -> None:
    if not bounds:
        raise ValueError("bounds must not be empty")
    if population_size < 4:
        raise ValueError("population_size must be at least 4")
    if generations < 0:
        raise ValueError("generations cannot be negative")
    if not math.isfinite(mutation) or mutation <= 0:
        raise ValueError("mutation must be positive and finite")
    if not math.isfinite(crossover) or not 0 <= crossover <= 1:
        raise ValueError("crossover must be finite and between zero and one")
    if any(
        not math.isfinite(lower) or not math.isfinite(upper) or upper <= lower
        for lower, upper in bounds
    ):
        raise ValueError("every bound must be finite and upper must exceed lower")


def differential_evolution_batch(
    evaluate_many: Callable[[Sequence[tuple[float, ...]]], Sequence[tuple[float, float]]],
    bounds: Sequence[tuple[float, float]],
    *,
    population_size: int = 20,
    generations: int = 40,
    mutation: float = 0.8,
    crossover: float = 0.9,
    seed: int = 0,
    max_evaluations: int | None = None,
    checkpoint: Callable[[int, tuple[Candidate, ...], int], None] | None = None,
) -> DifferentialEvolutionResult:
    """Run bounded DE/rand/1/bin with one batch evaluation per generation."""
    bounds_tuple = tuple(bounds)
    _validate_parameters(bounds_tuple, population_size, generations, mutation, crossover)
    budget = population_size * (generations + 1) if max_evaluations is None else max_evaluations
    if budget < population_size:
        raise ValueError("max_evaluations must cover the initial population")
    allowed_generations = min(generations, (budget - population_size) // population_size)
    rng = random.Random(seed)
    dimension_count = len(bounds_tuple)

    def random_vector() -> tuple[float, ...]:
        return tuple(rng.uniform(lower, upper) for lower, upper in bounds_tuple)

    def score_batch(vectors: Sequence[tuple[float, ...]]) -> list[Candidate]:
        scores = evaluate_many(vectors)
        if len(scores) != len(vectors):
            raise ValueError("evaluate_many returned a different number of scores")
        candidates: list[Candidate] = []
        for vector, (objective, violation) in zip(vectors, scores, strict=True):
            objective_value = float(objective)
            violation_value = float(violation)
            if not math.isfinite(objective_value) or not math.isfinite(violation_value):
                raise ValueError("evaluate_many returned a non-finite score")
            candidates.append(Candidate(vector, objective_value, max(0.0, violation_value)))
        return candidates

    vectors = [random_vector() for _ in range(population_size)]
    population = score_batch(vectors)
    evaluations = population_size
    if checkpoint is not None:
        checkpoint(0, tuple(population), evaluations)

    completed_generations = 0
    for generation in range(1, allowed_generations + 1):
        trial_vectors: list[tuple[float, ...]] = []
        for index, target in enumerate(population):
            a_index, b_index, c_index = rng.sample(range(population_size - 1), 3)
            if a_index >= index:
                a_index += 1
            if b_index >= index:
                b_index += 1
            if c_index >= index:
                c_index += 1
            a = population[a_index].x
            b = population[b_index].x
            c = population[c_index].x
            forced = rng.randrange(dimension_count)
            trial_values: list[float] = []
            for dimension, (lower, upper) in enumerate(bounds_tuple):
                mutant = a[dimension] + mutation * (b[dimension] - c[dimension])
                value = (
                    mutant
                    if rng.random() < crossover or dimension == forced
                    else target.x[dimension]
                )
                trial_values.append(min(upper, max(lower, value)))
            trial_vectors.append(tuple(trial_values))
        trials = score_batch(trial_vectors)
        evaluations += population_size
        population = [
            better(trial, target) for trial, target in zip(trials, population, strict=True)
        ]
        completed_generations = generation
        if checkpoint is not None:
            checkpoint(generation, tuple(population), evaluations)

    best = population[0]
    for candidate in population[1:]:
        best = better(candidate, best)
    return DifferentialEvolutionResult(
        best=best,
        population=tuple(population),
        evaluations=evaluations,
        generations=completed_generations,
    )


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
    """Compatibility wrapper around the batch optimizer."""

    def evaluate_many(
        vectors: Sequence[tuple[float, ...]],
    ) -> Sequence[tuple[float, float]]:
        return [evaluate(vector) for vector in vectors]

    return differential_evolution_batch(
        evaluate_many,
        bounds,
        population_size=population_size,
        generations=generations,
        mutation=mutation,
        crossover=crossover,
        seed=seed,
    ).best
