from __future__ import annotations

import io
import zipfile
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from aspenops_nexus.archive_safety import (
    ArchiveLimits,
    ArchiveSafetyError,
    _validate_member_name,
    read_member_bounded,
    validate_archive,
)
from aspenops_nexus.provenance import (
    _validate_member_declarations,
    _validate_signing,
    _verify_v1,
)


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"max_archive_bytes": 0}, "max_archive_bytes"),
        ({"max_members": 0}, "max_members"),
        ({"max_member_uncompressed_bytes": 0}, "max_member_uncompressed_bytes"),
        ({"max_total_uncompressed_bytes": 0}, "max_total_uncompressed_bytes"),
        ({"max_compression_ratio": 0.5}, "max_compression_ratio"),
    ],
)
def test_archive_limits_reject_nonpositive_values(
    kwargs: dict[str, int | float],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        ArchiveLimits(**kwargs)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "name",
    ["", "nul\x00name", r"folder\file", "folder/", "/absolute", "../escape", "C:/drive"],
)
def test_archive_member_names_fail_closed(name: str) -> None:
    with pytest.raises(ArchiveSafetyError, match="unsafe archive member"):
        _validate_member_name(name)


def test_validate_archive_reports_stat_failure(tmp_path: Path) -> None:
    missing = tmp_path / "missing.zip"
    archive = cast(zipfile.ZipFile, SimpleNamespace(infolist=lambda: []))
    with pytest.raises(ArchiveSafetyError, match="cannot stat archive"):
        validate_archive(missing, archive)


class FakeArchiveMetadata:
    def __init__(self, infos: list[Any]) -> None:
        self.infos = infos

    def infolist(self) -> list[Any]:
        return self.infos


def info(
    name: str,
    *,
    file_size: int = 1,
    compress_size: int = 1,
    compress_type: int = zipfile.ZIP_STORED,
    flag_bits: int = 0,
) -> Any:
    return SimpleNamespace(
        filename=name,
        file_size=file_size,
        compress_size=compress_size,
        compress_type=compress_type,
        flag_bits=flag_bits,
    )


def metadata_bundle(tmp_path: Path) -> Path:
    path = tmp_path / "metadata.zip"
    path.write_bytes(b"x")
    return path


@pytest.mark.parametrize(
    ("infos", "limits", "message"),
    [
        ([info("a"), info("a")], ArchiveLimits(), "duplicate"),
        ([info("a", flag_bits=1)], ArchiveLimits(), "encrypted"),
        ([info("a", compress_type=zipfile.ZIP_LZMA)], ArchiveLimits(), "unsupported"),
        (
            [info("a", file_size=2)],
            ArchiveLimits(max_member_uncompressed_bytes=1),
            "uncompressed size",
        ),
        (
            [info("a"), info("b")],
            ArchiveLimits(max_total_uncompressed_bytes=1),
            "total uncompressed",
        ),
        ([info("a", compress_size=0)], ArchiveLimits(), "invalid compressed size"),
        (
            [info("a", file_size=100, compress_size=1)],
            ArchiveLimits(max_compression_ratio=10.0),
            "compression ratio",
        ),
    ],
)
def test_validate_archive_rejects_malicious_metadata(
    tmp_path: Path,
    infos: list[Any],
    limits: ArchiveLimits,
    message: str,
) -> None:
    archive = cast(zipfile.ZipFile, FakeArchiveMetadata(infos))
    with pytest.raises(ArchiveSafetyError, match=message):
        validate_archive(metadata_bundle(tmp_path), archive, limits)


class FakeReadArchive:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    def open(self, info_value: Any, mode: str) -> Any:
        del info_value
        assert mode == "r"
        return nullcontext(io.BytesIO(self.payload))


def test_read_member_bounded_rejects_declared_and_actual_oversize() -> None:
    limits = ArchiveLimits(max_member_uncompressed_bytes=2)
    oversized = info("a", file_size=3)
    archive = cast(zipfile.ZipFile, FakeReadArchive(b"abc"))
    with pytest.raises(ArchiveSafetyError, match="exceeds read limit"):
        read_member_bounded(archive, oversized, limits)

    declared_small = info("a", file_size=2)
    with pytest.raises(ArchiveSafetyError, match="exceeded read limit"):
        read_member_bounded(archive, declared_small, limits)


def test_read_member_bounded_rejects_size_mismatch() -> None:
    archive = cast(zipfile.ZipFile, FakeReadArchive(b"a"))
    with pytest.raises(ArchiveSafetyError, match="size mismatch"):
        read_member_bounded(archive, info("a", file_size=2))


@pytest.mark.parametrize(
    ("value", "message"),
    [
        ([], "must be an object"),
        ({"manifest.json": {"sha256": "0" * 64, "size": 1}}, "reserved"),
        ({"x": []}, "declaration must be an object"),
        ({"x": {"sha256": "bad", "size": 1}}, "invalid sha256"),
        ({"x": {"sha256": "0" * 64, "size": True}}, "invalid size"),
        ({"x": {"sha256": "0" * 64, "size": -1}}, "invalid size"),
    ],
)
def test_member_declarations_reject_malformed_shapes(value: Any, message: str) -> None:
    declarations, error = _validate_member_declarations(value)
    assert declarations is None
    assert error is not None and message in error


def test_member_declarations_accept_valid_record() -> None:
    declarations, error = _validate_member_declarations(
        {"x": {"sha256": "0" * 64, "size": 0}}
    )
    assert error is None
    assert declarations == {"x": {"sha256": "0" * 64, "size": 0}}


@pytest.mark.parametrize(
    ("value", "message"),
    [
        ([], "must be an object"),
        ({"status": "unsigned", "algorithm": "Ed25519", "key_id": None}, "must not"),
        ({"status": "signed", "algorithm": "RSA", "key_id": "x"}, "Ed25519"),
        ({"status": "signed", "algorithm": "Ed25519", "key_id": ""}, "key_id"),
        ({"status": "signed", "algorithm": "Ed25519", "key_id": "x" * 129}, "key_id"),
        ({"status": "mystery", "algorithm": None, "key_id": None}, "status"),
    ],
)
def test_signing_metadata_rejects_ambiguous_shapes(value: Any, message: str) -> None:
    signing, error = _validate_signing(value)
    assert signing is None
    assert error is not None and message in error


def test_signing_metadata_accepts_unsigned_and_signed() -> None:
    unsigned, unsigned_error = _validate_signing(
        {"status": "unsigned", "algorithm": None, "key_id": None}
    )
    signed, signed_error = _validate_signing(
        {"status": "signed", "algorithm": "Ed25519", "key_id": "key"}
    )
    assert unsigned_error is None
    assert unsigned == {"status": "unsigned", "algorithm": None, "key_id": None}
    assert signed_error is None
    assert signed == {"status": "signed", "algorithm": "Ed25519", "key_id": "key"}


def test_legacy_bundle_verification_covers_valid_and_invalid_hashes() -> None:
    request = {"x": 1}
    results = [{"ok": True}]
    from aspenops_nexus.hashing import canonical_hash

    manifest = {
        "request_sha256": canonical_hash(request),
        "results_sha256": canonical_hash(results),
        "result_count": 1,
    }
    assert _verify_v1(manifest, request, results)["verification_status"] == "legacy-unsigned-valid"
    manifest["result_count"] = 2
    assert _verify_v1(manifest, request, results)["verification_status"] == "content-invalid"
