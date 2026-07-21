from __future__ import annotations

import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath


class ArchiveSafetyError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ArchiveLimits:
    max_archive_bytes: int = 64 * 1024 * 1024
    max_members: int = 32
    max_member_uncompressed_bytes: int = 32 * 1024 * 1024
    max_total_uncompressed_bytes: int = 64 * 1024 * 1024
    max_compression_ratio: float = 200.0

    def __post_init__(self) -> None:
        if self.max_archive_bytes < 1:
            raise ValueError("max_archive_bytes must be positive")
        if self.max_members < 1:
            raise ValueError("max_members must be positive")
        if self.max_member_uncompressed_bytes < 1:
            raise ValueError("max_member_uncompressed_bytes must be positive")
        if self.max_total_uncompressed_bytes < 1:
            raise ValueError("max_total_uncompressed_bytes must be positive")
        if self.max_compression_ratio < 1.0:
            raise ValueError("max_compression_ratio must be at least one")


DEFAULT_ARCHIVE_LIMITS = ArchiveLimits()
_SUPPORTED_COMPRESSION = {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}
_READ_CHUNK_BYTES = 64 * 1024


def _validate_member_name(name: str) -> None:
    if not name or "\x00" in name or "\\" in name or name.endswith("/"):
        raise ArchiveSafetyError(f"unsafe archive member name: {name!r}")
    path = PurePosixPath(name)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ArchiveSafetyError(f"unsafe archive member path: {name!r}")
    if path.parts and ":" in path.parts[0]:
        raise ArchiveSafetyError(f"unsafe archive member drive path: {name!r}")


def validate_archive(
    bundle: Path,
    archive: zipfile.ZipFile,
    limits: ArchiveLimits = DEFAULT_ARCHIVE_LIMITS,
) -> dict[str, zipfile.ZipInfo]:
    try:
        archive_size = bundle.stat().st_size
    except OSError as exc:
        raise ArchiveSafetyError(f"cannot stat archive: {exc}") from exc
    if archive_size > limits.max_archive_bytes:
        raise ArchiveSafetyError(
            f"archive size {archive_size} exceeds limit {limits.max_archive_bytes}"
        )

    infos = archive.infolist()
    if len(infos) > limits.max_members:
        raise ArchiveSafetyError(
            f"archive member count {len(infos)} exceeds limit {limits.max_members}"
        )
    names = [info.filename for info in infos]
    if len(names) != len(set(names)):
        raise ArchiveSafetyError("duplicate archive member names")

    total = 0
    by_name: dict[str, zipfile.ZipInfo] = {}
    for info in infos:
        _validate_member_name(info.filename)
        if info.flag_bits & 0x1:
            raise ArchiveSafetyError(f"encrypted archive member is not supported: {info.filename}")
        if info.compress_type not in _SUPPORTED_COMPRESSION:
            raise ArchiveSafetyError(
                f"unsupported compression method {info.compress_type}: {info.filename}"
            )
        if info.file_size > limits.max_member_uncompressed_bytes:
            raise ArchiveSafetyError(
                f"archive member {info.filename} exceeds uncompressed size limit"
            )
        total += info.file_size
        if total > limits.max_total_uncompressed_bytes:
            raise ArchiveSafetyError("archive total uncompressed size exceeds limit")
        if info.file_size:
            if info.compress_size <= 0:
                raise ArchiveSafetyError(f"invalid compressed size for {info.filename}")
            ratio = info.file_size / info.compress_size
            if ratio > limits.max_compression_ratio:
                raise ArchiveSafetyError(
                    f"archive member {info.filename} compression ratio {ratio:.2f} exceeds limit"
                )
        by_name[info.filename] = info
    return by_name


def read_member_bounded(
    archive: zipfile.ZipFile,
    info: zipfile.ZipInfo,
    limits: ArchiveLimits = DEFAULT_ARCHIVE_LIMITS,
) -> bytes:
    if info.file_size > limits.max_member_uncompressed_bytes:
        raise ArchiveSafetyError(f"archive member {info.filename} exceeds read limit")
    payload = bytearray()
    with archive.open(info, "r") as source:
        while True:
            chunk = source.read(min(_READ_CHUNK_BYTES, limits.max_member_uncompressed_bytes + 1))
            if not chunk:
                break
            payload.extend(chunk)
            if len(payload) > limits.max_member_uncompressed_bytes:
                raise ArchiveSafetyError(f"archive member {info.filename} exceeded read limit")
    if len(payload) != info.file_size:
        raise ArchiveSafetyError(
            f"archive member {info.filename} size mismatch: {len(payload)} != {info.file_size}"
        )
    return bytes(payload)
