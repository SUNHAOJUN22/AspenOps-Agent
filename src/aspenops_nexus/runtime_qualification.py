from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TypeAlias

from .simulator_capabilities import SimulatorCapabilityProfile

STATEMENT_SCHEMA = "aspenops.runtime-profile-qualification/v1"
ENVELOPE_SCHEMA = "aspenops.signed-runtime-profile-qualification/v1"

KeySource: TypeAlias = str | Path | bytes
_SHA256_LENGTH = 64
_KEY_ID_LENGTH = 32
_MAX_CASES = 256


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _strict_object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in pairs:
        if key in output:
            raise ValueError(f"Duplicate JSON key: {key}")
        output[key] = value
    return output


def _reject_constant(value: str) -> Any:
    raise ValueError(f"Non-finite JSON constant is not allowed: {value}")


def _strict_json(payload: bytes) -> Any:
    return json.loads(
        payload,
        object_pairs_hook=_strict_object_pairs,
        parse_constant=_reject_constant,
    )


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    text = value.strip()
    if "\x00" in text or "\r" in text or "\n" in text:
        raise ValueError(f"{label} must be one safe text line")
    return text


def _digest(value: Any, label: str) -> str:
    text = _text(value, label).casefold()
    if len(text) != _SHA256_LENGTH or any(character not in "0123456789abcdef" for character in text):
        raise ValueError(f"{label} must be a lowercase SHA-256 digest")
    return text


def _key_id(value: Any, label: str) -> str:
    text = _text(value, label).casefold()
    if len(text) != _KEY_ID_LENGTH or any(character not in "0123456789abcdef" for character in text):
        raise ValueError(f"{label} must be a 32-character public-key fingerprint")
    return text


def _parse_time(value: Any, label: str) -> datetime:
    text = _text(value, label)
    normalized = f"{text[:-1]}+00:00" if text.endswith("Z") else text
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(f"{label} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{label} must include a timezone")
    return parsed.astimezone(UTC)


