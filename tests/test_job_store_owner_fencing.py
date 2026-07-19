from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from aspenops_nexus.scheduler import JobStore


def expire_lease(path: Path, job_id: str) -> None:
    expired = (datetime.now(UTC) - timedelta(seconds=10)).isoformat()
    with sqlite3.connect(path) as connection:
        connection.execute(
            "UPDATE jobs SET lease_expires_at=? WHERE job_id=?",
            (expired, job_id),
        )


def reclaim_job(store: JobStore, path: Path, job_id: str) -> None:
    expire_lease(path, job_id)
    assert store.claim_next("worker-b") == (job_id, {"x": 1})
    assert store.mark_running(job_id, "worker-b")


def test_stale_owner_cannot_commit_progress_or_completion(tmp_path: Path) -> None:
    path = tmp_path / "jobs.sqlite3"
    store = JobStore(path)
    job_id = store.create({"x": 1}, max_attempts=2)
    assert store.claim_next("worker-a") is not None
    assert store.mark_running(job_id, "worker-a")
    reclaim_job(store, path, job_id)

    stale_results = [{"ok": True, "source": "worker-a"}]
    assert not store.append_progress(job_id, stale_results, 0, owner="worker-a")
    assert not store.complete(
        job_id,
        stale_results,
        tmp_path / "stale.zip",
        commit_token="stale",
        owner="worker-a",
    )

    fresh_results = [{"ok": True, "source": "worker-b"}]
    assert store.append_progress(job_id, fresh_results, 0, owner="worker-b")
    assert store.complete(
        job_id,
        fresh_results,
        tmp_path / "fresh.zip",
        commit_token="fresh",
        owner="worker-b",
    )
    record = store.get(job_id)
    assert record is not None
    assert record["status"] == "completed"
    assert record["results"] == fresh_results
    assert record["result_commit_token"] == "fresh"


def test_stale_owner_cannot_finalize_cancel_or_retry(tmp_path: Path) -> None:
    path = tmp_path / "jobs.sqlite3"
    store = JobStore(path)
    job_id = store.create({"x": 1}, max_attempts=2)
    assert store.claim_next("worker-a") is not None
    assert store.mark_running(job_id, "worker-a")
    reclaim_job(store, path, job_id)
    assert store.cancel(job_id, grace_s=100.0)

    assert not store.finalize_cancelled(job_id, [], owner="worker-a")
    assert (
        store.retry_or_fail(
            job_id,
            "stale failure",
            "transport_failure",
            retryable=True,
            owner="worker-a",
        )
        == "lease_lost"
    )
    record = store.get(job_id)
    assert record is not None
    assert record["status"] == "cancelling"
    assert record["lease_owner"] == "worker-b"

    assert store.finalize_cancelled(job_id, [], owner="worker-b")
    assert store.get(job_id)["status"] == "cancelled"


def test_completion_is_idempotent_for_the_same_commit_token(tmp_path: Path) -> None:
    store = JobStore(tmp_path / "jobs.sqlite3")
    job_id = store.create({"x": 1})
    assert store.claim_next("worker-a") is not None
    assert store.mark_running(job_id, "worker-a")
    results = [{"ok": True}]
    assert store.complete(
        job_id,
        results,
        tmp_path / "bundle.zip",
        commit_token="same",
        owner="worker-a",
    )
    assert store.complete(
        job_id,
        results,
        tmp_path / "bundle.zip",
        commit_token="same",
        owner="stale-owner",
    )
    assert not store.complete(
        job_id,
        results,
        tmp_path / "different.zip",
        commit_token="different",
        owner="worker-a",
    )


def test_cancellation_deadline_and_abort_dispatch_are_owner_scoped(tmp_path: Path) -> None:
    store = JobStore(tmp_path / "jobs.sqlite3")
    job_id = store.create({"x": 1})
    assert store.claim_next("worker-a") is not None
    assert store.mark_running(job_id, "worker-a")
    assert store.cancel(job_id, grace_s=0.0)

    assert store.cancellation_due(owner="worker-b") == []
    assert store.cancellation_due(owner="worker-a") == [job_id]
    assert not store.mark_abort_dispatched(job_id, [], owner="worker-b")
    assert store.get(job_id)["cancel_deadline"] is not None
    events = [{"worker_id": 0, "reason": "cancel_deadline"}]
    assert store.mark_abort_dispatched(job_id, events, owner="worker-a")
    assert store.get(job_id)["cancel_deadline"] is None
    event = next(
        item
        for item in store.events(job_id)
        if item["event"] == "worker_recycle_dispatched"
    )
    assert event["payload"] == {"events": events, "owner": "worker-a"}
