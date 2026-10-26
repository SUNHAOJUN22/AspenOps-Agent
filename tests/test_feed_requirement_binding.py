from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from aspenops_nexus.compilation_plan import compile_process_design
from aspenops_nexus.design_validation import validate_design_documents
from aspenops_nexus.process_ir_v2 import ProcessDesignIR
from aspenops_nexus.process_requirement import ProcessRequirementDocument
from aspenops_nexus.simulator_capabilities import get_builtin_capability_profile

ROOT = Path(__file__).resolve().parents[1]


def documents() -> tuple[dict[str, Any], dict[str, Any]]:
    requirement = json.loads(
        (ROOT / "examples/process-requirement-v1.example.json").read_text(encoding="utf-8")
    )
    design = json.loads(
        (ROOT / "examples/process-design-v2.example.json").read_text(encoding="utf-8")
    )
    design["requirement_hash"] = ProcessRequirementDocument.from_dict(requirement).digest()
    return requirement, design


def relink(requirement: dict[str, Any], design: dict[str, Any]) -> None:
    design["requirement_hash"] = ProcessRequirementDocument.from_dict(requirement).digest()


def codes(report: dict[str, Any]) -> set[str]:
    return {issue["code"] for issue in report["design_contract"]["issues"]}


@pytest.mark.parametrize("index,value", [(0, 200.0), (1, 150.0), (2, 20.0)])
def test_changed_feed_quantity_cannot_authorize_offline_plan(index: int, value: float) -> None:
    requirement, design = documents()
    design["streams"][0]["parameters"][index]["value"] = value
    report = validate_design_documents(requirement, design)
    assert report["valid"] is False
    assert report["status"] == "NEEDS_ENGINEERING_INPUT"
    assert report["preview"] is None
    assert "feeds.quantity_mismatch" in codes(report)


@pytest.mark.parametrize(
    "values",
    [
        [(100_000.0, "mol/h"), (298.15, "K"), (120.0, "kPa")],
        [(100.0 / 3.6, "mol/s"), (77.0, "degF"), (120_000.0, "Pa")],
    ],
)
def test_equivalent_feed_units_preserve_plan(values: list[tuple[float, str]]) -> None:
    # Independent unit identities: 1 kmol = 1000 mol; 1 h = 3600 s;
    # K = degC + 273.15; degF = 9/5 * degC + 32; 1 bar = 100000 Pa.
    requirement, design = documents()
    for parameter, (value, unit) in zip(design["streams"][0]["parameters"], values, strict=True):
        parameter.update(value=value, unit=unit, status="APPROVED_DEFAULT")
    report = validate_design_documents(requirement, design)
    assert report["valid"] is True
    assert report["status"] == "PLAN_ONLY"
    assert "does not authorize COM execution" in report["boundary"]
    plan = compile_process_design(
        ProcessDesignIR.from_dict(design), get_builtin_capability_profile("aspen_plus", "15")
    )
    step = next(
        item
        for item in plan.steps
        if item.operation == "create_stream" and item.target_id == "S001"
    )
    assert plan.status == "PLAN_ONLY"
    assert step.payload["parameters"] == design["streams"][0]["parameters"]


@pytest.mark.parametrize("field,index", [("total_flow", 0), ("temperature", 1), ("pressure", 2)])
def test_missing_feed_quantity_is_not_reconstructed_from_requirement(
    field: str, index: int
) -> None:
    requirement, design = documents()
    removed = design["streams"][0]["parameters"].pop(index)
    assert removed["name"] == field.upper()
    report = validate_design_documents(requirement, design)
    assert report["valid"] is False
    assert "feeds.quantity_missing" in codes(report)


@pytest.mark.parametrize("status", ["UNKNOWN", "INFERRED_PENDING_APPROVAL"])
@pytest.mark.parametrize("side", ["requirement", "design"])
def test_pending_quantity_never_inherits_approval_from_other_document(
    side: str, status: str
) -> None:
    requirement, design = documents()
    if side == "requirement":
        requirement["feeds"][0]["pressure"]["status"] = status
        relink(requirement, design)
    else:
        design["streams"][0]["parameters"][2]["status"] = status
    report = validate_design_documents(requirement, design)
    assert report["valid"] is False
    assert "feeds.quantity_invalid" in codes(report)


@pytest.mark.parametrize(
    "change",
    [{"unit": None}, {"unit": "kg/h"}, {"unit": "unregistered"}, {"value": "100"}],
)
@pytest.mark.parametrize("side", ["requirement", "design"])
def test_feed_quantity_requires_explicit_compatible_numeric_units(
    side: str, change: dict[str, Any]
) -> None:
    requirement, design = documents()
    if side == "requirement":
        requirement["feeds"][0]["total_flow"].update(change)
        relink(requirement, design)
    else:
        design["streams"][0]["parameters"][0].update(change)
    report = validate_design_documents(requirement, design)
    assert report["valid"] is False
    assert "feeds.quantity_invalid" in codes(report)


@pytest.mark.parametrize(
    "requirement_unit,requirement_value,design_unit,design_value",
    [("kg/h", 3600.0, "kg/s", 1.0), ("m3/h", 3.6, "L/s", 1.0)],
)
def test_flow_comparison_preserves_explicit_mass_or_volume_basis(
    requirement_unit: str, requirement_value: float, design_unit: str, design_value: float
) -> None:
    requirement, design = documents()
    requirement["feeds"][0]["total_flow"].update(value=requirement_value, unit=requirement_unit)
    design["streams"][0]["parameters"][0].update(value=design_value, unit=design_unit)
    relink(requirement, design)
    assert validate_design_documents(requirement, design)["valid"] is True


