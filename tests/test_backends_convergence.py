from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import aspenops_nexus.backends.aspen_plus as aspen_module
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
        self.async_modes: list[bool] = []

    def Run2(self, asynchronous: bool = False) -> None:
        self.run_calls += 1
        self.async_modes.append(asynchronous)


class FakeDelayedAspenEngine(FakeAspenEngine):
    def __init__(self, running_samples: int) -> None:
        super().__init__()
        self._configured_running_samples = running_samples
        self._remaining_running_samples = 0

    def Run2(self, asynchronous: bool = False) -> None:
        super().Run2(asynchronous)
        if asynchronous:
            self._remaining_running_samples = max(self._configured_running_samples, 0)

    @property
    def IsRunning(self) -> bool:
        if self._remaining_running_samples > 0:
            self._remaining_running_samples -= 1
            return True
        return False


class FakeLateStartingAspenEngine(FakeAspenEngine):
    def __init__(self, idle_samples: int, running_samples: int) -> None:
        super().__init__()
        self._idle_samples = idle_samples
        self._running_samples = running_samples

    @property
    def IsRunning(self) -> bool:
        if self._idle_samples > 0:
            self._idle_samples -= 1
            return False
        if self._running_samples > 0:
            self._running_samples -= 1
            return True
        return False


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
    monkeypatch.setenv("ASPENOPS_STATUS_STARTUP_TIMEOUT_S", "0.05")
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
    assert backend.document.Engine.async_modes == [False]


def test_aspen_backend_runs_visible_simulation_asynchronously(monkeypatch: Any) -> None:
    configure_fast_aspen_poll(monkeypatch)
    backend = AspenPlusBackend()
    backend.document = FakeAspenDocument("Run completed and converged")
    backend.document.Engine = FakeDelayedAspenEngine(running_samples=3)
    backend.visible = True

    result = backend.run()

    assert result["converged"] is True
    assert backend.document.Engine.run_calls == 1
    assert backend.document.Engine.async_modes == [True]
    assert result["engine_idle"] is True


