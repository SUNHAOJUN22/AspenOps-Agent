from __future__ import annotations

import bisect
import math
from dataclasses import asdict, dataclass
from typing import Literal

DriftLevel = Literal["OK", "WARNING", "BLOCK"]


@dataclass(frozen=True, slots=True)
class DriftThresholds:
    warning: float = 0.1
    block: float = 0.25
    probability_floor: float = 1e-6
    min_samples: int = 30

    def __post_init__(self) -> None:
        for name, value in (
            ("warning", self.warning),
            ("block", self.block),
            ("probability_floor", self.probability_floor),
        ):
            if not math.isfinite(value) or value <= 0.0:
                raise ValueError(f"{name} must be finite and positive")
        if self.warning >= self.block:
            raise ValueError("warning threshold must be below block threshold")
        if self.probability_floor >= 1.0:
            raise ValueError("probability_floor must be below one")
        if isinstance(self.min_samples, bool) or self.min_samples < 2:
            raise ValueError("min_samples must be an integer of at least two")


@dataclass(frozen=True, slots=True)
class DriftAssessment:
    psi: float
    level: DriftLevel
    reference_count: int
    current_count: int
    bins: tuple[float, ...]
    reference_distribution: tuple[float, ...]
    current_distribution: tuple[float, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _validate_samples(values: list[float] | tuple[float, ...], name: str) -> list[float]:
    if not values:
        raise ValueError(f"{name} samples must not be empty")
    normalized = [float(value) for value in values]
    if not all(math.isfinite(value) for value in normalized):
        raise ValueError(f"{name} samples must be finite")
    return normalized


def _validate_bins(bins: list[float] | tuple[float, ...]) -> tuple[float, ...]:
    normalized = tuple(float(value) for value in bins)
    if not normalized or not all(math.isfinite(value) for value in normalized):
        raise ValueError("PSI bins must contain finite cut points")
    if any(left >= right for left, right in zip(normalized, normalized[1:], strict=True)):
        raise ValueError("PSI bins must be strictly increasing")
    return normalized


def _distribution(values: list[float], bins: tuple[float, ...], floor: float) -> tuple[float, ...]:
    counts = [0] * (len(bins) + 1)
    for value in values:
        counts[bisect.bisect_right(bins, value)] += 1
    probabilities = [max(count / len(values), floor) for count in counts]
    total = math.fsum(probabilities)
    return tuple(probability / total for probability in probabilities)


def population_stability_index(
    reference: list[float] | tuple[float, ...],
    current: list[float] | tuple[float, ...],
    bins: list[float] | tuple[float, ...],
    thresholds: DriftThresholds = DriftThresholds(),
) -> DriftAssessment:
    reference_values = _validate_samples(reference, "reference")
    current_values = _validate_samples(current, "current")
    fixed_bins = _validate_bins(bins)
    if len(reference_values) < thresholds.min_samples:
        raise ValueError("reference sample count is below the drift minimum")
    if len(current_values) < thresholds.min_samples:
        raise ValueError("current sample count is below the drift minimum")
    reference_distribution = _distribution(
        reference_values, fixed_bins, thresholds.probability_floor
    )
    current_distribution = _distribution(current_values, fixed_bins, thresholds.probability_floor)
    psi = math.fsum(
        (reference_probability - current_probability)
        * math.log(reference_probability / current_probability)
        for reference_probability, current_probability in zip(
            reference_distribution, current_distribution, strict=True
        )
    )
    if psi >= thresholds.block:
        level: DriftLevel = "BLOCK"
    elif psi >= thresholds.warning:
        level = "WARNING"
    else:
        level = "OK"
    return DriftAssessment(
        psi=psi,
        level=level,
        reference_count=len(reference_values),
        current_count=len(current_values),
        bins=fixed_bins,
        reference_distribution=reference_distribution,
        current_distribution=current_distribution,
    )
