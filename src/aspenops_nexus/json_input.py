from __future__ import annotations

import json
import math
import os
import stat
from pathlib import Path
from typing import Any


def finite_json_float(token: str) -> float:
    """Decode a JSON decimal without silently erasing a nonzero measurement."""
    value = float(token)
    if not math.isfinite(value):
        raise ValueError("JSON number exceeds the finite range")
    significand = token.lower().partition("e")[0]
    if value == 0.0 and any(character in "123456789" for character in significand):
        raise ValueError("Nonzero JSON number underflows to zero")
    return value


def _unique_object(pairs: list[tuple[str, Any]], *, label: str = "JSON") -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate {label} key: {key}")
        result[key] = value
    return result


def _reject_constant(token: str) -> Any:
    raise ValueError(f"JSON contains non-finite constant: {token}")


def strict_json_loads(payload: str | bytes) -> Any:
    return json.loads(
        payload,
        parse_float=finite_json_float,
        parse_constant=_reject_constant,
        object_pairs_hook=_unique_object,
    )


def _unique_request_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    return _unique_object(pairs, label="request JSON")


def load_request_object(
    path: str | Path,
    *,
    root_label: str = "Request root",
    max_bytes: int | None = None,
) -> dict[str, Any]:
    request_path = Path(path)
    if max_bytes is None:
        payload = request_path.read_text(encoding="utf-8")
    else:
        if type(max_bytes) is not int or max_bytes < 0:
            raise ValueError("Request byte limit must be a non-negative integer")
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NONBLOCK", 0)
        descriptor = os.open(request_path, flags)
        try:
            metadata = os.fstat(descriptor)
            if not stat.S_ISREG(metadata.st_mode):
                raise ValueError(f"{root_label} must be a regular file")
            if metadata.st_size > max_bytes:
                raise ValueError(
                    f"{root_label} file is {metadata.st_size} bytes; limit is {max_bytes}"
                )
            with os.fdopen(descriptor, "rb") as stream:
                descriptor = -1
                raw = stream.read(max_bytes + 1)
            if len(raw) > max_bytes:
                raise ValueError(f"{root_label} file exceeds the {max_bytes}-byte input limit")
        finally:
            if descriptor >= 0:
                os.close(descriptor)
        payload = raw.decode("utf-8")
    value = json.loads(
        payload,
        parse_float=finite_json_float,
        parse_constant=_reject_constant,
        object_pairs_hook=_unique_request_object,
    )
    if not isinstance(value, dict):
        raise ValueError(f"{root_label} must be a JSON object")
    return value
