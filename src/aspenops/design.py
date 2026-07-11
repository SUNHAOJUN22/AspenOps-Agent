"""Deterministic design-of-experiments generators."""

from __future__ import annotations

import itertools
import math
import random
from collections.abc import Iterable
from dataclasses import dataclass

from aspenops.errors import ValidationError


@dataclass(frozen=True)
class Variable:
    key: str
    lower: float
    upper: float
    unit: str | None = None
    integer: bool = False

    def project(self, value: float) -> float:
        clipped = min(self.upper, max(self.lower, value))
        return float(round(clipped)) if self.integer else clipped


def latin_hypercube(
    variables: list[Variable], points: int, seed: int = 0
) -> list[dict[str, float]]:
    _validate_design(variables, points)
    rng = random.Random(seed)
    columns: dict[str, list[float]] = {}
    for variable in variables:
        samples = [
            variable.project(
                variable.lower + (index + rng.random()) / points * (variable.upper - variable.lower)
            )
            for index in range(points)
        ]
        rng.shuffle(samples)
        columns[variable.key] = samples
    return [
        {variable.key: columns[variable.key][row] for variable in variables}
        for row in range(points)
    ]


def random_design(variables: list[Variable], points: int, seed: int = 0) -> list[dict[str, float]]:
    _validate_design(variables, points)
    rng = random.Random(seed)
    return [
        {
            variable.key: variable.project(rng.uniform(variable.lower, variable.upper))
            for variable in variables
        }
        for _ in range(points)
    ]


def halton_design(variables: list[Variable], points: int, skip: int = 11) -> list[dict[str, float]]:
    _validate_design(variables, points)
    primes = _first_primes(len(variables))
    result: list[dict[str, float]] = []
    for row in range(skip, skip + points):
        point: dict[str, float] = {}
        for variable, base in zip(variables, primes, strict=True):
            fraction = _radical_inverse(row + 1, base)
            point[variable.key] = variable.project(
                variable.lower + fraction * (variable.upper - variable.lower)
            )
        result.append(point)
    return result


def grid_design(
    variables: list[Variable], levels: int, max_points: int = 10_000
) -> list[dict[str, float]]:
    _validate_design(variables, levels)
    total = levels ** len(variables)
    if total > max_points:
        raise ValidationError(f"Grid would create {total} points; limit is {max_points}")
    axes: list[list[float]] = []
    for variable in variables:
        if levels == 1:
            axes.append([variable.project((variable.lower + variable.upper) / 2.0)])
        else:
            axes.append(
                [
                    variable.project(
                        variable.lower + index / (levels - 1) * (variable.upper - variable.lower)
                    )
                    for index in range(levels)
                ]
            )
    return [
        {variable.key: value for variable, value in zip(variables, values, strict=True)}
        for values in itertools.product(*axes)
    ]


def nearest_neighbor_order(points: list[dict[str, float]]) -> list[int]:
    if not points:
        return []
    keys = sorted(points[0])
    remaining = set(range(1, len(points)))
    order = [0]
    while remaining:
        current = order[-1]
        next_index = min(
            remaining,
            key=lambda index: _distance(points[current], points[index], keys),
        )
        remaining.remove(next_index)
        order.append(next_index)
    return order


def reorder_by_indices(items: Iterable[object], order: list[int]) -> list[object]:
    materialized = list(items)
    return [materialized[index] for index in order]


def _distance(left: dict[str, float], right: dict[str, float], keys: list[str]) -> float:
    return math.sqrt(sum((left[key] - right[key]) ** 2 for key in keys))


def _validate_design(variables: list[Variable], points: int) -> None:
    if not variables:
        raise ValidationError("At least one variable is required")
    if points <= 0:
        raise ValidationError("Point count must be positive")
    for variable in variables:
        if variable.lower > variable.upper:
            raise ValidationError(f"Invalid bounds for {variable.key}")


def _radical_inverse(index: int, base: int) -> float:
    result = 0.0
    factor = 1.0 / base
    while index > 0:
        result += factor * (index % base)
        index //= base
        factor /= base
    return result


def _first_primes(count: int) -> list[int]:
    primes: list[int] = []
    candidate = 2
    while len(primes) < count:
        if all(candidate % prime for prime in primes if prime * prime <= candidate):
            primes.append(candidate)
        candidate += 1
    return primes
