from __future__ import annotations

import json
import math
import sqlite3
import threading
import uuid
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from .batch import dry_run_document, run_batch_document
from .config import Settings
from .hashing import canonical_hash
from .provenance import write_run_bundle

_SCHEMA_VERSION = 1
_MIGRATION_CHECKSUM = "jobs-v1-atomic-state-machine"
_DB_STATES = (
    "PENDING",
    "CLAIMED",
    "RUNNING",
    "SUCCEEDED",
    "FAILED",
    "CANCELLED",
    "TIMED_OUT",
    "INTERRUPTED",
)
_PUBLIC_STATES = {
    "PENDING": "pending",
    "CLAIMED": "claimed",
    "RUNNING": "running",
    "SUCCEEDED": "completed",
    "FAILED": "failed",
    "CANCELLED": "cancelled",
    "TIMED_OUT": "timed_out",
    "INTERRUPTED": "interrupted",
}


class JobStateError(RuntimeError):
    pass


def _now_dt() -> datetime:
    return datetime.now(UTC)


def _iso(value: datetime) -> str:
    return value.isoformat()


def _now() -> str:
    return _iso(_now_dt())


class JobStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._initialize_schema()
        self.recover_expired_leases()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.execute("PRAGMA busy_timeout=30000")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def _initialize_schema(self) -> None:
        with self._lock, closing(self._connect()) as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA synchronous=NORMAL")
            connection.execute("BEGIN IMMEDIATE")
            try:
                version = int(connection.execute("PRAGMA user_version").fetchone()[0])
                table_exists = (
                    connection.execute(
                        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='jobs'"
                    ).fetchone()
                    is not None
                )
                if version == 0 and table_exists:
                    self._migrate_legacy_schema(connection)
                elif version == 0:
                    self._create_schema(connection)
                elif version != _SCHEMA_VERSION:
                    raise RuntimeError(
                        f"Unsupported jobs database schema {version}; expected {_SCHEMA_VERSION}"
                    )
                else:
                    self._create_schema(connection)
                connection.execute(f"PRAGMA user_version={_SCHEMA_VERSION}")
                connection.execute(
                    """
                    INSERT OR IGNORE INTO schema_migrations(version, checksum, applied_at)
                    VALUES (?, ?, ?)
                    """,
                    (_SCHEMA_VERSION, _MIGRATION_CHECKSUM, _now()),
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise

    @staticmethod
    def _create_schema(connection: sqlite3.Connection) -> None:
        states = ",".join(f"'{state}'" for state in _DB_STATES)
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY CHECK(version > 0),
                checksum TEXT NOT NULL,
                applied_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            f"""
            CREATE TABLE IF NOT EXISTS jobs (
                job_id TEXT PRIMARY KEY,
                request_hash TEXT NOT NULL,
                idempotency_key TEXT UNIQUE,
                status TEXT NOT NULL CHECK(status IN ({states})),
                request_json TEXT NOT NULL,
                result_json TEXT,
                error_code TEXT,
                error_message TEXT,
                bundle_path TEXT,
                worker_owner TEXT,
                lease_expires_at TEXT,
                cancel_requested INTEGER NOT NULL DEFAULT 0 CHECK(cancel_requested IN (0, 1)),
                version INTEGER NOT NULL DEFAULT 0 CHECK(version >= 0),
                created_at TEXT NOT NULL,
                started_at TEXT,
                finished_at TEXT,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_jobs_claim ON jobs(status, cancel_requested, created_at, job_id)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_jobs_recent ON jobs(created_at DESC, job_id DESC)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_jobs_lease ON jobs(status, lease_expires_at)"
        )

    def _migrate_legacy_schema(self, connection: sqlite3.Connection) -> None:
        columns = {
            str(row[1]) for row in connection.execute("PRAGMA table_info(jobs)").fetchall()
        }
        expected = {
            "job_id",
            "request_hash",
            "status",
            "request_json",
            "result_json",
            "error",
            "bundle_path",
            "worker_owner",
            "cancel_requested",
            "created_at",
            "started_at",
            "finished_at",
            "updated_at",
        }
        if not expected.issubset(columns):
            raise RuntimeError("Unrecognized legacy jobs schema; refusing destructive migration")
        connection.execute("ALTER TABLE jobs RENAME TO jobs_legacy_v0")
        self._create_schema(connection)
        connection.execute(
            """
            INSERT INTO jobs(
                job_id, request_hash, status, request_json, result_json,
                error_message, bundle_path, worker_owner, cancel_requested,
                version, created_at, started_at, finished_at, updated_at
            )
            SELECT
                job_id,
                request_hash,
                CASE status
                    WHEN 'pending' THEN 'PENDING'
                    WHEN 'running' THEN 'INTERRUPTED'
                    WHEN 'completed' THEN 'SUCCEEDED'
                    WHEN 'failed' THEN 'FAILED'
                    WHEN 'cancelled' THEN 'CANCELLED'
                    WHEN 'interrupted' THEN 'INTERRUPTED'
                    ELSE 'FAILED'
                END,
                request_json,
                result_json,
                error,
                bundle_path,
                worker_owner,
                CASE WHEN cancel_requested <> 0 THEN 1 ELSE 0 END,
                0,
                created_at,
                started_at,
                CASE
                    WHEN status = 'running' THEN COALESCE(finished_at, updated_at)
                    ELSE finished_at
                END,
                updated_at
            FROM jobs_legacy_v0
            """
        )
        connection.execute("DROP TABLE jobs_legacy_v0")

    def recover_expired_leases(self) -> int:
        now = _now()
        with self._lock, closing(self._connect()) as connection, connection:
            cursor = connection.execute(
                """
                UPDATE jobs
                SET status='INTERRUPTED', error_code='LEASE_EXPIRED',
                    error_message='worker lease expired before completion',
                    finished_at=?, updated_at=?, version=version+1
                WHERE status IN ('CLAIMED','RUNNING')
                  AND lease_expires_at IS NOT NULL
                  AND lease_expires_at < ?
                """,
                (now, now, now),
            )
            return int(cursor.rowcount)

    def create(self, request: dict[str, Any], idempotency_key: str | None = None) -> str:
        if idempotency_key is not None and not idempotency_key.strip():
            raise ValueError("idempotency_key must not be blank")
        job_id = uuid.uuid4().hex
        now = _now()
        request_hash = canonical_hash(request)
        encoded = json.dumps(request, ensure_ascii=False, allow_nan=False)
        with self._lock, closing(self._connect()) as connection, connection:
            if idempotency_key is not None:
                existing = connection.execute(
                    "SELECT job_id, request_hash FROM jobs WHERE idempotency_key=?",
                    (idempotency_key,),
                ).fetchone()
                if existing is not None:
                    if str(existing[1]) != request_hash:
                        raise ValueError("idempotency_key is already bound to a different request")
                    return str(existing[0])
            connection.execute(
                """
                INSERT INTO jobs(
                    job_id, request_hash, idempotency_key, status,
                    request_json, created_at, updated_at
                ) VALUES(?,?,?,'PENDING',?,?,?)
                """,
                (job_id, request_hash, idempotency_key, encoded, now, now),
            )
        return job_id

    def claim_next(
        self, owner: str, lease_seconds: float = 1800.0
    ) -> tuple[str, dict[str, Any]] | None:
        if not owner.strip():
            raise ValueError("owner must not be blank")
        if not math.isfinite(lease_seconds) or lease_seconds <= 0.0:
            raise ValueError("lease_seconds must be finite and positive")
        now_dt = _now_dt()
        now = _iso(now_dt)
        lease_expires_at = _iso(now_dt + timedelta(seconds=lease_seconds))
        with self._lock, closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                row = connection.execute(
                    """
                    UPDATE jobs
                    SET status='CLAIMED', worker_owner=?, lease_expires_at=?,
                        started_at=COALESCE(started_at, ?), updated_at=?, version=version+1
                    WHERE job_id=(
                        SELECT job_id FROM jobs
                        WHERE status='PENDING' AND cancel_requested=0
                        ORDER BY created_at, job_id LIMIT 1
                    )
                    AND status='PENDING'
                    RETURNING job_id, request_json
                    """,
                    (owner, lease_expires_at, now, now),
                ).fetchone()
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        if row is None:
            return None
        return str(row[0]), json.loads(str(row[1]))

    def mark_running(self, job_id: str, owner: str) -> None:
        now = _now()
        with self._lock, closing(self._connect()) as connection, connection:
            cursor = connection.execute(
                """
                UPDATE jobs SET status='RUNNING', updated_at=?, version=version+1
                WHERE job_id=? AND status='CLAIMED' AND worker_owner=?
                """,
                (now, job_id, owner),
            )
            if cursor.rowcount != 1:
                raise JobStateError(f"Cannot transition job {job_id} from CLAIMED to RUNNING")

    def complete(
        self, job_id: str, results: list[dict[str, Any]], bundle_path: Path, owner: str
    ) -> bool:
        now = _now()
        encoded = json.dumps(results, ensure_ascii=False, allow_nan=False)
        with self._lock, closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                cursor = connection.execute(
                    """
                    UPDATE jobs
                    SET status='SUCCEEDED', result_json=?, bundle_path=?,
                        finished_at=?, updated_at=?, lease_expires_at=NULL,
                        error_code=NULL, error_message=NULL, version=version+1
                    WHERE job_id=? AND status='RUNNING' AND worker_owner=?
                      AND cancel_requested=0
                    """,
                    (encoded, str(bundle_path), now, now, job_id, owner),
                )
                if cursor.rowcount == 1:
                    connection.commit()
                    return True
                row = connection.execute(
                    "SELECT status, worker_owner, cancel_requested FROM jobs WHERE job_id=?",
                    (job_id,),
                ).fetchone()
                if row is not None and row[0] == "RUNNING" and row[1] == owner and bool(row[2]):
                    connection.execute(
                        """
                        UPDATE jobs SET status='CANCELLED', error_code='CANCELLED',
                            error_message='cancellation requested before result publication',
                            finished_at=?, updated_at=?, lease_expires_at=NULL,
                            version=version+1
                        WHERE job_id=? AND status='RUNNING' AND worker_owner=?
                        """,
                        (now, now, job_id, owner),
                    )
                    connection.commit()
                    return False
                raise JobStateError(f"Cannot complete job {job_id} from its current state")
            except Exception:
                connection.rollback()
                raise

    def fail(self, job_id: str, error: str, owner: str | None = None) -> None:
        now = _now()
        error_code = error.partition(":")[0] or "UNCLASSIFIED_ERROR"
        with self._lock, closing(self._connect()) as connection, connection:
            cursor = connection.execute(
                """
                UPDATE jobs
                SET status='FAILED', error_code=?, error_message=?,
                    finished_at=?, updated_at=?, lease_expires_at=NULL,
                    version=version+1
                WHERE job_id=? AND status IN ('CLAIMED','RUNNING')
                  AND (? IS NULL OR worker_owner=?)
                """,
                (error_code, error, now, now, job_id, owner, owner),
            )
            if cursor.rowcount != 1:
                raise JobStateError(f"Cannot fail terminal, missing, or foreign-owned job {job_id}")

    @staticmethod
    def _record_from_row(row: tuple[Any, ...]) -> dict[str, Any]:
        return {
            "job_id": row[0],
            "request_hash": row[1],
            "status": _PUBLIC_STATES[str(row[2])],
            "results": None if row[3] is None else json.loads(str(row[3])),
            "error": row[5],
            "error_code": row[4],
            "bundle_path": row[6],
            "worker_owner": row[7],
            "lease_expires_at": row[8],
            "cancel_requested": bool(row[9]),
            "version": int(row[10]),
            "created_at": row[11],
            "started_at": row[12],
            "finished_at": row[13],
            "updated_at": row[14],
        }

    def get(self, job_id: str) -> dict[str, Any] | None:
        with self._lock, closing(self._connect()) as connection:
            row = connection.execute(
                """
                SELECT job_id,request_hash,status,result_json,error_code,error_message,
                       bundle_path,worker_owner,lease_expires_at,cancel_requested,version,
                       created_at,started_at,finished_at,updated_at
                FROM jobs WHERE job_id=?
                """,
                (job_id,),
            ).fetchone()
        return None if row is None else self._record_from_row(row)

    def list_recent(self, limit: int = 20) -> list[dict[str, Any]]:
        limit = max(1, min(limit, 200))
        with self._lock, closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT job_id,request_hash,status,result_json,error_code,error_message,
                       bundle_path,worker_owner,lease_expires_at,cancel_requested,version,
                       created_at,started_at,finished_at,updated_at
                FROM jobs ORDER BY created_at DESC, job_id DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._record_from_row(row) for row in rows]

    def cancel(self, job_id: str) -> bool:
        now = _now()
        with self._lock, closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                cursor = connection.execute(
                    """
                    UPDATE jobs
                    SET cancel_requested=1, status='CANCELLED',
                        error_code='CANCELLED', error_message='cancelled before claim',
                        finished_at=?, updated_at=?, version=version+1
                    WHERE job_id=? AND status='PENDING'
                    """,
                    (now, now, job_id),
                )
                if cursor.rowcount == 0:
                    cursor = connection.execute(
                        """
                        UPDATE jobs SET cancel_requested=1, updated_at=?, version=version+1
                        WHERE job_id=? AND status IN ('CLAIMED','RUNNING')
                        """,
                        (now, job_id),
                    )
                connection.commit()
                return cursor.rowcount == 1
            except Exception:
                connection.rollback()
                raise


class BackgroundScheduler:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.settings.state_dir.mkdir(parents=True, exist_ok=True)
        self.store = JobStore(self.settings.state_dir / "jobs.sqlite3")
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.owner = f"scheduler-{uuid.uuid4().hex[:12]}"

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="aspenops-scheduler", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)

    def submit(self, request: dict[str, Any]) -> str:
        dry_run_document(request, self.settings)
        self.start()
        return self.store.create(request)

    def _loop(self) -> None:
        lease_seconds = max(60.0, self.settings.timeout_s + self.settings.startup_timeout_s + 60.0)
        while not self._stop.is_set():
            claimed = self.store.claim_next(self.owner, lease_seconds=lease_seconds)
            if claimed is None:
                self._stop.wait(self.settings.scheduler_poll_s)
                continue
            job_id, request = claimed
            try:
                self.store.mark_running(job_id, self.owner)
                results = run_batch_document(request, self.settings)
                record = self.store.get(job_id)
                if record and record["cancel_requested"]:
                    self.store.complete(job_id, results, Path(""), self.owner)
                    continue
                bundle = write_run_bundle(
                    request=request,
                    results=results,
                    output_path=self.settings.state_dir / "bundles" / f"{job_id}.zip",
                )
                self.store.complete(job_id, results, bundle, self.owner)
            except JobStateError:
                continue
            except Exception as exc:
                try:
                    self.store.fail(job_id, f"{type(exc).__name__}: {exc}", owner=self.owner)
                except JobStateError:
                    continue
