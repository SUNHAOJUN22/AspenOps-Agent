from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from aspenops_nexus.design_validation import (
    load_strict_json_object,
    validate_design_documents,
    validate_design_files,
)
from aspenops_nexus.engineering_rules import (
    _cycle_paths,
    _finite_parameter,
    _validate_equipment_contract,
    _validate_reaction,
    validate_process_design,
)
from aspenops_nexus.flowsheet_preview import render_flowsheet_preview
from aspenops_nexus.process_ir_v2 import (
    EquipmentDefinition,
    ParameterDefinition,
    ProcessDesignIR,
    PropertyMethodDefinition,
    ReactionDefinition,
)
from aspenops_nexus.process_requirement import ProcessRequirementDocument

ROOT = Path(__file__).resolve().parents[1]
REQUIREMENT = ROOT / "examples/process-requirement-v1.example.json"
DESIGN = ROOT / "examples/process-design-v2.example.json"


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def port(
    identifier: str,
    direction: str,
    domain: str = "material",
    *,
    required: bool = False,
    multiple: bool = False,
) -> dict[str, Any]:
    return {
        "id": identifier,
        "direction": direction,
        "domain": domain,
        "required": required,
        "multiple": multiple,
    }


def parameter(
    name: str,
    value: Any,
    *,
    status: str = "USER_PROVIDED",
    unit: str | None = None,
) -> dict[str, Any]:
    return {"name": name, "value": value, "unit": unit, "status": status}


def equipment(
    kind: str,
    ports: list[dict[str, Any]],
    *,
    parameters: list[dict[str, Any]] | None = None,
    specs: list[dict[str, Any]] | None = None,
) -> EquipmentDefinition:
    return EquipmentDefinition.from_dict(
        {
            "id": "UNIT_001",
            "display_name": kind,
            "kind": kind,
            "vendor_type": None,
            "ports": ports,
            "parameters": parameters or [],
            "design_specs": specs or [],
            "contract_version": "1",
        },
        label="equipment",
    )


def codes(item: EquipmentDefinition, reaction_count: int = 0) -> set[str]:
    return {
        issue.code
        for issue in _validate_equipment_contract(item, "equipment[0]", reaction_count)
    }


def test_equipment_contract_failure_branches() -> None:
    assert "equipment.feed_ports" in codes(equipment("feed", [port("IN", "in")]))
    assert "equipment.product_ports" in codes(equipment("product", [port("OUT", "out")]))
    assert "equipment.mixer_ports" in codes(equipment("mixer", [port("OUT", "out")]))

    splitter = codes(
        equipment("splitter", [port("IN", "in"), port("OUT", "out")])
    )
    assert {"equipment.splitter_ports", "equipment.specification_missing"}.issubset(splitter)

    thermal = codes(
        equipment(
            "heater",
            [
                port("E1", "in", "energy"),
                port("E2", "out", "energy"),
            ],
        )
    )
    assert {
        "equipment.thermal_ports",
        "equipment.thermal_energy_ports",
        "equipment.specification_missing",
    }.issubset(thermal)

    separator = codes(equipment("flash2", [port("IN", "in")]))
    assert {"equipment.separator_ports", "equipment.specification_missing"}.issubset(separator)

    pressure = codes(
        equipment(
            "compressor",
            [],
            parameters=[
                parameter("OUTLET_PRESSURE", 10.0),
                parameter("EFFICIENCY", 2.0),
            ],
        )
    )
    assert {"equipment.pressure_ports", "equipment.efficiency_range"}.issubset(pressure)

    column = codes(
        equipment(
            "distillation_column",
            [],
            parameters=[
                parameter("TOTAL_STAGES", 1.5),
                parameter("FEED_STAGE", 5),
            ],
            specs=[parameter("REFLUX_RATIO", 2.0)],
        )
    )
    assert {
        "equipment.column_ports",
        "equipment.column_stages",
        "equipment.column_feed_stage",
        "equipment.column_degrees_of_freedom",
    }.issubset(column)

    reactor = codes(equipment("reactor_cstr", []), reaction_count=0)
    assert {
        "equipment.reactor_ports",
        "equipment.reaction_set_missing",
        "equipment.specification_missing",
    }.issubset(reactor)

    valve = codes(equipment("valve", []))
    assert {"equipment.valve_ports", "equipment.specification_missing"}.issubset(valve)
    assert "equipment.contract_unavailable" in codes(equipment("unknown_unit", []))

    pending = equipment(
        "heater",
        [port("IN", "in"), port("OUT", "out")],
        parameters=[parameter("DUTY", 1.0, status="UNKNOWN")],
    )
    assert "equipment.parameter_unapproved" in codes(pending)