def _time_text(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Qualification timestamps must include a timezone")
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _read_key_source(source: KeySource) -> bytes:
    if isinstance(source, bytes):
        return source
    return Path(source).expanduser().read_bytes()


def _load_private_key(source: KeySource) -> Any:
    try:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    except ImportError as exc:
        raise RuntimeError("Install the 'signing' extra to sign runtime qualifications") from exc
    key = serialization.load_pem_private_key(_read_key_source(source), password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise TypeError("Runtime qualification signing key must be Ed25519")
    return key


def _load_public_key(source: KeySource) -> Any:
    try:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    except ImportError as exc:
        raise RuntimeError("Install the 'signing' extra to verify runtime qualifications") from exc
    key = serialization.load_pem_public_key(_read_key_source(source))
    if not isinstance(key, Ed25519PublicKey):
        raise TypeError("Runtime qualification verification key must be Ed25519")
    return key


def _public_key_id(public_key: Any) -> str:
    try:
        from cryptography.hazmat.primitives import serialization
    except ImportError as exc:
        raise RuntimeError("Install the 'signing' extra to process runtime qualifications") from exc
    raw = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return _sha256_bytes(bytes(raw))[:_KEY_ID_LENGTH]


@dataclass(frozen=True, slots=True, order=True)
class GoldenCaseQualification:
    case_id: str
    evidence_bundle_sha256: str
    topology_sha256: str
    layout_sha256: str
    passed: bool

    @classmethod
    def from_dict(cls, value: Any, *, label: str) -> GoldenCaseQualification:
        if not isinstance(value, dict):
            raise ValueError(f"{label} must be an object")
        required = {
            "case_id",
            "evidence_bundle_sha256",
            "topology_sha256",
            "layout_sha256",
            "passed",
        }
        if set(value) != required:
            raise ValueError(f"{label} must contain exactly {sorted(required)}")
        passed = value.get("passed")
        if not isinstance(passed, bool):
            raise ValueError(f"{label}.passed must be a boolean")
        return cls(
            case_id=_text(value.get("case_id"), f"{label}.case_id"),
            evidence_bundle_sha256=_digest(
                value.get("evidence_bundle_sha256"),
                f"{label}.evidence_bundle_sha256",
            ),
            topology_sha256=_digest(
                value.get("topology_sha256"),
                f"{label}.topology_sha256",
            ),
            layout_sha256=_digest(value.get("layout_sha256"), f"{label}.layout_sha256"),
            passed=passed,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "evidence_bundle_sha256": self.evidence_bundle_sha256,
            "topology_sha256": self.topology_sha256,
            "layout_sha256": self.layout_sha256,
            "passed": self.passed,
        }


@dataclass(frozen=True, slots=True)
class RuntimeQualificationStatement:
    profile_id: str
    profile_sha256: str
    simulator: str
    marketing_version: str
    adapter_contract: str
    adapter_code_sha256: str
    runtime_identity_sha256: str
    issued_at: datetime
    expires_at: datetime
    approved_by: str
    approval_scope: str
    golden_cases: tuple[GoldenCaseQualification, ...]
    schema: str = STATEMENT_SCHEMA

    @classmethod
    def from_dict(cls, value: Any) -> RuntimeQualificationStatement:
        if not isinstance(value, dict):
            raise ValueError("runtime qualification statement must be an object")
        required = {
            "schema",
            "profile_id",
            "profile_sha256",
            "simulator",
            "marketing_version",
            "adapter_contract",
            "adapter_code_sha256",
            "runtime_identity_sha256",
            "issued_at",
            "expires_at",
            "approved_by",
            "approval_scope",
            "golden_cases",
        }
        if set(value) != required:
            raise ValueError(
                "runtime qualification statement must contain exactly " + str(sorted(required))
            )
        schema = _text(value.get("schema"), "runtime qualification.schema")
        if schema != STATEMENT_SCHEMA:
            raise ValueError(f"Unsupported runtime qualification schema: {schema}")
        issued_at = _parse_time(value.get("issued_at"), "runtime qualification.issued_at")
        expires_at = _parse_time(value.get("expires_at"), "runtime qualification.expires_at")
        if expires_at <= issued_at:
            raise ValueError("runtime qualification expires_at must be later than issued_at")
        raw_cases = value.get("golden_cases")
        if not isinstance(raw_cases, list):
            raise ValueError("runtime qualification.golden_cases must be an array")
        if not raw_cases:
            raise ValueError("runtime qualification requires at least one Golden Case")
        if len(raw_cases) > _MAX_CASES:
            raise ValueError(f"runtime qualification exceeds {_MAX_CASES} Golden Cases")
        golden_cases = tuple(
            GoldenCaseQualification.from_dict(
                item,
                label=f"runtime qualification.golden_cases[{index}]",
            )
            for index, item in enumerate(raw_cases)
        )
        case_ids = [item.case_id for item in golden_cases]
        if len(set(case_ids)) != len(case_ids):
            raise ValueError("runtime qualification Golden Case IDs must be unique")
        if not all(item.passed for item in golden_cases):
            raise ValueError("runtime qualification contains a failed Golden Case")
        return cls(
            profile_id=_text(value.get("profile_id"), "runtime qualification.profile_id"),
            profile_sha256=_digest(
                value.get("profile_sha256"),
                "runtime qualification.profile_sha256",
            ),
            simulator=_text(value.get("simulator"), "runtime qualification.simulator").casefold(),
            marketing_version=_text(
                value.get("marketing_version"),
                "runtime qualification.marketing_version",
            ),
            adapter_contract=_text(
                value.get("adapter_contract"),
                "runtime qualification.adapter_contract",
            ),
            adapter_code_sha256=_digest(
                value.get("adapter_code_sha256"),
                "runtime qualification.adapter_code_sha256",
            ),
            runtime_identity_sha256=_digest(
                value.get("runtime_identity_sha256"),
                "runtime qualification.runtime_identity_sha256",
            ),
            issued_at=issued_at,
            expires_at=expires_at,
            approved_by=_text(value.get("approved_by"), "runtime qualification.approved_by"),
            approval_scope=_text(
                value.get("approval_scope"),
                "runtime qualification.approval_scope",
            ),
            golden_cases=tuple(sorted(golden_cases)),
            schema=schema,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "profile_id": self.profile_id,
            "profile_sha256": self.profile_sha256,
            "simulator": self.simulator,
            "marketing_version": self.marketing_version,
            "adapter_contract": self.adapter_contract,
            "adapter_code_sha256": self.adapter_code_sha256,
            "runtime_identity_sha256": self.runtime_identity_sha256,
            "issued_at": _time_text(self.issued_at),
            "expires_at": _time_text(self.expires_at),
            "approved_by": self.approved_by,
            "approval_scope": self.approval_scope,
            "golden_cases": [item.to_dict() for item in self.golden_cases],
        }

    def digest(self) -> str:
        return _sha256_bytes(_canonical_bytes(self.to_dict()))


@dataclass(frozen=True, slots=True)
class VerifiedRuntimeQualification:
    statement: RuntimeQualificationStatement
    signing_key_id: str
    evidence_sha256: str

    def assert_matches_profile(self, profile: SimulatorCapabilityProfile) -> None:
        if self.statement.profile_id != profile.profile_id:
            raise ValueError("Qualification profile_id does not match the capability profile")
        if self.statement.profile_sha256 != profile.digest():
            raise ValueError("Qualification profile hash does not match the capability profile")
        if self.statement.simulator != profile.simulator:
            raise ValueError("Qualification simulator does not match the capability profile")
        if self.statement.marketing_version != profile.marketing_version:
            raise ValueError("Qualification version does not match the capability profile")
        if self.statement.adapter_contract != profile.adapter_contract:
            raise ValueError("Qualification adapter contract does not match the capability profile")

    def assert_required_cases(self, required_case_ids: tuple[str, ...]) -> None:
        observed = {item.case_id for item in self.statement.golden_cases if item.passed}
        missing = sorted(set(required_case_ids) - observed)
        if missing:
            raise ValueError(
                "Runtime qualification is missing required Golden Cases: " + ", ".join(missing)
            )


def sign_runtime_qualification(
    statement: RuntimeQualificationStatement,
    private_key: KeySource,
) -> dict[str, Any]:
    key = _load_private_key(private_key)
    key_id = _public_key_id(key.public_key())
    statement_dict = statement.to_dict()
    signature = base64.b64encode(key.sign(_canonical_bytes(statement_dict))).decode("ascii")
    return {
        "schema": ENVELOPE_SCHEMA,
        "statement": statement_dict,
        "signing": {"algorithm": "Ed25519", "key_id": key_id},
        "signature": signature,
    }


def _load_envelope(source: str | Path | bytes | dict[str, Any]) -> dict[str, Any]:
    if isinstance(source, dict):
        return dict(source)
    if isinstance(source, bytes):
        value = _strict_json(source)
    else:
        value = _strict_json(Path(source).expanduser().read_bytes())
    if not isinstance(value, dict):
        raise ValueError("runtime qualification envelope root must be an object")
    return value


def verify_runtime_qualification(
    source: str | Path | bytes | dict[str, Any],
    *,
    trusted_public_key: KeySource,
    now: datetime | None = None,
    required_case_ids: tuple[str, ...] = (),
) -> VerifiedRuntimeQualification:
    envelope = _load_envelope(source)
    required = {"schema", "statement", "signing", "signature"}
    if set(envelope) != required:
        raise ValueError(
            "runtime qualification envelope must contain exactly " + str(sorted(required))
        )
    schema = _text(envelope.get("schema"), "runtime qualification envelope.schema")
    if schema != ENVELOPE_SCHEMA:
        raise ValueError(f"Unsupported runtime qualification envelope schema: {schema}")
    signing = envelope.get("signing")
    if not isinstance(signing, dict) or set(signing) != {"algorithm", "key_id"}:
        raise ValueError("runtime qualification signing metadata is invalid")
    if signing.get("algorithm") != "Ed25519":
        raise ValueError("runtime qualification signature algorithm must be Ed25519")
    key_id = _key_id(signing.get("key_id"), "runtime qualification signing.key_id")
    encoded_signature = _text(
        envelope.get("signature"),
        "runtime qualification signature",
    )
    statement = RuntimeQualificationStatement.from_dict(envelope.get("statement"))
    public_key = _load_public_key(trusted_public_key)
    if _public_key_id(public_key) != key_id:
        raise ValueError("trusted public key fingerprint does not match the qualification key ID")
    try:
        from cryptography.exceptions import InvalidSignature
    except ImportError as exc:
        raise RuntimeError("Install the 'signing' extra to verify runtime qualifications") from exc
    try:
        signature = base64.b64decode(encoded_signature, validate=True)
        public_key.verify(signature, _canonical_bytes(statement.to_dict()))
    except (InvalidSignature, ValueError) as exc:
        raise ValueError("runtime qualification signature is invalid") from exc
    current = now or datetime.now(UTC)
    if current.tzinfo is None or current.utcoffset() is None:
        raise ValueError("runtime qualification verification time must include a timezone")
    current = current.astimezone(UTC)
    if current < statement.issued_at:
        raise ValueError("runtime qualification is not valid yet")
    if current >= statement.expires_at:
        raise ValueError("runtime qualification has expired")
    verified = VerifiedRuntimeQualification(
        statement=statement,
        signing_key_id=key_id,
        evidence_sha256=_sha256_bytes(_canonical_bytes(envelope)),
    )
    verified.assert_required_cases(required_case_ids)
    return verified


def load_trusted_runtime_qualification(
    source: str | Path | bytes | dict[str, Any],
    *,
    trusted_key_dir: str | Path,
    now: datetime | None = None,
    required_case_ids: tuple[str, ...] = (),
) -> VerifiedRuntimeQualification:
    envelope = _load_envelope(source)
    signing = envelope.get("signing")
    if not isinstance(signing, dict):
        raise ValueError("runtime qualification signing metadata is invalid")
    key_id = _key_id(signing.get("key_id"), "runtime qualification signing.key_id")
    root = Path(trusted_key_dir).expanduser()
    if not root.is_absolute():
        raise ValueError("runtime qualification trusted key directory must be absolute")
    resolved_root = root.resolve()
    public_key = (resolved_root / f"{key_id}.pem").resolve()
    try:
        public_key.relative_to(resolved_root)
    except ValueError as exc:
        raise PermissionError("runtime qualification key resolved outside the trust directory") from exc
    if not public_key.is_file():
        raise FileNotFoundError(
            f"Trusted runtime qualification key is unavailable for key_id={key_id}"
        )
    return verify_runtime_qualification(
        envelope,
        trusted_public_key=public_key,
        now=now,
        required_case_ids=required_case_ids,
    )
