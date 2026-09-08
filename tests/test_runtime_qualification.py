from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from aspenops_nexus.runtime_qualification import (
    ENVELOPE_SCHEMA,
    STATEMENT_SCHEMA,
    GoldenCaseQualification,
    RuntimeQualificationStatement,
    VerifiedRuntimeQualification,
    _canonical_bytes,
    _load_envelope,
    _parse_time,
    _strict_json,
    _time_text,
    load_trusted_runtime_qualification,
    sign_runtime_qualification,
    verify_runtime_qualification,
)
from aspenops_nexus.simulator_capabilities import get_builtin_capability_profile

NOW = datetime(2026, 8, 2, 12, 0, tzinfo=UTC)


def key_material() -> tuple[bytes, bytes]:
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


def golden_case(case_id: str = "HEATER_FLASH_V15") -> GoldenCaseQualification:
    return GoldenCaseQualification(
        case_id=case_id,
        evidence_bundle_sha256="c" * 64,
        topology_sha256="d" * 64,
        layout_sha256="e" * 64,
        passed=True,
    )


def statement(
    *,
    issued_at: datetime | None = None,
    expires_at: datetime | None = None,
    cases: tuple[GoldenCaseQualification, ...] | None = None,
) -> RuntimeQualificationStatement:
    profile = get_builtin_capability_profile("aspen_plus", "15")
    return RuntimeQualificationStatement(
        profile_id=profile.profile_id,
        profile_sha256=profile.digest(),
        simulator=profile.simulator,
        marketing_version=profile.marketing_version,
        adapter_contract=profile.adapter_contract,
        adapter_code_sha256="a" * 64,
        runtime_identity_sha256="b" * 64,
        issued_at=issued_at or NOW - timedelta(hours=1),
        expires_at=expires_at or NOW + timedelta(days=1),
        approved_by="Engineer A",
        approval_scope="Golden Case qualification for controlled test runtime",
        golden_cases=cases or (golden_case(),),
    )


def verified(
    *,
    required_case_ids: tuple[str, ...] = ("HEATER_FLASH_V15",),
) -> tuple[VerifiedRuntimeQualification, dict[str, Any], bytes, bytes]:
    private_pem, public_pem = key_material()
    envelope = sign_runtime_qualification(statement(), private_pem)
    proof = verify_runtime_qualification(
        envelope,
        trusted_public_key=public_pem,
        now=NOW,
        required_case_ids=required_case_ids,
    )
    return proof, envelope, private_pem, public_pem


def test_sign_and_verify_runtime_qualification() -> None:
    proof, envelope, _, _ = verified()
    assert envelope["schema"] == ENVELOPE_SCHEMA
    assert envelope["statement"]["schema"] == STATEMENT_SCHEMA
    assert envelope["signing"]["algorithm"] == "Ed25519"
    assert len(envelope["signing"]["key_id"]) == 32
    assert proof.statement.digest() == statement().digest()
    assert proof.signing_key_id == envelope["signing"]["key_id"]
    assert len(proof.evidence_sha256) == 64
    proof.assert_matches_profile(get_builtin_capability_profile("aspen_plus", "15"))
    proof.assert_required_cases(("HEATER_FLASH_V15",))


def test_statement_roundtrip_and_canonical_time() -> None:
    source = statement()
    restored = RuntimeQualificationStatement.from_dict(source.to_dict())
    assert restored == source
    assert restored.digest() == source.digest()
    assert _time_text(NOW) == "2026-08-02T12:00:00Z"
    assert _parse_time("2026-08-02T12:00:00Z", "time") == NOW
    assert _parse_time("2026-08-02T20:00:00+08:00", "time") == NOW
    assert json.loads(_canonical_bytes({"b": 2, "a": 1})) == {"a": 1, "b": 2}


def test_golden_case_roundtrip_and_validation() -> None:
    case = golden_case()
    assert GoldenCaseQualification.from_dict(case.to_dict()) == case
    for payload in (
        [],
        {"case_id": "A"},
        {
            "case_id": "A",
            "evidence_bundle_sha256": "bad",
            "topology_sha256": "d" * 64,
            "layout_sha256": "e" * 64,
            "passed": True,
        },
        {
            "case_id": "A",
            "evidence_bundle_sha256": "c" * 64,
            "topology_sha256": "d" * 64,
            "layout_sha256": "e" * 64,
            "passed": "yes",
        },
    ):
        with pytest.raises(ValueError):
            GoldenCaseQualification.from_dict(payload, label="case")


def test_statement_rejects_shape_time_and_golden_case_errors() -> None:
    base = statement().to_dict()
    invalid: list[dict[str, Any]] = []
    value = dict(base)
    value["schema"] = "other/v1"
    invalid.append(value)
    value = dict(base)
    value["extra"] = True
    invalid.append(value)
    value = dict(base)
    value["issued_at"] = "not-a-time"
    invalid.append(value)
    value = dict(base)
    value["issued_at"] = "2026-08-02T12:00:00"
    invalid.append(value)
    value = dict(base)
    value["expires_at"] = value["issued_at"]
    invalid.append(value)
    value = dict(base)
    value["golden_cases"] = []
    invalid.append(value)
    value = dict(base)
    value["golden_cases"] = [golden_case().to_dict(), golden_case().to_dict()]
    invalid.append(value)
    value = dict(base)
    failed = golden_case().to_dict()
    failed["passed"] = False
    value["golden_cases"] = [failed]
    invalid.append(value)
    for payload in invalid:
        with pytest.raises(ValueError):
            RuntimeQualificationStatement.from_dict(payload)


