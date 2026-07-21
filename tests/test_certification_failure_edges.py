from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import pytest

from aspenops_nexus import certification
from aspenops_nexus.config import Settings


def _inputs(tmp_path: Path) -> tuple[dict[str, Any], Settings]:
    model = tmp_path / "model.json"
    registry = tmp_path / "registry.json"
    model.write_text("{}", encoding="utf-8")
    registry.write_text("{}", encoding="utf-8")
    return (
        {
            "backend": "mock",
            "model_path": str(model),
            "registry_path": str(registry),
        },
        Settings(state_dir=tmp_path / "state"),
    )


def test_tolerance_helpers_reject_non_numeric_and_unknown_policy_fields() -> None:
    assert certification._within_tolerance(object(), object(), 0.0, 0.0) == (
        False,
        None,
        None,
    )
    assert certification._within_tolerance(True, 1, 0.0, 0.0) == (False, None, None)
    assert certification._within_tolerance(math.nan, 1.0, 0.0, 0.0) == (
        False,
        None,
        None,
    )
    with pytest.raises(ValueError, match="Unsupported tolerance fields"):
        certification._tolerance_for(
            "x",
            0.0,
            0.0,
            {"x": {"unknown": 1.0}},
        )


def test_compare_result_marks_malformed_balance_as_structural_failure() -> None:
    comparisons, deterministic, absolute, relative = certification._compare_result(
        baseline={
            "ok": True,
            "values": {},
            "balance_residuals": {"mass": "malformed"},
        },
        candidate={
            "ok": True,
            "values": {},
            "balance_residuals": {"mass": {}},
        },
        repeat_index=1,
        point_index=0,
        default_abs=0.0,
        default_rel=0.0,
        output_tolerances=None,
    )
    assert deterministic is False
    assert absolute == 0.0
    assert relative == 0.0
    assert any(item.get("reason") == "missing_or_malformed_balance" for item in comparisons)


def test_certification_rejects_unsupported_backend_and_tolerance_shapes(
    tmp_path: Path,
) -> None:
    data, settings = _inputs(tmp_path)

    unsupported = dict(data, backend="unknown")
    with pytest.raises(ValueError, match="Unsupported certification backend"):
        certification.certify_batch_document(unsupported, settings, repeats=2)

    with pytest.raises(ValueError, match="output_tolerances must be an object"):
        certification.certify_batch_document(
            data,
            settings,
            repeats=2,
            output_tolerances=[],  # type: ignore[arg-type]
        )

    with pytest.raises(ValueError, match="keys must be non-empty"):
        certification.certify_batch_document(
            data,
            settings,
            repeats=2,
            output_tolerances={"": {}},
        )

    with pytest.raises(ValueError, match="must be an object"):
        certification.certify_batch_document(
            data,
            settings,
            repeats=2,
            output_tolerances={"x": []},  # type: ignore[dict-item]
        )
