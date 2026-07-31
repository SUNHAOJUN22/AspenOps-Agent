from __future__ import annotations

from dataclasses import asdict
from typing import Any

from aspenops_nexus.models import EvaluationResult


def _result() -> EvaluationResult:
    return EvaluationResult(
        ok=True,
        communication_ok=True,
        engine_ok=True,
        converged=True,
        feasible=True,
        values={
            "product": 0.995,
            "nested": {"series": [1.0, 2.0, 3.0], "flags": {"valid": True}},
        },
        units={"product": "fraction", "nested": None},
        violations=["advisory"],
        diagnostics={
            "worker": {"generation": 4, "history": ["start", "solve", "verify"]},
            "trace": [{"step": 1}, {"step": 2}],
        },
        elapsed_s=0.125,
        balance_residuals={
            "mass": {"absolute": 1e-8, "relative": 2e-8},
            "energy": {"absolute": 3e-8, "relative": 4e-8},
        },
        cache_source="computed",
        cache_hit=False,
        request_hash="a" * 64,
        worker_id=7,
    )


def test_result_snapshot_matches_legacy_asdict_and_roundtrips() -> None:
    result = _result()
    snapshot = result.to_dict()

    assert snapshot == asdict(result)
    assert EvaluationResult.from_dict(snapshot) == result


def test_result_snapshot_is_deeply_isolated() -> None:
    result = _result()
    snapshot: dict[str, Any] = result.to_dict()

    snapshot["values"]["nested"]["series"][0] = 99.0
    snapshot["values"]["nested"]["flags"]["valid"] = False
    snapshot["units"]["product"] = "%"
    snapshot["violations"].append("changed")
    snapshot["diagnostics"]["worker"]["history"][0] = "changed"
    snapshot["diagnostics"]["trace"][0]["step"] = 99
    snapshot["balance_residuals"]["mass"]["absolute"] = 99.0

    assert result.values["nested"]["series"][0] == 1.0
    assert result.values["nested"]["flags"]["valid"] is True
    assert result.units["product"] == "fraction"
    assert result.violations == ["advisory"]
    assert result.diagnostics["worker"]["history"][0] == "start"
    assert result.diagnostics["trace"][0]["step"] == 1
    assert result.balance_residuals["mass"]["absolute"] == 1e-8