def test_signature_tamper_wrong_key_and_invalid_signature_fail_closed() -> None:
    _, envelope, _, public_pem = verified()
    tampered = json.loads(json.dumps(envelope))
    tampered["statement"]["approval_scope"] = "tampered"
    with pytest.raises(ValueError, match="signature is invalid"):
        verify_runtime_qualification(tampered, trusted_public_key=public_pem, now=NOW)

    _, wrong_public = key_material()
    with pytest.raises(ValueError, match="fingerprint"):
        verify_runtime_qualification(envelope, trusted_public_key=wrong_public, now=NOW)

    malformed = json.loads(json.dumps(envelope))
    malformed["signature"] = "***"
    with pytest.raises(ValueError, match="signature is invalid"):
        verify_runtime_qualification(malformed, trusted_public_key=public_pem, now=NOW)


def test_expired_not_yet_valid_and_naive_time_fail_closed() -> None:
    private_pem, public_pem = key_material()
    expired = sign_runtime_qualification(
        statement(
            issued_at=NOW - timedelta(days=2),
            expires_at=NOW - timedelta(days=1),
        ),
        private_pem,
    )
    with pytest.raises(ValueError, match="expired"):
        verify_runtime_qualification(expired, trusted_public_key=public_pem, now=NOW)

    future = sign_runtime_qualification(
        statement(
            issued_at=NOW + timedelta(hours=1),
            expires_at=NOW + timedelta(days=1),
        ),
        private_pem,
    )
    with pytest.raises(ValueError, match="not valid yet"):
        verify_runtime_qualification(future, trusted_public_key=public_pem, now=NOW)

    with pytest.raises(ValueError, match="timezone"):
        verify_runtime_qualification(
            sign_runtime_qualification(statement(), private_pem),
            trusted_public_key=public_pem,
            now=datetime(2026, 8, 2, 12, 0),
        )


def test_profile_and_required_case_mismatches_fail_closed() -> None:
    proof, _, _, _ = verified(required_case_ids=())
    profile = get_builtin_capability_profile("aspen_plus", "15")
    mismatches = (
        replace(profile, profile_id="wrong"),
        replace(profile, marketing_version="14"),
        replace(profile, adapter_contract="wrong"),
        replace(profile, simulator="hysys"),
    )
    for changed in mismatches:
        with pytest.raises(ValueError):
            proof.assert_matches_profile(changed)
    with pytest.raises(ValueError, match="missing required Golden Cases"):
        proof.assert_required_cases(("MISSING_CASE",))


def test_strict_json_rejects_duplicates_nonfinite_and_bad_envelope_shapes() -> None:
    with pytest.raises(ValueError, match="Duplicate JSON key"):
        _strict_json(b'{"x":1,"x":2}')
    with pytest.raises(ValueError, match="Non-finite"):
        _strict_json(b'{"x":NaN}')
    with pytest.raises(ValueError, match="root must be an object"):
        _load_envelope(b"[]")

    _, envelope, _, public_pem = verified()
    invalid = json.loads(json.dumps(envelope))
    invalid["extra"] = True
    with pytest.raises(ValueError, match="contain exactly"):
        verify_runtime_qualification(invalid, trusted_public_key=public_pem, now=NOW)
    invalid = json.loads(json.dumps(envelope))
    invalid["schema"] = "other/v1"
    with pytest.raises(ValueError, match="Unsupported"):
        verify_runtime_qualification(invalid, trusted_public_key=public_pem, now=NOW)
    invalid = json.loads(json.dumps(envelope))
    invalid["signing"] = []
    with pytest.raises(ValueError, match="signing metadata"):
        verify_runtime_qualification(invalid, trusted_public_key=public_pem, now=NOW)
    invalid = json.loads(json.dumps(envelope))
    invalid["signing"]["algorithm"] = "RSA"
    with pytest.raises(ValueError, match="Ed25519"):
        verify_runtime_qualification(invalid, trusted_public_key=public_pem, now=NOW)


def test_trusted_key_directory_loader(tmp_path: Path) -> None:
    proof, envelope, _, public_pem = verified()
    trust = tmp_path / "trust"
    trust.mkdir()
    (trust / f"{proof.signing_key_id}.pem").write_bytes(public_pem)
    envelope_path = tmp_path / "qualification.json"
    envelope_path.write_text(json.dumps(envelope), encoding="utf-8")
    loaded = load_trusted_runtime_qualification(
        envelope_path,
        trusted_key_dir=trust.resolve(),
        now=NOW,
        required_case_ids=("HEATER_FLASH_V15",),
    )
    assert loaded.evidence_sha256 == proof.evidence_sha256

    with pytest.raises(ValueError, match="absolute"):
        load_trusted_runtime_qualification(
            envelope,
            trusted_key_dir="relative",
            now=NOW,
        )
    missing = tmp_path / "missing"
    missing.mkdir()
    with pytest.raises(FileNotFoundError, match="unavailable"):
        load_trusted_runtime_qualification(
            envelope,
            trusted_key_dir=missing.resolve(),
            now=NOW,
        )
