from __future__ import annotations

import json
from collections.abc import Callable
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

import aspenops_nexus.process_ir_v2 as ir
import aspenops_nexus.process_requirement as req

ROOT = Path(__file__).resolve().parents[1]
REQUIREMENT = ROOT / "examples/process-requirement-v1.example.json"
DESIGN = ROOT / "examples/process-design-v2.example.json"


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_requirement_helper_success_paths() -> None:
    assert req._object({1: "x"}, "value") == {"1": "x"}
    req._reject_unknown({"a": 1}, {"a"}, "value")
    assert req._array([1], "value", maximum=1) == [1]
    assert req._text(" e\u0301 ", "value") == "é"
    assert req._text("", "value", allow_empty=True) == ""
    assert req._identifier("FEED_001", "value") == "FEED_001"
    assert req._status("USER_PROVIDED", "value") == "USER_PROVIDED"
    assert req._finite(2, "value") == 2.0
    assert req._safe_scalar(" note ", "value") == "note"
    assert req._safe_scalar(True, "value") is True
    assert req._safe_scalar(3, "value") == 3
    assert req._safe_scalar(3.5, "value") == 3.5
    assert req._optional_text(None, "value") is None
    assert req._optional_text(" x ", "value") == "x"
    assert len(req._canonical_hash({"x": 1})) == 64


@pytest.mark.parametrize(
    "call",
    [
        lambda: req._object([], "value"),
        lambda: req._reject_unknown({"bad": 1}, set(), "value"),
        lambda: req._array({}, "value", maximum=1),
        lambda: req._array([1, 2], "value", maximum=1),
        lambda: req._text(1, "value"),
        lambda: req._text("", "value"),
        lambda: req._text("x" * (req.MAX_TEXT_LENGTH + 1), "value"),
        lambda: req._text("x\x00", "value"),
        lambda: req._text("x\u202e", "value"),
        lambda: req._text("x\x01", "value"),
        lambda: req._identifier("bad", "value"),
        lambda: req._status("BAD", "value"),
        lambda: req._finite(True, "value"),
        lambda: req._finite("1", "value"),
        lambda: req._finite(float("inf"), "value"),
        lambda: req._safe_scalar([], "value"),
    ],
)
def test_requirement_helper_failure_paths(call: Callable[[], Any]) -> None:
    with pytest.raises(ValueError):
        call()


def test_qualified_scalar_contract_branches() -> None:
    approved = req.QualifiedScalar.from_dict(
        {"value": 1.0, "status": "USER_PROVIDED", "unit": "bar", "uncertainty": 0.1},
        label="value",
    )
    assert approved.approved is True
    assert approved.to_dict()["uncertainty"] == 0.1
    pending = req.QualifiedScalar.from_dict(
        {"value": None, "status": "UNKNOWN"},
        label="value",
    )
    assert pending.approved is False
    with pytest.raises(ValueError, match="unsupported fields"):
        req.QualifiedScalar.from_dict(
            {"value": 1, "status": "USER_PROVIDED", "bad": 1},
            label="value",
        )
    with pytest.raises(ValueError, match="non-negative"):
        req.QualifiedScalar.from_dict(
            {"value": 1, "status": "USER_PROVIDED", "uncertainty": -1},
            label="value",
        )
    with pytest.raises(ValueError, match="without a value"):
        req.QualifiedScalar.from_dict(
            {"value": None, "status": "APPROVED_DEFAULT"},
            label="value",
        )


def test_composition_entry_contract_branches() -> None:
    entry = req.CompositionEntry.from_dict(
        {
            "component_id": "WATER",
            "fraction": 1.0,
            "basis": "mass",
            "status": "APPROVED_DEFAULT",
        },
        label="composition",
    )
    assert entry.approved is True
    assert entry.to_dict()["basis"] == "mass"
    pending = req.CompositionEntry.from_dict(
        {
            "component_id": "WATER",
            "fraction": 1.0,
            "basis": "mole",
            "status": "UNKNOWN",
        },
        label="composition",
    )
    assert pending.approved is False
    for payload in (
        {"component_id": "WATER", "fraction": 1.0, "basis": "bad", "status": "UNKNOWN"},
        {"component_id": "WATER", "fraction": 2.0, "basis": "mole", "status": "UNKNOWN"},
        {
            "component_id": "WATER",
            "fraction": 1.0,
            "basis": "mole",
            "status": "UNKNOWN",
            "extra": True,
        },
    ):
        with pytest.raises(ValueError):
            req.CompositionEntry.from_dict(payload, label="composition")


