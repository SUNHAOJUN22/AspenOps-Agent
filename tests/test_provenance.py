from __future__ import annotations

import json
import zipfile
from collections.abc import Callable
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from aspenops_nexus.provenance import verify_run_bundle, write_run_bundle

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "src/aspenops_nexus/data/mock-case.json"
REGISTRY = ROOT / "src/aspenops_nexus/data/node-registry.json"


def request() -> dict[str, str]:
    return {
        "model_path": str(MODEL),
        "registry_path": str(REGISTRY),
        "backend": "mock",
    }


def private_pem(key: Ed25519PrivateKey) -> bytes:
    return key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )


def public_pem(key: Ed25519PrivateKey) -> bytes:
    return key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )


def rewrite_archive(
    source_path: Path,
    target_path: Path,
    transform: Callable[[str, bytes], bytes | None],
) -> None:
    with zipfile.ZipFile(source_path) as source, zipfile.ZipFile(target_path, "w") as target:
        for name in source.namelist():
            action = transform(name, source.read(name))
            if action is not None:
                target.writestr(name, action)


def test_unsigned_bundle_roundtrip_and_tamper_detection(tmp_path: Path) -> None:
    path = write_run_bundle(
        request=request(),
        results=[{"ok": True, "values": {"x": 1.0}}],
        output_path=tmp_path / "run.zip",
    )
    verified = verify_run_bundle(path)
    assert verified["ok"]
    assert verified["verification_status"] == "unsigned-valid"
    assert verified["checks"]["signature"] is None
    assert verified["checks"]["all_ok"] is True

    tampered = tmp_path / "tampered.zip"

    def change_results(name: str, payload: bytes) -> bytes:
        if name == "results.json":
            return json.dumps([{"ok": True, "values": {"x": 2.0}}]).encode()
        return payload

    rewrite_archive(path, tampered, change_results)
    result = verify_run_bundle(tampered)
    assert result["ok"] is False
    assert result["verification_status"] == "content-invalid"
    assert result["checks"]["results_sha256"] is False
    assert result["checks"]["members"]["results.json"] is False


def test_manifest_all_ok_requires_literal_true_results(tmp_path: Path) -> None:
    path = write_run_bundle(
        request=request(),
        results=[{"ok": "false"}],  # type: ignore[list-item]
        output_path=tmp_path / "strict-all-ok.zip",
    )
    with zipfile.ZipFile(path) as archive:
        manifest = json.loads(archive.read("manifest.json"))
    assert manifest["all_ok"] is False

    verified = verify_run_bundle(path)
    assert verified["ok"] is True
    assert verified["checks"]["all_ok"] is True


def test_unsigned_manifest_all_ok_tampering_is_detected(tmp_path: Path) -> None:
    path = write_run_bundle(
        request=request(),
        results=[{"ok": False}],
        output_path=tmp_path / "run.zip",
    )
    rewritten = tmp_path / "all-ok-tampered.zip"

    def change_manifest(name: str, payload: bytes) -> bytes:
        if name != "manifest.json":
            return payload
        manifest = json.loads(payload)
        manifest["all_ok"] = True
        return json.dumps(manifest, indent=2, sort_keys=True).encode()

    rewrite_archive(path, rewritten, change_manifest)
    result = verify_run_bundle(rewritten)
    assert result["ok"] is False
    assert result["verification_status"] == "content-invalid"
    assert result["checks"]["all_ok"] is False


def test_bundle_rejects_undeclared_members(tmp_path: Path) -> None:
    path = write_run_bundle(
        request=request(),
        results=[{"ok": True}],
        output_path=tmp_path / "run.zip",
    )
    unexpected = tmp_path / "unexpected.zip"
    with zipfile.ZipFile(path) as source, zipfile.ZipFile(unexpected, "w") as target:
        for name in source.namelist():
            target.writestr(name, source.read(name))
        target.writestr("hidden.txt", b"not declared")
    result = verify_run_bundle(unexpected)
    assert result["ok"] is False
    assert result["verification_status"] == "content-invalid"
    assert result["unexpected"] == ["hidden.txt"]


def test_signed_bundle_requires_matching_trusted_public_key(tmp_path: Path) -> None:
    signing_key = Ed25519PrivateKey.generate()
    path = write_run_bundle(
        request=request(),
        results=[{"ok": True}],
        output_path=tmp_path / "signed.zip",
        signing_private_key=private_pem(signing_key),
    )
    unverified = verify_run_bundle(path)
    assert unverified["ok"] is False
    assert unverified["verification_status"] == "signed-unverified"

    verified = verify_run_bundle(path, verification_public_key=public_pem(signing_key))
    assert verified["ok"] is True
    assert verified["verification_status"] == "signed-valid"
    assert verified["checks"]["signature"] is True
    assert verified["checks"]["all_ok"] is True

    wrong_key = Ed25519PrivateKey.generate()
    rejected = verify_run_bundle(path, verification_public_key=public_pem(wrong_key))
    assert rejected["ok"] is False
    assert rejected["verification_status"] == "signed-invalid"


@pytest.mark.parametrize("key_id", ["", "x" * 129, "line\nbreak", "nul\x00key"])
def test_writer_rejects_invalid_signing_key_ids(tmp_path: Path, key_id: str) -> None:
    signing_key = Ed25519PrivateKey.generate()
    with pytest.raises(ValueError, match="signing_key_id"):
        write_run_bundle(
            request=request(),
            results=[{"ok": True}],
            output_path=tmp_path / "invalid-key-id.zip",
            signing_private_key=private_pem(signing_key),
            signing_key_id=key_id,
        )


def test_signature_detects_manifest_rewrite_after_hash_recalculation(tmp_path: Path) -> None:
    signing_key = Ed25519PrivateKey.generate()
    path = write_run_bundle(
        request=request(),
        results=[{"ok": True}],
        output_path=tmp_path / "signed.zip",
        signing_private_key=private_pem(signing_key),
    )
    rewritten = tmp_path / "rewritten.zip"

    def change_manifest(name: str, payload: bytes) -> bytes:
        if name != "manifest.json":
            return payload
        manifest = json.loads(payload)
        manifest["created_at"] = "2099-01-01T00:00:00+00:00"
        return json.dumps(manifest, indent=2, sort_keys=True).encode()

    rewrite_archive(path, rewritten, change_manifest)
    result = verify_run_bundle(
        rewritten,
        verification_public_key=public_pem(signing_key),
    )
    assert result["ok"] is False
    assert result["verification_status"] == "signed-invalid"
    assert result["checks"]["signature"] is False


def test_signed_bundle_rejects_missing_signature_member(tmp_path: Path) -> None:
    signing_key = Ed25519PrivateKey.generate()
    path = write_run_bundle(
        request=request(),
        results=[{"ok": True}],
        output_path=tmp_path / "signed.zip",
        signing_private_key=private_pem(signing_key),
    )
    missing_signature = tmp_path / "missing-signature.zip"

    def remove_signature(name: str, payload: bytes) -> bytes | None:
        return None if name == "manifest.sig" else payload

    rewrite_archive(path, missing_signature, remove_signature)
    result = verify_run_bundle(
        missing_signature,
        verification_public_key=public_pem(signing_key),
    )
    assert result["ok"] is False
    assert result["verification_status"] == "structure-invalid"
