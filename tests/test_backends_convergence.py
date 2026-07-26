from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from aspenops_nexus.backends.aspen_plus_strict import AspenPlusBackend
from aspenops_nexus.backends.factory import create_backend
from aspenops_nexus.backends.hysys import HysysBackend
from aspenops_nexus.backends.mock import MockBackend
from aspenops_nexus.evaluation import evaluate
from aspenops_nexus.models import EvaluationRequest
from aspenops_nexus.registry import NodeRegistry, ResolvedNode

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "src/aspenops_nexus/data/mock-case.json"
REGISTRY = ROOT / "src/aspenops_nexus/data/node-registry.json"


class FakeStatusNode:
    def __init__(self, value: Any) -> None:
        self.Value = value


class FakeTree:
    def __init__(self, value: Any | None) -> None:
        self.value = value

    def FindNode(self, path: str) -> FakeStatusNode | None:
        del path
        return None if self.value is None else FakeStatusNode(self.value)


class FakeAspenEngine:
    IsRunning = False

    def __init__(self) -> None:
        self.Errors = None
        self.Messages = None
        self.Warnings = None
        self.run_calls = 0

    def Run2(self) -> None:
        self.run_calls += 1


class FakeAspenDocument:
    def __init__(self, status: Any | None) -> None:
        self.Engine = FakeAspenEngine()
        self.Tree = FakeTree(status)


class FakeHysysBackend(HysysBackend):
    def __init__(self, value: Any) -> None:
        super().__init__()
        self.value = value
        self.case = SimpleNamespace(Solver=SimpleNamespace(IsSolving=False, CanSolve=False))

    def read(self, node: ResolvedNode) -> Any:
        del node
        return self.value


class NonFiniteConstraintBackend(MockBackend):
    def read(self, node: ResolvedNode) -> Any:
        if node.key == "stream.output.purity":
            return float("nan")
        return super().read(node)


class StringFlagBackend(MockBackend):
    def run(self) -> dict[str, Any]:
        return {
            "engine_returned": "false",
            "converged": True,
            "convergence_state": "converged",
        }


def convergence_node() -> ResolvedNode:
    return ResolvedNode(
        key="case.output.convergence",
        access="read",
        native_unit=None,
        quantity=None,
        paths=(),
        identifiers={},
        lower=None,
        upper=None,
        integer=False,
        backend="hysys",
        locator={"spreadsheet": "ASPENOPS_IO", "cell": "C4"},
        verification="project-required",
        description="Project convergence signal",
        role="convergence",
    )


