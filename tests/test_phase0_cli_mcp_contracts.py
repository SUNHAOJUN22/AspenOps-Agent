from __future__ import annotations

import json
import zipfile
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import aspenops_nexus.mcp_server as mcp_module
from aspenops_nexus.cli import _load, build_parser
from aspenops_nexus.config import Settings
from aspenops_nexus.mcp_server import AspenOpsTools, _require_supported_mcp_sdk
from aspenops_nexus.provenance import write_run_bundle

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "src/aspenops_nexus/data/mock-case.json"
REGISTRY = ROOT / "src/aspenops_nexus/data/node-registry.json"


@pytest.mark.parametrize("version", ["1.9", "1.9.0", "1.12.3", "1.28.1"])
def test_mcp_sdk_accepts_only_supported_one_x_range(
    monkeypatch: pytest.MonkeyPatch,
    version: str,
) -> None:
    monkeypatch.setattr(mcp_module, "distribution_version", lambda name: version)
    assert _require_supported_mcp_sdk() == version


@pytest.mark.parametrize("version", ["1.0", "1.8.99", "2.0", "0.99", "not-a-version"])
def test_mcp_sdk_rejects_versions_outside_contract(
    monkeypatch: pytest.MonkeyPatch,
    version: str,
) -> None:
    monkeypatch.setattr(mcp_module, "distribution_version", lambda name: version)
    with pytest.raises(RuntimeError, match="MCP Python SDK|determine MCP"):
        _require_supported_mcp_sdk()


def test_cli_verify_bundle_accepts_optional_public_key_and_optimize_uses_state_default() -> None:
    parser = build_parser()
    verify = parser.parse_args(["verify-bundle", "run.zip", "--public-key", "trusted.pem"])
    assert verify.public_key == "trusted.pem"
    optimize = parser.parse_args(["optimize", "request.json"])
    assert optimize.output == "var/optimization-result.json"


def test_cli_request_loader_rejects_duplicate_keys_and_nonfinite_constants(
    tmp_path: Path,
) -> None:
    duplicate = tmp_path / "duplicate.json"
    duplicate.write_text('{"model_path":"a","model_path":"b"}', encoding="utf-8")
    with pytest.raises(ValueError, match="Duplicate request JSON key"):
        _load(duplicate)

    nonfinite = tmp_path / "nan.json"
    nonfinite.write_text('{"value":NaN}', encoding="utf-8")
    with pytest.raises(ValueError, match="non-finite"):
        _load(nonfinite)


def test_mcp_evidence_verification_uses_only_admin_trust_store(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("cryptography")
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    private = Ed25519PrivateKey.generate()
    private_pem = private.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = private.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    bundle = write_run_bundle(
        request={
            "model_path": str(MODEL),
            "registry_path": str(REGISTRY),
            "backend": "mock",
        },
        results=[{"ok": True}],
        output_path=tmp_path / "signed.zip",
        signing_private_key=private_pem,
    )
    with zipfile.ZipFile(bundle) as archive:
        manifest: dict[str, Any] = json.loads(archive.read("manifest.json"))
    key_id = manifest["signing"]["key_id"]
    trust_dir = tmp_path / "trust"
    trust_dir.mkdir()
    (trust_dir / f"{key_id}.pem").write_bytes(public_pem)
    monkeypatch.setenv("ASPENOPS_TRUSTED_KEY_DIR", str(trust_dir.resolve()))

    tools = AspenOpsTools(Settings(), SimpleNamespace())  # type: ignore[arg-type]
    verified = tools.verify_evidence_bundle(str(bundle), key_id=key_id)
    assert verified["ok"] is True
    assert verified["verification_status"] == "signed-valid"

    with pytest.raises(ValueError, match="fingerprint"):
        tools.verify_evidence_bundle(str(bundle), key_id="../trusted.pem")


def test_mcp_trust_store_must_be_absolute(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle = write_run_bundle(
        request={
            "model_path": str(MODEL),
            "registry_path": str(REGISTRY),
            "backend": "mock",
        },
        results=[{"ok": True}],
        output_path=tmp_path / "unsigned.zip",
    )
    monkeypatch.setenv("ASPENOPS_TRUSTED_KEY_DIR", "relative-keys")
    tools = AspenOpsTools(Settings(), SimpleNamespace())  # type: ignore[arg-type]
    with pytest.raises(RuntimeError, match="absolute"):
        tools.verify_evidence_bundle(str(bundle), key_id="a" * 32)
