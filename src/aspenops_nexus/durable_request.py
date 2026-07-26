from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

PATH_FIELDS = ("model_path", "registry_path")


def pin_durable_request_paths(
    request: Mapping[str, Any],
    *,
    submission_cwd: Path,
) -> dict[str, Any]:
    """Return a request whose model identities survive a process/CWD boundary."""

    normalized = dict(request)
    base = submission_cwd.expanduser().resolve()
    paths_pinned = False
    for key in PATH_FIELDS:
        raw = normalized.get(key)
        if not isinstance(raw, str) or not raw.strip():
            continue
        candidate = Path(raw).expanduser()
        if not candidate.is_absolute():
            candidate = base / candidate
        normalized[key] = str(candidate.resolve())
        paths_pinned = True

    if paths_pinned:
        metadata_raw = normalized.get("metadata")
        if metadata_raw is None:
            metadata: dict[str, Any] = {}
        elif isinstance(metadata_raw, dict):
            source = cast(dict[object, object], metadata_raw)
            metadata = {str(key): value for key, value in source.items()}
        else:
            return normalized
        metadata.setdefault("submission_cwd", str(base))
        normalized["metadata"] = metadata
    return normalized


def durable_paths_pinned(request: Mapping[str, Any]) -> bool:
    """Return whether all required model identity paths are absolute strings."""

    values = (request.get(key) for key in PATH_FIELDS)
    return all(isinstance(value, str) and Path(value).is_absolute() for value in values)


def submission_directory(request: Mapping[str, Any]) -> str | None:
    """Read submission directory metadata without trusting arbitrary metadata types."""

    metadata = request.get("metadata")
    if not isinstance(metadata, dict):
        return None
    value = metadata.get("submission_cwd")
    return value if isinstance(value, str) else None
