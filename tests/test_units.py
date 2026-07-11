import math

import pytest

from aspenops.errors import UnitError
from aspenops.units import convert, dimension_of, normalize_unit


def test_temperature_and_pressure_conversion() -> None:
    assert convert(0, "C", "K") == pytest.approx(273.15)
    assert convert(32, "F", "C") == pytest.approx(0)
    assert convert(1, "bar", "kPa") == pytest.approx(100)
    assert convert(3600, "kg/h", "kg/s") == pytest.approx(1)
    assert math.isclose(convert(1, "%", "fraction"), 0.01)


def test_aliases_and_dimension() -> None:
    assert normalize_unit("kg/hr") == "kg/h"
    assert dimension_of("deg C") == "temperature"


def test_incompatible_or_unknown_units_fail_closed() -> None:
    with pytest.raises(UnitError):
        convert(1, "bar", "kg/h")
    with pytest.raises(UnitError):
        dimension_of("banana")
