from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path

from aspenops_nexus.scheduler import JobStore


def expire_lease(path: Path, job_id: str) -> None:
    expired = (datetime.now(UTC) - timedelta(seconds=10)).isoformat()
    with closing(sqlite3.connect(path)) as connection, connection:
        connection.execute(
            "UPDATE jobs SET lease_expires_at=? WHERE job_id=?",
            (expired, job_id),
        )


def test_expired_claim_cannot_transition_to_running(tmp_path: Path) -> None:
    path = tmp_path / "jobs.sqlite3"
    store = JobStore(path)
    job_id = store.create({"x": 1}, max_attempts=2)
    assert store.claim_next("worker-a") is not None
    expire_lease(path, job_id)

    assert store.mark_running(job_id, "worker-a") is False
    assert store.claim_next("worker-b") == (job_id, {"x": 1})
    record = store.get(job_id)
    assert record is not None
    assert record["status"] == "claimed"
    assert record["attempt"] == 2
    assert record["lease_owner"] == "worker-b"


def test_late_heartbeat_cannot_revive_expired_running_lease(tmp_path: Path) -> None:
    path = tmp_path / "jobs.sqlite3"
    store = JobStore(path)
    job_id = store.create({"x": 1}, max_attempts=2)
    assert store.claim_next("worker-a") is not None
    assert store.mark_running(job_id, "worker-a")
    expire_lease(path, job_id)

    assert store.heartbeat(job_id, "worker-a") is False
    assert store.claim_next("worker-b") == (job_id, {"x": 1})
    record = store.get(job_id)
    assert record is not None
    assert record["attempt"] == 2
    assert record["lease_owner"] == "worker-b"


def test_reclaimed_attempt_clears_stale_current_error_fields(tmp_path: Path) -> None:
    path = tmp_path / "jobs.sqlite3"
    store = JobStore(path)
    job_id = store.create({"x": 1}, max_attempts=2)
    assert store.claim_next("worker-a") is not None
    assert store.mark_running(job_id, "worker-a")
    expire_lease(path, job_id)

    assert store.claim_next("worker-b") == (job_id, {"x": 1})
    record = store.get(job_id)
    assert record is not None
    assert record["status"] == "claimed"
    assert record["error"] is None
    assert record["error_class"] is None
    assert record["finished_at"] is None
    assert any(item["event"] == "lease_expired" for item in store.events(job_id))
