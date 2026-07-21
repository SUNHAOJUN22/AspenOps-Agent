from __future__ import annotations

import base64
import hashlib
import json
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Callable

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

import aspenops_nexus.licensed_certification as licensed
from aspenops_nexus.config import Settings
from aspenops_nexus.hashing import canonical_hash, sha256_file
from aspenops_nexus.licensed_certification import (
    LicensedCertificationPlan,
    certification_preflight,
    verify_licensed_certification_bundle,
    write_licensed_certification_bundle,
)


def private_key(tmp_path: Path) -> tuple[Path, bytes, str]:
    key = Ed25519PrivateKey.generate()
    path = tmp_path / "private.pem"
    path.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    public = key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return path, public, licensed._key_id(key.public_key())


def plan_document(
    tmp_path: Path,
    key_id: str,
    *,
    approved_at: str = "2026-07-20T00:00:00+09:00",
) -> dict[str, Any]:
    model = tmp_path / "case.bkp"
    registry = tmp_path / "registry.json"
    model.write_bytes(b"model")
    registry.write_text(
        json.dumps(
            {
                "nodes": {
                    "x": {
                        "backend": "aspen_plus",
                        "access": "read",
                        "paths": ["\\Data\\x"],
                    },
                    "flow.in": {
                        "backend": "aspen_plus",
                        "access": "read",
                        "paths": ["\\Data\\in"],
                    },
                    "flow.out": {
                        "backend": "aspen_plus",
                        "access": "read",
                        "paths": ["\\Data\\out"],
                    },
                }
            }
        ),
        encoding="utf-8",
    )
    return {
        "schema": licensed.PLAN_SCHEMA,
        "case_id": "case-001",
        "approved_commit": "a" * 40,
        "backend": "aspen_plus",
        "request": {
            "backend": "aspen_plus",
            "model_path": str(model),
            "registry_path": str(registry),
            "workers": 1,
            "reads": [{"key": "x"}],
            "balances": [
                {
                    "name": "mass",
                    "terms": [
                        {"key": "flow.in", "coefficient": 1.0},
                        {"key": "flow.out", "coefficient": -1.0},
                    ],
                }
            ],
            "points": [{}],
        },
        "approved_artifacts": {
            "model_sha256": sha256_file(model),
            "registry_sha256": sha256_file(registry),
        },
        "repeatability": {
            "repeats": 2,
            "workers": [1],
            "default_tolerance": {"abs_tol": 1e-6, "rel_tol": 1e-6},
            "output_tolerances": {
                "x": {"abs_tol": 1e-5, "rel_tol": 1e-5},
                "balance:mass:residual": {"abs_tol": 1e-6, "rel_tol": 0.0},
            },
        },
        "engineering_acceptance": {
            "status": "approved",
            "reviewer": "engineer",
            "approved_at": approved_at,
            "scope": "Approved test scope",
        },
        "runtime_expectation": {
            "progids": ["Apwn.Document.40.0"],
            "version_patterns": ["^40\\."],
        },
        "license_expectation": {
            "slots": 1,
            "server_identity": "license-server",
            "feature_names": ["ASPEN_PLUS"],
        },
        "runner_expectation": {
            "names": ["runner-01"],
            "architecture": "X64",
        },
        "signing": {"required": True, "key_id": key_id},
    }


def plan_and_bundle(
    tmp_path: Path,
) -> tuple[LicensedCertificationPlan, Path, bytes, Path]:
    private_path, public, key_id = private_key(tmp_path)
    plan = LicensedCertificationPlan.from_document(plan_document(tmp_path, key_id))
    plan_hash = canonical_hash(plan.to_dict())
    preflight = {
        "schema": licensed.PREFLIGHT_SCHEMA,
        "ready": True,
        "certification_status": licensed.PENDING_REAL_ASPEN_CERTIFICATION,
        "evidence": {"plan_sha256": plan_hash},
    }
    report = {
        "schema": licensed.REPORT_SCHEMA,
        "case_id": plan.case_id,
        "approved_commit": plan.approved_commit,
        "backend": plan.backend,
        "certification_status": licensed.PENDING_REAL_ASPEN_CERTIFICATION,
    }
    environment = {
        "GITHUB_SHA": plan.approved_commit,
        "RUNNER_NAME": "runner-01",
        "RUNNER_ARCH": "X64",
        "RUNNER_ENVIRONMENT": "self-hosted",
        "ASPENOPS_LICENSE_SERVER_IDENTITY": "license-server",
        "ASPENOPS_LICENSE_FEATURES": "ASPEN_PLUS",
    }
    bundle, _ = write_licensed_certification_bundle(
        plan=plan,
        preflight=preflight,
        report=report,
        environment=environment,
        output_path=tmp_path / "bundle.zip",
        signing_private_key=private_path,
    )
    return plan, private_path, public, bundle


