from __future__ import annotations

import itertools
import math
import random
from collections.abc import Sequence

MAX_POINTS = 100_000
MAX_CELLS = 1_000_000
MAX_DIMENSIONS = 256


def _count(value: int, *, minimum: int, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")
    return value


def _bounds(bounds: Sequence[tuple[float, float]]) -> tuple[tuple[float, float], ...]:
    if not 1 <= len(bounds) <= MAX_DIMENSIONS:
        raise ValueError(f"bounds require 1..{MAX_DIMENSIONS} dimensions")
    result = []
    for lower, upper in bounds:
        if isinstance(lower, bool) or isinstance(upper, bool):
            raise ValueError("bounds must be finite numbers")
        try:
            low, high = float(lower), float(upper)
        except (ValueError, TypeError, OverflowError) as exc:
            raise ValueError("bounds must be finite numbers") from exc
        if not all(math.isfinite(v) for v in (low, high, high - low)) or high <= low:
            raise ValueError("upper bound must exceed lower bound with finite endpoints and width")
        result.append((low, high))
    return tuple(result)


def _budget(points: int, dimensions: int) -> None:
    if points > MAX_POINTS or points * dimensions > MAX_CELLS:
        raise ValueError(f"design exceeds budget: {MAX_POINTS} points or {MAX_CELLS} cells")


def latin_hypercube(
    bounds: Sequence[tuple[float, float]],
    n: int,
    *,
    seed: int = 0,
) -> list[list[float]]:
    count = _count(n, minimum=1, name="n")
    domain = _bounds(bounds)
    _budget(count, len(domain))
    rng = random.Random(seed)
    dimensions: list[list[float]] = []
    for lower, upper in domain:
        samples = [(i + rng.random()) / count for i in range(count)]
        rng.shuffle(samples)
        dimensions.append([lower + x * (upper - lower) for x in samples])
    return [[dimensions[d][i] for d in range(len(domain))] for i in range(count)]


def bounded_grid(
    bounds: Sequence[tuple[float, float]],
    levels: Sequence[int],
) -> list[list[float]]:
    if len(bounds) != len(levels):
        raise ValueError("bounds and levels must have the same length")
    domain = _bounds(bounds)
    counts = [_count(n, minimum=2, name="each grid dimension") for n in levels]
    _budget(math.prod(counts), len(domain))
    axes = [
        [lower + (upper - lower) * (i / (count - 1)) for i in range(count)]
        for (lower, upper), count in zip(domain, counts, strict=True)
    ]
    return [list(point) for point in itertools.product(*axes)]


def nearest_neighbor_order(points: Sequence[Sequence[float]]) -> list[int]:
    if not points:
        return []
    if len(points) > 5000:
        raise ValueError("nearest-neighbor ordering exceeds the 5000-point work budget")
    dimensions = len(points[0])
    if not 1 <= dimensions <= MAX_DIMENSIONS or any(len(p) != dimensions for p in points):
        raise ValueError("points must have equal non-empty dimensions")
    try:
        valid = all(not isinstance(v, bool) and math.isfinite(v) for p in points for v in p)
    except (TypeError, OverflowError) as exc:
        raise ValueError("points must contain finite real numbers") from exc
    if not valid:
        raise ValueError("points must contain finite real numbers")

    def distance(left: Sequence[float], right: Sequence[float]) -> float:
        value = math.dist(left, right)
        if not math.isfinite(value):
            raise ValueError("point distance exceeds the finite range")
        return value

    remaining = set(range(1, len(points)))
    order = [0]
    while remaining:
        last = points[order[-1]]
        next_index = min(remaining, key=lambda index: (distance(last, points[index]), index))
        order.append(next_index)
        remaining.remove(next_index)
    return order
