from __future__ import annotations

import hashlib
import json
import os
import platform
import stat
import sys
import uuid
import zipfile
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

from . import RUNTIME_SCHEMA, __version__
from .errors import EvidenceIntegrityError
from .hashing import canonical_hash, sha256_file

_BUNDLE_FORMAT = "aspenops.run-bundle/v2"
_MAX_MEMBER_BYTES = 100 * 1024 * 1024
_MAX_BUNDLE_UNCOMPRESSED_BYTES = 250 * 1024 * 1024
_PAYLOAD_NAMES = {
    "request.json",
    "results.json",
    "environment.json",
    "registry.snapshot.json",
    "README.txt",
}


def _json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _strict_json_loads(raw: bytes, name: str) -> Any:
    def reject_constant(value: str) -> None:
        raise EvidenceIntegrityError(f"{name} contains non-finite JSON constant {value!r}")

    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise EvidenceIntegrityError(f"{name} contains duplicate JSON key {key!r}")
            result[key] = value
        return result

    try:
        return json.loads(
            raw,
            object_pairs_hook=reject_duplicates,
            parse_constant=reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EvidenceIntegrityError(f"{name} is not strict UTF-8 JSON: {exc}") from exc


def _safe_member_name(name: str) -> bool:
    path = PurePosixPath(name)
    return (
        bool(name)
        and "\\" not in name
        and not path.is_absolute()
        and all(part not in {"", ".", ".."} for part in path.parts)
        and name == path.as_posix()
    )


def _write_lock(path: Path) -> int:
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    try:
        return os.open(path, flags, 0o600)
    except FileExistsError as exc:
        raise FileExistsError(f"Evidence bundle writer lock already exists: {path}") from exc


def _extract_worker_protocols(results: list[dict[str, Any]]) -> list[str]:
    protocols: set[str] = set()
    for result in results:
        diagnostics = result.get("diagnostics")
        if not isinstance(diagnostics, dict):
            continue
        worker = diagnostics.get("worker")
        if isinstance(worker, dict):
            protocol = worker.get("protocol") or worker.get("protocol_version")
            if protocol is not None:
                protocols.add(str(protocol))
    return sorted(protocols)


def write_run_bundle(
    *,
    request: dict[str, Any],
    results: list[dict[str, Any]],
    output_path: str | Path,
) -> Path:
    output = Path(output_path).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite immutable evidence bundle: {output}")
    lock_path = output.with_name(f".{output.name}.lock")
    lock_fd = _write_lock(lock_path)
    temp_path = output.with_name(f".{output.name}.{uuid.uuid4().hex}.tmp")
    sidecar = output.with_suffix(output.suffix + ".sha256")
    try:
        if sidecar.exists():
            raise FileExistsError(f"Refusing to overwrite evidence hash sidecar: {sidecar}")
        created_at = datetime.now(UTC).isoformat()
        model_path = Path(str(request["model_path"])).expanduser().resolve()
        registry_path = Path(str(request["registry_path"])).expanduser().resolve()
        if not model_path.is_file():
            raise FileNotFoundError(f"Evidence model file not found: {model_path}")
        if not registry_path.is_file():
            raise FileNotFoundError(f"Evidence registry file not found: {registry_path}")
        registry_snapshot = registry_path.read_bytes()
        _strict_json_loads(registry_snapshot, "registry.snapshot.json")
        environment = {
            "python_version": platform.python_version(),
            "python_implementation": platform.python_implementation(),
            "platform": platform.platform(),
            "runtime_executable_name": Path(sys.executable).name,
        }
        readme = (
            "AspenOps immutable evidence bundle. Verify manifest.json, every listed SHA-256, "
            "the exact member set, and the external model hash before relying on this evidence.\n"
        ).encode("utf-8")
        payloads: dict[str, bytes] = {
            "request.json": _json_bytes(request),
            "results.json": _json_bytes(results),
            "environment.json": _json_bytes(environment),
            "registry.snapshot.json": registry_snapshot,
            "README.txt": readme,
        }
        file_entries = [
            {"path": name, "sha256": _sha256_bytes(payload), "size": len(payload)}
            for name, payload in sorted(payloads.items())
        ]
        backend = str(request.get("backend", "unknown"))
        manifest = {
            "format": _BUNDLE_FORMAT,
            "runtime_schema": RUNTIME_SCHEMA,
            "runtime_version": __version__,
            "created_at": created_at,
            "request_sha256": canonical_hash(request),
            "results_sha256": canonical_hash(results),
            "model_sha256": sha256_file(model_path),
            "model_name": model_path.name,
            "registry_sha256": _sha256_bytes(registry_snapshot),
            "registry_name": registry_path.name,
            "result_count": len(results),
            "all_ok": all(bool(item.get("ok")) for item in results),
            "backend": backend,
            "worker_protocols": _extract_worker_protocols(results),
            "durations_s": [item.get("elapsed_s") for item in results],
            "qualification_level": "MOCK_ONLY" if backend == "mock" else "UNVERIFIED",
            "physical_certification": "BLOCKED",
            "parent_evidence_sha256": request.get("parent_evidence_sha256"),
            "approval_hash": request.get("approval_hash"),
            "files": file_entries,
            "content_manifest_sha256": canonical_hash(file_entries),
        }
        manifest_bytes = _json_bytes(manifest)
        with zipfile.ZipFile(
            temp_path,
            "x",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=9,
            strict_timestamps=True,
        ) as archive:
            archive.writestr("manifest.json", manifest_bytes)
            for name, payload in sorted(payloads.items()):
                archive.writestr(name, payload)
        with temp_path.open("rb") as handle:
            os.fsync(handle.fileno())
        os.replace(temp_path, output)
        artifact_sha256 = sha256_file(output)
        sidecar_temp = sidecar.with_name(f".{sidecar.name}.{uuid.uuid4().hex}.tmp")
        sidecar_temp.write_text(f"{artifact_sha256}  {output.name}\n", encoding="ascii")
        os.replace(sidecar_temp, sidecar)
        return output
    finally:
        if temp_path.exists():
            temp_path.unlink()
        os.close(lock_fd)
        lock_path.unlink(missing_ok=True)


def _verify_archive_structure(archive: zipfile.ZipFile) -> tuple[list[zipfile.ZipInfo], list[str]]:
    infos = archive.infolist()
    names = [info.filename for info in infos]
    errors: list[str] = []
    if len(names) != len(set(names)):
        errors.append("duplicate_member_name")
    for info in infos:
        if not _safe_member_name(info.filename):
            errors.append(f"unsafe_member:{info.filename}")
        mode = info.external_attr >> 16
        if stat.S_ISLNK(mode):
            errors.append(f"symlink_member:{info.filename}")
        if info.is_dir():
            errors.append(f"directory_member:{info.filename}")
        if info.file_size > _MAX_MEMBER_BYTES:
            errors.append(f"oversized_member:{info.filename}")
    if sum(info.file_size for info in infos) > _MAX_BUNDLE_UNCOMPRESSED_BYTES:
        errors.append("oversized_uncompressed_bundle")
    return infos, sorted(set(errors))


def verify_run_bundle(path: str | Path) -> dict[str, Any]:
    bundle = Path(path).expanduser().resolve()
    artifact_sha256 = sha256_file(bundle)
    try:
        with zipfile.ZipFile(bundle) as archive:
            infos, structure_errors = _verify_archive_structure(archive)
            if structure_errors:
                return {
                    "ok": False,
                    "error_code": "EVIDENCE_INTEGRITY_ERROR",
                    "errors": structure_errors,
                    "artifact_sha256": artifact_sha256,
                }
            names = {info.filename for info in infos}
            if "manifest.json" not in names:
                return {
                    "ok": False,
                    "error_code": "EVIDENCE_INTEGRITY_ERROR",
                    "errors": ["missing:manifest.json"],
                    "artifact_sha256": artifact_sha256,
                }
            manifest = _strict_json_loads(archive.read("manifest.json"), "manifest.json")
            if not isinstance(manifest, dict):
                raise EvidenceIntegrityError("manifest.json root must be an object")
            raw_entries = manifest.get("files")
            if not isinstance(raw_entries, list):
                raise EvidenceIntegrityError("manifest files must be a list")
            entries: dict[str, dict[str, Any]] = {}
            for raw_entry in raw_entries:
                if not isinstance(raw_entry, dict):
                    raise EvidenceIntegrityError("manifest file entry must be an object")
                name = str(raw_entry.get("path", ""))
                if name in entries:
                    raise EvidenceIntegrityError(f"duplicate manifest file entry: {name!r}")
                entries[name] = raw_entry
            expected_names = {"manifest.json", *entries}
            errors: list[str] = []
            if names != expected_names:
                for name in sorted(expected_names - names):
                    errors.append(f"missing:{name}")
                for name in sorted(names - expected_names):
                    errors.append(f"unlisted:{name}")
            if set(entries) != _PAYLOAD_NAMES:
                errors.append("unexpected_payload_manifest")
            checks: dict[str, bool] = {
                "format": manifest.get("format") == _BUNDLE_FORMAT,
                "content_manifest": canonical_hash(raw_entries)
                == manifest.get("content_manifest_sha256"),
                "physical_certification_blocked": manifest.get("physical_certification")
                == "BLOCKED",
            }
            payloads: dict[str, bytes] = {}
            for name, entry in entries.items():
                if name not in names:
                    continue
                payload = archive.read(name)
                payloads[name] = payload
                expected_size = entry.get("size")
                expected_hash = entry.get("sha256")
                checks[f"file_size:{name}"] = (
                    isinstance(expected_size, int) and len(payload) == expected_size
                )
                checks[f"file_sha256:{name}"] = _sha256_bytes(payload) == expected_hash
            if errors:
                return {
                    "ok": False,
                    "error_code": "EVIDENCE_INTEGRITY_ERROR",
                    "errors": sorted(errors),
                    "checks": checks,
                    "manifest": manifest,
                    "artifact_sha256": artifact_sha256,
                }
            request = _strict_json_loads(payloads["request.json"], "request.json")
            results = _strict_json_loads(payloads["results.json"], "results.json")
            registry = _strict_json_loads(
                payloads["registry.snapshot.json"], "registry.snapshot.json"
            )
            checks.update(
                {
                    "request_sha256": canonical_hash(request) == manifest.get("request_sha256"),
                    "results_sha256": canonical_hash(results) == manifest.get("results_sha256"),
                    "result_count": isinstance(results, list)
                    and len(results) == manifest.get("result_count"),
                    "registry_sha256": _sha256_bytes(payloads["registry.snapshot.json"])
                    == manifest.get("registry_sha256"),
                    "registry_object": isinstance(registry, dict),
                }
            )
    except (EvidenceIntegrityError, KeyError, OSError, zipfile.BadZipFile) as exc:
        return {
            "ok": False,
            "error_code": "EVIDENCE_INTEGRITY_ERROR",
            "errors": [f"{type(exc).__name__}:{exc}"],
            "artifact_sha256": artifact_sha256,
        }
    sidecar = bundle.with_suffix(bundle.suffix + ".sha256")
    sidecar_check: bool | None = None
    if sidecar.is_file():
        expected = sidecar.read_text(encoding="ascii").split(maxsplit=1)[0]
        sidecar_check = expected == artifact_sha256
        checks["artifact_sidecar_sha256"] = sidecar_check
    return {
        "ok": all(checks.values()),
        "checks": checks,
        "manifest": manifest,
        "artifact_sha256": artifact_sha256,
        "artifact_sidecar_present": sidecar_check is not None,
    }
