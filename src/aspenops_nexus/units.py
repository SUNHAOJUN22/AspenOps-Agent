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

    def to_base(self, value: float) -> float:
        return value * self.to_base_scale + self.to_base_offset

    def from_base(self, value: float) -> float:
        return (value - self.to_base_offset) / self.to_base_scale


_UNITS: dict[str, UnitSpec] = {
    "1": UnitSpec("dimensionless"),
    "fraction": UnitSpec("dimensionless"),
    "%": UnitSpec("dimensionless", 0.01),
    "ppm": UnitSpec("dimensionless", 1e-6),
    "K": UnitSpec("temperature"),
    "C": UnitSpec("temperature", 1.0, 273.15),
    "degC": UnitSpec("temperature", 1.0, 273.15),
    "F": UnitSpec("temperature", 5.0 / 9.0, 255.3722222222222),
    "degF": UnitSpec("temperature", 5.0 / 9.0, 255.3722222222222),
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

_SUPPORTED_UNITS: tuple[tuple[str, str], ...] = tuple(
    (name, spec.dimension) for name, spec in sorted(_UNITS.items())
)
_CONVERSIONS: dict[tuple[str, str], tuple[float, float, float, float]] = {
    (source, target): (
        source_spec.to_base_scale,
        source_spec.to_base_offset,
        target_spec.to_base_offset,
        target_spec.to_base_scale,
    )
    for source, source_spec in _UNITS.items()
    for target, target_spec in _UNITS.items()
    if source_spec.dimension == target_spec.dimension
}


def supported_units() -> dict[str, str]:
    return dict(_SUPPORTED_UNITS)


def dimension(unit: str | None) -> str | None:
    if unit is None:
        return None
    try:
        return _UNITS[unit].dimension
    except KeyError as exc:
        raise UnitError(f"Unsupported unit: {unit!r}") from exc


def convert(value: float, source: str | None, target: str | None) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise UnitError("Unit conversion value must be finite numeric")
    try:
        numeric = float(value)
    except OverflowError as exc:
        raise UnitError("Unit conversion value must be finite numeric") from exc
    if not math.isfinite(numeric):
        raise UnitError("Unit conversion value must be finite numeric")
    if source is not None and not isinstance(source, str):
        raise UnitError("Source unit must be a string or null")
    if target is not None and not isinstance(target, str):
        raise UnitError("Target unit must be a string or null")
    if source is None or target is None:
        return numeric
    if source == target:
        if source not in _UNITS:
            raise UnitError(f"Unsupported unit conversion: {source!r} -> {target!r}")
        return numeric
    conversion = _CONVERSIONS.get((source, target))
    if conversion is None:
        source_spec = _UNITS.get(source)
        target_spec = _UNITS.get(target)
        if source_spec is None or target_spec is None:
            raise UnitError(f"Unsupported unit conversion: {source!r} -> {target!r}")
        raise UnitError(
            f"Incompatible units: {source!r} ({source_spec.dimension}) and "
            f"{target!r} ({target_spec.dimension})"
        )
    source_scale, source_offset, target_offset, target_scale = conversion
    converted = (numeric * source_scale + source_offset - target_offset) / target_scale
    if not math.isfinite(converted):
        raise UnitError("Unit conversion produced a non-finite value")
    return converted
