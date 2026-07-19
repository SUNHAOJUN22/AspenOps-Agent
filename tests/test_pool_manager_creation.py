from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Any

import pytest

from aspenops_nexus.pool_manager import CaseKey, PoolManager, PoolRecord


class FakePool:
    def __init__(self, name: str) -> None:
        self.name = name
        self.close_calls = 0

    def close(self) -> None:
        self.close_calls += 1


def files(tmp_path: Path, suffix: str) -> tuple[Path, Path]:
    model = tmp_path / f"model-{suffix}.json"
    registry = tmp_path / f"registry-{suffix}.json"
    model.write_text(f'{{"case":"{suffix}"}}', encoding="utf-8")
    registry.write_text(f'{{"registry":"{suffix}"}}', encoding="utf-8")
    return model, registry


def record(kwargs: dict[str, Any], pool: FakePool) -> PoolRecord:
    return PoolRecord(
        key=CaseKey(
            backend=str(kwargs["backend_name"]),
            runtime_identity_hash=f"runtime-{pool.name}",
            model_digest=str(kwargs["model_digest"]),
            registry_digest=str(kwargs["registry_digest"]),
            compatibility_profile=str(kwargs["compatibility_profile"]),
        ),
        pool=pool,  # type: ignore[arg-type]
        workers=int(kwargs["workers"]),
        lookup_key=kwargs["lookup_key"],
    )


