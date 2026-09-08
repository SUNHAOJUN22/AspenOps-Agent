from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from aspenops_nexus.engineering_rules import validate_process_design
from aspenops_nexus.process_ir_v2 import ProcessDesignIR

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples/process-design-v2.example.json"


def document() -> dict[str, Any]:
    value = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def blocker_codes(value: dict[str, Any]) -> set[str]:
    report = validate_process_design(ProcessDesignIR.from_dict(value))
    assert report.valid is False
    return {issue.code for issue in report.blockers}


def test_process_design_v2_roundtrip_and_engineering_rules_pass() -> None:
    design = ProcessDesignIR.from_dict(document())
    report = validate_process_design(design)
    assert report.valid is True
    assert report.blockers == ()
    assert report.counts == {
        "components": 2,
        "equipment": 5,
        "streams": 4,
        "reactions": 0,
        "recycles": 0,
        "blockers": 0,
        "warnings": 0,
    }
    assert ProcessDesignIR.from_dict(design.to_dict()).digest() == design.digest()


def test_process_design_digest_is_stable_under_list_order() -> None:
    first = ProcessDesignIR.from_dict(document())
    reordered = deepcopy(document())
    reordered["components"].reverse()
    reordered["equipment"].reverse()
    reordered["streams"].reverse()
    second = ProcessDesignIR.from_dict(reordered)
    assert first.digest() == second.digest()


def test_process_design_rejects_lowercase_internal_id() -> None:
    value = document()
    value["equipment"][0]["id"] = "feed_001"
    with pytest.raises(ValueError, match="must match"):
        ProcessDesignIR.from_dict(value)


def test_process_design_rejects_duplicate_equipment_ids() -> None:
    value = document()
    value["equipment"][1]["id"] = value["equipment"][0]["id"]
    with pytest.raises(ValueError, match="unique IDs"):
        ProcessDesignIR.from_dict(value)


def test_process_design_rejects_unsafe_display_name() -> None:
    value = document()
    value["equipment"][0]["display_name"] = "feed\u202eexe"
    with pytest.raises(ValueError, match="bidirectional"):
        ProcessDesignIR.from_dict(value)


def test_process_design_rejects_invalid_requirement_hash() -> None:
    value = document()
    value["requirement_hash"] = "not-a-digest"
    with pytest.raises(ValueError, match="SHA-256"):
        ProcessDesignIR.from_dict(value)


def test_rule_engine_rejects_port_direction_mismatch() -> None:
    value = document()
    value["streams"][0]["source"] = {
        "equipment_id": "HTR_001",
        "port_id": "IN",
    }
    assert "stream.source_direction" in blocker_codes(value)


def test_rule_engine_rejects_energy_stream_on_material_ports() -> None:
    value = document()
    value["streams"][1]["kind"] = "energy"
    value["streams"][1]["components"] = []
    codes = blocker_codes(value)
    assert "stream.source_domain" in codes
    assert "stream.target_domain" in codes


def test_rule_engine_rejects_pending_equipment_parameter() -> None:
    value = document()
    value["equipment"][1]["parameters"][0]["status"] = "INFERRED_PENDING_APPROVAL"
    codes = blocker_codes(value)
    assert "equipment.specification_missing" in codes
    assert "equipment.parameter_unapproved" in codes


def test_rule_engine_rejects_unqualified_property_method_version() -> None:
    value = document()
    value["property_method"]["supported_versions"] = ["14"]
    assert "property_method.version_unqualified" in blocker_codes(value)


def test_rule_engine_rejects_missing_component_vendor_mapping() -> None:
    value = document()
    value["components"][0]["vendor_ids"] = {}
    assert "component.vendor_mapping_missing" in blocker_codes(value)


def test_rule_engine_rejects_column_with_open_degrees_of_freedom() -> None:
    value = document()
    column = value["equipment"][2]
    column["kind"] = "distillation_column"
    column["parameters"] = [
        {
            "name": "TOTAL_STAGES",
            "value": 20,
            "unit": "1",
            "status": "USER_PROVIDED",
        },
        {
            "name": "FEED_STAGE",
            "value": 10,
            "unit": "1",
            "status": "USER_PROVIDED",
        },
    ]
    column["design_specs"] = [
        {
            "name": "REFLUX_RATIO",
            "value": 2.0,
            "unit": "1",
            "status": "USER_PROVIDED",
        }
    ]
    assert "equipment.column_degrees_of_freedom" in blocker_codes(value)


