from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from aspenops_nexus.config import Settings, _env_bool, _env_float, _env_int
from aspenops_nexus.registry import NodeRegistry, RegistryError


def write_registry(tmp_path: Path, data: Any, name: str = "registry.json") -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def valid_node(**overrides: Any) -> dict[str, Any]:
    node: dict[str, Any] = {
        "backend": "mock",
        "access": "readwrite",
        "unit": "1",
        "identifiers": [],
        "paths": [r"\Data\Input\VALUE"],
    }
    node.update(overrides)
    return node


def test_environment_boolean_parser_covers_defaults_and_variants(monkeypatch: Any) -> None:
    monkeypatch.delenv("FLAG", raising=False)
    assert _env_bool("FLAG", True) is True
    for value in ("1", "TRUE", " yes ", "On"):
        monkeypatch.setenv("FLAG", value)
        assert _env_bool("FLAG", False) is True
    for value in ("0", "FALSE", " no ", "Off"):
        monkeypatch.setenv("FLAG", value)
        assert _env_bool("FLAG", True) is False
    monkeypatch.setenv("FLAG", "maybe")
    with pytest.raises(ValueError, match="Invalid Boolean"):
        _env_bool("FLAG", False)


def test_numeric_environment_parsers_enforce_minimums(monkeypatch: Any) -> None:
    monkeypatch.setenv("COUNT", "3")
    assert _env_int("COUNT", 1, 2) == 3
    monkeypatch.setenv("COUNT", "1")
    with pytest.raises(ValueError, match="COUNT must be >= 2"):
        _env_int("COUNT", 1, 2)

    monkeypatch.setenv("DELAY", "0.5")
    assert _env_float("DELAY", 1.0, 0.1) == 0.5
    monkeypatch.setenv("DELAY", "0")
    with pytest.raises(ValueError, match="DELAY must be >= 0.1"):
        _env_float("DELAY", 1.0, 0.1)


