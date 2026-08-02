from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from .runtime_qualification import (
    KeySource,
    _canonical_bytes,
    _digest,
    _key_id,
    _load_private_key,
    _load_public_key,
    _parse_time,
    _public_key_id,
    _sha256_bytes,
    _strict_json,
    _text,
    _time_text,
)
from .signed_revocation_policy import (
    RevocationPolicyCheckpoint,
    VerifiedSignedRevocationPolicy,
)

WITNESS_STATEMENT_SCHEMA = "aspenops.revocation-witness-statement/v1"
WITNESS_ENVELOPE_SCHEMA = "aspenops.revocation-witness-receipt/v1"
WITNESS_RECEIPT_FILENAME = "revocation-witness.signed.json"
WITNESS_AUTHORITY_DIRECTORY = "revocation-witnesses"
MAX_WITNESS_VALIDITY = timedelta(hours=24)


def _current_time(now: datetime | None) -> datetime:
    current = now or datetime.now(UTC)
    if current.tzinfo is None or current.utcoffset() is None:
        raise ValueError("revocation witness verification time must include a timezone")
    return current.astimezone(UTC)


def _load_object(source: str | Path | bytes | dict[str, Any]) -> dict[str, Any]:
    if isinstance(source, dict):
        return dict(source)
    if isinstance(source, bytes):
        value = _strict_json(source)
    else:
        value = _strict_json(Path(source).expanduser().read_bytes())
    if not isinstance(value, dict):
        raise ValueError("revocation witness envelope root must be an object")
    return value


@dataclass(frozen=True, slots=True)
class RevocationWitnessStatement:
    witness_id: str
    policy_sequence: int
    policy_evidence_sha256: str
    policy_signing_key_id: str
    checkpoint_sha256: str
    observed_at: datetime
    expires_at: datetime
    schema: str = WITNESS_STATEMENT_SCHEMA

    @classmethod
    def from_dict(cls, value: Any) -> RevocationWitnessStatement:
        if not isinstance(value, dict):
            raise ValueError("revocation witness statement must be an object")
        required = {
            "schema",
            "witness_id",
            "policy_sequence",
            "policy_evidence_sha256",
            "policy_signing_key_id",
            "checkpoint_sha256",
            "observed_at",
            "expires_at",
        }
        if set(value) != required:
            raise ValueError(
                "revocation witness statement must contain exactly " + str(sorted(required))
            )
        schema = _text(value.get("schema"), "revocation witness statement.schema")
        if schema != WITNESS_STATEMENT_SCHEMA:
            raise ValueError(f"unsupported revocation witness statement schema: {schema}")
        sequence = value.get("policy_sequence")
        if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 1:
            raise ValueError("revocation witness policy_sequence must be positive")
        observed_at = _parse_time(
            value.get("observed_at"),
            "revocation witness statement.observed_at",
        )
        expires_at = _parse_time(
            value.get("expires_at"),
            "revocation witness statement.expires_at",
        )
        if expires_at <= observed_at:
            raise ValueError("revocation witness expires_at must be after observed_at")
        if expires_at - observed_at > MAX_WITNESS_VALIDITY:
            raise ValueError("revocation witness validity exceeds the 24-hour limit")
        return cls(
            witness_id=_text(value.get("witness_id"), "revocation witness witness_id"),
            policy_sequence=sequence,
            policy_evidence_sha256=_digest(
                value.get("policy_evidence_sha256"),
                "revocation witness policy_evidence_sha256",
            ),
            policy_signing_key_id=_key_id(
                value.get("policy_signing_key_id"),
                "revocation witness policy_signing_key_id",
            ),
            checkpoint_sha256=_digest(
                value.get("checkpoint_sha256"),
                "revocation witness checkpoint_sha256",
            ),
            observed_at=observed_at,
            expires_at=expires_at,
            schema=schema,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "witness_id": self.witness_id,
            "policy_sequence": self.policy_sequence,
            "policy_evidence_sha256": self.policy_evidence_sha256,
            "policy_signing_key_id": self.policy_signing_key_id,
            "checkpoint_sha256": self.checkpoint_sha256,
            "observed_at": _time_text(self.observed_at),
            "expires_at": _time_text(self.expires_at),
        }

    def digest(self) -> str:
        return _sha256_bytes(_canonical_bytes(self.to_dict()))


@dataclass(frozen=True, slots=True)
class VerifiedRevocationWitness:
    statement: RevocationWitnessStatement
    signing_key_id: str
    evidence_sha256: str

    def assert_current(self, now: datetime | None = None) -> datetime:
        current = _current_time(now)
        if current < self.statement.observed_at:
            raise ValueError("revocation witness receipt is not valid yet")
        if current >= self.statement.expires_at:
            raise ValueError("revocation witness receipt has expired")
        return current

    def assert_matches(
        self,
        policy: VerifiedSignedRevocationPolicy,
        checkpoint: RevocationPolicyCheckpoint,
    ) -> None:
        mismatches: list[str] = []
        if self.statement.policy_sequence != policy.sequence:
            mismatches.append("policy_sequence")
        if self.statement.policy_evidence_sha256 != policy.evidence_sha256:
            mismatches.append("policy_evidence_sha256")
        if self.statement.policy_signing_key_id != policy.signing_key_id:
            mismatches.append("policy_signing_key_id")
        if self.statement.checkpoint_sha256 != checkpoint.digest():
            mismatches.append("checkpoint_sha256")
        if mismatches:
            raise ValueError(
                "revocation witness receipt does not match current trust state: "
                + ", ".join(mismatches)
            )

    def digest(self) -> str:
        return self.evidence_sha256


