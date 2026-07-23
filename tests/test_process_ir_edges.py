from __future__ import annotations

import pytest

from aspenops_nexus import process_ir
from aspenops_nexus import simulation_agents
from aspenops_nexus.process_ir import (
    ComponentSpec,
    Endpoint,
    ParameterSpec,
    PortSpec,
    ProcessIntent,
    StreamSpec,
    UnitOperationSpec,
    ValidationIssue,
    validate_process_intent,
)
from aspenops_nexus.simulation_agents import (
    AgentStageSpec,
    BackendCapability,
    FlowsheetBenchmarkRecord,
    ProcessIRCompiler,
    require_ir_compiler,
    summarize_benchmarks,
)


def valid_document() -> dict:
    return {
        "schema": "aspenops.flowsheet/v1",
        "name": "Methanol heating",
        "property_package": "NRTL",
        "components": [
            {"id": "METHANOL", "name": "Methanol"},
            {"id": "WATER", "name": "Water"},
        ],
        "units": [
            {
                "id": "FEED",
                "kind": "feed",
                "ports": [{"id": "out", "direction": "out"}],
            },
            {
                "id": "HEATER",
                "kind": "heater",
                "ports": [
                    {"id": "in", "direction": "in"},
                    {"id": "out", "direction": "out"},
                ],
                "parameters": [
                    {"name": "outlet_temperature", "value": 80.0, "unit": "C"}
                ],
            },
            {
                "id": "PRODUCT",
                "kind": "product",
                "ports": [{"id": "in", "direction": "in"}],
            },
        ],
        "streams": [
            {
                "id": "S1",
                "source": {"unit": "FEED", "port": "out"},
                "target": {"unit": "HEATER", "port": "in"},
                "components": ["METHANOL", "WATER"],
            },
            {
                "id": "S2",
                "source": {"unit": "HEATER", "port": "out"},
                "target": {"unit": "PRODUCT", "port": "in"},
                "components": ["METHANOL", "WATER"],
            },
        ],
        "metadata": {"source": "test"},
    }


def test_root_scalar_array_text_identifier_and_boolean_errors() -> None:
    with pytest.raises(ValueError, match="JSON object"):
        ProcessIntent.from_dict([])  # type: ignore[arg-type]

    document = valid_document()
    document["components"] = {}
    with pytest.raises(ValueError, match="JSON array"):
        ProcessIntent.from_dict(document)

    document = valid_document()
    document["name"] = 1
    with pytest.raises(ValueError, match="must be a string"):
        ProcessIntent.from_dict(document)

    document = valid_document()
    document["name"] = "   "
    with pytest.raises(ValueError, match="non-empty string"):
        ProcessIntent.from_dict(document)

    document = valid_document()
    document["components"][0]["id"] = "bad/id"
    with pytest.raises(ValueError, match="must match"):
        ProcessIntent.from_dict(document)

    document = valid_document()
    document["units"][0]["ports"][0]["required"] = "yes"
    with pytest.raises(ValueError, match="must be a boolean"):
        ProcessIntent.from_dict(document)


def test_scalar_and_metadata_contract_edges(monkeypatch: pytest.MonkeyPatch) -> None:
    assert ParameterSpec.from_dict({"name": "flag", "value": True}).to_dict() == {
        "name": "flag",
        "value": True,
    }
    assert ParameterSpec.from_dict({"name": "mode", "value": "steady"}).value == "steady"
    assert ParameterSpec.from_dict({"name": "count", "value": 3}).value == 3

    document = valid_document()
    document["metadata"] = {"nested": [1, 2.0, True, None, {"value": "ok"}]}
    assert ProcessIntent.from_dict(document).metadata["nested"][4]["value"] == "ok"

    document = valid_document()
    document["metadata"] = {"bad": float("inf")}
    with pytest.raises(ValueError, match="non-finite"):
        ProcessIntent.from_dict(document)

    document = valid_document()
    value: object = "leaf"
    for _ in range(process_ir.MAX_JSON_DEPTH + 2):
        value = {"nested": value}
    document["metadata"] = value
    with pytest.raises(ValueError, match="nesting depth"):
        ProcessIntent.from_dict(document)

    document = valid_document()
    document["metadata"] = {"bad": {1, 2}}
    with pytest.raises(ValueError, match="non-JSON"):
        ProcessIntent.from_dict(document)

    monkeypatch.setattr(process_ir, "MAX_METADATA_BYTES", 5)
    document = valid_document()
    document["metadata"] = {"long": "value"}
    with pytest.raises(ValueError, match="exceeds"):
        ProcessIntent.from_dict(document)


