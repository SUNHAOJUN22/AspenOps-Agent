import math

import pytest

from aspenops_nexus.units import UnitError, UnitSpec, convert, dimension


def test_temperature_conversion() -> None:
    assert convert(25.0, "C", "K") == pytest.approx(298.15)
    assert convert(298.15, "K", "C") == pytest.approx(25.0)


def test_temperature_difference_does_not_apply_absolute_offset() -> None:
    assert convert(10.0, "delta_degC", "delta_K") == pytest.approx(10.0)
    assert convert(18.0, "delta_degF", "delta_K") == pytest.approx(10.0)
    with pytest.raises(UnitError):
        convert(10.0, "delta_degC", "C")


def test_pressure_conversion() -> None:
    assert convert(1.0, "bar", "kPa") == pytest.approx(100.0)


def test_absolute_and_gauge_pressure_are_not_interchangeable() -> None:
    assert convert(1.0, "bar(g)", "kPa(g)") == pytest.approx(100.0)
    with pytest.raises(UnitError):
        convert(1.0, "bar(g)", "bar")


def test_incompatible_units() -> None:
    with pytest.raises(UnitError):
        convert(1.0, "bar", "kg/h")


def test_unsupported_same_unit_is_rejected() -> None:
    with pytest.raises(UnitError):
        convert(1.0, "not-a-unit", "not-a-unit")


def test_units_must_be_both_present_or_both_omitted() -> None:
    assert convert(1.5, None, None) == pytest.approx(1.5)
    with pytest.raises(UnitError):
        convert(1.0, None, "bar")
    with pytest.raises(UnitError):
        convert(1.0, "bar", None)


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_nonfinite_values_are_rejected(value: float) -> None:
    with pytest.raises(UnitError):
        convert(value, "bar", "kPa")


def test_negative_absolute_temperature_and_pressure_are_rejected() -> None:
    with pytest.raises(UnitError):
        convert(-274.0, "C", "K")
    with pytest.raises(UnitError):
        convert(-1.0, "bar", "Pa")


@pytest.mark.parametrize(
    ("value", "source", "target"),
    [
        (25.0, "C", "K"),
        (100.0, "bar", "kPa"),
        (3600.0, "kg/h", "kg/s"),
        (18.0, "delta_degF", "delta_K"),
    ],
)
def test_conversion_round_trip(value: float, source: str, target: str) -> None:
    converted = convert(value, source, target)
    assert convert(converted, target, source) == pytest.approx(value)


def test_unit_spec_rejects_invalid_scale_and_offset() -> None:
    with pytest.raises(ValueError):
        UnitSpec("x", 0.0)
    with pytest.raises(ValueError):
        UnitSpec("x", math.inf)
    with pytest.raises(ValueError):
        UnitSpec("x", 1.0, math.nan)


def test_additional_engineering_units() -> None:
    assert abs(convert(1.0, "t/h", "kg/h") - 1000.0) < 1e-9
    assert abs(convert(1.0, "atm", "kPa") - 101.325) < 1e-9
    assert dimension("cP") == "viscosity"
    assert dimension("m3/h") == "volume_flow"
