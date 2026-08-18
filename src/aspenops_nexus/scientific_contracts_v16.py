"""Fail-closed scientific contracts for AspenOps acceptance work."""

from __future__ import annotations

from dataclasses import dataclass
from math import fsum, isfinite
from typing import Mapping


class ContractError(ValueError):
    """Raised when a scientific contract is incomplete or inconsistent."""


def _real(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a non-Boolean real")
    number = float(value)
    if not isfinite(number):
        raise ContractError(f"{name} must be finite")
    return number


@dataclass(frozen=True, slots=True)
class Quantity:
    """A scalar value with an explicit dimension and SI conversion scale."""

    value: float
    unit: str
    dimension: str
    scale_to_si: float

    def si(self) -> float:
        number = _real(self.value, "value")
        scale = _real(self.scale_to_si, "scale_to_si")
        if scale <= 0.0 or not self.unit or not self.dimension:
            raise ContractError("invalid quantity metadata")
        converted = number * scale
        if not isfinite(converted):
            raise ContractError("conversion overflow")
        return converted


@dataclass(frozen=True, slots=True)
class BalanceDecision:
    """Component-wise balance result in a single canonical basis."""

    status: str
    residuals_si: Mapping[str, float]
    reason_codes: tuple[str, ...]


def component_balance(
    inputs: Mapping[str, Quantity],
    outputs: Mapping[str, Quantity],
    reaction_sources: Mapping[str, Quantity] | None = None,
    accumulation: Mapping[str, Quantity] | None = None,
    *,
    abs_tolerance_si: float,
    rel_tolerance: float,
) -> BalanceDecision:
    """Evaluate every component; total-flow cancellation is never sufficient."""

    absolute_tolerance = _real(abs_tolerance_si, "abs_tolerance_si")
    relative_tolerance = _real(rel_tolerance, "rel_tolerance")
    if absolute_tolerance < 0.0 or relative_tolerance < 0.0:
        raise ContractError("tolerances must be non-negative")

    sources = reaction_sources or {}
    inventory_rate = accumulation or {}
    all_quantities = [
        *inputs.values(),
        *outputs.values(),
        *sources.values(),
        *inventory_rate.values(),
    ]
    if not all_quantities:
        raise ContractError("at least one component is required")
    if len({quantity.dimension for quantity in all_quantities}) != 1:
        raise ContractError("one balance-basis dimension is required")

    components = sorted(set(inputs) | set(outputs) | set(sources) | set(inventory_rate))
    residuals: dict[str, float] = {}
    failures: list[str] = []
    for component in components:
        inlet = inputs[component].si() if component in inputs else 0.0
        outlet = outputs[component].si() if component in outputs else 0.0
        source = sources[component].si() if component in sources else 0.0
        accumulation_value = (
            inventory_rate[component].si() if component in inventory_rate else 0.0
        )
        residual = fsum((inlet, source, -outlet, -accumulation_value))
        residuals[component] = residual
        reference = max(
            abs(inlet),
            abs(outlet),
            abs(source),
            abs(accumulation_value),
            1.0e-30,
        )
        limit = absolute_tolerance + relative_tolerance * reference
        if abs(residual) > limit:
            failures.append(f"COMPONENT_RESIDUAL:{component}")

    return BalanceDecision(
        status="PASS" if not failures else "FAIL",
        residuals_si=residuals,
        reason_codes=tuple(failures),
    )


def normalized_objective(
    values: Mapping[str, float],
    references: Mapping[str, float],
    scales: Mapping[str, float],
    weights: Mapping[str, float],
) -> float:
    """Return a scalar objective composed only from dimensionless terms."""

    keys = set(values)
    if not keys or keys != set(references) or keys != set(scales) or keys != set(weights):
        raise ContractError("objective mappings must share the same non-empty key set")

    terms: list[float] = []
    weight_sum = 0.0
    for key in sorted(keys):
        value = _real(values[key], key)
        reference = _real(references[key], f"{key}.reference")
        scale = _real(scales[key], f"{key}.scale")
        weight = _real(weights[key], f"{key}.weight")
        if scale <= 0.0 or weight < 0.0:
            raise ContractError("scales must be positive and weights non-negative")
        weight_sum += weight
        terms.append(weight * (value - reference) / scale)

    if abs(weight_sum - 1.0) > 1.0e-12:
        raise ContractError("weights must sum to one")
    return fsum(terms)


def qualification_status(
    *,
    software_pass: bool,
    licensed_receipt_valid: bool,
    engineering_approval_valid: bool,
) -> str:
    """Keep software, licensed execution, and engineering acceptance separate."""

    flags = (software_pass, licensed_receipt_valid, engineering_approval_valid)
    if any(type(flag) is not bool for flag in flags):
        raise TypeError("typed Boolean flags are required")
    if not software_pass:
        return "SOFTWARE_FAIL"
    if not licensed_receipt_valid:
        return "PENDING_REAL_ASPEN_CERTIFICATION"
    if not engineering_approval_valid:
        return "ENGINEERING_ACCEPTANCE_HOLD"
    return "ENGINEERING_ACCEPTED"
