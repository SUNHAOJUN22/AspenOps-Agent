from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import closing, contextmanager
from pathlib import Path
from typing import Any

import pytest

from aspenops_nexus.cache import ResultCache


class CommitFailure(sqlite3.Connection):
    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> bool:
        if exc_type is None:
            self.rollback()
            raise sqlite3.OperationalError("injected commit failure")
        return bool(super().__exit__(exc_type, exc, traceback))


@contextmanager
def failing_connection(cache: ResultCache) -> Iterator[sqlite3.Connection]:
    # Explicit test ownership complements production operation-scoped closing.
    with closing(sqlite3.connect(cache.path, factory=CommitFailure)) as connection:
        yield connection


@pytest.mark.parametrize("existing", [False, True])
def test_rolled_back_payload_never_becomes_a_memory_hit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, existing: bool
) -> None:
    cache = ResultCache(tmp_path / "cache.sqlite3")
    if existing:
        cache.put("key", {"value": "committed"})
    with failing_connection(cache) as connection, monkeypatch.context() as scoped:
        scoped.setattr(cache, "_connect", lambda: connection)
        with pytest.raises(sqlite3.OperationalError, match="commit failure"):
            cache.put_many({"key": {"value": "rolled-back"}, "other": {"value": 2}})
    expected = {"value": "committed"} if existing else None
    assert cache.get("key") == expected
    assert cache.get("other") is None
    fresh = ResultCache(cache.path)
    assert fresh.get("key") == expected
    assert fresh.get("other") is None
    cache.close()
    fresh.close()


@pytest.mark.parametrize("operation", ["put", "stats", "close", "clear", "flush"])
def test_rolled_back_hit_accounting_remains_retryable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, operation: str
) -> None:
    cache = ResultCache(tmp_path / "cache.sqlite3")
    cache.put("key", {"value": 1})
    assert cache.get("key") == {"value": 1}
    before = dict(cache._memory)
    with failing_connection(cache) as connection, monkeypatch.context() as scoped:
        scoped.setattr(cache, "_connect", lambda: connection)
        with pytest.raises(sqlite3.OperationalError, match="commit failure"):
            if operation == "put":
                cache.put("other", {"value": 2})
            elif operation == "flush":
                scoped.setattr("aspenops_nexus.cache._HIT_FLUSH_THRESHOLD", 1)
                cache._flush_hits_if_needed()
            else:
                getattr(cache, operation)()
    assert cache._pending_hits == {"key": 1}
    assert cache._pending_hit_total == 1
    assert dict(cache._memory) == before
    assert cache.stats() == {"entries": 1, "hits": 1}
    assert cache.stats() == {"entries": 1, "hits": 1}
    cache.close()


def test_successful_clear_commits_before_discarding_memory(tmp_path: Path) -> None:
    cache = ResultCache(tmp_path / "cache.sqlite3")
    cache.put("key", {"value": 1})
    cache.get("key")
    assert cache.clear() == 1
    assert cache.get("key") is None
    assert not cache._memory
    assert not cache._pending_hits
    assert cache.stats() == {"entries": 0, "hits": 0}
    cache.close()
