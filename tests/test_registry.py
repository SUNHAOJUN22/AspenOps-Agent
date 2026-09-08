from importlib.resources import as_file, files

import pytest

from aspenops_nexus.registry import NodeRegistry, RegistryError


def registry() -> NodeRegistry:
    with as_file(files("aspenops_nexus.data").joinpath("node-registry.json")) as path:
        return NodeRegistry(path)


def test_resolve_and_validate() -> None:
    item = registry().resolve("stream.input.temperature", {"stream": "FEED"})
    assert "FEED" in item.paths[0]
    assert registry().validate_write(item, 100.0, "C") == 100.0


def test_bounds_are_enforced() -> None:
    item = registry().resolve("block.input.reflux_ratio", {"block": "C1"})
    with pytest.raises(RegistryError):
        registry().validate_write(item, -1.0, "1")


def test_read_only_rejected() -> None:
    item = registry().resolve("stream.output.purity", {"stream": "P"})
    with pytest.raises(RegistryError):
        registry().validate_write(item, 0.9, "fraction")


def test_identifier_injection_and_extra_identifier_are_rejected() -> None:
    with pytest.raises(RegistryError):
        registry().resolve("stream.input.temperature", {"stream": r"FEED\..\Blocks"})
    with pytest.raises(RegistryError):
        registry().resolve(
            "stream.input.temperature",
            {"stream": "FEED", "block": "C1"},
        )


def test_registry_description_is_agent_safe() -> None:
    descriptions = registry().describe()
    assert descriptions
    assert "paths" not in descriptions[0]
    assert {"key", "access", "unit", "identifiers"}.issubset(descriptions[0])
