from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from aspenops_nexus.compilation_plan import (
    CompilationIssue,
    CompilationStep,
    _canonical_hash,
    _equipment_order,
    _StepBuilder,
    compile_process_design,
)
from aspenops_nexus.process_ir_v2 import ProcessDesignIR
from aspenops_nexus.simulator_capabilities import (
    EquipmentCapability,
    get_builtin_capability_profile,
)

ROOT = Path(__file__).resolve().parents[1]
DESIGN = ROOT / "examples/process-design-v2.example.json"


def document() -> dict[str, Any]:
    value = json.loads(DESIGN.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def design() -> ProcessDesignIR:
    return ProcessDesignIR.from_dict(document())


def test_offline_profile_produces_deterministic_plan_only() -> None:
    process_design = design()
    profile = get_builtin_capability_profile("aspen_plus", "15")
    first = compile_process_design(process_design, profile)
    second = compile_process_design(process_design, profile)
    assert first.status == "PLAN_ONLY"
    assert first.executable is False
    assert first.blocked is False
    assert first.digest() == second.digest()
    assert first.to_dict() == second.to_dict()
    assert first.design_hash == process_design.digest()
    assert first.profile_hash == profile.digest()
    assert first.expected_topology.digest() == second.expected_topology.digest()
    assert first.expected_layout_hash == second.expected_layout_hash
    assert any(item.code == "profile.not_runtime_verified" for item in first.issues)
    with pytest.raises(RuntimeError, match="not executable"):
        first.assert_executable()


def test_verified_profile_produces_executable_plan() -> None:
    process_design = design()
    profile = replace(
        get_builtin_capability_profile("aspen_plus", "15"),
        qualification="VERIFIED_ON_TARGET_RUNTIME",
    )
    plan = compile_process_design(process_design, profile)
    assert plan.status == "EXECUTABLE"
    assert plan.executable is True
    assert plan.blocked is False
    plan.assert_executable()
    operations = [item.operation for item in plan.steps]
    assert operations[0:2] == ["assert_profile_identity", "create_case_shell"]
    assert "define_component" in operations
    assert "set_property_method" in operations
    assert "create_equipment" in operations
    assert "create_boundary" in operations
    assert "create_stream" in operations
    assert "connect_stream" in operations
    assert "solve_open_loop" in operations
    assert "readback_topology" in operations
    assert "readback_layout" in operations
    assert operations[-4:] == [
        "close_case",
        "reopen_case",
        "readback_topology_after_reopen",
        "readback_layout_after_reopen",
    ]
    assert [item.step_id for item in plan.steps] == [
        f"S{index:04d}" for index in range(1, len(plan.steps) + 1)
    ]


def test_compilation_order_is_topological_and_stable() -> None:
    process_design = design()
    assert _equipment_order(process_design) == (
        "FEED_001",
        "HTR_001",
        "SEP_001",
        "LIQ_PROD_001",
        "VAP_PROD_001",
    )
    value = document()
    value["equipment"].reverse()
    value["streams"].reverse()
    reordered = ProcessDesignIR.from_dict(value)
    assert _equipment_order(reordered) == _equipment_order(process_design)
    profile = replace(
        get_builtin_capability_profile("aspen_plus", "15"),
        qualification="VERIFIED_ON_TARGET_RUNTIME",
    )
    assert (
        compile_process_design(reordered, profile).digest()
        == compile_process_design(
            process_design,
            profile,
        ).digest()
    )


def test_blocked_design_has_no_steps() -> None:
    value = document()
    value["streams"][0]["target"] = {
        "equipment_id": "MISSING",
        "port_id": "IN",
    }
    plan = compile_process_design(
        ProcessDesignIR.from_dict(value),
        get_builtin_capability_profile("aspen_plus", "15"),
    )
    assert plan.status == "BLOCKED"
    assert plan.blocked is True
    assert plan.steps == ()
    assert any(item.code.startswith("engineering.") for item in plan.issues)


def test_profile_target_mismatch_blocks_plan() -> None:
    plan = compile_process_design(
        design(),
        get_builtin_capability_profile("hysys", "15"),
    )
    assert plan.status == "BLOCKED"
    assert any(item.code == "profile.target_mismatch" for item in plan.issues)


def test_missing_and_unsupported_equipment_capabilities_block_plan() -> None:
    process_design = design()
    profile = get_builtin_capability_profile("aspen_plus", "15")
    without_heater = replace(
        profile,
        equipment=tuple(item for item in profile.equipment if item.ir_kind != "heater"),
    )
    missing = compile_process_design(process_design, without_heater)
    assert missing.status == "BLOCKED"
    assert any(item.code == "capability.equipment_missing" for item in missing.issues)

    unsupported_equipment = tuple(
        replace(item, state="UNSUPPORTED") if item.ir_kind == "heater" else item
        for item in profile.equipment
    )
    unsupported = compile_process_design(
        process_design,
        replace(profile, equipment=unsupported_equipment),
    )
    assert unsupported.status == "BLOCKED"
    assert any(item.code == "capability.equipment_unsupported" for item in unsupported.issues)


def test_parameter_and_port_domain_capability_gaps_block_plan() -> None:
    process_design = design()
    profile = get_builtin_capability_profile("aspen_plus", "15")
    capabilities: list[EquipmentCapability] = []
    for item in profile.equipment:
        if item.ir_kind == "heater":
            capabilities.append(
                replace(
                    item,
                    required_port_domains=("energy",),
                    supported_parameter_names=(),
                )
            )
        else:
            capabilities.append(item)
    plan = compile_process_design(
        process_design,
        replace(profile, equipment=tuple(capabilities)),
    )
    codes = {item.code for item in plan.issues}
    assert "capability.port_domain" in codes
    assert "capability.parameter_missing" in codes
    assert plan.status == "BLOCKED"


def test_unsupported_stream_kind_blocks_plan() -> None:
    profile = get_builtin_capability_profile("aspen_plus", "15")
    plan = compile_process_design(
        design(),
        replace(
            profile,
            supported_stream_kinds=tuple(
                item for item in profile.supported_stream_kinds if item != "product"
            ),
        ),
    )
    assert plan.status == "BLOCKED"
    assert any(item.code == "capability.stream_kind" for item in plan.issues)


def test_unknown_equipment_kind_is_blocked() -> None:
    value = document()
    value["equipment"][1]["kind"] = "unknown_unit"
    process_design = ProcessDesignIR.from_dict(value)
    plan = compile_process_design(
        process_design,
        get_builtin_capability_profile("aspen_plus", "15"),
    )
    assert plan.status == "BLOCKED"
    assert any(item.code == "capability.equipment_missing" for item in plan.issues)


def test_step_serialization_issue_ordering_and_builder() -> None:
    issue = CompilationIssue("WARNING", "code", "path", "message")
    assert issue.to_dict()["severity"] == "WARNING"
    step = CompilationStep(
        step_id="S0001",
        phase="test",
        operation="noop",
        target_id="TARGET",
        adapter_key="adapter.noop",
        payload={"x": 1},
        preconditions=("ready",),
        expected_readback={"ok": True},
    )
    assert step.to_dict()["preconditions"] == ["ready"]

    builder = _StepBuilder()
    builder.add(
        phase="test",
        operation="noop",
        target_id="TARGET",
        adapter_key="adapter.noop",
        payload={},
    )
    assert builder.finish()[0].step_id == "S0001"
    assert len(_canonical_hash({"x": 1})) == 64


def test_recycle_design_adds_closed_loop_steps() -> None:
    value = document()
    value["streams"] = [item for item in value["streams"] if item["id"] != "S004"]
    value["equipment"] = [item for item in value["equipment"] if item["id"] != "LIQ_PROD_001"]
    recycle_equipment = deepcopy(value["equipment"][1])
    recycle_equipment["id"] = "RECYCLE_001"
    recycle_equipment["display_name"] = "Recycle return"
    recycle_equipment["kind"] = "mixer"
    recycle_equipment["parameters"] = []
    value["equipment"].append(recycle_equipment)
    value["equipment"][1]["ports"][0]["multiple"] = True
    value["equipment"][-1]["ports"] = [
        {
            "id": "IN",
            "direction": "in",
            "domain": "material",
            "required": True,
            "multiple": False,
        },
        {
            "id": "OUT",
            "direction": "out",
            "domain": "material",
            "required": True,
            "multiple": False,
        },
    ]
    value["streams"].append(
        {
            "id": "S005",
            "display_name": "Recycle feed",
            "kind": "material",
            "source": {"equipment_id": "SEP_001", "port_id": "LIQ"},
            "target": {"equipment_id": "RECYCLE_001", "port_id": "IN"},
            "components": ["ETHANOL", "WATER"],
            "parameters": [],
        }
    )
    value["streams"].append(
        {
            "id": "TEAR_001",
            "display_name": "Recycle tear",
            "kind": "tear",
            "source": {"equipment_id": "RECYCLE_001", "port_id": "OUT"},
            "target": {"equipment_id": "HTR_001", "port_id": "IN"},
            "components": ["ETHANOL", "WATER"],
            "parameters": [],
        }
    )
    value["recycles"] = [
        {
            "id": "REC_001",
            "stream_id": "S005",
            "tear_stream_id": "TEAR_001",
            "convergence_variables": ["FLOW", "TEMPERATURE"],
            "tolerance": 1e-6,
            "max_iterations": 50,
            "acceleration": "wegstein",
            "status": "USER_PROVIDED",
        }
    ]
    process_design = ProcessDesignIR.from_dict(value)
    profile = replace(
        get_builtin_capability_profile("aspen_plus", "15"),
        qualification="VERIFIED_ON_TARGET_RUNTIME",
    )
    plan = compile_process_design(process_design, profile)
    assert plan.status == "EXECUTABLE"
    operations = [item.operation for item in plan.steps]
    assert "configure_recycle" in operations
    assert "initialize_tear_stream" in operations
    assert "solve_closed_loop" in operations
