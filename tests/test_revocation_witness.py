from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from aspenops_nexus.revocation_witness import (
    MAX_WITNESS_VALIDITY,
    WITNESS_AUTHORITY_DIRECTORY,
    WITNESS_RECEIPT_FILENAME,
    RevocationWitnessStatement,
    load_trusted_revocation_witness,
    sign_revocation_witness,
    verify_revocation_witness,
)
from aspenops_nexus.runtime_execution_authorization import RuntimeRevocationPolicy
from aspenops_nexus.signed_revocation_policy import (
    SignedRevocationPolicyStatement,
    advance_revocation_policy_checkpoint,
    sign_revocation_policy,
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


def policy_context():
    private_pem, public_pem = keys()
    policy = RuntimeRevocationPolicy(
        policy_id="policy-001",
        issued_at=NOW - timedelta(hours=1),
        expires_at=NOW + timedelta(days=1),
        revoked_signing_key_ids=(),
        revoked_qualification_evidence_sha256=(),
        revoked_profile_ids=(),
        revoked_profile_sha256=(),
        revoked_adapter_code_sha256=(),
        revoked_runtime_identity_sha256=(),
    )
    envelope = sign_revocation_policy(
        SignedRevocationPolicyStatement(
            sequence=1,
            previous_policy_sha256=None,
            policy=policy,
        ),
        private_pem,
    )
    verified = verify_revocation_policy(
        envelope,
        trusted_public_key=public_pem,
        now=NOW,
    )
    return verified, advance_revocation_policy_checkpoint(verified), private_pem


def witness_statement(policy, checkpoint, **changes: Any) -> RevocationWitnessStatement:
    values: dict[str, Any] = {
        "witness_id": "witness-001",
        "policy_sequence": policy.sequence,
        "policy_evidence_sha256": policy.evidence_sha256,
        "policy_signing_key_id": policy.signing_key_id,
        "checkpoint_sha256": checkpoint.digest(),
        "observed_at": NOW - timedelta(minutes=5),
        "expires_at": NOW + timedelta(hours=1),
    }
    values.update(changes)
    return RevocationWitnessStatement(**values)


def verified_witness():
    policy, checkpoint, _ = policy_context()
    private_pem, public_pem = keys()
    statement = witness_statement(policy, checkpoint)
    envelope = sign_revocation_witness(statement, private_pem)
    verified = verify_revocation_witness(
        envelope,
        trusted_public_key=public_pem,
        now=NOW,
    )
    return policy, checkpoint, verified, envelope, private_pem, public_pem


def install(
    root: Path,
    envelope: dict[str, Any],
    public_pem: bytes,
) -> None:
    signing = envelope["signing"]
    assert isinstance(signing, dict)
    key_id = signing["key_id"]
    assert isinstance(key_id, str)
    directory = root / WITNESS_AUTHORITY_DIRECTORY
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{key_id}.pem").write_bytes(public_pem)
    (root / WITNESS_RECEIPT_FILENAME).write_text(
        json.dumps(envelope, sort_keys=True),
        encoding="utf-8",
    )


def test_sign_verify_round_trip_and_current_match() -> None:
    policy, checkpoint, item, envelope, _, public_pem = verified_witness()
    second = verify_revocation_witness(
        envelope,
        trusted_public_key=public_pem,
        now=NOW,
    )
    assert item == second
    assert RevocationWitnessStatement.from_dict(item.statement.to_dict()) == item.statement
    assert len(item.evidence_sha256) == 64
    assert item.assert_current(NOW) == NOW
    item.assert_matches(policy, checkpoint)


def test_tamper_and_wrong_witness_key_fail_closed() -> None:
    _, _, _, envelope, _, public_pem = verified_witness()
    tampered = json.loads(json.dumps(envelope))
    tampered["statement"]["witness_id"] = "tampered"
    with pytest.raises(ValueError, match="signature is invalid"):
        verify_revocation_witness(
            tampered,
            trusted_public_key=public_pem,
            now=NOW,
        )

    _, wrong_public = keys()
    with pytest.raises(ValueError, match="fingerprint"):
        verify_revocation_witness(
            envelope,
            trusted_public_key=wrong_public,
            now=NOW,
        )


def test_future_expired_and_excessive_validity_fail_closed() -> None:
    policy, checkpoint, _, _, private_pem, public_pem = verified_witness()
    future = witness_statement(
        policy,
        checkpoint,
        observed_at=NOW + timedelta(minutes=1),
        expires_at=NOW + timedelta(hours=1),
    )
    with pytest.raises(ValueError, match="not valid yet"):
        verify_revocation_witness(
            sign_revocation_witness(future, private_pem),
            trusted_public_key=public_pem,
            now=NOW,
        )

    expired = witness_statement(
        policy,
        checkpoint,
        observed_at=NOW - timedelta(hours=2),
        expires_at=NOW - timedelta(minutes=1),
    )
    with pytest.raises(ValueError, match="expired"):
        verify_revocation_witness(
            sign_revocation_witness(expired, private_pem),
            trusted_public_key=public_pem,
            now=NOW,
        )

    document = witness_statement(policy, checkpoint).to_dict()
    document["expires_at"] = (
        NOW - timedelta(minutes=5) + MAX_WITNESS_VALIDITY + timedelta(seconds=1)
    ).isoformat()
    with pytest.raises(ValueError, match="24-hour"):
        RevocationWitnessStatement.from_dict(document)


def test_policy_and_checkpoint_mismatch_fail_closed() -> None:
    policy, checkpoint, item, _, _, _ = verified_witness()
    changed_policy = replace(
        policy,
        statement=replace(policy.statement, sequence=2),
    )
    with pytest.raises(ValueError, match="policy_sequence"):
        item.assert_matches(changed_policy, checkpoint)

    changed_checkpoint = replace(
        checkpoint,
        accepted_policy_evidence_sha256="f" * 64,
    )
    with pytest.raises(ValueError, match="checkpoint_sha256"):
        item.assert_matches(policy, changed_checkpoint)


def test_trusted_loader_and_missing_inputs(tmp_path: Path) -> None:
    policy, checkpoint, item, envelope, _, public_pem = verified_witness()
    install(tmp_path, envelope, public_pem)
    assert load_trusted_revocation_witness(
        tmp_path,
        policy,
        checkpoint,
        now=NOW,
    ) == item

    (tmp_path / WITNESS_RECEIPT_FILENAME).unlink()
    with pytest.raises(FileNotFoundError, match="receipt is unavailable"):
        load_trusted_revocation_witness(
            tmp_path,
            policy,
            checkpoint,
            now=NOW,
        )

    install(tmp_path, envelope, public_pem)
    directory = tmp_path / WITNESS_AUTHORITY_DIRECTORY
    for path in directory.iterdir():
        path.unlink()
    with pytest.raises(FileNotFoundError, match="witness is unavailable"):
        load_trusted_revocation_witness(
            tmp_path,
            policy,
            checkpoint,
            now=NOW,
        )


def test_witness_must_be_independent_of_policy_authority(tmp_path: Path) -> None:
    policy, checkpoint, policy_private = policy_context()
    from cryptography.hazmat.primitives import serialization

    private = serialization.load_pem_private_key(policy_private, password=None)
    public_pem = private.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    envelope = sign_revocation_witness(
        witness_statement(policy, checkpoint),
        policy_private,
    )
    install(tmp_path, envelope, public_pem)
    with pytest.raises(PermissionError, match="independent"):
        load_trusted_revocation_witness(
            tmp_path,
            policy,
            checkpoint,
            now=NOW,
        )


def test_old_coordinated_state_is_blocked_after_witness_expiry(tmp_path: Path) -> None:
    policy, checkpoint, _, _, private_pem, public_pem = verified_witness()
    old_statement = witness_statement(
        policy,
        checkpoint,
        observed_at=NOW - timedelta(hours=2),
        expires_at=NOW - timedelta(minutes=1),
    )
    install(
        tmp_path,
        sign_revocation_witness(old_statement, private_pem),
        public_pem,
    )
    with pytest.raises(ValueError, match="expired"):
        load_trusted_revocation_witness(
            tmp_path,
            policy,
            checkpoint,
            now=NOW,
        )


def test_statement_parser_is_exact_and_timezone_safe() -> None:
    policy, checkpoint, _, _, _, _ = verified_witness()
    document = witness_statement(policy, checkpoint).to_dict()
    forged = dict(document)
    forged["unexpected"] = True
    with pytest.raises(ValueError, match="exactly"):
        RevocationWitnessStatement.from_dict(forged)

    forged = dict(document)
    forged["policy_sequence"] = 0
    with pytest.raises(ValueError, match="positive"):
        RevocationWitnessStatement.from_dict(forged)

    forged = dict(document)
    forged["expires_at"] = forged["observed_at"]
    with pytest.raises(ValueError, match="after observed_at"):
        RevocationWitnessStatement.from_dict(forged)

    item = RevocationWitnessStatement.from_dict(document)
    verified = replace(
        verified_witness()[2],
        statement=item,
    )
    with pytest.raises(ValueError, match="timezone"):
        verified.assert_current(datetime(2026, 8, 2, 12, 0))

    with pytest.raises(ValueError, match="absolute"):
        load_trusted_revocation_witness(
            Path("relative"),
            policy,
            checkpoint,
            now=NOW,
        )
