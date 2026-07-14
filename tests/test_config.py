import math

import pytest

from aspenops_nexus.config import Settings


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("timeout_s", math.nan),
        ("timeout_s", math.inf),
        ("startup_timeout_s", -1.0),
        ("worker_max_age_s", 0.0),
        ("scheduler_poll_s", 0.0),
    ],
)
def test_settings_reject_invalid_float_controls(field: str, value: float) -> None:
    with pytest.raises(ValueError):
        Settings(**{field: value})


@pytest.mark.parametrize("field", ["license_slots", "max_workers", "worker_max_points"])
def test_settings_reject_nonpositive_integer_controls(field: str) -> None:
    with pytest.raises(ValueError):
        Settings(**{field: 0})


def test_effective_workers_respects_license_and_configuration() -> None:
    assert Settings(max_workers=8, license_slots=3).effective_workers == 3
    assert Settings(max_workers=2, license_slots=8).effective_workers == 2


def test_direct_construction_validates_backend_and_mode() -> None:
    with pytest.raises(ValueError):
        Settings(backend="unknown")
    with pytest.raises(ValueError):
        Settings(mode="unsafe")
