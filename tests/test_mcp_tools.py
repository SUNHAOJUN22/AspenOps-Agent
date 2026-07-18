from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from aspenops_nexus.config import Settings
from aspenops_nexus.mcp_server import AspenOpsTools
from aspenops_nexus.provenance import write_run_bundle
from aspenops_nexus.scheduler import BackgroundScheduler

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "src/aspenops_nexus/data/mock-case.json"
REGISTRY = ROOT / "src/aspenops_nexus/data/node-registry.json"


def batch_document(points: int = 1) -> dict[str, Any]:
    return {
        "backend": "mock",
        "model_path": str(MODEL),
        "registry_path": str(REGISTRY),
        "workers": 1,
        "points": [
            {
                "writes": [
                    {
                        "key": "stream.input.temperature",
                        "identifiers": {"stream": "FEED"},
                        "value": 80.0 + index,
                        "unit": "C",
                    }
                ]
            }
            for index in range(points)
        ],
        "reads": [
            {
                "key": "stream.output.purity",
                "identifiers": {"stream": "PRODUCT"},
                "unit": "fraction",
            }
        ],
        "timeout_s": 10,
    }


def tools(tmp_path: Path) -> tuple[AspenOpsTools, BackgroundScheduler]:
    settings = Settings(
        state_dir=tmp_path,
        backend="mock",
        max_workers=1,
        license_slots=1,
        allowed_roots=(ROOT, tmp_path),
    )
    scheduler = BackgroundScheduler(settings)
    return AspenOpsTools(settings, scheduler), scheduler


def test_tool_facade_reports_system_registry_and_dry_run(tmp_path: Path) -> None:
    facade, scheduler = tools(tmp_path)
    try:
        system = facade.system_info()
        variables = facade.list_semantic_variables(str(REGISTRY))
        dry_run = facade.dry_run_request(batch_document())
    finally:
        scheduler.stop()

    assert system["ready"] is True
    assert system["pool_manager"]["resident_cases"] == 0
    assert variables["sha256"]
    assert any(item["key"] == "stream.output.purity" for item in variables["variables"])
    assert dry_run["ok"] is True
    assert dry_run["evaluations"] == 1


def test_tool_facade_runs_small_sync_batch_and_rejects_large_one(tmp_path: Path) -> None:
    facade, scheduler = tools(tmp_path)
    try:
        result = facade.run_batch_sync(batch_document())
        with pytest.raises(ValueError, match="limited to 16 points"):
            facade.run_batch_sync(batch_document(points=17))
    finally:
        scheduler.stop()

    assert result["validation"]["evaluations"] == 1
    assert result["results"][0]["ok"] is True
    assert result["results"][0]["values"]["stream.output.purity:stream=PRODUCT"] > 0


def test_submission_and_cancellation_tools_delegate_to_scheduler(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    facade, scheduler = tools(tmp_path)
    submitted: list[dict[str, Any]] = []

    def submit(request: dict[str, Any]) -> str:
        submitted.append(request)
        return "job-123"

    monkeypatch.setattr(scheduler, "submit", submit)
    monkeypatch.setattr(scheduler, "cancel", lambda job_id: job_id == "job-123")
    try:
        assert facade.submit_batch({"kind": "batch"}) == {"job_id": "job-123"}
        assert facade.submit_optimization({"optimization": {}}) == {"job_id": "job-123"}
        with pytest.raises(ValueError, match="requires an optimization object"):
            facade.submit_optimization({})
        assert facade.cancel_job("job-123") == {"cancel_requested": True}
        assert facade.cancel_optimization("missing") == {"cancel_requested": False}
    finally:
        scheduler.stop()

    assert submitted == [{"kind": "batch"}, {"optimization": {}}]


def test_status_and_result_tools_cover_missing_pending_and_completed_jobs(tmp_path: Path) -> None:
    facade, scheduler = tools(tmp_path)
    try:
        assert facade.job_status("missing") == {"found": False, "job": None}
        assert facade.optimization_status("missing") == {"found": False, "job": None}
        assert facade.job_result("missing") == {"found": False}
        assert facade.optimization_result("missing") == {"found": False}
        assert facade.list_recent_jobs() == {"jobs": []}

        job_id = scheduler.store.create({"kind": "batch"})
        pending = facade.job_result(job_id)
        assert pending["found"] is True
        assert pending["status"] == "pending"
        assert pending["last_completed_point"] == -1

        claimed = scheduler.store.claim_next("test-owner")
        assert claimed is not None and claimed[0] == job_id
        assert scheduler.store.mark_running(job_id, "test-owner")
        result_payload = [{"best": {"objective": 1.0}}]
        bundle = tmp_path / "job.zip"
        assert scheduler.store.complete(job_id, result_payload, bundle, "token")

        completed = facade.job_result(job_id)
        optimization = facade.optimization_result(job_id)
        recent = facade.list_recent_jobs(limit=1)
    finally:
        scheduler.stop()

    assert completed["status"] == "completed"
    assert completed["results"] == result_payload
    assert optimization["result"] == result_payload[0]
    assert optimization["bundle_path"] == str(bundle)
    assert recent["jobs"][0]["job_id"] == job_id


def test_verify_evidence_bundle_tool_uses_policy_and_integrity_verifier(tmp_path: Path) -> None:
    facade, scheduler = tools(tmp_path)
    request = {
        "backend": "mock",
        "model_path": str(MODEL),
        "registry_path": str(REGISTRY),
    }
    bundle = write_run_bundle(
        request=request,
        results=[{"ok": True, "values": {"x": 1.0}}],
        output_path=tmp_path / "run.zip",
    )
    try:
        result = facade.verify_evidence_bundle(str(bundle))
    finally:
        scheduler.stop()

    assert result["ok"] is True
    assert result["verification_status"] == "unsigned-valid"
