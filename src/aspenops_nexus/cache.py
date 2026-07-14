from __future__ import annotations

import json
import math
import sqlite3
import threading
import time
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from .hashing import canonical_hash

_CACHE_SCHEMA_VERSION = 1
_CACHE_STATES = ("PENDING", "READY", "CORRUPT")
ReservationState = Literal["HIT", "OWNER", "WAIT"]


class CacheError(RuntimeError):
    pass


class CacheCorruptionError(CacheError):
    pass


class CacheOwnershipError(CacheError):
    pass


class CacheWaitTimeoutError(TimeoutError, CacheError):
    pass


@dataclass(frozen=True, slots=True)
class CacheReservation:
    state: ReservationState
    payload: dict[str, Any] | None = None
    lease_expires_at: float | None = None


class ResultCache:
    """SQLite-backed immutable result cache with cross-process single-flight leases.

    Lease timestamps use Unix time because independent processes need a shared clock domain. Local
    wait durations use ``time.monotonic()`` so wall-clock changes cannot extend a request deadline.
    """

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._initialize_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.execute("PRAGMA busy_timeout=30000")
        return connection

    def _initialize_schema(self) -> None:
        with self._lock, closing(self._connect()) as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA synchronous=NORMAL")
            connection.execute("BEGIN IMMEDIATE")
            try:
                columns = {
                    str(row[1])
                    for row in connection.execute("PRAGMA table_info(result_cache)").fetchall()
                }
                if columns and "state" not in columns:
                    self._migrate_legacy_schema(connection, columns)
                else:
                    self._create_schema(connection)
                connection.execute(f"PRAGMA user_version={_CACHE_SCHEMA_VERSION}")
                connection.commit()
            except Exception:
                connection.rollback()
                raise

    @staticmethod
    def _create_schema(connection: sqlite3.Connection) -> None:
        states = ",".join(f"'{state}'" for state in _CACHE_STATES)
        connection.execute(
            f"""
            CREATE TABLE IF NOT EXISTS result_cache (
                cache_key TEXT PRIMARY KEY,
                state TEXT NOT NULL CHECK(state IN ({states})),
                payload TEXT,
                payload_hash TEXT,
                owner_token TEXT,
                lease_expires_at REAL,
                schema_version INTEGER NOT NULL DEFAULT 1 CHECK(schema_version > 0),
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                hit_count INTEGER NOT NULL DEFAULT 0 CHECK(hit_count >= 0),
                last_hit_at REAL,
                CHECK(
                    (state='PENDING' AND payload IS NULL AND payload_hash IS NULL
                     AND owner_token IS NOT NULL AND lease_expires_at IS NOT NULL)
                    OR
                    (state='READY' AND payload IS NOT NULL AND payload_hash IS NOT NULL
                     AND owner_token IS NULL AND lease_expires_at IS NULL)
                    OR
                    (state='CORRUPT')
                )
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_result_cache_pending ON result_cache(state, lease_expires_at)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_result_cache_eviction ON result_cache(state, last_hit_at, created_at)"
        )

    def _migrate_legacy_schema(self, connection: sqlite3.Connection, columns: set[str]) -> None:
        expected = {"cache_key", "payload", "created_at", "hit_count", "last_hit_at"}
        if not expected.issubset(columns):
            raise CacheError("Unrecognized legacy cache schema; refusing destructive migration")
        rows = connection.execute(
            "SELECT cache_key, payload, hit_count FROM result_cache"
        ).fetchall()
        connection.execute("ALTER TABLE result_cache RENAME TO result_cache_legacy_v0")
        self._create_schema(connection)
        now = time.time()
        for key, encoded, hit_count in rows:
            try:
                payload = json.loads(str(encoded))
                if not isinstance(payload, dict):
                    raise TypeError("cached payload must be an object")
                payload_hash = canonical_hash(payload)
            except (json.JSONDecodeError, TypeError, ValueError):
                connection.execute(
                    """
                    INSERT INTO result_cache(
                        cache_key, state, schema_version, created_at, updated_at, hit_count
                    ) VALUES(?, 'CORRUPT', ?, ?, ?, ?)
                    """,
                    (str(key), _CACHE_SCHEMA_VERSION, now, now, max(0, int(hit_count))),
                )
                continue
            connection.execute(
                """
                INSERT INTO result_cache(
                    cache_key, state, payload, payload_hash, schema_version,
                    created_at, updated_at, hit_count
                ) VALUES(?, 'READY', ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(key),
                    json.dumps(payload, sort_keys=True, ensure_ascii=False, allow_nan=False),
                    payload_hash,
                    _CACHE_SCHEMA_VERSION,
                    now,
                    now,
                    max(0, int(hit_count)),
                ),
            )
        connection.execute("DROP TABLE result_cache_legacy_v0")

    @staticmethod
    def _validate_key_owner(key: str, owner_token: str) -> None:
        if not key.strip():
            raise ValueError("cache key must not be blank")
        if not owner_token.strip():
            raise ValueError("cache owner token must not be blank")

    @staticmethod
    def _encode_payload(payload: dict[str, Any]) -> tuple[str, str]:
        encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, allow_nan=False)
        return encoded, canonical_hash(payload)

    @staticmethod
    def _decode_verified(
        key: str, encoded: str | None, expected_hash: str | None
    ) -> dict[str, Any]:
        if encoded is None or expected_hash is None:
            raise CacheCorruptionError(f"Cache entry {key!r} is missing payload integrity data")
        try:
            payload = json.loads(encoded)
        except json.JSONDecodeError as exc:
            raise CacheCorruptionError(f"Cache entry {key!r} contains malformed JSON") from exc
        if not isinstance(payload, dict):
            raise CacheCorruptionError(f"Cache entry {key!r} payload is not a JSON object")
        if canonical_hash(payload) != expected_hash:
            raise CacheCorruptionError(f"Cache entry {key!r} failed payload hash verification")
        return payload

    def reserve(self, key: str, owner_token: str, lease_seconds: float) -> CacheReservation:
        self._validate_key_owner(key, owner_token)
        if not math.isfinite(lease_seconds) or lease_seconds <= 0.0:
            raise ValueError("cache lease_seconds must be finite and positive")
        now = time.time()
        lease_expires_at = now + lease_seconds
        with self._lock, closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                row = connection.execute(
                    """
                    SELECT state, payload, payload_hash, owner_token, lease_expires_at
                    FROM result_cache WHERE cache_key=?
                    """,
                    (key,),
                ).fetchone()
                if row is None:
                    connection.execute(
                        """
                        INSERT INTO result_cache(
                            cache_key, state, owner_token, lease_expires_at,
                            schema_version, created_at, updated_at
                        ) VALUES(?, 'PENDING', ?, ?, ?, ?, ?)
                        """,
                        (
                            key,
                            owner_token,
                            lease_expires_at,
                            _CACHE_SCHEMA_VERSION,
                            now,
                            now,
                        ),
                    )
                    connection.commit()
                    return CacheReservation("OWNER", lease_expires_at=lease_expires_at)
                state = str(row[0])
                if state == "READY":
                    payload = self._decode_verified(key, row[1], row[2])
                    connection.execute(
                        """
                        UPDATE result_cache
                        SET hit_count=hit_count+1, last_hit_at=?, updated_at=?
                        WHERE cache_key=? AND state='READY'
                        """,
                        (now, now, key),
                    )
                    connection.commit()
                    return CacheReservation("HIT", payload=payload)
                if state == "CORRUPT":
                    raise CacheCorruptionError(f"Cache entry {key!r} is marked corrupt")
                current_lease = float(row[4])
                if current_lease <= now:
                    cursor = connection.execute(
                        """
                        UPDATE result_cache
                        SET owner_token=?, lease_expires_at=?, updated_at=?
                        WHERE cache_key=? AND state='PENDING' AND lease_expires_at<=?
                        """,
                        (owner_token, lease_expires_at, now, key, now),
                    )
                    if cursor.rowcount != 1:
                        raise CacheOwnershipError(
                            f"Cache lease takeover race for {key!r}; reservation must be retried"
                        )
                    connection.commit()
                    return CacheReservation("OWNER", lease_expires_at=lease_expires_at)
                connection.commit()
                return CacheReservation("WAIT", lease_expires_at=current_lease)
            except Exception:
                connection.rollback()
                raise

    def publish(self, key: str, owner_token: str, payload: dict[str, Any]) -> None:
        self._validate_key_owner(key, owner_token)
        encoded, payload_hash = self._encode_payload(payload)
        now = time.time()
        with self._lock, closing(self._connect()) as connection, connection:
            cursor = connection.execute(
                """
                UPDATE result_cache
                SET state='READY', payload=?, payload_hash=?, owner_token=NULL,
                    lease_expires_at=NULL, updated_at=?
                WHERE cache_key=? AND state='PENDING' AND owner_token=?
                """,
                (encoded, payload_hash, now, key, owner_token),
            )
            if cursor.rowcount != 1:
                raise CacheOwnershipError(
                    f"Cache entry {key!r} cannot be published by owner {owner_token!r}"
                )

    def abandon(self, key: str, owner_token: str) -> bool:
        self._validate_key_owner(key, owner_token)
        with self._lock, closing(self._connect()) as connection, connection:
            cursor = connection.execute(
                """
                DELETE FROM result_cache
                WHERE cache_key=? AND state='PENDING' AND owner_token=?
                """,
                (key, owner_token),
            )
            return cursor.rowcount == 1

    def wait_for_ready(
        self, key: str, timeout_s: float, poll_s: float = 0.05
    ) -> dict[str, Any] | None:
        if not key.strip():
            raise ValueError("cache key must not be blank")
        if not math.isfinite(timeout_s) or timeout_s <= 0.0:
            raise ValueError("cache wait timeout must be finite and positive")
        if not math.isfinite(poll_s) or poll_s <= 0.0:
            raise ValueError("cache poll interval must be finite and positive")
        deadline = time.monotonic() + timeout_s
        while True:
            now_wall = time.time()
            with self._lock, closing(self._connect()) as connection:
                row = connection.execute(
                    """
                    SELECT state, payload, payload_hash, lease_expires_at
                    FROM result_cache WHERE cache_key=?
                    """,
                    (key,),
                ).fetchone()
            if row is None:
                return None
            state = str(row[0])
            if state == "READY":
                return self.get(key)
            if state == "CORRUPT":
                raise CacheCorruptionError(f"Cache entry {key!r} is marked corrupt")
            if float(row[3]) <= now_wall:
                return None
            remaining = deadline - time.monotonic()
            if remaining <= 0.0:
                raise CacheWaitTimeoutError(f"Timed out waiting for cache entry {key!r}")
            time.sleep(min(poll_s, remaining))

    def get(self, key: str) -> dict[str, Any] | None:
        if not key.strip():
            raise ValueError("cache key must not be blank")
        now = time.time()
        with self._lock, closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                row = connection.execute(
                    """
                    SELECT state, payload, payload_hash
                    FROM result_cache WHERE cache_key=?
                    """,
                    (key,),
                ).fetchone()
                if row is None or str(row[0]) == "PENDING":
                    connection.commit()
                    return None
                if str(row[0]) == "CORRUPT":
                    raise CacheCorruptionError(f"Cache entry {key!r} is marked corrupt")
                payload = self._decode_verified(key, row[1], row[2])
                connection.execute(
                    """
                    UPDATE result_cache
                    SET hit_count=hit_count+1, last_hit_at=?, updated_at=?
                    WHERE cache_key=? AND state='READY'
                    """,
                    (now, now, key),
                )
                connection.commit()
                return payload
            except Exception:
                connection.rollback()
                raise

    def put(self, key: str, payload: dict[str, Any]) -> None:
        """Publish a ready immutable entry without a prior reservation.

        This compatibility method is suitable for trusted single-process callers. Concurrent solver
        paths must use ``reserve`` and ``publish`` so duplicate work is prevented.
        """

        if not key.strip():
            raise ValueError("cache key must not be blank")
        encoded, payload_hash = self._encode_payload(payload)
        now = time.time()
        with self._lock, closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                row = connection.execute(
                    "SELECT state, payload_hash FROM result_cache WHERE cache_key=?",
                    (key,),
                ).fetchone()
                if row is None:
                    connection.execute(
                        """
                        INSERT INTO result_cache(
                            cache_key, state, payload, payload_hash, schema_version,
                            created_at, updated_at
                        ) VALUES(?, 'READY', ?, ?, ?, ?, ?)
                        """,
                        (
                            key,
                            encoded,
                            payload_hash,
                            _CACHE_SCHEMA_VERSION,
                            now,
                            now,
                        ),
                    )
                    connection.commit()
                    return
                if str(row[0]) == "READY" and str(row[1]) == payload_hash:
                    connection.commit()
                    return
                raise CacheOwnershipError(
                    f"Cache entry {key!r} already exists with different or pending content"
                )
            except Exception:
                connection.rollback()
                raise

    def stats(self) -> dict[str, int]:
        with self._lock, closing(self._connect()) as connection:
            row = connection.execute(
                """
                SELECT
                    SUM(CASE WHEN state='READY' THEN 1 ELSE 0 END),
                    COALESCE(SUM(CASE WHEN state='READY' THEN hit_count ELSE 0 END), 0)
                FROM result_cache
                """
            ).fetchone()
        return {"entries": int(row[0] or 0), "hits": int(row[1])}

    def clear(self) -> int:
        with self._lock, closing(self._connect()) as connection, connection:
            cursor = connection.execute("DELETE FROM result_cache")
            return int(cursor.rowcount)
