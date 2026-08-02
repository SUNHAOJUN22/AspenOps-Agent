from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from .compilation_plan import CompilationPlan, CompilationStep, compile_process_design
from .native_topology import NativeTopologySnapshot
from .process_ir_v2 import ProcessDesignIR
from .runtime_qualification import VerifiedRuntimeQualification
from .simulator_capabilities import SimulatorCapabilityProfile

QUALIFIED_PLAN_SCHEMA = "aspenops.runtime-qualified-compilation-plan/v1"


def _canonical_hash(value: Any) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True, slots=True)
class RuntimeQualifiedCompilationPlan:
    base_plan: CompilationPlan
    qualification: VerifiedRuntimeQualification
    required_case_ids: tuple[str, ...]
    schema: str = QUALIFIED_PLAN_SCHEMA

    @property
    def profile_id(self) -> str:
        return self.base_plan.profile_id

    @property
    def profile_hash(self) -> str:
        return self.base_plan.profile_hash

    @property
    def qualification_evidence_sha256(self) -> str:
        return self.qualification.evidence_sha256

    @property
    def qualification_key_id(self) -> str:
        return self.qualification.signing_key_id

    @property
    def adapter_code_sha256(self) -> str:
        return self.qualification.statement.adapter_code_sha256

    @property
    def runtime_identity_sha256(self) -> str:
        return self.qualification.statement.runtime_identity_sha256

    @property
    def steps(self) -> tuple[CompilationStep, ...]:
        return self.base_plan.steps

    @property
    def expected_topology(self) -> NativeTopologySnapshot:
        return self.base_plan.expected_topology

    @property
    def expected_layout_hash(self) -> str:
        return self.base_plan.expected_layout_hash

    @property
    def executable(self) -> bool:
        return not self.base_plan.blocked

    def assert_executable(self) -> None:
        if self.base_plan.blocked:
            raise RuntimeError("Runtime-qualified plan wraps a blocked compilation plan")
        self.qualification.assert_required_cases(self.required_case_ids)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "base_plan": self.base_plan.to_dict(),
            "base_plan_sha256": self.base_plan.digest(),
            "qualification_evidence_sha256": self.qualification_evidence_sha256,
            "qualification_key_id": self.qualification_key_id,
            "adapter_code_sha256": self.adapter_code_sha256,
            "runtime_identity_sha256": self.runtime_identity_sha256,
            "required_case_ids": list(self.required_case_ids),
            "boundary": (
                "This wrapper authorizes only the exact deterministic base plan and the exact "
                "verified qualification evidence. It does not replace native readback, signed run "
                "evidence or human engineering acceptance."
            ),
        }

    def digest(self) -> str:
        return _canonical_hash(self.to_dict())


def qualify_compilation_plan(
    design: ProcessDesignIR,
    profile: SimulatorCapabilityProfile,
    qualification: VerifiedRuntimeQualification,
    *,
    required_case_ids: tuple[str, ...] = (),
) -> RuntimeQualifiedCompilationPlan:
    if profile.qualification == "REVOKED":
        raise ValueError("Revoked capability profile cannot be runtime-qualified")
    qualification.assert_matches_profile(profile)
    qualification.assert_required_cases(required_case_ids)
    base_plan = compile_process_design(design, profile)
    if base_plan.blocked:
        raise ValueError(
            "Cannot runtime-qualify a blocked compilation plan: "
            f"{[item.code for item in base_plan.issues]}"
        )
    return RuntimeQualifiedCompilationPlan(
        base_plan=base_plan,
        qualification=qualification,
        required_case_ids=tuple(sorted(set(required_case_ids))),
    )