def test_equipment_contract_success_branches() -> None:
    valid = (
        equipment("feed", [port("OUT", "out")]),
        equipment("product", [port("IN", "in")]),
        equipment("mixer", [port("IN", "in"), port("OUT", "out")]),
        equipment(
            "splitter",
            [port("IN", "in"), port("O1", "out"), port("O2", "out")],
            parameters=[parameter("SPLIT_FRACTION", 0.5)],
        ),
        equipment(
            "cooler",
            [port("IN", "in"), port("OUT", "out"), port("Q", "out", "energy")],
            parameters=[parameter("OUTLET_TEMPERATURE", 20.0)],
        ),
        equipment(
            "separator",
            [port("IN", "in"), port("VAP", "out"), port("LIQ", "out")],
            parameters=[parameter("PRESSURE", 1.0)],
        ),
        equipment(
            "pump",
            [port("IN", "in"), port("OUT", "out")],
            parameters=[
                parameter("OUTLET_PRESSURE", 10.0),
                parameter("EFFICIENCY", 0.8),
            ],
        ),
        equipment(
            "distillation_column",
            [port("IN", "in"), port("D", "out"), port("B", "out")],
            parameters=[
                parameter("TOTAL_STAGES", 20),
                parameter("FEED_STAGE", 10),
            ],
            specs=[
                parameter("REFLUX_RATIO", 2.0),
                parameter("DISTILLATE_RATE", 40.0),
            ],
        ),
        equipment(
            "reactor_pfr",
            [port("IN", "in"), port("OUT", "out")],
            parameters=[parameter("VOLUME", 1.0)],
        ),
        equipment(
            "valve",
            [port("IN", "in"), port("OUT", "out")],
            parameters=[parameter("PRESSURE_DROP", 1.0)],
        ),
    )
    for item in valid:
        reaction_count = 1 if item.kind.startswith("reactor_") else 0
        assert _validate_equipment_contract(item, "equipment[0]", reaction_count) == []


def test_parameter_and_reaction_helper_branches() -> None:
    approved = ParameterDefinition.from_dict(
        parameter("EFFICIENCY", 0.8),
        label="parameter",
    )
    pending = ParameterDefinition.from_dict(
        parameter("PENDING", 1.0, status="UNKNOWN"),
        label="parameter",
    )
    discrete = ParameterDefinition("MODE", "fixed", None, "USER_PROVIDED")
    nonfinite = ParameterDefinition("VALUE", float("inf"), None, "USER_PROVIDED")
    assert _finite_parameter({"EFFICIENCY": approved}, "EFFICIENCY") == 0.8
    assert _finite_parameter({}, "EFFICIENCY") is None
    assert _finite_parameter({"MODE": discrete}, "MODE") is None
    assert _finite_parameter({"VALUE": nonfinite}, "VALUE") is None

    valid = ReactionDefinition.from_dict(
        {
            "id": "RXN_001",
            "kind": "stoichiometric",
            "stoichiometry": {"A": -1.0, "B": 1.0},
            "phase": "liquid",
            "status": "USER_PROVIDED",
            "parameters": [],
        },
        label="reaction",
    )
    assert _validate_reaction(valid, {"A", "B"}, "reaction") == []

    invalid = replace(
        valid,
        stoichiometry={"UNKNOWN": 1.0},
        status="UNKNOWN",
        parameters=(pending,),
    )
    reaction_codes = {
        issue.code for issue in _validate_reaction(invalid, {"A", "B"}, "reaction")
    }
    assert {
        "reaction.unknown_component",
        "reaction.stoichiometry_direction",
        "reaction.unapproved",
        "reaction.parameter_unapproved",
    } == reaction_codes


