"""Small deterministic engineering-unit conversion layer.

The runtime intentionally supports a focused set of units used by the bundled
registry. Unknown units fail closed instead of being guessed.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass

from aspenops.errors import UnitError


@dataclass(frozen=True)
class UnitDef:
    dimension: str
    to_base: Callable[[float], float]
    from_base: Callable[[float], float]


def _linear(
    scale: float, offset: float = 0.0
) -> tuple[Callable[[float], float], Callable[[float], float]]:
    return (lambda value: value * scale + offset, lambda value: (value - offset) / scale)


def _unit(dimension: str, scale: float, offset: float = 0.0) -> UnitDef:
    to_base, from_base = _linear(scale, offset)
    return UnitDef(dimension=dimension, to_base=to_base, from_base=from_base)


_UNITS: dict[str, UnitDef] = {
    "K": _unit("temperature", 1.0),
    "C": _unit("temperature", 1.0, 273.15),
    "degC": _unit("temperature", 1.0, 273.15),
    "F": UnitDef(
        "temperature",
        lambda value: (value - 32.0) * 5.0 / 9.0 + 273.15,
        lambda value: (value - 273.15) * 9.0 / 5.0 + 32.0,
    ),
    "Pa": _unit("pressure", 1.0),
    "kPa": _unit("pressure", 1_000.0),
    "MPa": _unit("pressure", 1_000_000.0),
    "bar": _unit("pressure", 100_000.0),
    "atm": _unit("pressure", 101_325.0),
    "psi": _unit("pressure", 6_894.757293168),
    "kg/s": _unit("mass_flow", 1.0),
    "kg/h": _unit("mass_flow", 1.0 / 3_600.0),
    "t/h": _unit("mass_flow", 1_000.0 / 3_600.0),
    "mol/s": _unit("molar_flow", 1.0),
    "kmol/h": _unit("molar_flow", 1_000.0 / 3_600.0),
    "W": _unit("power", 1.0),
    "kW": _unit("power", 1_000.0),
    "MW": _unit("power", 1_000_000.0),
    "kJ/h": _unit("power", 1_000.0 / 3_600.0),
    "s": _unit("time", 1.0),
    "min": _unit("time", 60.0),
    "h": _unit("time", 3_600.0),
    "kg/m3": _unit("density", 1.0),
    "Pa*s": _unit("viscosity", 1.0),
    "cP": _unit("viscosity", 0.001),
    "fraction": _unit("fraction", 1.0),
    "%": _unit("fraction", 0.01),
    "dimensionless": _unit("dimensionless", 1.0),
}


def normalize_unit(unit: str) -> str:
    aliases = {
        "°C": "C",
        "deg C": "C",
        "kg/hr": "kg/h",
        "kmol/hr": "kmol/h",
        "kJ/hr": "kJ/h",
        "wtfrac": "fraction",
    }
    return aliases.get(unit.strip(), unit.strip())


def dimension_of(unit: str) -> str:
    normalized = normalize_unit(unit)
    try:
        return _UNITS[normalized].dimension
    except KeyError as exc:
        raise UnitError(f"Unknown unit: {unit}") from exc


def convert(value: float, from_unit: str, to_unit: str) -> float:
    if not math.isfinite(float(value)):
        raise UnitError("Unit conversion requires a finite value")
    source_name = normalize_unit(from_unit)
    target_name = normalize_unit(to_unit)
    try:
        source = _UNITS[source_name]
        target = _UNITS[target_name]
    except KeyError as exc:
        missing = source_name if source_name not in _UNITS else target_name
        raise UnitError(f"Unknown unit: {missing}") from exc
    if source.dimension != target.dimension:
        raise UnitError(
            f"Incompatible units: {from_unit} ({source.dimension}) -> "
            f"{to_unit} ({target.dimension})"
        )
    result = target.from_base(source.to_base(float(value)))
    if not math.isfinite(result):
        raise UnitError("Unit conversion produced a non-finite value")
    return result