def rewrite_signed_bundle(
    bundle: Path,
    private_path: Path,
    output: Path,
    mutate: Callable[[dict[str, bytes], dict[str, Any]], None],
) -> Path:
    with zipfile.ZipFile(bundle, "r") as archive:
        members = {info.filename: archive.read(info.filename) for info in archive.infolist()}
    manifest = json.loads(members["manifest.json"])
    mutate(members, manifest)
    key = serialization.load_pem_private_key(private_path.read_bytes(), password=None)
    assert isinstance(key, Ed25519PrivateKey)
    manifest_payload = licensed._pretty_bytes(manifest)
    members["manifest.json"] = manifest_payload
    members["manifest.sig"] = base64.b64encode(
        key.sign(licensed._canonical_bytes(manifest))
    )
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, payload in members.items():
            archive.writestr(name, payload)
    return output


def update_member(
    members: dict[str, bytes], manifest: dict[str, Any], name: str, value: Any
) -> None:
    payload = licensed._pretty_bytes(value)
    members[name] = payload
    manifest["members"][name] = {
        "sha256": hashlib.sha256(payload).hexdigest(),
        "size": len(payload),
    }


def test_valid_bundle_passes_cross_file_semantic_checks(tmp_path: Path) -> None:
    _, _, public, bundle = plan_and_bundle(tmp_path)

    report = verify_licensed_certification_bundle(
        bundle, trusted_public_key=public
    )

    assert report["verification_status"] == "signed-valid"
    assert all(report["member_checks"].values())
    assert all(report["semantic_checks"].values())


def test_resigned_manifest_with_extra_declaration_is_structure_invalid(
    tmp_path: Path,
) -> None:
    _, private_path, public, bundle = plan_and_bundle(tmp_path)

    def mutate(members: dict[str, bytes], manifest: dict[str, Any]) -> None:
        del members
        manifest["members"]["extra.json"] = {"sha256": "0" * 64, "size": 0}

    rewritten = rewrite_signed_bundle(
        bundle, private_path, tmp_path / "extra-declaration.zip", mutate
    )
    report = verify_licensed_certification_bundle(
        rewritten, trusted_public_key=public
    )

    assert report["verification_status"] == "structure-invalid"
    assert report["manifest_member_unexpected"] == ["extra.json"]


def test_key_id_file_must_match_signed_manifest(tmp_path: Path) -> None:
    _, private_path, public, bundle = plan_and_bundle(tmp_path)

    def mutate(members: dict[str, bytes], manifest: dict[str, Any]) -> None:
        del manifest
        members["signing-key-id.txt"] = b"0" * 32

    rewritten = rewrite_signed_bundle(
        bundle, private_path, tmp_path / "wrong-key-id.zip", mutate
    )
    report = verify_licensed_certification_bundle(
        rewritten, trusted_public_key=public
    )

    assert report["verification_status"] == "structure-invalid"


def test_signed_nonobject_member_is_still_structure_invalid(tmp_path: Path) -> None:
    _, private_path, public, bundle = plan_and_bundle(tmp_path)

    def mutate(members: dict[str, bytes], manifest: dict[str, Any]) -> None:
        update_member(members, manifest, "preflight.json", [])

    rewritten = rewrite_signed_bundle(
        bundle, private_path, tmp_path / "array-root.zip", mutate
    )
    report = verify_licensed_certification_bundle(
        rewritten, trusted_public_key=public
    )

    assert report["verification_status"] == "structure-invalid"
    assert "root must be an object" in report["error"]


