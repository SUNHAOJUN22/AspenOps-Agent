"""Bounded differential-evolution optimizer with feasibility ordering."""

from __future__ import annotations

import random
from collections.abc import Callable
from dataclasses import dataclass

from aspenops.design import Variable
from aspenops.errors import ValidationError
from aspenops.evaluation import deb_better
from aspenops.models import EvaluationResult


@dataclass(frozen=True)
class OptimizationConfig:
    population_size: int = 12
    generations: int = 20
    differential_weight: float = 0.7
    crossover_probability: float = 0.9
    seed: int = 0


@dataclass(frozen=True)
class OptimizationRecord:
    generation: int
    point: dict[str, float]
    result: EvaluationResult


def differential_evolution(
    variables: list[Variable],
    evaluate: Callable[[dict[str, float]], EvaluationResult],
    config: OptimizationConfig | None = None,
) -> tuple[OptimizationRecord, list[OptimizationRecord]]:
    config = config or OptimizationConfig()
    if len(variables) == 0:
        raise ValidationError("At least one optimization variable is required")
    keys = [variable.key for variable in variables]
    if len(set(keys)) != len(keys):
        raise ValidationError("Optimization variable keys must be unique")
    if config.population_size < 4:
        raise ValidationError("Differential evolution requires population_size >= 4")
    if config.generations < 0:
        raise ValidationError("generations must be non-negative")
    if not 0 < config.differential_weight <= 2:
        raise ValidationError("differential_weight must be in (0, 2]")
    if not 0 <= config.crossover_probability <= 1:
        raise ValidationError("crossover_probability must be in [0, 1]")

    rng = random.Random(config.seed)
    population = [
        {
            variable.key: variable.project(rng.uniform(variable.lower, variable.upper))
            for variable in variables
        }
        for _ in range(config.population_size)
    ]
    evaluations = [evaluate(point) for point in population]
    history = [
        OptimizationRecord(generation=0, point=point.copy(), result=result)
        for point, result in zip(population, evaluations, strict=True)
    ]

    for generation in range(1, config.generations + 1):
        best_index = _best_index(evaluations)
        for index in range(config.population_size):
            candidates = [
                candidate for candidate in range(config.population_size) if candidate != index
            ]
            r1, r2 = rng.sample(candidates, 2)
            mutant: dict[str, float] = {}
            for variable in variables:
                value = population[best_index][variable.key] + config.differential_weight * (
                    population[r1][variable.key] - population[r2][variable.key]
                )
                mutant[variable.key] = variable.project(value)

            forced_key = rng.choice(variables).key
            trial: dict[str, float] = {}
            for variable in variables:
                if variable.key == forced_key or rng.random() <= config.crossover_probability:
                    trial[variable.key] = mutant[variable.key]
                else:
                    trial[variable.key] = population[index][variable.key]
            trial_result = evaluate(trial)
            if deb_better(trial_result, evaluations[index]):
                population[index] = trial
                evaluations[index] = trial_result
            history.append(
                OptimizationRecord(
                    generation=generation,
                    point=population[index].copy(),
                    result=evaluations[index],
                )
            )

    best_index = _best_index(evaluations)
    best = OptimizationRecord(
        generation=config.generations,
        point=population[best_index].copy(),
        result=evaluations[best_index],
    )
    return best, history


def _best_index(evaluations: list[EvaluationResult]) -> int:
    best = 0
    for index in range(1, len(evaluations)):
        if deb_better(evaluations[index], evaluations[best]):
            best = index
    return best
