from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, fields
from typing import Any

from .certification import PENDING_REAL_ASPEN_CERTIFICATION
from .hashing import canonical_hash
from .licensed_certification import LicensedCertificationPlan
from .qualified_compilation import RuntimeQualifiedCompilationPlan
from .simulator_capabilities import SimulatorCapabilityProfile

QUALIFIED_LICENSED_LINK_SCHEMA = "aspenops.qualified-licensed-link/v1"
OFFLINE_BINDING_ONLY = "OFFLINE_BINDING_ONLY"

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
_KEY_ID_RE = re.compile(r"^[0-9a-f]{32}$")


def _canonical_hash(value: Any) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    text = value.strip()
    if "\x00" in text or "\r" in text or "\n" in text:
        raise ValueError(f"{label} must be one safe text line")
    return text


def _digest(value: Any, label: str) -> str:
    text = _text(value, label).casefold()
    if _SHA256_RE.fullmatch(text) is None:
        raise ValueError(f"{label} must be a lowercase SHA-256 digest")
    return text


def _commit(value: Any) -> str:
    text = _text(value, "approved_commit").casefold()
    if _COMMIT_RE.fullmatch(text) is None:
        raise ValueError("approved_commit must be a full lowercase Git SHA")
    return text


def _key_id(value: Any, label: str) -> str:
    text = _text(value, label).casefold()
    if _KEY_ID_RE.fullmatch(text) is None:
        raise ValueError(f"{label} must be a 32-character lowercase key identifier")
    return text


