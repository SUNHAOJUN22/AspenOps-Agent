from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

import aspenops_nexus.certification as certification
from aspenops_nexus.certification import (
    CONTROL_PLANE_VERIFIED,
    PENDING_ENGINEERING_ACCEPTANCE,
    PENDING_REAL_ASPEN_CERTIFICATION,
    certify_batch_document,
)
from aspenops_nexus.config import Settings


def minimal_request(tmp_path: Path, *, backend: str = "mock") -> dict[str, Any]:
    model = tmp_path / "model.json"
    registry = tmp_path / "registry.json"
    model.write_text("{}", encoding="utf-8")
    registry.write_text('{"nodes":{"x":{"access":"read","paths":["x"]}}}', encoding="utf-8")
    return {
        "backend": backend,
        "model_path": str(model),
        "registry_path": str(registry),
        "reads": [{"key": "x"}],
        "points": [{}],
    }


def result(value: float, *, ok: bool = True) -> dict[str, Any]:
    return {
        "ok": ok,
        "communication_ok": True,
        "engine_ok": True,
        "converged": True,
        "feasible": True,
        "values": {"x": value},
        "units": {"x": None},
        "violations": [],
        "diagnostics": {},
        "elapsed_s": 0.1,
        "balance_residuals": {"mass": {"residual": 0.0}},
        "cache_source": "computed",
        "cache_hit": False,
        "request_hash": "abc",
        "worker_id": 0,
    }


def test_mock_report_cannot_claim_real_certification(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        certification, "run_batch_document", lambda request, settings: [result(1.0)]
    )

    report = certify_batch_document(
        minimal_request(tmp_path),
        Settings(state_dir=tmp_path),
        repeats=2,
    )

    assert report["schema"] == "aspenops.certification/v2"
    assert report["passed"] is True
    assert report["certification_status"] == CONTROL_PLANE_VERIFIED
    assert report["qualification_level"] == "portable-control-plane"
    assert "REAL_ASPEN_CERTIFIED" in report["boundary"]
    json.dumps(report, allow_nan=False)


@pytest.mark.parametrize(
    ("abs_tol", "rel_tol", "engineering_approved"),
    [(None, None, True), (1e-6, 1e-6, False)],
)
def test_real_backend_is_blocked_before_open_without_approved_tolerances(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    abs_tol: float | None,
    rel_tol: float | None,
    engineering_approved: bool,
) -> None:
    def unexpected_run(request: dict[str, Any], settings: Settings) -> list[dict[str, Any]]:
        raise AssertionError("real simulator must not be opened")

    monkeypatch.setattr(certification, "run_batch_document", unexpected_run)
    report = certify_batch_document(
        minimal_request(tmp_path, backend="aspen_plus"),
        Settings(backend="aspen_plus", state_dir=tmp_path),
        repeats=3,
        abs_tol=abs_tol,
        rel_tol=rel_tol,
        engineering_approved=engineering_approved,
    )

    assert report["passed"] is False
    assert report["certification_status"] == PENDING_ENGINEERING_ACCEPTANCE
    assert report["runs"] == []


@pytest.mark.parametrize("repeats", [True, 1, 101])
def test_repeat_count_is_strictly_bounded(tmp_path: Path, repeats: object) -> None:
    with pytest.raises(ValueError, match="repeats"):
        certify_batch_document(
            minimal_request(tmp_path),
            Settings(state_dir=tmp_path),
            repeats=repeats,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize("value", [True, -1.0, float("nan"), float("inf")])
def test_tolerances_reject_nonfinite_or_boolean_values(tmp_path: Path, value: object) -> None:
    with pytest.raises(ValueError, match="abs_tol"):
        certify_batch_document(
            minimal_request(tmp_path),
            Settings(state_dir=tmp_path),
            repeats=2,
            abs_tol=value,  # type: ignore[arg-type]
        )


def test_missing_output_is_reported_without_nonfinite_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def fake_run(request: dict[str, Any], settings: Settings) -> list[dict[str, Any]]:
        nonlocal calls
        calls += 1
        current = result(1.0)
        if calls == 2:
            current["values"] = {}
        return [current]

    monkeypatch.setattr(certification, "run_batch_document", fake_run)
    report = certify_batch_document(
        minimal_request(tmp_path),
        Settings(state_dir=tmp_path),
        repeats=2,
    )

    assert report["passed"] is False
    missing = [item for item in report["comparisons"] if item.get("key") == "x"]
    assert missing and missing[0]["absolute_error"] is None
    json.dumps(report, allow_nan=False)


def test_per_output_tolerance_overrides_default(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def fake_run(request: dict[str, Any], settings: Settings) -> list[dict[str, Any]]:
        nonlocal calls
        calls += 1
        return [result(1.0 if calls == 1 else 1.05)]

    monkeypatch.setattr(certification, "run_batch_document", fake_run)
    report = certify_batch_document(
        minimal_request(tmp_path),
        Settings(state_dir=tmp_path),
        repeats=2,
        abs_tol=0.0,
        rel_tol=0.0,
        output_tolerances={"x": {"abs_tol": 0.1, "rel_tol": 0.0}},
    )

    assert report["passed"] is True
    comparison = next(item for item in report["comparisons"] if item.get("key") == "x")
    assert comparison["abs_tol"] == 0.1


def test_real_repeatability_pass_remains_pending_certification(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        certification, "run_batch_document", lambda request, settings: [result(1.0)]
    )
    report = certify_batch_document(
        minimal_request(tmp_path, backend="hysys"),
        Settings(backend="hysys", state_dir=tmp_path),
        repeats=3,
        abs_tol=1e-6,
        rel_tol=1e-6,
        engineering_approved=True,
    )

    assert report["passed"] is True
    assert report["repeatability_gate_passed"] is True
    assert report["certification_status"] == PENDING_REAL_ASPEN_CERTIFICATION
    assert report["qualification_level"] == "licensed-runtime-repeatability"
