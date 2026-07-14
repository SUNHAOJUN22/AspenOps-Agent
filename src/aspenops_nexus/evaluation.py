from __future__ import annotations

import math
import time
from typing import Any

from .backends.base import SimulatorBackend
from .models import ConstraintSpec, EvaluationRequest, EvaluationResult
from .registry import NodeRegistry, ResolvedNode
from .units import convert, dimension


def _value_key(key: str, identifiers: dict[str, str]) -> str:
    suffix = ",".join(f"{k}={v}" for k, v in sorted(identifiers.items()))
    return key if not suffix else f"{key}:{suffix}"


def _converted(raw: Any, node: ResolvedNode, unit: str | None) -> Any:
    if isinstance(raw, (bool, str)):
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


def _required_bool(run_info: dict[str, Any], key: str, default: bool) -> bool:
    raw = run_info.get(key, default)
    if not isinstance(raw, bool):
        raise TypeError(f"Backend run status {key!r} must be Boolean, got {type(raw).__name__}")
    return raw


def _constraint_assessment(spec: ConstraintSpec, actual: float) -> tuple[float, bool]:
    if not math.isfinite(actual):
        return math.inf, False
    if spec.operator == "<":
        required_margin = spec.tolerance or math.ulp(max(abs(actual), abs(spec.value), 1.0))
        violation = max(0.0, required_margin - (spec.value - actual))
        return violation, violation <= 0.0
    if spec.operator == "<=":
        violation = max(0.0, actual - spec.value - spec.tolerance)
        return violation, violation <= 0.0
    if spec.operator == ">":
        required_margin = spec.tolerance or math.ulp(max(abs(actual), abs(spec.value), 1.0))
        violation = max(0.0, required_margin - (actual - spec.value))
        return violation, violation <= 0.0
    if spec.operator == ">=":
        violation = max(0.0, spec.value - actual - spec.tolerance)
        return violation, violation <= 0.0
    violation = max(0.0, abs(actual - spec.value) - spec.tolerance)
    return violation, violation <= 0.0


def _constraint_scale(spec: ConstraintSpec) -> tuple[float, str]:
    if spec.scale is not None:
        return spec.scale, "explicit"
    return max(abs(spec.value), spec.tolerance, 1.0), "derived_from_limit"


def evaluate(
    backend: SimulatorBackend,
    registry: NodeRegistry,
    request: EvaluationRequest,
    *,
    worker_id: int | None = None,
) -> EvaluationResult:
    """Execute one deterministic evaluation transaction.

    State transition:
        validate -> reset -> atomic writes -> solve -> required reads -> constraints -> balances

    The result intentionally separates transport, engine return, numerical convergence and physical
    feasibility. A Python function returning without exception is never treated as proof of a valid
    process solution.
    """

    started = time.perf_counter()
    violations: list[str] = []
    diagnostics: dict[str, Any] = {"state_trace": ["received"]}
    balance_residuals: dict[str, dict[str, float | str]] = {}
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
        for read in request.reads:
            node = registry.resolve(read.key, read.identifiers)
            registry.validate_backend(node, request.backend)
            read_pairs.append((read, node))
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
        engine_ok = _required_bool(run_info, "engine_returned", True)
        converged = _required_bool(run_info, "converged", False)
        diagnostics["run"] = run_info
        diagnostics["runtime"] = backend.runtime_identity()
        diagnostics["state_trace"].append("engine_returned")

        raw_values = backend.bulk_read([node for _, node in read_pairs])
        for (read, node), raw in zip(read_pairs, raw_values, strict=True):
            output_key = _value_key(read.key, read.identifiers)
            converted = _converted(raw, node, read.unit)
            values[output_key] = converted
            units[output_key] = read.unit or node.native_unit
            if read.required and not _finite(converted):
                violations.append(f"non_finite_required_output:{output_key}")
                feasible = False
        diagnostics["state_trace"].append("outputs_read")

        constraint_details: list[dict[str, Any]] = []
        normalized_violations: list[float] = []
        for index, constraint in enumerate(request.constraints):
            node = registry.resolve(constraint.key, constraint.identifiers)
            registry.validate_backend(node, request.backend)
            actual_raw = backend.read(node)
            actual = float(_converted(actual_raw, node, constraint.unit))
            violation, passed = _constraint_assessment(constraint, actual)
            scale, scale_source = _constraint_scale(constraint)
            normalized_violation = constraint.weight * violation / scale
            normalized_violations.append(normalized_violation)
            name = constraint.name or f"constraint_{index}"
            constraint_details.append(
                {
                    "name": name,
                    "actual": actual,
                    "operator": constraint.operator,
                    "limit": constraint.value,
                    "tolerance": constraint.tolerance,
                    "violation": violation,
                    "normalization_scale": scale,
                    "scale_source": scale_source,
                    "weight": constraint.weight,
                    "normalized_violation": normalized_violation,
                    "unit": constraint.unit or node.native_unit,
                    "passed": passed,
                }
            )
            if not passed:
                violations.append(f"constraint_failed:{name}")
                feasible = False
        if constraint_details:
            diagnostics["constraints"] = constraint_details
            diagnostics["total_normalized_constraint_violation"] = math.fsum(
                normalized_violations
            )

        for balance in request.balances:
            resolved_terms = [
                (term, registry.resolve(term.key, term.identifiers)) for term in balance.terms
            ]
            first_term, first_node = resolved_terms[0]
            canonical_unit = balance.unit or first_term.unit or first_node.native_unit
            if canonical_unit is not None:
                canonical_dimension = dimension(canonical_unit)
                for term, _node in resolved_terms:
                    if term.unit is not None and dimension(term.unit) != canonical_dimension:
                        raise ValueError(
                            f"Balance {balance.name!r} mixes incompatible units: "
                            f"{term.unit!r} and {canonical_unit!r}"
                        )
            signed_terms: list[float] = []
            absolute_terms: list[float] = []
            for term, node in resolved_terms:
                registry.validate_backend(node, request.backend)
                raw = backend.read(node)
                converted = float(_converted(raw, node, canonical_unit))
                if not math.isfinite(converted):
                    raise ValueError(
                        f"Balance {balance.name!r} received a non-finite term from {term.key!r}"
                    )
                signed = term.coefficient * converted
                signed_terms.append(signed)
                absolute_terms.append(abs(signed))
            residual = math.fsum(signed_terms) - balance.expected
            absolute = abs(residual)
            sum_absolute_terms = math.fsum(absolute_terms)
            relative_denominator = max(sum_absolute_terms, balance.floor)
            relative = absolute / relative_denominator
            tolerance_scale = max(
                sum_absolute_terms,
                abs(balance.expected),
                balance.floor,
            )
            threshold = balance.abs_tol + balance.rel_tol * tolerance_scale
            passed = absolute <= threshold
            balance_residuals[balance.name] = {
                "residual": residual,
                "absolute": absolute,
                "sum_absolute_terms": sum_absolute_terms,
                "relative_denominator": relative_denominator,
                "relative": relative,
                "expected": balance.expected,
                "tolerance_scale": tolerance_scale,
                "threshold": threshold,
                "abs_tol": balance.abs_tol,
                "rel_tol": balance.rel_tol,
                "unit": canonical_unit or "",
                "passed": 1.0 if passed else 0.0,
            }
            if not passed:
                violations.append(f"balance_failed:{balance.name}")
                feasible = False

        if not engine_ok:
            violations.append("engine_did_not_return")
            feasible = False
        if not converged:
            violations.append("simulator_not_converged")
            feasible = False
        diagnostics["state_trace"].append("verified")
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
