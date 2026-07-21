from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from aspenops_nexus.scheduler import JobStore


def test_job_store_claim_run_complete_and_list(tmp_path: Path) -> None:
    store = JobStore(tmp_path / "jobs.sqlite3")
    job_id = store.create({"x": 1})
    claimed = store.claim_next("worker-a")
    assert claimed == (job_id, {"x": 1})
    claimed_record = store.get(job_id)
    assert claimed_record is not None
    assert claimed_record["status"] == "claimed"
    assert claimed_record["attempt"] == 1
    assert claimed_record["lease_owner"] == "worker-a"
    assert store.mark_running(job_id, "worker-a")
    assert store.heartbeat(job_id, "worker-a")
    token = "stable-token"
    assert store.complete(
        job_id,
        [{"ok": True}],
        tmp_path / "bundle.zip",
        commit_token=token,
        owner="worker-a",
    )
    assert store.complete(
        job_id,
        [{"ok": True}],
        tmp_path / "bundle.zip",
        commit_token=token,
        owner="worker-a",
    )
    record = store.get(job_id)
    assert record is not None
    assert record["status"] == "completed"
    assert record["result_commit_token"] == token
    assert store.list_recent(1)[0]["job_id"] == job_id
    assert {event["event"] for event in store.events(job_id)} >= {
        "created",
        "claimed",
        "running",
        "completed",
    }


def test_job_store_cancel_pending(tmp_path: Path) -> None:
    store = JobStore(tmp_path / "jobs.sqlite3")
    job_id = store.create({"x": 1})
    assert store.cancel(job_id)
    record = store.get(job_id)
    assert record is not None
    assert record["status"] == "cancelled"
    assert store.claim_next("worker-a") is None


def test_job_store_cancel_running_sets_deadline(tmp_path: Path) -> None:
    store = JobStore(tmp_path / "jobs.sqlite3")
    job_id = store.create({"x": 1})
    assert store.claim_next("worker-a") is not None
    assert store.mark_running(job_id, "worker-a")
    assert store.cancel(job_id, grace_s=0.0)
    record = store.get(job_id)
    assert record is not None
    assert record["status"] == "cancelling"
    assert record["cancel_requested"] is True
    assert job_id in store.cancellation_due()
    assert store.finalize_cancelled(job_id, [{"ok": False}], owner="worker-a")
    assert store.get(job_id)["status"] == "cancelled"


def test_expired_lease_is_reclaimed_at_least_once(tmp_path: Path) -> None:
    path = tmp_path / "jobs.sqlite3"
    store = JobStore(path)
    job_id = store.create({"x": 1}, max_attempts=3)
    assert store.claim_next("worker-a") is not None
    assert store.mark_running(job_id, "worker-a")
    expired = (datetime.now(UTC) - timedelta(seconds=10)).isoformat()
    with sqlite3.connect(path) as connection:
        connection.execute(
            "UPDATE jobs SET lease_expires_at=? WHERE job_id=?",
            (expired, job_id),
        )
    reclaimed = store.claim_next("worker-b")
    assert reclaimed == (job_id, {"x": 1})
    record = store.get(job_id)
    assert record is not None
    assert record["lease_owner"] == "worker-b"
    assert record["attempt"] == 2
    assert any(event["event"] == "lease_expired" for event in store.events(job_id))