def test_required_fields_and_direction_errors() -> None:
    with pytest.raises(ValueError, match="requires name and value"):
        ParameterSpec.from_dict({"name": "x"})
    with pytest.raises(ValueError, match="requires id"):
        ComponentSpec.from_dict({})
    with pytest.raises(ValueError, match="requires id and direction"):
        PortSpec.from_dict({"id": "in"})
    with pytest.raises(ValueError, match="must be 'in' or 'out'"):
        PortSpec.from_dict({"id": "in", "direction": "side"})
    with pytest.raises(ValueError, match="requires unit and port"):
        Endpoint.from_dict({"unit": "A"}, label="endpoint")
    with pytest.raises(ValueError, match="requires id and kind"):
        UnitOperationSpec.from_dict({"id": "A"})
    with pytest.raises(ValueError, match="requires id, source and target"):
        StreamSpec.from_dict({"id": "S"})
    with pytest.raises(ValueError, match="requires name"):
        ProcessIntent.from_dict({})
    with pytest.raises(ValueError, match="Unsupported process intent schema"):
        ProcessIntent.from_dict({"schema": "other/v1", "name": "x"})


def test_empty_process_and_missing_property_package_report() -> None:
    intent = ProcessIntent.from_dict({"name": "Empty"})
    report = validate_process_intent(intent)
    assert report.valid is False
    assert {issue.code for issue in report.issues} == {
        "components.empty",
        "property_package.missing",
        "units.empty",
    }
    payload = report.to_dict()
    assert payload["valid"] is False
    assert payload["issues"][0]["severity"] in {"error", "warning"}


