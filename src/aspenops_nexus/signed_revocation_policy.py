from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .runtime_execution_authorization import RuntimeRevocationPolicy
from .runtime_qualification import (
    KeySource,
    _canonical_bytes,
    _digest,
    _key_id,
    _load_private_key,
    _load_public_key,
    _public_key_id,
    _sha256_bytes,
    _strict_json,
    _text,
)
from .simulator_capabilities import SimulatorCapabilityProfile

SIGNED_POLICY_STATEMENT_SCHEMA = "aspenops.signed-runtime-revocation-statement/v1"
SIGNED_POLICY_ENVELOPE_SCHEMA = "aspenops.signed-runtime-revocation-policy/v1"
REVOCATION_CHECKPOINT_SCHEMA = "aspenops.runtime-revocation-checkpoint/v1"
SIGNED_POLICY_FILENAME = "revocations.signed.json"
REVOCATION_CHECKPOINT_FILENAME = "revocation-checkpoint.json"
REVOCATION_AUTHORITY_DIRECTORY = "revocation-authorities"


def _sequence(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{label} must be a positive integer")
    return value


def _optional_digest(value: Any, label: str) -> str | None:
    if value is None:
        return None
    return _digest(value, label)


def _load_object(source: str | Path | bytes | dict[str, Any], label: str) -> dict[str, Any]:
    if isinstance(source, dict):
        return dict(source)
    if isinstance(source, bytes):
        value = _strict_json(source)
    else:
        value = _strict_json(Path(source).expanduser().read_bytes())
    if not isinstance(value, dict):
        raise ValueError(f"{label} root must be an object")
    return value


def _current_time(now: datetime | None) -> datetime:
    current = now or datetime.now(UTC)
    if current.tzinfo is None or current.utcoffset() is None:
        raise ValueError("signed revocation-policy verification time must include a timezone")
    return current.astimezone(UTC)


@dataclass(frozen=True, slots=True)
class SignedRevocationPolicyStatement:
    sequence: int
    previous_policy_sha256: str | None
    policy: RuntimeRevocationPolicy
    schema: str = SIGNED_POLICY_STATEMENT_SCHEMA

    @classmethod
    def from_dict(cls, value: Any) -> SignedRevocationPolicyStatement:
        if not isinstance(value, dict):
            raise ValueError("signed revocation-policy statement must be an object")
        required = {"schema", "sequence", "previous_policy_sha256", "policy"}
        if set(value) != required:
            raise ValueError(
                "signed revocation-policy statement must contain exactly "
                + str(sorted(required))
            )
        schema = _text(value.get("schema"), "signed revocation-policy statement.schema")
        if schema != SIGNED_POLICY_STATEMENT_SCHEMA:
            raise ValueError(f"unsupported signed revocation-policy statement schema: {schema}")
        sequence = _sequence(value.get("sequence"), "signed revocation-policy sequence")
        previous = _optional_digest(
            value.get("previous_policy_sha256"),
            "signed revocation-policy previous_policy_sha256",
        )
        if sequence == 1 and previous is not None:
            raise ValueError("first signed revocation policy cannot declare a predecessor")
        if sequence > 1 and previous is None:
            raise ValueError("non-initial signed revocation policy requires a predecessor")
        return cls(
            sequence=sequence,
            previous_policy_sha256=previous,
            policy=RuntimeRevocationPolicy.from_dict(value.get("policy")),
            schema=schema,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "sequence": self.sequence,
            "previous_policy_sha256": self.previous_policy_sha256,
            "policy": self.policy.to_dict(),
        }

    def digest(self) -> str:
        return _sha256_bytes(_canonical_bytes(self.to_dict()))


@dataclass(frozen=True, slots=True)
class VerifiedSignedRevocationPolicy:
    statement: SignedRevocationPolicyStatement
    signing_key_id: str
    evidence_sha256: str

    @property
    def policy(self) -> RuntimeRevocationPolicy:
        return self.statement.policy

    @property
    def sequence(self) -> int:
        return self.statement.sequence

    def assert_allows(
        self,
        qualification: Any,
        profile: SimulatorCapabilityProfile,
    ) -> None:
        self.policy.assert_allows(qualification, profile)

    def digest(self) -> str:
        return self.evidence_sha256


@dataclass(frozen=True, slots=True)
class RevocationPolicyCheckpoint:
    accepted_sequence: int
    accepted_policy_evidence_sha256: str
    accepted_signing_key_id: str
    schema: str = REVOCATION_CHECKPOINT_SCHEMA

    @classmethod
    def from_dict(cls, value: Any) -> RevocationPolicyCheckpoint:
        if not isinstance(value, dict):
            raise ValueError("revocation-policy checkpoint must be an object")
        required = {
            "schema",
            "accepted_sequence",
            "accepted_policy_evidence_sha256",
            "accepted_signing_key_id",
        }
        if set(value) != required:
            raise ValueError(
                "revocation-policy checkpoint must contain exactly " + str(sorted(required))
            )
        schema = _text(value.get("schema"), "revocation-policy checkpoint.schema")
        if schema != REVOCATION_CHECKPOINT_SCHEMA:
            raise ValueError(f"unsupported revocation-policy checkpoint schema: {schema}")
        return cls(
            accepted_sequence=_sequence(
                value.get("accepted_sequence"),
                "revocation-policy checkpoint.accepted_sequence",
            ),
            accepted_policy_evidence_sha256=_digest(
                value.get("accepted_policy_evidence_sha256"),
                "revocation-policy checkpoint.accepted_policy_evidence_sha256",
            ),
            accepted_signing_key_id=_key_id(
                value.get("accepted_signing_key_id"),
                "revocation-policy checkpoint.accepted_signing_key_id",
            ),
            schema=schema,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "accepted_sequence": self.accepted_sequence,
            "accepted_policy_evidence_sha256": self.accepted_policy_evidence_sha256,
            "accepted_signing_key_id": self.accepted_signing_key_id,
        }

    def digest(self) -> str:
        return _sha256_bytes(_canonical_bytes(self.to_dict()))


def sign_revocation_policy(
    statement: SignedRevocationPolicyStatement,
    private_key: KeySource,
) -> dict[str, Any]:
    key = _load_private_key(private_key)
    key_id = _public_key_id(key.public_key())
    statement_dict = SignedRevocationPolicyStatement.from_dict(statement.to_dict()).to_dict()
    signature = base64.b64encode(key.sign(_canonical_bytes(statement_dict))).decode("ascii")
    return {
        "schema": SIGNED_POLICY_ENVELOPE_SCHEMA,
        "statement": statement_dict,
        "signing": {"algorithm": "Ed25519", "key_id": key_id},
        "signature": signature,
    }


def verify_revocation_policy(
    source: str | Path | bytes | dict[str, Any],
    *,
    trusted_public_key: KeySource,
    now: datetime | None = None,
) -> VerifiedSignedRevocationPolicy:
    envelope = _load_object(source, "signed revocation-policy envelope")
    required = {"schema", "statement", "signing", "signature"}
    if set(envelope) != required:
        raise ValueError(
            "signed revocation-policy envelope must contain exactly " + str(sorted(required))
        )
    schema = _text(envelope.get("schema"), "signed revocation-policy envelope.schema")
    if schema != SIGNED_POLICY_ENVELOPE_SCHEMA:
        raise ValueError(f"unsupported signed revocation-policy envelope schema: {schema}")
    signing = envelope.get("signing")
    if not isinstance(signing, dict) or set(signing) != {"algorithm", "key_id"}:
        raise ValueError("signed revocation-policy signing metadata is invalid")
    if signing.get("algorithm") != "Ed25519":
        raise ValueError("signed revocation-policy algorithm must be Ed25519")
    key_id = _key_id(signing.get("key_id"), "signed revocation-policy signing.key_id")
    encoded_signature = _text(envelope.get("signature"), "signed revocation-policy signature")
    statement = SignedRevocationPolicyStatement.from_dict(envelope.get("statement"))
    public_key = _load_public_key(trusted_public_key)
    if _public_key_id(public_key) != key_id:
        raise ValueError("trusted revocation authority fingerprint does not match the policy key ID")
    try:
        from cryptography.exceptions import InvalidSignature
    except ImportError as exc:
        raise RuntimeError("Install the 'signing' extra to verify revocation policies") from exc
    try:
        signature = base64.b64decode(encoded_signature, validate=True)
        public_key.verify(signature, _canonical_bytes(statement.to_dict()))
    except (InvalidSignature, ValueError) as exc:
        raise ValueError("signed revocation-policy signature is invalid") from exc
    statement.policy.assert_current(_current_time(now))
    return VerifiedSignedRevocationPolicy(
        statement=statement,
        signing_key_id=key_id,
        evidence_sha256=_sha256_bytes(_canonical_bytes(envelope)),
    )


def validate_revocation_policy_checkpoint(
    policy: VerifiedSignedRevocationPolicy,
    checkpoint: RevocationPolicyCheckpoint,
) -> None:
    if policy.sequence < checkpoint.accepted_sequence:
        raise PermissionError("signed revocation-policy rollback detected")
    if policy.sequence == checkpoint.accepted_sequence:
        if policy.evidence_sha256 != checkpoint.accepted_policy_evidence_sha256:
            raise PermissionError("signed revocation policy changed at the accepted sequence")
        if policy.signing_key_id != checkpoint.accepted_signing_key_id:
            raise PermissionError("revocation authority changed at the accepted sequence")
        return
    if policy.sequence != checkpoint.accepted_sequence + 1:
        raise PermissionError("signed revocation-policy sequence skipped the trusted checkpoint")
    if (
        policy.statement.previous_policy_sha256
        != checkpoint.accepted_policy_evidence_sha256
    ):
        raise PermissionError("signed revocation-policy chain does not extend the checkpoint")


def advance_revocation_policy_checkpoint(
    policy: VerifiedSignedRevocationPolicy,
    checkpoint: RevocationPolicyCheckpoint | None = None,
) -> RevocationPolicyCheckpoint:
    if checkpoint is not None:
        validate_revocation_policy_checkpoint(policy, checkpoint)
    elif policy.sequence != 1 or policy.statement.previous_policy_sha256 is not None:
        raise ValueError("initial revocation checkpoint requires sequence 1 without a predecessor")
    return RevocationPolicyCheckpoint(
        accepted_sequence=policy.sequence,
        accepted_policy_evidence_sha256=policy.evidence_sha256,
        accepted_signing_key_id=policy.signing_key_id,
    )


def load_trusted_signed_revocation_policy(
    trusted_key_dir: str | Path,
    *,
    now: datetime | None = None,
) -> tuple[VerifiedSignedRevocationPolicy, RevocationPolicyCheckpoint]:
    root = Path(trusted_key_dir).expanduser()
    if not root.is_absolute():
        raise ValueError("signed revocation-policy trusted directory must be absolute")
    resolved_root = root.resolve()
    policy_path = (resolved_root / SIGNED_POLICY_FILENAME).resolve()
    checkpoint_path = (resolved_root / REVOCATION_CHECKPOINT_FILENAME).resolve()
    for path, label in (
        (policy_path, "signed revocation policy"),
        (checkpoint_path, "revocation-policy checkpoint"),
    ):
        try:
            path.relative_to(resolved_root)
        except ValueError as exc:
            raise PermissionError(f"{label} resolved outside the trusted directory") from exc
        if not path.is_file():
            raise FileNotFoundError(f"{label} is unavailable")
    envelope = _load_object(policy_path, "signed revocation-policy envelope")
    signing = envelope.get("signing")
    if not isinstance(signing, dict):
        raise ValueError("signed revocation-policy signing metadata is invalid")
    key_id = _key_id(signing.get("key_id"), "signed revocation-policy signing.key_id")
    authority_root = (resolved_root / REVOCATION_AUTHORITY_DIRECTORY).resolve()
    try:
        authority_root.relative_to(resolved_root)
    except ValueError as exc:
        raise PermissionError("revocation authority directory escaped the trust root") from exc
    public_key = (authority_root / f"{key_id}.pem").resolve()
    try:
        public_key.relative_to(authority_root)
    except ValueError as exc:
        raise PermissionError("revocation authority key escaped its trust directory") from exc
    if not public_key.is_file():
        raise FileNotFoundError(
            f"trusted revocation authority is unavailable for key_id={key_id}"
        )
    verified = verify_revocation_policy(
        envelope,
        trusted_public_key=public_key,
        now=now,
    )
    checkpoint_value = _strict_json(checkpoint_path.read_bytes())
    checkpoint = RevocationPolicyCheckpoint.from_dict(checkpoint_value)
    validate_revocation_policy_checkpoint(verified, checkpoint)
    return verified, checkpoint
