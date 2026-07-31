from __future__ import annotations

import json
from typing import Any

import pytest

import aspenops_nexus.cache as cache_module
from aspenops_nexus.cache import ResultCache


def _legacy_encode(payload: dict[str, Any]) -> str:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def test_bulk_encoder_matches_legacy_bytes_and_constructs_once(monkeypatch: Any) -> None:
    payloads = {
        "one": {"z": 2, "a": "雪", "nested": [1, {"flag": True}]},
        "two": {"value": 3.5, "none": None},
        "three": {"mapping": {"b": 2, "a": 1}},
    }
    expected = {key: _legacy_encode(payload) for key, payload in payloads.items()}
    original = cache_module.json.JSONEncoder
    constructions = 0

    class CountingEncoder(original):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            nonlocal constructions
            constructions += 1
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(cache_module.json, "JSONEncoder", CountingEncoder)
    assert cache_module._encode_payloads(payloads) == expected
    assert constructions == 1


def test_bulk_encoder_rejects_nonfinite_payloads() -> None:
    with pytest.raises(ValueError, match="Out of range float values"):
        cache_module._encode_payloads({"bad": {"value": float("nan")}})


def test_put_many_preserves_roundtrip_and_compact_memory_bytes(tmp_path: Any) -> None:
    cache = ResultCache(tmp_path / "cache.sqlite3")
    payloads = {
        f"key-{index}": {
            "index": index,
            "unicode": "聚丙烯",
            "nested": {"values": [index, index + 1]},
        }
        for index in range(20)
    }
    cache.put_many(payloads)

    assert cache.get_many(list(payloads)) == payloads
    assert cache.stats()["entries"] == len(payloads)
    assert cache._memory["key-0"] == _legacy_encode(payloads["key-0"])
