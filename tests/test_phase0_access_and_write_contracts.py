from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from aspenops_nexus.backends.base import (
    SimulatorBackend,
    TransactionState,
    WriteTransactionError,
)
from aspenops_nexus.evaluation_plan import EvaluationPlanCompiler
from aspenops_nexus.models import EvaluationRequest
from aspenops_nexus.registry import NodeRegistry, RegistryError, ResolvedNode


def _registry(tmp_path: Path) -> NodeRegistry:
    path = tmp_path / "registry.json"
    path.write_text(
        json.dumps(
            {
                "schema": "aspenops.registry/v1",
                "nodes": {
                    "write.only": {
                        "backend": "mock",
                        "access": "write",
                        "unit": "1",
                        "identifiers": [],
                        "paths": ["write.only"],
                    },
                    "read.write": {
                        "backend": "mock",
                        "access": "readwrite",
                        "unit": "1",
                        "identifiers": [],
                        "paths": ["read.write"],
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    return NodeRegistry(path)


def _request(tmp_path: Path, **overrides: Any) -> EvaluationRequest:
    model = tmp_path / "model.json"
    model.write_text("{}", encoding="utf-8")
    payload: dict[str, Any] = {
        "model_path": str(model),
        "registry_path": str(tmp_path / "registry.json"),
        "backend": "mock",
        "writes": [],
        "reads": [],
    }
    payload.update(overrides)
    return EvaluationRequest.from_dict(payload)


@pytest.mark.parametrize(
    "request_fields",
    [
        {
            "reads": [
                {
                    "key": "write.only",
                    "identifiers": {},
                    "unit": "1",
                }
            ]
        },
        {
            "constraints": [
                {
                    "key": "write.only",
                    "identifiers": {},
                    "operator": ">=",
                    "value": 0.0,
                    "unit": "1",
                }
            ]
        },
        {
            "balances": [
                {
                    "name": "blocked",
                    "terms": [
                        {
                            "key": "write.only",
                            "identifiers": {},
                            "coefficient": 1.0,
                            "unit": "1",
                        }
                    ],
                }
            ]
        },
    ],
)
def test_write_only_nodes_cannot_be_read_by_any_plan_path(
    tmp_path: Path,
    request_fields: dict[str, Any],
) -> None:
    registry = _registry(tmp_path)
    with pytest.raises(RegistryError, match="write-only"):
        EvaluationPlanCompiler.compile(registry, _request(tmp_path, **request_fields))


def test_readwrite_node_remains_available_for_reads(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    request = _request(
        tmp_path,
        reads=[{"key": "read.write", "identifiers": {}, "unit": "1"}],
    )
    plan = EvaluationPlanCompiler.compile(registry, request)
    assert [node.key for node in plan.unique_reads] == ["read.write"]


def _node(key: str) -> ResolvedNode:
    return ResolvedNode(
        key=key,
        access="readwrite",
        native_unit=None,
        quantity=None,
        paths=(key,),
        identifiers={},
        lower=None,
        upper=None,
        integer=False,
        backend="mock",
        locator={},
        verification="project-required",
        description="",
    )


class ContractBackend(SimulatorBackend):
    name = "mock"

    def __init__(self, mode: str = "normal") -> None:
        self.mode = mode
        self.values: dict[str, Any] = {
            "numeric": 1.0,
            "flag": False,
            "label": "old",
        }

    def open(self, model_path: Path, *, visible: bool = False) -> None:
        del model_path, visible

    def close(self) -> None:
        return None

    def reinitialize(self) -> None:
        return None

    def write(self, node: ResolvedNode, value: Any) -> None:
        if self.mode == "ignore" and node.key in {"numeric", "label"}:
            return
        if self.mode == "coerce_bool" and isinstance(value, bool):
            self.values[node.key] = int(value)
            return
        self.values[node.key] = value

    def read(self, node: ResolvedNode) -> Any:
        return self.values[node.key]

    def run(self) -> dict[str, Any]:
        return {
            "engine_returned": True,
            "converged": True,
            "convergence_state": "converged",
        }

    def runtime_identity(self) -> dict[str, Any]:
        return {"backend": self.name}


def test_bulk_write_rejects_silently_ignored_numeric_write() -> None:
    backend = ContractBackend("ignore")
    with pytest.raises(WriteTransactionError) as caught:
        backend.bulk_write([(_node("numeric"), 2.0)])
    assert caught.value.state is TransactionState.ROLLED_BACK
    assert backend.values["numeric"] == 1.0


def test_bulk_write_rejects_silently_ignored_string_write() -> None:
    backend = ContractBackend("ignore")
    with pytest.raises(WriteTransactionError) as caught:
        backend.bulk_write([(_node("label"), "new")])
    assert caught.value.state is TransactionState.ROLLED_BACK
    assert backend.values["label"] == "old"


def test_bulk_write_rejects_boolean_coercion_and_taints_failed_rollback() -> None:
    backend = ContractBackend("coerce_bool")
    with pytest.raises(WriteTransactionError) as caught:
        backend.bulk_write([(_node("flag"), True)])
    assert caught.value.state is TransactionState.TAINTED
    assert caught.value.rollback_errors


def test_bulk_write_accepts_verified_discrete_and_numeric_values() -> None:
    backend = ContractBackend()
    backend.bulk_write(
        [
            (_node("numeric"), 2.0),
            (_node("flag"), True),
            (_node("label"), "new"),
        ]
    )
    assert backend.values == {"numeric": 2.0, "flag": True, "label": "new"}
