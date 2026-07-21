from __future__ import annotations

from pathlib import Path

from aspenops_nexus.scheduler import JobStore


def test_second_store_preserves_live_claimed_lease(tmp_path: Path) -> None:
    path = tmp_path / "jobs.sqlite3"
    first = JobStore(path)
    job_id = first.create({"x": 1})
    assert first.claim_next("worker-a", lease_s=120.0) is not None

    second = JobStore(path)
    record = second.get(job_id)

    assert record is not None
    assert record["status"] == "claimed"
    assert record["lease_owner"] == "worker-a"
    assert record["lease_expires_at"] is not None
