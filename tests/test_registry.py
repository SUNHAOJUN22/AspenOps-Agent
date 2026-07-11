from pathlib import Path

import pytest

from aspenops.errors import NodeResolutionError, ValidationError
from aspenops.registry import NodeRegistry, load_bundled_registry


def test_bundled_registry_metadata_and_resolution_cache() -> None:
    registry = load_bundled_registry()
    keys = registry.keys()
    assert "stream.input.temperature" in keys
    spec = registry.get("stream.input.temperature")
    assert spec.identifiers == {"stream"}

    calls: list[str] = []

    def exists(path: str) -> bool:
        calls.append(path)
        return path == "mock.feed.temperature"

    cache: dict[tuple[str, tuple[tuple[str, str], ...]], str] = {}
    resolved = registry.resolve("stream.input.temperature", {"stream": "FEED"}, exists, cache)
    assert resolved == "mock.feed.temperature"
    first_call_count = len(calls)
    assert (
        registry.resolve("stream.input.temperature", {"stream": "FEED"}, exists, cache) == resolved
    )
    assert len(calls) == first_call_count + 1


def test_registry_rejects_identifiers_and_missing_paths() -> None:
    registry = load_bundled_registry()
    with pytest.raises(ValidationError):
        registry.resolve("stream.input.temperature", {}, lambda _: True)
    with pytest.raises(ValidationError):
        registry.resolve("stream.input.temperature", {"stream": "BAD\\PATH"}, lambda _: True)
    with pytest.raises(NodeResolutionError):
        registry.resolve("stream.input.temperature", {"stream": "FEED"}, lambda _: False)


def test_registry_yaml_validation(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        "nodes:\n  x:\n    quantity: pressure\n    default_unit: kg/h\n    candidates: ['x']\n",
        encoding="utf-8",
    )
    with pytest.raises(ValidationError):
        NodeRegistry.from_yaml(bad)
