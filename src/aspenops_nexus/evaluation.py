from __future__ import annotations

import math
import time
from pathlib import Path
from typing import Any

from .backends.base import SimulatorBackend, TransactionState, WriteTransactionError
from .evaluation_plan import EvaluationPlan, EvaluationPlanCompiler, node_identity
from .models import ConstraintSpec, EvaluationRequest, EvaluationResult
from .registry import NodeRegistry, ResolvedNode
from .units import convert


def _converted(raw: Any, node: ResolvedNode, unit: str | None) -> Any:
    if isinstance(raw, bool | str):
        return raw
    target_unit = unit or node.native_unit
    return convert(float(raw), node.native_unit, target_unit)


def _finite(value: Any) -> bool:
    if isinstance(value, bool | str):
        return True
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _non_finite_label(value: float) -> str:
    if math.isnan(value):
        return "nan"
    return "positive_infinity" if value > 0 else "negative_infinity"


def _safe_fsum(values: list[float]) -> float:
    try:
        return math.fsum(values)
    except OverflowError:
        return math.inf


def _json_safe(
    value: Any,
    *,
    path: str,
    issues: dict[str, str],
) -> Any:
    if value is None or isinstance(value, bool | str | int):
        return value
    if isinstance(value, float):
        if math.isfinite(value):
            return value
        issues[path] = _non_finite_label(value)
        return None
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {
            str(key): _json_safe(item, path=f"{path}.{key}", issues=issues)
            for key, item in value.items()
        }
    if isinstance(value, list | tuple):
        return [
            _json_safe(item, path=f"{path}[{index}]", issues=issues)
            for index, item in enumerate(value)
        ]
    issues[path] = f"unsupported_type:{type(value).__name__}"
    text = repr(value)
    return text if len(text) <= 512 else f"{text[:512]}...[truncated]"


def _strict_run_flag(run_info: dict[str, Any], name: str) -> bool:
    value = run_info.get(name)
    if not isinstance(value, bool):
        raise TypeError(f"Backend run field {name} must be Boolean")
    return value


def _constraint_violation(spec: ConstraintSpec, actual: float) -> float:
    tolerance = spec.tolerance
    if spec.operator == "<":
        return max(0.0, actual - (spec.value - tolerance))
    if spec.operator == "<=":
        return max(0.0, actual - (spec.value + tolerance))
    if spec.operator == ">":
        return max(0.0, (spec.value + tolerance) - actual)
    if spec.operator == ">=":
        return max(0.0, (spec.value - tolerance) - actual)
    return max(0.0, abs(actual - spec.value) - tolerance)