def test_feed_and_product_requirement_edge_branches() -> None:
    base = load(REQUIREMENT)
    feed = deepcopy(base["feeds"][0])
    feed["bad"] = 1
    with pytest.raises(ValueError, match="unsupported fields"):
        req.FeedRequirement.from_dict(feed, label="feed")

    duplicate_components = deepcopy(base["feeds"][0])
    duplicate_components["components"].append("WATER")
    with pytest.raises(ValueError, match="unique IDs"):
        req.FeedRequirement.from_dict(duplicate_components, label="feed")

    duplicate_composition = deepcopy(base["feeds"][0])
    duplicate_composition["composition"].append(deepcopy(duplicate_composition["composition"][0]))
    with pytest.raises(ValueError, match="repeats"):
        req.FeedRequirement.from_dict(duplicate_composition, label="feed")

    mixed_basis = deepcopy(base["feeds"][0])
    mixed_basis["composition"][1]["basis"] = "mass"
    with pytest.raises(ValueError, match="cannot mix"):
        req.FeedRequirement.from_dict(mixed_basis, label="feed")

    bad_phase = deepcopy(base["feeds"][0])
    bad_phase["phase"] = "plasma"
    with pytest.raises(ValueError, match="unsupported"):
        req.FeedRequirement.from_dict(bad_phase, label="feed")

    product = deepcopy(base["products"][0])
    product["bad"] = 1
    with pytest.raises(ValueError, match="unsupported fields"):
        req.ProductRequirement.from_dict(product, label="product")
    product = deepcopy(base["products"][0])
    product["specifications"] = []
    with pytest.raises(ValueError, match="JSON object"):
        req.ProductRequirement.from_dict(product, label="product")


def test_requirement_document_shape_and_readiness_branches() -> None:
    base = load(REQUIREMENT)
    invalid_documents = []
    value = deepcopy(base)
    value["bad"] = 1
    invalid_documents.append(value)
    value = deepcopy(base)
    value["schema"] = "other/v1"
    invalid_documents.append(value)
    value = deepcopy(base)
    value["project"] = []
    invalid_documents.append(value)
    value = deepcopy(base)
    value["project"]["target_simulator"] = "raw_com"
    invalid_documents.append(value)
    value = deepcopy(base)
    value["project"]["target_version"] = "13"
    invalid_documents.append(value)
    value = deepcopy(base)
    value["process_objective"] = []
    invalid_documents.append(value)
    value = deepcopy(base)
    value["feeds"] = {}
    invalid_documents.append(value)
    value = deepcopy(base)
    value["products"] = {}
    invalid_documents.append(value)
    value = deepcopy(base)
    value["feeds"].append(deepcopy(value["feeds"][0]))
    invalid_documents.append(value)
    value = deepcopy(base)
    value["products"].append(deepcopy(value["products"][0]))
    invalid_documents.append(value)
    value = deepcopy(base)
    value["required_sections"].append(value["required_sections"][0])
    invalid_documents.append(value)
    value = deepcopy(base)
    value["assumptions"] = []
    invalid_documents.append(value)
    value = deepcopy(base)
    value["metadata"] = []
    invalid_documents.append(value)
    for document in invalid_documents:
        with pytest.raises(ValueError):
            req.ProcessRequirementDocument.from_dict(document)

    empty = deepcopy(base)
    empty["feeds"] = []
    empty["products"] = []
    empty["property_method"] = {"value": None, "status": "UNKNOWN"}
    readiness = req.ProcessRequirementDocument.from_dict(empty).readiness()
    assert readiness.status == "NEEDS_ENGINEERING_INPUT"
    assert "At least one feed is required" in readiness.blockers
    assert "At least one product is required" in readiness.blockers

    incomplete = deepcopy(base)
    incomplete["feeds"][0]["components"] = []
    incomplete["feeds"][0]["composition"] = []
    incomplete["feeds"][0]["total_flow"] = {"value": None, "status": "UNKNOWN"}
    incomplete["products"][0]["specifications"] = {}
    incomplete["products"][1]["specifications"]["WATER_MOLE_FRACTION_MIN"]["status"] = "UNKNOWN"
    readiness = req.ProcessRequirementDocument.from_dict(incomplete).readiness()
    assert readiness.status == "NEEDS_ENGINEERING_INPUT"
    assert any("no declared components" in item for item in readiness.blockers)
    assert any("no required specification" in item for item in readiness.blockers)


