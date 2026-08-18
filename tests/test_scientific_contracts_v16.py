"""Focused counterexamples for the AspenOps V16 scientific contracts."""

import pytest

from aspenops_nexus.scientific_contracts_v16 import (
    Quantity,
    component_balance,
    normalized_objective,
    qualification_status,
)


def mass_flow(value: float, unit: str = "kg/h", scale: float = 1.0 / 3600.0) -> Quantity:
    return Quantity(value, unit, "mass_flow", scale)


def test_equal_total_flow_cannot_hide_species_substitution() -> None:
    decision = component_balance(
        {"A": mass_flow(100.0)},
        {"B": mass_flow(100.0)},
        abs_tolerance_si=1.0e-12,
        rel_tolerance=1.0e-12,
    )
    assert decision.status == "FAIL"
    assert set(decision.reason_codes) == {
        "COMPONENT_RESIDUAL:A",
        "COMPONENT_RESIDUAL:B",
    }


def test_units_are_canonicalized_before_balance() -> None:
    decision = component_balance(
        {"A": mass_flow(3.6)},
        {"A": mass_flow(0.001, "kg/s", 1.0)},
        abs_tolerance_si=1.0e-12,
        rel_tolerance=1.0e-12,
    )
    assert decision.status == "PASS"


def test_boolean_and_nonfinite_quantities_are_rejected() -> None:
    with pytest.raises(TypeError):
        Quantity(True, "kg/s", "mass_flow", 1.0).si()
    with pytest.raises(ValueError):
        Quantity(float("nan"), "kg/s", "mass_flow", 1.0).si()


def test_dimensionless_objective_is_unit_representation_invariant() -> None:
    kilowatt_form = normalized_objective(
        {"energy": 110.0, "cost": 80.0},
        {"energy": 100.0, "cost": 100.0},
        {"energy": 20.0, "cost": 40.0},
        {"energy": 0.4, "cost": 0.6},
    )
    watt_form = normalized_objective(
        {"energy": 110_000.0, "cost": 80.0},
        {"energy": 100_000.0, "cost": 100.0},
        {"energy": 20_000.0, "cost": 40.0},
        {"energy": 0.4, "cost": 0.6},
    )
    assert kilowatt_form == pytest.approx(watt_form)


def test_software_pass_is_not_aspen_certification() -> None:
    assert (
        qualification_status(
            software_pass=True,
            licensed_receipt_valid=False,
            engineering_approval_valid=False,
        )
        == "PENDING_REAL_ASPEN_CERTIFICATION"
    )
