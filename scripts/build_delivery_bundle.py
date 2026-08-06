from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import tomllib
import zipfile
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
SHA256_RE = re.compile(r"[0-9a-f]{40}")
ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
MAX_FILES = 10_000
MAX_FILE_BYTES = 64 * 1024 * 1024
MAX_TOTAL_BYTES = 512 * 1024 * 1024
EXCLUDED_PARTS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "htmlcov",
    "node_modules",
    "var",
}
EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".coverage", ".tmp"}
QUALIFICATION_PATHS = (
    "docs/ACCEPTANCE_HARDENING_QUALIFICATION.json",
    "docs/DELIVERY_QUALIFICATION.json",
)


class DeliveryBundleError(ValueError):
    pass


def _reject_constant(value: str) -> None:
    raise DeliveryBundleError(f"Non-standard JSON constant: {value}")


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DeliveryBundleError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _load_strict_json(path: Path) -> Any:
    return json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=_strict_object,
        parse_constant=_reject_constant,
    )


def _json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False, ensure_ascii=False)
        + "\n"
    ).encode("utf-8")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _safe_relative(path: Path, root: Path) -> PurePosixPath:
    try:
        relative = path.relative_to(root)
    except ValueError as exc:
        raise DeliveryBundleError(f"Path escapes source root: {path}") from exc
    pure = PurePosixPath(relative.as_posix())
    if pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
        raise DeliveryBundleError(f"Unsafe archive path: {pure}")
    return pure


