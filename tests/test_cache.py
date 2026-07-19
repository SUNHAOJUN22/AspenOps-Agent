import sqlite3
from pathlib import Path

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
    cache.put_many(
        {
            "a": {"value": {"nested": 1}},
            "b": {"value": 2},
        }
    )

    loaded = cache.get_many(["a", "a", "b", "missing"])

    assert loaded == {
        "a": {"value": {"nested": 1}},
        "b": {"value": 2},
    }
    loaded["a"]["value"]["nested"] = 99
    assert cache.get("a") == {"value": {"nested": 1}}
    assert cache.stats() == {"entries": 2, "hits": 4}


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
