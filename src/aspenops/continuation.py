"""Adaptive continuation for difficult operating-point transitions."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Generic, TypeVar

from aspenops.errors import SimulationError, ValidationError

T = TypeVar("T")


@dataclass(frozen=True)
class ContinuationStep(Generic[T]):
    fraction: float
    point: dict[str, float]
    result: T
    success: bool


def adaptive_continuation(
    start: dict[str, float],
    target: dict[str, float],
    evaluate: Callable[[dict[str, float]], tuple[T, bool]],
    *,
    initial_step: float = 0.25,
    minimum_step: float = 0.01,
    maximum_step: float = 0.5,
    growth: float = 1.5,
    shrink: float = 0.5,
    max_attempts: int = 100,
) -> list[ContinuationStep[T]]:
    if start.keys() != target.keys():
        raise ValidationError("Continuation start and target must have identical variables")
    if not 0 < minimum_step <= initial_step <= maximum_step <= 1:
        raise ValidationError("Invalid continuation step bounds")
    fraction = 0.0
    step = initial_step
    history: list[ContinuationStep[T]] = []
    attempts = 0
    while fraction < 1.0:
        attempts += 1
        if attempts > max_attempts:
            raise SimulationError("Continuation exceeded maximum attempts")
        trial_fraction = min(1.0, fraction + step)
        point = {key: start[key] + trial_fraction * (target[key] - start[key]) for key in start}
        result, success = evaluate(point)
        history.append(
            ContinuationStep(
                fraction=trial_fraction,
                point=point,
                result=result,
                success=success,
            )
        )
        if success:
            fraction = trial_fraction
            step = min(maximum_step, step * growth)
            continue
        step *= shrink
        if step < minimum_step:
            raise SimulationError(
                f"Continuation failed near fraction {trial_fraction:.4f}; "
                f"step {step:.4f} is below minimum {minimum_step:.4f}"
            )
    return history