def design_document() -> dict[str, Any]:
    return load(DESIGN)


def validation_codes(value: dict[str, Any]) -> set[str]:
    return {
        issue.code for issue in validate_process_design(ProcessDesignIR.from_dict(value)).issues
    }


def test_design_validation_global_component_and_property_branches() -> None:
    value = design_document()
    value["components"] = []
    value["equipment"] = []
    value["streams"] = []
    value["property_method"]["status"] = "UNKNOWN"
    value["property_method"]["vendor"] = "hysys"
    value["property_method"]["supported_versions"] = ["14"]
    codes_found = validation_codes(value)
    assert {
        "components.empty",
        "equipment.empty",
        "property_method.unapproved",
        "property_method.vendor_mismatch",
        "property_method.version_unqualified",
    }.issubset(codes_found)

    value = design_document()
    value["components"][0]["status"] = "UNKNOWN"
    value["components"][0]["vendor_ids"] = {}
    codes_found = validation_codes(value)
    assert {"component.unapproved", "component.vendor_mapping_missing"}.issubset(codes_found)

    value = design_document()
    value["components"][0]["pseudo_component"] = True
    value["components"][0]["vendor_ids"] = {}
    assert "component.vendor_mapping_missing" not in validation_codes(value)


def test_design_validation_stream_endpoint_and_content_branches() -> None:
    value = design_document()
    value["streams"][0]["source"] = {"equipment_id": "MISSING", "port_id": "OUT"}
    value["streams"][0]["target"] = {"equipment_id": "MISSING", "port_id": "IN"}
    codes_found = validation_codes(value)
    assert {
        "stream.source_equipment_missing",
        "stream.target_equipment_missing",
        "stream.source_port_missing",
        "stream.target_port_missing",
    }.issubset(codes_found)

    value = design_document()
    value["streams"][0]["source"] = {"equipment_id": "HTR_001", "port_id": "IN"}
    value["streams"][0]["target"] = {"equipment_id": "HTR_001", "port_id": "OUT"}
    codes_found = validation_codes(value)
    assert {
        "stream.source_direction",
        "stream.target_direction",
        "stream.self_connection",
    }.issubset(codes_found)

    value = design_document()
    value["streams"][0]["components"] = ["UNKNOWN"]
    value["streams"][1]["components"] = []
    value["streams"][2]["kind"] = "energy"
    value["streams"][2]["parameters"] = [parameter("DUTY", 1.0, status="UNKNOWN")]
    codes_found = validation_codes(value)
    assert {
        "stream.unknown_component",
        "stream.components_empty",
        "stream.source_domain",
        "stream.target_domain",
        "stream.nonmaterial_components",
        "stream.parameter_unapproved",
    }.issubset(codes_found)


def test_design_validation_port_multiple_connection_branch() -> None:
    value = design_document()
    duplicate = deepcopy(value["streams"][0])
    duplicate["id"] = "S999"
    duplicate["target"] = {"equipment_id": "SEP_001", "port_id": "IN"}
    value["streams"].append(duplicate)
    assert "port.multiple_connections" in validation_codes(value)


