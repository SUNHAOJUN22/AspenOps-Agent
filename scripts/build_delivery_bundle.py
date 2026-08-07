from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import tomllib
import zipfile
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
GIT_SHA_RE = re.compile(r"[0-9a-f]{40}")
ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
MAX_FILES = 10_000
MAX_FILE_BYTES = 64 * 1024 * 1024
MAX_TOTAL_BYTES = 512 * 1024 * 1024
EXPECTED_REAL_ASPEN_STATUS = "PENDING_REAL_ASPEN_CERTIFICATION"
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
EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".tmp"}
EXCLUDED_FILE_NAMES = {".coverage"}
GENERATED_CURRENT_QUALIFICATION = "docs/DELIVERY_QUALIFICATION.json"
EXCLUDED_SOURCE_PATHS = {GENERATED_CURRENT_QUALIFICATION}
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
        json.dumps(
            value,
            indent=2,
            sort_keys=True,
            allow_nan=False,
            ensure_ascii=False,
        )
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
    if (resolved_root / ".git").exists():
        tracked = _git_output(resolved_root, "ls-files", "-z")
        candidates = [
            resolved_root / name
            for name in tracked.split("\0")
            if name
        ]
    else:
        candidates = sorted(resolved_root.rglob("*"), key=lambda item: item.as_posix())
    for path in candidates:
        if path.is_symlink():
            raise DeliveryBundleError(f"Symlink is not allowed in delivery source: {path}")
        if not path.is_file():
            if (resolved_root / ".git").exists():
                raise DeliveryBundleError(f"Tracked delivery path is not a file: {path}")
            continue
        resolved = path.resolve(strict=True)
        if _inside(resolved, resolved_output):
            continue
        relative = _safe_relative(resolved, resolved_root)
        if relative.as_posix() in EXCLUDED_SOURCE_PATHS:
            continue
        if any(part in EXCLUDED_PARTS for part in relative.parts):
            continue
        if resolved.name in EXCLUDED_FILE_NAMES or resolved.suffix.lower() in EXCLUDED_SUFFIXES:
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


def _evidence_index(
    root: Path,
    source_sha: str,
    qualified_tree_sha: str | None = None,
) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    for relative in QUALIFICATION_PATHS:
        path = root / relative
        if not path.is_file():
            continue
        document = _load_strict_json(path)
        if not isinstance(document, dict):
            raise DeliveryBundleError(f"Evidence root must be an object: {relative}")
        expected_schema = (
            "aspenops.delivery-qualification/v2"
            if relative == GENERATED_CURRENT_QUALIFICATION
            else "aspenops.acceptance-hardening-qualification/v2"
        )
        if document.get("schema") != expected_schema or document.get("status") != "PASS":
            raise DeliveryBundleError(f"Qualification evidence is not PASS: {relative}")
        status = document.get("real_aspen_status")
        if status != EXPECTED_REAL_ASPEN_STATUS:
            raise DeliveryBundleError(
                f"Evidence must preserve {EXPECTED_REAL_ASPEN_STATUS}: {relative}"
            )
        passed = document.get("passed")
        coverage = document.get("branch_coverage_percent")
        if isinstance(passed, bool) or not isinstance(passed, int) or passed < 1200:
            raise DeliveryBundleError(f"Qualification test floor is not met: {relative}")
        if (
            isinstance(coverage, bool)
            or not isinstance(coverage, int | float)
            or not math.isfinite(float(coverage))
            or float(coverage) < 95.0
        ):
            raise DeliveryBundleError(f"Qualification coverage floor is not met: {relative}")
        if relative == GENERATED_CURRENT_QUALIFICATION:
            if document.get("validated_source_parent") != source_sha:
                raise DeliveryBundleError(
                    "Current delivery qualification does not match requested source SHA"
                )
            if (
                qualified_tree_sha is not None
                and document.get("qualified_content_tree_sha") != qualified_tree_sha
            ):
                raise DeliveryBundleError(
                    "Current delivery qualification does not match checked-out Git tree"
                )
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
        "real_aspen_status": EXPECTED_REAL_ASPEN_STATUS,
        "records": records,
    }


