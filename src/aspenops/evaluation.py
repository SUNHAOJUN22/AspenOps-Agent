"""Safe objective, constraints and conservation residuals."""

from __future__ import annotations

import ast
import math
from collections.abc import Callable
from dataclasses import dataclass

from aspenops.errors import ValidationError
from aspenops.models import EvaluationResult, RunReport, RunState

_ALLOWED_FUNCTIONS: dict[str, Callable[..., float]] = {
    "abs": lambda value: abs(float(value)),
    "min": lambda *values: min(float(value) for value in values),
    "max": lambda *values: max(float(value) for value in values),
    "sqrt": lambda value: math.sqrt(float(value)),
    "log": lambda value: math.log(float(value)),
    "exp": lambda value: math.exp(float(value)),
}


@dataclass(frozen=True)
class Constraint:
    expression: str
    relation: str
    rhs: float
    tolerance: float = 0.0

    def __post_init__(self) -> None:
        if self.relation not in {"<=", ">=", "=="}:
            raise ValidationError(f"Unsupported constraint relation: {self.relation}")
        if not math.isfinite(self.rhs):
            raise ValidationError("Constraint rhs must be finite")
        if not math.isfinite(self.tolerance) or self.tolerance < 0:
            raise ValidationError("Constraint tolerance must be finite and non-negative")

    def violation(self, values: dict[str, float]) -> float:
        lhs = safe_evaluate(self.expression, values)
        if self.relation == "<=":
            result = max(0.0, lhs - self.rhs - self.tolerance)
        elif self.relation == ">=":
            result = max(0.0, self.rhs - lhs - self.tolerance)
        else:
            result = max(0.0, abs(lhs - self.rhs) - self.tolerance)
        if not math.isfinite(result):
            raise ValidationError("Constraint violation is not finite")
        return result


@dataclass(frozen=True)
class Balance:
    terms: dict[str, float]
    absolute_tolerance: float
    relative_tolerance: float
    scale_floor: float = 1e-12

    def __post_init__(self) -> None:
        if not self.terms:
            raise ValidationError("Balance requires at least one term")
        if any(not math.isfinite(value) for value in self.terms.values()):
            raise ValidationError("Balance coefficients must be finite")
        if not math.isfinite(self.absolute_tolerance) or self.absolute_tolerance < 0:
            raise ValidationError("Absolute tolerance must be finite and non-negative")
        if not math.isfinite(self.relative_tolerance) or self.relative_tolerance < 0:
            raise ValidationError("Relative tolerance must be finite and non-negative")
        if not math.isfinite(self.scale_floor) or self.scale_floor <= 0:
            raise ValidationError("Balance scale_floor must be finite and positive")

    def residuals(self, values: dict[str, float]) -> tuple[float, float, bool]:
        selected = {key: float(values[key]) for key in self.terms}
        invalid = [key for key, value in selected.items() if not math.isfinite(value)]
        if invalid:
            raise ValidationError(f"Balance values must be finite: {sorted(invalid)}")
        signed = sum(coefficient * selected[key] for key, coefficient in self.terms.items())
        scale = max(
            sum(abs(coefficient * selected[key]) for key, coefficient in self.terms.items()),
            self.scale_floor,
        )
        absolute = abs(signed)
        relative = absolute / scale
        if not math.isfinite(absolute) or not math.isfinite(relative):
            raise ValidationError("Balance residual is not finite")
        passed = absolute <= self.absolute_tolerance or relative <= self.relative_tolerance
        return absolute, relative, passed


def safe_evaluate(expression: str, values: dict[str, float]) -> float:
    invalid = [key for key, value in values.items() if not math.isfinite(float(value))]
    if invalid:
        raise ValidationError(f"Expression values must be finite: {sorted(invalid)}")
    try:
        tree = ast.parse(expression, mode="eval")
        result = float(_evaluate_node(tree.body, values))
    except (ArithmeticError, OverflowError, SyntaxError, ValueError) as exc:
        raise ValidationError(f"Expression evaluation failed: {exc}") from exc
    if not math.isfinite(result):
        raise ValidationError("Expression result must be finite")
    return result


