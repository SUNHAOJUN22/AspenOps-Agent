from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from aspenops_nexus.runtime_execution_authorization import RuntimeRevocationPolicy
from aspenops_nexus.signed_revocation_policy import (
    REVOCATION_AUTHORITY_DIRECTORY,
    REVOCATION_CHECKPOINT_FILENAME,
    SIGNED_POLICY_FILENAME,
    RevocationPolicyCheckpoint,
    SignedRevocationPolicyStatement,
    advance_revocation_policy_checkpoint,
    load_trusted_signed_revocation_policy,
    sign_revocation_policy,
    validate_revocation_policy_checkpoint,
    verify_revocation_policy,
)

NOW = datetime(2026, 8, 2, 12, 0, tzinfo=UTC)


def keys() -> tuple[bytes, bytes]:
    pytest.importorskip("cryptography")
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    private = Ed25519PrivateKey.generate()
    return (
        private.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ),
        private.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ),
    )


def policy(*, policy_id: str = "policy-001") -> RuntimeRevocationPolicy:
    return RuntimeRevocationPolicy(
        policy_id=policy_id,
        issued_at=NOW - timedelta(hours=1),
        expires_at=NOW + timedelta(days=1),
        revoked_signing_key_ids=(),
        revoked_qualification_evidence_sha256=(),
        revoked_profile_ids=(),
        revoked_profile_sha256=(),
        revoked_adapter_code_sha256=(),
        revoked_runtime_identity_sha256=(),
    )


def verified(
    *,
    sequence: int = 1,
    previous: str | None = None,
    policy_id: str = "policy-001",
    private_pem: bytes | None = None,
    public_pem: bytes | None = None,
):
    if private_pem is None or public_pem is None:
        private_pem, public_pem = keys()
    statement = SignedRevocationPolicyStatement(
        sequence=sequence,
        previous_policy_sha256=previous,
        policy=policy(policy_id=policy_id),
    )
    envelope = sign_revocation_policy(statement, private_pem)
    return (
        verify_revocation_policy(
            envelope,
            trusted_public_key=public_pem,
            now=NOW,
        ),
        envelope,
        private_pem,
        public_pem,
    )


def install(
    root: Path,
    envelope: dict[str, Any],
    public_pem: bytes,
    checkpoint: RevocationPolicyCheckpoint,
) -> None:
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


def test_sign_verify_and_strict_round_trip() -> None:
    item, envelope, _, public_pem = verified()
    second = verify_revocation_policy(
        envelope,
        trusted_public_key=public_pem,
        now=NOW,
    )
    assert item == second
    assert item.sequence == 1
    assert item.policy.policy_id == "policy-001"
    assert len(item.evidence_sha256) == 64
    assert SignedRevocationPolicyStatement.from_dict(item.statement.to_dict()) == item.statement


def test_signature_tamper_and_wrong_authority_fail_closed() -> None:
    _, envelope, _, public_pem = verified()
    tampered = json.loads(json.dumps(envelope))
    tampered["statement"]["policy"]["policy_id"] = "tampered"
    with pytest.raises(ValueError, match="signature is invalid"):
        verify_revocation_policy(
            tampered,
            trusted_public_key=public_pem,
            now=NOW,
        )

    _, wrong_public = keys()
    with pytest.raises(ValueError, match="fingerprint"):
        verify_revocation_policy(
            envelope,
            trusted_public_key=wrong_public,
            now=NOW,
        )


def test_statement_sequence_and_predecessor_contracts() -> None:
    document = SignedRevocationPolicyStatement(
        sequence=1,
        previous_policy_sha256=None,
        policy=policy(),
    ).to_dict()
    forged = dict(document)
    forged["previous_policy_sha256"] = "a" * 64
    with pytest.raises(ValueError, match="first.*predecessor"):
        SignedRevocationPolicyStatement.from_dict(forged)

    forged = dict(document)
    forged["sequence"] = 2
    with pytest.raises(ValueError, match="requires a predecessor"):
        SignedRevocationPolicyStatement.from_dict(forged)

    forged = dict(document)
    forged["sequence"] = True
    with pytest.raises(ValueError, match="positive integer"):
        SignedRevocationPolicyStatement.from_dict(forged)


def test_initial_checkpoint_and_current_policy() -> None:
    item, _, _, _ = verified()
    checkpoint = advance_revocation_policy_checkpoint(item)
    validate_revocation_policy_checkpoint(item, checkpoint)
    assert checkpoint.accepted_sequence == 1
    assert checkpoint.accepted_policy_evidence_sha256 == item.evidence_sha256
    assert RevocationPolicyCheckpoint.from_dict(checkpoint.to_dict()) == checkpoint
    assert len(checkpoint.digest()) == 64


