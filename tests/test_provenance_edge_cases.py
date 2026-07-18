from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from aspenops_nexus.hashing import canonical_hash
from aspenops_nexus.provenance import verify_run_bundle


def test_corrupt_zip_is_structure_invalid(tmp_path: Path) -> None:
    path = tmp_path / "corrupt.zip"
    path.write_bytes(b"not a zip archive")
    result = verify_run_bundle(path)
    assert result["ok"] is False
    assert result["verification_status"] == "structure-invalid"


def test_duplicate_member_names_are_rejected(tmp_path: Path) -> None:
    path = tmp_path / "duplicates.zip"
    with pytest.warns(UserWarning, match="Duplicate name"):
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("manifest.json", b"{}")
            archive.writestr("request.json", b"{}")
            archive.writestr("request.json", b"{}")
            archive.writestr("results.json", b"[]")
            archive.writestr("environment.json", b"{}")
    result = verify_run_bundle(path)
    assert result["ok"] is False
    assert result["verification_status"] == "structure-invalid"


def test_legacy_v1_bundle_remains_readable(tmp_path: Path) -> None:
    request = {"model_path": "case.json", "registry_path": "registry.json"}
    results = [{"ok": True}]
    manifest = {
        "format": "aspenops.run-bundle/v1",
        "request_sha256": canonical_hash(request),
        "results_sha256": canonical_hash(results),
        "result_count": 1,
    }
    path = tmp_path / "legacy.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("manifest.json", json.dumps(manifest))
        archive.writestr("request.json", json.dumps(request))
        archive.writestr("results.json", json.dumps(results))
        archive.writestr("environment.json", b"{}")
    result = verify_run_bundle(path)
    assert result["ok"] is True
    assert result["verification_status"] == "legacy-unsigned-valid"


def test_missing_required_member_is_structure_invalid(tmp_path: Path) -> None:
    path = tmp_path / "missing.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("manifest.json", b"{}")
        archive.writestr("request.json", b"{}")
    result = verify_run_bundle(path)
    assert result["ok"] is False
    assert result["verification_status"] == "structure-invalid"
    assert "results.json" in result["missing"]
