from __future__ import annotations

import json
import math
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


def load_request_object(path: str | Path, *, root_label: str = "Request root") -> dict[str, Any]:
    value = json.loads(
        Path(path).read_text(encoding="utf-8"),
        parse_float=finite_json_float,
        parse_constant=_reject_constant,
        object_pairs_hook=_unique_request_object,
    )
    if not isinstance(value, dict):
        raise ValueError(f"{root_label} must be a JSON object")
    return value
