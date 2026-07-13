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

    def violation(self, values: dict[str, float]) -> float:
        _require_finite("constraint rhs", self.rhs)
        _require_finite("constraint tolerance", self.tolerance)
        if self.tolerance < 0:
            raise ValidationError("Constraint tolerance must be non-negative")
        lhs = safe_evaluate(self.expression, values)
        if self.relation == "<=":
            return max(0.0, lhs - self.rhs - self.tolerance)
        if self.relation == ">=":
            return max(0.0, self.rhs - lhs - self.tolerance)
        if self.relation == "==":
            return max(0.0, abs(lhs - self.rhs) - self.tolerance)
        raise ValidationError(f"Unsupported constraint relation: {self.relation}")


@dataclass(frozen=True)
class Balance:
    terms: dict[str, float]
    absolute_tolerance: float
    relative_tolerance: float
    scale_floor: float = 1e-12

    def residuals(self, values: dict[str, float]) -> tuple[float, float, bool]:
        if not self.terms:
            raise ValidationError("Balance requires at least one term")
        for name, coefficient in self.terms.items():
            _require_finite(f"balance coefficient {name}", coefficient)
            try:
                value = values[name]
            except KeyError as exc:
                raise ValidationError(f"Unknown balance variable: {name}") from exc
            _require_finite(f"balance value {name}", value)
        for label, value in (
            ("absolute tolerance", self.absolute_tolerance),
            ("relative tolerance", self.relative_tolerance),
            ("scale floor", self.scale_floor),
        ):
            _require_finite(f"balance {label}", value)
        if self.absolute_tolerance < 0 or self.relative_tolerance < 0:
            raise ValidationError("Balance tolerances must be non-negative")
        if self.scale_floor <= 0:
            raise ValidationError("Balance scale_floor must be positive")

        signed = sum(coefficient * values[key] for key, coefficient in self.terms.items())
        scale = max(
            sum(abs(coefficient * values[key]) for key, coefficient in self.terms.items()),
            self.scale_floor,
        )
        absolute = abs(signed)
        relative = absolute / scale
        _require_finite("balance absolute residual", absolute)
        _require_finite("balance relative residual", relative)
        passed = absolute <= self.absolute_tolerance or relative <= self.relative_tolerance
        return absolute, relative, passed


def safe_evaluate(expression: str, values: dict[str, float]) -> float:
    _validate_finite_mapping(values)
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise ValidationError(f"Invalid expression syntax: {exc.msg}") from exc
    try:
        result = float(_evaluate_node(tree.body, values))
    except (ArithmeticError, TypeError, ValueError) as exc:
        raise ValidationError(f"Expression evaluation failed: {exc}") from exc
    _require_finite("expression result", result)
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
    if run.state != RunState.CONVERGED:
        return EvaluationResult(
            inputs=inputs,
            outputs=outputs,
            run=run,
            objective=None,
            constraint_violation=math.inf,
            balance_violation=math.inf,
            feasible=False,
        )

    merged = {**inputs, **outputs}
    try:
        _validate_finite_mapping(merged)
        objective = safe_evaluate(objective_expression, merged) if objective_expression else None
        constraint_violation = sum(
            constraint.violation(merged) ** 2 for constraint in constraints or []
        )
        _require_finite("constraint violation", constraint_violation)
        balance_violation = 0.0
        balances_pass = True
        for balance in balances or []:
            _, relative, passed = balance.residuals(merged)
            balance_violation += relative**2
            balances_pass = balances_pass and passed
        _require_finite("balance violation", balance_violation)
    except ValidationError as exc:
        return EvaluationResult(
            inputs=inputs,
            outputs=outputs,
            run=run,
            objective=None,
            constraint_violation=math.inf,
            balance_violation=math.inf,
            feasible=False,
            metadata={"validation_error": str(exc)},
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
    left_feasible = left.feasible and _violations_are_finite(left)
    right_feasible = right.feasible and _violations_are_finite(right)
    if left_feasible != right_feasible:
        return left_feasible
    if left_feasible:
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


def _validate_finite_mapping(values: dict[str, float]) -> None:
    for key, value in values.items():
        _require_finite(f"value {key}", value)


def _require_finite(label: str, value: float) -> None:
    try:
        finite = math.isfinite(float(value))
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{label} must be numeric") from exc
    if not finite:
        raise ValidationError(f"{label} must be finite")


def _finite_or_inf(value: float | None) -> float:
    if value is None:
        return math.inf
    return float(value) if math.isfinite(float(value)) else math.inf


def _violations_are_finite(result: EvaluationResult) -> bool:
    return math.isfinite(float(result.constraint_violation)) and math.isfinite(
        float(result.balance_violation)
    )
