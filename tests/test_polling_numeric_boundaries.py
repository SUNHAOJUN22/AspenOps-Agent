from __future__ import annotations

import math
from typing import Any

import pytest

from aspenops_nexus.convergence import normalize_running_flag, poll_engine_idle


@pytest.mark.parametrize("field", ["timeout_s", "poll_interval_s"])
@pytest.mark.parametrize(
    "value", [math.nan, math.inf, -math.inf, True, False, "1", None, 0, -1, 10**400]
)
def test_invalid_polling_duration_rejected_before_engine_access(field: str, value: Any) -> None:
    options: dict[str, Any] = {"timeout_s": 1.0, "poll_interval_s": 0.1, "stable_samples": 2}
    options[field] = value

    def forbidden_read() -> bool:
        pytest.fail("invalid timing reached the external engine")

    with pytest.raises(ValueError, match=field):
        poll_engine_idle(forbidden_read, **options)


@pytest.mark.parametrize("value", [True, False, 0, -1, 1.5, math.nan, math.inf, "2", None])
def test_stable_samples_is_a_positive_integer(value: Any) -> None:
    with pytest.raises(ValueError, match="stable_samples"):
        poll_engine_idle(lambda: False, timeout_s=1.0, poll_interval_s=0.1, stable_samples=value)


@pytest.mark.parametrize("value", [10**400, -(10**400)])
def test_unrepresentable_com_integer_is_unknown(value: int) -> None:
    assert normalize_running_flag(value) is None
