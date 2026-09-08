from __future__ import annotations

import itertools
import random
from collections.abc import Sequence


def latin_hypercube(
    bounds: Sequence[tuple[float, float]],
    n: int,
    *,
    seed: int = 0,
) -> list[list[float]]:
    if n <= 0:
        raise ValueError("n must be positive")
    rng = random.Random(seed)
    dimensions: list[list[float]] = []
    for lower, upper in bounds:
        if upper <= lower:
            raise ValueError("upper bound must exceed lower bound")
        samples = [(i + rng.random()) / n for i in range(n)]
        rng.shuffle(samples)
        dimensions.append([lower + x * (upper - lower) for x in samples])
    return [[dimensions[d][i] for d in range(len(bounds))] for i in range(n)]


def bounded_grid(
    bounds: Sequence[tuple[float, float]],
    levels: Sequence[int],
) -> list[list[float]]:
    if len(bounds) != len(levels):
        raise ValueError("bounds and levels must have the same length")
    axes: list[list[float]] = []
    for (lower, upper), count in zip(bounds, levels, strict=True):
        if count < 2:
            raise ValueError("each grid dimension needs at least two levels")
        axes.append([lower + (upper - lower) * i / (count - 1) for i in range(count)])
    return [list(point) for point in itertools.product(*axes)]


def nearest_neighbor_order(points: Sequence[Sequence[float]]) -> list[int]:
    if not points:
        return []
    remaining = set(range(1, len(points)))
    order = [0]
    while remaining:
        last = points[order[-1]]
        next_index = min(
            remaining,
            key=lambda index: sum((a - b) ** 2 for a, b in zip(last, points[index], strict=True)),
        )
        order.append(next_index)
        remaining.remove(next_index)
    return order
