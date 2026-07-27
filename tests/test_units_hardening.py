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