def test_ir_helper_success_and_failure_paths() -> None:
    assert ir._object({1: "x"}, "value") == {"1": "x"}
    assert ir._bounded_object({"x": 1}, "value", maximum=1) == {"x": 1}
    assert ir._array([1], "value", maximum=1) == [1]
    assert ir._text(" e\u0301 ", "value") == "é"
    assert ir._text("", "value", allow_empty=True) == ""
    assert ir._identifier("UNIT_001", "value") == "UNIT_001"
    assert ir._status("UNKNOWN", "value") == "UNKNOWN"
    assert ir._optional_text(None, "value") is None
    assert ir._optional_text(" x ", "value") == "x"
    assert ir._finite(2, "value") == 2.0
    assert ir._positive(2, "value") == 2.0
    assert ir._scalar(" x ", "value") == "x"
    assert ir._scalar(False, "value") is False
    assert ir._scalar(1, "value") == 1
    assert ir._scalar(1.5, "value") == 1.5
    assert len(ir._canonical_hash({"x": 1})) == 64

    failures = (
        lambda: ir._object([], "value"),
        lambda: ir._bounded_object({"a": 1, "b": 2}, "value", maximum=1),
        lambda: ir._array({}, "value", maximum=1),
        lambda: ir._array([1, 2], "value", maximum=1),
        lambda: ir._text(1, "value"),
        lambda: ir._text("", "value"),
        lambda: ir._text("x" * (ir.MAX_TEXT_LENGTH + 1), "value"),
        lambda: ir._text("x\x00", "value"),
        lambda: ir._text("x\u202e", "value"),
        lambda: ir._text("x\x01", "value"),
        lambda: ir._identifier("bad", "value"),
        lambda: ir._status("BAD", "value"),
        lambda: ir._finite(True, "value"),
        lambda: ir._finite(float("nan"), "value"),
        lambda: ir._positive(0, "value"),
        lambda: ir._scalar([], "value"),
    )
    for call in failures:
        with pytest.raises(ValueError):
            call()


def test_ir_component_property_port_parameter_edge_branches() -> None:
    component = ir.ComponentDefinition.from_dict(
        {
            "id": "WATER",
            "display_name": "Water",
            "vendor_ids": {"aspen_plus": "WATER"},
            "cas": "7732-18-5",
            "formula": "H2O",
            "molecular_weight": 18.0,
            "pseudo_component": False,
            "electrolyte": False,
            "polymer": False,
            "solid": False,
            "status": "USER_PROVIDED",
        },
        label="component",
    )
    assert component.to_dict()["cas"] == "7732-18-5"
    for payload in (
        {"id": "WATER", "display_name": "Water", "vendor_ids": {}, "bad": 1},
        {"id": "WATER", "display_name": "Water", "vendor_ids": {}, "cas": "bad"},
        {"id": "WATER", "display_name": "Water", "vendor_ids": {}, "molecular_weight": 0},
        {"id": "WATER", "display_name": "Water", "vendor_ids": {}, "solid": "no"},
    ):
        with pytest.raises(ValueError):
            ir.ComponentDefinition.from_dict(payload, label="component")

    method = ir.PropertyMethodDefinition.from_dict(
        {
            "id": "NRTL",
            "vendor": "aspen_plus",
            "supported_versions": ["15"],
            "phase_scope": ["vapor-liquid"],
            "rationale": "approved",
            "status": "APPROVED_DEFAULT",
        },
        label="method",
    )
    assert method.approved is True
    assert method.to_dict()["vendor"] == "aspen_plus"
    duplicate_method = method.to_dict()
    duplicate_method["supported_versions"] = ["15", "15"]
    with pytest.raises(ValueError, match="unique"):
        ir.PropertyMethodDefinition.from_dict(duplicate_method, label="method")

    port = ir.PortDefinition.from_dict(
        {"id": "IN", "direction": "in", "domain": "material"},
        label="port",
    )
    assert port.to_dict()["required"] is True
    for payload in (
        {"id": "IN", "direction": "side", "domain": "material"},
        {"id": "IN", "direction": "in", "domain": "unknown"},
        {"id": "IN", "direction": "in", "domain": "material", "required": "yes"},
    ):
        with pytest.raises(ValueError):
            ir.PortDefinition.from_dict(payload, label="port")

    parameter = ir.ParameterDefinition.from_dict(
        {"name": "DUTY", "value": 1.0, "unit": "kW", "status": "USER_PROVIDED"},
        label="parameter",
    )
    assert parameter.approved is True
    assert parameter.to_dict()["unit"] == "kW"
    with pytest.raises(ValueError, match="without a value"):
        ir.ParameterDefinition.from_dict(
            {"name": "DUTY", "value": None, "status": "APPROVED_DEFAULT"},
            label="parameter",
        )


