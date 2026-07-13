from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import closing
from pathlib import Path
from typing import Any


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

    def get(self, key: str) -> dict[str, Any] | None:
        with self._lock, closing(self._connect()) as connection, connection:
            row = connection.execute(
                "SELECT payload FROM result_cache WHERE cache_key = ?", (key,)
            ).fetchone()
            if row is not None:
                connection.execute(
                    """
                    UPDATE result_cache
                    SET hit_count = hit_count + 1, last_hit_at = CURRENT_TIMESTAMP
                    WHERE cache_key = ?
                    """,
                    (key,),
                )
        return None if row is None else json.loads(str(row[0]))

    def put(self, key: str, payload: dict[str, Any]) -> None:
        encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, allow_nan=False)
        with self._lock, closing(self._connect()) as connection, connection:
            connection.execute(
                """
                INSERT INTO result_cache(cache_key, payload)
                VALUES (?, ?)
                ON CONFLICT(cache_key) DO UPDATE SET payload=excluded.payload
                """,
                (key, encoded),
            )

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
