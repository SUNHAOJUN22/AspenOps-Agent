from __future__ import annotations

import math
from pathlib import Path

import pytest

from aspenops.backends.aspen_plus import AspenPlusBackend
from aspenops.continuation import adaptive_continuation
from aspenops.design import Variable, latin_hypercube, nearest_neighbor_order
from aspenops.errors import (
    AccessViolation,
    CaseOpenError,
    ConfigurationError,
    ValidationError,
    WorkerError,
    WorkerTimeout,
)
from aspenops.evaluation import build_evaluation, safe_evaluate
from aspenops.models import EvaluationResult, RunReport, RunState, ValueRead, ValueWrite
from aspenops.optimizer import OptimizationConfig, differential_evolution
from aspenops.pool import CasePool
from aspenops.service import SessionManager
from aspenops.worker import WorkerClient


def _case(tmp_path: Path) -> Path:
    path = tmp_path / "case.json"
    path.write_text("{}", encoding="utf-8")
    return path


def _temperature(value: float = 420.0) -> ValueWrite:
    return ValueWrite(
        key="block.input.temperature",
        identifiers={"block": "R-101"},
        value=value,
        unit="C",
    )


def _conversion() -> ValueRead:
    return ValueRead(
        key="block.output.conversion",
        identifiers={"block": "R-101"},
        unit="fraction",
    )


def test_timeout_never_implicitly_restarts_worker(tmp_path: Path) -> None:
    worker = WorkerClient("mock", timeout_s=0.05, backend_options={"run_delay_s": 0.3})
    worker.start()
    worker.call("open", {"path": str(_case(tmp_path))})
    with pytest.raises(WorkerTimeout):
        worker.call("run")
    assert not worker.alive
    with pytest.raises(WorkerError, match="explicitly start and reopen"):
        worker.call("run")


def test_read_only_is_enforced_by_service_and_worker(tmp_path: Path) -> None:
    case = _case(tmp_path)
    manager = SessionManager(allowed_roots=[tmp_path], default_timeout_s=10)
    session = manager.open_session(case, backend="mock", read_only=True)
    assert session.read_only
    with pytest.raises(AccessViolation):
        manager.set_values(session.session_id, [_temperature()])
    with pytest.raises(AccessViolation):
        manager.save(session.session_id)
    manager.close_all()

    with WorkerClient("mock", timeout_s=10) as worker:
        worker.call("open", {"path": str(case), "read_only": True})
        with pytest.raises(WorkerError, match="Read-only"):
            worker.call(
                "set_many",
                {"writes": [_temperature().model_dump(mode="json")]},
            )
        with pytest.raises(WorkerError, match="Read-only"):
            worker.call("save", {"path": None})


def test_dead_session_must_be_reopened(tmp_path: Path) -> None:
    manager = SessionManager(allowed_roots=[tmp_path], default_timeout_s=0.05)
    session = manager.open_session(
        _case(tmp_path),
        backend="mock",
        backend_options={"run_delay_s": 0.3},
        timeout_s=0.05,
    )
    with pytest.raises(WorkerTimeout):
        manager.run(session.session_id)
    assert not manager.list_sessions()[0].alive
    with pytest.raises(ConfigurationError, match="close and reopen"):
        manager.run(session.session_id)
    manager.close_all()


def test_aspen_status_and_read_only_open_fail_closed() -> None:
    classify = AspenPlusBackend._classify_status
    assert classify(None) == RunState.UNKNOWN
    assert classify("mystery") == RunState.UNKNOWN
    assert classify("Calculation completed successfully") == RunState.CONVERGED
    assert classify("solver diverged") == RunState.FAILED

    calls: list[tuple[object, ...]] = []

    class Document:
        def InitFromArchive2(self, *args: object) -> None:
            calls.append(args)
            if len(args) == 1:
                return
            raise TypeError("read-only parameter unsupported")

    with pytest.raises(CaseOpenError, match="read-only"):
        AspenPlusBackend()._open_document(Document(), Path("case.bkp"), read_only=True)
    assert calls == [("case.bkp", True)]


def test_nonfinite_values_are_rejected_or_infeasible(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="finite"):
        safe_evaluate("x + 1", {"x": math.nan})
    with pytest.raises(ValidationError):
        safe_evaluate("exp(10000)", {})

    result = build_evaluation(
        inputs={"x": 1.0},
        outputs={"y": math.inf},
        run=RunReport(state=RunState.CONVERGED),
        objective_expression="y",
    )
    assert not result.feasible
    assert math.isinf(result.constraint_violation)
    assert "validation_error" in result.metadata

    manager = SessionManager(allowed_roots=[tmp_path], default_timeout_s=10)
    session = manager.open_session(_case(tmp_path), backend="mock")
    with pytest.raises(WorkerError, match="finite"):
        manager.set_values(session.session_id, [_temperature(math.nan)])
    manager.close_all()


def test_design_and_continuation_validation() -> None:
    variable = Variable("n", 0.6, 1.6, integer=True)
    assert variable.project(0.6) == 1.0
    assert variable.project(1.6) == 1.0
    with pytest.raises(ValidationError, match="no feasible integer"):
        Variable("bad", 0.1, 0.9, integer=True)

    duplicates = [Variable("x", 0, 1), Variable("x", 1, 2)]
    with pytest.raises(ValidationError, match="unique"):
        latin_hypercube(duplicates, 2)

    points = [
        {"small": 0.0, "large": 0.0},
        {"small": 1.0, "large": 1.0},
        {"small": 0.0, "large": 50.0},
    ]
    assert nearest_neighbor_order(points)[:2] == [0, 2]

    def evaluate(point: dict[str, float]) -> tuple[dict[str, float], bool]:
        return point, True

    with pytest.raises(ValidationError, match="growth"):
        adaptive_continuation({"x": 0}, {"x": 1}, evaluate, growth=1)
    with pytest.raises(ValidationError, match="shrink"):
        adaptive_continuation({"x": 0}, {"x": 1}, evaluate, shrink=1)
    with pytest.raises(ValidationError, match="max_attempts"):
        adaptive_continuation({"x": 0}, {"x": 1}, evaluate, max_attempts=0)


def test_optimizer_rejects_duplicate_keys() -> None:
    variables = [Variable("x", 0, 1), Variable("x", 1, 2)]

    def evaluate(point: dict[str, float]) -> EvaluationResult:
        return EvaluationResult(
            inputs=point,
            outputs={},
            run=RunReport(state=RunState.CONVERGED),
            objective=0,
            feasible=True,
        )

    with pytest.raises(ValidationError, match="unique"):
        differential_evolution(variables, evaluate, OptimizationConfig(population_size=4))


def test_pool_is_permanently_broken_after_worker_timeout(tmp_path: Path) -> None:
    pool = CasePool(
        backend="mock",
        case_path=_case(tmp_path),
        workers=1,
        timeout_s=0.05,
        backend_options={"run_delay_s": 0.3},
    )
    with pytest.raises(WorkerTimeout):
        pool.evaluate_many([[_temperature()]], [_conversion()])
    with pytest.raises(WorkerError, match="broken"):
        pool.evaluate_many([[_temperature()]], [_conversion()])
    pool.close()
