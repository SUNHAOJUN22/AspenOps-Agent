import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from test_batch import request

from aspenops_nexus.config import Settings
from aspenops_nexus.scheduler import BackgroundScheduler, JobStateError, JobStore


def test_background_scheduler(tmp_path: Path) -> None:
    scheduler = BackgroundScheduler(Settings(state_dir=tmp_path, max_workers=1, license_slots=1))
    job_id = scheduler.submit(request())
    deadline = time.monotonic() + 20
    record = None
    while time.monotonic() < deadline:
        record = scheduler.store.get(job_id)
        if record and record["status"] in {"completed", "failed"}:
            break
        time.sleep(0.1)
    scheduler.stop()
    assert record is not None
    assert record["status"] == "completed", record
    assert Path(record["bundle_path"]).exists()


def test_claim_is_atomic_across_store_instances(tmp_path: Path) -> None:
    path = tmp_path / "jobs.sqlite3"
    first = JobStore(path)
    second = JobStore(path)
    job_id = first.create({"case": 1})

    with ThreadPoolExecutor(max_workers=2) as executor:
        claims = list(
            executor.map(
                lambda item: item[0].claim_next(item[1], lease_seconds=60),
                [(first, "worker-a"), (second, "worker-b")],
            )
        )

    successful = [claim for claim in claims if claim is not None]
    assert len(successful) == 1
    assert successful[0][0] == job_id
    assert first.get(job_id)["status"] == "claimed"


def test_legal_state_machine_and_terminal_immutability(tmp_path: Path) -> None:
    store = JobStore(tmp_path / "jobs.sqlite3")
    job_id = store.create({"case": 1})
    assert store.get(job_id)["status"] == "pending"

    assert store.claim_next("worker", lease_seconds=60)[0] == job_id
    store.mark_running(job_id, "worker")
    assert store.get(job_id)["status"] == "running"

    assert store.complete(job_id, [{"ok": True}], tmp_path / "bundle.zip", "worker")
    assert store.get(job_id)["status"] == "completed"
    with pytest.raises(JobStateError):
        store.fail(job_id, "EngineError: late failure", owner="worker")


def test_second_store_does_not_interrupt_live_lease(tmp_path: Path) -> None:
    path = tmp_path / "jobs.sqlite3"
    store = JobStore(path)
    job_id = store.create({"case": 1})
    store.claim_next("worker", lease_seconds=60)
    store.mark_running(job_id, "worker")

    reopened = JobStore(path)
    assert reopened.get(job_id)["status"] == "running"


def test_expired_lease_is_recovered_as_interrupted(tmp_path: Path) -> None:
    path = tmp_path / "jobs.sqlite3"
    store = JobStore(path)
    job_id = store.create({"case": 1})
    store.claim_next("worker", lease_seconds=0.001)
    store.mark_running(job_id, "worker")
    time.sleep(0.01)

    reopened = JobStore(path)
    record = reopened.get(job_id)
    assert record["status"] == "interrupted"
    assert record["error_code"] == "LEASE_EXPIRED"


def test_pending_cancel_is_terminal(tmp_path: Path) -> None:
    store = JobStore(tmp_path / "jobs.sqlite3")
    job_id = store.create({"case": 1})
    assert store.cancel(job_id)
    assert store.get(job_id)["status"] == "cancelled"
    assert store.claim_next("worker", lease_seconds=60) is None
    with pytest.raises(JobStateError):
        store.fail(job_id, "EngineError: must not rewrite terminal state")


def test_idempotency_key_is_bound_to_request_hash(tmp_path: Path) -> None:
    store = JobStore(tmp_path / "jobs.sqlite3")
    first = store.create({"case": 1}, idempotency_key="request-1")
    assert store.create({"case": 1}, idempotency_key="request-1") == first
    with pytest.raises(ValueError):
        store.create({"case": 2}, idempotency_key="request-1")


def test_schema_rejects_illegal_status(tmp_path: Path) -> None:
    path = tmp_path / "jobs.sqlite3"
    JobStore(path)
    with sqlite3.connect(path) as connection, pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            """
            INSERT INTO jobs(job_id, request_hash, status, request_json, created_at, updated_at)
            VALUES('bad', 'hash', 'NOT_A_STATE', '{}', 'now', 'now')
            """
        )


def test_legacy_schema_migration_is_atomic_and_conservative(tmp_path: Path) -> None:
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
        connection.execute(
            """
            INSERT INTO jobs(
                job_id, request_hash, status, request_json, worker_owner,
                created_at, started_at, updated_at
            ) VALUES('running-job', 'hash', 'running', '{}', 'old-worker', 't0', 't1', 't2')
            """
        )

    store = JobStore(path)
    record = store.get("running-job")
    assert record["status"] == "interrupted"
    with sqlite3.connect(path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0] == 1
