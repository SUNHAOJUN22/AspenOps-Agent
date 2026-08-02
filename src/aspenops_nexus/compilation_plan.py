from __future__ import annotations

import hashlib
import json
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any, Literal

from .engineering_rules import EngineeringValidationReport, validate_process_design
from .flowsheet_preview import render_flowsheet_preview
from .native_topology import NativeTopologySnapshot
from .process_ir_v2 import EquipmentDefinition, ProcessDesignIR
from .simulator_capabilities import (
    EquipmentCapability,
    SimulatorCapabilityProfile,
)

COMPILATION_PLAN_SCHEMA = "aspenops.compilation-plan/v1"

CompilationStatus = Literal["BLOCKED", "PLAN_ONLY", "EXECUTABLE"]
IssueSeverity = Literal["ERROR", "EXECUTION_BLOCKER", "WARNING"]


def _canonical_hash(value: Any) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True, slots=True, order=True)
class CompilationIssue:
    severity: IssueSeverity
    code: str
    path: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {
            "severity": self.severity,
            "code": self.code,
            "path": self.path,
            "message": self.message,
        }


@dataclass(frozen=True, slots=True)
class CompilationStep:
    step_id: str
    phase: str
    operation: str
    target_id: str
    adapter_key: str
    payload: dict[str, Any]
    preconditions: tuple[str, ...]
    expected_readback: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "phase": self.phase,
            "operation": self.operation,
            "target_id": self.target_id,
            "adapter_key": self.adapter_key,
            "payload": self.payload,
            "preconditions": list(self.preconditions),
            "expected_readback": self.expected_readback,
        }


@dataclass(frozen=True, slots=True)
class CompilationPlan:
    status: CompilationStatus
    design_hash: str
    profile_hash: str
    profile_id: str
    simulator: str
    marketing_version: str
    adapter_contract: str
    expected_topology: NativeTopologySnapshot
    expected_layout_hash: str
    steps: tuple[CompilationStep, ...]
    issues: tuple[CompilationIssue, ...]
    boundary: str
    schema: str = COMPILATION_PLAN_SCHEMA

    @property
    def executable(self) -> bool:
        return self.status == "EXECUTABLE"

    @property
    def blocked(self) -> bool:
        return self.status == "BLOCKED"

    def assert_executable(self) -> None:
        if not self.executable:
            raise RuntimeError(
                "Compilation plan is not executable; status="
                f"{self.status}; issues={[item.code for item in self.issues]}"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "status": self.status,
            "design_hash": self.design_hash,
            "profile_hash": self.profile_hash,
            "profile_id": self.profile_id,
            "simulator": self.simulator,
            "marketing_version": self.marketing_version,
            "adapter_contract": self.adapter_contract,
            "expected_topology": self.expected_topology.to_dict(),
            "expected_layout_hash": self.expected_layout_hash,
            "steps": [item.to_dict() for item in self.steps],
            "issues": [item.to_dict() for item in self.issues],
            "boundary": self.boundary,
        }

    def digest(self) -> str:
        return _canonical_hash(self.to_dict())


def _parameter_payload(item: Any) -> dict[str, Any]:
    return {
        "name": item.name,
        "value": item.value,
        "unit": item.unit,
        "status": item.status,
    }


def _equipment_order(design: ProcessDesignIR) -> tuple[str, ...]:
    equipment_ids = {item.id for item in design.equipment}
    adjacency: dict[str, set[str]] = defaultdict(set)
    indegree = {item: 0 for item in equipment_ids}
    for stream in design.streams:
        if stream.kind == "tear":
            continue
        source = stream.source.equipment_id
        target = stream.target.equipment_id
        if source not in equipment_ids or target not in equipment_ids:
            continue
        if target in adjacency[source]:
            continue
        adjacency[source].add(target)
        indegree[target] += 1
    ready = deque(sorted(item for item, count in indegree.items() if count == 0))
    ordered: list[str] = []
    while ready:
        source = ready.popleft()
        ordered.append(source)
        for target in sorted(adjacency.get(source, set())):
            indegree[target] -= 1
            if indegree[target] == 0:
                ready.append(target)
    for item in sorted(equipment_ids - set(ordered)):
        ordered.append(item)
    return tuple(ordered)


