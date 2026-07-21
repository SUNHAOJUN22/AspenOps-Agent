from __future__ import annotations

import json
import zipfile
from pathlib import Path
from typing import Any

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

import aspenops_nexus.licensed_certification as licensed
from aspenops_nexus.config import Settings
from aspenops_nexus.hashing import sha256_file
from aspenops_nexus.licensed_certification import (
    PENDING_REAL_ASPEN_CERTIFICATION,
    LicensedCertificationPlan,
    certification_preflight,
    execute_licensed_certification,
    verify_licensed_certification_bundle,
    write_licensed_certification_bundle,
)


def key_material(tmp_path: Path) -> tuple[Path, bytes, str]:
    private = Ed25519PrivateKey.generate()
    private_path = tmp_path / "certification-private.pem"
    private_path.write_bytes(
        private.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    public_bytes = private.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    key_id = licensed._key_id(private.public_key())
    return private_path, public_bytes, key_id


def plan_document(tmp_path: Path, key_id: str) -> dict[str, Any]:
    model = tmp_path / "case.bkp"
    registry = tmp_path / "registry.json"
    model.write_bytes(b"approved-model")
    registry.write_text(
        json.dumps(
            {
                "nodes": {
                    "product.purity": {
                        "backend": "aspen_plus",
                        "access": "read",
                        "paths": ["\\Data\\Streams\\PRODUCT\\Output\\PURITY"],
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    return {
        "schema": "aspenops.licensed-certification-plan/v1",
        "case_id": "qualification-case-001",
        "approved_commit": "a" * 40,
        "backend": "aspen_plus",
        "request": {
            "backend": "aspen_plus",
            "model_path": str(model),
            "registry_path": str(registry),
            "reads": [{"key": "product.purity"}],
            "points": [{}],
            "workers": 1,
        },
        "approved_artifacts": {
            "model_sha256": sha256_file(model),
            "registry_sha256": sha256_file(registry),
        },
        "repeatability": {
            "repeats": 3,
            "workers": [1, 2],
            "default_tolerance": {"abs_tol": 1e-6, "rel_tol": 1e-6},
            "output_tolerances": {"product.purity": {"abs_tol": 1e-5, "rel_tol": 1e-5}},
        },
        "engineering_acceptance": {
            "status": "approved",
            "reviewer": "qualified-engineer",
            "approved_at": "2026-07-21T00:00:00+09:00",
            "scope": "Approved non-confidential Aspen Plus qualification case",
        },
        "runtime_expectation": {
            "progids": ["Apwn.Document.40.0"],
            "version_patterns": ["^40\\."],
        },
        "license_expectation": {
            "slots": 2,
            "server_identity": "approved-license-server",
            "feature_names": ["ASPEN_PLUS"],
        },
        "runner_expectation": {
            "names": ["aspen-cert-runner-01"],
            "architecture": "X64",
        },
        "signing": {"required": True, "key_id": key_id},
    }


def settings(tmp_path: Path) -> Settings:
    return Settings(
        backend="aspen_plus",
        allowed_roots=(tmp_path.resolve(),),
        state_dir=(tmp_path / "state").resolve(),
        license_slots=2,
        max_workers=2,
    )


def environment(tmp_path: Path, private_key: Path) -> dict[str, str]:
    workspace = tmp_path / "workspace"
    workspace.mkdir(exist_ok=True)
    return {
        "GITHUB_SHA": "a" * 40,
        "GITHUB_WORKSPACE": str(workspace),
        "RUNNER_NAME": "aspen-cert-runner-01",
        "RUNNER_ARCH": "X64",
        "RUNNER_ENVIRONMENT": "self-hosted",
        "ASPENOPS_LICENSE_SERVER_IDENTITY": "approved-license-server",
        "ASPENOPS_LICENSE_FEATURES": "ASPEN_PLUS;OTHER_FEATURE",
        "ASPENOPS_CERT_SIGNING_KEY": str(private_key),
    }


def compatibility(*, fallback: bool = False) -> dict[str, Any]:
    return {
        "aspen_plus": [
            {
                "product": "aspen_plus",
                "progid": "Apwn.Document.40.0",
                "numeric_version": [40, 0],
                "registry_view": "fallback" if fallback else "64-bit",
                "pinned": False,
            }
        ],
        "hysys": [],
    }


def valid_preflight(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[LicensedCertificationPlan, Settings, dict[str, str], bytes]:
    private_path, public_key, key_id = key_material(tmp_path)
    plan = LicensedCertificationPlan.from_document(plan_document(tmp_path, key_id))
    configured = settings(tmp_path)
    env = environment(tmp_path, private_path)
    monkeypatch.setattr(licensed.platform, "system", lambda: "Windows")
    monkeypatch.setattr(licensed.platform, "machine", lambda: "X64")
    monkeypatch.setattr(licensed, "compatibility_report", lambda: compatibility())
    monkeypatch.setattr(
        licensed,
        "dry_run_document",
        lambda request, active_settings: {"ok": True, "compiled_points": 1},
    )
    return plan, configured, env, public_key


def test_plan_round_trip_is_canonical_and_strict(tmp_path: Path) -> None:
    _, _, key_id = key_material(tmp_path)
    document = plan_document(tmp_path, key_id)
    plan = LicensedCertificationPlan.from_document(document)

    assert LicensedCertificationPlan.from_document(plan.to_dict()) == plan
    assert licensed.canonical_hash(plan.to_dict()) == licensed.canonical_hash(document)
    document["unexpected"] = True
    with pytest.raises(ValueError, match="Unsupported certification plan fields"):
        LicensedCertificationPlan.from_document(document)


@pytest.mark.parametrize(
    ("mutator", "message"),
    [
        (lambda doc: doc.update(approved_commit="main"), "approved_commit"),
        (
            lambda doc: doc["repeatability"].update(workers=[1, 1]),
            "unique worker counts",
        ),
        (
            lambda doc: doc["engineering_acceptance"].update(approved_at="2026-07-21T00:00:00"),
            "include a timezone",
        ),
        (
            lambda doc: doc["license_expectation"].update(slots=True),
            "must be an integer",
        ),
        (
            lambda doc: doc["signing"].update(required=False),
            "requires signing.required=true",
        ),
        (
            lambda doc: doc["approved_artifacts"].update(model_sha256="bad"),
            "SHA-256",
        ),
    ],
)
def test_plan_rejects_ambiguous_or_unsafe_fields(
    tmp_path: Path,
    mutator: Any,
    message: str,
) -> None:
    _, _, key_id = key_material(tmp_path)
    document = plan_document(tmp_path, key_id)
    mutator(document)
    with pytest.raises(ValueError, match=message):
        LicensedCertificationPlan.from_document(document)


def test_preflight_is_ready_only_for_exact_approved_scope(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan, configured, env, _ = valid_preflight(tmp_path, monkeypatch)

    report = certification_preflight(
        plan,
        configured,
        environment=env,
        system_name="Windows",
        machine_architecture="X64",
    )

    assert report["ready"] is True
    assert report["blockers"] == []
    assert report["certification_status"] == PENDING_REAL_ASPEN_CERTIFICATION
    serialized = json.dumps(report, allow_nan=False)
    assert env["ASPENOPS_CERT_SIGNING_KEY"] not in serialized
    assert "PRIVATE KEY" not in serialized


def test_preflight_rejects_compatibility_fallback_as_registration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan, configured, env, _ = valid_preflight(tmp_path, monkeypatch)
    monkeypatch.setattr(licensed, "compatibility_report", lambda: compatibility(fallback=True))

    report = certification_preflight(plan, configured, environment=env)

    assert report["ready"] is False
    assert "approved_progid_missing" in {item["code"] for item in report["blockers"]}


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("GITHUB_SHA", "b" * 40, "commit_mismatch"),
        ("RUNNER_NAME", "unapproved-runner", "runner_name_not_approved"),
        ("RUNNER_ENVIRONMENT", "github-hosted", "self_hosted_runner_required"),
        ("RUNNER_ARCH", "ARM64", "runner_architecture_mismatch"),
        (
            "ASPENOPS_LICENSE_SERVER_IDENTITY",
            "different-server",
            "license_server_mismatch",
        ),
        ("ASPENOPS_LICENSE_FEATURES", "OTHER_FEATURE", "license_features_missing"),
    ],
)
def test_preflight_reports_machine_readable_blockers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: str,
    code: str,
) -> None:
    plan, configured, env, _ = valid_preflight(tmp_path, monkeypatch)
    env[field] = value

    report = certification_preflight(
        plan,
        configured,
        environment=env,
        system_name="Windows",
        machine_architecture=env["RUNNER_ARCH"],
    )

    assert report["ready"] is False
    assert code in {item["code"] for item in report["blockers"]}


def test_preflight_rejects_key_inside_workspace(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan, configured, env, _ = valid_preflight(tmp_path, monkeypatch)
    workspace_key = Path(env["GITHUB_WORKSPACE"]) / "key.pem"
    workspace_key.write_bytes(Path(env["ASPENOPS_CERT_SIGNING_KEY"]).read_bytes())
    env["ASPENOPS_CERT_SIGNING_KEY"] = str(workspace_key)

    report = certification_preflight(
        plan,
        configured,
        environment=env,
        system_name="Windows",
        machine_architecture="X64",
    )

    assert "signing_key_inside_workspace" in {item["code"] for item in report["blockers"]}


def test_preflight_rejects_digest_mismatch_and_never_hides_it(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan, configured, env, _ = valid_preflight(tmp_path, monkeypatch)
    Path(str(plan.request["model_path"])).write_bytes(b"mutated")

    report = certification_preflight(
        plan,
        configured,
        environment=env,
        system_name="Windows",
        machine_architecture="X64",
    )

    blocker = next(item for item in report["blockers"] if item["code"] == "model_digest_mismatch")
    assert blocker["expected"] == plan.model_sha256
    assert blocker["observed"] != plan.model_sha256


def test_blocked_execution_never_calls_repeatability_runtime(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan, configured, env, _ = valid_preflight(tmp_path, monkeypatch)
    env["GITHUB_SHA"] = "b" * 40

    def unexpected_certify(*args: Any, **kwargs: Any) -> dict[str, Any]:
        raise AssertionError("licensed runtime must not execute")

    monkeypatch.setattr(licensed, "certify_batch_document", unexpected_certify)
    report = execute_licensed_certification(
        plan,
        configured,
        output_dir=configured.state_dir / "blocked",
        environment=env,
    )

    assert report["executed"] is False
    assert report["certification_status"] == PENDING_REAL_ASPEN_CERTIFICATION
    assert Path(report["preflight_path"]).is_file()


def execution_report(workers: int) -> dict[str, Any]:
    return {
        "schema": "aspenops.certification/v2",
        "passed": True,
        "repeatability_gate_passed": True,
        "workers": workers,
        "certification_status": PENDING_REAL_ASPEN_CERTIFICATION,
        "runs": [
            [
                {
                    "ok": True,
                    "diagnostics": {
                        "worker": {
                            "runtime": {
                                "progid": "Apwn.Document.40.0",
                                "exposed": {"Version": "40.1"},
                            }
                        }
                    },
                }
            ]
        ],
    }


def test_successful_execution_stays_pending_and_writes_signed_bundle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan, configured, env, public_key = valid_preflight(tmp_path, monkeypatch)
    monkeypatch.setattr(
        licensed,
        "certify_batch_document",
        lambda request, active_settings, **kwargs: execution_report(kwargs["workers"]),
    )

    report = execute_licensed_certification(
        plan,
        configured,
        output_dir=configured.state_dir / "successful",
        environment=env,
    )

    assert report["runtime_gate_passed"] is True
    assert report["certification_status"] == PENDING_REAL_ASPEN_CERTIFICATION
    assert report["bundle_verification"]["verification_status"] == "signed-valid"
    assert Path(report["bundle_path"]).is_file()
    assert (
        verify_licensed_certification_bundle(report["bundle_path"], trusted_public_key=public_key)[
            "ok"
        ]
        is True
    )
    assert report["certification_status"] != REAL_CERTIFICATION_TEXT


REAL_CERTIFICATION_TEXT = "REAL_ASPEN" + "_CERTIFIED"


def test_signed_bundle_detects_tampering_and_wrong_key(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan, configured, env, public_key = valid_preflight(tmp_path, monkeypatch)
    preflight = certification_preflight(
        plan,
        configured,
        environment=env,
        system_name="Windows",
        machine_architecture="X64",
    )
    report = {
        "schema": "aspenops.licensed-certification-report/v1",
        "case_id": plan.case_id,
        "approved_commit": plan.approved_commit,
        "backend": plan.backend,
        "certification_status": PENDING_REAL_ASPEN_CERTIFICATION,
    }
    bundle, _ = write_licensed_certification_bundle(
        plan=plan,
        preflight=preflight,
        report=report,
        environment=env,
        output_path=tmp_path / "bundle.zip",
        signing_private_key=env["ASPENOPS_CERT_SIGNING_KEY"],
    )
    assert (
        verify_licensed_certification_bundle(bundle, trusted_public_key=public_key)[
            "verification_status"
        ]
        == "signed-valid"
    )

    wrong_private = Ed25519PrivateKey.generate()
    wrong_public = wrong_private.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    assert (
        verify_licensed_certification_bundle(bundle, trusted_public_key=wrong_public)[
            "verification_status"
        ]
        == "signed-invalid"
    )

    with (
        zipfile.ZipFile(bundle, "a", compression=zipfile.ZIP_DEFLATED) as archive,
        pytest.warns(UserWarning, match="Duplicate name"),
    ):
        archive.writestr("report.json", b'{"tampered":true}')
    assert (
        verify_licensed_certification_bundle(bundle, trusted_public_key=public_key)[
            "verification_status"
        ]
        == "structure-invalid"
    )


def test_bundle_rejects_missing_member(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan, configured, env, public_key = valid_preflight(tmp_path, monkeypatch)
    preflight = certification_preflight(
        plan,
        configured,
        environment=env,
        system_name="Windows",
        machine_architecture="X64",
    )
    bundle, _ = write_licensed_certification_bundle(
        plan=plan,
        preflight=preflight,
        report={"certification_status": PENDING_REAL_ASPEN_CERTIFICATION},
        environment=env,
        output_path=tmp_path / "complete.zip",
        signing_private_key=env["ASPENOPS_CERT_SIGNING_KEY"],
    )
    incomplete = tmp_path / "incomplete.zip"
    with zipfile.ZipFile(bundle, "r") as source, zipfile.ZipFile(incomplete, "w") as target:
        for info in source.infolist():
            if info.filename != "environment.json":
                target.writestr(info.filename, source.read(info.filename))

    verification = verify_licensed_certification_bundle(incomplete, trusted_public_key=public_key)
    assert verification["verification_status"] == "structure-invalid"
    assert verification["missing"] == ["environment.json"]


def test_plan_rejects_worker_counts_above_approved_license_slots(
    tmp_path: Path,
) -> None:
    _, _, key_id = key_material(tmp_path)
    document = plan_document(tmp_path, key_id)
    document["repeatability"]["workers"] = [1, 3]
    document["license_expectation"]["slots"] = 2

    with pytest.raises(ValueError, match="cannot exceed approved license"):
        LicensedCertificationPlan.from_document(document)


@pytest.mark.parametrize(
    ("section", "field"),
    [
        ("runtime_expectation", "progids"),
        ("license_expectation", "feature_names"),
        ("runner_expectation", "names"),
    ],
)
def test_plan_rejects_wildcard_approval_scopes(
    tmp_path: Path,
    section: str,
    field: str,
) -> None:
    _, _, key_id = key_material(tmp_path)
    document = plan_document(tmp_path, key_id)
    document[section][field] = ["*"]

    with pytest.raises(ValueError, match="wildcard"):
        LicensedCertificationPlan.from_document(document)


@pytest.mark.parametrize("pattern", [r"40\..*", ".*", "[invalid"])
def test_plan_rejects_broad_or_invalid_version_patterns(
    tmp_path: Path,
    pattern: str,
) -> None:
    _, _, key_id = key_material(tmp_path)
    document = plan_document(tmp_path, key_id)
    document["runtime_expectation"]["version_patterns"] = [pattern]

    with pytest.raises(ValueError, match="pattern|anchored"):
        LicensedCertificationPlan.from_document(document)


def test_out_of_scope_runtime_identity_fails_runtime_gate_but_stays_pending(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan, configured, env, _ = valid_preflight(tmp_path, monkeypatch)

    def mismatched_runtime(
        request: dict[str, Any],
        active_settings: Settings,
        **kwargs: Any,
    ) -> dict[str, Any]:
        report = execution_report(kwargs["workers"])
        runtime = report["runs"][0][0]["diagnostics"]["worker"]["runtime"]
        runtime["progid"] = "Apwn.Document.999.0"
        return report

    monkeypatch.setattr(licensed, "certify_batch_document", mismatched_runtime)
    report = execute_licensed_certification(
        plan,
        configured,
        output_dir=configured.state_dir / "out-of-scope",
        environment=env,
    )

    assert report["repeatability_gate_passed"] is True
    assert report["runtime_gate_passed"] is False
    assert report["certification_status"] == PENDING_REAL_ASPEN_CERTIFICATION
    assert "runtime_progid_out_of_scope" in {
        item["code"] for item in report["runtime_scope"]["violations"]
    }


def test_direct_runtime_field_cannot_forge_worker_protocol_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan, configured, env, _ = valid_preflight(tmp_path, monkeypatch)

    def forged_runtime(
        request: dict[str, Any],
        active_settings: Settings,
        **kwargs: Any,
    ) -> dict[str, Any]:
        report = execution_report(kwargs["workers"])
        worker_runtime = report["runs"][0][0]["diagnostics"].pop("worker")
        report["runs"][0][0]["diagnostics"]["runtime"] = worker_runtime["runtime"]
        return report

    monkeypatch.setattr(licensed, "certify_batch_document", forged_runtime)
    report = execute_licensed_certification(
        plan,
        configured,
        output_dir=configured.state_dir / "forged-runtime",
        environment=env,
    )

    assert report["runtime_gate_passed"] is False
    assert "runtime_identity_missing" in {
        item["code"] for item in report["runtime_scope"]["violations"]
    }


def test_output_directory_must_remain_in_approved_roots(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan, configured, env, _ = valid_preflight(tmp_path, monkeypatch)
    with pytest.raises(PermissionError, match="output"):
        execute_licensed_certification(
            plan,
            configured,
            output_dir=tmp_path.parent / "outside-certification",
            environment=env,
        )
