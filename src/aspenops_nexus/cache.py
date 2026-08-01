from __future__ import annotations

import json
import sqlite3
import threading
from collections import Counter, OrderedDict
from collections.abc import Iterator
from contextlib import closing
from pathlib import Path
from typing import Any

_SQLITE_PARAMETER_BATCH = 900
_MEMORY_MAX_ENTRIES = 4096
_HIT_FLUSH_THRESHOLD = 1024


def _chunks(values: list[str], size: int = _SQLITE_PARAMETER_BATCH) -> Iterator[list[str]]:
    for index in range(0, len(values), size):
        yield values[index : index + size]


def _encode_payloads(payloads: dict[str, dict[str, Any]]) -> dict[str, str]:
    encode = json.JSONEncoder(
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode
    return {key: encode(payload) for key, payload in payloads.items()}


class ResultCache:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._memory: OrderedDict[str, str] = OrderedDict()
        self._pending_hits: Counter[str] = Counter()
        self._pending_hit_total = 0
        with closing(self._connect()) as connection, connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA synchronous=NORMAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS result_cache (
                    cache_key TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    hit_count INTEGER NOT NULL DEFAULT 0,
                    last_hit_at TEXT
                )
                """
            )
            connection.execute("PRAGMA optimize")

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.execute("PRAGMA busy_timeout=30000")
        return connection

    def _remember(self, key: str, encoded: str) -> None:
        self._memory[key] = encoded
        self._memory.move_to_end(key)
        while len(self._memory) > _MEMORY_MAX_ENTRIES:
            self._memory.popitem(last=False)

    def _flush_hits(self, connection: sqlite3.Connection) -> None:
        if not self._pending_hits:
            return
        connection.executemany(
            """
            UPDATE result_cache
            SET hit_count = hit_count + ?, last_hit_at = CURRENT_TIMESTAMP
            WHERE cache_key = ?
            """,
            ((count, key) for key, count in self._pending_hits.items()),
        )
        self._pending_hits.clear()
        self._pending_hit_total = 0

    def _flush_hits_if_needed(self) -> None:
        if self._pending_hit_total < _HIT_FLUSH_THRESHOLD:
            return
        with closing(self._connect()) as connection, connection:
            self._flush_hits(connection)

    def _discard(self, keys: list[str]) -> None:
        if not keys:
            return
        with closing(self._connect()) as connection, connection:
            for batch in _chunks(keys):
                placeholders = ",".join("?" for _ in batch)
                connection.execute(
                    f"DELETE FROM result_cache WHERE cache_key IN ({placeholders})",
                    batch,
                )
        for key in keys:
            self._memory.pop(key, None)
            self._pending_hit_total -= self._pending_hits.pop(key, 0)
        self._pending_hit_total = max(0, self._pending_hit_total)

    def get_many(self, keys: list[str]) -> dict[str, dict[str, Any]]:
        if not keys:
            return {}
        counts = Counter(keys)
        unique_keys = list(counts)
        encoded: dict[str, str] = {}
        with self._lock:
            missing: list[str] = []
            for key in unique_keys:
                memory_payload = self._memory.get(key)
                if memory_payload is None:
                    missing.append(key)
                else:
                    self._memory.move_to_end(key)
                    encoded[key] = memory_payload
            if missing:
                with closing(self._connect()) as connection:
                    for batch in _chunks(missing):
                        placeholders = ",".join("?" for _ in batch)
                        rows = connection.execute(
                            "SELECT cache_key, payload FROM result_cache "
                            f"WHERE cache_key IN ({placeholders})",
                            batch,
                        ).fetchall()
                        for row in rows:
                            key = str(row[0])
                            payload = str(row[1])
                            encoded[key] = payload
                            self._remember(key, payload)

            decoded: dict[str, dict[str, Any]] = {}
            corrupt: list[str] = []
            for key, payload in encoded.items():
                try:
                    value = json.loads(payload)
                except json.JSONDecodeError:
                    corrupt.append(key)
                    continue
                if not isinstance(value, dict):
                    corrupt.append(key)
                    continue
                decoded[key] = {str(name): item for name, item in value.items()}

            self._discard(corrupt)
            for key in decoded:
                count = counts[key]
                self._pending_hits[key] += count
                self._pending_hit_total += count
            self._flush_hits_if_needed()
            return decoded

    def get(self, key: str) -> dict[str, Any] | None:
        return self.get_many([key]).get(key)

    def put_many(self, payloads: dict[str, dict[str, Any]]) -> None:
        if not payloads:
            return
        encoded_payloads = _encode_payloads(payloads)
        with self._lock, closing(self._connect()) as connection, connection:
            self._flush_hits(connection)
            connection.executemany(
                """
                INSERT INTO result_cache(cache_key, payload)
                VALUES (?, ?)
                ON CONFLICT(cache_key) DO UPDATE SET payload=excluded.payload
                """,
                encoded_payloads.items(),
            )
            for key, encoded in encoded_payloads.items():
                self._remember(key, encoded)

    def put(self, key: str, payload: dict[str, Any]) -> None:
        self.put_many({key: payload})

    def close(self) -> None:
        """Persist pending hit accounting; cache connections remain operation-scoped."""
        with self._lock:
            if not self._pending_hits:
                return
            with closing(self._connect()) as connection, connection:
                self._flush_hits(connection)

    def stats(self) -> dict[str, int]:
        with self._lock, closing(self._connect()) as connection, connection:
            self._flush_hits(connection)
            row = connection.execute(
                "SELECT COUNT(*), COALESCE(SUM(hit_count), 0) FROM result_cache"
            ).fetchone()
        return {"entries": int(row[0]), "hits": int(row[1])}

    def clear(self) -> int:
        with self._lock, closing(self._connect()) as connection, connection:
            self._flush_hits(connection)
            cursor = connection.execute("DELETE FROM result_cache")
            self._memory.clear()
            return int(cursor.rowcount)
