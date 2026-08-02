from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from .compilation_plan import CompilationPlan, CompilationStep
from .native_topology import (
    NativeTopologySnapshot,
    TopologyComparisonReport,
    compare_topology,
)


class NativeBuildError(RuntimeError):
    pass


class NativeBuildAdapter(Protocol):
    @property
    def profile_id(self) -> str: ...

    @property
    def profile_hash(self) -> str: ...

    @property
    def adapter_code_sha256(self) -> str: ...

    @property
    def runtime_identity_sha256(self) -> str: ...

    def apply_step(self, step: CompilationStep) -> dict[str, Any]: ...

    def read_topology(self) -> NativeTopologySnapshot: ...

    def read_layout_hash(self) -> str: ...


@dataclass(frozen=True, slots=True)
class StepExecutionRecord:
    step_id: str
    operation: str
    target_id: str
    result: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "operation": self.operation,
            "target_id": self.target_id,
            "result": self.result,
        }


@dataclass(frozen=True, slots=True)
class NativeBuildExecutionRecord:
    plan_hash: str
    profile_id: str
    profile_hash: str
    qualification_evidence_sha256: str
    adapter_code_sha256: str
    runtime_identity_sha256: str
    completed: bool
    step_records: tuple[StepExecutionRecord, ...]
    topology_reports: tuple[TopologyComparisonReport, ...]
    layout_hashes: tuple[str, ...]
    boundary: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_hash": self.plan_hash,
            "profile_id": self.profile_id,
            "profile_hash": self.profile_hash,
            "qualification_evidence_sha256": self.qualification_evidence_sha256,
            "adapter_code_sha256": self.adapter_code_sha256,
            "runtime_identity_sha256": self.runtime_identity_sha256,
            "completed": self.completed,
            "step_records": [item.to_dict() for item in self.step_records],
            "topology_reports": [item.to_dict() for item in self.topology_reports],
            "layout_hashes": list(self.layout_hashes),
            "boundary": self.boundary,
        }


def _contains_expected(observed: Any, expected: Any) -> bool:
    if isinstance(expected, dict):
        if not isinstance(observed, dict):
            return False
        return all(
            key in observed and _contains_expected(observed[key], value)
            for key, value in expected.items()
        )
    if isinstance(expected, list):
        return isinstance(observed, list) and observed == expected
    return bool(observed == expected)


def execute_compilation_plan(
    plan: CompilationPlan,
    adapter: NativeBuildAdapter,
) -> NativeBuildExecutionRecord:
    plan.assert_executable()
    if adapter.profile_id != plan.profile_id:
        raise NativeBuildError("Native adapter profile_id does not match the compilation plan")
    if adapter.profile_hash != plan.profile_hash:
        raise NativeBuildError("Native adapter profile_hash does not match the compilation plan")
    if (
        plan.qualification_evidence_sha256 is None
        or plan.adapter_code_sha256 is None
        or plan.runtime_identity_sha256 is None
    ):
        raise NativeBuildError("Executable plan omitted runtime qualification identity")
    if adapter.adapter_code_sha256 != plan.adapter_code_sha256:
        raise NativeBuildError(
            "Native adapter code hash does not match the runtime qualification"
        )
    if adapter.runtime_identity_sha256 != plan.runtime_identity_sha256:
        raise NativeBuildError(
            "Native adapter runtime identity does not match the runtime qualification"
        )

    step_records: list[StepExecutionRecord] = []
    topology_reports: list[TopologyComparisonReport] = []
    layout_hashes: list[str] = []
    for step in plan.steps:
        if step.operation in {
            "readback_topology",
            "readback_topology_after_reopen",
        }:
            observed_topology = adapter.read_topology()
            report = compare_topology(plan.expected_topology, observed_topology)
            topology_reports.append(report)
            if not report.matches:
                raise NativeBuildError(
                    f"Topology readback mismatch at {step.step_id}: "
                    f"{[item.code for item in report.mismatches]}"
                )
            result = {"topology_hash": report.observed_hash}
        elif step.operation in {"readback_layout", "readback_layout_after_reopen"}:
            layout_hash = adapter.read_layout_hash()
            layout_hashes.append(layout_hash)
            if layout_hash != plan.expected_layout_hash:
                raise NativeBuildError(
                    f"Layout readback mismatch at {step.step_id}: "
                    f"{layout_hash} != {plan.expected_layout_hash}"
                )
            result = {"layout_hash": layout_hash}
        else:
            result = adapter.apply_step(step)
            if not isinstance(result, dict):
                raise NativeBuildError(
                    f"Native adapter returned a non-object result for {step.step_id}"
                )
        if not _contains_expected(result, step.expected_readback):
            raise NativeBuildError(
                f"Mandatory readback failed at {step.step_id}: "
                f"expected subset={step.expected_readback!r}, observed={result!r}"
            )
        step_records.append(
            StepExecutionRecord(
                step_id=step.step_id,
                operation=step.operation,
                target_id=step.target_id,
                result=result,
            )
        )
    return NativeBuildExecutionRecord(
        plan_hash=plan.digest(),
        profile_id=plan.profile_id,
        profile_hash=plan.profile_hash,
        qualification_evidence_sha256=plan.qualification_evidence_sha256,
        adapter_code_sha256=plan.adapter_code_sha256,
        runtime_identity_sha256=plan.runtime_identity_sha256,
        completed=True,
        step_records=tuple(step_records),
        topology_reports=tuple(topology_reports),
        layout_hashes=tuple(layout_hashes),
        boundary=(
            "This execution record proves only that an adapter honored the AspenOps compilation "
            "and readback contracts. Real Aspen certification additionally requires an approved "
            "licensed runtime profile, signed evidence and human engineering acceptance."
        ),
    )
