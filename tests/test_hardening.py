from __future__ import annotations

import math
from pathlib import Path

import pytest

from aspenops.backends.aspen_plus import AspenPlusBackend
from aspenops.backends.mock import MockBackend
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
from aspenops.evaluation import Balance, Constraint, build_evaluation, deb_better, safe_evaluate
from aspenops.models import EvaluationResult, RunReport, RunState, ValueRead, ValueWrite
from aspenops.optimizer import OptimizationConfig, differential_evolution
from aspenops.pool import CasePool
from aspenops.service import SessionManager
from aspenops.worker import WorkerClient


def test_worker_full_lifecycle(tmp_path: Path) -> None:
    case = tmp_path / "case.json"
    case.write_text("{}", encoding="utf-8")
    with WorkerClient("mock", timeout_s=10) as worker:
        worker.call("open", {"path": str(case)})
        worker.call(
            "set_many",
            {
                "writes": [
                    ValueWrite(
                        key="block.input.temperature",
                        identifiers={"block": "R-101"},
                        value=445,
                        unit="C",
                    ).model_dump(mode="json")
                ]
            },
        )
        assert RunReport.model_validate(worker.call("run")).state == RunState.CONVERGED


def test_worker_timeout_does_not_implicitly_restart(tmp_path: Path) -> None:
    case = tmp_path / "case.json"
    case.write_text("{}", encoding="utf-8")
    worker = WorkerClient("mock", timeout_s=0.05, backend_options={"run_delay_s": 0.3})
    worker.start()
    worker.call("open", {"path": str(case)})
    with pytest.raises(WorkerTimeout):
        worker.call("run")
    assert not worker.alive
    with pytest.raises(WorkerError, match="explicitly start and reopen"):
        worker.call("run")


def test_worker_read_only_is_enforced(tmp_path: Path) -> None:
    case = tmp_path / "case.json"
    case.write_text("{}", encoding="utf-8")
    with WorkerClient("mock", timeout_s=10) as worker:
        worker.call("open", {"path": str(case), "read_only": True})
        with pytest.raises(WorkerError, match="Read-only"):
            worker.call(
                "set_many",
                {
                    "writes": [
                        ValueWrite(
                            key="stream.input.temperature",
                            identifiers={"stream": "FEED"},
                            value=100,
                            unit="C",
                        ).model_dump(mode="json")
                    ]
                },
            )
        with pytest.raises(WorkerError, match="Read-only"):
            worker.call("save", {"path": None})


def test_service_read_only_and_dead_session(tmp_path: Path) -> None:
    case = tmp_path / "case.json"
    case.write_text("{}", encoding="utf-8")
    manager = SessionManager(allowed_roots=[tmp_path], default_timeout_s=10)
    session = manager.open_session(case, backend="mock", read_only=True)
    assert session.read_only
    with pytest.raises(AccessViolation):
        manager.set_values(
            session.session_id,
            [
                ValueWrite(
                    key="stream.input.temperature",
                    identifiers={"stream": "FEED"},
                    value=100,
                    unit="C",
                )
            ],
        )
    with pytest.raises(AccessViolation):
        manager.save(session.session_id)
    manager.close_session(session.session_id)
    with pytest.raises(ConfigurationError):
        manager.close_session(session.session_id)


