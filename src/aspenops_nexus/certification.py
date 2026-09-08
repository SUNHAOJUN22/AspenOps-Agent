from __future__ import annotations

import math
import shutil
import tempfile
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from . import __version__
from .batch import run_batch_document
from .config import Settings
from .hashing import canonical_hash, sha256_file

CONTROL_PLANE_VERIFIED = "CONTROL_PLANE_VERIFIED"
PENDING_ENGINEERING_ACCEPTANCE = "PENDING_ENGINEERING_ACCEPTANCE"
PENDING_REAL_ASPEN_CERTIFICATION = "PENDING_REAL_ASPEN_CERTIFICATION"


def _finite_nonnegative(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"{label} must be a finite non-negative number")
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise ValueError(f"{label} must be a finite non-negative number")
    return number


def _positive_integer(value: Any, label: str, *, minimum: int = 1, maximum: int = 100) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{label} must be an integer")
    if value < minimum or value > maximum:
        raise ValueError(f"{label} must be between {minimum} and {maximum}")
    return value


def _within_tolerance(
    reference: Any,
    candidate: Any,
    abs_tol: float,
    rel_tol: float,
) -> tuple[bool, float | None, float | None]:
    if isinstance(reference, bool | str) or isinstance(candidate, bool | str):
        passed = type(reference) is type(candidate) and reference == candidate
        return passed, 0.0 if passed else None, 0.0 if passed else None
    if isinstance(reference, bool) or isinstance(candidate, bool):
        return False, None, None
    try:
        ref = float(reference)
        value = float(candidate)
    except (TypeError, ValueError):
        return False, None, None
    if not math.isfinite(ref) or not math.isfinite(value):
        return False, None, None
    absolute = abs(value - ref)
    scale = max(abs(ref), abs(value), 1.0)
    relative = absolute / scale
    return absolute <= abs_tol or relative <= rel_tol, absolute, relative


def _tolerance_for(
    key: str,
    default_abs: float,
    default_rel: float,
    output_tolerances: dict[str, dict[str, float]] | None,
) -> tuple[float, float]:
    if not output_tolerances or key not in output_tolerances:
        return default_abs, default_rel
    policy = output_tolerances[key]
    unknown = sorted(set(policy) - {"abs_tol", "rel_tol"})
    if unknown:
        raise ValueError(f"Unsupported tolerance fields for {key}: {', '.join(unknown)}")
    return (
        _finite_nonnegative(policy.get("abs_tol", default_abs), f"{key} abs_tol"),
        _finite_nonnegative(policy.get("rel_tol", default_rel), f"{key} rel_tol"),
    )


def _compare_mapping(
    *,
    prefix: str,
    reference: dict[str, Any],
    candidate: dict[str, Any],
    repeat_index: int,
    point_index: int,
    default_abs: float,
    default_rel: float,
    output_tolerances: dict[str, dict[str, float]] | None,
) -> tuple[list[dict[str, Any]], bool, float, float]:
    comparisons: list[dict[str, Any]] = []
    deterministic = True
    max_absolute = 0.0
    max_relative = 0.0
    for key in sorted(set(reference) | set(candidate)):
        qualified_key = f"{prefix}{key}"
        abs_tol, rel_tol = _tolerance_for(
            qualified_key, default_abs, default_rel, output_tolerances
        )
        if key not in reference or key not in candidate:
            passed, absolute, relative = False, None, None
        else:
            passed, absolute, relative = _within_tolerance(
                reference[key], candidate[key], abs_tol, rel_tol
            )
        deterministic = deterministic and passed
        if absolute is not None:
            max_absolute = max(max_absolute, absolute)
        if relative is not None:
            max_relative = max(max_relative, relative)
        comparisons.append(
            {
                "repeat": repeat_index,
                "point": point_index,
                "key": qualified_key,
                "passed": passed,
                "absolute_error": absolute,
                "relative_error": relative,
                "abs_tol": abs_tol,
                "rel_tol": rel_tol,
            }
        )
    return comparisons, deterministic, max_absolute, max_relative


