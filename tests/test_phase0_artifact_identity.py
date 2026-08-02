from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import pytest

import aspenops_nexus.worker as worker_module
from aspenops_nexus.hashing import sha256_file
from aspenops_nexus.models import EvaluationRequest
from aspenops_nexus.pool import CasePool
from aspenops_nexus.worker import _validate_ready_message, evaluate_on_worker, start_worker, stop_worker

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "src/aspenops_nexus/data/mock-case.json"
REGISTRY = ROOT / "src/aspenops_nexus/data/node-registry.json"


def _request(model: Path, registry: Path) -> EvaluationRequest:
    return EvaluationRequest.from_dict(
        {
            "model_path": str(model),
            "registry_path": str(registry),
            "backend": "mock",
            "writes": [],
            "reads": [],
            "timeout_s": 10.0,
        }
    )


def test_worker_stages_both_artifacts_and_reports_verified_identity(tmp_path: Path) -> None:
    model = tmp_path / "case.json"
    registry = tmp_path / "registry.json"
    shutil.copy2(MODEL, model)
    shutil.copy2(REGISTRY, registry)
    handle = start_worker(
        worker_id=0,
        backend_name="mock",
        model_path=model,
        registry_path=registry,
        visible=False,
        startup_timeout_s=10.0,
        expected_model_sha256=sha256_file(model),
        expected_registry_sha256=sha256_file(registry),
    )
    stage_dir = handle.staged_model.parent
    try:
        assert handle.staged_model.is_file()
        assert handle.staged_registry is not None and handle.staged_registry.is_file()
        assert handle.model_sha256 == sha256_file(model)
        assert handle.registry_sha256 == sha256_file(registry)
        artifacts = handle.runtime["execution_artifacts"]
        assert artifacts["model_sha256"] == handle.model_sha256
        assert artifacts["registry_sha256"] == handle.registry_sha256
        assert Path(artifacts["staged_model_path"]) == handle.staged_model
        assert Path(artifacts["staged_registry_path"]) == handle.staged_registry

        result = evaluate_on_worker(handle, _request(model, registry))
        identity = result.diagnostics["execution_identity"]
        assert identity["model_sha256"] == handle.model_sha256
        assert identity["registry_sha256"] == handle.registry_sha256
    finally:
        stop_worker(handle)
    assert not stage_dir.exists()


def test_worker_snapshot_rejects_wrong_approved_digest_and_cleans_stage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model = tmp_path / "case.json"
    registry = tmp_path / "registry.json"
    shutil.copy2(MODEL, model)
    shutil.copy2(REGISTRY, registry)
    stage = tmp_path / "forced-stage"

    def make_stage(prefix: str) -> str:
        del prefix
        stage.mkdir()
        return str(stage)

    monkeypatch.setattr(worker_module.tempfile, "mkdtemp", make_stage)
    with pytest.raises(RuntimeError, match="Model changed"):
        start_worker(
            worker_id=1,
            backend_name="mock",
            model_path=model,
            registry_path=registry,
            visible=False,
            expected_model_sha256="0" * 64,
            expected_registry_sha256=sha256_file(registry),
        )
    assert not stage.exists()


def test_ready_message_rejects_forged_worker_digest() -> None:
    message: dict[str, Any] = {
        "protocol": worker_module.IPC_PROTOCOL,
        "kind": "ready",
        "worker_id": 3,
        "generation": 2,
        "runtime": {
            "backend": "mock",
            "execution_artifacts": {
                "model_sha256": "a" * 64,
                "registry_sha256": "b" * 64,
                "staged_model_path": "model",
                "staged_registry_path": "registry",
            },
        },
    }
    with pytest.raises(RuntimeError, match="model digest mismatch"):
        _validate_ready_message(
            message,
            worker_id=3,
            generation=2,
            expected_model_sha256="c" * 64,
            expected_registry_sha256="b" * 64,
        )


def test_casepool_fails_closed_when_model_changes_after_identity_capture(
    tmp_path: Path,
) -> None:
    model = tmp_path / "case.json"
    registry = tmp_path / "registry.json"
    shutil.copy2(MODEL, model)
    shutil.copy2(REGISTRY, registry)
    pool = CasePool(
        backend_name="mock",
        model_path=model,
        registry_path=registry,
        workers=1,
        visible=False,
        cache_path=tmp_path / "cache.sqlite3",
    )
    model.write_text('{"changed": true}', encoding="utf-8")
    try:
        with pytest.raises(RuntimeError, match="Model changed"):
            pool.start()
    finally:
        pool.close()


def test_casepool_fails_closed_when_registry_changes_after_identity_capture(
    tmp_path: Path,
) -> None:
    model = tmp_path / "case.json"
    registry = tmp_path / "registry.json"
    shutil.copy2(MODEL, model)
    shutil.copy2(REGISTRY, registry)
    pool = CasePool(
        backend_name="mock",
        model_path=model,
        registry_path=registry,
        workers=1,
        visible=False,
        cache_path=tmp_path / "cache.sqlite3",
    )
    registry.write_text('{"nodes": {}}', encoding="utf-8")
    try:
        with pytest.raises(RuntimeError, match="Registry changed"):
            pool.start()
    finally:
        pool.close()
