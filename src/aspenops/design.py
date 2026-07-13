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

    def __post_init__(self) -> None:
        if not self.key:
            raise ValidationError("Variable key must not be empty")
        if not math.isfinite(self.lower) or not math.isfinite(self.upper):
            raise ValidationError(f"Variable bounds must be finite for {self.key}")
        if self.lower > self.upper:
            raise ValidationError(f"Invalid bounds for {self.key}")
        if self.integer and math.ceil(self.lower) > math.floor(self.upper):
            raise ValidationError(f"Integer variable {self.key} has no feasible integer in its bounds")

    def project(self, value: float) -> float:
        if not math.isfinite(value):
            raise ValidationError(f"Variable {self.key} received a non-finite value")
        clipped = min(self.upper, max(self.lower, value))
        if not self.integer:
            return clipped
        lower_integer = math.ceil(self.lower)
        upper_integer = math.floor(self.upper)
        projected = min(upper_integer, max(lower_integer, round(clipped)))
        return float(projected)


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
    if skip < 0:
        raise ValidationError("Halton skip must be non-negative")
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
    if max_points <= 0:
        raise ValidationError("max_points must be positive")
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
    if not keys:
        raise ValidationError("Nearest-neighbor points must contain at least one variable")
    for point in points:
        if sorted(point) != keys:
            raise ValidationError("Nearest-neighbor points must have identical variables")
        for key in keys:
            if not math.isfinite(point[key]):
                raise ValidationError(f"Nearest-neighbor value {key} must be finite")
    ranges = {
        key: max(point[key] for point in points) - min(point[key] for point in points)
        for key in keys
    }
    scales = {key: (value if value > 0 else 1.0) for key, value in ranges.items()}
    remaining = set(range(1, len(points)))
    order = [0]
    while remaining:
        current = order[-1]
        next_index = min(
            remaining,
            key=lambda index: _distance(points[current], points[index], keys, scales),
        )
        remaining.remove(next_index)
        order.append(next_index)
    return order


def reorder_by_indices(items: Iterable[object], order: list[int]) -> list[object]:
    materialized = list(items)
    return [materialized[index] for index in order]


def _distance(
    left: dict[str, float],
    right: dict[str, float],
    keys: list[str],
    scales: dict[str, float],
) -> float:
    return math.sqrt(
        sum(((left[key] - right[key]) / scales[key]) ** 2 for key in keys)
    )


def _validate_design(variables: list[Variable], points: int) -> None:
    if not variables:
        raise ValidationError("At least one variable is required")
    if points <= 0:
        raise ValidationError("Point count must be positive")
    keys = [variable.key for variable in variables]
    if len(set(keys)) != len(keys):
        raise ValidationError("Variable keys must be unique")


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
