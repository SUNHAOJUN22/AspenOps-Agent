from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from aspenops_nexus.hashing import canonical_hash
from aspenops_nexus.provenance import verify_run_bundle


def _legacy_members(metadata: object = None) -> dict[str, bytes]:
    request = {
        "model_path": "case.json",
        "registry_path": "registry.json",
        "metadata": metadata,
    }
    results = [{"ok": True}]
    manifest = {
        "format": "aspenops.run-bundle/v1",
        "request_sha256": canonical_hash(request),
        "results_sha256": canonical_hash(results),
        "result_count": 1,
    }
    return {
        "manifest.json": json.dumps(manifest).encode(),
        "request.json": json.dumps(request).encode(),
        "results.json": json.dumps(results).encode(),
        "environment.json": b"{}",
    }


def _archive(path: Path, members: dict[str, bytes]) -> Path:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED) as archive:
        for name, payload in members.items():
            archive.writestr(name, payload)
    return path


@pytest.mark.parametrize(
    "member", ["manifest.json", "request.json", "results.json", "environment.json"]
)
def test_small_archive_with_excessive_json_depth_returns_structured_rejection(
    tmp_path: Path, member: str
) -> None:
    members = _legacy_members()
    # Keep the real input far below the byte budget while exceeding the JSON
    # decoder's nesting limit on supported Python runtimes.
    members[member] = b"[" * 20_000 + b"0" + b"]" * 20_000
    path = _archive(tmp_path / "deep-json.zip", members)
    assert path.stat().st_size < 64 * 1024

    result = verify_run_bundle(path)

    assert result["ok"] is False
    assert result["verification_status"] == "structure-invalid"
    assert "RecursionError" in result["error"]


def test_ordinary_nested_metadata_preserves_integrity_verification(tmp_path: Path) -> None:
    metadata: object = {"source": "fixture", "value": 1.25}
    for _ in range(24):
        metadata = {"child": [metadata]}
    path = _archive(tmp_path / "nested-valid.zip", _legacy_members(metadata))

    result = verify_run_bundle(path)

    assert result["ok"] is True
    assert result["verification_status"] == "legacy-unsigned-valid"
    assert all(result["checks"].values())
