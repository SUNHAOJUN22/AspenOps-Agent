from __future__ import annotations

import json
import time
from pathlib import Path

from test_batch import request

from aspenops_nexus.config import Settings
from aspenops_nexus.pool_manager import PoolManager
from aspenops_nexus.scheduler import BackgroundScheduler

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "src/aspenops_nexus/data/mock-case.json"
REGISTRY = ROOT / "src/aspenops_nexus/data/node-registry.json"


def manager(tmp_path: Path, *, slots: int = 2, cases: int = 2) -> PoolManager:
    return PoolManager(
        cache_path=tmp_path / "cache.sqlite3",
        license_slots=slots,
        max_resident_cases=cases,
        idle_timeout_s=3600,
    )


def test_reuses_the_same_pool_for_identical_case_content(tmp_path: Path) -> None:
    pool_manager = manager(tmp_path)
    with pool_manager.acquire(
        backend_name="mock",
        model_path=MODEL,
        registry_path=REGISTRY,
        workers=2,
        visible=False,
    ) as first:
        first_identity = id(first)
    with pool_manager.acquire(
        backend_name="mock",
        model_path=MODEL,
        registry_path=REGISTRY,
        workers=2,
        visible=False,
    ) as second:
        assert id(second) == first_identity
    stats = pool_manager.stats()
    assert stats["created_pools"] == 1
    assert stats["reused_leases"] == 1
    assert stats["resident_workers"] == 2
    pool_manager.close()


def test_license_budget_caps_requested_workers(tmp_path: Path) -> None:
    pool_manager = manager(tmp_path, slots=1)
    with pool_manager.acquire(
        backend_name="mock",
        model_path=MODEL,
        registry_path=REGISTRY,
        workers=8,
        visible=False,
    ) as pool:
        assert pool.workers == 1
    assert pool_manager.stats()["resident_workers"] == 1
    pool_manager.close()


def test_lru_evicts_an_idle_case_before_opening_another(tmp_path: Path) -> None:
    alternate = tmp_path / "alternate-model.json"
    model_data = json.loads(MODEL.read_text(encoding="utf-8"))
    model_data["solve_delay_ms"] = 1
    alternate.write_text(json.dumps(model_data), encoding="utf-8")
    pool_manager = manager(tmp_path, slots=1, cases=1)
    with pool_manager.acquire(
        backend_name="mock",
        model_path=MODEL,
        registry_path=REGISTRY,
        workers=1,
        visible=False,
    ):
        pass
    with pool_manager.acquire(
        backend_name="mock",
        model_path=alternate,
        registry_path=REGISTRY,
        workers=1,
        visible=False,
    ):
        pass
    stats = pool_manager.stats()
    assert stats["created_pools"] == 2
    assert stats["evicted_pools"] == 1
    assert stats["resident_cases"] == 1
    pool_manager.close()


def test_background_scheduler_reuses_pool_across_jobs(tmp_path: Path) -> None:
    scheduler = BackgroundScheduler(
        Settings(
            state_dir=tmp_path,
            max_workers=1,
            license_slots=1,
            max_resident_cases=1,
        )
    )
    first_job = scheduler.submit(request())
    second_job = scheduler.submit(request())
    deadline = time.time() + 30
    first_record = None
    second_record = None
    while time.time() < deadline:
        first_record = scheduler.store.get(first_job)
        second_record = scheduler.store.get(second_job)
        if (
            first_record
            and second_record
            and first_record["status"] in {"completed", "failed"}
            and second_record["status"] in {"completed", "failed"}
        ):
            break
        time.sleep(0.1)
    stats = scheduler.pool_manager.stats()
    scheduler.stop()
    assert first_record is not None and first_record["status"] == "completed"
    assert second_record is not None and second_record["status"] == "completed"
    assert stats["created_pools"] == 1
    assert stats["reused_leases"] >= 1
