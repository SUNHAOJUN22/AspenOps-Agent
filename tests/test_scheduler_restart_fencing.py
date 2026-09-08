from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

import pytest

from aspenops_nexus.config import Settings
from aspenops_nexus.scheduler import BackgroundScheduler, JobStore


def test_second_store_preserves_live_running_lease(tmp_path: Path) -> None:
    path = tmp_path / "jobs.sqlite3"
    first = JobStore(path)
    job_id = first.create({"x": 1})
    assert first.claim_next("worker-a", lease_s=120.0) is not None
    assert first.mark_running(job_id, "worker-a", lease_s=120.0)

    second = JobStore(path)
    record = second.get(job_id)

    assert record is not None
    assert record["status"] == "running"
    assert record["lease_owner"] == "worker-a"
    assert record["lease_expires_at"] is not None


def test_second_store_preserves_live_cancelling_lease(tmp_path: Path) -> None:
    path = tmp_path / "jobs.sqlite3"
    first = JobStore(path)
    job_id = first.create({"x": 1})
    assert first.claim_next("worker-a", lease_s=120.0) is not None
    assert first.mark_running(job_id, "worker-a", lease_s=120.0)
    assert first.cancel(job_id, grace_s=120.0)

    second = JobStore(path)
    record = second.get(job_id)

    assert record is not None
    assert record["status"] == "cancelling"
    assert record["lease_owner"] == "worker-a"
    assert record["cancel_deadline"] is not None


def test_restart_recovers_only_unleased_orphan(tmp_path: Path) -> None:
    path = tmp_path / "jobs.sqlite3"
    first = JobStore(path)
    job_id = first.create({"x": 1})
    assert first.claim_next("worker-a", lease_s=120.0) is not None
    assert first.mark_running(job_id, "worker-a", lease_s=120.0)
    with closing(sqlite3.connect(path)) as connection, connection:
        connection.execute(
            "UPDATE jobs SET lease_expires_at=NULL WHERE job_id=?",
            (job_id,),
        )

    restarted = JobStore(path)
    record = restarted.get(job_id)

    assert record is not None
    assert record["status"] == "retry_wait"
    assert record["lease_owner"] is None
    assert record["error_class"] == "service_restart"


def test_commit_bundle_finalizes_cancel_arriving_during_complete(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scheduler = BackgroundScheduler(
        Settings(
            state_dir=tmp_path / "state",
            backend="mock",
            max_workers=1,
            license_slots=1,
        )
    )
    try:
        job_id = scheduler.store.create({"x": 1})
        assert scheduler.store.claim_next(scheduler.owner, lease_s=120.0) is not None
        assert scheduler.store.mark_running(job_id, scheduler.owner, lease_s=120.0)
        results: list[dict[str, Any]] = [{"ok": True}]
        bundle = tmp_path / "bundle.zip"
        bundle.write_bytes(b"bundle")
        original_complete = scheduler.store.complete

        def racing_complete(*args: Any, **kwargs: Any) -> bool:
            assert scheduler.store.cancel(job_id, grace_s=120.0)
            return original_complete(*args, **kwargs)

        monkeypatch.setattr(scheduler.store, "complete", racing_complete)

        assert scheduler._commit_bundle(job_id, results, bundle)
        record = scheduler.store.get(job_id)
        assert record is not None
        assert record["status"] == "cancelled"
        assert record["bundle_path"] == str(bundle)
    finally:
        scheduler.stop()
