from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from aspenops_nexus.compilation_plan import CompilationPlan, CompilationStep, compile_process_design
from aspenops_nexus.native_builder import (
    NativeBuildError,
    _contains_expected,
    execute_compilation_plan,
)
from aspenops_nexus.native_topology import NativeTopologySnapshot, TopologyNode
from aspenops_nexus.process_ir_v2 import ProcessDesignIR
from aspenops_nexus.simulator_capabilities import get_builtin_capability_profile

ROOT = Path(__file__).resolve().parents[1]
DESIGN = ROOT / "examples/process-design-v2.example.json"


def design() -> ProcessDesignIR:
    value = json.loads(DESIGN.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return ProcessDesignIR.from_dict(value)


def executable_plan() -> CompilationPlan:
    profile = replace(
        get_builtin_capability_profile("aspen_plus", "15"),
        qualification="VERIFIED_ON_TARGET_RUNTIME",
    )
    return compile_process_design(design(), profile)


class FakeAdapter:
    def __init__(
        self,
        plan: CompilationPlan,
        *,
        topology: NativeTopologySnapshot | None = None,
        layout_hash: str | None = None,
    ) -> None:
        self._profile_id = plan.profile_id
        self._profile_hash = plan.profile_hash
        self.topology = topology or plan.expected_topology
        self.layout_hash = layout_hash or plan.expected_layout_hash
        self.operations: list[str] = []
        self.override_results: dict[str, Any] = {}

    @property
    def profile_id(self) -> str:
        return self._profile_id

    @property
    def profile_hash(self) -> str:
        return self._profile_hash

    def apply_step(self, step: CompilationStep) -> dict[str, Any]:
        self.operations.append(step.operation)
        override = self.override_results.get(step.step_id)
        if override is not None:
            return override
        return dict(step.expected_readback)

    def read_topology(self) -> NativeTopologySnapshot:
        self.operations.append("read_topology")
        return self.topology

    def read_layout_hash(self) -> str:
        self.operations.append("read_layout_hash")
        return self.layout_hash


def test_execute_compilation_plan_success() -> None:
    plan = executable_plan()
    adapter = FakeAdapter(plan)
    record = execute_compilation_plan(plan, adapter)
    assert record.completed is True
    assert record.plan_hash == plan.digest()
    assert record.profile_id == plan.profile_id
    assert record.profile_hash == plan.profile_hash
    assert len(record.step_records) == len(plan.steps)
    assert len(record.topology_reports) == 2
    assert all(item.matches for item in record.topology_reports)
    assert record.layout_hashes == (plan.expected_layout_hash, plan.expected_layout_hash)
    assert "licensed runtime profile" in record.boundary
    assert record.to_dict()["completed"] is True


def test_plan_only_cannot_execute() -> None:
    plan = compile_process_design(
        design(),
        get_builtin_capability_profile("aspen_plus", "15"),
    )
    with pytest.raises(RuntimeError, match="not executable"):
        execute_compilation_plan(plan, FakeAdapter(plan))


def test_adapter_profile_identity_must_match() -> None:
    plan = executable_plan()
    adapter = FakeAdapter(plan)
    adapter._profile_id = "wrong"
    with pytest.raises(NativeBuildError, match="profile_id"):
        execute_compilation_plan(plan, adapter)

    adapter = FakeAdapter(plan)
    adapter._profile_hash = "0" * 64
    with pytest.raises(NativeBuildError, match="profile_hash"):
        execute_compilation_plan(plan, adapter)


def test_topology_mismatch_fails_closed() -> None:
    plan = executable_plan()
    changed = replace(
        plan.expected_topology,
        nodes=(*plan.expected_topology.nodes, TopologyNode("EXTRA_001", "heater")),
        source="native-readback",
    )
    with pytest.raises(NativeBuildError, match="Topology readback mismatch"):
        execute_compilation_plan(plan, FakeAdapter(plan, topology=changed))


def test_layout_mismatch_fails_closed() -> None:
    plan = executable_plan()
    with pytest.raises(NativeBuildError, match="Layout readback mismatch"):
        execute_compilation_plan(plan, FakeAdapter(plan, layout_hash="0" * 64))


def test_non_object_step_result_fails_closed() -> None:
    plan = executable_plan()
    adapter = FakeAdapter(plan)
    first_apply = next(
        item
        for item in plan.steps
        if item.operation
        not in {
            "readback_topology",
            "readback_topology_after_reopen",
            "readback_layout",
            "readback_layout_after_reopen",
        }
    )
    adapter.override_results[first_apply.step_id] = "not-an-object"
    with pytest.raises(NativeBuildError, match="non-object"):
        execute_compilation_plan(plan, adapter)


def test_missing_mandatory_readback_fails_closed() -> None:
    plan = executable_plan()
    adapter = FakeAdapter(plan)
    first_apply = next(item for item in plan.steps if item.expected_readback)
    adapter.override_results[first_apply.step_id] = {}
    with pytest.raises(NativeBuildError, match="Mandatory readback failed"):
        execute_compilation_plan(plan, adapter)


def test_expected_subset_comparison() -> None:
    assert _contains_expected({"a": 1, "b": 2}, {"a": 1}) is True
    assert _contains_expected({"a": {"b": 1, "c": 2}}, {"a": {"b": 1}}) is True
    assert _contains_expected({"a": [1, 2]}, {"a": [1, 2]}) is True
    assert _contains_expected({"a": [1, 2]}, {"a": [1]}) is False
    assert _contains_expected([], {}) is False
    assert _contains_expected({"a": 1}, {"a": 2}) is False