def _engineering_issues(report: EngineeringValidationReport) -> list[CompilationIssue]:
    output: list[CompilationIssue] = []
    for issue in report.issues:
        if issue.severity in {"HARD_ERROR", "ENGINEERING_BLOCKER"}:
            severity: IssueSeverity = "ERROR"
        else:
            severity = "WARNING"
        output.append(
            CompilationIssue(
                severity=severity,
                code=f"engineering.{issue.code}",
                path=issue.path,
                message=issue.message,
            )
        )
    return output


def _capability_issues(
    design: ProcessDesignIR,
    profile: SimulatorCapabilityProfile,
) -> tuple[list[CompilationIssue], dict[str, EquipmentCapability]]:
    issues: list[CompilationIssue] = []
    capabilities = profile.equipment_by_kind()
    for equipment_index, equipment in enumerate(design.equipment):
        path = f"equipment[{equipment_index}]"
        capability = capabilities.get(equipment.kind)
        if capability is None:
            issues.append(
                CompilationIssue(
                    "ERROR",
                    "capability.equipment_missing",
                    path,
                    f"Profile {profile.profile_id} has no contract for {equipment.kind}",
                )
            )
            continue
        if capability.state == "UNSUPPORTED":
            issues.append(
                CompilationIssue(
                    "ERROR",
                    "capability.equipment_unsupported",
                    path,
                    f"Profile {profile.profile_id} marks {equipment.kind} unsupported",
                )
            )
        required_domains = set(capability.required_port_domains)
        observed_domains = {port.domain for port in equipment.ports}
        if not observed_domains.issubset(required_domains):
            issues.append(
                CompilationIssue(
                    "ERROR",
                    "capability.port_domain",
                    f"{path}.ports",
                    "Equipment declares a port domain outside the capability profile",
                )
            )
        supported_parameters = set(capability.supported_parameter_names)
        for parameter in (*equipment.parameters, *equipment.design_specs):
            if parameter.name not in supported_parameters:
                issues.append(
                    CompilationIssue(
                        "ERROR",
                        "capability.parameter_missing",
                        f"{path}.parameters.{parameter.name}",
                        f"Profile has no adapter contract for parameter {parameter.name}",
                    )
                )
    supported_streams = set(profile.supported_stream_kinds)
    for stream_index, stream in enumerate(design.streams):
        if stream.kind not in supported_streams:
            issues.append(
                CompilationIssue(
                    "ERROR",
                    "capability.stream_kind",
                    f"streams[{stream_index}].kind",
                    f"Profile does not support stream kind {stream.kind}",
                )
            )
    if not profile.executable:
        issues.append(
            CompilationIssue(
                "EXECUTION_BLOCKER",
                "profile.not_runtime_verified",
                "capability_profile.qualification",
                "Capability profile is offline-only and cannot authorize COM execution",
            )
        )
    return issues, capabilities


class _StepBuilder:
    def __init__(self) -> None:
        self._steps: list[CompilationStep] = []

    def add(
        self,
        *,
        phase: str,
        operation: str,
        target_id: str,
        adapter_key: str,
        payload: dict[str, Any],
        preconditions: tuple[str, ...] = (),
        expected_readback: dict[str, Any] | None = None,
    ) -> None:
        step_id = f"S{len(self._steps) + 1:04d}"
        self._steps.append(
            CompilationStep(
                step_id=step_id,
                phase=phase,
                operation=operation,
                target_id=target_id,
                adapter_key=adapter_key,
                payload=payload,
                preconditions=preconditions,
                expected_readback=expected_readback or {},
            )
        )

    def finish(self) -> tuple[CompilationStep, ...]:
        return tuple(self._steps)


def _add_equipment_steps(
    builder: _StepBuilder,
    design: ProcessDesignIR,
    capabilities: dict[str, EquipmentCapability],
) -> None:
    equipment_map: dict[str, EquipmentDefinition] = {item.id: item for item in design.equipment}
    for equipment_id in _equipment_order(design):
        equipment = equipment_map[equipment_id]
        capability = capabilities.get(equipment.kind)
        if capability is None:
            continue
        builder.add(
            phase="equipment",
            operation="create_boundary"
            if equipment.kind in {"feed", "product"}
            else "create_equipment",
            target_id=equipment.id,
            adapter_key=capability.adapter_key,
            payload={
                "kind": equipment.kind,
                "display_name": equipment.display_name,
                "vendor_type": equipment.vendor_type,
                "contract_version": equipment.contract_version,
                "ports": [item.to_dict() for item in equipment.ports],
            },
            preconditions=("components_defined", "property_method_defined"),
            expected_readback={"id": equipment.id, "kind": equipment.kind},
        )
        for parameter in sorted(
            (*equipment.parameters, *equipment.design_specs),
            key=lambda item: item.name,
        ):
            builder.add(
                phase="equipment_parameters",
                operation="set_equipment_parameter",
                target_id=f"{equipment.id}.{parameter.name}",
                adapter_key=f"{capability.adapter_key}.parameter.{parameter.name}",
                payload=_parameter_payload(parameter),
                preconditions=(f"equipment:{equipment.id}",),
                expected_readback=_parameter_payload(parameter),
            )


