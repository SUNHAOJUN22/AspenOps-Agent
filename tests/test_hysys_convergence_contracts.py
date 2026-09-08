from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from aspenops_nexus.backends.hysys import HysysBackend
from aspenops_nexus.registry import NodeRegistry, RegistryError, ResolvedNode


class FakeHysysBackend(HysysBackend):
    def __init__(self, value: Any) -> None:
        super().__init__()
        self.value = value
        self.case = SimpleNamespace(Solver=SimpleNamespace(IsSolving=False, CanSolve=False))

    def read(self, node: ResolvedNode) -> Any:
        del node
        return self.value


def convergence_node(**contract: Any) -> ResolvedNode:
    return ResolvedNode(
        key="solver.status.converged",
        access="read",
        native_unit=None,
        quantity=None,
        paths=(),
        identifiers={},
        lower=None,
        upper=None,
        integer=False,
        backend="hysys",
        locator={"spreadsheet": "ASPENOPS_IO", "cell": "C1", **contract},
        verification="project-required",
        description="Project-owned convergence contract",
        role="convergence",
    )


def configure_fast_poll(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ASPENOPS_HYSYS_STATUS_TIMEOUT_S", "0.05")
    monkeypatch.setenv("ASPENOPS_HYSYS_STATUS_POLL_S", "0.001")
    monkeypatch.setenv("ASPENOPS_HYSYS_STATUS_STABLE_SAMPLES", "1")


def test_numeric_threshold_contract_uses_operator_and_tolerance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure_fast_poll(monkeypatch)
    node = convergence_node(
        convergence_operator=">=",
        convergence_threshold=0.95,
        convergence_tolerance=0.01,
    )
    accepted = FakeHysysBackend(0.945)
    accepted.configure_convergence_nodes([node])
    rejected = FakeHysysBackend(0.93)
    rejected.configure_convergence_nodes([node])

    accepted_result = accepted.run()
    rejected_result = rejected.run()

    assert accepted_result["convergence_state"] == "converged"
    assert accepted_result["status_nodes"][0]["raw_value"] == 0.945
    assert rejected_result["convergence_state"] == "not_converged"


@pytest.mark.parametrize(
    ("operator", "value", "expected"),
    [
        (">", 1.011, "converged"),
        (">", 1.0, "not_converged"),
        ("<=", 1.01, "converged"),
        ("<", 0.98, "converged"),
        ("==", 1.005, "converged"),
        ("==", 1.02, "not_converged"),
    ],
)
def test_all_threshold_operators(
    monkeypatch: pytest.MonkeyPatch,
    operator: str,
    value: float,
    expected: str,
) -> None:
    configure_fast_poll(monkeypatch)
    node = convergence_node(
        convergence_operator=operator,
        convergence_threshold=1.0,
        convergence_tolerance=0.01,
    )
    backend = FakeHysysBackend(value)
    backend.configure_convergence_nodes([node])

    assert backend.run()["convergence_state"] == expected


def test_string_enum_contract_is_trimmed_and_case_insensitive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure_fast_poll(monkeypatch)
    node = convergence_node(
        converged_values=["SOLVED", "ready"],
        not_converged_values=["FAILED", "blocked"],
    )
    accepted = FakeHysysBackend(" solved ")
    accepted.configure_convergence_nodes([node])
    rejected = FakeHysysBackend("Failed")
    rejected.configure_convergence_nodes([node])

    assert accepted.run()["convergence_state"] == "converged"
    assert rejected.run()["convergence_state"] == "not_converged"


def test_unknown_custom_enum_value_still_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    configure_fast_poll(monkeypatch)
    node = convergence_node(
        converged_values=["SOLVED"],
        not_converged_values=["FAILED"],
    )
    backend = FakeHysysBackend("PENDING")
    backend.configure_convergence_nodes([node])

    assert backend.run()["convergence_state"] == "unknown"


def test_default_normalization_remains_backward_compatible() -> None:
    assert HysysBackend._normalize_convergence_value(True) == "converged"
    assert HysysBackend._normalize_convergence_value(False) == "not converged"
    assert HysysBackend._normalize_convergence_value(1) == "converged"
    assert HysysBackend._normalize_convergence_value(0.0) == "not converged"
    assert HysysBackend._normalize_convergence_value(2.0) == 2.0


def test_contract_marker_matching_is_type_safe_and_finite() -> None:
    assert HysysBackend._contract_value_matches(True, True)
    assert not HysysBackend._contract_value_matches(1, True)
    assert HysysBackend._contract_value_matches(" OK ", "ok")
    assert not HysysBackend._contract_value_matches(1, "1")
    assert HysysBackend._contract_value_matches(1, 1.0)
    assert not HysysBackend._contract_value_matches(float("nan"), 1.0)
    assert not HysysBackend._contract_value_matches("1", 1.0)
    assert not HysysBackend._contract_value_matches([], {"unsupported": True})


def test_threshold_contract_leaves_non_numeric_or_nonfinite_signal_unclassified() -> None:
    node = convergence_node(
        convergence_operator=">=",
        convergence_threshold=1.0,
    )
    assert HysysBackend._normalize_convergence_value("pending", node) == "pending"
    value = HysysBackend._normalize_convergence_value(float("nan"), node)
    assert value != value


def write_registry(tmp_path: Path, locator: dict[str, Any]) -> Path:
    path = tmp_path / "registry.json"
    path.write_text(
        json.dumps(
            {
                "nodes": {
                    "solver.status.converged": {
                        "backend": "hysys",
                        "access": "read",
                        "role": "convergence",
                        "locator": {
                            "spreadsheet": "ASPENOPS_IO",
                            "cell": "C1",
                            **locator,
                        },
                    }
                }
            },
            allow_nan=True,
        ),
        encoding="utf-8",
    )
    return path


@pytest.mark.parametrize(
    ("locator", "message"),
    [
        ({"convergence_operator": ">="}, "define convergence_operator and"),
        ({"convergence_threshold": 1.0}, "define convergence_operator and"),
        ({"convergence_tolerance": 0.1}, "cannot define convergence_tolerance"),
        (
            {"convergence_operator": "!=", "convergence_threshold": 1.0},
            "Invalid convergence operator",
        ),
        (
            {"convergence_operator": ">=", "convergence_threshold": float("nan")},
            "threshold.*finite numeric",
        ),
        (
            {"convergence_operator": ">=", "convergence_threshold": True},
            "threshold.*finite numeric",
        ),
        (
            {
                "convergence_operator": ">=",
                "convergence_threshold": 1.0,
                "convergence_tolerance": -1.0,
            },
            "tolerance.*finite non-negative",
        ),
        (
            {
                "convergence_operator": ">=",
                "convergence_threshold": 1.0,
                "convergence_tolerance": True,
            },
            "tolerance.*finite non-negative",
        ),
        ({"converged_values": []}, "converged_values must be a non-empty array"),
        ({"converged_values": [" "]}, "values must not be empty strings"),
        ({"converged_values": [["bad"]]}, "finite scalar JSON values"),
        ({"converged_values": [1, 1.0]}, "must contain unique values"),
        ({"converged_values": ["OK", " ok "]}, "must contain unique values"),
        (
            {"converged_values": ["OK"], "not_converged_values": [" ok "]},
            "both converged and not converged",
        ),
        (
            {
                "convergence_operator": ">=",
                "convergence_threshold": 1.0,
                "converged_values": ["OK"],
            },
            "cannot mix threshold and enumerated",
        ),
    ],
)
def test_registry_rejects_ambiguous_convergence_contracts(
    tmp_path: Path,
    locator: dict[str, Any],
    message: str,
) -> None:
    with pytest.raises(RegistryError, match=message):
        NodeRegistry(write_registry(tmp_path, locator))


def test_registry_preserves_valid_threshold_contract(tmp_path: Path) -> None:
    registry = NodeRegistry(
        write_registry(
            tmp_path,
            {
                "convergence_operator": "<=",
                "convergence_threshold": 0.001,
                "convergence_tolerance": 1e-6,
            },
        )
    )

    node = registry.convergence_nodes("hysys")[0]
    assert node.locator["convergence_operator"] == "<="
    assert node.locator["convergence_threshold"] == 0.001
