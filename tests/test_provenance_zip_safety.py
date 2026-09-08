from __future__ import annotations

import json
import struct
import warnings
import zipfile
from pathlib import Path
from typing import Any

import pytest

from aspenops_nexus.archive_safety import ArchiveLimits
from aspenops_nexus.provenance import verify_run_bundle, write_run_bundle

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "src/aspenops_nexus/data/mock-case.json"
REGISTRY = ROOT / "src/aspenops_nexus/data/node-registry.json"


def request() -> dict[str, Any]:
    return {
        "backend": "mock",
        "model_path": str(MODEL),
        "registry_path": str(REGISTRY),
    }


def valid_bundle(tmp_path: Path) -> Path:
    return write_run_bundle(
        request=request(),
        results=[{"ok": True, "values": {"x": 1.0}}],
        output_path=tmp_path / "valid.zip",
    )


def members(path: Path) -> dict[str, bytes]:
    with zipfile.ZipFile(path) as archive:
        return {name: archive.read(name) for name in archive.namelist()}


def write_members(
    path: Path,
    payloads: dict[str, bytes],
    *,
    compression: int = zipfile.ZIP_DEFLATED,
) -> Path:
    with zipfile.ZipFile(path, "w", compression=compression) as archive:
        for name, payload in payloads.items():
            archive.writestr(name, payload)
    return path


def set_encrypted_flag(path: Path) -> None:
    data = bytearray(path.read_bytes())
    cursor = 0
    while True:
        cursor = data.find(b"PK\x03\x04", cursor)
        if cursor < 0:
            break
        flags = struct.unpack_from("<H", data, cursor + 6)[0]
        struct.pack_into("<H", data, cursor + 6, flags | 0x1)
        cursor += 4
    cursor = 0
    while True:
        cursor = data.find(b"PK\x01\x02", cursor)
        if cursor < 0:
            break
        flags = struct.unpack_from("<H", data, cursor + 8)[0]
        struct.pack_into("<H", data, cursor + 8, flags | 0x1)
        cursor += 4
    path.write_bytes(data)


def assert_structure_invalid(result: dict[str, Any], text: str) -> None:
    assert result["ok"] is False
    assert result["verification_status"] == "structure-invalid"
    assert text.lower() in str(result.get("error", "")).lower()


def test_valid_unsigned_bundle_remains_accepted(tmp_path: Path) -> None:
    result = verify_run_bundle(valid_bundle(tmp_path))
    assert result["ok"] is True
    assert result["verification_status"] == "unsigned-valid"


def test_archive_size_member_count_and_member_size_limits(tmp_path: Path) -> None:
    bundle = valid_bundle(tmp_path)
    assert_structure_invalid(
        verify_run_bundle(bundle, limits=ArchiveLimits(max_archive_bytes=1)),
        "archive size",
    )
    assert_structure_invalid(
        verify_run_bundle(bundle, limits=ArchiveLimits(max_members=2)),
        "member count",
    )
    assert_structure_invalid(
        verify_run_bundle(
            bundle,
            limits=ArchiveLimits(max_member_uncompressed_bytes=8),
        ),
        "uncompressed size",
    )
    assert_structure_invalid(
        verify_run_bundle(
            bundle,
            limits=ArchiveLimits(max_total_uncompressed_bytes=16),
        ),
        "total uncompressed",
    )


def test_high_compression_ratio_and_unsupported_compression_are_rejected(
    tmp_path: Path,
) -> None:
    payloads = members(valid_bundle(tmp_path))
    payloads["large-zeroes.bin"] = b"0" * 20_000
    compressed = write_members(tmp_path / "ratio.zip", payloads)
    assert_structure_invalid(
        verify_run_bundle(
            compressed,
            limits=ArchiveLimits(max_compression_ratio=2.0),
        ),
        "compression ratio",
    )

    unsupported = write_members(
        tmp_path / "bzip2.zip",
        members(valid_bundle(tmp_path)),
        compression=zipfile.ZIP_BZIP2,
    )
    assert_structure_invalid(verify_run_bundle(unsupported), "unsupported compression")


def test_unsafe_duplicate_and_encrypted_members_are_rejected(tmp_path: Path) -> None:
    payloads = members(valid_bundle(tmp_path))
    payloads["../escape.txt"] = b"escape"
    assert_structure_invalid(
        verify_run_bundle(write_members(tmp_path / "unsafe.zip", payloads)),
        "unsafe archive member",
    )

    duplicate = tmp_path / "duplicate.zip"
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with zipfile.ZipFile(duplicate, "w") as archive:
            archive.writestr("manifest.json", b"{}")
            archive.writestr("manifest.json", b"{}")
    assert_structure_invalid(verify_run_bundle(duplicate), "duplicate")

    encrypted = valid_bundle(tmp_path)
    set_encrypted_flag(encrypted)
    assert_structure_invalid(verify_run_bundle(encrypted), "encrypted")


def test_json_root_types_and_signing_structure_are_validated(tmp_path: Path) -> None:
    payloads = members(valid_bundle(tmp_path))
    payloads["request.json"] = b"[]"
    malformed_request = write_members(tmp_path / "request-root.zip", payloads)
    assert_structure_invalid(verify_run_bundle(malformed_request), "request.json root")

    payloads = members(valid_bundle(tmp_path))
    manifest = json.loads(payloads["manifest.json"])
    manifest["signing"] = "signed"
    payloads["manifest.json"] = json.dumps(manifest).encode("utf-8")
    malformed_signing = write_members(tmp_path / "signing.zip", payloads)
    assert_structure_invalid(verify_run_bundle(malformed_signing), "signing")


def test_valid_signed_bundle_remains_accepted(tmp_path: Path) -> None:
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
        request=request(),
        results=[{"ok": True}],
        output_path=tmp_path / "signed.zip",
        signing_private_key=private_pem,
    )
    result = verify_run_bundle(bundle, verification_public_key=public_pem)
    assert result["ok"] is True
    assert result["verification_status"] == "signed-valid"
