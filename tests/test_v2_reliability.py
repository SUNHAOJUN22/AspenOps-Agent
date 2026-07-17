from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from aspenops_nexus.backends.base import (
    SimulatorBackend,
    TransactionState,
    WriteTransactionError,
)
from aspenops_nexus.backends.mock import MockBackend
from aspenops_nexus.evaluation import evaluate
from aspenops_nexus.models import EvaluationRequest
from aspenops_nexus.registry import NodeRegistry, ResolvedNode

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "src/aspenops_nexus/data/mock-case.json"
REGISTRY = ROOT / "src/aspenops_nexus/data/node-registry.json"


class UnknownConvergenceBackend(MockBackend):
    def run(self) -> dict[str, Any]:
        return {
            "engine_returned": True,
            "converged": True,
            "convergence_state": "unknown",
        }


class CountingBackend(MockBackend):
    def __init__(self) -> None:
        super().__init__()
        self.read_count = 0

    def read(self, node: ResolvedNode) -> Any:
        self.read_count += 1
        return super().read(node)


class RollbackFailureBackend(SimulatorBackend):
    name = "mock"

    def __init__(self) -> None:
        self.values = {"a": 1.0, "b": 2.0}
        self.write_calls = 0

    def open(self, model_path: Path, *, visible: bool = False) -> None:
        del model_path, visible

    def close(self) -> None:
        return None

    def reinitialize(self) -> None:
        return None

    def read(self, node: ResolvedNode) -> Any:
        return self.values[node.key]

    def write(self, node: ResolvedNode, value: Any) -> None:
        self.write_calls += 1
        if self.write_calls == 2:
            self.values[node.key] = value
            raise RuntimeError("partial write")
        if self.write_calls >= 3:
            raise RuntimeError("rollback unavailable")
        self.values[node.key] = value

    def run(self) -> dict[str, Any]:
        return {"engine_returned": True, "convergence_state": "converged", "converged": True}

    def runtime_identity(self) -> dict[str, Any]:
        return {"backend": self.name}


def request_with_duplicate_reads() -> EvaluationRequest:
    return EvaluationRequest.from_dict(
        {
            "model_path": str(MODEL),
            "registry_path": str(REGISTRY),
            "backend": "mock",
            "writes": [],
            "reads": [
                {
                    "key": "stream.output.purity",
                    "identifiers": {"stream": "PRODUCT"},
                    "unit": "fraction",
                }
            ],
            "constraints": [
                {
                    "name": "purity",
                    "key": "stream.output.purity",
                    "identifiers": {"stream": "PRODUCT"},
                    "operator": ">=",
                    "value": 0.5,
                    "unit": "fraction",
                }
            ],
        }
    )


def test_unknown_convergence_fails_closed() -> None:
    backend = UnknownConvergenceBackend()
    backend.open(MODEL)
    result = evaluate(backend, NodeRegistry(REGISTRY), request_with_duplicate_reads())
    assert not result.ok
    assert not result.converged
    assert "simulator_not_converged:unknown" in result.violations


def test_evaluation_reads_duplicate_node_once() -> None:
    backend = CountingBackend()
    backend.open(MODEL)
    result = evaluate(backend, NodeRegistry(REGISTRY), request_with_duplicate_reads())
    assert result.ok
    assert result.diagnostics["io"]["unique_read_nodes"] == 1
    assert result.diagnostics["io"]["avoided_duplicate_reads"] == 1
    assert result.diagnostics["io"]["com_reads"] == 1


def test_rollback_failure_taints_transaction() -> None:
    backend = RollbackFailureBackend()
    nodes = [
        ResolvedNode("a", "readwrite", None, None, ("a",), {}, None, None, False, "mock", {}, "", ""),
        ResolvedNode("b", "readwrite", None, None, ("b",), {}, None, None, False, "mock", {}, "", ""),
    ]
    with pytest.raises(WriteTransactionError) as caught:
        backend.bulk_write([(nodes[0], 10.0), (nodes[1], 20.0)])
    assert caught.value.state is TransactionState.TAINTED
    assert caught.value.rollback_errors