def _build_steps(
    design: ProcessDesignIR,
    profile: SimulatorCapabilityProfile,
    capabilities: dict[str, EquipmentCapability],
    expected_topology: NativeTopologySnapshot,
    expected_layout_hash: str,
) -> tuple[CompilationStep, ...]:
    builder = _StepBuilder()
    builder.add(
        phase="identity",
        operation="assert_profile_identity",
        target_id=profile.profile_id,
        adapter_key="control.assert_profile_identity",
        payload={
            "design_hash": design.digest(),
            "profile_hash": profile.digest(),
            "simulator": profile.simulator,
            "marketing_version": profile.marketing_version,
        },
        expected_readback={"profile_hash": profile.digest()},
    )
    builder.add(
        phase="case",
        operation="create_case_shell",
        target_id=design.name,
        adapter_key="case.create_shell",
        payload={
            "name": design.name,
            "simulator": design.target_simulator,
            "marketing_version": design.target_version,
        },
        preconditions=("profile_identity_verified",),
        expected_readback={"case_open": True},
    )
    for component in sorted(design.components, key=lambda item: item.id):
        builder.add(
            phase="components",
            operation="define_component",
            target_id=component.id,
            adapter_key="component.define",
            payload=component.to_dict(),
            preconditions=("case_open",),
            expected_readback={
                "id": component.id,
                "vendor_id": component.vendor_ids.get(profile.simulator),
            },
        )
    builder.add(
        phase="thermodynamics",
        operation="set_property_method",
        target_id=design.property_method.id,
        adapter_key="thermodynamics.set_property_method",
        payload=design.property_method.to_dict(),
        preconditions=("components_defined",),
        expected_readback={
            "id": design.property_method.id,
            "vendor": design.property_method.vendor,
        },
    )
    _add_equipment_steps(builder, design, capabilities)
    for stream in sorted(design.streams, key=lambda item: item.id):
        builder.add(
            phase="streams",
            operation="create_stream",
            target_id=stream.id,
            adapter_key=f"stream.create.{stream.kind}",
            payload={
                "id": stream.id,
                "display_name": stream.display_name,
                "kind": stream.kind,
                "components": list(stream.components),
                "parameters": [_parameter_payload(item) for item in stream.parameters],
            },
            preconditions=("equipment_created",),
            expected_readback={"id": stream.id, "kind": stream.kind},
        )
        builder.add(
            phase="connections",
            operation="connect_stream",
            target_id=stream.id,
            adapter_key="stream.connect",
            payload={
                "source": stream.source.to_dict(),
                "target": stream.target.to_dict(),
            },
            preconditions=(f"stream:{stream.id}",),
            expected_readback={
                "source": stream.source.to_dict(),
                "target": stream.target.to_dict(),
            },
        )
    for reaction in sorted(design.reactions, key=lambda item: item.id):
        builder.add(
            phase="reactions",
            operation="define_reaction",
            target_id=reaction.id,
            adapter_key=f"reaction.define.{reaction.kind}",
            payload=reaction.to_dict(),
            preconditions=("components_defined", "equipment_created"),
            expected_readback={"id": reaction.id, "kind": reaction.kind},
        )
    for recycle in sorted(design.recycles, key=lambda item: item.id):
        builder.add(
            phase="recycles",
            operation="configure_recycle",
            target_id=recycle.id,
            adapter_key="recycle.configure",
            payload=recycle.to_dict(),
            preconditions=("streams_connected",),
            expected_readback={
                "id": recycle.id,
                "tear_stream_id": recycle.tear_stream_id,
            },
        )
        builder.add(
            phase="recycles",
            operation="initialize_tear_stream",
            target_id=recycle.tear_stream_id,
            adapter_key="recycle.initialize_tear",
            payload={
                "recycle_id": recycle.id,
                "tear_stream_id": recycle.tear_stream_id,
                "variables": list(recycle.convergence_variables),
            },
            preconditions=(f"recycle:{recycle.id}",),
            expected_readback={"initialized": True},
        )
    builder.add(
        phase="solve",
        operation="solve_open_loop",
        target_id=design.name,
        adapter_key="solver.solve_open_loop",
        payload={"recycles_enabled": False},
        preconditions=("streams_connected",),
        expected_readback={"engine_returned": True},
    )
    if design.recycles:
        builder.add(
            phase="solve",
            operation="solve_closed_loop",
            target_id=design.name,
            adapter_key="solver.solve_closed_loop",
            payload={"recycles_enabled": True},
            preconditions=("open_loop_solved", "tear_streams_initialized"),
            expected_readback={"engine_returned": True},
        )
    builder.add(
        phase="verification",
        operation="readback_topology",
        target_id=design.name,
        adapter_key="topology.readback",
        payload={"expected_topology_hash": expected_topology.digest()},
        preconditions=("solve_returned",),
        expected_readback={"topology_hash": expected_topology.digest()},
    )
    builder.add(
        phase="verification",
        operation="readback_layout",
        target_id=design.name,
        adapter_key="layout.readback",
        payload={"expected_layout_hash": expected_layout_hash},
        preconditions=("topology_verified",),
        expected_readback={"layout_hash": expected_layout_hash},
    )
    builder.add(
        phase="persistence",
        operation="save_case",
        target_id=design.name,
        adapter_key="case.save_private_output",
        payload={"overwrite_source": False},
        preconditions=("topology_verified", "layout_verified"),
        expected_readback={"saved": True},
    )
    builder.add(
        phase="persistence",
        operation="close_case",
        target_id=design.name,
        adapter_key="case.close",
        payload={},
        preconditions=("case_saved",),
        expected_readback={"case_open": False},
    )
    builder.add(
        phase="persistence",
        operation="reopen_case",
        target_id=design.name,
        adapter_key="case.reopen_private_output",
        payload={},
        preconditions=("case_closed",),
        expected_readback={"case_open": True},
    )
    builder.add(
        phase="roundtrip_verification",
        operation="readback_topology_after_reopen",
        target_id=design.name,
        adapter_key="topology.readback",
        payload={"expected_topology_hash": expected_topology.digest()},
        preconditions=("case_reopened",),
        expected_readback={"topology_hash": expected_topology.digest()},
    )
    builder.add(
        phase="roundtrip_verification",
        operation="readback_layout_after_reopen",
        target_id=design.name,
        adapter_key="layout.readback",
        payload={"expected_layout_hash": expected_layout_hash},
        preconditions=("roundtrip_topology_verified",),
        expected_readback={"layout_hash": expected_layout_hash},
    )
    return builder.finish()