def test_ir_equipment_stream_reaction_recycle_edge_branches() -> None:
    base = load(DESIGN)
    equipment = deepcopy(base["equipment"][1])
    equipment["ports"].append(deepcopy(equipment["ports"][0]))
    with pytest.raises(ValueError, match="unique IDs"):
        ir.EquipmentDefinition.from_dict(equipment, label="equipment")
    equipment = deepcopy(base["equipment"][1])
    equipment["parameters"].append(deepcopy(equipment["parameters"][0]))
    with pytest.raises(ValueError, match="unique IDs"):
        ir.EquipmentDefinition.from_dict(equipment, label="equipment")

    with pytest.raises(ValueError, match="unsupported fields"):
        ir.Endpoint.from_dict(
            {"equipment_id": "HTR_001", "port_id": "OUT", "bad": 1},
            label="endpoint",
        )

    stream = ir.StreamDefinition.from_dict(base["streams"][0], label="stream")
    assert stream.domain == "material"
    assert stream.to_dict()["id"] == "S001"
    energy = deepcopy(base["streams"][0])
    energy["kind"] = "energy"
    energy["components"] = []
    assert ir.StreamDefinition.from_dict(energy, label="stream").domain == "energy"
    information = deepcopy(energy)
    information["kind"] = "information"
    assert ir.StreamDefinition.from_dict(information, label="stream").domain == "information"
    duplicate_components = deepcopy(base["streams"][0])
    duplicate_components["components"].append("WATER")
    with pytest.raises(ValueError, match="unique IDs"):
        ir.StreamDefinition.from_dict(duplicate_components, label="stream")
    bad_kind = deepcopy(base["streams"][0])
    bad_kind["kind"] = "unknown"
    with pytest.raises(ValueError, match="unsupported"):
        ir.StreamDefinition.from_dict(bad_kind, label="stream")

    reaction = ir.ReactionDefinition.from_dict(
        {
            "id": "RXN_001",
            "kind": "stoichiometric",
            "stoichiometry": {"WATER": -1.0, "ETHANOL": 1.0},
            "phase": "liquid",
            "status": "USER_PROVIDED",
            "parameters": [],
        },
        label="reaction",
    )
    assert reaction.to_dict()["kind"] == "stoichiometric"
    with pytest.raises(ValueError, match="required"):
        ir.ReactionDefinition.from_dict(
            {
                "id": "RXN_001",
                "kind": "kinetic",
                "stoichiometry": {},
                "phase": "liquid",
                "status": "UNKNOWN",
            },
            label="reaction",
        )

    recycle = ir.RecycleDefinition.from_dict(
        {
            "id": "RECYCLE_001",
            "stream_id": "S004",
            "tear_stream_id": "TEAR_001",
            "convergence_variables": ["FLOW", "TEMPERATURE"],
            "tolerance": 1e-6,
            "max_iterations": 50,
            "acceleration": "wegstein",
            "status": "USER_PROVIDED",
        },
        label="recycle",
    )
    assert recycle.to_dict()["max_iterations"] == 50
    for payload in (
        {
            "id": "RECYCLE_001",
            "stream_id": "S004",
            "tear_stream_id": "TEAR_001",
            "convergence_variables": [],
        },
        {
            "id": "RECYCLE_001",
            "stream_id": "S004",
            "tear_stream_id": "TEAR_001",
            "convergence_variables": ["FLOW", "FLOW"],
        },
        {
            "id": "RECYCLE_001",
            "stream_id": "S004",
            "tear_stream_id": "TEAR_001",
            "convergence_variables": ["FLOW"],
            "max_iterations": True,
        },
        {
            "id": "RECYCLE_001",
            "stream_id": "S004",
            "tear_stream_id": "TEAR_001",
            "convergence_variables": ["FLOW"],
            "max_iterations": 0,
        },
    ):
        with pytest.raises(ValueError):
            ir.RecycleDefinition.from_dict(payload, label="recycle")


def test_process_design_document_edge_branches() -> None:
    base = load(DESIGN)
    design = ir.ProcessDesignIR.from_dict(base)
    assert design.normalized().digest() == design.digest()
    assert design.canonical_dict()["schema"] == ir.DESIGN_SCHEMA

    invalid_documents = []
    value = deepcopy(base)
    value["bad"] = 1
    invalid_documents.append(value)
    value = deepcopy(base)
    value["schema"] = "other/v1"
    invalid_documents.append(value)
    value = deepcopy(base)
    value["requirement_hash"] = "bad"
    invalid_documents.append(value)
    value = deepcopy(base)
    value["target_simulator"] = "raw_com"
    invalid_documents.append(value)
    value = deepcopy(base)
    value["target_version"] = "13"
    invalid_documents.append(value)
    value = deepcopy(base)
    value["components"].append(deepcopy(value["components"][0]))
    invalid_documents.append(value)
    value = deepcopy(base)
    value["equipment"].append(deepcopy(value["equipment"][0]))
    invalid_documents.append(value)
    value = deepcopy(base)
    value["streams"].append(deepcopy(value["streams"][0]))
    invalid_documents.append(value)
    value = deepcopy(base)
    value["metadata"] = []
    invalid_documents.append(value)
    for document in invalid_documents:
        with pytest.raises(ValueError):
            ir.ProcessDesignIR.from_dict(document)
