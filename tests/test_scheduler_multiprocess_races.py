from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from aspenops_nexus.config import Settings
from aspenops_nexus.scheduler import BackgroundScheduler, JobStore


def expire_lease(path: Path, job_id: str) -> None:
    expired = (datetime.now(UTC) - timedelta(seconds=10)).isoformat()
    with closing(sqlite3.connect(path)) as connection, connection:
        connection.execute(
            "UPDATE jobs SET lease_expires_at=? WHERE job_id=?",
            (expired, job_id),
        )


def running_job(
    store: JobStore,
    *,
    owner: str = "owner-a",
    max_attempts: int = 3,
) -> str:
    job_id = store.create({"kind": "batch"}, max_attempts=max_attempts)
    claimed = store.claim_next(owner, lease_s=120.0)
    assert claimed is not None and claimed[0] == job_id
    assert store.mark_running(job_id, owner, lease_s=120.0)
    return job_id


def test_second_store_does_not_recover_another_process_valid_lease(tmp_path: Path) -> None:
    path = tmp_path / "jobs.sqlite3"
    first = JobStore(path)
    job_id = running_job(first)

    second = JobStore(path)
    record = second.get(job_id)

    assert record is not None
    assert record["status"] == "running"
    assert record["lease_owner"] == "owner-a"
    assert record["error"] is None


def test_second_store_preserves_valid_cancelling_lease(tmp_path: Path) -> None:
    path = tmp_path / "jobs.sqlite3"
    first = JobStore(path)
    job_id = running_job(first)
    assert first.cancel(job_id, grace_s=120.0)

    second = JobStore(path)
    record = second.get(job_id)

    assert record is not None
    assert record["status"] == "cancelling"
    assert record["lease_owner"] == "owner-a"
    assert record["cancel_deadline"] is not None


def test_second_store_recovers_only_expired_lease(tmp_path: Path) -> None:
    path = tmp_path / "jobs.sqlite3"
    first = JobStore(path)
    job_id = running_job(first, max_attempts=2)
    expire_lease(path, job_id)

    second = JobStore(path)
    record = second.get(job_id)

    assert record is not None
    assert record["status"] == "retry_wait"
    assert record["lease_owner"] is None
    assert record["error_class"] == "lease_expired"


def test_second_store_dead_letters_expired_final_attempt(tmp_path: Path) -> None:
    path = tmp_path / "jobs.sqlite3"
    first = JobStore(path)
    job_id = running_job(first, max_attempts=1)
    expire_lease(path, job_id)

    second = JobStore(path)
    record = second.get(job_id)

    assert record is not None
    assert record["status"] == "dead_letter"
    assert record["finished_at"] is not None
    assert record["error_class"] == "lease_expired"


def test_second_store_finalizes_only_expired_cancellation(tmp_path: Path) -> None:
    path = tmp_path / "jobs.sqlite3"
    first = JobStore(path)
    job_id = running_job(first)
    assert first.cancel(job_id, grace_s=120.0)
    expire_lease(path, job_id)

    second = JobStore(path)
    record = second.get(job_id)

    assert record is not None
    assert record["status"] == "cancelled"
    assert record["finished_at"] is not None
    assert record["lease_owner"] is None


def test_cancel_between_bundle_write_and_complete_is_finalized_immediately(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scheduler = BackgroundScheduler(Settings(state_dir=tmp_path, backend="mock"))
    scheduler.owner = "owner-a"
    job_id = running_job(scheduler.store, owner=scheduler.owner)
    bundle = tmp_path / "bundles" / "race.zip"
    bundle.parent.mkdir(parents=True)
    bundle.write_bytes(b"bundle")
    results = [{"ok": True}]
    original_complete = scheduler.store.complete

    def complete_after_cancellation(*args: object, **kwargs: object) -> bool:
        assert scheduler.store.cancel(job_id, grace_s=120.0)
        return original_complete(*args, **kwargs)

    monkeypatch.setattr(scheduler.store, "complete", complete_after_cancellation)
    try:
        assert scheduler._commit_bundle(job_id, results, bundle)
        record = scheduler.store.get(job_id)
    finally:
        scheduler.stop()

    assert record is not None
    assert record["status"] == "cancelled"
    assert record["results"] == results
    assert record["bundle_path"] == str(bundle)
    assert bundle.is_file()


def test_stale_owner_uncommitted_bundle_is_deleted(tmp_path: Path) -> None:
    path = tmp_path / "jobs.sqlite3"
    scheduler = BackgroundScheduler(Settings(state_dir=tmp_path, backend="mock"))
    scheduler.owner = "owner-a"
    job_id = running_job(scheduler.store, owner=scheduler.owner, max_attempts=2)
    expire_lease(path, job_id)
    assert scheduler.store.claim_next("owner-b", lease_s=120.0) is not None
    assert scheduler.store.mark_running(job_id, "owner-b", lease_s=120.0)
    bundle = tmp_path / "bundles" / "stale.zip"
    bundle.parent.mkdir(parents=True)
    bundle.write_bytes(b"stale")

    try:
        assert not scheduler._commit_bundle(job_id, [{"ok": True}], bundle)
    finally:
        scheduler.stop()

    assert not bundle.exists()
    record = JobStore(path).get(job_id)
    assert record is not None
    assert record["status"] == "running"
    assert record["lease_owner"] == "owner-b"


def test_idempotent_duplicate_bundle_is_deleted_when_not_adopted(tmp_path: Path) -> None:
    scheduler = BackgroundScheduler(Settings(state_dir=tmp_path, backend="mock"))
    scheduler.owner = "owner-a"
    job_id = running_job(scheduler.store, owner=scheduler.owner)
    results = [{"ok": True}]
    adopted = tmp_path / "bundles" / "adopted.zip"
    duplicate = tmp_path / "bundles" / "duplicate.zip"
    adopted.parent.mkdir(parents=True)
    adopted.write_bytes(b"adopted")
    duplicate.write_bytes(b"duplicate")
    assert scheduler.store.complete(
        job_id,
        results,
        adopted,
        owner=scheduler.owner,
    )

    scheduler.owner = "stale-owner"
    try:
        assert scheduler._commit_bundle(job_id, results, duplicate)
    finally:
        scheduler.stop()

    assert adopted.is_file()
    assert not duplicate.exists()
    record = JobStore(tmp_path / "jobs.sqlite3").get(job_id)
    assert record is not None
    assert record["bundle_path"] == str(adopted)