def sign_revocation_witness(
    statement: RevocationWitnessStatement,
    private_key: KeySource,
) -> dict[str, Any]:
    key = _load_private_key(private_key)
    key_id = _public_key_id(key.public_key())
    statement_dict = RevocationWitnessStatement.from_dict(statement.to_dict()).to_dict()
    signature = base64.b64encode(key.sign(_canonical_bytes(statement_dict))).decode("ascii")
    return {
        "schema": WITNESS_ENVELOPE_SCHEMA,
        "statement": statement_dict,
        "signing": {"algorithm": "Ed25519", "key_id": key_id},
        "signature": signature,
    }


def verify_revocation_witness(
    source: str | Path | bytes | dict[str, Any],
    *,
    trusted_public_key: KeySource,
    now: datetime | None = None,
) -> VerifiedRevocationWitness:
    envelope = _load_object(source)
    required = {"schema", "statement", "signing", "signature"}
    if set(envelope) != required:
        raise ValueError(
            "revocation witness envelope must contain exactly " + str(sorted(required))
        )
    schema = _text(envelope.get("schema"), "revocation witness envelope.schema")
    if schema != WITNESS_ENVELOPE_SCHEMA:
        raise ValueError(f"unsupported revocation witness envelope schema: {schema}")
    signing = envelope.get("signing")
    if not isinstance(signing, dict) or set(signing) != {"algorithm", "key_id"}:
        raise ValueError("revocation witness signing metadata is invalid")
    if signing.get("algorithm") != "Ed25519":
        raise ValueError("revocation witness algorithm must be Ed25519")
    key_id = _key_id(signing.get("key_id"), "revocation witness signing.key_id")
    signature_text = _text(envelope.get("signature"), "revocation witness signature")
    statement = RevocationWitnessStatement.from_dict(envelope.get("statement"))
    public_key = _load_public_key(trusted_public_key)
    if _public_key_id(public_key) != key_id:
        raise ValueError("trusted witness fingerprint does not match the receipt key ID")
    try:
        from cryptography.exceptions import InvalidSignature
    except ImportError as exc:
        raise RuntimeError("Install the 'signing' extra to verify witness receipts") from exc
    try:
        signature = base64.b64decode(signature_text, validate=True)
        public_key.verify(signature, _canonical_bytes(statement.to_dict()))
    except (InvalidSignature, ValueError) as exc:
        raise ValueError("revocation witness signature is invalid") from exc
    verified = VerifiedRevocationWitness(
        statement=statement,
        signing_key_id=key_id,
        evidence_sha256=_sha256_bytes(_canonical_bytes(envelope)),
    )
    verified.assert_current(now)
    return verified


def load_trusted_revocation_witness(
    trusted_key_dir: str | Path,
    policy: VerifiedSignedRevocationPolicy,
    checkpoint: RevocationPolicyCheckpoint,
    *,
    now: datetime | None = None,
) -> VerifiedRevocationWitness:
    root = Path(trusted_key_dir).expanduser()
    if not root.is_absolute():
        raise ValueError("revocation witness trusted directory must be absolute")
    resolved_root = root.resolve()
    receipt_path = (resolved_root / WITNESS_RECEIPT_FILENAME).resolve()
    try:
        receipt_path.relative_to(resolved_root)
    except ValueError as exc:
        raise PermissionError("revocation witness receipt escaped the trust root") from exc
    if not receipt_path.is_file():
        raise FileNotFoundError("revocation witness receipt is unavailable")
    envelope = _load_object(receipt_path)
    signing = envelope.get("signing")
    if not isinstance(signing, dict):
        raise ValueError("revocation witness signing metadata is invalid")
    key_id = _key_id(signing.get("key_id"), "revocation witness signing.key_id")
    if key_id == policy.signing_key_id:
        raise PermissionError(
            "revocation witness authority must be independent of the policy authority"
        )
    witness_root = (resolved_root / WITNESS_AUTHORITY_DIRECTORY).resolve()
    try:
        witness_root.relative_to(resolved_root)
    except ValueError as exc:
        raise PermissionError("revocation witness directory escaped the trust root") from exc
    public_key = (witness_root / f"{key_id}.pem").resolve()
    try:
        public_key.relative_to(witness_root)
    except ValueError as exc:
        raise PermissionError("revocation witness key escaped its authority directory") from exc
    if not public_key.is_file():
        raise FileNotFoundError(f"trusted revocation witness is unavailable for key_id={key_id}")
    verified = verify_revocation_witness(
        envelope,
        trusted_public_key=public_key,
        now=now,
    )
    verified.assert_matches(policy, checkpoint)
    return verified
