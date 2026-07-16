import json
import zipfile
from importlib.resources import as_file, files
from pathlib import Path

import pytest

from aspenops_nexus.hashing import sha256_file
from aspenops_nexus.provenance import verify_run_bundle, write_run_bundle


def resource(name: str) -> Path:
    with as_file(files("aspenops_nexus.data").joinpath(name)) as path:
        return Path(path)


def request() -> dict:
    return {
        "backend": "mock",
        "model_path": str(resource("mock-case.json")),
        "registry_path": str(resource("node-registry.json")),
        "writes": [],
        "reads": [],
    }


def results() -> list[dict]:
    return [
        {
            "ok": True,
            "communication_ok": True,
            "engine_ok": True,
            "converged": True,
            "feasible": True,
            "elapsed_s": 0.01,
            "diagnostics": {"worker": {"protocol": "mock-v1"}},
            "values": {},
            "units": {},
            "violations": [],
            "balance_residuals": {},
        }
    ]


def rewrite_bundle(source: Path, target: Path, replacements: dict[str, bytes]) -> None:
    with (
        zipfile.ZipFile(source) as archive,
        zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as output,
    ):
        for info in archive.infolist():
            payload = replacements.get(info.filename, archive.read(info.filename))
            output.writestr(info.filename, payload)


def test_evidence_bundle_roundtrip_is_exact_and_blocked_for_mock(tmp_path: Path) -> None:
    bundle = write_run_bundle(
        request=request(),
        results=results(),
        output_path=tmp_path / "evidence.zip",
    )
    verification = verify_run_bundle(bundle)

    assert verification["ok"] is True
    assert verification["manifest"]["physical_certification"] == "BLOCKED"
    assert verification["manifest"]["qualification_level"] == "MOCK_ONLY"
    assert verification["manifest"]["worker_protocols"] == ["mock-v1"]
    assert verification["artifact_sidecar_present"] is True
    assert verification["artifact_sha256"] == sha256_file(bundle)


def test_evidence_bundle_is_immutable_by_path(tmp_path: Path) -> None:
    path = tmp_path / "evidence.zip"
    write_run_bundle(request=request(), results=results(), output_path=path)
    with pytest.raises(FileExistsError, match="Refusing to overwrite"):
        write_run_bundle(request=request(), results=results(), output_path=path)


def test_unlisted_file_is_rejected(tmp_path: Path) -> None:
    original = write_run_bundle(
        request=request(), results=results(), output_path=tmp_path / "original.zip"
    )
    tampered = tmp_path / "extra.zip"
    rewrite_bundle(original, tampered, {})
    with zipfile.ZipFile(tampered, "a") as archive:
        archive.writestr("unlisted.txt", b"unlisted")

    verification = verify_run_bundle(tampered)
    assert verification["ok"] is False
    assert "unlisted:unlisted.txt" in verification["errors"]


def test_tampered_request_payload_is_rejected(tmp_path: Path) -> None:
    original = write_run_bundle(
        request=request(), results=results(), output_path=tmp_path / "original.zip"
    )
    tampered = tmp_path / "tampered.zip"
    altered = {**request(), "backend": "aspen_plus"}
    rewrite_bundle(
        original,
        tampered,
        {"request.json": json.dumps(altered, sort_keys=True).encode("utf-8")},
    )

    verification = verify_run_bundle(tampered)
    assert verification["ok"] is False
    assert verification["checks"]["file_sha256:request.json"] is False


def test_missing_payload_is_rejected(tmp_path: Path) -> None:
    original = write_run_bundle(
        request=request(), results=results(), output_path=tmp_path / "original.zip"
    )
    incomplete = tmp_path / "incomplete.zip"
    with zipfile.ZipFile(original) as source, zipfile.ZipFile(incomplete, "w") as target:
        for info in source.infolist():
            if info.filename != "environment.json":
                target.writestr(info.filename, source.read(info.filename))

    verification = verify_run_bundle(incomplete)
    assert verification["ok"] is False
    assert "missing:environment.json" in verification["errors"]
