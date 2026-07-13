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
from .hashing import sha256_file


def _within_tolerance(
    reference: Any, candidate: Any, abs_tol: float, rel_tol: float
) -> tuple[bool, float, float]:
    if isinstance(reference, bool | str) or isinstance(candidate, bool | str):
        passed = reference == candidate
        return passed, 0.0 if passed else float("inf"), 0.0 if passed else float("inf")
    ref = float(reference)
    value = float(candidate)
    if not math.isfinite(ref) or not math.isfinite(value):
        return False, float("inf"), float("inf")
    absolute = abs(value - ref)
    scale = max(abs(ref), abs(value), 1.0)
    relative = absolute / scale
    return absolute <= abs_tol or relative <= rel_tol, absolute, relative


def certify_batch_document(
    data: dict[str, Any],
    settings: Settings,
    *,
    repeats: int = 3,
    abs_tol: float = 1e-8,
    rel_tol: float = 1e-6,
) -> dict[str, Any]:
    """Repeat from independent model copies and compare all declared outputs.

    This detects orchestration nondeterminism, hidden warm-start dependence, stale cache
    identity and
    simulator instability. It does not prove model validity; that requires domain-specific balances,
    specifications and an approved qualification case.
    """

    if repeats < 2:
        raise ValueError("Certification requires at least two independent repeats")
    if abs_tol < 0 or rel_tol < 0:
        raise ValueError("Certification tolerances cannot be negative")
    runs: list[list[dict[str, Any]]] = []
    temp_roots: list[Path] = []
    try:
        for repeat_index in range(repeats):
            state_dir = Path(tempfile.mkdtemp(prefix=f"aspenops-cert-{repeat_index}-"))
            temp_roots.append(state_dir)
            isolated = replace(
                settings,
                state_dir=state_dir,
                max_workers=1,
                license_slots=1,
                cache_failures=False,
            )
            request = dict(data)
            request["workers"] = 1
            request["reset_mode"] = "reinitialize"
            runs.append(run_batch_document(request, isolated))
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
                if bool(baseline.get("ok")) != bool(candidate.get("ok")):
                    deterministic = False
                    comparisons.append(
                        {
                            "repeat": repeat_index,
                            "point": point_index,
                            "key": "__ok__",
                            "passed": False,
                            "reference": baseline.get("ok"),
                            "candidate": candidate.get("ok"),
                        }
                    )
                keys = sorted(set(baseline["values"]) | set(candidate["values"]))
                for key in keys:
                    if key not in baseline["values"] or key not in candidate["values"]:
                        passed, absolute, relative = False, float("inf"), float("inf")
                    else:
                        passed, absolute, relative = _within_tolerance(
                            baseline["values"][key],
                            candidate["values"][key],
                            abs_tol,
                            rel_tol,
                        )
                    deterministic = deterministic and passed
                    max_absolute_error = max(max_absolute_error, absolute)
                    max_relative_error = max(max_relative_error, relative)
                    comparisons.append(
                        {
                            "repeat": repeat_index,
                            "point": point_index,
                            "key": key,
                            "passed": passed,
                            "absolute_error": absolute,
                            "relative_error": relative,
                        }
                    )

    all_successful = all(result["ok"] for run in runs for result in run)
    model_path = Path(str(data["model_path"])).expanduser().resolve()
    registry_path = Path(str(data["registry_path"])).expanduser().resolve()
    backend = str(data.get("backend", settings.backend))
    return {
        "schema": "aspenops.certification/v1",
        "runtime_version": __version__,
        "generated_at": datetime.now(UTC).isoformat(),
        "backend": backend,
        "model_path": str(model_path),
        "model_sha256": sha256_file(model_path),
        "registry_path": str(registry_path),
        "registry_sha256": sha256_file(registry_path),
        "repeats": repeats,
        "abs_tol": abs_tol,
        "rel_tol": rel_tol,
        "all_runs_successful": all_successful,
        "deterministic": deterministic,
        "max_absolute_error": max_absolute_error,
        "max_relative_error": max_relative_error,
        "passed": all_successful and deterministic,
        "comparisons": comparisons,
        "runs": runs,
        "qualification_level": (
            "control-plane" if backend == "mock" else "licensed-simulator-runtime"
        ),
        "boundary": (
            "Mock certification proves orchestration determinism only. A real Aspen qualification "
            "requires a licensed Windows host, a non-confidential approved model, case-specific "
            "semantic paths, explicit process constraints and conservation checks."
        ),
    }