def _compare_result(
    *,
    baseline: dict[str, Any],
    candidate: dict[str, Any],
    repeat_index: int,
    point_index: int,
    default_abs: float,
    default_rel: float,
    output_tolerances: dict[str, dict[str, float]] | None,
) -> tuple[list[dict[str, Any]], bool, float, float]:
    comparisons: list[dict[str, Any]] = []
    deterministic = True
    max_absolute = 0.0
    max_relative = 0.0

    exact_fields = (
        "ok",
        "communication_ok",
        "engine_ok",
        "converged",
        "feasible",
        "units",
        "violations",
        "request_hash",
    )
    for field in exact_fields:
        passed = baseline.get(field) == candidate.get(field)
        deterministic = deterministic and passed
        comparisons.append(
            {
                "repeat": repeat_index,
                "point": point_index,
                "key": f"__{field}__",
                "passed": passed,
                "reference": baseline.get(field),
                "candidate": candidate.get(field),
            }
        )

    value_comparisons, values_ok, value_abs, value_rel = _compare_mapping(
        prefix="",
        reference=dict(baseline.get("values", {})),
        candidate=dict(candidate.get("values", {})),
        repeat_index=repeat_index,
        point_index=point_index,
        default_abs=default_abs,
        default_rel=default_rel,
        output_tolerances=output_tolerances,
    )
    comparisons.extend(value_comparisons)
    deterministic = deterministic and values_ok
    max_absolute = max(max_absolute, value_abs)
    max_relative = max(max_relative, value_rel)

    baseline_balances = dict(baseline.get("balance_residuals", {}))
    candidate_balances = dict(candidate.get("balance_residuals", {}))
    for balance_name in sorted(set(baseline_balances) | set(candidate_balances)):
        baseline_detail = baseline_balances.get(balance_name)
        candidate_detail = candidate_balances.get(balance_name)
        if not isinstance(baseline_detail, dict) or not isinstance(candidate_detail, dict):
            deterministic = False
            comparisons.append(
                {
                    "repeat": repeat_index,
                    "point": point_index,
                    "key": f"balance:{balance_name}",
                    "passed": False,
                    "reason": "missing_or_malformed_balance",
                }
            )
            continue
        balance_comparisons, balance_ok, balance_abs, balance_rel = _compare_mapping(
            prefix=f"balance:{balance_name}:",
            reference=baseline_detail,
            candidate=candidate_detail,
            repeat_index=repeat_index,
            point_index=point_index,
            default_abs=default_abs,
            default_rel=default_rel,
            output_tolerances=output_tolerances,
        )
        comparisons.extend(balance_comparisons)
        deterministic = deterministic and balance_ok
        max_absolute = max(max_absolute, balance_abs)
        max_relative = max(max_relative, balance_rel)

    return comparisons, deterministic, max_absolute, max_relative


