import json
from pathlib import Path

import pytest

from aspenops_nexus.errors import classify_exception
from aspenops_nexus.registry import NodeRegistry, RegistryError


def write_registry(tmp_path: Path, data: dict) -> Path:
    path = tmp_path / "registry.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def minimal_node(**overrides) -> dict:
    node = {
        "access": "read",
        "unit": "fraction",
        "backend": "any",
        "identifiers": ["stream"],
        "paths": ["/Streams/{stream}/purity"],
    }
    node.update(overrides)
    return node


def test_registry_rejects_duplicate_json_keys(tmp_path: Path) -> None:
    path = tmp_path / "registry.json"
    path.write_text(
        '{"nodes":{"x":{"access":"read","access":"write",'
        '"identifiers":[],"paths":["/x"]}}}',
        encoding="utf-8",
    )
    with pytest.raises(RegistryError, match="duplicate JSON key"):
        NodeRegistry(path)


def test_registry_rejects_unknown_root_and_node_fields(tmp_path: Path) -> None:
    with pytest.raises(RegistryError, match="Unknown fields in registry root"):
        NodeRegistry(
            write_registry(
                tmp_path,
                {"nodes": {"x": minimal_node()}, "ndoes": {}},
            )
        )
    with pytest.raises(RegistryError, match="Unknown fields in registry node"):
        NodeRegistry(
            write_registry(
                tmp_path,
                {"nodes": {"x": minimal_node(unt="fraction")}},
            )
        )


def test_registry_schema_strings_units_and_paths_are_strict(tmp_path: Path) -> None:
    with pytest.raises(RegistryError, match="Unsupported registry schema"):
        NodeRegistry(
            write_registry(
                tmp_path,
                {"schema": "aspenops.registry/v2", "nodes": {"x": minimal_node()}},
            )
        )
    with pytest.raises(RegistryError, match="registry name must be a string"):
        NodeRegistry(
            write_registry(
                tmp_path,
                {"name": None, "nodes": {"x": minimal_node()}},
            )
        )
    with pytest.raises(RegistryError, match="Invalid unit"):
        NodeRegistry(
            write_registry(
                tmp_path,
                {"nodes": {"x": minimal_node(unit="not-a-unit")}},
            )
        )
    with pytest.raises(RegistryError, match="paths.*unique"):
        NodeRegistry(
            write_registry(
                tmp_path,
                {
                    "nodes": {
                        "x": minimal_node(
                            paths=["/Streams/{stream}/purity", "/Streams/{stream}/purity"]
                        )
                    }
                },
            )
        )


def test_resolve_does_not_coerce_identifier_types(tmp_path: Path) -> None:
    registry = NodeRegistry(write_registry(tmp_path, {"nodes": {"x": minimal_node()}}))
    with pytest.raises(RegistryError, match="string keys and string values"):
        registry.resolve("x", {"stream": 1})  # type: ignore[dict-item]
    with pytest.raises(RegistryError, match="non-empty string"):
        registry.resolve(1, {"stream": "A"})  # type: ignore[arg-type]


def test_registry_errors_use_the_stable_error_taxonomy(tmp_path: Path) -> None:
    with pytest.raises(RegistryError) as captured:
        NodeRegistry(write_registry(tmp_path, {"nodes": {"x": minimal_node(access="bad")}}))
    classified = classify_exception(captured.value)
    assert classified["code"] == "REGISTRY_ERROR"
    assert classified["retryable"] is False
