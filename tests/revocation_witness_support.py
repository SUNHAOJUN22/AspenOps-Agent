from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from aspenops_nexus.revocation_witness import (
    WITNESS_AUTHORITY_DIRECTORY,
    WITNESS_RECEIPT_FILENAME,
    RevocationWitnessStatement,
    sign_revocation_witness,
)
from aspenops_nexus.signed_revocation_policy import (
    RevocationPolicyCheckpoint,
    VerifiedSignedRevocationPolicy,
)


def install_revocation_witness(
    root: Path,
    policy: VerifiedSignedRevocationPolicy,
    checkpoint: RevocationPolicyCheckpoint,
    *,
    now: datetime,
    witness_id: str = "test-witness",
    observed_at: datetime | None = None,
    expires_at: datetime | None = None,
) -> dict[str, object]:
    pytest.importorskip("cryptography")
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

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
    statement = RevocationWitnessStatement(
        witness_id=witness_id,
        policy_sequence=policy.sequence,
        policy_evidence_sha256=policy.evidence_sha256,
        policy_signing_key_id=policy.signing_key_id,
        checkpoint_sha256=checkpoint.digest(),
        observed_at=observed_at or now - timedelta(minutes=5),
        expires_at=expires_at or now + timedelta(hours=1),
    )
    envelope = sign_revocation_witness(statement, private_pem)
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
    return envelope