def test_settings_from_env_normalizes_all_control_plane_values(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    first = tmp_path / "models"
    second = tmp_path / "results"
    monkeypatch.setenv("ASPENOPS_ALLOWED_ROOTS", f"{first}; ;{second}")
    monkeypatch.setenv("ASPENOPS_LICENSE_SLOTS", "2")
    monkeypatch.setenv("ASPENOPS_MAX_WORKERS", "8")
    monkeypatch.setenv("ASPENOPS_BACKEND", " HYSYS ")
    monkeypatch.setenv("ASPENOPS_MODE", " ENHANCED ")
    monkeypatch.setenv("ASPENOPS_VISIBLE", "true")
    monkeypatch.setenv("ASPENOPS_CACHE_FAILURES", "yes")
    monkeypatch.setenv("ASPENOPS_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("ASPENOPS_MAX_RESIDENT_CASES", "4")
    monkeypatch.setenv("ASPENOPS_CANCELLATION_GRACE_S", "0")

    settings = Settings.from_env()

    assert settings.backend == "hysys"
    assert settings.mode == "enhanced"
    assert settings.allowed_roots == (first.resolve(), second.resolve())
    assert settings.effective_workers == 2
    assert settings.visible is True
    assert settings.cache_failures is True
    assert settings.state_dir == (tmp_path / "state").resolve()
    assert settings.max_resident_cases == 4
    assert settings.cancellation_grace_s == 0.0


@pytest.mark.parametrize(
    ("name", "value", "message"),
    [
        ("ASPENOPS_BACKEND", "raw-com", "Unsupported ASPENOPS_BACKEND"),
        ("ASPENOPS_MODE", "unrestricted", "Unsupported ASPENOPS_MODE"),
    ],
)
def test_settings_reject_unsupported_modes(
    monkeypatch: Any,
    name: str,
    value: str,
    message: str,
) -> None:
    monkeypatch.setenv(name, value)
    with pytest.raises(ValueError, match=message):
        Settings.from_env()


def test_registry_rejects_invalid_json_and_root_shapes(tmp_path: Path) -> None:
    invalid = tmp_path / "invalid.json"
    invalid.write_text("{broken", encoding="utf-8")
    with pytest.raises(RegistryError, match="Invalid registry JSON"):
        NodeRegistry(invalid)

    with pytest.raises(RegistryError, match="root must be an object"):
        NodeRegistry(write_registry(tmp_path, [], "list.json"))
    with pytest.raises(RegistryError, match="non-empty 'nodes'"):
        NodeRegistry(write_registry(tmp_path, {"nodes": {}}, "empty.json"))


@pytest.mark.parametrize(
    ("key", "definition", "message"),
    [
        ("", valid_node(), "Semantic keys must be non-empty"),
        ("node", "not-an-object", "must be an object"),
        ("node", valid_node(access="execute"), "Invalid access"),
        ("node", valid_node(role="shell"), "Invalid role"),
        (
            "node",
            valid_node(role="convergence", access="write"),
            "must be readable",
        ),
        (
            "node",
            valid_node(role="convergence", identifiers=["stream"]),
            "cannot require identifiers",
        ),
        ("node", valid_node(lower=2, upper=1), "Lower bound exceeds upper"),
        ("node", valid_node(paths=[], locator={}), "requires at least one path or locator"),
        ("node", valid_node(paths="not-a-list"), "paths for node must be a list"),
        (
            "node",
            valid_node(paths=[], locator=["not", "an", "object"]),
            "locator for node must be an object",
        ),
    ],
)
def test_registry_rejects_unsafe_node_definitions(
    tmp_path: Path,
    key: str,
    definition: Any,
    message: str,
) -> None:
    with pytest.raises((RegistryError, TypeError), match=message):
        NodeRegistry(write_registry(tmp_path, {"nodes": {key: definition}}))


def test_registry_resolution_reports_unknown_missing_and_unresolved_identifiers(
    tmp_path: Path,
) -> None:
    registry = NodeRegistry(
        write_registry(
            tmp_path,
            {
                "nodes": {
                    "normal": valid_node(
                        identifiers=["stream"],
                        paths=[r"\Data\Streams\{stream}\VALUE"],
                    ),
                    "broken-template": valid_node(paths=[r"\Data\{missing}\VALUE"]),
                }
            },
        )
    )
    with pytest.raises(RegistryError, match="Unknown semantic key"):
        registry.resolve("missing", {})
    with pytest.raises(RegistryError, match="Missing identifiers"):
        registry.resolve("normal", {})
    with pytest.raises(RegistryError, match="Unresolved identifier"):
        registry.resolve("broken-template", {})


def test_registry_convergence_filter_backend_and_to_dict(tmp_path: Path) -> None:
    registry = NodeRegistry(
        write_registry(
            tmp_path,
            {
                "nodes": {
                    "aspen-status": valid_node(
                        backend="aspen_plus",
                        access="read",
                        unit=None,
                        role="convergence",
                    ),
                    "hysys-status": valid_node(
                        backend="hysys",
                        access="read",
                        unit=None,
                        role="convergence",
                    ),
                    "any-status": valid_node(
                        backend="any",
                        access="read",
                        unit=None,
                        role="convergence",
                    ),
                }
            },
        )
    )

    assert [node.key for node in registry.convergence_nodes("aspen_plus")] == [
        "any-status",
        "aspen-status",
    ]
    assert len(registry.convergence_nodes("mock")) == 3
    assert registry.resolve("any-status", {}).to_dict()["role"] == "convergence"

    hysys = registry.resolve("hysys-status", {})
    with pytest.raises(RegistryError, match="targets backend"):
        registry.validate_backend(hysys, "aspen_plus")
    registry.validate_backend(hysys, "mock")


def test_registry_write_validation_covers_type_integer_and_upper_bounds(tmp_path: Path) -> None:
    registry = NodeRegistry(
        write_registry(
            tmp_path,
            {
                "nodes": {
                    "numeric": valid_node(lower=0, upper=2),
                    "integer": valid_node(integer=True, lower=0, upper=4),
                    "label": valid_node(unit=None),
                }
            },
        )
    )

    with pytest.raises(RegistryError, match="cannot receive bool"):
        registry.validate_write(registry.resolve("numeric", {}), True, None)
    with pytest.raises(RegistryError, match="requires an integer"):
        registry.validate_write(registry.resolve("integer", {}), 1.5, "1")
    with pytest.raises(RegistryError, match="above upper bound"):
        registry.validate_write(registry.resolve("numeric", {}), 3, "1")

    assert registry.validate_write(registry.resolve("integer", {}), 2, "1") == 2
    assert registry.validate_write(registry.resolve("label", {}), "ready", None) == "ready"