def test_design_validation_recycle_branches() -> None:
    value = design_document()
    value["recycles"] = [
        {
            "id": "RECYCLE_001",
            "stream_id": "MISSING",
            "tear_stream_id": "S001",
            "convergence_variables": ["FLOW"],
            "tolerance": 1e-6,
            "max_iterations": 50,
            "acceleration": "wegstein",
            "status": "UNKNOWN",
        }
    ]
    codes_found = validation_codes(value)
    assert {
        "recycle.stream_missing",
        "recycle.tear_missing",
        "recycle.unapproved",
        "recycle.no_graph_cycle",
    }.issubset(codes_found)

    value = design_document()
    value["streams"].append(
        {
            "id": "TEAR_001",
            "display_name": "Tear",
            "kind": "tear",
            "source": {"equipment_id": "SEP_001", "port_id": "LIQ"},
            "target": {"equipment_id": "HTR_001", "port_id": "IN"},
            "components": ["ETHANOL", "WATER"],
            "parameters": [],
        }
    )
    design = ProcessDesignIR.from_dict(value)
    assert _cycle_paths(design)
    codes_found = {issue.code for issue in validate_process_design(design).issues}
    assert "topology.recycle_contract_missing" in codes_found
    assert "recycle.tear_unowned" in codes_found


def test_engineering_report_serialization() -> None:
    report = validate_process_design(ProcessDesignIR.from_dict(design_document()))
    payload = report.to_dict()
    assert payload["valid"] is True
    assert payload["blockers"] == []
    assert payload["counts"]["equipment"] == 5


def linked_documents() -> tuple[dict[str, Any], dict[str, Any]]:
    requirement = load(REQUIREMENT)
    parsed = ProcessRequirementDocument.from_dict(requirement)
    design = load(DESIGN)
    design["requirement_hash"] = parsed.digest()
    return requirement, design


def test_design_validation_strict_json_and_file_paths(tmp_path: Path) -> None:
    duplicate = tmp_path / "duplicate.json"
    duplicate.write_text('{"x":1,"x":2}', encoding="utf-8")
    with pytest.raises(ValueError, match="Duplicate JSON key"):
        load_strict_json_object(duplicate)
    nonfinite = tmp_path / "nonfinite.json"
    nonfinite.write_text('{"x":NaN}', encoding="utf-8")
    with pytest.raises(ValueError, match="non-finite"):
        load_strict_json_object(nonfinite)
    root = tmp_path / "root.json"
    root.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="root must be an object"):
        load_strict_json_object(root)

    requirement, design = linked_documents()
    requirement_path = tmp_path / "requirement.json"
    design_path = tmp_path / "design.json"
    requirement_path.write_text(json.dumps(requirement), encoding="utf-8")
    design_path.write_text(json.dumps(design), encoding="utf-8")
    report = validate_design_files(requirement_path, design_path)
    assert report["valid"] is True
    assert report["preview"] is not None

    design["requirement_hash"] = "0" * 64
    report = validate_design_documents(requirement, design)
    assert report["valid"] is False
    assert report["preview"] is None


def test_preview_empty_missing_endpoint_and_tear_paths() -> None:
    method = PropertyMethodDefinition(
        id="NRTL",
        vendor="aspen_plus",
        supported_versions=("15",),
        phase_scope=("vapor-liquid",),
        rationale="test",
        status="APPROVED_DEFAULT",
    )
    empty = ProcessDesignIR(
        name="Empty",
        target_simulator="aspen_plus",
        target_version="15",
        requirement_hash="a" * 64,
        components=(),
        property_method=method,
        equipment=(),
        streams=(),
    )
    preview = render_flowsheet_preview(empty)
    assert preview.positions == ()
    assert "<svg" in preview.svg

    value = design_document()
    value["streams"][0]["source"] = {"equipment_id": "MISSING", "port_id": "OUT"}
    missing = render_flowsheet_preview(ProcessDesignIR.from_dict(value))
    assert "S001" in {edge["id"] for edge in missing.graph["edges"]}

    value = design_document()
    value["streams"].append(
        {
            "id": "TEAR_001",
            "display_name": "Recycle tear",
            "kind": "tear",
            "source": {"equipment_id": "SEP_001", "port_id": "LIQ"},
            "target": {"equipment_id": "HTR_001", "port_id": "IN"},
            "components": ["ETHANOL", "WATER"],
            "parameters": [],
        }
    )
    tear = render_flowsheet_preview(ProcessDesignIR.from_dict(value))
    assert "Recycle tear" in tear.svg
