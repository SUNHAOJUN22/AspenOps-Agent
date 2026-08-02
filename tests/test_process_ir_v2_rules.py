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


def test_process_design_rejects_unsafe_display_name() -> None:
    value = document()
    value["equipment"][0]["display_name"] = "feed\u202eexe"
    with pytest.raises(ValueError, match="bidirectional"):
        ProcessDesignIR.from_dict(value)


def test_rule_engine_rejects_port_direction_mismatch() -> None:
    value = document()
    value["streams"][0]["source"] = {
        "equipment_id": "HTR_001",
        "port_id": "IN",
    }
    report = validate_process_design(ProcessDesignIR.from_dict(value))
    assert report.valid is False
    assert any(issue.code == "stream.source_direction" for issue in report.blockers)


def test_rule_engine_rejects_energy_stream_on_material_ports() -> None:
    value = document()
    value["streams"][1]["kind"] = "energy"
    value["streams"][1]["components"] = []
    report = validate_process_design(ProcessDesignIR.from_dict(value))
    assert report.valid is False
    assert any(issue.code == "stream.source_domain" for issue in report.blockers)
    assert any(issue.code == "stream.target_domain" for issue in report.blockers)


def test_rule_engine_rejects_pending_equipment_parameter() -> None:
    value = document()
    value["equipment"][1]["parameters"][0]["status"] = "INFERRED_PENDING_APPROVAL"
    report = validate_process_design(ProcessDesignIR.from_dict(value))
    assert report.valid is False
    codes = {issue.code for issue in report.blockers}
    assert "equipment.specification_missing" in codes
    assert "equipment.parameter_unapproved" in codes


def test_rule_engine_rejects_unqualified_property_method_version() -> None:
    value = document()
    value["property_method"]["supported_versions"] = ["14"]
    report = validate_process_design(ProcessDesignIR.from_dict(value))
    assert report.valid is False
    assert any(
        issue.code == "property_method.version_unqualified" for issue in report.blockers
    )


def test_rule_engine_rejects_column_with_open_degrees_of_freedom() -> None:
    value = document()
    column = value["equipment"][2]
    column["kind"] = "distillation_column"
    column["ports"] = [
        {
            "id": "FEED",
            "direction": "in",
            "domain": "material",
            "required": true,
            "multiple": false
        }
    ]
