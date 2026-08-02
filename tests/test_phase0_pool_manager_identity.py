from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

import aspenops_nexus.pool_manager as pool_manager_module
from aspenops_nexus.pool_manager import PoolManager


class MismatchedPool:
    def __init__(self, **kwargs: Any) -> None:
        del kwargs
        self.model_sha256 = "b" * 64
        self.registry_sha256 = "c" * 64
        self.closed = False

    def start(self) -> None:
        return None

    def close(self) -> None:
        self.closed = True

    def _runtime_cache_identity(self) -> dict[str, Any]:
        return {"backend": "mock"}


def test_pool_manager_rejects_casepool_digest_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model = tmp_path / "model.json"
    registry = tmp_path / "registry.json"
    model.write_text('{"model": 1}', encoding="utf-8")
    registry.write_text('{"registry": 1}', encoding="utf-8")
    created: list[MismatchedPool] = []

    def create_pool(**kwargs: Any) -> MismatchedPool:
        pool = MismatchedPool(**kwargs)
        created.append(pool)
        return pool

    monkeypatch.setattr(pool_manager_module, "CasePool", create_pool)
    manager = PoolManager(
        cache_path=tmp_path / "cache.sqlite3",
        license_slots=1,
    )
    try:
        with pytest.raises(RuntimeError, match="changed between PoolManager"):
            with manager.acquire(
                backend_name="mock",
                model_path=model,
                registry_path=registry,
                workers=1,
                visible=False,
            ):
                pytest.fail("mismatched pool must not be leased")
    finally:
        manager.close()
    assert created and created[0].closed is True