def wait_for_stat(manager: PoolManager, key: str, value: int, timeout: float = 2.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if manager.stats()[key] == value:
            return
        time.sleep(0.001)
    raise AssertionError(f"{key} did not reach {value}: {manager.stats()}")


def acquire_once(
    manager: PoolManager,
    model: Path,
    registry: Path,
    output: list[Any],
    errors: list[BaseException],
) -> None:
    try:
        with manager.acquire(
            backend_name="mock",
            model_path=model,
            registry_path=registry,
            workers=1,
            visible=False,
        ) as pool:
            output.append(pool)
    except BaseException as exc:
        errors.append(exc)


def test_same_case_creation_is_singleflight(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model, registry = files(tmp_path, "same")
    manager = PoolManager(
        cache_path=tmp_path / "cache.sqlite3",
        license_slots=2,
        max_resident_cases=2,
    )
    entered = threading.Event()
    release = threading.Event()
    calls = 0
    pool = FakePool("same")

    def new_record(**kwargs: Any) -> PoolRecord:
        nonlocal calls
        calls += 1
        entered.set()
        assert release.wait(2.0)
        return record(kwargs, pool)

    monkeypatch.setattr(manager, "_new_record", new_record)
    output: list[Any] = []
    errors: list[BaseException] = []
    first = threading.Thread(target=acquire_once, args=(manager, model, registry, output, errors))
    second = threading.Thread(target=acquire_once, args=(manager, model, registry, output, errors))
    first.start()
    assert entered.wait(2.0)
    second.start()
    wait_for_stat(manager, "creation_waiters", 1)
    release.set()
    first.join(2.0)
    second.join(2.0)

    assert errors == []
    assert calls == 1
    assert output == [pool, pool]
    assert manager.stats()["reused_leases"] == 1
    manager.close()
    assert pool.close_calls == 1


def test_different_cases_start_concurrently_within_license_budget(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first_files = files(tmp_path, "first")
    second_files = files(tmp_path, "second")
    manager = PoolManager(
        cache_path=tmp_path / "cache.sqlite3",
        license_slots=2,
        max_resident_cases=2,
    )
    barrier = threading.Barrier(2)
    pools: list[FakePool] = []
    lock = threading.Lock()

    def new_record(**kwargs: Any) -> PoolRecord:
        pool = FakePool(str(kwargs["model_digest"]))
        with lock:
            pools.append(pool)
        barrier.wait(timeout=2.0)
        return record(kwargs, pool)

    monkeypatch.setattr(manager, "_new_record", new_record)
    output: list[Any] = []
    errors: list[BaseException] = []
    threads = [
        threading.Thread(
            target=acquire_once,
            args=(manager, model, registry, output, errors),
        )
        for model, registry in (first_files, second_files)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(2.0)

    assert errors == []
    assert len(output) == 2
    assert manager.stats()["startup_parallelism_peak"] == 2
    assert manager.stats()["created_pools"] == 2
    manager.close()
    assert all(pool.close_calls == 1 for pool in pools)


def test_creating_workers_count_against_license_capacity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first_files = files(tmp_path, "first")
    second_files = files(tmp_path, "second")
    manager = PoolManager(
        cache_path=tmp_path / "cache.sqlite3",
        license_slots=1,
        max_resident_cases=2,
    )
    entered = threading.Event()
    release = threading.Event()

    def new_record(**kwargs: Any) -> PoolRecord:
        entered.set()
        assert release.wait(2.0)
        return record(kwargs, FakePool("first"))

    monkeypatch.setattr(manager, "_new_record", new_record)
    output: list[Any] = []
    errors: list[BaseException] = []
    first = threading.Thread(
        target=acquire_once,
        args=(manager, *first_files, output, errors),
    )
    first.start()
    assert entered.wait(2.0)
    assert manager.stats()["creating_workers"] == 1
    with pytest.raises(RuntimeError, match="license budget"):
        with manager.acquire(
            backend_name="mock",
            model_path=second_files[0],
            registry_path=second_files[1],
            workers=1,
            visible=False,
        ):
            pass
    release.set()
    first.join(2.0)
    assert errors == []
    manager.close()


def test_creation_failure_wakes_all_same_case_waiters(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model, registry = files(tmp_path, "failure")
    manager = PoolManager(
        cache_path=tmp_path / "cache.sqlite3",
        license_slots=2,
        max_resident_cases=2,
    )
    entered = threading.Event()
    release = threading.Event()
    calls = 0

    def new_record(**kwargs: Any) -> PoolRecord:
        del kwargs
        nonlocal calls
        calls += 1
        entered.set()
        assert release.wait(2.0)
        raise RuntimeError("startup failed")

    monkeypatch.setattr(manager, "_new_record", new_record)
    output: list[Any] = []
    errors: list[BaseException] = []
    first = threading.Thread(target=acquire_once, args=(manager, model, registry, output, errors))
    second = threading.Thread(target=acquire_once, args=(manager, model, registry, output, errors))
    first.start()
    assert entered.wait(2.0)
    second.start()
    wait_for_stat(manager, "creation_waiters", 1)
    release.set()
    first.join(2.0)
    second.join(2.0)

    assert output == []
    assert calls == 1
    assert len(errors) == 2
    assert all(str(error) == "startup failed" for error in errors)
    assert manager.stats()["creation_failures"] == 1
    assert manager.stats()["creating_cases"] == 0
    manager.close()


def test_close_during_creation_closes_new_pool_and_unblocks_creator(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model, registry = files(tmp_path, "closing")
    manager = PoolManager(
        cache_path=tmp_path / "cache.sqlite3",
        license_slots=1,
        max_resident_cases=1,
    )
    entered = threading.Event()
    release = threading.Event()
    pool = FakePool("closing")

    def new_record(**kwargs: Any) -> PoolRecord:
        entered.set()
        assert release.wait(2.0)
        return record(kwargs, pool)

    monkeypatch.setattr(manager, "_new_record", new_record)
    output: list[Any] = []
    errors: list[BaseException] = []
    creator = threading.Thread(target=acquire_once, args=(manager, model, registry, output, errors))
    creator.start()
    assert entered.wait(2.0)
    close_errors: list[BaseException] = []

    def close_manager() -> None:
        try:
            manager.close()
        except BaseException as exc:
            close_errors.append(exc)

    closer = threading.Thread(target=close_manager)
    closer.start()
    release.set()
    creator.join(2.0)
    closer.join(2.0)

    assert output == []
    assert close_errors == []
    assert len(errors) == 1
    assert "closed while CasePool was starting" in str(errors[0])
    assert pool.close_calls == 1
    assert manager.stats()["resident_cases"] == 0
