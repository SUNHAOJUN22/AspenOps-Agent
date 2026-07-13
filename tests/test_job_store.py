from pathlib import Path

from aspenops_nexus.scheduler import JobStore


def test_job_store_claim_complete_and_list(tmp_path: Path) -> None:
    store = JobStore(tmp_path / "jobs.sqlite3")
    job_id = store.create({"x": 1})
    claimed = store.claim_next("worker-a")
    assert claimed == (job_id, {"x": 1})
    store.complete(job_id, [{"ok": True}], tmp_path / "bundle.zip")
    record = store.get(job_id)
    assert record is not None
    assert record["status"] == "completed"
    assert store.list_recent(1)[0]["job_id"] == job_id


def test_job_store_cancel_pending(tmp_path: Path) -> None:
    store = JobStore(tmp_path / "jobs.sqlite3")
    job_id = store.create({"x": 1})
    assert store.cancel(job_id)
    assert store.get(job_id)["status"] == "cancelled"
    assert store.claim_next("worker-a") is None
