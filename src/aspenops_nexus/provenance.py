from __future__ import annotations

import json
import os
import platform
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from . import RUNTIME_SCHEMA, __version__
from .hashing import canonical_hash, sha256_file


def write_run_bundle(
    *,
    request: dict[str, Any],
    results: list[dict[str, Any]],
    output_path: str | Path,
) -> Path:
    output = Path(output_path).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    created_at = datetime.now(UTC).isoformat()
    model_path = Path(str(request["model_path"])).expanduser().resolve()
    registry_path = Path(str(request["registry_path"])).expanduser().resolve()
    request_json = json.dumps(
        request, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False
    )
    results_json = json.dumps(
        results, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False
    )
    manifest = {
        "format": "aspenops.run-bundle/v1",
        "runtime_schema": RUNTIME_SCHEMA,
        "runtime_version": __version__,
        "created_at": created_at,
        "request_sha256": canonical_hash(request),
        "results_sha256": canonical_hash(results),
        "model_sha256": sha256_file(model_path),
        "registry_sha256": sha256_file(registry_path),
        "result_count": len(results),
        "all_ok": all(bool(item.get("ok")) for item in results),
    }
    environment = {
        "python": sys.version,
        "platform": platform.platform(),
        "executable": sys.executable,
        "cwd": os.getcwd(),
        "pid": os.getpid(),
    }
    manifest_json = json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False)
    environment_json = json.dumps(environment, indent=2, sort_keys=True, ensure_ascii=False)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        archive.writestr("manifest.json", manifest_json)
        archive.writestr("request.json", request_json)
        archive.writestr("results.json", results_json)
        archive.writestr("environment.json", environment_json)
        archive.writestr(
            "README.txt",
            "This archive is an immutable AspenOps evidence bundle. Verify the SHA-256 values in "
            "manifest.json before relying on model, registry or result identity.\n",
        )
    return output


def verify_run_bundle(path: str | Path) -> dict[str, Any]:
    bundle = Path(path).expanduser().resolve()
    with zipfile.ZipFile(bundle) as archive:
        required = {"manifest.json", "request.json", "results.json", "environment.json"}
        missing = sorted(required - set(archive.namelist()))
        if missing:
            return {"ok": False, "missing": missing}
        manifest = json.loads(archive.read("manifest.json"))
        request = json.loads(archive.read("request.json"))
        results = json.loads(archive.read("results.json"))
    checks = {
        "request_sha256": canonical_hash(request) == manifest.get("request_sha256"),
        "results_sha256": canonical_hash(results) == manifest.get("results_sha256"),
        "result_count": len(results) == manifest.get("result_count"),
    }
    return {"ok": all(checks.values()), "checks": checks, "manifest": manifest}
