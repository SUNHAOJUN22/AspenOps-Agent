from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import pytest

from aspenops_nexus.registry import NodeRegistry, RegistryError


def _node(**overrides: Any) -> dict[str, Any]:
    value: dict[str, Any] = {
        "backend": "mock",
        "access": "readwrite",
        "unit": "1",
        "identifiers": [],
        "paths": [r"\Data\Input\VALUE"],
    }
    value.update(overrides)
    return value


def _write(tmp_path: Path, node: dict[str, Any], *, allow_nan: bool = True) -> Path:
    path = tmp_path / "registry.json"
    path.write_text(
        json.dumps({"nodes": {"node": node}}, allow_nan=allow_nan),
        encoding="utf-8",
    )
    return path


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"lower": True}, "lower for node must be finite numeric"),
        ({"upper": math.inf}, "unsupported constant: Infinity"),
        ({"integer": "false"}, "integer for node must be a boolean"),
        ({"backend": "raw-com"}, "Invalid backend for node"),
        ({"unit": 1}, "unit for node must be a non-empty string or null"),
        ({"identifiers": "stream"}, "identifiers for node must be a list"),
        ({"identifiers": ["stream", "stream"]}, "must contain unique names"),
        ({"identifiers": ["stream.name"]}, "Unsafe identifier name"),
        ({"paths": [1]}, "paths for node must contain non-empty strings"),
        ({"paths": [""]}, "paths for node must contain non-empty strings"),
        ({"locator": []}, "locator for node must be an object"),
    ],
)
def test_registry_definition_is_fail_closed(
    tmp_path: Path,
    overrides: dict[str, Any],
    message: str,
) -> None:
    with pytest.raises(RegistryError, match=message):
        NodeRegistry(_write(tmp_path, _node(**overrides)))


def test_registry_rejects_nonfinite_json_constants_anywhere(tmp_path: Path) -> None:
    with pytest.raises(RegistryError, match="unsupported constant: NaN"):
        NodeRegistry(_write(tmp_path, _node(locator={"mock_value": math.nan})))


def test_registry_accepts_explicit_valid_definition_types(tmp_path: Path) -> None:
    registry = NodeRegistry(
        _write(
            tmp_path,
            _node(
                backend="any",
                integer=False,
                lower=0,
                upper=10,
                identifiers=["stream"],
                paths=[r"\Data\Streams\{stream}\VALUE"],
            ),
        )
    )
    resolved = registry.resolve("node", {"stream": "FEED"})
    assert resolved.backend == "any"
    assert resolved.integer is False
    assert resolved.lower == 0.0
    assert resolved.upper == 10.0
