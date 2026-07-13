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
