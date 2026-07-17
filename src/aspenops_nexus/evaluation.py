from __future__ import annotations

import math
import time
from typing import Any

from .backends.base import SimulatorBackend, TransactionState, WriteTransactionError
from .models import ConstraintSpec, EvaluationRequest, EvaluationResult
from .registry import NodeRegistry, ResolvedNode
from .units import convert


def _value_key(key: str, identifiers: dict[str, str]) -> str:
    suffix = ",".join(f"{k}={v}" for k, v in sorted(identifiers.items()))
    return key if not suffix else f"{key}:{suffix}"


def _node_identity(node: ResolvedNode) -> str:
    return _value_key(node.key, node.identifiers)


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
        write_items: list[tuple[ResolvedNode, Any]] = []
        for write in request.writes:
            node = registry.resolve(write.key, write.identifiers)
            registry.validate_backend(node, request.backend)
            validated = registry.validate_write(node, write.value, write.unit)
            write_items.append((node, validated))

        read_pairs: list[tuple[Any, ResolvedNode]] = []
        unique_nodes: dict[str, ResolvedNode] = {}
        for read in request.reads:
            node = registry.resolve(read.key, read.identifiers)
            registry.validate_backend(node, request.backend)
            read_pairs.append((read, node))
            unique_nodes.setdefault(_node_identity(node), node)
        resolved_constraints: list[tuple[ConstraintSpec, ResolvedNode]] = []
        for constraint in request.constraints:
            node = registry.resolve(constraint.key, constraint.identifiers)
            registry.validate_backend(node, request.backend)
            resolved_constraints.append((constraint, node))
            unique_nodes.setdefault(_node_identity(node), node)
        resolved_balances: list[tuple[Any, list[tuple[Any, ResolvedNode]]]] = []
        for balance in request.balances:
            terms: list[tuple[Any, ResolvedNode]] = []
            for term in balance.terms:
                node = registry.resolve(term.key, term.identifiers)
                registry.validate_backend(node, request.backend)
                terms.append((term, node))
                unique_nodes.setdefault(_node_identity(node), node)
            resolved_balances.append((balance, terms))
        diagnostics["state_trace"].append("validated")

        if request.reinitialize:
            backend.reinitialize()
            diagnostics["state_trace"].append("reinitialized")
        else:
            diagnostics["state_trace"].append("warm_start")
        backend.bulk_write(write_items)
        diagnostics["state_trace"].append("writes_committed")

        run_info = backend.run()
        communication_ok = True
        engine_ok = bool(run_info.get("engine_returned", False))
        convergence_state = str(run_info.get("convergence_state", "unknown"))
        converged = convergence_state == "converged" and bool(run_info.get("converged", False))
        diagnostics["run"] = run_info
        diagnostics["runtime"] = backend.runtime_identity()
        diagnostics["state_trace"].append("engine_returned")

        ordered_nodes = list(unique_nodes.values())
        raw_by_identity = dict(
            zip(
                (_node_identity(node) for node in ordered_nodes),
                backend.bulk_read(ordered_nodes),
                strict=True,
            )
        )
        declared_read_count = len(read_pairs) + len(resolved_constraints) + sum(
            len(terms) for _, terms in resolved_balances
        )
        diagnostics["io"] = {
            "unique_write_nodes": len(write_items),
            "unique_read_nodes": len(ordered_nodes),
            "avoided_duplicate_reads": max(0, declared_read_count - len(ordered_nodes)),
            "com_reads": len(ordered_nodes),
            "com_writes": len(write_items),
        }

        for read, node in read_pairs:
            output_key = _value_key(read.key, read.identifiers)
            converted = _converted(raw_by_identity[_node_identity(node)], node, read.unit)
            values[output_key] = converted
            units[output_key] = read.unit or node.native_unit
            if read.required and not _finite(converted):
                violations.append(f"non_finite_required_output:{output_key}")
                feasible = False
        diagnostics["state_trace"].append("outputs_read")

        constraint_details: list[dict[str, Any]] = []
        total_constraint_violation = 0.0
        for index, (constraint, node) in enumerate(resolved_constraints):
            actual = float(
                _converted(raw_by_identity[_node_identity(node)], node, constraint.unit)
            )
            violation = _constraint_violation(constraint, actual)
            passed = violation <= 0.0
            name = constraint.name or f"constraint_{index}"
            total_constraint_violation += violation
            constraint_details.append(
                {
                    "name": name,
                    "actual": actual,
                    "operator": constraint.operator,
                    "limit": constraint.value,
                    "tolerance": constraint.tolerance,
                    "violation": violation,
                    "unit": constraint.unit or node.native_unit,
                    "passed": passed,
                }
            )
            if not passed:
                violations.append(f"constraint_failed:{name}")
                feasible = False
        if constraint_details:
            diagnostics["constraints"] = constraint_details
            diagnostics["total_constraint_violation"] = total_constraint_violation

        for balance, terms in resolved_balances:
            signed_terms: list[float] = []
            absolute_terms: list[float] = []
            for term, node in terms:
                converted = float(
                    _converted(raw_by_identity[_node_identity(node)], node, term.unit)
                )
                signed = term.coefficient * converted
                signed_terms.append(signed)
                absolute_terms.append(abs(signed))
            residual = math.fsum(signed_terms) - balance.expected
            scale = max(math.fsum(absolute_terms), balance.floor)
            relative = abs(residual) / scale
            passed = abs(residual) <= balance.abs_tol or relative <= balance.rel_tol
            balance_residuals[balance.name] = {
                "residual": residual,
                "absolute": abs(residual),
                "scale": scale,
                "relative": relative,
                "abs_tol": balance.abs_tol,
                "rel_tol": balance.rel_tol,
                "passed": 1.0 if passed else 0.0,
            }
            if not passed:
                violations.append(f"balance_failed:{balance.name}")
                feasible = False

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