def _inside(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _iter_source_files(root: Path, output_dir: Path) -> tuple[Path, ...]:
    resolved_root = root.resolve(strict=True)
    resolved_output = output_dir.resolve(strict=False)
    files: list[Path] = []
    total_bytes = 0
    for path in sorted(resolved_root.rglob("*"), key=lambda item: item.as_posix()):
        if path.is_symlink():
            raise DeliveryBundleError(f"Symlink is not allowed in delivery source: {path}")
        if not path.is_file():
            continue
        resolved = path.resolve(strict=True)
        if _inside(resolved, resolved_output):
            continue
        relative = _safe_relative(resolved, resolved_root)
        if any(part in EXCLUDED_PARTS for part in relative.parts):
            continue
        if resolved.suffix.lower() in EXCLUDED_SUFFIXES:
            continue
        size = resolved.stat().st_size
        if size > MAX_FILE_BYTES:
            raise DeliveryBundleError(f"Source file exceeds size limit: {relative}")
        total_bytes += size
        if total_bytes > MAX_TOTAL_BYTES:
            raise DeliveryBundleError("Delivery source exceeds total size limit")
        files.append(resolved)
        if len(files) > MAX_FILES:
            raise DeliveryBundleError("Delivery source exceeds file-count limit")
    if not files:
        raise DeliveryBundleError("Delivery source contains no files")
    return tuple(files)


def _zip_bytes(entries: Iterable[tuple[str, bytes]]) -> bytes:
    from io import BytesIO

    buffer = BytesIO()
    with zipfile.ZipFile(
        buffer,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
        strict_timestamps=True,
    ) as archive:
        for name, payload in sorted(entries):
            pure = PurePosixPath(name)
            if pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
                raise DeliveryBundleError(f"Unsafe ZIP member: {name}")
            info = zipfile.ZipInfo(pure.as_posix(), ZIP_TIMESTAMP)
            info.create_system = 3
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(
                info,
                payload,
                compress_type=zipfile.ZIP_DEFLATED,
                compresslevel=9,
            )
    return buffer.getvalue()


def _source_archive(root: Path, output_dir: Path, source_sha: str) -> tuple[bytes, int]:
    prefix = f"AspenOps-Agent-{source_sha[:12]}"
    entries: list[tuple[str, bytes]] = []
    for path in _iter_source_files(root, output_dir):
        relative = _safe_relative(path, root.resolve(strict=True))
        entries.append((f"{prefix}/{relative.as_posix()}", path.read_bytes()))
    return _zip_bytes(entries), len(entries)


def _package_metadata(root: Path) -> dict[str, str]:
    document = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    project = document.get("project")
    if not isinstance(project, dict):
        raise DeliveryBundleError("pyproject.toml is missing [project]")
    name = project.get("name")
    version = project.get("version")
    if not isinstance(name, str) or not name:
        raise DeliveryBundleError("Project name is missing")
    if not isinstance(version, str) or not version:
        raise DeliveryBundleError("Project version is missing")
    return {"name": name, "version": version}


def _spdx_id(name: str, version: str, index: int) -> str:
    token = re.sub(r"[^A-Za-z0-9.-]+", "-", f"{name}-{version}").strip("-.")
    return f"SPDXRef-Package-{token or 'unknown'}-{index}"


def _build_spdx(root: Path, source_sha: str, generated_at: str) -> dict[str, Any]:
    lock = tomllib.loads((root / "uv.lock").read_text(encoding="utf-8"))
    raw_packages = lock.get("package")
    if not isinstance(raw_packages, list):
        raise DeliveryBundleError("uv.lock is missing package inventory")
    inventory: set[tuple[str, str]] = set()
    for raw in raw_packages:
        if not isinstance(raw, dict):
            raise DeliveryBundleError("uv.lock package entry must be an object")
        name = raw.get("name")
        version = raw.get("version")
        if isinstance(name, str) and isinstance(version, str):
            inventory.add((name, version))
    packages: list[dict[str, Any]] = []
    describes: list[str] = []
    for index, (name, version) in enumerate(sorted(inventory), start=1):
        spdx_id = _spdx_id(name, version, index)
        describes.append(spdx_id)
        packages.append(
            {
                "SPDXID": spdx_id,
                "name": name,
                "versionInfo": version,
                "downloadLocation": "NOASSERTION",
                "filesAnalyzed": False,
                "licenseConcluded": "NOASSERTION",
                "licenseDeclared": "NOASSERTION",
                "copyrightText": "NOASSERTION",
            }
        )
    return {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": f"AspenOps-Agent-{source_sha[:12]}",
        "documentNamespace": (
            "https://github.com/SUNHAOJUN22/AspenOps-Agent/"
            f"spdx/{source_sha}"
        ),
        "creationInfo": {
            "created": generated_at,
            "creators": ["Tool: AspenOps deterministic delivery builder"],
        },
        "documentDescribes": describes,
        "packages": packages,
    }


def _evidence_index(root: Path, source_sha: str) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    external_status = "PENDING_REAL_ASPEN_CERTIFICATION"
    for relative in QUALIFICATION_PATHS:
        path = root / relative
        if not path.is_file():
            continue
        document = _load_strict_json(path)
        if not isinstance(document, dict):
            raise DeliveryBundleError(f"Evidence root must be an object: {relative}")
        status = document.get("real_aspen_status")
        if isinstance(status, str):
            external_status = status
        records.append(
            {
                "path": relative,
                "sha256": _sha256_file(path),
                "size_bytes": path.stat().st_size,
                "schema": document.get("schema"),
                "status": document.get("status"),
                "source_sha": document.get("source_sha")
                or document.get("validated_source_parent"),
            }
        )
    if not records:
        raise DeliveryBundleError("No qualification evidence is available")
    return {
        "schema": "aspenops.delivery-evidence-index/v1",
        "source_sha": source_sha,
        "real_aspen_status": external_status,
        "records": records,
    }


def _copy_dist_artifacts(root: Path, output_dir: Path) -> tuple[Path, ...]:
    dist = root / "dist"
    if not dist.is_dir():
        raise DeliveryBundleError("--include-dist requires a populated dist directory")
    copied: list[Path] = []
    for source in sorted(dist.iterdir(), key=lambda item: item.name):
        if source.is_symlink() or not source.is_file():
            continue
        if source.suffix not in {".whl", ".gz"}:
            continue
        target = output_dir / source.name
        shutil.copyfile(source, target)
        copied.append(target)
    if not copied:
        raise DeliveryBundleError("No wheel or source distribution was found in dist")
    return tuple(copied)


def _artifact_record(path: Path, output_dir: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(output_dir).as_posix(),
        "sha256": _sha256_file(path),
        "size_bytes": path.stat().st_size,
    }


def build_delivery_bundle(
    *,
    root: Path,
    output_dir: Path,
    source_sha: str,
    source_date_epoch: int = 0,
    include_dist: bool = False,
) -> dict[str, Any]:
    resolved_root = root.resolve(strict=True)
    if not SHA256_RE.fullmatch(source_sha):
        raise DeliveryBundleError("source_sha must be a 40-character lowercase Git SHA")
    if isinstance(source_date_epoch, bool) or source_date_epoch < 0:
        raise DeliveryBundleError("source_date_epoch must be a non-negative integer")
    resolved_output = output_dir.resolve(strict=False)
    if resolved_output.exists() and any(resolved_output.iterdir()):
        raise DeliveryBundleError("output directory must be empty")
    resolved_output.mkdir(parents=True, exist_ok=True)

    generated_at = (
        datetime.fromtimestamp(source_date_epoch, UTC)
        .isoformat()
        .replace("+00:00", "Z")
    )
    stem = source_sha[:12]
    source_name = f"aspenops-source-{stem}.zip"
    sbom_name = f"aspenops-sbom-{stem}.spdx.json"
    evidence_name = f"aspenops-evidence-index-{stem}.json"
    manifest_name = f"aspenops-delivery-manifest-{stem}.json"
    handover_name = f"aspenops-handover-{stem}.zip"

    source_payload, source_file_count = _source_archive(
        resolved_root, resolved_output, source_sha
    )
    source_path = resolved_output / source_name
    source_path.write_bytes(source_payload)

    sbom_path = resolved_output / sbom_name
    sbom_path.write_bytes(
        _json_bytes(_build_spdx(resolved_root, source_sha, generated_at))
    )
    evidence = _evidence_index(resolved_root, source_sha)
    evidence_path = resolved_output / evidence_name
    evidence_path.write_bytes(_json_bytes(evidence))

    payload_paths: list[Path] = [source_path, sbom_path, evidence_path]
    if include_dist:
        payload_paths.extend(_copy_dist_artifacts(resolved_root, resolved_output))

    package = _package_metadata(resolved_root)
    manifest = {
        "schema": "aspenops.delivery-manifest/v1",
        "source_sha": source_sha,
        "generated_at": generated_at,
        "package": package,
        "real_aspen_status": evidence["real_aspen_status"],
        "source_archive": {
            "path": source_name,
            "file_count": source_file_count,
            "root_prefix": f"AspenOps-Agent-{stem}",
        },
        "artifacts": [
            _artifact_record(path, resolved_output) for path in sorted(payload_paths)
        ],
        "reproducibility": {
            "source_date_epoch": source_date_epoch,
            "zip_member_timestamp": "1980-01-01T00:00:00Z",
            "sorted_entries": True,
            "normalized_file_mode": "0644",
        },
        "qualification_boundary": (
            "Software delivery PASS does not grant licensed Aspen engineering certification."
        ),
    }
    manifest_path = resolved_output / manifest_name
    manifest_path.write_bytes(_json_bytes(manifest))

    checksum_paths = sorted([*payload_paths, manifest_path], key=lambda item: item.name)
    checksums = "".join(
        f"{_sha256_file(path)}  {path.name}\n" for path in checksum_paths
    ).encode("ascii")
    checksums_path = resolved_output / "SHA256SUMS"
    checksums_path.write_bytes(checksums)

    handover_entries = [
        (path.name, path.read_bytes())
        for path in [*checksum_paths, checksums_path]
    ]
    handover_path = resolved_output / handover_name
    handover_path.write_bytes(_zip_bytes(handover_entries))
    handover_digest = _sha256_file(handover_path)
    digest_path = resolved_output / f"{handover_name}.sha256"
    digest_path.write_text(f"{handover_digest}  {handover_name}\n", encoding="ascii")

    return {
        "schema": "aspenops.delivery-build-report/v1",
        "status": "PASS",
        "source_sha": source_sha,
        "package": package,
        "real_aspen_status": evidence["real_aspen_status"],
        "source_file_count": source_file_count,
        "output_dir": str(resolved_output),
        "handover": _artifact_record(handover_path, resolved_output),
        "handover_checksum": digest_path.name,
        "artifacts": [
            _artifact_record(path, resolved_output)
            for path in sorted(resolved_output.iterdir(), key=lambda item: item.name)
            if path.is_file()
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build a deterministic AspenOps software-delivery handover package"
    )
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--source-sha", default=os.environ.get("GITHUB_SHA"))
    parser.add_argument(
        "--source-date-epoch",
        type=int,
        default=int(os.environ.get("SOURCE_DATE_EPOCH", "0")),
    )
    parser.add_argument("--include-dist", action="store_true")
    args = parser.parse_args(argv)
    if args.source_sha is None:
        parser.error("--source-sha or GITHUB_SHA is required")
    report = build_delivery_bundle(
        root=args.root,
        output_dir=args.output_dir,
        source_sha=args.source_sha,
        source_date_epoch=args.source_date_epoch,
        include_dist=args.include_dist,
    )
    print(_json_bytes(report).decode("utf-8"), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
