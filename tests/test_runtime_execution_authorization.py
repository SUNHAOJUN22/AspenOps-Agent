from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from aspenops_nexus.process_ir_v2 import ProcessDesignIR
from aspenops_nexus.qualified_compilation import (
    RuntimeQualifiedCompilationPlan,
    qualify_compilation_plan,
)
from aspenops_nexus.runtime_execution_authorization import (
    REVOCATION_POLICY_SCHEMA,
    RuntimeRevocationPolicy,
    authorize_runtime_execution,
    load_trusted_runtime_revocation_policy,
)
from aspenops_nexus.runtime_qualification import (
    GoldenCaseQualification,
    RuntimeQualificationStatement,
    sign_runtime_qualification,
    verify_runtime_qualification,
)
from aspenops_nexus.signed_revocation_policy import (
    REVOCATION_AUTHORITY_DIRECTORY,
    REVOCATION_CHECKPOINT_FILENAME,
    SIGNED_POLICY_FILENAME,
    SignedRevocationPolicyStatement,
    advance_revocation_policy_checkpoint,
    sign_revocation_policy,
    verify_revocation_policy,
)
from aspenops_nexus.simulator_capabilities import (
    SimulatorCapabilityProfile,
    get_builtin_capability_profile,
)

ROOT = Path(__file__).resolve().parents[1]
DESIGN = ROOT / "examples/process-design-v2.example.json"
NOW = datetime(2026, 8, 2, 12, 0, tzinfo=UTC)
CASE_ID = "HEATER_FLASH_V15"
_PRIVATE_AUTHORITY_KEY = ".test-revocation-authority-private.pem"
_PUBLIC_AUTHORITY_KEY = ".test-revocation-authority-public.pem"


