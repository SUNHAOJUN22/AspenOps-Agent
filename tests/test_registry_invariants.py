import json
import math
from pathlib import Path
from typing import Any

import pytest

from aspenops_nexus.registry import NodeRegistry, RegistryError


def write_registry(tmp_path: Path, node: dict[str, Any]) -> Path:
    path = tmp_path / "registry.json"
    path.write_text(json.dumps({"nodes": {"x": node}}), encoding="utf-8")
    return path


def base_node() -> dict[str, Any]:
    return {
        "access": "readwrite",
        "unit": "bar",
        "quantity": "pressure_absolute",
        "backend": "aspen_plus",
        "identifiers": ["stream"],
        "locator": {"mock_key": "pressure_{stream}"},
    }


def test_quantity_must_match_unit_dimension(tmp_path: Path) -> None:
    node = {**base_node(), "quantity": "mass_flow"}
    with pytest.raises(RegistryError, match="does not match"):
        NodeRegistry(write_registry(tmp_path, node))


@pytest.mark.parametrize("bound", [math.nan, math.inf, -math.inf])
def test_bounds_must_be_finite(tmp_path: Path, bound: float) -> None:
    node = {**base_node(), "lower": bound}
    with pytest.raises(RegistryError, match="must be finite"):
        NodeRegistry(write_registry(tmp_path, node))


def test_integer_flag_must_be_json_boolean(tmp_path: Path) -> None:
    node = {**base_node(), "integer": "false"}
    with pytest.raises(RegistryError, match="JSON Boolean"):
        NodeRegistry(write_registry(tmp_path, node))


def test_identifier_templates_are_plain_and_declared(tmp_path: Path) -> None:
    node = {**base_node(), "locator": {"mock_key": "{stream.__class__}"}}
    with pytest.raises(RegistryError, match="undeclared identifier"):
        NodeRegistry(write_registry(tmp_path, node))


def test_unit_errors_are_exposed_as_registry_errors(tmp_path: Path) -> None:
    registry = NodeRegistry(write_registry(tmp_path, base_node()))
    resolved = registry.resolve("x", {"stream": "FEED"})
    with pytest.raises(RegistryError, match="Invalid unit"):
        registry.validate_write(resolved, 1.0, "kg/h")


def test_integer_validation_uses_explicit_absolute_tolerance(tmp_path: Path) -> None:
    node = {
        "access": "write",
        "unit": "1",
        "quantity": "dimensionless",
        "integer": True,
        "locator": {"mock_key": "stages"},
    }
    registry = NodeRegistry(write_registry(tmp_path, node))
    resolved = registry.resolve("x", {})
    assert registry.validate_write(resolved, 2.0 + 5e-10, "1") == 2
    with pytest.raises(RegistryError, match="integer value"):
        registry.validate_write(resolved, 2.0 + 2e-9, "1")
