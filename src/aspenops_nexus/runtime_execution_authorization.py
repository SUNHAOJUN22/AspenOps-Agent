from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .hashing import canonical_hash
from .qualified_compilation import RuntimeQualifiedCompilationPlan
from .runtime_qualification import VerifiedRuntimeQualification, verify_runtime_qualification
from .signed_revocation_policy import (
    RevocationPolicyCheckpoint,
    VerifiedSignedRevocationPolicy,
)
from .simulator_capabilities import SimulatorCapabilityProfile

REVOCATION_POLICY_SCHEMA = "aspenops.runtime-revocation-policy/v1"
RUNTIME_AUTHORIZATION_SCHEMA = "aspenops.fresh-runtime-authorization/v1"
_MAX_ITEMS = 10_000


def _utc_now(value: datetime | None, label: str) -> datetime:
    current = value or datetime.now(UTC)
    if current.tzinfo is None or current.utcoffset() is None:
        raise ValueError(f"{label} must include a timezone")
    return current.astimezone(UTC)


def _time_text(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _parse_time(value: Any, label: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty ISO-8601 timestamp")
    text = value.strip()
    normalized = f"{text[:-1]}+00:00" if text.endswith("Z") else text
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(f"{label} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{label} must include a timezone")
    return parsed.astimezone(UTC)


def _bounded_unique_texts(value: Any, label: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be an array")
    if len(value) > _MAX_ITEMS:
        raise ValueError(f"{label} exceeds {_MAX_ITEMS} items")
    output: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{label}[{index}] must be a non-empty string")
        text = item.strip()
        if "\x00" in text or "\r" in text or "\n" in text:
            raise ValueError(f"{label}[{index}] must be one safe text line")
        output.append(text)
    if len(set(output)) != len(output):
        raise ValueError(f"{label} must contain unique values")
    return tuple(sorted(output))


def _bounded_unique_digests(value: Any, label: str) -> tuple[str, ...]:
    values = _bounded_unique_texts(value, label)
    for item in values:
        if len(item) != 64 or any(character not in "0123456789abcdef" for character in item):
            raise ValueError(f"{label} must contain lowercase SHA-256 digests")
    return values


def _bounded_unique_key_ids(value: Any, label: str) -> tuple[str, ...]:
    values = _bounded_unique_texts(value, label)
    for item in values:
        if len(item) != 32 or any(character not in "0123456789abcdef" for character in item):
            raise ValueError(f"{label} must contain 32-character public-key fingerprints")
    return values


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
        required = {
            "schema",
            "policy_id",
            "issued_at",
            "expires_at",
            "revoked_signing_key_ids",
            "revoked_qualification_evidence_sha256",
            "revoked_profile_ids",
            "revoked_profile_sha256",
            "revoked_adapter_code_sha256",
            "revoked_runtime_identity_sha256",
        }
        if set(value) != required:
            raise ValueError(
                "runtime revocation policy must contain exactly " + str(sorted(required))
            )
        schema = value.get("schema")
        if schema != REVOCATION_POLICY_SCHEMA:
            raise ValueError(f"Unsupported runtime revocation policy schema: {schema}")
        policy_id = value.get("policy_id")
        if not isinstance(policy_id, str) or not policy_id.strip():
            raise ValueError("runtime revocation policy_id must be a non-empty string")
        issued_at = _parse_time(value.get("issued_at"), "runtime revocation issued_at")
        expires_at = _parse_time(value.get("expires_at"), "runtime revocation expires_at")
        if expires_at <= issued_at:
            raise ValueError("runtime revocation expires_at must be later than issued_at")
        return cls(
            policy_id=policy_id.strip(),
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
            schema=schema,
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
        current = _utc_now(now, "runtime revocation verification time")
        if current < self.issued_at:
            raise ValueError("runtime revocation policy is not valid yet")
        if current >= self.expires_at:
            raise ValueError("runtime revocation policy has expired")
        return current


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
            "revocation_witness_expires_at": _time_text(self.revocation_witness_expires_at),
            "authorized_at": _time_text(self.authorized_at),
            "expires_at": _time_text(self.expires_at),
            "required_case_ids": list(self.required_case_ids),
        }

    def digest(self) -> str:
        return canonical_hash(self.to_dict())


def load_trusted_runtime_qualification(
    source: str | Path | bytes | dict[str, Any],
    *,
    trusted_key_dir: str | Path,
    now: datetime | None,
    required_case_ids: tuple[str, ...],
) -> VerifiedRuntimeQualification:
    envelope = source if isinstance(source, dict) else None
    if envelope is None:
        if isinstance(source, bytes):
            value = json.loads(source)
        else:
            value = json.loads(Path(source).expanduser().read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError("runtime qualification envelope root must be an object")
        envelope = value
    signing = envelope.get("signing")
    if not isinstance(signing, dict):
        raise ValueError("runtime qualification signing metadata is invalid")
    key_id = signing.get("key_id")
    if not isinstance(key_id, str):
        raise ValueError("runtime qualification signing key ID is invalid")
    trusted_key = Path(trusted_key_dir).expanduser().resolve() / f"{key_id}.pem"
    if not trusted_key.is_file():
        raise FileNotFoundError(f"Trusted runtime qualification key is unavailable: {key_id}")
    return verify_runtime_qualification(
        envelope,
        trusted_public_key=trusted_key,
        now=now,
        required_case_ids=required_case_ids,
    )


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

    # Compare the explicit security identities before the aggregate dataclass comparison. This
    # preserves precise failure diagnostics and ensures each identity drift path remains testable.
    if qualification.evidence_sha256 != plan.qualification_evidence_sha256:
        raise ValueError("runtime qualification evidence hash changed")
    if qualification.signing_key_id != plan.qualification_key_id:
        raise ValueError("runtime qualification signing key changed")
    if qualification.statement.adapter_code_sha256 != plan.adapter_code_sha256:
        raise ValueError("runtime qualification adapter-code hash changed")
    if qualification.statement.runtime_identity_sha256 != plan.runtime_identity_sha256:
        raise ValueError("runtime qualification identity hash changed")
    if qualification != plan.qualification:
        raise ValueError(
            "fresh runtime qualification does not match the qualified compilation plan"
        )

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
