from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from aspenops_nexus.process_ir import ProcessIntent, validate_process_intent
from aspenops_nexus.simulation_agents import (
    BackendUnavailableError,
    FlowsheetBenchmarkRecord,
    agent_pipeline,
    backend_capabilities,
    capability_matrix,
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


def issue_codes(report) -> set[str]:
    return {issue.code for issue in report.issues}


def test_valid_process_intent_is_deterministic() -> None:
    first = ProcessIntent.from_dict(valid_document())
    altered = valid_document()
    altered["components"].reverse()
    altered["units"].reverse()
    altered["streams"].reverse()
    second = ProcessIntent.from_dict(altered)

    first_report = validate_process_intent(first)
    second_report = validate_process_intent(second)

    assert first_report.valid is True
    assert second_report.valid is True
    assert first.digest() == second.digest()
    assert first.canonical_json() == second.canonical_json()
    assert first_report.counts == {
        "components": 2,
        "units": 3,
        "streams": 2,
        "ports": 4,
        "parameters": 1,
    }


def test_unknown_fields_and_forbidden_metadata_fail_closed() -> None:
    unknown = valid_document()
    unknown["arbitrary_code"] = "print('unsafe')"
    with pytest.raises(ValueError, match="unsupported fields"):
        ProcessIntent.from_dict(unknown)

    forbidden = valid_document()
    forbidden["metadata"] = {"script": "print('unsafe')"}
    with pytest.raises(ValueError, match="forbidden"):
        ProcessIntent.from_dict(forbidden)


def test_nonfinite_and_forbidden_parameter_values_are_rejected() -> None:
    nonfinite = valid_document()
    nonfinite["units"][1]["parameters"][0]["value"] = float("nan")
    with pytest.raises(ValueError, match="finite scalar"):
        ProcessIntent.from_dict(nonfinite)

    forbidden = valid_document()
    forbidden["units"][1]["parameters"][0]["name"] = "tree_path"
    with pytest.raises(ValueError, match="forbidden"):
        ProcessIntent.from_dict(forbidden)


def test_duplicate_ids_and_parameter_names_are_reported() -> None:
    document = valid_document()
    document["components"].append({"id": "WATER"})
    document["units"][1]["parameters"].append(
        {"name": "outlet_temperature", "value": 90.0, "unit": "C"}
    )
    report = validate_process_intent(ProcessIntent.from_dict(document))

    assert report.valid is False
    assert "components.duplicate_id" in issue_codes(report)
    assert "parameter.duplicate_name" in issue_codes(report)


def test_unknown_units_ports_and_components_are_reported() -> None:
    document = valid_document()
    document["streams"][0]["source"]["unit"] = "MISSING"
    document["streams"][1]["target"]["port"] = "missing"
    document["streams"][1]["components"].append("UNKNOWN")
    report = validate_process_intent(ProcessIntent.from_dict(document))

    assert report.valid is False
    assert {
        "stream.unknown_unit",
        "stream.unknown_port",
        "stream.unknown_component",
    }.issubset(issue_codes(report))


def test_port_direction_and_required_connectivity_are_enforced() -> None:
    document = valid_document()
    document["streams"][0]["source"] = {"unit": "HEATER", "port": "in"}
    report = validate_process_intent(ProcessIntent.from_dict(document))

    assert report.valid is False
    assert "stream.port_direction" in issue_codes(report)
    assert "port.required_unconnected" in issue_codes(report)


def test_self_connection_duplicate_connection_and_fanout_are_rejected() -> None:
    document = valid_document()
    document["units"][1]["ports"].append(
        {"id": "in2", "direction": "in", "required": False}
    )
    document["streams"].append(
        {
            "id": "S3",
            "source": {"unit": "HEATER", "port": "out"},
            "target": {"unit": "HEATER", "port": "in2"},
            "components": ["WATER"],
        }
    )
    document["streams"].append(deepcopy(document["streams"][1]))
    document["streams"][-1]["id"] = "S4"
    report = validate_process_intent(ProcessIntent.from_dict(document))

    assert report.valid is False
    assert "stream.self_connection" in issue_codes(report)
    assert "stream.duplicate_connection" in issue_codes(report)
    assert "port.multiple_connections" in issue_codes(report)


def recycle_document() -> dict:
    return {
        "schema": "aspenops.flowsheet/v1",
        "name": "Explicit recycle",
        "property_package": "IDEAL",
        "components": [{"id": "A"}],
        "units": [
            {
                "id": "FEED",
                "kind": "feed",
                "ports": [{"id": "out", "direction": "out"}],
            },
            {
                "id": "MIX",
                "kind": "mixer",
                "ports": [
                    {"id": "feed", "direction": "in"},
                    {"id": "recycle", "direction": "in"},
                    {"id": "out", "direction": "out"},
                ],
            },
            {
                "id": "HEAT",
                "kind": "heater",
                "ports": [
                    {"id": "in", "direction": "in"},
                    {"id": "out", "direction": "out"},
                ],
            },
            {
                "id": "SPLIT",
                "kind": "splitter",
                "ports": [
                    {"id": "in", "direction": "in"},
                    {"id": "product", "direction": "out"},
                    {"id": "recycle", "direction": "out"},
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
                "id": "F",
                "source": {"unit": "FEED", "port": "out"},
                "target": {"unit": "MIX", "port": "feed"},
            },
            {
                "id": "M",
                "source": {"unit": "MIX", "port": "out"},
                "target": {"unit": "HEAT", "port": "in"},
            },
            {
                "id": "H",
                "source": {"unit": "HEAT", "port": "out"},
                "target": {"unit": "SPLIT", "port": "in"},
            },
            {
                "id": "P",
                "source": {"unit": "SPLIT", "port": "product"},
                "target": {"unit": "PRODUCT", "port": "in"},
            },
            {
                "id": "R",
                "source": {"unit": "SPLIT", "port": "recycle"},
                "target": {"unit": "MIX", "port": "recycle"},
            },
        ],
    }


def test_recycle_cycles_are_warning_or_error_by_policy() -> None:
    intent = ProcessIntent.from_dict(recycle_document())
    permissive = validate_process_intent(intent, allow_recycles=True)
    strict = validate_process_intent(intent, allow_recycles=False)

    assert permissive.valid is True
    assert any(
        issue.code == "topology.recycle_cycle" and issue.severity == "warning"
        for issue in permissive.issues
    )
    assert strict.valid is False
    assert any(
        issue.code == "topology.recycle_cycle" and issue.severity == "error"
        for issue in strict.issues
    )


def test_noncanonical_unit_kind_is_warning_not_invention() -> None:
    document = valid_document()
    document["units"][1]["kind"] = "membrane_superunit"
    report = validate_process_intent(ProcessIntent.from_dict(document))

    assert report.valid is True
    assert "unit.noncanonical_kind" in issue_codes(report)


def test_backend_capabilities_are_explicit_and_fail_closed() -> None:
    capabilities = {item.backend: item for item in backend_capabilities()}

    assert set(capabilities) == {
        "mock",
        "aspen_plus",
        "hysys",
        "dwsim",
        "idaes",
        "modelica",
    }
    assert capabilities["aspen_plus"].execution == "available"
    assert capabilities["aspen_plus"].ir_compiler == "planned"
    assert capabilities["dwsim"].execution == "planned"
    assert len(capability_matrix()) == 6

    with pytest.raises(BackendUnavailableError, match="will not pretend"):
        require_ir_compiler("dwsim")
    with pytest.raises(BackendUnavailableError, match="Unknown simulator backend"):
        require_ir_compiler("unknown")


def test_agent_pipeline_preserves_separation_of_concerns() -> None:
    stages = agent_pipeline()
    assert [item.id for item in stages] == [
        "knowledge",
        "concept",
        "parameter",
        "execution",
        "repair",
        "review",
    ]
    assert stages[1].permitted_output == "aspenops.flowsheet/v1"
    assert all("shell" not in item.permitted_output.casefold() for item in stages)


def test_benchmark_records_preserve_execution_boundaries() -> None:
    records = (
        FlowsheetBenchmarkRecord.from_dict(
            {
                "scenario_id": "CASE1",
                "backend": "mock",
                "topology_valid": True,
                "compiler_available": True,
                "execution_attempted": True,
                "converged": True,
                "material_balance_ok": True,
                "energy_balance_ok": True,
                "repair_iterations": 1,
            }
        ),
        FlowsheetBenchmarkRecord.from_dict(
            {
                "scenario_id": "CASE2",
                "backend": "dwsim",
                "topology_valid": True,
                "compiler_available": False,
                "execution_attempted": False,
                "repair_iterations": 0,
                "human_intervention": True,
            }
        ),
    )
    summary = summarize_benchmarks(records)

    assert summary["scenarios"] == 2
    assert summary["execution_attempted"] == 1
    assert summary["convergence_rate_percent"] == 100.0
    assert summary["balance_rate_percent"] == 100.0
    assert summary["repair_iterations"] == 1
    assert summary["human_interventions"] == 1

    with pytest.raises(ValueError, match="non-attempted execution"):
        FlowsheetBenchmarkRecord.from_dict(
            {
                "scenario_id": "BAD",
                "backend": "idaes",
                "topology_valid": True,
                "compiler_available": False,
                "execution_attempted": False,
                "converged": True,
            }
        )


def test_example_document_is_valid() -> None:
    path = Path("examples/process-intent.example.json")
    document = json.loads(path.read_text(encoding="utf-8"))
    report = validate_process_intent(ProcessIntent.from_dict(document))
    assert report.valid is True
