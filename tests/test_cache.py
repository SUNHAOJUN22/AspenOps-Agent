from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from aspenops_nexus.cache import ResultCache


def test_cache_roundtrip_stats_and_clear(tmp_path: Path) -> None:
    cache = ResultCache(tmp_path / "cache.sqlite3")
    cache.put("a", {"ok": True, "value": 3.0})
    assert cache.get("a") == {"ok": True, "value": 3.0}
    assert cache.get("missing") is None
    assert cache.stats() == {"entries": 1, "hits": 1}
    assert cache.clear() == 1
    assert cache.stats()["entries"] == 0


def test_bulk_cache_counts_duplicate_hits_and_isolates_returned_values(tmp_path: Path) -> None:
    cache = ResultCache(tmp_path / "cache.sqlite3")
    payload = {"value": {"nested": 1}}
    cache.put_many(
        {
            "a": payload,
            "b": {"value": 2},
        }
    )
    payload["value"]["nested"] = 88

    loaded = cache.get_many(["a", "a", "b", "missing"])

    assert loaded == {
        "a": {"value": {"nested": 1}},
        "b": {"value": 2},
    }
    loaded["a"]["value"]["nested"] = 99
    assert cache.get("a") == {"value": {"nested": 1}}
    assert cache.stats() == {"entries": 2, "hits": 4}


def test_memory_hits_skip_json_decode_and_sqlite_connection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache = ResultCache(tmp_path / "cache.sqlite3")
    cache.put("a", {"value": {"nested": 1}})
    decode_calls = 0
    original_loads = json.loads

    def counted_loads(value: str, *args: Any, **kwargs: Any) -> Any:
        nonlocal decode_calls
        decode_calls += 1
        return original_loads(value, *args, **kwargs)

    def forbidden_connect() -> sqlite3.Connection:
        raise AssertionError("memory cache hit must not open SQLite")

    monkeypatch.setattr("aspenops_nexus.cache.json.loads", counted_loads)
    monkeypatch.setattr(cache, "_connect", forbidden_connect)

    loaded = cache.get_many(["a", "a"])
    assert loaded == {"a": {"value": {"nested": 1}}}
    assert decode_calls == 0


def test_database_payload_decodes_once_then_stays_structured_in_memory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "cache.sqlite3"
    ResultCache(path).put("a", {"value": {"nested": 1}})
    cache = ResultCache(path)
    decode_calls = 0
    original_loads = json.loads

    def counted_loads(value: str, *args: Any, **kwargs: Any) -> Any:
        nonlocal decode_calls
        decode_calls += 1
        return original_loads(value, *args, **kwargs)

    monkeypatch.setattr("aspenops_nexus.cache.json.loads", counted_loads)

    first = cache.get_many(["a", "a"])
    first["a"]["value"]["nested"] = 99
    second = cache.get("a")

    assert second == {"value": {"nested": 1}}
    assert decode_calls == 1


def test_bulk_cache_chunks_queries_beyond_sqlite_parameter_limit(tmp_path: Path) -> None:
    path = tmp_path / "cache.sqlite3"
    payloads = {f"key-{index}": {"index": index} for index in range(905)}
    ResultCache(path).put_many(payloads)

    reopened = ResultCache(path)
    loaded = reopened.get_many(list(payloads))

    assert len(loaded) == 905
    assert loaded["key-0"] == {"index": 0}
    assert loaded["key-904"] == {"index": 904}
    assert reopened.stats() == {"entries": 905, "hits": 905}


def test_hit_flush_threshold_uses_constant_time_total(tmp_path: Path) -> None:
    path = tmp_path / "cache.sqlite3"
    payloads = {f"key-{index}": {"index": index} for index in range(1024)}
    cache = ResultCache(path)
    cache.put_many(payloads)

    assert cache.get_many(list(payloads)) == payloads
    assert cache._pending_hit_total == 0
    assert not cache._pending_hits
    assert cache.stats() == {"entries": 1024, "hits": 1024}


def test_pending_hit_total_tracks_discard_and_explicit_flush(tmp_path: Path) -> None:
    path = tmp_path / "cache.sqlite3"
    cache = ResultCache(path)
    cache.put_many({"a": {"value": 1}, "b": {"value": 2}})

    assert cache.get_many(["a", "a", "b"]) == {
        "a": {"value": 1},
        "b": {"value": 2},
    }
    assert cache._pending_hit_total == 3
    cache._discard(["a"])
    assert cache._pending_hit_total == 1
    assert cache.stats() == {"entries": 1, "hits": 1}
    assert cache._pending_hit_total == 0


def test_cache_persists_compact_json(tmp_path: Path) -> None:
    path = tmp_path / "cache.sqlite3"
    cache = ResultCache(path)
    payload = {"ok": True, "nested": {"value": 3}}
    cache.put("a", payload)

    with sqlite3.connect(path) as connection:
        encoded = str(
            connection.execute(
                "SELECT payload FROM result_cache WHERE cache_key = ?",
                ("a",),
            ).fetchone()[0]
        )

    assert ": " not in encoded
    assert ", " not in encoded
    assert json.loads(encoded) == payload


def test_corrupted_cache_entries_are_removed_without_poisoning_valid_hits(tmp_path: Path) -> None:
    path = tmp_path / "cache.sqlite3"
    cache = ResultCache(path)
    cache.put("good", {"ok": True, "value": 7})
    with sqlite3.connect(path) as connection:
        connection.executemany(
            "INSERT INTO result_cache(cache_key, payload) VALUES (?, ?)",
            [
                ("invalid-json", "{not-json"),
                ("wrong-shape", "[1, 2, 3]"),
            ],
        )

    assert cache.get_many(["good", "good", "invalid-json", "wrong-shape"]) == {
        "good": {"ok": True, "value": 7}
    }
    assert cache.get("invalid-json") is None
    assert cache.get("wrong-shape") is None
    assert cache.stats() == {"entries": 1, "hits": 2}