def build_evaluation(
    *,
    inputs: dict[str, float],
    outputs: dict[str, float],
    run: RunReport,
    objective_expression: str | None = None,
    constraints: list[Constraint] | None = None,
    balances: list[Balance] | None = None,
) -> EvaluationResult:
    merged = {**inputs, **outputs}
    invalid_fields = sorted(
        key for key, value in merged.items() if not math.isfinite(float(value))
    )
    if run.state != RunState.CONVERGED or invalid_fields:
        metadata: dict[str, object] = {}
        if invalid_fields:
            metadata["invalid_numeric_fields"] = invalid_fields
        return EvaluationResult(
            inputs=inputs,
            outputs=outputs,
            run=run,
            objective=None,
            constraint_violation=math.inf,
            balance_violation=math.inf,
            feasible=False,
            metadata=metadata,
        )
    try:
        objective = safe_evaluate(objective_expression, merged) if objective_expression else None
        constraint_violation = sum(
            constraint.violation(merged) ** 2 for constraint in constraints or []
        )
        balance_violation = 0.0
        balances_pass = True
        for balance in balances or []:
            _, relative, passed = balance.residuals(merged)
            balance_violation += relative**2
            balances_pass = balances_pass and passed
    except (KeyError, ValidationError) as exc:
        return EvaluationResult(
            inputs=inputs,
            outputs=outputs,
            run=run,
            objective=None,
            constraint_violation=math.inf,
            balance_violation=math.inf,
            feasible=False,
            metadata={"evaluation_error": str(exc)},
        )
    if not math.isfinite(constraint_violation) or not math.isfinite(balance_violation):
        return EvaluationResult(
            inputs=inputs,
            outputs=outputs,
            run=run,
            objective=None,
            constraint_violation=math.inf,
            balance_violation=math.inf,
            feasible=False,
            metadata={"evaluation_error": "Non-finite violation metric"},
        )
    feasible = constraint_violation == 0.0 and balances_pass
    return EvaluationResult(
        inputs=inputs,
        outputs=outputs,
        run=run,
        objective=objective,
        constraint_violation=constraint_violation,
        balance_violation=balance_violation,
        feasible=feasible,
    )


def deb_better(left: EvaluationResult, right: EvaluationResult) -> bool:
    """Return True when left dominates right under Deb-style feasibility ordering."""
    if left.feasible != right.feasible:
        return left.feasible
    if left.feasible:
        left_objective = _finite_or_inf(left.objective)
        right_objective = _finite_or_inf(right.objective)
        return left_objective < right_objective
    left_violation = _finite_or_inf(left.constraint_violation) + _finite_or_inf(
        left.balance_violation
    )
    right_violation = _finite_or_inf(right.constraint_violation) + _finite_or_inf(
        right.balance_violation
    )
    return left_violation < right_violation


def _finite_or_inf(value: float | None) -> float:
    if value is None:
        return math.inf
    numeric = float(value)
    return numeric if math.isfinite(numeric) else math.inf


def _evaluate_node(node: ast.AST, values: dict[str, float]) -> float:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.Name):
        try:
            return float(values[node.id])
        except KeyError as exc:
            raise ValidationError(f"Unknown expression variable: {node.id}") from exc
    if isinstance(node, ast.BinOp):
        left = _evaluate_node(node.left, values)
        right = _evaluate_node(node.right, values)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            return left / right
        if isinstance(node.op, ast.Pow):
            return float(left**right)
        if isinstance(node.op, ast.Mod):
            return left % right
    if isinstance(node, ast.UnaryOp):
        operand = _evaluate_node(node.operand, values)
        if isinstance(node.op, ast.UAdd):
            return operand
        if isinstance(node.op, ast.USub):
            return -operand
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        function = _ALLOWED_FUNCTIONS.get(node.func.id)
        if function is None:
            raise ValidationError(f"Function not allowed: {node.func.id}")
        if node.keywords:
            raise ValidationError("Keyword arguments are not allowed")
        return function(*[_evaluate_node(argument, values) for argument in node.args])
    raise ValidationError(f"Expression node not allowed: {type(node).__name__}")