def test_next_policy_extends_checkpoint_and_can_advance() -> None:
    first, _, private_pem, public_pem = verified()
    checkpoint = advance_revocation_policy_checkpoint(first)
    second, _, _, _ = verified(
        sequence=2,
        previous=first.evidence_sha256,
        policy_id="policy-002",
        private_pem=private_pem,
        public_pem=public_pem,
    )
    validate_revocation_policy_checkpoint(second, checkpoint)
    advanced = advance_revocation_policy_checkpoint(second, checkpoint)
    assert advanced.accepted_sequence == 2
    assert advanced.accepted_policy_evidence_sha256 == second.evidence_sha256


def test_rollback_same_sequence_replacement_and_skip_fail_closed() -> None:
    first, _, private_pem, public_pem = verified()
    checkpoint = advance_revocation_policy_checkpoint(first)

    replacement, _, _, _ = verified(
        sequence=1,
        policy_id="replacement",
        private_pem=private_pem,
        public_pem=public_pem,
    )
    with pytest.raises(PermissionError, match="changed at the accepted sequence"):
        validate_revocation_policy_checkpoint(replacement, checkpoint)

    old_checkpoint = RevocationPolicyCheckpoint(
        accepted_sequence=2,
        accepted_policy_evidence_sha256="a" * 64,
        accepted_signing_key_id=first.signing_key_id,
    )
    with pytest.raises(PermissionError, match="rollback"):
        validate_revocation_policy_checkpoint(first, old_checkpoint)

    skipped, _, _, _ = verified(
        sequence=3,
        previous=first.evidence_sha256,
        private_pem=private_pem,
        public_pem=public_pem,
    )
    with pytest.raises(PermissionError, match="sequence skipped"):
        validate_revocation_policy_checkpoint(skipped, checkpoint)


def test_wrong_chain_and_authority_change_at_same_sequence_fail_closed() -> None:
    first, _, _, _ = verified()
    checkpoint = advance_revocation_policy_checkpoint(first)
    next_policy, _, _, _ = verified(
        sequence=2,
        previous="f" * 64,
    )
    with pytest.raises(PermissionError, match="does not extend"):
        validate_revocation_policy_checkpoint(next_policy, checkpoint)

    other, _, _, _ = verified(sequence=1)
    forged_checkpoint = RevocationPolicyCheckpoint(
        accepted_sequence=1,
        accepted_policy_evidence_sha256=other.evidence_sha256,
        accepted_signing_key_id=first.signing_key_id,
    )
    with pytest.raises(PermissionError, match="authority changed"):
        validate_revocation_policy_checkpoint(other, forged_checkpoint)


def test_trusted_loader_requires_policy_checkpoint_and_separate_authority(
    tmp_path: Path,
) -> None:
    item, envelope, _, public_pem = verified()
    checkpoint = advance_revocation_policy_checkpoint(item)
    install(tmp_path, envelope, public_pem, checkpoint)
    loaded, loaded_checkpoint = load_trusted_signed_revocation_policy(
        tmp_path,
        now=NOW,
    )
    assert loaded == item
    assert loaded_checkpoint == checkpoint

    (tmp_path / REVOCATION_CHECKPOINT_FILENAME).unlink()
    with pytest.raises(FileNotFoundError, match="checkpoint is unavailable"):
        load_trusted_signed_revocation_policy(tmp_path, now=NOW)


def test_loader_rejects_missing_authority_and_relative_root(tmp_path: Path) -> None:
    item, envelope, _, public_pem = verified()
    checkpoint = advance_revocation_policy_checkpoint(item)
    install(tmp_path, envelope, public_pem, checkpoint)
    authority = tmp_path / REVOCATION_AUTHORITY_DIRECTORY
    for path in authority.iterdir():
        path.unlink()
    with pytest.raises(FileNotFoundError, match="authority is unavailable"):
        load_trusted_signed_revocation_policy(tmp_path, now=NOW)

    with pytest.raises(ValueError, match="absolute"):
        load_trusted_signed_revocation_policy(Path("relative"), now=NOW)


def test_checkpoint_parser_rejects_unknown_fields_and_bad_values() -> None:
    item, _, _, _ = verified()
    document = advance_revocation_policy_checkpoint(item).to_dict()
    forged = dict(document)
    forged["unexpected"] = True
    with pytest.raises(ValueError, match="exactly"):
        RevocationPolicyCheckpoint.from_dict(forged)

    forged = dict(document)
    forged["accepted_sequence"] = 0
    with pytest.raises(ValueError, match="positive integer"):
        RevocationPolicyCheckpoint.from_dict(forged)

    with pytest.raises(ValueError, match="initial.*sequence 1"):
        advance_revocation_policy_checkpoint(verified(sequence=2, previous="a" * 64)[0])
