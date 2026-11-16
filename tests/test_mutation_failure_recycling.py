from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from aspenops_nexus.backends.hysys import HysysBackend
from aspenops_nexus.backends.mock import MockBackend
from aspenops_nexus.evaluation import evaluate
from aspenops_nexus.models import EvaluationRequest, EvaluationResult
from aspenops_nexus.pool import CasePool
from aspenops_nexus.registry import NodeRegistry, ResolvedNode
from aspenops_nexus.worker import WorkerHandle

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "src/aspenops_nexus/data/mock-case.json"
REGISTRY = ROOT / "src/aspenops_nexus/data/node-registry.json"


def request(*, backend: str = "mock", warm: bool = False) -> EvaluationRequest:
    return EvaluationRequest.from_dict(
        {
            "model_path": str(MODEL),
            "registry_path": str(REGISTRY),
            "backend": backend,
            "writes": [],
            "reads": [],
            "reset_mode": "warm_start" if warm else "reinitialize",
        }
    )


class PartiallyResetSolver:
    def __init__(self) -> None:
        self.can_solve = True

    @property
    def CanSolve(self) -> bool:
        return self.can_solve

    @CanSolve.setter
    def CanSolve(self, enabled: bool) -> None:
        if enabled:
            raise RuntimeError("transport failed after disabling the solver")
        self.can_solve = False


def test_failed_native_adapter_reset_marks_uncertain_state_for_recycling() -> None:
    solver = PartiallyResetSolver()
    backend = HysysBackend()
    backend.case = SimpleNamespace(Solver=solver)
    result = evaluate(backend, NodeRegistry(REGISTRY), request(backend="hysys"))
    assert solver.CanSolve is False
    assert result.ok is False
    assert result.communication_ok is False
    assert result.diagnostics["state_trace"] == ["received", "plan_compiled", "failed"]
    assert result.violations == ["execution_error:BackendError"]
    assert result.diagnostics.get("worker_tainted") is True


class PartiallyMutatingBackend(MockBackend):
    def __init__(self, stage: str) -> None:
        super().__init__()
        self.stage = stage

    def reinitialize(self) -> None:
        if self.stage == "reset":
            self.state["feed_temperature_C"] = -999.0
            raise RuntimeError("reset interrupted after changing state")
        super().reinitialize()

    def bulk_write(self, items: list[tuple[ResolvedNode, Any]]) -> None:
        if self.stage == "write":
            self.state["feed_temperature_C"] = -999.0
            raise RuntimeError("unclassified backend failure during write")
        super().bulk_write(items)


@pytest.mark.parametrize("warm", [False, True])
def test_unclassified_write_failure_cannot_reuse_possibly_mutated_state(warm: bool) -> None:
    backend = PartiallyMutatingBackend("write")
    backend.open(MODEL)
    try:
        result = evaluate(backend, NodeRegistry(REGISTRY), request(warm=warm))
        assert backend.state["feed_temperature_C"] == -999.0
        assert result.ok is False
        assert result.diagnostics.get("worker_tainted") is True
    finally:
        backend.close()


def test_rejected_plan_does_not_taint_or_mutate_a_healthy_worker() -> None:
    backend = PartiallyMutatingBackend("reset")
    backend.open(MODEL)
    initial_state = dict(backend.state)
    payload = request().to_dict()
    payload["reads"] = [{"key": "unregistered.output", "identifiers": {}}]
    try:
        result = evaluate(backend, NodeRegistry(REGISTRY), EvaluationRequest.from_dict(payload))
        assert result.ok is False
        assert result.diagnostics.get("worker_tainted", False) is False
        assert backend.state == initial_state
    finally:
        backend.close()


def test_reset_failure_recycles_generation_and_blocks_warm_continuation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    backend = PartiallyMutatingBackend("reset")
    backend.open(MODEL)
    calls = 0

    def fail_reset(handle: WorkerHandle, evaluation: EvaluationRequest) -> EvaluationResult:
        nonlocal calls
        calls += 1
        return evaluate(backend, NodeRegistry(REGISTRY), evaluation, worker_id=handle.worker_id)

    monkeypatch.setattr("aspenops_nexus.pool.evaluate_on_worker", fail_reset)
    try:
        with CasePool(
            backend_name="mock",
            model_path=MODEL,
            registry_path=REGISTRY,
            workers=1,
            visible=False,
            cache_path=tmp_path / "cache.sqlite3",
        ) as pool:
            failed = pool.evaluate_many([request()])[0]
            assert failed.ok is False
            assert pool._handles[0].generation == 1
            assert failed.diagnostics["worker"]["recycle_reason"] == "tainted"
            assert failed.diagnostics["worker"]["old_generation"] == 0
            assert failed.diagnostics["worker"]["new_generation"] == 1
            warm_result = pool.evaluate_many([request(warm=True)])[0]
            assert warm_result.violations == ["warm_start_state_lost"]
            assert calls == 1
    finally:
        backend.close()