def constraint_only_request() -> EvaluationRequest:
    return EvaluationRequest.from_dict(
        {
            "model_path": str(MODEL),
            "registry_path": str(REGISTRY),
            "backend": "mock",
            "writes": [],
            "reads": [],
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


def empty_request() -> EvaluationRequest:
    return EvaluationRequest.from_dict(
        {
            "model_path": str(MODEL),
            "registry_path": str(REGISTRY),
            "backend": "mock",
            "writes": [],
            "reads": [],
        }
    )


def configure_fast_aspen_poll(monkeypatch: Any) -> None:
    monkeypatch.setenv("ASPENOPS_STATUS_TIMEOUT_S", "0.05")
    monkeypatch.setenv("ASPENOPS_STATUS_POLL_S", "0.001")
    monkeypatch.setenv("ASPENOPS_STATUS_STABLE_SAMPLES", "1")


def configure_fast_hysys_poll(monkeypatch: Any) -> None:
    monkeypatch.setenv("ASPENOPS_HYSYS_STATUS_TIMEOUT_S", "0.05")
    monkeypatch.setenv("ASPENOPS_HYSYS_STATUS_POLL_S", "0.001")
    monkeypatch.setenv("ASPENOPS_HYSYS_STATUS_STABLE_SAMPLES", "1")


def test_aspen_backend_accepts_explicit_success_when_idle(monkeypatch: Any) -> None:
    configure_fast_aspen_poll(monkeypatch)
    backend = AspenPlusBackend()
    backend.document = FakeAspenDocument("Run completed and converged")

    result = backend.run()

    assert result["converged"] is True
    assert result["convergence_state"] == "converged"
    assert backend.document.Engine.run_calls == 1


def test_aspen_backend_rejects_negative_evidence(monkeypatch: Any) -> None:
    configure_fast_aspen_poll(monkeypatch)
    backend = AspenPlusBackend()
    backend.document = FakeAspenDocument("Run not converged")

    result = backend.run()

    assert result["converged"] is False
    assert result["convergence_state"] == "not_converged"


def test_aspen_backend_fails_closed_without_success_evidence(monkeypatch: Any) -> None:
    configure_fast_aspen_poll(monkeypatch)
    backend = AspenPlusBackend()
    backend.document = FakeAspenDocument(None)

    result = backend.run()

    assert result["converged"] is False
    assert result["convergence_state"] == "unknown"


def test_factory_aspen_running_state_does_not_use_string_truthiness() -> None:
    backend = create_backend("aspen_plus")
    running = getattr(backend, "_engine_running")
    assert running(SimpleNamespace(IsRunning="False")) is False
    assert running(SimpleNamespace(IsRunning="TRUE")) is True
    assert running(SimpleNamespace(IsRunning=-1)) is True
    assert running(SimpleNamespace(IsRunning=0)) is False
    assert running(SimpleNamespace(IsRunning="unknown")) is None


def test_hysys_running_state_does_not_use_string_truthiness() -> None:
    assert HysysBackend._solver_running(SimpleNamespace(IsSolving="False")) is False
    assert HysysBackend._solver_running(SimpleNamespace(IsSolving="TRUE")) is True
    assert HysysBackend._solver_running(SimpleNamespace(IsSolving=-1)) is True
    assert HysysBackend._solver_running(SimpleNamespace(IsSolving=0)) is False
    assert HysysBackend._solver_running(SimpleNamespace(IsSolving="unknown")) is None


def test_hysys_backend_uses_project_boolean_convergence_node(monkeypatch: Any) -> None:
    configure_fast_hysys_poll(monkeypatch)
    backend = FakeHysysBackend(True)
    backend.configure_convergence_nodes([convergence_node()])

    result = backend.run()

    assert result["converged"] is True
    assert result["convergence_state"] == "converged"
    assert backend.case.Solver.CanSolve is True


def test_hysys_backend_rejects_false_project_signal(monkeypatch: Any) -> None:
    configure_fast_hysys_poll(monkeypatch)
    backend = FakeHysysBackend(False)
    backend.configure_convergence_nodes([convergence_node()])

    result = backend.run()

    assert result["converged"] is False
    assert result["convergence_state"] == "not_converged"


def test_hysys_backend_fails_closed_without_project_signal(monkeypatch: Any) -> None:
    configure_fast_hysys_poll(monkeypatch)
    backend = FakeHysysBackend(True)

    result = backend.run()

    assert result["converged"] is False
    assert result["convergence_state"] == "unknown"


def test_non_finite_constraint_fails_closed_on_every_software_gate() -> None:
    backend = NonFiniteConstraintBackend()
    backend.open(MODEL)

    result = evaluate(backend, NodeRegistry(REGISTRY), constraint_only_request())

    assert "constraint_non_finite:purity" in result.violations
    assert "constraint_failed:purity" in result.violations
    assert result.diagnostics["constraints"][0]["passed"] is False
    assert not result.feasible
    json.dumps(result.to_dict(), allow_nan=False)


def test_backend_protocol_rejects_truthy_string_flags_on_every_gate() -> None:
    backend = StringFlagBackend()
    backend.open(MODEL)

    result = evaluate(backend, NodeRegistry(REGISTRY), empty_request())

    assert result.communication_ok is True
    assert result.engine_ok is False
    assert "execution_error:TypeError" in result.violations
    assert not result.ok
    json.dumps(result.to_dict(), allow_nan=False)
