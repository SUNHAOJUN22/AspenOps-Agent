from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

import aspenops_nexus.licensed_certification as licensed
from aspenops_nexus.licensed_certification import LicensedCertificationPlan
from test_licensed_certification import (
    compatibility,
    environment,
    key_material,
    plan_document,
    settings,
    valid_preflight,
)


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda value: value.update(schema="wrong"), "schema"),
        (lambda value: value.update(backend="mock"), "aspen_plus or hysys"),
        (
            lambda value: value["request"].update(backend="hysys"),
            "request.backend must match",
        ),
        (
            lambda value: value["runner_expectation"].update(architecture="X86"),
            "X64 or ARM64",
        ),
        (
            lambda value: value["signing"].update(required=False),
            "requires signing.required=true",
        ),
        (
            lambda value: value["signing"].update(key_id="bad"),
            "32-character",
        ),
    ],
)
def test_plan_rejects_remaining_invalid_scope_shapes(
    tmp_path: Path,
    mutate: Any,
    message: str,
) -> None:
    _, _, key_id = key_material(tmp_path)
    document = plan_document(tmp_path, key_id)
    mutate(document)
    with pytest.raises(ValueError, match=message):
        LicensedCertificationPlan.from_document(document)


def test_preflight_rejects_pointer_width_future_approval_and_license_scope(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    private_path, _, key_id = key_material(tmp_path)
    document = plan_document(tmp_path, key_id)
    now = datetime(2026, 7, 21, tzinfo=UTC)
    document["engineering_acceptance"]["approved_at"] = (now + timedelta(hours=1)).isoformat()
    plan = LicensedCertificationPlan.from_document(document)
    configured = settings(tmp_path)
    configured = configured.__class__(
        **{
            **{
                field: getattr(configured, field)
                for field in configured.__dataclass_fields__
            },
            "license_slots": 1,
        }
    )
    env = environment(tmp_path, private_path)
    env["ASPENOPS_LICENSE_FEATURES"] = "OTHER_FEATURE"

    report = licensed.certification_preflight(
        plan,
        configured,
        environment=env,
        system_name="Windows",
        machine_architecture="X64",
        pointer_bits=32,
        current_time=now,
        compatibility=compatibility(),
    )
    codes = {item["code"] for item in report["blockers"]}
    assert {
        "python_64bit_required",
        "engineering_approval_in_future",
        "license_slot_mismatch",
        "license_features_missing",
    }.issubset(codes)


def test_preflight_requires_timezone_aware_observation_time(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan, configured, env, _ = valid_preflight(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match="timezone-aware"):
        licensed.certification_preflight(
            plan,
            configured,
            environment=env,
            system_name="Windows",
            machine_architecture="X64",
            pointer_bits=64,
            current_time=datetime(2026, 7, 21),
            compatibility=compatibility(),
        )


def test_preflight_classifies_unreadable_invalid_and_mismatched_keys(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan, configured, env, _ = valid_preflight(tmp_path, monkeypatch)

    unreadable = dict(env)
    unreadable["ASPENOPS_CERT_SIGNING_KEY"] = str(tmp_path / "missing.pem")
    report = licensed.certification_preflight(
        plan,
        configured,
        environment=unreadable,
        compatibility=compatibility(),
    )
    assert "signing_key_unreadable" in {item["code"] for item in report["blockers"]}

    invalid_path = tmp_path / "invalid.pem"
    invalid_path.write_text("not a key", encoding="utf-8")
    invalid = dict(env)
    invalid["ASPENOPS_CERT_SIGNING_KEY"] = str(invalid_path)
    report = licensed.certification_preflight(
        plan,
        configured,
        environment=invalid,
        compatibility=compatibility(),
    )
    assert "signing_key_invalid" in {item["code"] for item in report["blockers"]}

    other_path, _, _ = key_material(tmp_path / "other")
    mismatched = dict(env)
    mismatched["ASPENOPS_CERT_SIGNING_KEY"] = str(other_path)
    report = licensed.certification_preflight(
        plan,
        configured,
        environment=mismatched,
        compatibility=compatibility(),
    )
    assert "signing_key_id_mismatch" in {item["code"] for item in report["blockers"]}


def test_preflight_records_state_directory_and_dry_run_failures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan, configured, env, _ = valid_preflight(tmp_path, monkeypatch)

    monkeypatch.setattr(
        licensed.tempfile,
        "NamedTemporaryFile",
        lambda **kwargs: (_ for _ in ()).throw(OSError("disk unavailable")),
    )
    monkeypatch.setattr(
        licensed,
        "dry_run_document",
        lambda request, active: (_ for _ in ()).throw(ValueError("bad semantic plan")),
    )
    report = licensed.certification_preflight(
        plan,
        configured,
        environment=env,
        compatibility=compatibility(),
    )
    codes = {item["code"] for item in report["blockers"]}
    assert {"state_dir_not_writable", "dry_run_failed"}.issubset(codes)


def test_runtime_scope_rejects_malformed_report_shapes(tmp_path: Path) -> None:
    _, _, key_id = key_material(tmp_path)
    plan = LicensedCertificationPlan.from_document(plan_document(tmp_path, key_id))
    evidence = licensed._runtime_scope_evidence(
        plan,
        [
            {"runs": "bad"},
            {"runs": ["bad"]},
            {"runs": [["bad", {"diagnostics": {}}, {"diagnostics": {"worker": {}}}]]},
        ],
    )
    codes = {item["code"] for item in evidence["violations"]}
    assert {
        "runtime_runs_missing",
        "runtime_run_malformed",
        "runtime_result_malformed",
        "runtime_identity_missing",
        "no_runtime_identity_evidence",
    }.issubset(codes)


def test_key_loaders_reject_non_ed25519_keys() -> None:
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_bytes = private.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_bytes = private.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    with pytest.raises(TypeError, match="Ed25519 private"):
        licensed._load_private_key(private_bytes)
    with pytest.raises(TypeError, match="Ed25519 public"):
        licensed._load_public_key(public_bytes)