def test_service_detects_dead_worker(tmp_path: Path) -> None:
    case = tmp_path / "case.json"
    case.write_text("{}", encoding="utf-8")
    manager = SessionManager(allowed_roots=[tmp_path], default_timeout_s=0.05)
    session = manager.open_session(
        case,
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


def test_mock_backend_direct_read_only_enforcement(tmp_path: Path) -> None:
    case = tmp_path / "case.json"
    case.write_text("{}", encoding="utf-8")
    backend = MockBackend()
    backend.open_case(case, read_only=True)
    with pytest.raises(AccessViolation):
        backend.set_raw("mock.feed.temperature", 90, "C")
    with pytest.raises(AccessViolation):
        backend.save()


def test_aspen_status_classification_is_fail_closed() -> None:
    classify = AspenPlusBackend._classify_status
    assert classify(None) == RunState.UNKNOWN
    assert classify("") == RunState.UNKNOWN
    assert classify("mystery code 8") == RunState.UNKNOWN
    assert classify("Calculation completed successfully") == RunState.CONVERGED
    assert classify("solver diverged") == RunState.FAILED


def test_aspen_read_only_open_never_falls_back_to_writable() -> None:
    calls: list[tuple[object, ...]] = []

    class Document:
        def InitFromArchive2(self, *args: object) -> None:
            calls.append(args)
            if len(args) == 1:
                return
            raise TypeError("read-only parameter unsupported")

    backend = AspenPlusBackend()
    with pytest.raises(CaseOpenError, match="read-only"):
        backend._open_document(Document(), Path("case.bkp"), read_only=True)
    assert calls == [("case.bkp", True)]


def test_safe_evaluate_rejects_nonfinite_values_and_results() -> None:
    with pytest.raises(ValidationError, match="finite"):
        safe_evaluate("x + 1", {"x": math.nan})
    with pytest.raises(ValidationError):
        safe_evaluate("exp(10000)", {})
    with pytest.raises(ValidationError):
        safe_evaluate("1 +", {})


def test_build_evaluation_marks_nonfinite_outputs_infeasible() -> None:
    result = build_evaluation(
        inputs={"x": 1.0},
        outputs={"y": math.inf},
        run=RunReport(state=RunState.CONVERGED),
        objective_expression="y",
    )
    assert not result.feasible
    assert math.isinf(result.constraint_violation)
    assert "validation_error" in result.metadata


def test_balance_and_constraint_validation() -> None:
    with pytest.raises(ValidationError):
        Constraint("x", "<=", 1, tolerance=-1).violation({"x": 0})
    with pytest.raises(ValidationError):
        Balance({}, 1, 1).residuals({})
    with pytest.raises(ValidationError):
        Balance({"x": 1}, 1, 1, scale_floor=0).residuals({"x": 1})


def test_deb_ordering_treats_nan_as_worst() -> None:
    run = RunReport(state=RunState.CONVERGED)
    bad = EvaluationResult(
        inputs={},
        outputs={},
        run=run,
        objective=math.nan,
        constraint_violation=math.nan,
        balance_violation=0,
        feasible=True,
    )
    good = EvaluationResult(
        inputs={},
        outputs={},
        run=run,
        objective=1,
        constraint_violation=0,
        balance_violation=0,
        feasible=True,
    )
    assert deb_better(good, bad)
    assert not deb_better(bad, good)


def test_integer_projection_stays_within_bounds() -> None:
    variable = Variable("n", 0.6, 1.6, integer=True)
    assert variable.project(0.6) == 1.0
    assert variable.project(1.6) == 1.0
    with pytest.raises(ValidationError, match="no feasible integer"):
        Variable("bad", 0.1, 0.9, integer=True)


def test_duplicate_variable_names_are_rejected() -> None:
    variables = [Variable("x", 0, 1), Variable("x", 1, 2)]
    with pytest.raises(ValidationError, match="unique"):
        latin_hypercube(variables, 2)


def test_nearest_neighbor_uses_normalized_scales() -> None:
    points = [
        {"small": 0.0, "large": 0.0},
        {"small": 1.0, "large": 1.0},
        {"small": 0.0, "large": 50.0},
    ]
    assert nearest_neighbor_order(points)[:2] == [0, 2]


def test_continuation_parameter_validation() -> None:
    def evaluate(point: dict[str, float]) -> tuple[dict[str, float], bool]:
        return point, True

    with pytest.raises(ValidationError, match="growth"):
        adaptive_continuation({"x": 0}, {"x": 1}, evaluate, growth=1)
    with pytest.raises(ValidationError, match="shrink"):
        adaptive_continuation({"x": 0}, {"x": 1}, evaluate, shrink=1)
    with pytest.raises(ValidationError, match="max_attempts"):
        adaptive_continuation({"x": 0}, {"x": 1}, evaluate, max_attempts=0)
    with pytest.raises(ValidationError, match="finite"):
        adaptive_continuation({"x": math.nan}, {"x": 1}, evaluate)


def test_nonfinite_semantic_write_is_rejected(tmp_path: Path) -> None:
    case = tmp_path / "case.json"
    case.write_text("{}", encoding="utf-8")
    manager = SessionManager(allowed_roots=[tmp_path], default_timeout_s=10)
    session = manager.open_session(case, backend="mock")
    with pytest.raises(WorkerError, match="finite"):
        manager.set_values(
            session.session_id,
            [
                ValueWrite(
                    key="stream.input.temperature",
                    identifiers={"stream": "FEED"},
                    value=math.nan,
                    unit="C",
                )
            ],
        )
    manager.close_all()


def test_optimizer_rejects_duplicate_variable_names() -> None:
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


def test_pool_becomes_broken_after_timeout(tmp_path: Path) -> None:
    case = tmp_path / "case.json"
    case.write_text("{}", encoding="utf-8")
    pool = CasePool(
        backend="mock",
        case_path=case,
        workers=1,
        timeout_s=0.05,
        backend_options={"run_delay_s": 0.3},
    )
    point = [
        ValueWrite(
            key="block.input.temperature",
            identifiers={"block": "R-101"},
            value=420,
            unit="C",
        )
    ]
    output = [
        ValueRead(
            key="block.output.conversion",
            identifiers={"block": "R-101"},
            unit="fraction",
        )
    ]
    with pytest.raises(WorkerTimeout):
        pool.evaluate_many([point], output)
    with pytest.raises(WorkerError, match="broken"):
        pool.evaluate_many([point], output)
    pool.close()