def test_resource_limits_ports_and_duplicate_components(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(process_ir, "MAX_COMPONENTS", 1)
    monkeypatch.setattr(process_ir, "MAX_UNITS", 2)
    monkeypatch.setattr(process_ir, "MAX_STREAMS", 1)
    monkeypatch.setattr(process_ir, "MAX_PORTS_PER_UNIT", 1)
    monkeypatch.setattr(process_ir, "MAX_PARAMETERS_PER_ENTITY", 0)
    document = valid_document()
    document["units"][0]["ports"].append(
        {"id": "extra", "direction": "out", "required": False}
    )
    document["units"][1]["ports"].append(
        {"id": "in", "direction": "in", "required": False}
    )
    document["streams"][0]["parameters"] = [{"name": "flow", "value": 1}]
    document["streams"][0]["components"].append("WATER")
    report = validate_process_intent(ProcessIntent.from_dict(document))
    codes = {issue.code for issue in report.issues}
    assert {
        "resource.components_limit",
        "resource.units_limit",
        "resource.streams_limit",
        "resource.port_limit",
        "resource.parameter_limit",
        "port.duplicate_id",
        "stream.duplicate_component",
    }.issubset(codes)


def test_unit_without_ports_is_invalid() -> None:
    document = valid_document()
    document["units"][1]["ports"] = []
    report = validate_process_intent(ProcessIntent.from_dict(document))
    assert "unit.ports_empty" in {issue.code for issue in report.issues}


def test_cycle_search_handles_previously_visited_nonactive_nodes() -> None:
    document = {
        "schema": "aspenops.flowsheet/v1",
        "name": "Diamond",
        "property_package": "IDEAL",
        "components": [{"id": "A"}],
        "units": [
            {
                "id": "A",
                "kind": "splitter",
                "ports": [
                    {"id": "b", "direction": "out"},
                    {"id": "c", "direction": "out"},
                ],
            },
            {
                "id": "B",
                "kind": "heater",
                "ports": [
                    {"id": "in", "direction": "in"},
                    {"id": "out", "direction": "out"},
                ],
            },
            {
                "id": "C",
                "kind": "mixer",
                "ports": [
                    {"id": "a", "direction": "in"},
                    {"id": "b", "direction": "in"},
                ],
            },
        ],
        "streams": [
            {
                "id": "AB",
                "source": {"unit": "A", "port": "b"},
                "target": {"unit": "B", "port": "in"},
            },
            {
                "id": "BC",
                "source": {"unit": "B", "port": "out"},
                "target": {"unit": "C", "port": "b"},
            },
            {
                "id": "AC",
                "source": {"unit": "A", "port": "c"},
                "target": {"unit": "C", "port": "a"},
            },
        ],
    }
    report = validate_process_intent(ProcessIntent.from_dict(document))
    assert "topology.recycle_cycle" not in {issue.code for issue in report.issues}


def test_simulation_agent_helper_and_protocol_edges(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(ValueError, match="JSON object"):
        FlowsheetBenchmarkRecord.from_dict([])  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="unsupported fields"):
        FlowsheetBenchmarkRecord.from_dict(
            {
                "scenario_id": "X",
                "backend": "mock",
                "topology_valid": True,
                "compiler_available": True,
                "execution_attempted": False,
                "extra": 1,
            }
        )
    with pytest.raises(ValueError, match="is missing"):
        FlowsheetBenchmarkRecord.from_dict({})
    with pytest.raises(ValueError, match="stable identifier"):
        FlowsheetBenchmarkRecord.from_dict(
            {
                "scenario_id": "bad/id",
                "backend": "mock",
                "topology_valid": True,
                "compiler_available": True,
                "execution_attempted": False,
            }
        )
    with pytest.raises(ValueError, match="must be a boolean"):
        FlowsheetBenchmarkRecord.from_dict(
            {
                "scenario_id": "X",
                "backend": "mock",
                "topology_valid": "yes",
                "compiler_available": True,
                "execution_attempted": False,
            }
        )
    with pytest.raises(ValueError, match="non-negative integer"):
        FlowsheetBenchmarkRecord.from_dict(
            {
                "scenario_id": "X",
                "backend": "mock",
                "topology_valid": True,
                "compiler_available": True,
                "execution_attempted": False,
                "repair_iterations": -1,
            }
        )

    available = BackendCapability(
        "test",
        "available",
        "available",
        True,
        False,
        False,
        False,
        ("linux",),
        "test",
    )
    monkeypatch.setattr(simulation_agents, "backend_capabilities", lambda: (available,))
    assert require_ir_compiler("test") is None

    stage = AgentStageSpec("test", "test responsibility", "test output")
    assert stage.to_dict()["id"] == "test"

    class Compiler:
        backend = "test"

        def compile(self, intent: ProcessIntent) -> dict:
            return intent.canonical_dict()

    assert isinstance(Compiler(), ProcessIRCompiler)


def test_benchmark_serialization_and_empty_summary() -> None:
    record = FlowsheetBenchmarkRecord.from_dict(
        {
            "scenario_id": "CASE",
            "backend": "mock",
            "topology_valid": True,
            "compiler_available": False,
            "execution_attempted": False,
            "note": "not run",
        }
    )
    assert record.to_dict()["converged"] is None
    summary = summarize_benchmarks((record,))
    assert summary["convergence_rate_percent"] is None
    assert summary["balance_rate_percent"] is None


def test_validation_issue_ordering_and_serialization() -> None:
    issue = ValidationIssue("warning", "x", "path", "message")
    assert issue.to_dict() == {
        "severity": "warning",
        "code": "x",
        "path": "path",
        "message": "message",
    }
