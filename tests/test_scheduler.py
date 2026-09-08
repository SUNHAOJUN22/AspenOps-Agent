from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from test_batch import request

from aspenops_nexus.config import Settings
from aspenops_nexus.scheduler import BackgroundScheduler

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "src/aspenops_nexus/data/mock-case.json"


def wait_for_status(
    scheduler: BackgroundScheduler,
    job_id: str,
    terminal: set[str],
    *,
    timeout_s: float = 30.0,
) -> dict[str, Any] | None:
    deadline = time.time() + timeout_s
    record = None
    while time.time() < deadline:
        record = scheduler.store.get(job_id)
        if record and record["status"] in terminal:
            return record
        time.sleep(0.05)
    return record


def wait_for_active_pool(
    scheduler: BackgroundScheduler,
    job_id: str,
    *,
    timeout_s: float = 10.0,
) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if job_id in scheduler._active_snapshot():
            return True
        time.sleep(0.02)
    return False


def test_background_scheduler(tmp_path: Path) -> None:
    scheduler = BackgroundScheduler(Settings(state_dir=tmp_path, max_workers=1, license_slots=1))
    job_id = scheduler.submit(request())
    record = wait_for_status(scheduler, job_id, {"completed", "failed", "dead_letter"})
    scheduler.stop()
    assert record is not None
    assert record["status"] == "completed", record
    assert Path(record["bundle_path"]).exists()
    assert record["last_completed_point"] == len(record["results"]) - 1


def test_running_job_is_cancelled_after_deadline(tmp_path: Path) -> None:
    slow_model = tmp_path / "slow-mock-case.json"
    model_data = json.loads(MODEL.read_text(encoding="utf-8"))
    model_data["solve_delay_ms"] = 1000
    slow_model.write_text(json.dumps(model_data), encoding="utf-8")
    batch = request()
    batch["model_path"] = str(slow_model)
    batch["workers"] = 1
    settings = Settings(
        state_dir=tmp_path / "state",
        max_workers=1,
        license_slots=1,
        scheduler_poll_s=0.02,
        job_lease_s=2.0,
        cancellation_grace_s=0.05,
    )
    scheduler = BackgroundScheduler(settings)
    job_id = scheduler.submit(batch)
    running = wait_for_status(scheduler, job_id, {"running", "completed", "failed"})
    assert running is not None and running["status"] == "running"
    assert wait_for_active_pool(scheduler, job_id)
    time.sleep(0.1)
    assert scheduler.cancel(job_id)
    record = wait_for_status(scheduler, job_id, {"cancelled", "failed", "dead_letter"})
    events = scheduler.store.events(job_id)
    scheduler.stop()
    assert record is not None
    assert record["status"] == "cancelled", record
    assert record["cancel_requested"] is True
    assert record["results"] is not None
    assert Path(record["bundle_path"]).exists()
    assert any(event["event"] == "worker_recycle_dispatched" for event in events)


def test_cancel_completion_orders_recycle_before_terminal(tmp_path: Path) -> None:
    slow_model = tmp_path / "slow-cooperative-cancel-case.json"
    model_data = json.loads(MODEL.read_text(encoding="utf-8"))
    model_data["solve_delay_ms"] = 1000
    slow_model.write_text(json.dumps(model_data), encoding="utf-8")
    batch = request()
    batch["model_path"] = str(slow_model)
    batch["workers"] = 1
    settings = Settings(
        state_dir=tmp_path / "state",
        max_workers=1,
        license_slots=1,
        scheduler_poll_s=0.02,
        job_lease_s=2.0,
        cancellation_grace_s=30.0,
    )
    scheduler = BackgroundScheduler(settings)
    job_id = scheduler.submit(batch)
    running = wait_for_status(
        scheduler,
        job_id,
        {"running", "completed", "failed"},
    )
    assert running is not None and running["status"] == "running"
    assert wait_for_active_pool(scheduler, job_id)
    assert scheduler.cancel(job_id)
    record = wait_for_status(
        scheduler,
        job_id,
        {"cancelled", "failed", "dead_letter"},
    )
    events = scheduler.store.events(job_id)
    scheduler.stop()
    assert record is not None
    assert record["status"] == "cancelled", record
    assert record["finished_at"] is not None
    recycle = next(event for event in events if event["event"] == "worker_recycle_dispatched")
    assert recycle["created_at"] <= record["finished_at"]
