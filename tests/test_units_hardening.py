from __future__ import annotations

import math

import pytest

from aspenops_nexus.units import UnitError, convert


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf, True])
def test_unit_conversion_rejects_nonfinite_and_boolean_values(value: object) -> None:
    with pytest.raises(UnitError, match="finite numeric"):
        convert(value, "1", "1")  # type: ignore[arg-type]


def test_unit_conversion_rejects_nonfinite_derived_result() -> None:
    with pytest.raises(UnitError, match="produced a non-finite value"):
        convert(1e308, "MW", "W")


def test_unit_conversion_rejects_integer_too_large_for_float() -> None:
    with pytest.raises(UnitError, match="finite numeric"):
        convert(10**10000, "1", "1")


def test_unit_conversion_rejects_unknown_equal_units() -> None:
    with pytest.raises(UnitError, match="Unsupported unit conversion"):
        convert(1.0, "bogus", "bogus")


@pytest.mark.parametrize(("source", "target"), [([], "1"), ("1", [])])
def test_unit_conversion_rejects_nonstring_unit_names(
    source: object,
    target: object,
) -> None:
    with pytest.raises(UnitError, match="unit must be a string or null"):
        convert(1.0, source, target)  # type: ignore[arg-type]
