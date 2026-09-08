from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from pathlib import Path
from typing import Any

import pytest

from aspenops_nexus.hashing import canonical_hash, sha256_file
from aspenops_nexus.provenance import verify_run_bundle, write_run_bundle

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "src/aspenops_nexus/data/mock-case.json"
REGISTRY = ROOT / "src/aspenops_nexus/data/node-registry.json"


def _request(model: Path, registry: Path) -> dict[str, Any]:
    return {
        "model_path": str(model),
        "registry_path": str(registry),
        "backend": "mock",
    }


def _result(model_digest: str, registry_digest: str, *, worker_id: int = 0) -> dict[str, Any]:
    runtime = {
        "backend": "mock",
        "platform": "test",
        "model_path": f"private-{worker_id}",
        "process_supervision": {
            "supported": False,
            "managed": False,
            "worker_pid": 100 + worker_id,
            "error": "not windows",
        },
        "execution_artifacts": {
            "model_sha256": model_digest,
            "registry_sha256": registry_digest,
            "staged_model_path": f"stage-{worker_id}/model",
            "staged_registry_path": f"stage-{worker_id}/registry",
        },
    }
    return {
        "ok": True,
        "communication_ok": True,
        "engine_ok": True,
        "converged": True,
        "feasible": True,
        "values": {"x": 1.0},
        "units": {"x": "1"},
        "violations": [],
        "diagnostics": {
            "execution_identity": {
                "model_sha256": model_digest,
                "registry_sha256": registry_digest,
                "backend": "mock",
                "worker_generation": 0,
            },
            "worker": {"generation": 0, "runtime": runtime},
        },
        "elapsed_s": 0.1,
        "balance_residuals": {},
        "cache_source": "computed",
        "cache_hit": False,
        "request_hash": "a" * 64,
        "worker_id": worker_id,
    }


def _archive_members(path: Path) -> dict[str, bytes]:
    with zipfile.ZipFile(path) as archive:
        return {name: archive.read(name) for name in archive.namelist()}


def test_v3_bundle_uses_worker_snapshot_not_later_source_bytes(tmp_path: Path) -> None:
    model = tmp_path / "model.json"
    registry = tmp_path / "registry.json"
    shutil.copy2(MODEL, model)
    shutil.copy2(REGISTRY, registry)
    model_digest = sha256_file(model)
    registry_digest = sha256_file(registry)
    bundle = write_run_bundle(
        request=_request(model, registry),
        results=[_result(model_digest, registry_digest)],
        output_path=tmp_path / "run.zip",
    )

    model.write_text('{"replaced": true}', encoding="utf-8")
    registry.write_text('{"nodes": {}}', encoding="utf-8")

    with zipfile.ZipFile(bundle) as archive:
        manifest = json.loads(archive.read("manifest.json"))
    assert manifest["format"] == "aspenops.integrity-bundle/v3"
    assert manifest["execution_identity_bound"] is True
    assert manifest["model_sha256"] == model_digest
    assert manifest["registry_sha256"] == registry_digest
    assert manifest["model_sha256"] != sha256_file(model)
    assert manifest["registry_sha256"] != sha256_file(registry)

    verified = verify_run_bundle(bundle)
    assert verified["ok"] is True
    assert verified["verification_status"] == "unsigned-valid"
    assert all(verified["checks"]["execution_identity"].values())


def test_v3_verifier_rejects_result_identity_rewritten_under_same_manifest(
    tmp_path: Path,
) -> None:
    model_digest = sha256_file(MODEL)
    registry_digest = sha256_file(REGISTRY)
    source = write_run_bundle(
        request=_request(MODEL, REGISTRY),
        results=[_result(model_digest, registry_digest)],
        output_path=tmp_path / "source.zip",
    )
    members = _archive_members(source)
    manifest = json.loads(members["manifest.json"])
    results = json.loads(members["results.json"])
    results[0]["diagnostics"]["execution_identity"]["model_sha256"] = "f" * 64
    rewritten_results = json.dumps(
        results,
        indent=2,
        sort_keys=True,
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    manifest["results_sha256"] = canonical_hash(results)
    manifest["members"]["results.json"] = {
        "sha256": hashlib.sha256(rewritten_results).hexdigest(),
        "size": len(rewritten_results),
    }
    members["results.json"] = rewritten_results
    members["manifest.json"] = json.dumps(
        manifest,
        indent=2,
        sort_keys=True,
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    rewritten = tmp_path / "rewritten.zip"
    with zipfile.ZipFile(rewritten, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, payload in members.items():
            archive.writestr(name, payload)

    verified = verify_run_bundle(rewritten)
    assert verified["ok"] is False
    assert verified["verification_status"] == "content-invalid"
    assert verified["checks"]["execution_identity"]["model_sha256"] is False


def test_writer_rejects_mixed_runtime_identity_results(tmp_path: Path) -> None:
    model_digest = sha256_file(MODEL)
    registry_digest = sha256_file(REGISTRY)
    first = _result(model_digest, registry_digest, worker_id=0)
    second = _result(model_digest, registry_digest, worker_id=1)
    second["diagnostics"]["worker"]["runtime"]["platform"] = "different-runtime"
    with pytest.raises(ValueError, match="different execution"):
        write_run_bundle(
            request=_request(MODEL, REGISTRY),
            results=[first, second],
            output_path=tmp_path / "mixed.zip",
        )


def test_signed_writer_rejects_human_label_as_key_id(tmp_path: Path) -> None:
    pytest.importorskip("cryptography")
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    key = Ed25519PrivateKey.generate()
    private_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    with pytest.raises(ValueError, match="public-key fingerprint"):
        write_run_bundle(
            request=_request(MODEL, REGISTRY),
            results=[{"ok": True}],
            output_path=tmp_path / "bad-key-id.zip",
            signing_private_key=private_pem,
            signing_key_id="production-key",
        )


def test_verifier_returns_structure_invalid_for_nan_json(tmp_path: Path) -> None:
    bundle = write_run_bundle(
        request=_request(MODEL, REGISTRY),
        results=[{"ok": True}],
        output_path=tmp_path / "source.zip",
    )
    members = _archive_members(bundle)
    members["results.json"] = b'[{"ok": true, "value": NaN}]'
    malformed = tmp_path / "nan.zip"
    with zipfile.ZipFile(malformed, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, payload in members.items():
            archive.writestr(name, payload)
    verified = verify_run_bundle(malformed)
    assert verified["ok"] is False
    assert verified["verification_status"] == "structure-invalid"
    assert "Non-finite JSON" in verified["error"]
