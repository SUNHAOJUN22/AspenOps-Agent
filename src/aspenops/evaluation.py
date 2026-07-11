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
        signed = sum(coefficient * values[key] for key, coefficient in self.terms.items())
        scale = max(
            sum(abs(coefficient * values[key]) for key, coefficient in self.terms.items()),
            self.scale_floor,
        )
        absolute = abs(signed)
        relative = absolute / scale
        passed = absolute <= self.absolute_tolerance or relative <= self.relative_tolerance
        return absolute, relative, passed


def safe_evaluate(expression: str, values: dict[str, float]) -> float:
    tree = ast.parse(expression, mode="eval")
    return float(_evaluate_node(tree.body, values))


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
        left_objective = math.inf if left.objective is None else left.objective
        right_objective = math.inf if right.objective is None else right.objective
        return left_objective < right_objective
    left_violation = left.constraint_violation + left.balance_violation
    right_violation = right.constraint_violation + right.balance_violation
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