def compile_process_design(
    design: ProcessDesignIR,
    profile: SimulatorCapabilityProfile,
) -> CompilationPlan:
    engineering = validate_process_design(design)
    issues = _engineering_issues(engineering)
    try:
        profile.assert_matches_design(design)
    except ValueError as exc:
        issues.append(
            CompilationIssue(
                "ERROR",
                "profile.target_mismatch",
                "capability_profile",
                str(exc),
            )
        )
    capability_issues, capabilities = _capability_issues(design, profile)
    issues.extend(capability_issues)
    errors = [item for item in issues if item.severity == "ERROR"]
    execution_blockers = [
        item for item in issues if item.severity == "EXECUTION_BLOCKER"
    ]
    if errors:
        status: CompilationStatus = "BLOCKED"
    elif execution_blockers:
        status = "PLAN_ONLY"
    else:
        status = "EXECUTABLE"
    expected_topology = NativeTopologySnapshot.from_design(design)
    preview = render_flowsheet_preview(design)
    steps = (
        ()
        if status == "BLOCKED"
        else _build_steps(
            design,
            profile,
            capabilities,
            expected_topology,
            preview.layout_hash,
        )
    )
    ordered_issues = tuple(sorted(issues))
    return CompilationPlan(
        status=status,
        design_hash=design.digest(),
        profile_hash=profile.digest(),
        profile_id=profile.profile_id,
        simulator=profile.simulator,
        marketing_version=profile.marketing_version,
        adapter_contract=profile.adapter_contract,
        expected_topology=expected_topology,
        expected_layout_hash=preview.layout_hash,
        steps=steps,
        issues=ordered_issues,
        boundary=(
            "This plan is deterministic and simulator-neutral. COM execution is authorized only "
            "when the capability profile is VERIFIED_ON_TARGET_RUNTIME and every adapter step "
            "performs mandatory readback, topology comparison, save/reopen and roundtrip checks."
        ),
    )