@pytest.mark.parametrize(
    ("setting", "value"),
    [
        ("ASPENOPS_STATUS_TIMEOUT_S", "nan"),
        ("ASPENOPS_STATUS_POLL_S", "0"),
        ("ASPENOPS_STATUS_STABLE_SAMPLES", "0"),
        ("ASPENOPS_STATUS_STARTUP_TIMEOUT_S", "not-a-number"),
    ],
)
def test_invalid_aspen_poll_configuration_does_not_start_simulation(
    monkeypatch: Any, setting: str, value: str
) -> None:
    for name in (
        "ASPENOPS_STATUS_TIMEOUT_S",
        "ASPENOPS_STATUS_POLL_S",
        "ASPENOPS_STATUS_STABLE_SAMPLES",
        "ASPENOPS_STATUS_STARTUP_TIMEOUT_S",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv(setting, value)
    backend = AspenPlusBackend()
    backend.document = FakeAspenDocument("Run completed and converged")
    backend.visible = True

    with pytest.raises(ValueError):
        backend.run()

    assert backend.document.Engine.run_calls == 0


def test_aspen_visible_backend_allows_delayed_startup(monkeypatch: Any) -> None:
    configure_fast_aspen_poll(monkeypatch)
    backend = AspenPlusBackend()
    backend.document = FakeAspenDocument("Run completed and converged")
    backend.document.Engine = FakeLateStartingAspenEngine(idle_samples=3, running_samples=2)
    backend.visible = True

    result = backend.run()

    assert result["converged"] is True
    assert backend.document.Engine.async_modes == [True]
    assert result["convergence_evidence"]["samples"] == 6


def test_aspen_visible_backend_rejects_stale_success_without_running(monkeypatch: Any) -> None:
    configure_fast_aspen_poll(monkeypatch)
    backend = AspenPlusBackend()
    backend.document = FakeAspenDocument("Run completed and converged")
    backend.visible = True

    result = backend.run()

    assert backend.document.Engine.run_calls == 1
    assert backend.document.Engine.async_modes == [True]
    assert result["converged"] is False
    assert result["convergence_state"] == "timeout"
    assert result["convergence_evidence"]["error"] == (
        "engine never reported running within the startup confirmation window"
    )


def test_evaluate_rejects_success_read_after_aspen_status_deadline(monkeypatch: Any) -> None:
    now = [0.0]
    calls = [0]

    class SlowStatusEngine(FakeAspenEngine):
        @property
        def IsRunning(self) -> bool:
            calls[0] += 1
            if calls[0] == 1:
                return True
            now[0] += 2.0
            return False

    def sleep(seconds: float) -> None:
        now[0] += seconds

    real_poll = aspen_module.poll_engine_idle

    def controlled_poll(reader: Any, **kwargs: Any) -> Any:
        return real_poll(reader, **kwargs, clock=lambda: now[0], sleeper=sleep)

    monkeypatch.setattr(aspen_module, "poll_engine_idle", controlled_poll)
    monkeypatch.setenv("ASPENOPS_STATUS_TIMEOUT_S", "1")
    monkeypatch.setenv("ASPENOPS_STATUS_STARTUP_TIMEOUT_S", "0.5")
    monkeypatch.setenv("ASPENOPS_STATUS_POLL_S", "0.1")
    monkeypatch.setenv("ASPENOPS_STATUS_STABLE_SAMPLES", "1")
    backend = AspenPlusBackend()
    backend.document = FakeAspenDocument("Run completed and converged")
    backend.document.Engine = SlowStatusEngine()
    backend.visible = True
    request = EvaluationRequest.from_dict(
        {
            "model_path": str(MODEL),
            "registry_path": str(REGISTRY),
            "backend": "aspen_plus",
            "writes": [],
            "reads": [],
            "reinitialize": False,
        }
    )

    result = evaluate(backend, NodeRegistry(REGISTRY), request)

    assert result.ok is False
    assert "simulator_not_converged:timeout" in result.violations
    assert backend.document.Engine.async_modes == [True]
    assert calls[0] == 2


def test_visible_aspen_poll_uses_runtime_timeout_by_default(monkeypatch: Any) -> None:
    monkeypatch.delenv("ASPENOPS_STATUS_TIMEOUT_S", raising=False)
    monkeypatch.delenv("ASPENOPS_TIMEOUT_S", raising=False)
    monkeypatch.delenv("ASPENOPS_STATUS_STARTUP_TIMEOUT_S", raising=False)
    backend = AspenPlusBackend()
    backend.document = FakeAspenDocument("Run completed and converged")
    backend.visible = True
    captured: dict[str, float] = {}
    real_poll = aspen_module.poll_engine_idle

    def capture_timeout(
        read_running: Any,
        *,
        timeout_s: float,
        poll_interval_s: float,
        stable_samples: int,
        require_running_observation: bool = False,
        startup_timeout_s: float | None = None,
    ) -> Any:
        captured["timeout_s"] = timeout_s
        captured["startup_timeout_s"] = startup_timeout_s
        captured["require_running_observation"] = require_running_observation
        return real_poll(
            read_running,
            timeout_s=0.05,
            poll_interval_s=0.001,
            stable_samples=1,
            require_running_observation=require_running_observation,
            startup_timeout_s=startup_timeout_s,
        )

    monkeypatch.setattr(aspen_module, "poll_engine_idle", capture_timeout)

    backend.run()

    assert captured["timeout_s"] == 1200.0
    assert captured["startup_timeout_s"] == 30.0
    assert captured["require_running_observation"] is True


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
    running = backend._engine_running
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


@pytest.mark.parametrize(
    ("setting", "value"),
    [
        ("ASPENOPS_HYSYS_STATUS_TIMEOUT_S", "nan"),
        ("ASPENOPS_HYSYS_STATUS_POLL_S", "0"),
        ("ASPENOPS_HYSYS_STATUS_STABLE_SAMPLES", "0"),
        ("ASPENOPS_HYSYS_STATUS_TIMEOUT_S", "not-a-number"),
    ],
)
def test_invalid_hysys_poll_configuration_does_not_enable_solver(
    monkeypatch: Any, setting: str, value: str
) -> None:
    configure_fast_hysys_poll(monkeypatch)
    monkeypatch.setenv(setting, value)
    backend = FakeHysysBackend(True)

    with pytest.raises(ValueError):
        backend.run()

    assert backend.case.Solver.CanSolve is False


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
