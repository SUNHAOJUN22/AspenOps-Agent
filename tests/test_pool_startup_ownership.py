from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

import aspenops_nexus.pool as pool_module
from aspenops_nexus.pool import CasePool
from aspenops_nexus.worker import WorkerHandle

ROOT = Path(__file__).resolve().parents[1]


class CancelledStartup(BaseException):
    pass


@pytest.fixture
def pool(tmp_path: Path) -> Any:
    instance = CasePool(
        backend_name="mock",
        model_path=ROOT / "src/aspenops_nexus/data/mock-case.json",
        registry_path=ROOT / "src/aspenops_nexus/data/node-registry.json",
        workers=2,
        visible=False,
        cache_path=tmp_path / "cache.sqlite3",
    )
    yield instance
    instance._handles.clear()
    instance.cache.close()


def handle(pool: CasePool, worker_id: int) -> WorkerHandle:
    placeholder: Any = object()
    return WorkerHandle(
        worker_id=worker_id,
        process=placeholder,
        connection=placeholder,
        staged_model=pool.model_path,
        runtime={"backend": "mock"},
        model_sha256=pool.model_sha256,
        registry_sha256=pool.registry_sha256,
    )


@pytest.mark.parametrize("invalid_index", [0, 1])
def test_startup_owns_handle_before_identity_validation(
    pool: CasePool, monkeypatch: pytest.MonkeyPatch, invalid_index: int
) -> None:
    created: list[WorkerHandle] = []
    stopped: list[WorkerHandle] = []

    def create(worker_id: int) -> WorkerHandle:
        new = handle(pool, worker_id)
        if worker_id == invalid_index:
            new.model_sha256 = "0" * 64
        created.append(new)
        return new

    monkeypatch.setattr(pool, "_new_handle", create)
    monkeypatch.setattr(pool_module, "stop_worker", stopped.append)
    with pytest.raises(RuntimeError, match="model snapshot"):
        pool.start()
    assert stopped == created
    assert not pool._handles


def test_cancelled_second_startup_releases_first_worker(
    pool: CasePool, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = handle(pool, 0)
    stopped: list[WorkerHandle] = []

    def create(worker_id: int) -> WorkerHandle:
        if worker_id == 1:
            raise CancelledStartup("cancelled")
        return first

    monkeypatch.setattr(pool, "_new_handle", create)
    monkeypatch.setattr(pool_module, "stop_worker", stopped.append)
    with pytest.raises(CancelledStartup, match="cancelled"):
        pool.start()
    assert stopped == [first]
    assert not pool._handles


def test_cancelled_replacement_validation_aborts_new_worker(
    pool: CasePool, monkeypatch: pytest.MonkeyPatch
) -> None:
    previous = handle(pool, 0)
    replacement = handle(pool, 0)
    pool._handles = [previous]
    stopped: list[WorkerHandle] = []
    aborted: list[WorkerHandle] = []

    def validate(candidate: WorkerHandle) -> None:
        assert candidate is replacement
        raise CancelledStartup("cancelled")

    monkeypatch.setattr(pool, "_new_handle", lambda worker_id: replacement)
    monkeypatch.setattr(pool, "_assert_handle_identity", validate)
    monkeypatch.setattr(pool_module, "stop_worker", stopped.append)
    monkeypatch.setattr(pool_module, "abort_worker", aborted.append)
    with pytest.raises(CancelledStartup, match="cancelled"):
        pool._replace(0)
    assert stopped == [previous]
    assert aborted == [replacement]
    assert pool._handles == [previous]
