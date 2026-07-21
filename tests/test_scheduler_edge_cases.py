from __future__ import annotations

import sqlite3
from pathlib import Path

from aspenops_nexus.scheduler import JobStore


def test_retryable_errors_move_to_retry_then_dead_letter(tmp_path: Path) -> None:
    store = JobStore(tmp_path / "jobs.sqlite3")
    job_id = store.create({"x": 1}, max_attempts=2)
    assert store.claim_next("worker-a") is not None
    assert store.mark_running(job_id, "worker-a")
    assert (
        store.retry_or_fail(
            job_id,
            "temporary license failure",
            "transient_license",
            retryable=True,
            owner="worker-a",
        )
        == "retry_wait"
    )
    assert store.claim_next("worker-b") is not None
    assert store.mark_running(job_id, "worker-b")
    assert (
        store.retry_or_fail(
            job_id,
            "temporary license failure",
            "transient_license",
            retryable=True,
            owner="worker-b",
        )
        == "dead_letter"
    )
    record = store.get(job_id)
    assert record is not None
    assert record["status"] == "dead_letter"
    assert record["error_class"] == "transient_license"


def test_non_retryable_error_fails_immediately(tmp_path: Path) -> None:
    store = JobStore(tmp_path / "jobs.sqlite3")
    job_id = store.create({"x": 1})
    assert store.claim_next("worker-a") is not None
    assert store.mark_running(job_id, "worker-a")
    assert (
        store.retry_or_fail(
            job_id,
            "invalid registry",
            "invalid_request",
            retryable=False,
            owner="worker-a",
        )
        == "failed"
    )
    assert store.get(job_id)["status"] == "failed"


def test_service_restart_recovers_unleased_running_job(tmp_path: Path) -> None:
    path = tmp_path / "jobs.sqlite3"
    store = JobStore(path)
    job_id = store.create({"x": 1})
    assert store.claim_next("worker-a") is not None
    assert store.mark_running(job_id, "worker-a")
    with sqlite3.connect(path) as connection:
        connection.execute(
            "UPDATE jobs SET lease_expires_at=NULL WHERE job_id=?",
            (job_id,),
        )
    restarted = JobStore(path)
    record = restarted.get(job_id)
    assert record is not None
    assert record["status"] == "retry_wait"
    assert record["lease_owner"] is None


def test_service_restart_finalizes_unleased_cancelling_job(tmp_path: Path) -> None:
    path = tmp_path / "jobs.sqlite3"
    store = JobStore(path)
    job_id = store.create({"x": 1})
    assert store.claim_next("worker-a") is not None
    assert store.mark_running(job_id, "worker-a")
    assert store.cancel(job_id, grace_s=100)
    with sqlite3.connect(path) as connection:
        connection.execute(
            "UPDATE jobs SET lease_expires_at=NULL WHERE job_id=?",
            (job_id,),
        )
    restarted = JobStore(path)
    record = restarted.get(job_id)
    assert record is not None
    assert record["status"] == "cancelled"
    assert "restart" in record["error"]


def test_schema_migrates_legacy_job_table(tmp_path: Path) -> None:
    path = tmp_path / "jobs.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            CREATE TABLE jobs (
                job_id TEXT PRIMARY KEY,
                request_hash TEXT NOT NULL,
                status TEXT NOT NULL,
                request_json TEXT NOT NULL,
                result_json TEXT,
                error TEXT,
                bundle_path TEXT,
                worker_owner TEXT,
                cancel_requested INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                started_at TEXT,
                finished_at TEXT,
                updated_at TEXT NOT NULL
            )
            """
        )
    JobStore(path)
    with sqlite3.connect(path) as connection:
        columns = {str(row[1]) for row in connection.execute("PRAGMA table_info(jobs)")}
    assert {
        "lease_owner",
        "lease_expires_at",
        "attempt",
        "max_attempts",
        "result_commit_token",
        "error_class",
    }.issubset(columns)
