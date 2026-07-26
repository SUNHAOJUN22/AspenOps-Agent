from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from aspenops_nexus.backends.aspen_plus import AspenPlusBackend
from aspenops_nexus.backends.hysys import HysysBackend
from aspenops_nexus.registry import ResolvedNode


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
