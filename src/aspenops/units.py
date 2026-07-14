from __future__ import annotations

import math
from dataclasses import dataclass


class UnitError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class UnitSpec:
    dimension: str
    scale: float = 1.0
    offset: float = 0.0

    def to_base(self, value: float) -> float:
        return value * self.scale + self.offset

    def from_base(self, value: float) -> float:
        return (value - self.offset) / self.scale


_UNITS: dict[str, UnitSpec] = {
    "1": UnitSpec("dimensionless"),
    "fraction": UnitSpec("dimensionless"),
    "%": UnitSpec("dimensionless", 0.01),
    "ppm": UnitSpec("dimensionless", 1e-6),
    "K": UnitSpec("absolute_temperature"),
    "degC": UnitSpec("absolute_temperature", 1.0, 273.15),
    "C": UnitSpec("absolute_temperature", 1.0, 273.15),
    "degF": UnitSpec("absolute_temperature", 5.0 / 9.0, 255.3722222222222),
    "F": UnitSpec("absolute_temperature", 5.0 / 9.0, 255.3722222222222),
    "delta_K": UnitSpec("temperature_difference"),
    "delta_degC": UnitSpec("temperature_difference"),
    "delta_degF": UnitSpec("temperature_difference", 5.0 / 9.0),
    "Pa": UnitSpec("pressure"),
    "kPa": UnitSpec("pressure", 1_000.0),
    "MPa": UnitSpec("pressure", 1_000_000.0),
    "bar": UnitSpec("pressure", 100_000.0),
    "mbar": UnitSpec("pressure", 100.0),
    "atm": UnitSpec("pressure", 101_325.0),
    "psi": UnitSpec("pressure", 6_894.757293168),
    "kg/s": UnitSpec("mass_flow"),
    "kg/h": UnitSpec("mass_flow", 1.0 / 3600.0),
    "t/h": UnitSpec("mass_flow", 1000.0 / 3600.0),
    "g/s": UnitSpec("mass_flow", 0.001),
    "mol/s": UnitSpec("molar_flow"),
    "mol/h": UnitSpec("molar_flow", 1.0 / 3600.0),
    "kmol/s": UnitSpec("molar_flow", 1000.0),
    "kmol/h": UnitSpec("molar_flow", 1000.0 / 3600.0),
    "W": UnitSpec("power"),
    "kW": UnitSpec("power", 1_000.0),
    "MW": UnitSpec("power", 1_000_000.0),
    "J/s": UnitSpec("power"),
    "kJ/h": UnitSpec("power", 1000.0 / 3600.0),
    "m3/s": UnitSpec("volumetric_flow"),
    "m3/h": UnitSpec("volumetric_flow", 1.0 / 3600.0),
    "L/s": UnitSpec("volumetric_flow", 0.001),
    "L/min": UnitSpec("volumetric_flow", 0.001 / 60.0),
    "kg/m3": UnitSpec("density"),
    "g/cm3": UnitSpec("density", 1000.0),
    "Pa.s": UnitSpec("viscosity"),
    "cP": UnitSpec("viscosity", 0.001),
}


def supported_units() -> dict[str, str]:
    return {name: spec.dimension for name, spec in sorted(_UNITS.items())}


def dimension(unit: str | None) -> str | None:
    if unit is None:
        return None
    try:
        return _UNITS[unit].dimension
    except KeyError as exc:
        raise UnitError(f"Unsupported unit: {unit!r}") from exc


def convert(value: float, source: str | None, target: str | None) -> float:
    numeric = float(value)
    if not math.isfinite(numeric):
        raise UnitError("Unit conversion requires a finite value")
    if source is None or target is None or source == target:
        return numeric
    try:
        src = _UNITS[source]
        dst = _UNITS[target]
    except KeyError as exc:
        raise UnitError(f"Unsupported unit conversion: {source!r} -> {target!r}") from exc
    if src.dimension != dst.dimension:
        raise UnitError(
            f"Incompatible units: {source!r} ({src.dimension}) and {target!r} ({dst.dimension})"
        )
    return dst.from_base(src.to_base(numeric))
