from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from .compilation_plan import CompilationStep
from .native_topology import (
    NativeTopologySnapshot,
    TopologyComparisonReport,
    compare_topology,
)
from .qualified_compilation import RuntimeQualifiedCompilationPlan
from .runtime_execution_authorization import authorize_runtime_execution
from .simulator_capabilities import SimulatorCapabilityProfile


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
    runtime_authorization_sha256: str
    revocation_policy_sha256: str
    authorized_at: str
    authorization_expires_at: str
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
            "runtime_authorization_sha256": self.runtime_authorization_sha256,
            "revocation_policy_sha256": self.revocation_policy_sha256,
            "authorized_at": self.authorized_at,
            "authorization_expires_at": self.authorization_expires_at,
            "completed": self.completed,
            "step_records": [item.to_dict() for item in self.step_records],
            "topology_reports": [item.to_dict() for item in self.topology_reports],
            "layout_hashes": list(self.layout_hashes),
            "boundary": self.boundary,
        }


def _time_text(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


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
    plan: RuntimeQualifiedCompilationPlan,
    adapter: NativeBuildAdapter,
    *,
    profile: SimulatorCapabilityProfile | None = None,
    qualification_source: str | Path | bytes | dict[str, Any] | None = None,
    trusted_key_dir: str | Path | None = None,
    now: datetime | None = None,
    additional_required_case_ids: tuple[str, ...] = (),
) -> NativeBuildExecutionRecord:
    if not isinstance(plan, RuntimeQualifiedCompilationPlan):
        raise NativeBuildError("RuntimeQualifiedCompilationPlan is required for native execution")
    if profile is None or qualification_source is None or trusted_key_dir is None:
        raise NativeBuildError(
            "Fresh runtime authorization inputs are required for native execution"
        )
    try:
        authorization = authorize_runtime_execution(
            plan,
            profile,
            qualification_source,
            trusted_key_dir=trusted_key_dir,
            now=now,
            additional_required_case_ids=additional_required_case_ids,
        )
    except (FileNotFoundError, PermissionError, ValueError) as exc:
        raise NativeBuildError(f"Fresh runtime authorization failed: {exc}") from exc

    if adapter.profile_id != plan.profile_id:
        raise NativeBuildError("Native adapter profile_id does not match the compilation plan")
    if adapter.profile_hash != authorization.profile_sha256:
        raise NativeBuildError("Native adapter profile_hash does not match the compilation plan")
    if adapter.adapter_code_sha256 != authorization.adapter_code_sha256:
        raise NativeBuildError("Native adapter code hash does not match the runtime qualification")
    if adapter.runtime_identity_sha256 != authorization.runtime_identity_sha256:
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
        profile_hash=authorization.profile_sha256,
        qualification_evidence_sha256=authorization.qualification_evidence_sha256,
        adapter_code_sha256=authorization.adapter_code_sha256,
        runtime_identity_sha256=authorization.runtime_identity_sha256,
        runtime_authorization_sha256=authorization.digest(),
        revocation_policy_sha256=authorization.revocation_policy_sha256,
        authorized_at=_time_text(authorization.authorized_at),
        authorization_expires_at=_time_text(authorization.expires_at),
        completed=True,
        step_records=tuple(step_records),
        topology_reports=tuple(topology_reports),
        layout_hashes=tuple(layout_hashes),
        boundary=(
            "This execution record proves only that a freshly authorized adapter honored the "
            "AspenOps compilation and readback contracts. Real Aspen certification additionally "
            "requires licensed runtime evidence and human engineering acceptance."
        ),
    )