def design() -> ProcessDesignIR:
    value = json.loads(DESIGN.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return ProcessDesignIR.from_dict(value)


def authority_keys(root: Path) -> tuple[bytes, bytes]:
    pytest.importorskip("cryptography")
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    private_path = root / _PRIVATE_AUTHORITY_KEY
    public_path = root / _PUBLIC_AUTHORITY_KEY
    if private_path.is_file() and public_path.is_file():
        return private_path.read_bytes(), public_path.read_bytes()
    private = Ed25519PrivateKey.generate()
    private_pem = private.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = private.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    private_path.write_bytes(private_pem)
    public_path.write_bytes(public_pem)
    return private_pem, public_pem


def write_policy(
    root: Path,
    *,
    issued_at: datetime | None = None,
    expires_at: datetime | None = None,
    sequence: int = 1,
    previous_policy_sha256: str | None = None,
    **revocations: list[str],
) -> dict[str, Any]:
    policy_document: dict[str, Any] = {
        "schema": REVOCATION_POLICY_SCHEMA,
        "policy_id": f"policy-{sequence:03d}",
        "issued_at": (issued_at or NOW - timedelta(hours=1)).isoformat(),
        "expires_at": (expires_at or NOW + timedelta(hours=2)).isoformat(),
        "revoked_signing_key_ids": [],
        "revoked_qualification_evidence_sha256": [],
        "revoked_profile_ids": [],
        "revoked_profile_sha256": [],
        "revoked_adapter_code_sha256": [],
        "revoked_runtime_identity_sha256": [],
    }
    policy_document.update(revocations)
    private_pem, public_pem = authority_keys(root)
    statement = SignedRevocationPolicyStatement(
        sequence=sequence,
        previous_policy_sha256=previous_policy_sha256,
        policy=RuntimeRevocationPolicy.from_dict(policy_document),
    )
    envelope = sign_revocation_policy(statement, private_pem)
    verified = verify_revocation_policy(
        envelope,
        trusted_public_key=public_pem,
        now=NOW,
    )
    checkpoint = advance_revocation_policy_checkpoint(verified)
    signing = envelope["signing"]
    assert isinstance(signing, dict)
    key_id = signing["key_id"]
    assert isinstance(key_id, str)
    authority = root / REVOCATION_AUTHORITY_DIRECTORY
    authority.mkdir(parents=True, exist_ok=True)
    (authority / f"{key_id}.pem").write_bytes(public_pem)
    (root / SIGNED_POLICY_FILENAME).write_text(
        json.dumps(envelope, sort_keys=True),
        encoding="utf-8",
    )
    (root / REVOCATION_CHECKPOINT_FILENAME).write_text(
        json.dumps(checkpoint.to_dict(), sort_keys=True),
        encoding="utf-8",
    )
    return policy_document


def context(
    tmp_path: Path,
    *,
    issued_at: datetime | None = None,
    expires_at: datetime | None = None,
    verified_at: datetime | None = None,
    case_ids: tuple[str, ...] = (CASE_ID,),
) -> tuple[
    RuntimeQualifiedCompilationPlan,
    SimulatorCapabilityProfile,
    dict[str, Any],
    str,
]:
    pytest.importorskip("cryptography")
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    profile = get_builtin_capability_profile("aspen_plus", "15")
    private = Ed25519PrivateKey.generate()
    private_pem = private.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = private.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    statement = RuntimeQualificationStatement(
        profile_id=profile.profile_id,
        profile_sha256=profile.digest(),
        simulator=profile.simulator,
        marketing_version=profile.marketing_version,
        adapter_contract=profile.adapter_contract,
        adapter_code_sha256="a" * 64,
        runtime_identity_sha256="b" * 64,
        issued_at=issued_at or NOW - timedelta(hours=1),
        expires_at=expires_at or NOW + timedelta(hours=4),
        approved_by="Engineer A",
        approval_scope="Synthetic fresh-authorization test",
        golden_cases=tuple(
            GoldenCaseQualification(
                case_id=case_id,
                evidence_bundle_sha256="c" * 64,
                topology_sha256="d" * 64,
                layout_sha256="e" * 64,
                passed=True,
            )
            for case_id in case_ids
        ),
    )
    envelope = sign_runtime_qualification(statement, private_pem)
    signing = envelope["signing"]
    assert isinstance(signing, dict)
    key_id = signing["key_id"]
    assert isinstance(key_id, str)
    (tmp_path / f"{key_id}.pem").write_bytes(public_pem)
    write_policy(tmp_path)
    verified = verify_runtime_qualification(
        envelope,
        trusted_public_key=public_pem,
        now=verified_at or NOW,
        required_case_ids=case_ids,
    )
    plan = qualify_compilation_plan(
        design(),
        profile,
        verified,
        required_case_ids=case_ids,
    )
    return plan, profile, envelope, key_id


def test_policy_round_trip_current_and_digest(tmp_path: Path) -> None:
    document = write_policy(
        tmp_path,
        revoked_profile_ids=["profile-b", "profile-a"],
    )
    policy = RuntimeRevocationPolicy.from_dict(document)
    assert policy.revoked_profile_ids == ("profile-a", "profile-b")
    assert RuntimeRevocationPolicy.from_dict(policy.to_dict()) == policy
    assert len(policy.digest()) == 64
    assert policy.assert_current(NOW) == NOW
    verified, checkpoint = load_trusted_runtime_revocation_policy(tmp_path, now=NOW)
    assert verified.policy == policy
    assert verified.sequence == 1
    assert checkpoint.accepted_policy_evidence_sha256 == verified.evidence_sha256


def test_fresh_authorization_is_deterministic_and_bounded(tmp_path: Path) -> None:
    plan, profile, envelope, _ = context(tmp_path)
    first = authorize_runtime_execution(
        plan,
        profile,
        envelope,
        trusted_key_dir=tmp_path,
        now=NOW,
    )
    second = authorize_runtime_execution(
        plan,
        profile,
        envelope,
        trusted_key_dir=tmp_path,
        now=NOW,
    )
    assert first == second
    assert first.digest() == second.digest()
    assert first.qualified_plan_sha256 == plan.digest()
    assert first.qualification_evidence_sha256 == plan.qualification_evidence_sha256
    assert first.profile_sha256 == profile.digest()
    assert first.authorized_at == NOW
    assert first.expires_at == NOW + timedelta(hours=2)
    assert first.required_case_ids == (CASE_ID,)
    assert len(first.revocation_policy_sha256) == 64
    assert len(first.revocation_policy_signing_key_id) == 32
    assert first.revocation_policy_sequence == 1
    assert len(first.revocation_checkpoint_sha256) == 64


def test_previously_verified_qualification_cannot_execute_after_expiry(
    tmp_path: Path,
) -> None:
    plan, profile, envelope, _ = context(
        tmp_path,
        issued_at=NOW - timedelta(hours=2),
        expires_at=NOW - timedelta(minutes=1),
        verified_at=NOW - timedelta(hours=1),
    )
    with pytest.raises(ValueError, match="expired"):
        authorize_runtime_execution(
            plan,
            profile,
            envelope,
            trusted_key_dir=tmp_path,
            now=NOW,
        )


def test_future_qualification_is_rejected_at_execution(tmp_path: Path) -> None:
    future = NOW + timedelta(hours=1)
    plan, profile, envelope, _ = context(
        tmp_path,
        issued_at=future,
        expires_at=future + timedelta(hours=2),
        verified_at=future,
    )
    with pytest.raises(ValueError, match="not valid yet"):
        authorize_runtime_execution(
            plan,
            profile,
            envelope,
            trusted_key_dir=tmp_path,
            now=NOW,
        )


def test_missing_current_key_or_signed_policy_fails_closed(tmp_path: Path) -> None:
    plan, profile, envelope, key_id = context(tmp_path)
    (tmp_path / f"{key_id}.pem").unlink()
    with pytest.raises(FileNotFoundError, match="key is unavailable"):
        authorize_runtime_execution(
            plan,
            profile,
            envelope,
            trusted_key_dir=tmp_path,
            now=NOW,
        )

    plan, profile, envelope, _ = context(tmp_path)
    (tmp_path / SIGNED_POLICY_FILENAME).unlink()
    with pytest.raises(FileNotFoundError, match="signed revocation policy is unavailable"):
        authorize_runtime_execution(
            plan,
            profile,
            envelope,
            trusted_key_dir=tmp_path,
            now=NOW,
        )


def test_future_and_expired_signed_policies_fail_closed(tmp_path: Path) -> None:
    plan, profile, envelope, _ = context(tmp_path)
    write_policy(
        tmp_path,
        issued_at=NOW + timedelta(minutes=1),
        expires_at=NOW + timedelta(hours=1),
    )
    with pytest.raises(ValueError, match="not valid yet"):
        authorize_runtime_execution(
            plan,
            profile,
            envelope,
            trusted_key_dir=tmp_path,
            now=NOW,
        )

    write_policy(
        tmp_path,
        issued_at=NOW - timedelta(hours=2),
        expires_at=NOW - timedelta(minutes=1),
    )
    with pytest.raises(ValueError, match="policy has expired"):
        authorize_runtime_execution(
            plan,
            profile,
            envelope,
            trusted_key_dir=tmp_path,
            now=NOW,
        )


@pytest.mark.parametrize(
    ("field", "value_name", "message"),
    [
        ("revoked_signing_key_ids", "key_id", "signing key is revoked"),
        (
            "revoked_qualification_evidence_sha256",
            "evidence",
            "evidence is revoked",
        ),
        ("revoked_profile_ids", "profile_id", "profile ID is revoked"),
        ("revoked_profile_sha256", "profile_hash", "profile hash is revoked"),
        ("revoked_adapter_code_sha256", "adapter", "adapter code is revoked"),
        (
            "revoked_runtime_identity_sha256",
            "runtime",
            "runtime identity is revoked",
        ),
    ],
)
def test_each_revocation_dimension_blocks_execution(
    tmp_path: Path,
    field: str,
    value_name: str,
    message: str,
) -> None:
    plan, profile, envelope, key_id = context(tmp_path)
    values = {
        "key_id": key_id,
        "evidence": plan.qualification_evidence_sha256,
        "profile_id": profile.profile_id,
        "profile_hash": profile.digest(),
        "adapter": plan.adapter_code_sha256,
        "runtime": plan.runtime_identity_sha256,
    }
    write_policy(tmp_path, **{field: [values[value_name]]})
    with pytest.raises(PermissionError, match=message):
        authorize_runtime_execution(
            plan,
            profile,
            envelope,
            trusted_key_dir=tmp_path,
            now=NOW,
        )


def test_profile_revocation_or_substitution_fails_closed(tmp_path: Path) -> None:
    plan, profile, envelope, _ = context(tmp_path)
    with pytest.raises(PermissionError, match="profile is revoked"):
        authorize_runtime_execution(
            plan,
            replace(profile, qualification="REVOKED"),
            envelope,
            trusted_key_dir=tmp_path,
            now=NOW,
        )
    with pytest.raises(ValueError, match="current profile"):
        authorize_runtime_execution(
            plan,
            replace(profile, adapter_contract="changed-contract"),
            envelope,
            trusted_key_dir=tmp_path,
            now=NOW,
        )


def test_additional_required_case_is_checked_fresh(tmp_path: Path) -> None:
    plan, profile, envelope, _ = context(tmp_path)
    with pytest.raises(ValueError, match="required Golden Cases"):
        authorize_runtime_execution(
            plan,
            profile,
            envelope,
            trusted_key_dir=tmp_path,
            now=NOW,
            additional_required_case_ids=("NEW_CASE",),
        )


def test_different_valid_envelope_cannot_replace_plan_qualification(
    tmp_path: Path,
) -> None:
    plan, profile, _, _ = context(tmp_path)
    _, _, second_envelope, _ = context(tmp_path)
    with pytest.raises(ValueError, match="does not match"):
        authorize_runtime_execution(
            plan,
            profile,
            second_envelope,
            trusted_key_dir=tmp_path,
            now=NOW,
        )


def test_policy_parser_is_exact_bounded_and_timezone_safe(tmp_path: Path) -> None:
    document = write_policy(tmp_path)
    forged = dict(document)
    forged["unexpected"] = True
    with pytest.raises(ValueError, match="exactly"):
        RuntimeRevocationPolicy.from_dict(forged)

    forged = dict(document)
    forged["revoked_profile_ids"] = ["duplicate", "duplicate"]
    with pytest.raises(ValueError, match="unique"):
        RuntimeRevocationPolicy.from_dict(forged)

    forged = dict(document)
    forged["expires_at"] = forged["issued_at"]
    with pytest.raises(ValueError, match="after issued_at"):
        RuntimeRevocationPolicy.from_dict(forged)

    policy = RuntimeRevocationPolicy.from_dict(document)
    with pytest.raises(ValueError, match="timezone"):
        policy.assert_current(datetime(2026, 8, 2, 12, 0))

    with pytest.raises(ValueError, match="absolute"):
        load_trusted_runtime_revocation_policy(Path("relative"), now=NOW)


def test_unsigned_legacy_policy_is_not_accepted(tmp_path: Path) -> None:
    plan, profile, envelope, _ = context(tmp_path)
    policy = RuntimeRevocationPolicy.from_dict(write_policy(tmp_path))
    (tmp_path / SIGNED_POLICY_FILENAME).unlink()
    (tmp_path / "revocations.json").write_text(
        json.dumps(policy.to_dict()),
        encoding="utf-8",
    )
    with pytest.raises(FileNotFoundError, match="signed revocation policy"):
        authorize_runtime_execution(
            plan,
            profile,
            envelope,
            trusted_key_dir=tmp_path,
            now=NOW,
        )
