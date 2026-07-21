from __future__ import annotations

import zipfile
from pathlib import Path

from aspenops_nexus.provenance import verify_run_bundle


def test_absolute_zip_member_path_is_rejected(tmp_path: Path) -> None:
    bundle = tmp_path / "absolute.zip"
    with zipfile.ZipFile(bundle, "w") as archive:
        archive.writestr("/absolute.txt", b"unsafe")

    result = verify_run_bundle(bundle)

    assert result["ok"] is False
    assert result["verification_status"] == "structure-invalid"
    assert "unsafe archive member" in result["error"].lower()