def test_signed_cross_scope_commit_mismatch_is_content_invalid(tmp_path: Path) -> None:
    _, private_path, public, bundle = plan_and_bundle(tmp_path)

    def mutate(members: dict[str, bytes], manifest: dict[str, Any]) -> None:
        environment = json.loads(members["environment.json"])
        environment["git_commit"] = "b" * 40
        update_member(members, manifest, "environment.json", environment)

    rewritten = rewrite_signed_bundle(
        bundle, private_path, tmp_path / "wrong-commit.zip", mutate
    )
    report = verify_licensed_certification_bundle(
        rewritten, trusted_public_key=public
    )

    assert report["verification_status"] == "content-invalid"
    assert report["semantic_checks"]["environment_commit"] is False


@pytest.mark.parametrize(
    "mutation",
    [
        lambda manifest: manifest.update(unexpected=True),
        lambda manifest: manifest["signing"].update(algorithm="RSA"),
        lambda manifest: manifest["members"]["plan.json"].update(size=True),
    ],
)
def test_resigned_malformed_manifest_is_rejected(
    tmp_path: Path,
    mutation: Callable[[dict[str, Any]], None],
) -> None:
    _, private_path, public, bundle = plan_and_bundle(tmp_path)

    def mutate(members: dict[str, bytes], manifest: dict[str, Any]) -> None:
        del members
        mutation(manifest)

    rewritten = rewrite_signed_bundle(
        bundle, private_path, tmp_path / f"malformed-{id(mutation)}.zip", mutate
    )
    report = verify_licensed_certification_bundle(
        rewritten, trusted_public_key=public
    )

    assert report["verification_status"] == "structure-invalid"


def test_plan_rejects_tolerance_keys_outside_request(tmp_path: Path) -> None:
    _, _, key_id = private_key(tmp_path)
    document = plan_document(tmp_path, key_id)
    document["repeatability"]["output_tolerances"]["unrequested.output"] = {
        "abs_tol": 1.0,
        "rel_tol": 0.0,
    }

    with pytest.raises(ValueError, match="outside the request"):
        LicensedCertificationPlan.from_document(document)


def preflight_settings(tmp_path: Path) -> Settings:
    return Settings(
        backend="aspen_plus",
        allowed_roots=(tmp_path.resolve(),),
        state_dir=(tmp_path / "state").resolve(),
        license_slots=1,
        max_workers=1,
    )


def preflight_environment(tmp_path: Path, private_path: Path) -> dict[str, str]:
    workspace = tmp_path / "workspace"
    workspace.mkdir(exist_ok=True)
    return {
        "GITHUB_SHA": "a" * 40,
        "GITHUB_WORKSPACE": str(workspace),
        "RUNNER_NAME": "runner-01",
        "RUNNER_ARCH": "X64",
        "RUNNER_ENVIRONMENT": "self-hosted",
        "ASPENOPS_LICENSE_SERVER_IDENTITY": "license-server",
        "ASPENOPS_LICENSE_FEATURES": "ASPEN_PLUS",
        "ASPENOPS_CERT_SIGNING_KEY": str(private_path),
    }


def compatibility() -> dict[str, Any]:
    return {
        "aspen_plus": [
            {
                "progid": "Apwn.Document.40.0",
                "registry_view": "64-bit",
            }
        ]
    }


def test_preflight_rejects_future_approval_and_32bit_python(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    private_path, _, key_id = private_key(tmp_path)
    future = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    plan = LicensedCertificationPlan.from_document(
        plan_document(tmp_path, key_id, approved_at=future)
    )
    monkeypatch.setattr(
        licensed,
        "dry_run_document",
        lambda request, settings: {"ok": True},
    )

    report = certification_preflight(
        plan,
        preflight_settings(tmp_path),
        environment=preflight_environment(tmp_path, private_path),
        system_name="Windows",
        machine_architecture="X64",
        pointer_bits=32,
        current_time=datetime.now(UTC),
        compatibility=compatibility(),
    )

    codes = {item["code"] for item in report["blockers"]}
    assert "engineering_approval_in_future" in codes
    assert "python_64bit_required" in codes
    assert report["ready"] is False
