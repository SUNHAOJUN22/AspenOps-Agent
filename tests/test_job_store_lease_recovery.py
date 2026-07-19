from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from aspenops_nexus.scheduler import JobStore


def _expire_lease(path: Path, job_id: str) -> None:
    expired = (datetime.now(UTC) - timedelta(seconds=10)).isoformat()
    with sqlite3.connect(path) as connection:
        connection.execute(
            "UPDATE jobs SET lease_expires_at=? WHERE job_id=?",
            (expired, job_id),
        )


def test_expired_lease_retries_before_final_attempt(tmp_path: Path) -> None:
    path = tmp_path / "jobs.sqlite3"
    store = JobStore(path)
    job_id = store.create({"x": 1}, max_attempts=2)
    assert store.claim_next("worker-a") is not None
    assert store.mark_running(job_id, "worker-a")
    _expire_lease(path, job_id)

    assert store.claim_next("worker-b") == (job_id, {"x": 1})
    record = store.get(job_id)
    assert record is not None
    assert record["status"] == "claimed"
    assert record["attempt"] == 2
    assert record["lease_owner"] == "worker-b"
    event = next(item for item in store.events(job_id) if item["event"] == "lease_expired")
    assert event["payload"] == {"attempt": 1, "max_attempts": 2}


def test_expired_lease_dead_letters_final_attempt(tmp_path: Path) -> None:
    path = tmp_path / "jobs.sqlite3"
    store = JobStore(path)
    job_id = store.create({"x": 1}, max_attempts=1)
    assert store.claim_next("worker-a") is not None
    assert store.mark_running(job_id, "worker-a")
    _expire_lease(path, job_id)

    assert store.claim_next("worker-b") is None
    record = store.get(job_id)
    assert record is not None
    assert record["status"] == "dead_letter"
    assert record["error_class"] == "lease_expired"
    assert record["finished_at"] is not None
    assert record["lease_owner"] is None
    event = next(
        item
        for item in store.events(job_id)
        if item["event"] == "dead_letter_after_lease_expiry"
    )
    assert event["payload"] == {"attempt": 1, "max_attempts": 1}


def test_service_restart_retries_before_final_attempt(tmp_path: Path) -> None:
    path = tmp_path / "jobs.sqlite3"
    store = JobStore(path)
    job_id = store.create({"x": 1}, max_attempts=2)
    assert store.claim_next("worker-a") is not None
    assert store.mark_running(job_id, "worker-a")

    restarted = JobStore(path)
    record = restarted.get(job_id)
    assert record is not None
    assert record["status"] == "retry_wait"
    assert record["error_class"] == "service_restart"
    assert record["finished_at"] is None
    assert record["lease_owner"] is None


def test_service_restart_dead_letters_final_attempt(tmp_path: Path) -> None:
    path = tmp_path / "jobs.sqlite3"
    store = JobStore(path)
    job_id = store.create({"x": 1}, max_attempts=1)
    assert store.claim_next("worker-a") is not None
    assert store.mark_running(job_id, "worker-a")

    restarted = JobStore(path)
    record = restarted.get(job_id)
    assert record is not None
    assert record["status"] == "dead_letter"
    assert record["error_class"] == "service_restart"
    assert record["finished_at"] is not None
    assert record["lease_owner"] is None
    assert restarted.claim_next("worker-b") is None


def test_cancelled_expired_lease_stays_cancelled(tmp_path: Path) -> None:
    path = tmp_path / "jobs.sqlite3"
    store = JobStore(path)
    job_id = store.create({"x": 1}, max_attempts=2)
    assert store.claim_next("worker-a") is not None
    assert store.mark_running(job_id, "worker-a")
    assert store.cancel(job_id, grace_s=100.0)
    _expire_lease(path, job_id)

    assert store.claim_next("worker-b") is None
    record = store.get(job_id)
    assert record is not None
    assert record["status"] == "cancelled"
    assert record["cancel_requested"] is True
    assert record["finished_at"] is not None
    assert any(
        item["event"] == "cancelled_after_lease_expiry" for item in store.events(job_id)
    )
