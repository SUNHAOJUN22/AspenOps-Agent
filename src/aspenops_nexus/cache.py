from __future__ import annotations

import json
import sqlite3
import threading
from collections import Counter, OrderedDict
from contextlib import closing
from pathlib import Path
from typing import Any

_SQLITE_PARAMETER_BATCH = 900
_MEMORY_MAX_ENTRIES = 4096
_HIT_FLUSH_THRESHOLD = 1024


def _chunks(values: list[str], size: int = _SQLITE_PARAMETER_BATCH) -> list[list[str]]:
    return [values[index : index + size] for index in range(0, len(values), size)]


class ResultCache:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._memory: OrderedDict[str, str] = OrderedDict()
        self._pending_hits: Counter[str] = Counter()
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
            [(count, key) for key, count in self._pending_hits.items()],
        )
        self._pending_hits.clear()

    def _flush_hits_if_needed(self) -> None:
        if sum(self._pending_hits.values()) < _HIT_FLUSH_THRESHOLD:
            return
        with closing(self._connect()) as connection, connection:
            self._flush_hits(connection)

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
            self._pending_hits.update({key: counts[key] for key in encoded})
            self._flush_hits_if_needed()
            return {key: json.loads(payload) for key, payload in encoded.items()}

    def get(self, key: str) -> dict[str, Any] | None:
        return self.get_many([key]).get(key)

    def put_many(self, payloads: dict[str, dict[str, Any]]) -> None:
        if not payloads:
            return
        encoded_payloads = {
            key: json.dumps(payload, sort_keys=True, ensure_ascii=False, allow_nan=False)
            for key, payload in payloads.items()
        }
        rows = list(encoded_payloads.items())
        with self._lock, closing(self._connect()) as connection, connection:
            self._flush_hits(connection)
            connection.executemany(
                """
                INSERT INTO result_cache(cache_key, payload)
                VALUES (?, ?)
                ON CONFLICT(cache_key) DO UPDATE SET payload=excluded.payload
                """,
                rows,
            )
            for key, encoded in encoded_payloads.items():
                self._remember(key, encoded)

    def put(self, key: str, payload: dict[str, Any]) -> None:
        self.put_many({key: payload})

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
