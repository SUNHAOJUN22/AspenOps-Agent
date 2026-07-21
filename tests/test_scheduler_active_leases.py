from __future__ import annotations

import threading
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import aspenops_nexus.scheduler as scheduler_module
from aspenops_nexus.scheduler import BackgroundScheduler


class TwoTickStop:
    def __init__(self) -> None:
        self.calls = 0

    def wait(self, timeout: float) -> bool:
        del timeout
        self.calls += 1
        return self.calls > 1

    def is_set(self) -> bool:
        return False


class WatchStore:
    def __init__(self, *, heartbeat_ok: bool, due: list[str] | None = None) -> None:
        self.heartbeat_ok = heartbeat_ok
        self.due = list(due or [])
        self.heartbeats: list[tuple[str, str, float]] = []
        self.lease_lost: list[tuple[str, str, list[dict[str, Any]]]] = []
        self.abort_dispatches: list[tuple[str, str, list[dict[str, Any]]]] = []

    def heartbeat(self, job_id: str, owner: str, lease_s: float) -> bool:
        self.heartbeats.append((job_id, owner, lease_s))
        return self.heartbeat_ok

    def cancellation_due(self, owner: str | None = None) -> list[str]:
        assert owner == "scheduler-owner"
        return list(self.due)

    def record_lease_lost(
        self,
        job_id: str,
        owner: str,
        events: list[dict[str, Any]],
    ) -> None:
        self.lease_lost.append((job_id, owner, events))

    def mark_abort_dispatched(
        self,
        job_id: str,
        events: list[dict[str, Any]],
        *,
        owner: str,
    ) -> bool:
        self.abort_dispatches.append((job_id, owner, events))
        return True


class FakePool:
    def __init__(self) -> None:
        self.reasons: list[str] = []

    def force_recycle_all(self, reason: str) -> list[dict[str, Any]]:
        self.reasons.append(reason)
        return [{"worker_id": 0, "reason": reason}]


def watcher_scheduler(store: WatchStore) -> BackgroundScheduler:
    scheduler = object.__new__(BackgroundScheduler)
    scheduler.settings = SimpleNamespace(scheduler_poll_s=0.1, job_lease_s=3.0)
    scheduler.store = store
    scheduler._stop = TwoTickStop()
    scheduler._active_lock = threading.RLock()
    scheduler._active_jobs = {"job-1"}
    scheduler._active_pools = {}
    scheduler.owner = "scheduler-owner"
    return scheduler


def test_watcher_heartbeats_active_job_before_pool_binding() -> None:
    store = WatchStore(heartbeat_ok=True)
    scheduler = watcher_scheduler(store)

    scheduler._watch_active_jobs()

    assert store.heartbeats == [("job-1", "scheduler-owner", 3.0)]
    assert scheduler._active_job_snapshot() == {"job-1"}
    assert store.lease_lost == []


def test_watcher_recycles_pool_and_unregisters_job_after_lease_loss() -> None:
    store = WatchStore(heartbeat_ok=False)
    scheduler = watcher_scheduler(store)
    pool = FakePool()
    scheduler._active_pools["job-1"] = pool

    scheduler._watch_active_jobs()

    assert pool.reasons == ["lease_lost"]
    assert scheduler._active_snapshot() == {}
    assert scheduler._active_job_snapshot() == set()
    assert store.lease_lost == [
        (
            "job-1",
            "scheduler-owner",
            [{"worker_id": 0, "reason": "lease_lost"}],
        )
    ]


def test_due_cancellation_without_pool_keeps_deadline_pending() -> None:
    store = WatchStore(heartbeat_ok=True, due=["job-1"])
    scheduler = watcher_scheduler(store)

    scheduler._watch_active_jobs()

    assert store.abort_dispatches == []
    assert scheduler._active_job_snapshot() == {"job-1"}


class LoopStore:
    def __init__(self, scheduler: BackgroundScheduler) -> None:
        self.scheduler = scheduler
        self.claimed = False
        self.completed = False

    def claim_next(self, owner: str, lease_s: float) -> tuple[str, dict[str, Any]] | None:
        del owner, lease_s
        if self.claimed:
            return None
        self.claimed = True
        return "job-1", {"backend": "mock"}

    def mark_running(self, job_id: str, owner: str, lease_s: float) -> bool:
        del job_id, owner, lease_s
        return True

    def is_cancel_requested(self, job_id: str) -> bool:
        del job_id
        return False

    def append_progress(
        self,
        job_id: str,
        results: list[dict[str, Any]],
        last_completed_point: int,
        *,
        owner: str,
    ) -> bool:
        del job_id, results, last_completed_point, owner
        return True

    def get(self, job_id: str) -> dict[str, Any]:
        del job_id
        return {"cancel_requested": False}

    def complete(
        self,
        job_id: str,
        results: list[dict[str, Any]],
        bundle_path: Path,
        commit_token: str | None = None,
        *,
        owner: str,
    ) -> bool:
        del job_id, results, bundle_path, commit_token, owner
        self.completed = True
        return True

    def retry_or_fail(
        self,
        job_id: str,
        error: str,
        error_class: str,
        *,
        retryable: bool,
        owner: str,
    ) -> str:
        raise AssertionError((job_id, error, error_class, retryable, owner))


class LoopPoolManager:
    def evict_idle(self) -> int:
        return 0


def test_loop_registers_job_for_entire_execution_window(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scheduler = object.__new__(BackgroundScheduler)
    scheduler.settings = SimpleNamespace(
        state_dir=tmp_path,
        job_lease_s=3.0,
        scheduler_poll_s=0.01,
    )
    scheduler._stop = threading.Event()
    scheduler._active_lock = threading.RLock()
    scheduler._active_jobs = set()
    scheduler._active_pools = {}
    scheduler.owner = "scheduler-owner"
    scheduler.pool_manager = LoopPoolManager()
    scheduler.store = LoopStore(scheduler)

    def run_batch(*args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        del args, kwargs
        assert scheduler._active_job_snapshot() == {"job-1"}
        scheduler._stop.set()
        return [{"ok": True, "violations": []}]

    def write_bundle(*, output_path: Path, **kwargs: Any) -> Path:
        del kwargs
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"bundle")
        return output_path

    monkeypatch.setattr(scheduler_module, "run_batch_document", run_batch)
    monkeypatch.setattr(scheduler_module, "write_run_bundle", write_bundle)

    scheduler._loop()

    assert scheduler.store.completed is True
    assert scheduler._active_job_snapshot() == set()
