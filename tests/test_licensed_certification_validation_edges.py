from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

import aspenops_nexus.licensed_certification as licensed
from aspenops_nexus.config import Settings
from aspenops_nexus.hashing import sha256_file


@pytest.mark.parametrize(
    ("operation", "message"),
    [
        (lambda: licensed._object([], "value"), "must be an object"),
        (lambda: licensed._array({}, "value"), "must be an array"),
        (lambda: licensed._text(1, "value"), "must be a string"),
        (lambda: licensed._text("  ", "value"), "non-empty string"),
        (lambda: licensed._finite_nonnegative(True, "value"), "finite non-negative"),
        (lambda: licensed._finite_nonnegative(-1, "value"), "finite non-negative"),
        (lambda: licensed._positive_integer(True, "value"), "must be an integer"),
        (lambda: licensed._positive_integer(0, "value"), "between 1"),
        (lambda: licensed._digest("bad", "digest"), "SHA-256"),
        (lambda: licensed._commit("main"), "40-character Git SHA"),
        (lambda: licensed._unique_texts([], "items"), "at least one item"),
        (lambda: licensed._unique_texts(["A", "a"], "items"), "unique values"),
        (lambda: licensed._scoped_texts(["bad*"], "items"), "wildcard"),
        (lambda: licensed._version_patterns([".*"]), "anchored"),
        (lambda: licensed._version_patterns(["^["]), "Invalid runtime version pattern"),
        (lambda: licensed._timezone_aware("bad", "time"), "ISO-8601"),
        (lambda: licensed._timezone_aware("2026-07-21T00:00:00", "time"), "timezone"),
        (
            lambda: licensed.TolerancePolicy.from_document({"abs_tol": 1.0}, "policy"),
            "requires abs_tol and rel_tol",
        ),
        (
            lambda: licensed.RepeatabilityPlan.from_document(
                {
                    "repeats": 1,
                    "workers": [1],
                    "default_tolerance": {"abs_tol": 0.0, "rel_tol": 0.0},
                }
            ),
            "at least two",
        ),
        (
            lambda: licensed.RepeatabilityPlan.from_document(
                {
                    "repeats": 2,
                    "workers": [],
                    "default_tolerance": {"abs_tol": 0.0, "rel_tol": 0.0},
                }
            ),
            "unique worker counts",
        ),
        (
            lambda: licensed.RepeatabilityPlan.from_document(
                {
                    "repeats": 2,
                    "workers": [1, 1],
                    "default_tolerance": {"abs_tol": 0.0, "rel_tol": 0.0},
                }
            ),
            "unique worker counts",
        ),
        (
            lambda: licensed.EngineeringAcceptance.from_document(
                {
                    "status": "self-approved",
                    "reviewer": "reviewer",
                    "approved_at": "2026-07-21T00:00:00+00:00",
                    "scope": "scope",
                }
            ),
            "approved or pending",
        ),
    ],
)
def test_validation_helpers_reject_ambiguous_inputs(
    operation: Callable[[], Any],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        operation()


def _plan(
    tmp_path: Path,
    *,
    files: bool,
    acceptance: str = "approved",
) -> licensed.LicensedCertificationPlan:
    model = tmp_path / "case.bkp"
    registry = tmp_path / "registry.json"
    if files:
        model.write_bytes(b"model")
        registry.write_text("{}", encoding="utf-8")
    return licensed.LicensedCertificationPlan(
        case_id="qualification-case",
        approved_commit="a" * 40,
        backend="aspen_plus",
        request={
            "backend": "aspen_plus",
            "model_path": str(model),
            "registry_path": str(registry),
            "reads": [],
            "points": [{}],
        },
        model_sha256=sha256_file(model) if files else "0" * 64,
        registry_sha256=sha256_file(registry) if files else "0" * 64,
        repeatability=licensed.RepeatabilityPlan(
            repeats=2,
            workers=(1,),
            default_tolerance=licensed.TolerancePolicy(1e-6, 1e-6),
            output_tolerances={},
        ),
        engineering_acceptance=licensed.EngineeringAcceptance(
            status=acceptance,
            reviewer="qualified-engineer",
            approved_at="2026-07-21T00:00:00+00:00",
            scope="approved scope",
        ),
        progids=("Apwn.Document.40.0",),
        version_patterns=("^40\\.",),
        license_slots=1,
        license_server_identity="approved-server",
        feature_names=("ASPEN_PLUS",),
        runner_names=("approved-runner",),
        runner_architecture="X64",
        signing_required=True,
        signing_key_id="0" * 32,
    )


def test_plan_loader_round_trips_a_canonical_document(tmp_path: Path) -> None:
    plan = _plan(tmp_path, files=True)
    path = tmp_path / "plan.json"
    path.write_text(json.dumps(plan.to_dict()), encoding="utf-8")
    assert licensed.load_licensed_plan(path) == plan


def test_preflight_accumulates_independent_fail_closed_blockers(tmp_path: Path) -> None:
    plan = _plan(tmp_path, files=False, acceptance="pending")
    report = licensed.certification_preflight(
        plan,
        Settings(
            backend="mock",
            state_dir=tmp_path / "state",
            allowed_roots=(),
            license_slots=2,
        ),
        environment={
            "GITHUB_SHA": "b" * 40,
            "RUNNER_NAME": "unapproved-runner",
            "RUNNER_ARCH": "ARM64",
            "RUNNER_ENVIRONMENT": "github-hosted",
        },
        system_name="Linux",
        machine_architecture="ARM64",
        compatibility={"aspen_plus": []},
        pointer_bits=32,
        current_time=datetime.now(UTC),
    )
    codes = {item["code"] for item in report["blockers"]}
    assert {
        "native_windows_required",
        "self_hosted_runner_required",
        "runner_name_not_approved",
        "runner_architecture_mismatch",
        "python_64bit_required",
        "commit_mismatch",
        "backend_mismatch",
        "allowed_roots_missing",
        "model_missing",
        "registry_missing",
        "engineering_acceptance_pending",
        "license_slot_mismatch",
        "license_server_mismatch",
        "license_features_missing",
        "approved_progid_missing",
        "signing_key_missing",
    }.issubset(codes)
    assert report["ready"] is False
    assert report["runtime_execution_allowed"] is False
    assert report["warnings"]


def test_preflight_rejects_naive_runtime_time(tmp_path: Path) -> None:
    plan = _plan(tmp_path, files=False)
    with pytest.raises(ValueError, match="timezone-aware"):
        licensed.certification_preflight(
            plan,
            Settings(backend="aspen_plus", state_dir=tmp_path / "state"),
            environment={},
            system_name="Windows",
            machine_architecture="X64",
            compatibility={"aspen_plus": []},
            current_time=datetime(2026, 7, 21),
        )


def test_preflight_records_invalid_key_state_dir_and_dry_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = _plan(tmp_path, files=True)
    invalid_key = tmp_path / "outside-workspace-invalid-key.pem"
    invalid_key.write_text("not a private key", encoding="utf-8")
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    def fail_named_temporary_file(*args: Any, **kwargs: Any) -> Any:
        raise OSError("read only")

    def fail_dry_run(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("invalid request")

    monkeypatch.setattr(licensed.tempfile, "NamedTemporaryFile", fail_named_temporary_file)
    monkeypatch.setattr(licensed, "dry_run_document", fail_dry_run)
    report = licensed.certification_preflight(
        plan,
        Settings(
            backend="aspen_plus",
            state_dir=tmp_path / "state",
            allowed_roots=(tmp_path.resolve(),),
            license_slots=1,
        ),
        environment={
            "GITHUB_SHA": "a" * 40,
            "RUNNER_NAME": "approved-runner",
            "RUNNER_ARCH": "X64",
            "RUNNER_ENVIRONMENT": "self-hosted",
            "ASPENOPS_LICENSE_SERVER_IDENTITY": "approved-server",
            "ASPENOPS_LICENSE_FEATURES": "ASPEN_PLUS",
            "ASPENOPS_CERT_SIGNING_KEY": str(invalid_key),
            "GITHUB_WORKSPACE": str(workspace),
        },
        system_name="Windows",
        machine_architecture="X64",
        compatibility={"aspen_plus": [{"progid": "Apwn.Document.40.0", "registry_view": "64-bit"}]},
        current_time=datetime(2026, 7, 21, 1, tzinfo=UTC),
    )
    codes = {item["code"] for item in report["blockers"]}
    assert {"signing_key_invalid", "state_dir_not_writable", "dry_run_failed"}.issubset(codes)


def test_non_ed25519_keys_are_rejected(tmp_path: Path) -> None:
    private = rsa.generate_private_key(public_exponent=65537, key_size=1024)
    private_path = tmp_path / "rsa-private.pem"
    public_path = tmp_path / "rsa-public.pem"
    private_path.write_bytes(
        private.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    public_path.write_bytes(
        private.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    with pytest.raises(TypeError, match="Ed25519 private key"):
        licensed._load_private_key(private_path)
    with pytest.raises(TypeError, match="Ed25519 public key"):
        licensed._load_public_key(public_path)
