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


@pytest.mark.parametrize("value", [1e308, -1e308])
@pytest.mark.parametrize("source,target", [("MW", "W"), ("C", "F")])
def test_unrepresentable_conversion_still_fails_closed(
    value: float, source: str, target: str
) -> None:
    with pytest.raises(UnitError, match="non-finite"):
        convert(value, source, target)


@pytest.mark.parametrize("sign", [-1.0, 1.0])
@pytest.mark.parametrize("source,target", [("W", "kW"), ("Pa", "bar"), ("ppm", "1")])
def test_nonzero_scaled_quantity_cannot_silently_become_zero(
    sign: float, source: str, target: str
) -> None:
    with pytest.raises(UnitError, match="underflow"):
        convert(sign * math.ulp(0.0), source, target)


@pytest.mark.parametrize("sign", [-1.0, 1.0])
def test_representable_result_survives_underflow_in_the_unused_base_unit(sign: float) -> None:
    value = sign * math.ulp(0.0)
    assert convert(value, "L/s", "L/min") == value * 60.0
    assert convert(value, "g/s", "kg/h") == value * 3.6


@pytest.mark.parametrize("source,target", [("C", "degC"), ("F", "degF"), ("W", "J/s")])
def test_equivalent_unit_aliases_preserve_tiny_nonzero_values(source: str, target: str) -> None:
    value = math.ulp(0.0)
    assert convert(value, source, target) == value


@pytest.mark.parametrize(
    "value,source,target",
    [(273.15, "K", "C"), (-273.15, "C", "K"), (32.0, "F", "C")],
)
def test_legitimate_affine_zero_is_not_underflow(value: float, source: str, target: str) -> None:
    assert convert(value, source, target) == 0.0


@pytest.mark.parametrize("source,target", [("C", "F"), ("F", "C")])
def test_temperature_zero_points_remain_convertible(source: str, target: str) -> None:
    expected = 32.0 if source == "C" else -160.0 / 9.0
    assert convert(0.0, source, target) == pytest.approx(expected)


def test_exact_zero_and_same_unit_values_remain_valid() -> None:
    assert convert(0.0, "Pa", "bar") == 0.0
    assert convert(math.ulp(0.0), "W", "W") == math.ulp(0.0)