def _git_output(root: Path, *args: str) -> str:
    try:
        completed = subprocess.run(
            ["git", "-C", str(root), *args],
            check=True,
            capture_output=True,
            text=True,
            shell=False,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise DeliveryBundleError(f"Git identity check failed: {' '.join(args)}") from exc
    return completed.stdout.strip()


def _dirty_path_allowed(path: str) -> bool:
    normalized = PurePosixPath(path.strip('"'))
    if normalized.as_posix() == GENERATED_CURRENT_QUALIFICATION:
        return True
    if normalized.parts and normalized.parts[0] in EXCLUDED_PARTS:
        return True
    return (
        normalized.name in EXCLUDED_FILE_NAMES
        or normalized.suffix.lower() in EXCLUDED_SUFFIXES
    )


def _verify_git_source_identity(root: Path, source_sha: str) -> bool:
    if not (root / ".git").exists():
        return False
    head = _git_output(root, "rev-parse", "HEAD")
    if head != source_sha:
        raise DeliveryBundleError(
            f"source_sha does not match checked-out HEAD: expected {head}, received {source_sha}"
        )
    status = _git_output(root, "status", "--porcelain=v1", "--untracked-files=all")
    dirty: list[str] = []
    for line in status.splitlines():
        if len(line) < 4:
            dirty.append(line)
            continue
        candidate = line[3:]
        if " -> " in candidate:
            candidate = candidate.rsplit(" -> ", 1)[1]
        if not _dirty_path_allowed(candidate):
            dirty.append(line)
    if dirty:
        raise DeliveryBundleError(
            "delivery source contains uncommitted files: " + "; ".join(dirty[:10])
        )
    return True


def _is_distribution(path: Path) -> bool:
    return path.name.endswith(".whl") or path.name.endswith(".tar.gz")


def _copy_dist_artifacts(root: Path, output_dir: Path) -> tuple[Path, ...]:
    dist = root / "dist"
    if not dist.is_dir():
        raise DeliveryBundleError("--include-dist requires a populated dist directory")
    copied: list[Path] = []
    total_bytes = 0
    for source in sorted(dist.iterdir(), key=lambda item: item.name):
        if source.is_symlink() or not source.is_file() or not _is_distribution(source):
            continue
        size = source.stat().st_size
        if size > MAX_FILE_BYTES:
            raise DeliveryBundleError(f"Distribution exceeds size limit: {source.name}")
        total_bytes += size
        if total_bytes > MAX_TOTAL_BYTES:
            raise DeliveryBundleError("Distribution payload exceeds total size limit")
        target = output_dir / source.name
        shutil.copyfile(source, target)
        copied.append(target)
    if not copied:
        raise DeliveryBundleError("No wheel or source distribution was found in dist")
    return tuple(copied)


def _artifact_record(path: Path, output_dir: Path) -> dict[str, Any]:
    try:
        relative = path.relative_to(output_dir)
    except ValueError as exc:
        raise DeliveryBundleError(f"Artifact escapes output directory: {path}") from exc
    return {
        "path": relative.as_posix(),
        "sha256": _sha256_file(path),
        "size_bytes": path.stat().st_size,
    }


def _prepare_output_dir(output_dir: Path) -> Path:
    resolved_output = output_dir.resolve(strict=False)
    if resolved_output.exists():
        if not resolved_output.is_dir():
            raise DeliveryBundleError("output path must be a directory")
        if any(resolved_output.iterdir()):
            raise DeliveryBundleError("output directory must be empty")
    resolved_output.mkdir(parents=True, exist_ok=True)
    return resolved_output


def build_delivery_bundle(
    *,
    root: Path,
    output_dir: Path,
    source_sha: str,
    source_date_epoch: int = 0,
    include_dist: bool = False,
) -> dict[str, Any]:
    resolved_root = root.resolve(strict=True)
    if not GIT_SHA_RE.fullmatch(source_sha):
        raise DeliveryBundleError(
            "source_sha must be a 40-character lowercase hexadecimal Git SHA"
        )
    if (
        isinstance(source_date_epoch, bool)
        or not isinstance(source_date_epoch, int)
        or source_date_epoch < 0
    ):
        raise DeliveryBundleError("source_date_epoch must be a non-negative integer")
    git_identity_verified = _verify_git_source_identity(resolved_root, source_sha)
    qualified_tree_sha: str | None = None
    if git_identity_verified:
        qualified_tree_sha = _git_output(resolved_root, "rev-parse", "HEAD^{tree}")
        if not GIT_SHA_RE.fullmatch(qualified_tree_sha):
            raise DeliveryBundleError("checked-out Git tree has an invalid identity")
    resolved_output = _prepare_output_dir(output_dir)

    try:
        generated_at = (
            datetime.fromtimestamp(source_date_epoch, UTC)
            .isoformat()
            .replace("+00:00", "Z")
        )
    except (OverflowError, OSError, ValueError) as exc:
        raise DeliveryBundleError("source_date_epoch is outside the supported range") from exc

    stem = source_sha[:12]
    source_name = f"aspenops-source-{stem}.zip"
    sbom_name = f"aspenops-sbom-{stem}.spdx.json"
    evidence_name = f"aspenops-evidence-index-{stem}.json"
    manifest_name = f"aspenops-delivery-manifest-{stem}.json"
    handover_name = f"aspenops-handover-{stem}.zip"

    source_payload, source_file_count = _source_archive(
        resolved_root,
        resolved_output,
        source_sha,
    )
    source_path = resolved_output / source_name
    source_path.write_bytes(source_payload)

    sbom_path = resolved_output / sbom_name
    sbom_path.write_bytes(
        _json_bytes(_build_spdx(resolved_root, source_sha, generated_at))
    )

    evidence = _evidence_index(
        resolved_root,
        source_sha,
        qualified_tree_sha=qualified_tree_sha,
    )
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
        "git_identity_verified": git_identity_verified,
        "git_tree_sha": qualified_tree_sha,
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
    digest_path.write_text(
        f"{handover_digest}  {handover_name}\n",
        encoding="ascii",
    )

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
