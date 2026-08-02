from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .hashing import canonical_hash
from .qualified_compilation import RuntimeQualifiedCompilationPlan
from .runtime_qualification import (
    VerifiedRuntimeQualification,
    _digest,
    _key_id,
    _parse_time,
    _text,
    _time_text,
    load_trusted_runtime_qualification,
)
from .simulator_capabilities import SimulatorCapabilityProfile

if TYPE_CHECKING:
    from .signed_revocation_policy import (
        RevocationPolicyCheckpoint,
        VerifiedSignedRevocationPolicy,
    )

REVOCATION_POLICY_SCHEMA = "aspenops.runtime-revocations/v1"
RUNTIME_AUTHORIZATION_SCHEMA = "aspenops.fresh-runtime-authorization/v3"
_MAX_REVOCATIONS_PER_KIND = 10_000


def _utc_now(value: datetime | None, label: str) -> datetime:
    current = value or datetime.now(UTC)
    if current.tzinfo is None or current.utcoffset() is None:
        raise ValueError(f"{label} must include a timezone")
    return current.astimezone(UTC)


def _bounded_unique_texts(value: Any, label: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be an array")
    if len(value) > _MAX_REVOCATIONS_PER_KIND:
        raise ValueError(f"{label} exceeds the revocation-policy limit")
    items = tuple(sorted(_text(item, f"{label} item") for item in value))
    if len(items) != len(set(items)):
        raise ValueError(f"{label} must contain unique values")
    return items


def _bounded_unique_digests(value: Any, label: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be an array")
    if len(value) > _MAX_REVOCATIONS_PER_KIND:
        raise ValueError(f"{label} exceeds the revocation-policy limit")
    items = tuple(sorted(_digest(item, f"{label} item") for item in value))
    if len(items) != len(set(items)):
        raise ValueError(f"{label} must contain unique values")
    return items


def _bounded_unique_key_ids(value: Any, label: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be an array")
    if len(value) > _MAX_REVOCATIONS_PER_KIND:
        raise ValueError(f"{label} exceeds the revocation-policy limit")
    items = tuple(sorted(_key_id(item, f"{label} item") for item in value))
    if len(items) != len(set(items)):
        raise ValueError(f"{label} must contain unique values")
    return items


@dataclass(frozen=True, slots=True)
class RuntimeRevocationPolicy:
    policy_id: str
    issued_at: datetime
    expires_at: datetime
    revoked_signing_key_ids: tuple[str, ...]
    revoked_qualification_evidence_sha256: tuple[str, ...]
    revoked_profile_ids: tuple[str, ...]
    revoked_profile_sha256: tuple[str, ...]
    revoked_adapter_code_sha256: tuple[str, ...]
    revoked_runtime_identity_sha256: tuple[str, ...]
    schema: str = REVOCATION_POLICY_SCHEMA

    @classmethod
    def from_dict(cls, value: Any) -> RuntimeRevocationPolicy:
        if not isinstance(value, dict):
            raise ValueError("runtime revocation policy must be an object")
        required = {field.name for field in fields(cls)}
        if set(value) != required:
            raise ValueError(
                "runtime revocation policy must contain exactly " + str(sorted(required))
            )
        if value.get("schema") != REVOCATION_POLICY_SCHEMA:
            raise ValueError("unsupported runtime revocation-policy schema")
        issued_at = _parse_time(
            value.get("issued_at"),
            "runtime revocation policy.issued_at",
        )
        expires_at = _parse_time(
            value.get("expires_at"),
            "runtime revocation policy.expires_at",
        )
        if expires_at <= issued_at:
            raise ValueError("runtime revocation policy expires_at must be after issued_at")
        return cls(
            policy_id=_text(value.get("policy_id"), "runtime revocation policy.policy_id"),
            issued_at=issued_at,
            expires_at=expires_at,
            revoked_signing_key_ids=_bounded_unique_key_ids(
                value.get("revoked_signing_key_ids"),
                "revoked_signing_key_ids",
            ),
            revoked_qualification_evidence_sha256=_bounded_unique_digests(
                value.get("revoked_qualification_evidence_sha256"),
                "revoked_qualification_evidence_sha256",
            ),
            revoked_profile_ids=_bounded_unique_texts(
                value.get("revoked_profile_ids"),
                "revoked_profile_ids",
            ),
            revoked_profile_sha256=_bounded_unique_digests(
                value.get("revoked_profile_sha256"),
                "revoked_profile_sha256",
            ),
            revoked_adapter_code_sha256=_bounded_unique_digests(
                value.get("revoked_adapter_code_sha256"),
                "revoked_adapter_code_sha256",
            ),
            revoked_runtime_identity_sha256=_bounded_unique_digests(
                value.get("revoked_runtime_identity_sha256"),
                "revoked_runtime_identity_sha256",
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "policy_id": self.policy_id,
            "issued_at": _time_text(self.issued_at),
            "expires_at": _time_text(self.expires_at),
            "revoked_signing_key_ids": list(self.revoked_signing_key_ids),
            "revoked_qualification_evidence_sha256": list(
                self.revoked_qualification_evidence_sha256
            ),
            "revoked_profile_ids": list(self.revoked_profile_ids),
            "revoked_profile_sha256": list(self.revoked_profile_sha256),
            "revoked_adapter_code_sha256": list(self.revoked_adapter_code_sha256),
            "revoked_runtime_identity_sha256": list(self.revoked_runtime_identity_sha256),
        }

    def digest(self) -> str:
        return canonical_hash(self.to_dict())

    def assert_current(self, now: datetime | None = None) -> datetime:
        current = _utc_now(now, "runtime revocation-policy validation time")
        if current < self.issued_at:
            raise ValueError("runtime revocation policy is not valid yet")
        if current >= self.expires_at:
            raise ValueError("runtime revocation policy has expired")
        return current

    def assert_allows(
        self,
        qualification: VerifiedRuntimeQualification,
        profile: SimulatorCapabilityProfile,
    ) -> None:
        if qualification.signing_key_id in self.revoked_signing_key_ids:
            raise PermissionError("runtime qualification signing key is revoked")
        if qualification.evidence_sha256 in self.revoked_qualification_evidence_sha256:
            raise PermissionError("runtime qualification evidence is revoked")
        if profile.profile_id in self.revoked_profile_ids:
            raise PermissionError("runtime capability profile ID is revoked")
        if profile.digest() in self.revoked_profile_sha256:
            raise PermissionError("runtime capability profile hash is revoked")
        if qualification.statement.adapter_code_sha256 in self.revoked_adapter_code_sha256:
            raise PermissionError("runtime adapter code is revoked")
        if qualification.statement.runtime_identity_sha256 in self.revoked_runtime_identity_sha256:
            raise PermissionError("runtime identity is revoked")


@dataclass(frozen=True, slots=True)
class FreshRuntimeAuthorization:
    qualified_plan_sha256: str
    qualification_evidence_sha256: str
    qualification_key_id: str
    profile_sha256: str
    adapter_code_sha256: str
    runtime_identity_sha256: str
    revocation_policy_sha256: str
    revocation_policy_signing_key_id: str
    revocation_policy_sequence: int
    revocation_checkpoint_sha256: str
    revocation_witness_sha256: str
    revocation_witness_signing_key_id: str
    revocation_witness_id: str
    revocation_witness_expires_at: datetime
    authorized_at: datetime
    expires_at: datetime
    required_case_ids: tuple[str, ...]
    schema: str = RUNTIME_AUTHORIZATION_SCHEMA

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "qualified_plan_sha256": self.qualified_plan_sha256,
            "qualification_evidence_sha256": self.qualification_evidence_sha256,
            "qualification_key_id": self.qualification_key_id,
            "profile_sha256": self.profile_sha256,
            "adapter_code_sha256": self.adapter_code_sha256,
            "runtime_identity_sha256": self.runtime_identity_sha256,
            "revocation_policy_sha256": self.revocation_policy_sha256,
            "revocation_policy_signing_key_id": self.revocation_policy_signing_key_id,
            "revocation_policy_sequence": self.revocation_policy_sequence,
            "revocation_checkpoint_sha256": self.revocation_checkpoint_sha256,
            "revocation_witness_sha256": self.revocation_witness_sha256,
            "revocation_witness_signing_key_id": self.revocation_witness_signing_key_id,
            "revocation_witness_id": self.revocation_witness_id,
            "revocation_witness_expires_at": _time_text(
                self.revocation_witness_expires_at
            ),
            "authorized_at": _time_text(self.authorized_at),
            "expires_at": _time_text(self.expires_at),
            "required_case_ids": list(self.required_case_ids),
        }

    def digest(self) -> str:
        return canonical_hash(self.to_dict())


def load_trusted_runtime_revocation_policy(
    trusted_key_dir: str | Path,
    *,
    now: datetime | None = None,
) -> tuple[VerifiedSignedRevocationPolicy, RevocationPolicyCheckpoint]:
    from .signed_revocation_policy import load_trusted_signed_revocation_policy

    return load_trusted_signed_revocation_policy(trusted_key_dir, now=now)


def authorize_runtime_execution(
    plan: RuntimeQualifiedCompilationPlan,
    profile: SimulatorCapabilityProfile,
    qualification_source: str | Path | bytes | dict[str, Any],
    *,
    trusted_key_dir: str | Path,
    now: datetime | None = None,
    additional_required_case_ids: tuple[str, ...] = (),
) -> FreshRuntimeAuthorization:
    from .revocation_witness import load_trusted_revocation_witness

    plan.assert_executable()
    if profile.qualification == "REVOKED":
        raise PermissionError("runtime capability profile is revoked")
    if plan.profile_id != profile.profile_id or plan.profile_hash != profile.digest():
        raise ValueError("runtime-qualified plan does not match the current profile")

    required_cases = tuple(sorted({*plan.required_case_ids, *additional_required_case_ids}))
    current = _utc_now(now, "runtime execution authorization time")
    qualification = load_trusted_runtime_qualification(
        qualification_source,
        trusted_key_dir=trusted_key_dir,
        now=current,
        required_case_ids=required_cases,
    )
    qualification.assert_matches_profile(profile)
    if qualification != plan.qualification:
        raise ValueError(
            "fresh runtime qualification does not match the qualified compilation plan"
        )
    if qualification.evidence_sha256 != plan.qualification_evidence_sha256:
        raise ValueError("runtime qualification evidence hash changed")
    if qualification.signing_key_id != plan.qualification_key_id:
        raise ValueError("runtime qualification signing key changed")
    if qualification.statement.adapter_code_sha256 != plan.adapter_code_sha256:
        raise ValueError("runtime qualification adapter-code hash changed")
    if qualification.statement.runtime_identity_sha256 != plan.runtime_identity_sha256:
        raise ValueError("runtime qualification identity hash changed")

    signed_policy, checkpoint = load_trusted_runtime_revocation_policy(
        trusted_key_dir,
        now=current,
    )
    signed_policy.assert_allows(qualification, profile)
    witness = load_trusted_revocation_witness(
        trusted_key_dir,
        signed_policy,
        checkpoint,
        now=current,
    )
    expires_at = min(
        qualification.statement.expires_at,
        signed_policy.policy.expires_at,
        witness.statement.expires_at,
    )
    return FreshRuntimeAuthorization(
        qualified_plan_sha256=plan.digest(),
        qualification_evidence_sha256=qualification.evidence_sha256,
        qualification_key_id=qualification.signing_key_id,
        profile_sha256=profile.digest(),
        adapter_code_sha256=qualification.statement.adapter_code_sha256,
        runtime_identity_sha256=qualification.statement.runtime_identity_sha256,
        revocation_policy_sha256=signed_policy.evidence_sha256,
        revocation_policy_signing_key_id=signed_policy.signing_key_id,
        revocation_policy_sequence=signed_policy.sequence,
        revocation_checkpoint_sha256=checkpoint.digest(),
        revocation_witness_sha256=witness.evidence_sha256,
        revocation_witness_signing_key_id=witness.signing_key_id,
        revocation_witness_id=witness.statement.witness_id,
        revocation_witness_expires_at=witness.statement.expires_at,
        authorized_at=current,
        expires_at=expires_at,
        required_case_ids=required_cases,
    )
