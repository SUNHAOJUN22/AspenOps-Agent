import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from aspenops_nexus.cache import (
    CacheCorruptionError,
    CacheOwnershipError,
    CacheWaitTimeoutError,
    ResultCache,
)


def test_cache_roundtrip_stats_and_clear(tmp_path: Path) -> None:
    cache = ResultCache(tmp_path / "cache.sqlite3")
    cache.put("a", {"ok": True, "value": 3.0})
    assert cache.get("a") == {"ok": True, "value": 3.0}
    assert cache.get("missing") is None
    assert cache.stats() == {"entries": 1, "hits": 1}
    assert cache.clear() == 1
    assert cache.stats()["entries"] == 0


def test_ready_entries_are_immutable(tmp_path: Path) -> None:
    cache = ResultCache(tmp_path / "cache.sqlite3")
    cache.put("a", {"value": 1})
    cache.put("a", {"value": 1})
    with pytest.raises(CacheOwnershipError):
        cache.put("a", {"value": 2})


def test_only_one_cross_instance_owner_is_reserved(tmp_path: Path) -> None:
    path = tmp_path / "cache.sqlite3"
    first = ResultCache(path)
    second = ResultCache(path)

    with ThreadPoolExecutor(max_workers=2) as executor:
        reservations = list(
            executor.map(
                lambda item: item[0].reserve("condition", item[1], lease_seconds=60),
                [(first, "owner-a"), (second, "owner-b")],
            )
        )

    assert sorted(item.state for item in reservations) == ["OWNER", "WAIT"]


def test_owner_publishes_and_waiter_reads_verified_payload(tmp_path: Path) -> None:
    path = tmp_path / "cache.sqlite3"
    owner_cache = ResultCache(path)
    waiter_cache = ResultCache(path)
    assert owner_cache.reserve("condition", "owner", lease_seconds=60).state == "OWNER"
    assert waiter_cache.reserve("condition", "waiter", lease_seconds=60).state == "WAIT"

    owner_cache.publish("condition", "owner", {"ok": True, "value": 7.0})
    assert waiter_cache.wait_for_ready("condition", timeout_s=1.0) == {
        "ok": True,
        "value": 7.0,
    }
    assert waiter_cache.reserve("condition", "late", lease_seconds=60).state == "HIT"


def test_publish_requires_current_owner(tmp_path: Path) -> None:
    cache = ResultCache(tmp_path / "cache.sqlite3")
    cache.reserve("condition", "owner", lease_seconds=60)
    with pytest.raises(CacheOwnershipError):
        cache.publish("condition", "other", {"ok": True})


def test_stale_lease_can_be_taken_over(tmp_path: Path) -> None:
    cache = ResultCache(tmp_path / "cache.sqlite3")
    cache.reserve("condition", "stale", lease_seconds=0.001)
    time.sleep(0.01)
    assert cache.reserve("condition", "replacement", lease_seconds=60).state == "OWNER"
    with pytest.raises(CacheOwnershipError):
        cache.publish("condition", "stale", {"ok": True})
    cache.publish("condition", "replacement", {"ok": True})


def test_abandon_releases_pending_entry(tmp_path: Path) -> None:
    cache = ResultCache(tmp_path / "cache.sqlite3")
    cache.reserve("condition", "owner", lease_seconds=60)
    assert not cache.abandon("condition", "other")
    assert cache.abandon("condition", "owner")
    assert cache.reserve("condition", "next", lease_seconds=60).state == "OWNER"


def test_wait_timeout_uses_bounded_duration(tmp_path: Path) -> None:
    cache = ResultCache(tmp_path / "cache.sqlite3")
    cache.reserve("condition", "owner", lease_seconds=60)
    started = time.monotonic()
    with pytest.raises(CacheWaitTimeoutError):
        cache.wait_for_ready("condition", timeout_s=0.02, poll_s=0.005)
    elapsed = time.monotonic() - started
    assert 0.015 <= elapsed < 0.5


def test_payload_tampering_is_detected(tmp_path: Path) -> None:
    path = tmp_path / "cache.sqlite3"
    cache = ResultCache(path)
    cache.put("condition", {"ok": True})
    with sqlite3.connect(path) as connection:
        connection.execute(
            "UPDATE result_cache SET payload=? WHERE cache_key=?",
            ('{"ok":false}', "condition"),
        )
    with pytest.raises(CacheCorruptionError):
        cache.get("condition")


def test_legacy_cache_is_migrated_with_integrity_hashes(tmp_path: Path) -> None:
    path = tmp_path / "cache.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            CREATE TABLE result_cache (
                cache_key TEXT PRIMARY KEY,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                hit_count INTEGER NOT NULL DEFAULT 0,
                last_hit_at TEXT
            )
            """
        )
        connection.execute(
            "INSERT INTO result_cache(cache_key, payload, hit_count) VALUES(?, ?, ?)",
            ("legacy", '{"value":1}', 2),
        )

    cache = ResultCache(path)
    assert cache.get("legacy") == {"value": 1}
    assert cache.stats() == {"entries": 1, "hits": 3}
