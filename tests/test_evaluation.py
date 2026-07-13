import math

import pytest

from aspenops.errors import ValidationError
from aspenops.evaluation import Balance, Constraint, build_evaluation, deb_better, safe_evaluate
from aspenops.models import EvaluationResult, RunReport, RunState


def test_safe_expression_and_constraint() -> None:
    values = {"x": 3.0, "y": 4.0}
    assert safe_evaluate("sqrt(x**2 + y**2)", values) == pytest.approx(5)
    assert Constraint("x + y", "<=", 6).violation(values) == pytest.approx(1)
    with pytest.raises(ValidationError):
        safe_evaluate("__import__('os').system('echo bad')", values)
    with pytest.raises(ValidationError):
        safe_evaluate("x.real", values)


def test_balance_and_feasibility_ordering() -> None:
    balance = Balance({"feed": 1, "product": -1}, 0.1, 1e-4)
    absolute, relative, passed = balance.residuals({"feed": 1000, "product": 999.95})
    assert absolute == pytest.approx(0.05)
    assert relative < 1e-4
    assert passed

    run = RunReport(state=RunState.CONVERGED)
    feasible = build_evaluation(
        inputs={"x": 1},
        outputs={"feed": 1000, "product": 1000, "cost": 5},
        run=run,
        objective_expression="cost",
        balances=[balance],
    )
    infeasible = EvaluationResult(
        inputs={},
        outputs={},
        run=run,
        objective=-100,
        constraint_violation=1,
        balance_violation=0,
        feasible=False,
    )
    assert deb_better(feasible, infeasible)

    failed = build_evaluation(inputs={}, outputs={}, run=RunReport(state=RunState.FAILED))
    assert math.isinf(failed.constraint_violation)


def test_expression_operator_and_relation_branches() -> None:
    values = {"x": 5.0, "y": 2.0}
    assert safe_evaluate("+x - y * 2 + x / y + x % y", values) == pytest.approx(4.5)
    assert safe_evaluate("-y", values) == -2
    assert safe_evaluate("min(x, y) + max(x, y) + abs(-y) + log(exp(1))", values) == pytest.approx(
        10
    )
    assert Constraint("x", ">=", 6).violation(values) == 1
    assert Constraint("x", "==", 4, tolerance=0.25).violation(values) == 0.75
    with pytest.raises(ValidationError):
        Constraint("x", "!=", 1).violation(values)
    with pytest.raises(ValidationError):
        safe_evaluate("missing + 1", values)
    with pytest.raises(ValidationError):
        safe_evaluate("round(x)", values)


def test_non_finite_values_are_infeasible() -> None:
    run = RunReport(state=RunState.CONVERGED)
    result = build_evaluation(
        inputs={"x": 1.0},
        outputs={"cost": math.nan},
        run=run,
        objective_expression="cost",
    )
    assert not result.feasible
    assert result.objective is None
    assert math.isinf(result.constraint_violation)
    assert result.metadata["invalid_numeric_fields"] == ["cost"]
    with pytest.raises(ValidationError, match="finite"):
        safe_evaluate("x", {"x": math.inf})
    with pytest.raises(ValidationError, match="finite"):
        Balance({"feed": 1.0}, 1.0, 1.0).residuals({"feed": math.nan})


def test_non_finite_deb_values_are_worst_case() -> None:
    run = RunReport(state=RunState.CONVERGED)
    finite = EvaluationResult(
        inputs={},
        outputs={},
        run=run,
        constraint_violation=1.0,
        balance_violation=0.0,
        feasible=False,
    )
    non_finite = EvaluationResult(
        inputs={},
        outputs={},
        run=run,
        constraint_violation=math.nan,
        balance_violation=0.0,
        feasible=False,
    )
    assert deb_better(finite, non_finite)