def _case_ids(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ValueError("golden_case_ids must be an array")
    items = tuple(sorted(_text(item, "golden_case_ids item") for item in value))
    if not items:
        raise ValueError("golden_case_ids must contain at least one case")
    if len(items) != len(set(item.casefold() for item in items)):
        raise ValueError("golden_case_ids must contain unique values")
    return items


@dataclass(frozen=True, slots=True)
class QualifiedLicensedCertificationLink:
    licensed_plan_sha256: str
    case_id: str
    approved_commit: str
    backend: str
    model_sha256: str
    registry_sha256: str
    licensed_signing_key_id: str
    qualified_plan_sha256: str
    base_plan_sha256: str
    qualification_evidence_sha256: str
    qualification_key_id: str
    profile_id: str
    profile_sha256: str
    adapter_contract: str
    adapter_code_sha256: str
    runtime_identity_sha256: str
    expected_topology_sha256: str
    expected_layout_sha256: str
    golden_case_ids: tuple[str, ...]
    schema: str = QUALIFIED_LICENSED_LINK_SCHEMA
    execution_status: str = OFFLINE_BINDING_ONLY
    real_aspen_status: str = PENDING_REAL_ASPEN_CERTIFICATION

    @classmethod
    def from_dict(cls, value: Any) -> QualifiedLicensedCertificationLink:
        if not isinstance(value, dict):
            raise ValueError("qualified licensed link must be an object")
        required = {field.name for field in fields(cls)}
        if set(value) != required:
            raise ValueError(
                "qualified licensed link must contain exactly " + str(sorted(required))
            )
        if value.get("schema") != QUALIFIED_LICENSED_LINK_SCHEMA:
            raise ValueError("unsupported qualified licensed link schema")
        if value.get("execution_status") != OFFLINE_BINDING_ONLY:
            raise ValueError("qualified licensed link cannot authorize runtime execution")
        if value.get("real_aspen_status") != PENDING_REAL_ASPEN_CERTIFICATION:
            raise ValueError("qualified licensed link must remain pending real certification")
        return cls(
            licensed_plan_sha256=_digest(
                value.get("licensed_plan_sha256"), "licensed_plan_sha256"
            ),
            case_id=_text(value.get("case_id"), "case_id"),
            approved_commit=_commit(value.get("approved_commit")),
            backend=_text(value.get("backend"), "backend").casefold(),
            model_sha256=_digest(value.get("model_sha256"), "model_sha256"),
            registry_sha256=_digest(value.get("registry_sha256"), "registry_sha256"),
            licensed_signing_key_id=_key_id(
                value.get("licensed_signing_key_id"), "licensed_signing_key_id"
            ),
            qualified_plan_sha256=_digest(
                value.get("qualified_plan_sha256"), "qualified_plan_sha256"
            ),
            base_plan_sha256=_digest(value.get("base_plan_sha256"), "base_plan_sha256"),
            qualification_evidence_sha256=_digest(
                value.get("qualification_evidence_sha256"),
                "qualification_evidence_sha256",
            ),
            qualification_key_id=_key_id(
                value.get("qualification_key_id"), "qualification_key_id"
            ),
            profile_id=_text(value.get("profile_id"), "profile_id"),
            profile_sha256=_digest(value.get("profile_sha256"), "profile_sha256"),
            adapter_contract=_text(value.get("adapter_contract"), "adapter_contract"),
            adapter_code_sha256=_digest(
                value.get("adapter_code_sha256"), "adapter_code_sha256"
            ),
            runtime_identity_sha256=_digest(
                value.get("runtime_identity_sha256"), "runtime_identity_sha256"
            ),
            expected_topology_sha256=_digest(
                value.get("expected_topology_sha256"), "expected_topology_sha256"
            ),
            expected_layout_sha256=_digest(
                value.get("expected_layout_sha256"), "expected_layout_sha256"
            ),
            golden_case_ids=_case_ids(value.get("golden_case_ids")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "execution_status": self.execution_status,
            "real_aspen_status": self.real_aspen_status,
            "licensed_plan_sha256": self.licensed_plan_sha256,
            "case_id": self.case_id,
            "approved_commit": self.approved_commit,
            "backend": self.backend,
            "model_sha256": self.model_sha256,
            "registry_sha256": self.registry_sha256,
            "licensed_signing_key_id": self.licensed_signing_key_id,
            "qualified_plan_sha256": self.qualified_plan_sha256,
            "base_plan_sha256": self.base_plan_sha256,
            "qualification_evidence_sha256": self.qualification_evidence_sha256,
            "qualification_key_id": self.qualification_key_id,
            "profile_id": self.profile_id,
            "profile_sha256": self.profile_sha256,
            "adapter_contract": self.adapter_contract,
            "adapter_code_sha256": self.adapter_code_sha256,
            "runtime_identity_sha256": self.runtime_identity_sha256,
            "expected_topology_sha256": self.expected_topology_sha256,
            "expected_layout_sha256": self.expected_layout_sha256,
            "golden_case_ids": list(self.golden_case_ids),
        }

    def digest(self) -> str:
        return _canonical_hash(self.to_dict())

    def assert_matches(
        self,
        licensed_plan: LicensedCertificationPlan,
        qualified_plan: RuntimeQualifiedCompilationPlan,
        profile: SimulatorCapabilityProfile,
        *,
        required_case_ids: tuple[str, ...] = (),
    ) -> None:
        expected = link_qualified_compilation_to_licensed_plan(
            licensed_plan,
            qualified_plan,
            profile,
            required_case_ids=required_case_ids,
        )
        mismatches = [
            field.name
            for field in fields(self)
            if getattr(self, field.name) != getattr(expected, field.name)
        ]
        if mismatches:
            raise ValueError(
                "qualified licensed link does not match current inputs: "
                + ", ".join(mismatches)
            )


def link_qualified_compilation_to_licensed_plan(
    licensed_plan: LicensedCertificationPlan,
    qualified_plan: RuntimeQualifiedCompilationPlan,
    profile: SimulatorCapabilityProfile,
    *,
    required_case_ids: tuple[str, ...] = (),
) -> QualifiedLicensedCertificationLink:
    qualified_plan.assert_executable()
    qualified_plan.qualification.assert_matches_profile(profile)
    if licensed_plan.backend != profile.simulator:
        raise ValueError("licensed certification backend does not match capability profile")
    if qualified_plan.profile_id != profile.profile_id:
        raise ValueError("runtime-qualified plan profile ID does not match capability profile")
    if qualified_plan.profile_hash != profile.digest():
        raise ValueError("runtime-qualified plan profile hash does not match capability profile")

    passed_cases = {
        item.case_id
        for item in qualified_plan.qualification.statement.golden_cases
        if item.passed
    }
    required = tuple(
        sorted(
            {
                licensed_plan.case_id,
                *qualified_plan.required_case_ids,
                *required_case_ids,
            }
        )
    )
    qualified_plan.qualification.assert_required_cases(required)
    if licensed_plan.case_id not in passed_cases:
        raise ValueError(
            "licensed certification case is not a passed Golden Case in the qualification"
        )

    return QualifiedLicensedCertificationLink(
        licensed_plan_sha256=canonical_hash(licensed_plan.to_dict()),
        case_id=licensed_plan.case_id,
        approved_commit=licensed_plan.approved_commit,
        backend=licensed_plan.backend,
        model_sha256=licensed_plan.model_sha256,
        registry_sha256=licensed_plan.registry_sha256,
        licensed_signing_key_id=licensed_plan.signing_key_id,
        qualified_plan_sha256=qualified_plan.digest(),
        base_plan_sha256=qualified_plan.base_plan.digest(),
        qualification_evidence_sha256=qualified_plan.qualification_evidence_sha256,
        qualification_key_id=qualified_plan.qualification_key_id,
        profile_id=profile.profile_id,
        profile_sha256=profile.digest(),
        adapter_contract=profile.adapter_contract,
        adapter_code_sha256=qualified_plan.adapter_code_sha256,
        runtime_identity_sha256=qualified_plan.runtime_identity_sha256,
        expected_topology_sha256=qualified_plan.expected_topology.digest(),
        expected_layout_sha256=qualified_plan.expected_layout_hash,
        golden_case_ids=required,
    )
