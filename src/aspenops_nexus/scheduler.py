from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .batch import dry_run_document, run_batch_document
from .config import Settings
from .hashing import canonical_hash
from .pool_manager import PoolManager
from .provenance import write_run_bundle


def _now() -> str:
    return datetime.now(UTC).isoformat()


class JobStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        with closing(self._connect()) as connection, connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA synchronous=NORMAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    request_hash TEXT NOT NULL,
                    status TEXT NOT NULL,
                    request_json TEXT NOT NULL,
                    result_json TEXT,
                    error TEXT,
                    bundle_path TEXT,
                    worker_owner TEXT,
                    cancel_requested INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    finished_at TEXT,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                UPDATE jobs
                SET status='interrupted', error='service restarted while job was running',
                    finished_at=?, updated_at=?
                WHERE status='running'
                """,
                (_now(), _now()),
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.execute("PRAGMA busy_timeout=30000")
        return connection

    def create(self, request: dict[str, Any]) -> str:
        job_id = uuid.uuid4().hex
        now = _now()
        request_hash = canonical_hash(request)
        with self._lock, closing(self._connect()) as connection, connection:
            connection.execute(
                """
                INSERT INTO jobs(
                    job_id, request_hash, status, request_json, created_at, updated_at
                ) VALUES(?,?,?,?,?,?)
                """,
                (
                    job_id,
                    request_hash,
                    "pending",
                    json.dumps(request, ensure_ascii=False, allow_nan=False),
                    now,
                    now,
                ),
            )
        return job_id

    def claim_next(self, owner: str) -> tuple[str, dict[str, Any]] | None:
        with self._lock, closing(self._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT job_id, request_json FROM jobs
                WHERE status='pending' AND cancel_requested=0
                ORDER BY created_at, job_id LIMIT 1
                """
            ).fetchone()
            if row is None:
                connection.commit()
                return None
            now = _now()
            cursor = connection.execute(
                """
                UPDATE jobs SET status='running', worker_owner=?, started_at=?, updated_at=?
                WHERE job_id=? AND status='pending'
                """,
                (owner, now, now, row[0]),
            )
            connection.commit()
            if cursor.rowcount != 1:
                return None
        return str(row[0]), json.loads(str(row[1]))

    def complete(self, job_id: str, results: list[dict[str, Any]], bundle_path: Path) -> None:
        now = _now()
        with self._lock, closing(self._connect()) as connection, connection:
            connection.execute(
                """
                UPDATE jobs SET status='completed', result_json=?, bundle_path=?,
                    finished_at=?, updated_at=? WHERE job_id=? AND status='running'
                """,
                (
                    json.dumps(results, ensure_ascii=False, allow_nan=False),
                    str(bundle_path),
                    now,
                    now,
                    job_id,
                ),
            )

    def fail(self, job_id: str, error: str) -> None:
        now = _now()
        with self._lock, closing(self._connect()) as connection, connection:
            connection.execute(
                """
                UPDATE jobs SET status='failed', error=?, finished_at=?, updated_at=?
                WHERE job_id=?
                """,
                (error, now, now, job_id),
            )

    def get(self, job_id: str) -> dict[str, Any] | None:
        with self._lock, closing(self._connect()) as connection:
            row = connection.execute(
                """
                SELECT job_id,request_hash,status,result_json,error,bundle_path,worker_owner,
                       cancel_requested,created_at,started_at,finished_at,updated_at
                FROM jobs WHERE job_id=?
                """,
                (job_id,),
            ).fetchone()
        if row is None:
            return None
        return {
            "job_id": row[0],
            "request_hash": row[1],
            "status": row[2],
            "results": None if row[3] is None else json.loads(str(row[3])),
            "error": row[4],
            "bundle_path": row[5],
            "worker_owner": row[6],
            "cancel_requested": bool(row[7]),
            "created_at": row[8],
            "started_at": row[9],
            "finished_at": row[10],
            "updated_at": row[11],
        }

    def list_recent(self, limit: int = 20) -> list[dict[str, Any]]:
        limit = max(1, min(limit, 200))
        with self._lock, closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT job_id FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [item for row in rows if (item := self.get(str(row[0]))) is not None]

    def cancel(self, job_id: str) -> bool:
        now = _now()
        with self._lock, closing(self._connect()) as connection, connection:
            cursor = connection.execute(
                """
                UPDATE jobs
                SET cancel_requested=1,
                    status=CASE WHEN status='pending' THEN 'cancelled' ELSE status END,
                    finished_at=CASE WHEN status='pending' THEN ? ELSE finished_at END,
                    updated_at=?
                WHERE job_id=? AND status IN ('pending','running')
                """,
                (now, now, job_id),
            )
            return cursor.rowcount == 1


class BackgroundScheduler:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.settings.state_dir.mkdir(parents=True, exist_ok=True)
        self.store = JobStore(self.settings.state_dir / "jobs.sqlite3")
        self.pool_manager = PoolManager(
            cache_path=self.settings.state_dir / "cache.sqlite3",
            license_slots=self.settings.license_slots,
            max_resident_cases=self.settings.max_resident_cases,
            idle_timeout_s=self.settings.pool_idle_timeout_s,
            worker_max_points=self.settings.worker_max_points,
            worker_max_age_s=self.settings.worker_max_age_s,
            startup_timeout_s=self.settings.startup_timeout_s,
            cache_failures=self.settings.cache_failures,
        )
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
        if not self._thread or not self._thread.is_alive():
            self.pool_manager.close()

    def submit(self, request: dict[str, Any]) -> str:
        dry_run_document(request, self.settings)
        self.start()
        return self.store.create(request)

    def _loop(self) -> None:
        while not self._stop.is_set():
            claimed = self.store.claim_next(self.owner)
            if claimed is None:
                self.pool_manager.evict_idle()
                self._stop.wait(self.settings.scheduler_poll_s)
                continue
            job_id, request = claimed
            try:
                results = run_batch_document(
                    request,
                    self.settings,
                    pool_manager=self.pool_manager,
                )
                record = self.store.get(job_id)
                if record and record["cancel_requested"]:
                    self.store.fail(
                        job_id,
                        "cancellation requested after simulator execution started",
                    )
                    continue
                bundle = write_run_bundle(
                    request=request,
                    results=results,
                    output_path=self.settings.state_dir / "bundles" / f"{job_id}.zip",
                )
                self.store.complete(job_id, results, bundle)
            except Exception as exc:
                self.store.fail(job_id, f"{type(exc).__name__}: {exc}")
