from __future__ import annotations

import math

import pytest

from aspenops_nexus.units import UnitError, convert


@pytest.mark.parametrize("value", [1e308, -1e308])
@pytest.mark.parametrize("source,target,scale", [("kPa", "MPa", 0.001), ("bar", "MPa", 0.1)])
def test_representable_conversion_survives_base_unit_overflow(
    value: float, source: str, target: str, scale: float
) -> None:
    result = convert(value, source, target)
    assert math.isfinite(result)
    assert result == pytest.approx(value * scale)
    assert convert(result, target, source) == pytest.approx(value)


def test_unrepresentable_conversion_still_fails_closed() -> None:
    with pytest.raises(UnitError, match="non-finite"):
        convert(1e308, "MW", "W")
