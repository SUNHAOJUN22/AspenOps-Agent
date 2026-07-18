from __future__ import annotations

import json
import sqlite3
import threading
from collections import Counter
from contextlib import closing
from pathlib import Path
from typing import Any

_SQLITE_PARAMETER_BATCH = 900


def _chunks(values: list[str], size: int = _SQLITE_PARAMETER_BATCH) -> list[list[str]]:
    return [values[index : index + size] for index in range(0, len(values), size)]


class ResultCache:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
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

    def get_many(self, keys: list[str]) -> dict[str, dict[str, Any]]:
        if not keys:
            return {}
        counts = Counter(keys)
        unique_keys = list(counts)
        encoded: dict[str, str] = {}
        with self._lock, closing(self._connect()) as connection, connection:
            for batch in _chunks(unique_keys):
                placeholders = ",".join("?" for _ in batch)
                rows = connection.execute(
                    f"SELECT cache_key, payload FROM result_cache WHERE cache_key IN ({placeholders})",
                    batch,
                ).fetchall()
                encoded.update((str(row[0]), str(row[1])) for row in rows)
            if encoded:
                connection.executemany(
                    """
                    UPDATE result_cache
                    SET hit_count = hit_count + ?, last_hit_at = CURRENT_TIMESTAMP
                    WHERE cache_key = ?
                    """,
                    [(counts[key], key) for key in encoded],
                )
        return {key: json.loads(payload) for key, payload in encoded.items()}

    def get(self, key: str) -> dict[str, Any] | None:
        return self.get_many([key]).get(key)

    def put_many(self, payloads: dict[str, dict[str, Any]]) -> None:
        if not payloads:
            return
        rows = [
            (
                key,
                json.dumps(payload, sort_keys=True, ensure_ascii=False, allow_nan=False),
            )
            for key, payload in payloads.items()
        ]
        with self._lock, closing(self._connect()) as connection, connection:
            connection.executemany(
                """
                INSERT INTO result_cache(cache_key, payload)
                VALUES (?, ?)
                ON CONFLICT(cache_key) DO UPDATE SET payload=excluded.payload
                """,
                rows,
            )

    def put(self, key: str, payload: dict[str, Any]) -> None:
        self.put_many({key: payload})

    def stats(self) -> dict[str, int]:
        with self._lock, closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT COUNT(*), COALESCE(SUM(hit_count), 0) FROM result_cache"
            ).fetchone()
        return {"entries": int(row[0]), "hits": int(row[1])}

    def clear(self) -> int:
        with self._lock, closing(self._connect()) as connection, connection:
            cursor = connection.execute("DELETE FROM result_cache")
            return int(cursor.rowcount)