def evaluate(
    backend: SimulatorBackend,
    registry: NodeRegistry,
    request: EvaluationRequest,
    *,
    worker_id: int | None = None,
    plan: EvaluationPlan | None = None,
) -> EvaluationResult:
    started = time.perf_counter()
    violations: list[str] = []
    diagnostics: dict[str, Any] = {"state_trace": ["received"]}
    balance_residuals: dict[str, dict[str, float]] = {}
    communication_ok = False
    engine_ok = False
    converged = False
    feasible = True
    values: dict[str, Any] = {}
    units: dict[str, str | None] = {}
    try:
        active_plan = plan or EvaluationPlanCompiler.compile(registry, request)
        diagnostics["state_trace"].append("plan_compiled")
        diagnostics["io"] = {
            "declared_writes": active_plan.estimated_io.declared_writes,
            "unique_write_nodes": active_plan.estimated_io.unique_write_nodes,
            "declared_reads": active_plan.estimated_io.declared_reads,
            "unique_read_nodes": active_plan.estimated_io.unique_read_nodes,
            "avoided_duplicate_reads": active_plan.estimated_io.avoided_duplicate_reads,
            "com_reads": active_plan.estimated_io.unique_read_nodes,
            "com_writes": active_plan.estimated_io.declared_writes,
        }

        if request.reinitialize:
            backend.reinitialize()
            diagnostics["state_trace"].append("reinitialized")
        else:
            diagnostics["state_trace"].append("warm_start")
        backend.bulk_write(
            [(compiled.node, compiled.native_value) for compiled in active_plan.writes]
        )
        diagnostics["state_trace"].append("writes_committed")

        raw_run_info = backend.run()
        communication_ok = True
        if not isinstance(raw_run_info, dict):
            raise TypeError("Backend run result must be an object")
        engine_ok = _strict_run_flag(raw_run_info, "engine_returned")
        converged_flag = _strict_run_flag(raw_run_info, "converged")
        convergence_state_raw = raw_run_info.get("convergence_state")
        if not isinstance(convergence_state_raw, str) or not convergence_state_raw:
            raise TypeError("Backend run field convergence_state must be a non-empty string")
        convergence_state = convergence_state_raw
        converged = convergence_state == "converged" and converged_flag

        raw_runtime = backend.runtime_identity()
        if not isinstance(raw_runtime, dict):
            raise TypeError("Backend runtime identity must be an object")
        diagnostic_issues: dict[str, str] = {}
        diagnostics["run"] = _json_safe(raw_run_info, path="run", issues=diagnostic_issues)
        diagnostics["runtime"] = _json_safe(
            raw_runtime,
            path="runtime",
            issues=diagnostic_issues,
        )
        if diagnostic_issues:
            diagnostics["backend_diagnostic_sanitization"] = diagnostic_issues
            violations.append("backend_diagnostics_not_json_safe")
            feasible = False
        diagnostics["state_trace"].append("engine_returned")

        raw_by_identity = dict(
            zip(
                (node_identity(node) for node in active_plan.unique_reads),
                backend.bulk_read(list(active_plan.unique_reads)),
                strict=True,
            )
        )

        non_finite_outputs: dict[str, str] = {}
        for binding in active_plan.output_bindings:
            converted = _converted(
                raw_by_identity[binding.identity], binding.node, binding.spec.unit
            )
            units[binding.output_key] = binding.spec.unit or binding.node.native_unit
            if not _finite(converted):
                numeric = float(converted)
                values[binding.output_key] = None
                non_finite_outputs[binding.output_key] = _non_finite_label(numeric)
                if binding.spec.required:
                    violations.append(f"non_finite_required_output:{binding.output_key}")
                    feasible = False
                continue
            values[binding.output_key] = converted
        if non_finite_outputs:
            diagnostics["non_finite_outputs"] = non_finite_outputs
        diagnostics["state_trace"].append("outputs_read")

        constraint_details: list[dict[str, Any]] = []
        total_constraint_violation = 0.0
        constraint_violation_finite = True
        for index, compiled_constraint in enumerate(active_plan.constraints):
            name = compiled_constraint.spec.name or f"constraint_{index}"
            converted = _converted(
                raw_by_identity[compiled_constraint.identity],
                compiled_constraint.node,
                compiled_constraint.spec.unit,
            )
            try:
                actual = float(converted)
            except (TypeError, ValueError):
                constraint_violation_finite = False
                constraint_details.append(
                    {
                        "name": name,
                        "actual": None,
                        "operator": compiled_constraint.spec.operator,
                        "limit": compiled_constraint.spec.value,
                        "tolerance": compiled_constraint.spec.tolerance,
                        "violation": None,
                        "unit": (
                            compiled_constraint.spec.unit
                            or compiled_constraint.node.native_unit
                        ),
                        "passed": False,
                        "failure": "non_numeric",
                        "observed_type": type(converted).__name__,
                    }
                )
                violations.append(f"constraint_non_numeric:{name}")
                violations.append(f"constraint_failed:{name}")
                feasible = False
                continue
            if not math.isfinite(actual):
                constraint_violation_finite = False
                constraint_details.append(
                    {
                        "name": name,
                        "actual": None,
                        "operator": compiled_constraint.spec.operator,
                        "limit": compiled_constraint.spec.value,
                        "tolerance": compiled_constraint.spec.tolerance,
                        "violation": None,
                        "unit": (
                            compiled_constraint.spec.unit
                            or compiled_constraint.node.native_unit
                        ),
                        "passed": False,
                        "failure": "non_finite",
                        "non_finite_value": _non_finite_label(actual),
                    }
                )
                violations.append(f"constraint_non_finite:{name}")
                violations.append(f"constraint_failed:{name}")
                feasible = False
                continue
            violation = _constraint_violation(compiled_constraint.spec, actual)
            if not math.isfinite(violation):
                constraint_violation_finite = False
                constraint_details.append(
                    {
                        "name": name,
                        "actual": actual,
                        "operator": compiled_constraint.spec.operator,
                        "limit": compiled_constraint.spec.value,
                        "tolerance": compiled_constraint.spec.tolerance,
                        "violation": None,
                        "unit": (
                            compiled_constraint.spec.unit
                            or compiled_constraint.node.native_unit
                        ),
                        "passed": False,
                        "failure": "derived_overflow",
                    }
                )
                violations.append(f"constraint_non_finite:{name}")
                violations.append(f"constraint_failed:{name}")
                feasible = False
                continue
            passed = violation <= 0.0
            total_constraint_violation += violation
            constraint_details.append(
                {
                    "name": name,
                    "actual": actual,
                    "operator": compiled_constraint.spec.operator,
                    "limit": compiled_constraint.spec.value,
                    "tolerance": compiled_constraint.spec.tolerance,
                    "violation": violation,
                    "unit": (
                        compiled_constraint.spec.unit or compiled_constraint.node.native_unit
                    ),
                    "passed": passed,
                }
            )
            if not passed:
                violations.append(f"constraint_failed:{name}")
                feasible = False
        if constraint_details:
            diagnostics["constraints"] = constraint_details
            diagnostics["total_constraint_violation"] = (
                total_constraint_violation if constraint_violation_finite else None
            )
            diagnostics["finite_constraint_violation_sum"] = total_constraint_violation

        non_finite_balances: dict[str, list[dict[str, str]]] = {}
        for compiled_balance in active_plan.balances:
            name = compiled_balance.spec.name
            signed_terms: list[float] = []
            absolute_terms: list[float] = []
            invalid_terms: list[dict[str, str]] = []
            for compiled_term in compiled_balance.terms:
                converted = _converted(
                    raw_by_identity[compiled_term.identity],
                    compiled_term.node,
                    compiled_term.spec.unit,
                )
                try:
                    numeric = float(converted)
                except (TypeError, ValueError):
                    invalid_terms.append(
                        {
                            "identity": compiled_term.identity,
                            "value": f"non_numeric:{type(converted).__name__}",
                        }
                    )
                    continue
                if not math.isfinite(numeric):
                    invalid_terms.append(
                        {
                            "identity": compiled_term.identity,
                            "value": _non_finite_label(numeric),
                        }
                    )
                    continue
                signed = compiled_term.spec.coefficient * numeric
                if not math.isfinite(signed):
                    invalid_terms.append(
                        {
                            "identity": compiled_term.identity,
                            "value": "derived_overflow",
                        }
                    )
                    continue
                signed_terms.append(signed)
                absolute_terms.append(abs(signed))
            if invalid_terms:
                scale = max(_safe_fsum(absolute_terms), compiled_balance.spec.floor)
                balance_residuals[name] = {
                    "residual": 0.0,
                    "absolute": 0.0,
                    "scale": scale if math.isfinite(scale) else 0.0,
                    "relative": 0.0,
                    "abs_tol": compiled_balance.spec.abs_tol,
                    "rel_tol": compiled_balance.spec.rel_tol,
                    "passed": 0.0,
                }
                non_finite_balances[name] = invalid_terms
                violations.append(f"balance_non_finite:{name}")
                violations.append(f"balance_failed:{name}")
                feasible = False
                continue
            signed_sum = _safe_fsum(signed_terms)
            absolute_sum = _safe_fsum(absolute_terms)
            residual = signed_sum - compiled_balance.spec.expected
            scale = max(absolute_sum, compiled_balance.spec.floor)
            relative = abs(residual) / scale if scale > 0 else math.inf
            if not all(math.isfinite(item) for item in (residual, scale, relative)):
                balance_residuals[name] = {
                    "residual": 0.0,
                    "absolute": 0.0,
                    "scale": 0.0,
                    "relative": 0.0,
                    "abs_tol": compiled_balance.spec.abs_tol,
                    "rel_tol": compiled_balance.spec.rel_tol,
                    "passed": 0.0,
                }
                non_finite_balances[name] = [
                    {"identity": "derived_balance", "value": "derived_overflow"}
                ]
                violations.append(f"balance_non_finite:{name}")
                violations.append(f"balance_failed:{name}")
                feasible = False
                continue
            passed = (
                abs(residual) <= compiled_balance.spec.abs_tol
                or relative <= compiled_balance.spec.rel_tol
            )
            balance_residuals[name] = {
                "residual": residual,
                "absolute": abs(residual),
                "scale": scale,
                "relative": relative,
                "abs_tol": compiled_balance.spec.abs_tol,
                "rel_tol": compiled_balance.spec.rel_tol,
                "passed": 1.0 if passed else 0.0,
            }
            if not passed:
                violations.append(f"balance_failed:{name}")
                feasible = False
        if non_finite_balances:
            diagnostics["non_finite_balances"] = non_finite_balances

        if not engine_ok:
            violations.append("engine_did_not_return")
            feasible = False
        if not converged:
            violations.append(f"simulator_not_converged:{convergence_state}")
            feasible = False
        diagnostics["state_trace"].append("verified")
    except WriteTransactionError as exc:
        diagnostics["exception_type"] = type(exc).__name__
        diagnostics["exception"] = str(exc)
        diagnostics["transaction_state"] = exc.state.value
        diagnostics["worker_tainted"] = exc.state is TransactionState.TAINTED
        diagnostics["state_trace"].append("failed")
        violations.append(f"write_transaction:{exc.state.value}")
        feasible = False
    except Exception as exc:
        diagnostics["exception_type"] = type(exc).__name__
        diagnostics["exception"] = str(exc)
        diagnostics["state_trace"].append("failed")
        violations.append(f"execution_error:{type(exc).__name__}")
        feasible = False
    elapsed = time.perf_counter() - started
    ok = communication_ok and engine_ok and converged and feasible
    return EvaluationResult(
        ok=ok,
        communication_ok=communication_ok,
        engine_ok=engine_ok,
        converged=converged,
        feasible=feasible,
        values=values,
        units=units,
        violations=violations,
        diagnostics=diagnostics,
        elapsed_s=elapsed,
        balance_residuals=balance_residuals,
        worker_id=worker_id,
    )
