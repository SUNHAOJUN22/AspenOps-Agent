from __future__ import annotations

import base64
import hashlib
import json
import os
import platform
import re
import sys
import uuid
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TypeAlias

from . import RUNTIME_SCHEMA, __version__
from .archive_safety import (
    DEFAULT_ARCHIVE_LIMITS,
    ArchiveLimits,
    ArchiveSafetyError,
    read_member_bounded,
    validate_archive,
)
from .hashing import canonical_hash, sha256_file

KeySource: TypeAlias = str | Path | bytes
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_RESERVED_MEMBERS = {"manifest.json", "manifest.sig", "signing-key-id.txt"}


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        indent=2,
        sort_keys=True,
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _read_key_source(source: KeySource) -> bytes:
    if isinstance(source, bytes):
        return source
    return Path(source).expanduser().read_bytes()


def _load_private_key(source: KeySource) -> Any:
    try:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    except ImportError as exc:
        raise RuntimeError(
            "Install the 'signing' extra to create Ed25519 integrity bundles"
        ) from exc
    key = serialization.load_pem_private_key(_read_key_source(source), password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise TypeError("Signing key must be an Ed25519 private key")
    return key


def _load_public_key(source: KeySource) -> Any:
    try:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    except ImportError as exc:
        raise RuntimeError(
            "Install the 'signing' extra to verify Ed25519 integrity bundles"
        ) from exc
    key = serialization.load_pem_public_key(_read_key_source(source))
    if not isinstance(key, Ed25519PublicKey):
        raise TypeError("Verification key must be an Ed25519 public key")
    return key


def _key_id(public_key: Any) -> str:
    try:
        from cryptography.hazmat.primitives import serialization
    except ImportError as exc:
        raise RuntimeError(
            "Install the 'signing' extra to process Ed25519 integrity bundles"
        ) from exc
    raw = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return _sha256_bytes(bytes(raw))[:32]


def _member_record(payload: bytes) -> dict[str, Any]:
    return {"sha256": _sha256_bytes(payload), "size": len(payload)}


def _environment() -> dict[str, Any]:
    return {
        "python": sys.version,
        "platform": platform.platform(),
        "executable": sys.executable,
        "cwd": os.getcwd(),
        "pid": os.getpid(),
        "git_commit": os.getenv("ASPENOPS_GIT_COMMIT") or os.getenv("GITHUB_SHA"),
    }


def write_run_bundle(
    *,
    request: dict[str, Any],
    results: list[dict[str, Any]],
    output_path: str | Path,
    signing_private_key: KeySource | None = None,
    signing_key_id: str | None = None,
) -> Path:
    """Write a self-checking integrity bundle, optionally signed with Ed25519."""
    output = Path(output_path).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    model_path = Path(str(request["model_path"])).expanduser().resolve()
    registry_path = Path(str(request["registry_path"])).expanduser().resolve()

    members = {
        "request.json": _json_bytes(request),
        "results.json": _json_bytes(results),
        "environment.json": _json_bytes(_environment()),
        "README.txt": (
            b"This archive is a self-checking AspenOps integrity bundle. Internal hashes detect "
            b"accidental or unsophisticated modification. Cryptographic authenticity requires a "
            b"valid Ed25519 signature from a trusted key.\n"
        ),
    }
    signing: dict[str, Any] = {
        "status": "unsigned",
        "algorithm": None,
        "key_id": None,
    }
    private_key: Any = None
    if signing_private_key is not None:
        private_key = _load_private_key(signing_private_key)
        signing = {
            "status": "signed",
            "algorithm": "Ed25519",
            "key_id": signing_key_id or _key_id(private_key.public_key()),
        }

    manifest = {
        "format": "aspenops.integrity-bundle/v2",
        "runtime_schema": RUNTIME_SCHEMA,
        "runtime_version": __version__,
        "created_at": datetime.now(UTC).isoformat(),
        "request_sha256": canonical_hash(request),
        "results_sha256": canonical_hash(results),
        "model_sha256": sha256_file(model_path),
        "registry_sha256": sha256_file(registry_path),
        "result_count": len(results),
        "all_ok": all(bool(item.get("ok")) for item in results),
        "members": {name: _member_record(payload) for name, payload in members.items()},
        "signing": signing,
    }
    manifest_payload = _json_bytes(manifest)
    signature_payload: bytes | None = None
    if private_key is not None:
        signature_payload = base64.b64encode(private_key.sign(_canonical_bytes(manifest)))

    temporary = output.with_name(f".{output.name}.{uuid.uuid4().hex}.tmp")
    try:
        with zipfile.ZipFile(
            temporary,
            "w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=9,
        ) as archive:
            archive.writestr("manifest.json", manifest_payload)
            for name, payload in members.items():
                archive.writestr(name, payload)
            if signature_payload is not None:
                archive.writestr("manifest.sig", signature_payload)
                archive.writestr("signing-key-id.txt", str(signing["key_id"]).encode("utf-8"))
        os.replace(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)
    return output


def _structure_invalid(error: str, **extra: Any) -> dict[str, Any]:
    return {
        "ok": False,
        "verification_status": "structure-invalid",
        "error": error,
        **extra,
    }


def _verify_v1(
    manifest: dict[str, Any],
    request: dict[str, Any],
    results: list[Any],
) -> dict[str, Any]:
    checks = {
        "request_sha256": canonical_hash(request) == manifest.get("request_sha256"),
        "results_sha256": canonical_hash(results) == manifest.get("results_sha256"),
        "result_count": len(results) == manifest.get("result_count"),
    }
    return {
        "ok": all(checks.values()),
        "verification_status": "legacy-unsigned-valid"
        if all(checks.values())
        else "content-invalid",
        "checks": checks,
        "manifest": manifest,
        "boundary": "Legacy v1 bundles provide internal hash checks but no authenticity proof.",
    }


def _validate_member_declarations(
    value: Any,
) -> tuple[dict[str, dict[str, Any]] | None, str | None]:
    if not isinstance(value, dict):
        return None, "manifest members must be an object"
    declarations: dict[str, dict[str, Any]] = {}
    for raw_name, raw_declaration in value.items():
        name = str(raw_name)
        if name in _RESERVED_MEMBERS:
            return None, f"reserved member cannot be declared: {name}"
        if not isinstance(raw_declaration, dict):
            return None, f"member declaration must be an object: {name}"
        digest = raw_declaration.get("sha256")
        size = raw_declaration.get("size")
        if not isinstance(digest, str) or _SHA256_PATTERN.fullmatch(digest) is None:
            return None, f"member declaration has invalid sha256: {name}"
        if isinstance(size, bool) or not isinstance(size, int) or size < 0:
            return None, f"member declaration has invalid size: {name}"
        declarations[name] = {"sha256": digest, "size": size}
    return declarations, None


def _validate_signing(value: Any) -> tuple[dict[str, Any] | None, str | None]:
    if not isinstance(value, dict):
        return None, "manifest signing must be an object"
    status = value.get("status")
    algorithm = value.get("algorithm")
    key_id = value.get("key_id")
    if status == "unsigned":
        if algorithm is not None or key_id is not None:
            return None, "unsigned signing metadata must not define algorithm or key_id"
    elif status == "signed":
        if algorithm != "Ed25519":
            return None, "signed bundle must use Ed25519"
        if not isinstance(key_id, str) or not key_id or len(key_id) > 128:
            return None, "signed bundle key_id must be a non-empty bounded string"
    else:
        return None, "manifest signing status must be unsigned or signed"
    return {"status": status, "algorithm": algorithm, "key_id": key_id}, None


def _verify_signature(
    *,
    archive: zipfile.ZipFile,
    infos: dict[str, zipfile.ZipInfo],
    manifest: dict[str, Any],
    signing: dict[str, Any],
    verification_public_key: KeySource | None,
    limits: ArchiveLimits,
) -> tuple[bool | None, str | None]:
    try:
        archived_key_id = read_member_bounded(
            archive,
            infos["signing-key-id.txt"],
            limits,
        ).decode("utf-8")
    except (ArchiveSafetyError, UnicodeDecodeError, KeyError) as exc:
        return False, f"{type(exc).__name__}: {exc}"
    manifest_key_id = str(signing["key_id"])
    if archived_key_id != manifest_key_id:
        return False, "signing key ID does not match manifest"
    if verification_public_key is None:
        return None, "verification public key is required"
    public_key = _load_public_key(verification_public_key)
    if _key_id(public_key) != manifest_key_id:
        return False, "verification public key ID does not match manifest"
    try:
        from cryptography.exceptions import InvalidSignature
    except ImportError as exc:
        raise RuntimeError(
            "Install the 'signing' extra to verify Ed25519 integrity bundles"
        ) from exc
    try:
        encoded_signature = read_member_bounded(archive, infos["manifest.sig"], limits)
        signature = base64.b64decode(encoded_signature, validate=True)
        public_key.verify(signature, _canonical_bytes(manifest))
        return True, None
    except (ArchiveSafetyError, InvalidSignature, ValueError, KeyError) as exc:
        return False, f"{type(exc).__name__}: {exc}"


def verify_run_bundle(
    path: str | Path,
    *,
    verification_public_key: KeySource | None = None,
    limits: ArchiveLimits = DEFAULT_ARCHIVE_LIMITS,
) -> dict[str, Any]:
    bundle = Path(path).expanduser().resolve()
    try:
        with zipfile.ZipFile(bundle) as archive:
            infos = validate_archive(bundle, archive, limits)
            actual_names = set(infos)
            required = {"manifest.json", "request.json", "results.json", "environment.json"}
            missing = sorted(required - actual_names)
            if missing:
                return _structure_invalid("required archive members are missing", missing=missing)

            manifest = json.loads(read_member_bounded(archive, infos["manifest.json"], limits))
            request = json.loads(read_member_bounded(archive, infos["request.json"], limits))
            results = json.loads(read_member_bounded(archive, infos["results.json"], limits))
            environment = json.loads(
                read_member_bounded(archive, infos["environment.json"], limits)
            )
            if not isinstance(manifest, dict):
                return _structure_invalid("manifest.json root must be an object")
            if not isinstance(request, dict):
                return _structure_invalid("request.json root must be an object")
            if not isinstance(results, list):
                return _structure_invalid("results.json root must be an array")
            if not isinstance(environment, dict):
                return _structure_invalid("environment.json root must be an object")

            if manifest.get("format") != "aspenops.integrity-bundle/v2":
                return _verify_v1(manifest, request, results)

            declared_members, declaration_error = _validate_member_declarations(
                manifest.get("members")
            )
            if declared_members is None:
                return _structure_invalid(str(declaration_error), manifest=manifest)
            signing, signing_error = _validate_signing(manifest.get("signing"))
            if signing is None:
                return _structure_invalid(str(signing_error), manifest=manifest)

            signed = signing["status"] == "signed"
            expected_names = {"manifest.json", *declared_members}
            if signed:
                expected_names.update({"manifest.sig", "signing-key-id.txt"})
            unexpected = sorted(actual_names - expected_names)
            undeclared_missing = sorted(expected_names - actual_names)

            if signed:
                signing_missing = sorted({"manifest.sig", "signing-key-id.txt"} - actual_names)
                if signing_missing:
                    return _structure_invalid(
                        "signed archive members are missing",
                        missing=signing_missing,
                        manifest=manifest,
                    )

                member_checks: dict[str, bool] = {}
            for name, declaration in declared_members.items():
                info = infos.get(name)
                if info is None:
                    member_checks[name] = False
                    continue
                payload = read_member_bounded(archive, info, limits)
                member_checks[name] = (
                    _sha256_bytes(payload) == declaration["sha256"]
                    and len(payload) == declaration["size"]
                )

            semantic_checks = {
                "request_sha256": canonical_hash(request) == manifest.get("request_sha256"),
                "results_sha256": canonical_hash(results) == manifest.get("results_sha256"),
                "result_count": len(results) == manifest.get("result_count"),
            }
            content_valid = (
                not unexpected
                and not undeclared_missing
                and all(member_checks.values())
                and all(semantic_checks.values())
            )

            signature_valid: bool | None = None
            signature_error: str | None = None
            if signed:
                signature_valid, signature_error = _verify_signature(
                    archive=archive,
                    infos=infos,
                    manifest=manifest,
                    signing=signing,
                    verification_public_key=verification_public_key,
                    limits=limits,
                )
    except (
        ArchiveSafetyError,
        OSError,
        zipfile.BadZipFile,
        json.JSONDecodeError,
        UnicodeDecodeError,
        KeyError,
    ) as exc:
        return _structure_invalid(f"{type(exc).__name__}: {exc}")

    if not content_valid:
        verification_status = "content-invalid"
        ok = False
    elif not signed:
        verification_status = "unsigned-valid"
        ok = True
    elif signature_valid is True:
        verification_status = "signed-valid"
        ok = True
    elif verification_public_key is None:
        verification_status = "signed-unverified"
        ok = False
    else:
        verification_status = "signed-invalid"
        ok = False
    return {
        "ok": ok,
        "verification_status": verification_status,
        "checks": {
            **semantic_checks,
            "members": member_checks,
            "unexpected_members": not unexpected,
            "missing_declared_members": not undeclared_missing,
            "signature": signature_valid,
        },
        "unexpected": unexpected,
        "missing": undeclared_missing,
        "signature_error": signature_error,
        "manifest": manifest,
        "boundary": (
            "Unsigned bundles provide self-checking integrity only. A signed-valid result proves "
            "that the manifest was signed by the supplied trusted Ed25519 public key."
        ),
    }