def test_rule_engine_rejects_column_feed_stage_outside_stage_range() -> None:
    value = document()
    column = value["equipment"][2]
    column["kind"] = "distillation_column"
    column["parameters"] = [
        {
            "name": "TOTAL_STAGES",
            "value": 20,
            "unit": "1",
            "status": "USER_PROVIDED",
        },
        {
            "name": "FEED_STAGE",
            "value": 30,
            "unit": "1",
            "status": "USER_PROVIDED",
        },
    ]
    column["design_specs"] = [
        {
            "name": "REFLUX_RATIO",
            "value": 2.0,
            "unit": "1",
            "status": "USER_PROVIDED",
        },
        {
            "name": "DISTILLATE_RATE",
            "value": 40.0,
            "unit": "kmol/h",
            "status": "USER_PROVIDED",
        },
    ]
    assert "equipment.column_feed_stage" in blocker_codes(value)


def test_rule_engine_rejects_reactor_without_reaction_definition() -> None:
    value = document()
    reactor = value["equipment"][1]
    reactor["kind"] = "reactor_cstr"
    reactor["parameters"] = [
        {
            "name": "VOLUME",
            "value": 2.0,
            "unit": "m3",
            "status": "USER_PROVIDED",
        }
    ]
    assert "equipment.reaction_set_missing" in blocker_codes(value)


def test_rule_engine_rejects_reaction_with_unknown_component() -> None:
    value = document()
    value["reactions"] = [
        {
            "id": "RXN_001",
            "kind": "stoichiometric",
            "stoichiometry": {"ETHANOL": -1.0, "METHANOL": 1.0},
            "phase": "liquid",
            "status": "USER_PROVIDED",
            "parameters": [],
        }
    ]
    assert "reaction.unknown_component" in blocker_codes(value)


def test_rule_engine_rejects_unapproved_reaction() -> None:
    value = document()
    value["reactions"] = [
        {
            "id": "RXN_001",
            "kind": "stoichiometric",
            "stoichiometry": {"ETHANOL": -1.0, "WATER": 1.0},
            "phase": "liquid",
            "status": "INFERRED_PENDING_APPROVAL",
            "parameters": [],
        }
    ]
    assert "reaction.unapproved" in blocker_codes(value)


def test_rule_engine_rejects_directed_cycle_without_recycle_contract() -> None:
    value = document()
    value["streams"].append(
        {
            "id": "S005",
            "display_name": "Unapproved return",
            "kind": "material",
            "source": {"equipment_id": "SEP_001", "port_id": "LIQ"},
            "target": {"equipment_id": "HTR_001", "port_id": "IN"},
            "components": ["ETHANOL", "WATER"],
            "parameters": [],
        }
    )
    assert "topology.recycle_contract_missing" in blocker_codes(value)


def test_rule_engine_rejects_unowned_tear_stream() -> None:
    value = document()
    value["streams"].append(
        {
            "id": "TEAR_001",
            "display_name": "Unowned tear",
            "kind": "tear",
            "source": {"equipment_id": "SEP_001", "port_id": "LIQ"},
            "target": {"equipment_id": "HTR_001", "port_id": "IN"},
            "components": ["ETHANOL", "WATER"],
            "parameters": [],
        }
    )
    assert "recycle.tear_unowned" in blocker_codes(value)


def test_rule_engine_rejects_self_connection() -> None:
    value = document()
    value["streams"][1]["target"] = {
        "equipment_id": "HTR_001",
        "port_id": "IN",
    }
    assert "stream.self_connection" in blocker_codes(value)


def test_rule_engine_rejects_required_unconnected_port() -> None:
    value = document()
    value["streams"] = [stream for stream in value["streams"] if stream["id"] != "S004"]
    assert "port.required_unconnected" in blocker_codes(value)
