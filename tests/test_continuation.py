import math

import pytest

from aspenops.continuation import adaptive_continuation
from aspenops.errors import SimulationError, ValidationError


def test_adaptive_continuation_reaches_target_after_shrink() -> None:
    previous = 0.0

    def evaluate(point: dict[str, float]) -> tuple[float, bool]:
        nonlocal previous
        jump = point["x"] - previous
        success = jump <= 0.35
        if success:
            previous = point["x"]
        return point["x"], success

    history = adaptive_continuation(
        {"x": 0.0},
        {"x": 1.0},
        evaluate,
        initial_step=0.5,
        minimum_step=0.05,
        maximum_step=0.5,
    )
    assert history[-1].fraction == 1.0
    assert any(not step.success for step in history)


def test_continuation_validation_and_failure() -> None:
    with pytest.raises(ValidationError):
        adaptive_continuation({"x": 0}, {"y": 1}, lambda point: (point, True))
    with pytest.raises(SimulationError):
        adaptive_continuation(
            {"x": 0},
            {"x": 1},
            lambda point: (point, False),
            initial_step=0.1,
            minimum_step=0.05,
        )


def test_continuation_rejects_invalid_controls() -> None:
    def evaluator(point: dict[str, float]) -> tuple[dict[str, float], bool]:
        return point, True

    with pytest.raises(ValidationError, match="growth"):
        adaptive_continuation({"x": 0}, {"x": 1}, evaluator, growth=1.0)
    with pytest.raises(ValidationError, match="shrink"):
        adaptive_continuation({"x": 0}, {"x": 1}, evaluator, shrink=1.0)
    with pytest.raises(ValidationError, match="max_attempts"):
        adaptive_continuation({"x": 0}, {"x": 1}, evaluator, max_attempts=0)
    with pytest.raises(ValidationError, match="finite"):
        adaptive_continuation({"x": 0}, {"x": math.inf}, evaluator)