def test_matching_wrong_quantity_dimension_is_still_invalid() -> None:
    requirement, design = documents()
    requirement["feeds"][0]["temperature"]["unit"] = "bar"
    design["streams"][0]["parameters"][1]["unit"] = "bar"
    relink(requirement, design)
    assert "feeds.quantity_invalid" in codes(validate_design_documents(requirement, design))


def test_requirement_uncertainty_does_not_authorize_changed_feed_setpoint() -> None:
    requirement, design = documents()
    requirement["feeds"][0]["total_flow"]["uncertainty"] = 5.0
    design["streams"][0]["parameters"][0]["value"] = 100.01
    relink(requirement, design)
    assert "feeds.quantity_mismatch" in codes(validate_design_documents(requirement, design))


def test_relative_roundoff_does_not_hide_a_doubled_subnormal_flow() -> None:
    requirement, design = documents()
    requirement["feeds"][0]["total_flow"].update(value=5e-324, unit="mol/s")
    design["streams"][0]["parameters"][0].update(value=1e-323, unit="mol/s")
    relink(requirement, design)
    assert "feeds.quantity_mismatch" in codes(validate_design_documents(requirement, design))


@pytest.mark.parametrize("index,value,unit", [(0, 0.0, "kg/s"), (1, 0.0, "K"), (2, -1.0, "Pa")])
def test_invalid_physical_setpoints_do_not_bind_even_when_both_documents_agree(
    index: int, value: float, unit: str
) -> None:
    requirement, design = documents()
    field = ("total_flow", "temperature", "pressure")[index]
    requirement["feeds"][0][field].update(value=value, unit=unit)
    design["streams"][0]["parameters"][index].update(value=value, unit=unit)
    relink(requirement, design)
    assert "feeds.quantity_invalid" in codes(validate_design_documents(requirement, design))


def test_unique_feed_source_binding_does_not_depend_on_stream_order_or_name() -> None:
    requirement, design = documents()
    design["streams"][0]["id"] = "RENAMED_FEED"
    design["streams"].reverse()
    report = validate_design_documents(requirement, design)
    assert report["valid"] is True


@pytest.mark.parametrize("mode", ["missing", "multiple"])
def test_feed_boundary_requires_one_unambiguous_outgoing_material_stream(mode: str) -> None:
    requirement, design = documents()
    if mode == "missing":
        design["streams"].pop(0)
    else:
        extra = deepcopy(design["streams"][0])
        extra["id"] = "EXTRA_FEED"
        design["streams"].append(extra)
        # Allowing fan-out on ports does not define a feed-flow allocation contract.
        design["equipment"][0]["ports"][0]["multiple"] = True
        design["equipment"][1]["ports"][0]["multiple"] = True
    report = validate_design_documents(requirement, design)
    assert "feeds.boundary_stream_count" in codes(report)
    assert report["valid"] is False


def test_feed_component_scope_is_checked_at_its_boundary() -> None:
    requirement, design = documents()
    design["streams"][0]["components"] = ["ETHANOL"]
    report = validate_design_documents(requirement, design)
    assert report["valid"] is False
    assert "feeds.components_mismatch" in codes(report)


@pytest.mark.parametrize("location", ["parameters", "design_specs"])
def test_feed_equipment_cannot_add_an_ambiguous_second_quantity_source(location: str) -> None:
    requirement, design = documents()
    duplicate = deepcopy(design["streams"][0]["parameters"][0])
    duplicate["value"] = 200.0
    design["equipment"][0][location].append(duplicate)
    report = validate_design_documents(requirement, design)
    assert report["valid"] is False
    assert "feeds.quantity_location_ambiguous" in codes(report)


def test_two_feeds_keep_their_own_component_and_quantity_contracts() -> None:
    requirement, design = documents()
    second_feed = deepcopy(requirement["feeds"][0])
    second_feed["id"] = "FEED_002"
    second_feed["components"] = ["WATER"]
    second_feed["composition"] = [
        {"component_id": "WATER", "fraction": 1.0, "basis": "mole", "status": "USER_PROVIDED"}
    ]
    second_feed["total_flow"]["value"] = 50.0
    requirement["feeds"].append(second_feed)
    second_equipment = deepcopy(design["equipment"][0])
    second_equipment["id"] = "FEED_002"
    design["equipment"].append(second_equipment)
    second_stream = deepcopy(design["streams"][0])
    second_stream.update(id="SECOND_FEED", source={"equipment_id": "FEED_002", "port_id": "OUT"})
    second_stream["components"] = ["WATER"]
    second_stream["parameters"][0]["value"] = 50.0
    design["streams"].append(second_stream)
    design["equipment"][1]["ports"][0]["multiple"] = True
    relink(requirement, design)
    assert validate_design_documents(requirement, design)["valid"] is True
    design["streams"][0]["source"], second_stream["source"] = (
        second_stream["source"],
        design["streams"][0]["source"],
    )
    report = validate_design_documents(requirement, design)
    assert report["valid"] is False
    assert {"feeds.components_mismatch", "feeds.quantity_mismatch"} <= codes(report)
