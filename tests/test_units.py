import pytest

from aspenops_nexus.units import UnitError, convert


def test_temperature_conversion() -> None:
    assert convert(25.0, "C", "K") == pytest.approx(298.15)
    assert convert(298.15, "K", "C") == pytest.approx(25.0)


def test_pressure_conversion() -> None:
    assert convert(1.0, "bar", "kPa") == pytest.approx(100.0)


def test_incompatible_units() -> None:
    with pytest.raises(UnitError):
        convert(1.0, "bar", "kg/h")


def test_additional_engineering_units() -> None:
    from aspenops_nexus.units import convert, dimension

    assert abs(convert(1.0, "t/h", "kg/h") - 1000.0) < 1e-9
    assert abs(convert(1.0, "atm", "kPa") - 101.325) < 1e-9
    assert dimension("cP") == "viscosity"
