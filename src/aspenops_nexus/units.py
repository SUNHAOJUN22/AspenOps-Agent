from __future__ import annotations

import math
from dataclasses import dataclass


class UnitError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class UnitSpec:
    dimension: str
    to_base_scale: float = 1.0
    to_base_offset: float = 0.0

    def __post_init__(self) -> None:
        if not self.dimension:
            raise ValueError("Unit dimension must not be empty")
        if not math.isfinite(self.to_base_scale) or self.to_base_scale <= 0.0:
            raise ValueError("Unit scale must be finite and strictly positive")
        if not math.isfinite(self.to_base_offset):
            raise ValueError("Unit offset must be finite")

    def to_base(self, value: float) -> float:
        return value * self.to_base_scale + self.to_base_offset

    def from_base(self, value: float) -> float:
        return (value - self.to_base_offset) / self.to_base_scale


_UNITS: dict[str, UnitSpec] = {
    "1": UnitSpec("dimensionless"),
    "fraction": UnitSpec("dimensionless"),
    "%": UnitSpec("dimensionless", 0.01),
    "ppm": UnitSpec("dimensionless", 1e-6),
    "K": UnitSpec("absolute_temperature"),
    "C": UnitSpec("absolute_temperature", 1.0, 273.15),
    "degC": UnitSpec("absolute_temperature", 1.0, 273.15),
    "F": UnitSpec("absolute_temperature", 5.0 / 9.0, 255.3722222222222),
    "degF": UnitSpec("absolute_temperature", 5.0 / 9.0, 255.3722222222222),
    "delta_K": UnitSpec("temperature_difference"),
    "delta_C": UnitSpec("temperature_difference"),
    "delta_degC": UnitSpec("temperature_difference"),
    "delta_F": UnitSpec("temperature_difference", 5.0 / 9.0),
    "delta_degF": UnitSpec("temperature_difference", 5.0 / 9.0),
    "Pa": UnitSpec("pressure_absolute"),
    "kPa": UnitSpec("pressure_absolute", 1_000.0),
    "MPa": UnitSpec("pressure_absolute", 1_000_000.0),
    "bar": UnitSpec("pressure_absolute", 100_000.0),
    "mbar": UnitSpec("pressure_absolute", 100.0),
    "atm": UnitSpec("pressure_absolute", 101_325.0),
    "psi": UnitSpec("pressure_absolute", 6_894.757293168),
    "Pa(g)": UnitSpec("pressure_gauge"),
    "kPa(g)": UnitSpec("pressure_gauge", 1_000.0),
    "MPa(g)": UnitSpec("pressure_gauge", 1_000_000.0),
    "bar(g)": UnitSpec("pressure_gauge", 100_000.0),
    "mbar(g)": UnitSpec("pressure_gauge", 100.0),
    "psi(g)": UnitSpec("pressure_gauge", 6_894.757293168),
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
    "m3/s": UnitSpec("volume_flow"),
    "m3/h": UnitSpec("volume_flow", 1.0 / 3600.0),
    "L/s": UnitSpec("volume_flow", 0.001),
    "L/min": UnitSpec("volume_flow", 0.001 / 60.0),
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
    if source is None and target is None:
        return numeric
    if source is None or target is None:
        raise UnitError("Source and target units must either both be provided or both be omitted")
    try:
        src = _UNITS[source]
        dst = _UNITS[target]
    except KeyError as exc:
        raise UnitError(f"Unsupported unit conversion: {source!r} -> {target!r}") from exc
    if src.dimension != dst.dimension:
        raise UnitError(
            f"Incompatible units: {source!r} ({src.dimension}) and {target!r} ({dst.dimension})"
        )
    if source == target:
        return numeric
    base_value = src.to_base(numeric)
    if not math.isfinite(base_value):
        raise UnitError("Unit conversion overflowed the canonical representation")
    if src.dimension in {"absolute_temperature", "pressure_absolute"} and base_value < 0.0:
        raise UnitError(f"{src.dimension} cannot be negative in canonical units")
    converted = dst.from_base(base_value)
    if not math.isfinite(converted):
        raise UnitError("Unit conversion overflowed the target representation")
    return converted