def certify_batch_document(
    data: dict[str, Any],
    settings: Settings,
    *,
    repeats: int = 3,
    abs_tol: float | None = None,
    rel_tol: float | None = None,
    output_tolerances: dict[str, dict[str, float]] | None = None,
    workers: int = 1,
    engineering_approved: bool = False,
) -> dict[str, Any]:
    """Run independent staged copies and report repeatability without self-certifying.

    Mock runs may use conservative library defaults and can only reach
    ``CONTROL_PLANE_VERIFIED``. Real backends require explicit engineering
    tolerances before any simulator call. Even a passing real repeatability
    gate remains ``PENDING_REAL_ASPEN_CERTIFICATION`` until the external,
    signed and engineer-approved certification procedure is complete.
    """

    repeat_count = _positive_integer(repeats, "repeats", minimum=2, maximum=100)
    worker_count = _positive_integer(workers, "workers", minimum=1, maximum=64)
    backend = str(data.get("backend", settings.backend)).strip().lower()
    if backend not in {"mock", "aspen_plus", "hysys"}:
        raise ValueError(f"Unsupported certification backend: {backend}")

    if backend == "mock":
        effective_abs = 1e-8 if abs_tol is None else _finite_nonnegative(abs_tol, "abs_tol")
        effective_rel = 1e-6 if rel_tol is None else _finite_nonnegative(rel_tol, "rel_tol")
    else:
        if abs_tol is None or rel_tol is None:
            return {
                "schema": "aspenops.certification/v2",
                "runtime_version": __version__,
                "generated_at": datetime.now(UTC).isoformat(),
                "backend": backend,
                "passed": False,
                "repeatability_gate_passed": False,
                "certification_status": PENDING_ENGINEERING_ACCEPTANCE,
                "blockers": [
                    "Real-simulator repeatability requires explicit, "
                    "engineer-approved absolute and relative tolerances."
                ],
                "runs": [],
                "comparisons": [],
                "boundary": (
                    "No real simulator was opened because engineering tolerances were absent. "
                    "This function never grants REAL_ASPEN_CERTIFIED."
                ),
            }
        effective_abs = _finite_nonnegative(abs_tol, "abs_tol")
        effective_rel = _finite_nonnegative(rel_tol, "rel_tol")
        if not engineering_approved:
            return {
                "schema": "aspenops.certification/v2",
                "runtime_version": __version__,
                "generated_at": datetime.now(UTC).isoformat(),
                "backend": backend,
                "passed": False,
                "repeatability_gate_passed": False,
                "certification_status": PENDING_ENGINEERING_ACCEPTANCE,
                "blockers": ["Engineering acceptance has not been explicitly approved."],
                "runs": [],
                "comparisons": [],
                "boundary": (
                    "No real simulator was opened because engineering acceptance was not approved. "
                    "This function never grants REAL_ASPEN_CERTIFIED."
                ),
            }

    if output_tolerances is not None:
        if not isinstance(output_tolerances, dict):
            raise ValueError("output_tolerances must be an object")
        for raw_key, raw_policy in output_tolerances.items():
            if not isinstance(raw_key, str) or not raw_key.strip():
                raise ValueError("output_tolerances keys must be non-empty strings")
            if not isinstance(raw_policy, dict):
                raise ValueError(f"Tolerance policy for {raw_key} must be an object")
            _tolerance_for(raw_key, effective_abs, effective_rel, output_tolerances)

    runs: list[list[dict[str, Any]]] = []
    run_hashes: list[str] = []
    temp_roots: list[Path] = []
    try:
        temporary_parent: Path | None = None
        if backend != "mock":
            temporary_parent = settings.state_dir
            temporary_parent.mkdir(parents=True, exist_ok=True)
        for repeat_index in range(repeat_count):
            state_dir = Path(
                tempfile.mkdtemp(
                    prefix=f"aspenops-cert-{repeat_index}-",
                    dir=temporary_parent,
                )
            )
            temp_roots.append(state_dir)
            isolated = replace(
                settings,
                state_dir=state_dir,
                max_workers=worker_count,
                license_slots=worker_count,
                cache_failures=False,
            )
            request = dict(data)
            request["workers"] = worker_count
            request["reset_mode"] = "reinitialize"
            result = run_batch_document(request, isolated)
            runs.append(result)
            run_hashes.append(canonical_hash(result))
    finally:
        for path in temp_roots:
            shutil.rmtree(path, ignore_errors=True)

    reference = runs[0]
    comparisons: list[dict[str, Any]] = []
    deterministic = True
    max_absolute_error = 0.0
    max_relative_error = 0.0
    if any(len(run) != len(reference) for run in runs):
        deterministic = False
        comparisons.append({"passed": False, "reason": "result_count_mismatch"})
    else:
        for repeat_index, run in enumerate(runs[1:], start=1):
            for point_index, (baseline, candidate) in enumerate(zip(reference, run, strict=True)):
                result_comparisons, result_ok, result_abs, result_rel = _compare_result(
                    baseline=baseline,
                    candidate=candidate,
                    repeat_index=repeat_index,
                    point_index=point_index,
                    default_abs=effective_abs,
                    default_rel=effective_rel,
                    output_tolerances=output_tolerances,
                )
                comparisons.extend(result_comparisons)
                deterministic = deterministic and result_ok
                max_absolute_error = max(max_absolute_error, result_abs)
                max_relative_error = max(max_relative_error, result_rel)

    all_successful = all(bool(result.get("ok")) for run in runs for result in run)
    model_path = Path(str(data["model_path"])).expanduser().resolve()
    registry_path = Path(str(data["registry_path"])).expanduser().resolve()
    repeatability_gate_passed = all_successful and deterministic
    if backend == "mock":
        certification_status = (
            CONTROL_PLANE_VERIFIED
            if repeatability_gate_passed
            else PENDING_REAL_ASPEN_CERTIFICATION
        )
        qualification_level = "portable-control-plane"
    else:
        certification_status = PENDING_REAL_ASPEN_CERTIFICATION
        qualification_level = "licensed-runtime-repeatability"

    return {
        "schema": "aspenops.certification/v2",
        "runtime_version": __version__,
        "generated_at": datetime.now(UTC).isoformat(),
        "backend": backend,
        "model_path": str(model_path),
        "model_sha256": sha256_file(model_path),
        "registry_path": str(registry_path),
        "registry_sha256": sha256_file(registry_path),
        "repeats": repeat_count,
        "workers": worker_count,
        "abs_tol": effective_abs,
        "rel_tol": effective_rel,
        "output_tolerances": output_tolerances or {},
        "engineering_approved": engineering_approved,
        "all_runs_successful": all_successful,
        "deterministic": deterministic,
        "repeatability_gate_passed": repeatability_gate_passed,
        "max_absolute_error": max_absolute_error,
        "max_relative_error": max_relative_error,
        "passed": repeatability_gate_passed,
        "comparisons": comparisons,
        "run_hashes": run_hashes,
        "runs": runs,
        "qualification_level": qualification_level,
        "certification_status": certification_status,
        "boundary": (
            "A passing report proves only the scoped repeatability gate. Mock runs are portable "
            "control-plane evidence. Real runs remain PENDING_REAL_ASPEN_CERTIFICATION until an "
            "approved licensed Windows workflow, engineering acceptance, process-isolation tests, "
            "performance evidence and a trusted Ed25519 certification bundle are independently "
            "reviewed. This function never grants REAL_ASPEN_CERTIFIED."
        ),
    }
