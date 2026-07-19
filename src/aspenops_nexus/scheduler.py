from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from contextlib import closing
from datetime import UTC, datetime, timedelta
from functools import partial
from pathlib import Path
from typing import Any

from .batch import dry_run_document, run_batch_document
from .config import Settings
from .hashing import canonical_hash
from .optimization import OptimizationProblem, run_optimization_document
from .pool import CasePool
from .pool_manager import PoolManager
from .provenance import write_run_bundle


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _future(seconds: float) -> str:
    return (datetime.now(UTC) + timedelta(seconds=max(0.0, seconds))).isoformat()


class JobStore:
    """Durable at-least-once job state with leases and idempotent result commits."""

    _MIGRATIONS = {
        "lease_owner": "TEXT",
        "lease_expires_at": "TEXT",
        "heartbeat_at": "TEXT",
        "attempt": "INTEGER NOT NULL DEFAULT 0",
        "max_attempts": "INTEGER NOT NULL DEFAULT 3",
        "last_completed_point": "INTEGER NOT NULL DEFAULT -1",
        "cancel_deadline": "TEXT",
        "result_commit_token": "TEXT",
        "error_class": "TEXT",
        "case_key": "TEXT",
    }

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
                    updated_at TEXT NOT NULL,
                    lease_owner TEXT,
                    lease_expires_at TEXT,
                    heartbeat_at TEXT,
                    attempt INTEGER NOT NULL DEFAULT 0,
                    max_attempts INTEGER NOT NULL DEFAULT 3,
                    last_completed_point INTEGER NOT NULL DEFAULT -1,
                    cancel_deadline TEXT,
                    result_commit_token TEXT,
                    error_class TEXT,
                    case_key TEXT
                )
                """
            )
            self._ensure_columns(connection)
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS job_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL,
                    event TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            self._recover_after_restart(connection)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.execute("PRAGMA busy_timeout=30000")
        return connection

    @classmethod
    def _ensure_columns(cls, connection: sqlite3.Connection) -> None:
        existing = {str(row[1]) for row in connection.execute("PRAGMA table_info(jobs)").fetchall()}
        for name, definition in cls._MIGRATIONS.items():
            if name not in existing:
                connection.execute(f"ALTER TABLE jobs ADD COLUMN {name} {definition}")

    @staticmethod
    def _event(
        connection: sqlite3.Connection,
        job_id: str,
        event: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        connection.execute(
            """
            INSERT INTO job_events(job_id,event,payload_json,created_at)
            VALUES(?,?,?,?)
            """,
            (
                job_id,
                event,
                json.dumps(payload or {}, ensure_ascii=False, allow_nan=False),
                _now(),
            ),
        )

    def _recover_after_restart(self, connection: sqlite3.Connection) -> None:
        now = _now()
        connection.execute(
            """
            UPDATE jobs
            SET status='cancelled', error='service restarted during cancellation',
                finished_at=?, updated_at=?, lease_owner=NULL, lease_expires_at=NULL
            WHERE status IN ('claimed','running','cancelling') AND cancel_requested=1
            """,
            (now, now),
        )
        connection.execute(
            """
            UPDATE jobs
            SET status=CASE
                    WHEN attempt < max_attempts THEN 'retry_wait'
                    ELSE 'dead_letter'
                END,
                error=CASE
                    WHEN attempt < max_attempts
                        THEN 'service restarted while job held a lease'
                    ELSE 'service restarted after final job attempt'
                END,
                error_class='service_restart',
                finished_at=CASE
                    WHEN attempt < max_attempts THEN NULL ELSE ?
                END,
                updated_at=?, lease_owner=NULL, lease_expires_at=NULL
            WHERE status IN ('claimed','running') AND cancel_requested=0
            """,
            (now, now),
        )

    def create(self, request: dict[str, Any], max_attempts: int = 3) -> str:
        job_id = uuid.uuid4().hex
        now = _now()
        request_hash = canonical_hash(request)
        with self._lock, closing(self._connect()) as connection, connection:
            connection.execute(
                """
                INSERT INTO jobs(
                    job_id,request_hash,status,request_json,max_attempts,created_at,updated_at
                ) VALUES(?,?,?,?,?,?,?)
                """,
                (
                    job_id,
                    request_hash,
                    "pending",
                    json.dumps(request, ensure_ascii=False, allow_nan=False),
                    max(1, max_attempts),
                    now,
                    now,
                ),
            )
            self._event(connection, job_id, "created", {"request_hash": request_hash})
        return job_id

    def _recover_expired(self, connection: sqlite3.Connection, now: str) -> None:
        cancelled = connection.execute(
            """
            SELECT job_id FROM jobs
            WHERE status IN ('claimed','running','cancelling')
              AND lease_expires_at IS NOT NULL AND lease_expires_at < ?
              AND cancel_requested=1
            """,
            (now,),
        ).fetchall()
        connection.execute(
            """
            UPDATE jobs
            SET status='cancelled', error='lease expired after cancellation', finished_at=?,
                updated_at=?, lease_owner=NULL, lease_expires_at=NULL
            WHERE status IN ('claimed','running','cancelling')
              AND lease_expires_at IS NOT NULL AND lease_expires_at < ?
              AND cancel_requested=1
            """,
            (now, now, now),
        )
        for row in cancelled:
            self._event(connection, str(row[0]), "cancelled_after_lease_expiry")

        expired = connection.execute(
            """
            SELECT job_id,attempt,max_attempts FROM jobs
            WHERE status IN ('claimed','running')
              AND lease_expires_at IS NOT NULL AND lease_expires_at < ?
              AND cancel_requested=0
            """,
            (now,),
        ).fetchall()
        connection.execute(
            """
            UPDATE jobs
            SET status=CASE
                    WHEN attempt < max_attempts THEN 'retry_wait'
                    ELSE 'dead_letter'
                END,
                error=CASE
                    WHEN attempt < max_attempts THEN 'job lease expired'
                    ELSE 'job lease expired after final attempt'
                END,
                error_class='lease_expired',
                finished_at=CASE
                    WHEN attempt < max_attempts THEN NULL ELSE ?
                END,
                updated_at=?, lease_owner=NULL, lease_expires_at=NULL
            WHERE status IN ('claimed','running')
              AND lease_expires_at IS NOT NULL AND lease_expires_at < ?
              AND cancel_requested=0
            """,
            (now, now, now),
        )
        for row in expired:
            attempt = int(row[1])
            max_attempts = int(row[2])
            event = "lease_expired" if attempt < max_attempts else "dead_letter_after_lease_expiry"
            self._event(
                connection,
                str(row[0]),
                event,
                {"attempt": attempt, "max_attempts": max_attempts},
            )

    def claim_next(self, owner: str, lease_s: float = 30.0) -> tuple[str, dict[str, Any]] | None:
        with self._lock, closing(self._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            now = _now()
            self._recover_expired(connection, now)
            row = connection.execute(
                """
                SELECT job_id,request_json FROM jobs
                WHERE status IN ('pending','retry_wait')
                  AND cancel_requested=0 AND attempt < max_attempts
                ORDER BY created_at,job_id LIMIT 1
                """
            ).fetchone()
            if row is None:
                connection.commit()
                return None
            lease_expires_at = _future(lease_s)
            cursor = connection.execute(
                """
                UPDATE jobs
                SET status='claimed', worker_owner=?, lease_owner=?, lease_expires_at=?,
                    heartbeat_at=?, started_at=COALESCE(started_at,?), updated_at=?,
                    attempt=attempt+1
                WHERE job_id=? AND status IN ('pending','retry_wait')
                """,
                (owner, owner, lease_expires_at, now, now, now, row[0]),
            )
            if cursor.rowcount != 1:
                connection.rollback()
                return None
            self._event(
                connection,
                str(row[0]),
                "claimed",
                {"owner": owner, "lease_expires_at": lease_expires_at},
            )
            connection.commit()
        return str(row[0]), json.loads(str(row[1]))

    def mark_running(self, job_id: str, owner: str, lease_s: float = 30.0) -> bool:
        now = _now()
        with self._lock, closing(self._connect()) as connection, connection:
            cursor = connection.execute(
                """
                UPDATE jobs
                SET status='running', heartbeat_at=?, lease_expires_at=?, updated_at=?
                WHERE job_id=? AND status='claimed' AND lease_owner=?
                """,
                (now, _future(lease_s), now, job_id, owner),
            )
            if cursor.rowcount == 1:
                self._event(connection, job_id, "running", {"owner": owner})
            return cursor.rowcount == 1

    def heartbeat(self, job_id: str, owner: str, lease_s: float = 30.0) -> bool:
        now = _now()
        with self._lock, closing(self._connect()) as connection, connection:
            cursor = connection.execute(
                """
                UPDATE jobs
                SET heartbeat_at=?, lease_expires_at=?, updated_at=?
                WHERE job_id=? AND lease_owner=?
                  AND status IN ('claimed','running','cancelling')
                """,
                (now, _future(lease_s), now, job_id, owner),
            )
            return cursor.rowcount == 1

    def append_progress(
        self,
        job_id: str,
        results: list[dict[str, Any]],
        last_completed_point: int,
    ) -> bool:
        now = _now()
        with self._lock, closing(self._connect()) as connection, connection:
            cursor = connection.execute(
                """
                UPDATE jobs
                SET result_json=?, last_completed_point=?, updated_at=?
                WHERE job_id=? AND status IN ('running','cancelling')
                """,
                (
                    json.dumps(results, ensure_ascii=False, allow_nan=False),
                    last_completed_point,
                    now,
                    job_id,
                ),
            )
            if cursor.rowcount == 1:
                self._event(
                    connection,
                    job_id,
                    "progress_committed",
                    {"last_completed_point": last_completed_point},
                )
            return cursor.rowcount == 1

    def complete(
        self,
        job_id: str,
        results: list[dict[str, Any]],
        bundle_path: Path,
        commit_token: str | None = None,
    ) -> bool:
        token = commit_token or canonical_hash(results)
        now = _now()
        with self._lock, closing(self._connect()) as connection, connection:
            existing = connection.execute(
                "SELECT status,result_commit_token FROM jobs WHERE job_id=?", (job_id,)
            ).fetchone()
            if existing is None:
                return False
            if existing[0] == "completed":
                return str(existing[1]) == token
            cursor = connection.execute(
                """
                UPDATE jobs
                SET status='completed', result_json=?, bundle_path=?, result_commit_token=?,
                    finished_at=?, updated_at=?, lease_owner=NULL, lease_expires_at=NULL
                WHERE job_id=? AND status='running'
                """,
                (
                    json.dumps(results, ensure_ascii=False, allow_nan=False),
                    str(bundle_path),
                    token,
                    now,
                    now,
                    job_id,
                ),
            )
            if cursor.rowcount == 1:
                self._event(connection, job_id, "completed", {"commit_token": token})
            return cursor.rowcount == 1

    def finalize_cancelled(
        self,
        job_id: str,
        results: list[dict[str, Any]],
        bundle_path: Path | None = None,
    ) -> bool:
        now = _now()
        with self._lock, closing(self._connect()) as connection, connection:
            cursor = connection.execute(
                """
                UPDATE jobs
                SET status='cancelled', result_json=?, bundle_path=?, finished_at=?, updated_at=?,
                    lease_owner=NULL, lease_expires_at=NULL, cancel_deadline=NULL
                WHERE job_id=? AND status IN ('claimed','running','cancelling')
                """,
                (
                    json.dumps(results, ensure_ascii=False, allow_nan=False),
                    None if bundle_path is None else str(bundle_path),
                    now,
                    now,
                    job_id,
                ),
            )
            if cursor.rowcount == 1:
                self._event(connection, job_id, "cancelled")
            return cursor.rowcount == 1

    def fail(self, job_id: str, error: str, error_class: str = "execution_error") -> None:
        now = _now()
        with self._lock, closing(self._connect()) as connection, connection:
            connection.execute(
                """
                UPDATE jobs
                SET status='failed', error=?, error_class=?, finished_at=?, updated_at=?,
                    lease_owner=NULL, lease_expires_at=NULL
                WHERE job_id=?
                """,
                (error, error_class, now, now, job_id),
            )
            self._event(connection, job_id, "failed", {"error_class": error_class})

    def retry_or_fail(
        self,
        job_id: str,
        error: str,
        error_class: str,
        *,
        retryable: bool,
    ) -> str:
        now = _now()
        with self._lock, closing(self._connect()) as connection, connection:
            row = connection.execute(
                "SELECT attempt,max_attempts FROM jobs WHERE job_id=?", (job_id,)
            ).fetchone()
            if row is None:
                return "missing"
            attempt = int(row[0])
            max_attempts = int(row[1])
            if retryable and attempt < max_attempts:
                status = "retry_wait"
                finished_at = None
            elif retryable:
                status = "dead_letter"
                finished_at = now
            else:
                status = "failed"
                finished_at = now
            connection.execute(
                """
                UPDATE jobs
                SET status=?, error=?, error_class=?, finished_at=?, updated_at=?,
                    lease_owner=NULL, lease_expires_at=NULL
                WHERE job_id=?
                """,
                (status, error, error_class, finished_at, now, job_id),
            )
            self._event(
                connection,
                job_id,
                status,
                {"error_class": error_class, "attempt": attempt},
            )
            return status

    def get(self, job_id: str) -> dict[str, Any] | None:
        with self._lock, closing(self._connect()) as connection:
            row = connection.execute(
                """
                SELECT job_id,request_hash,status,result_json,error,bundle_path,worker_owner,
                       cancel_requested,created_at,started_at,finished_at,updated_at,
                       lease_owner,lease_expires_at,heartbeat_at,attempt,max_attempts,
                       last_completed_point,cancel_deadline,result_commit_token,error_class,case_key
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
            "lease_owner": row[12],
            "lease_expires_at": row[13],
            "heartbeat_at": row[14],
            "attempt": int(row[15]),
            "max_attempts": int(row[16]),
            "last_completed_point": int(row[17]),
            "cancel_deadline": row[18],
            "result_commit_token": row[19],
            "error_class": row[20],
            "case_key": row[21],
        }

    def list_recent(self, limit: int = 20) -> list[dict[str, Any]]:
        limit = max(1, min(limit, 200))
        with self._lock, closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT job_id FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [item for row in rows if (item := self.get(str(row[0]))) is not None]

    def events(self, job_id: str, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock, closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT event,payload_json,created_at FROM job_events
                WHERE job_id=? ORDER BY event_id DESC LIMIT ?
                """,
                (job_id, max(1, min(limit, 1000))),
            ).fetchall()
        return [
            {"event": row[0], "payload": json.loads(str(row[1])), "created_at": row[2]}
            for row in rows
        ]

    def cancel(self, job_id: str, grace_s: float = 2.0) -> bool:
        now = _now()
        deadline = _future(grace_s)
        with self._lock, closing(self._connect()) as connection, connection:
            cursor = connection.execute(
                """
                UPDATE jobs
                SET cancel_requested=1,
                    status=CASE
                        WHEN status IN ('pending','retry_wait') THEN 'cancelled'
                        WHEN status IN ('claimed','running') THEN 'cancelling'
                        ELSE status
                    END,
                    cancel_deadline=CASE
                        WHEN status IN ('claimed','running') THEN ? ELSE cancel_deadline
                    END,
                    finished_at=CASE
                        WHEN status IN ('pending','retry_wait') THEN ? ELSE finished_at
                    END,
                    updated_at=?
                WHERE job_id=?
                  AND status IN ('pending','retry_wait','claimed','running','cancelling')
                """,
                (deadline, now, now, job_id),
            )
            if cursor.rowcount == 1:
                self._event(connection, job_id, "cancel_requested", {"deadline": deadline})
            return cursor.rowcount == 1

    def is_cancel_requested(self, job_id: str) -> bool:
        with self._lock, closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT cancel_requested FROM jobs WHERE job_id=?", (job_id,)
            ).fetchone()
        return bool(row and row[0])

    def cancellation_due(self) -> list[str]:
        now = _now()
        with self._lock, closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT job_id FROM jobs
                WHERE status='cancelling' AND cancel_deadline IS NOT NULL
                  AND cancel_deadline <= ?
                """,
                (now,),
            ).fetchall()
        return [str(row[0]) for row in rows]

    def mark_abort_dispatched(self, job_id: str, events: list[dict[str, Any]]) -> None:
        with self._lock, closing(self._connect()) as connection, connection:
            connection.execute(
                "UPDATE jobs SET cancel_deadline=NULL,updated_at=? WHERE job_id=?",
                (_now(), job_id),
            )
            self._event(connection, job_id, "worker_recycle_dispatched", {"events": events})


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
        self._watcher_thread: threading.Thread | None = None
        self._active_lock = threading.RLock()
        self._active_pools: dict[str, CasePool] = {}
        self.owner = f"scheduler-{uuid.uuid4().hex[:12]}"

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="aspenops-scheduler", daemon=True)
        self._watcher_thread = threading.Thread(
            target=self._watch_active_jobs,
            name="aspenops-cancellation-watcher",
            daemon=True,
        )
        self._thread.start()
        self._watcher_thread.start()

    def _active_snapshot(self) -> dict[str, CasePool]:
        with self._active_lock:
            return dict(self._active_pools)

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)
        if self._thread and self._thread.is_alive():
            for pool in self._active_snapshot().values():
                pool.force_recycle_all("scheduler_stop")
            self._thread.join(timeout=10)
        if self._watcher_thread:
            self._watcher_thread.join(timeout=5)
        if not self._thread or not self._thread.is_alive():
            self.pool_manager.close()

    def submit(self, request: dict[str, Any]) -> str:
        if "optimization" in request:
            OptimizationProblem.from_document(request)
            dry_run_document(
                {key: value for key, value in request.items() if key != "optimization"},
                self.settings,
            )
        else:
            dry_run_document(request, self.settings)
        self.start()
        return self.store.create(request, self.settings.job_max_attempts)

    def cancel(self, job_id: str) -> bool:
        return self.store.cancel(job_id, self.settings.cancellation_grace_s)

    def _observe_pool(self, job_id: str, pool: CasePool | None) -> None:
        with self._active_lock:
            if pool is None:
                self._active_pools.pop(job_id, None)
            else:
                self._active_pools[job_id] = pool

    def _watch_active_jobs(self) -> None:
        interval = max(0.05, min(self.settings.scheduler_poll_s, self.settings.job_lease_s / 3))
        while not self._stop.wait(interval):
            active = self._active_snapshot()
            for job_id in active:
                self.store.heartbeat(job_id, self.owner, self.settings.job_lease_s)
            for job_id in self.store.cancellation_due():
                pool = active.get(job_id)
                events = [] if pool is None else pool.force_recycle_all("cancel_deadline")
                self.store.mark_abort_dispatched(job_id, events)

    @staticmethod
    def _last_completed_point(results: list[dict[str, Any]]) -> int:
        last = -1
        for index, result in enumerate(results):
            violations = set(result.get("violations", []))
            if "batch_cancelled" in violations:
                break
            if violations.intersection(
                {"worker_receive_failed", "worker_send_failed", "worker_protocol_error"}
            ):
                break
            last = index
        return last

    @staticmethod
    def _classify_error(exc: Exception) -> tuple[str, bool]:
        text = str(exc).lower()
        if "license" in text:
            return "transient_license", True
        if isinstance(exc, TimeoutError):
            return "startup_timeout", True
        if "worker_timeout" in text or "solve timeout" in text:
            return "solve_timeout", True
        if "brokenpipe" in text or "worker_receive" in text:
            return "transport_failure", True
        if isinstance(exc, PermissionError | ValueError):
            return "invalid_request", False
        return "execution_error", False

    def _loop(self) -> None:
        while not self._stop.is_set():
            claimed = self.store.claim_next(self.owner, self.settings.job_lease_s)
            if claimed is None:
                self.pool_manager.evict_idle()
                self._stop.wait(self.settings.scheduler_poll_s)
                continue
            job_id, request = claimed
            if not self.store.mark_running(job_id, self.owner, self.settings.job_lease_s):
                continue
            try:
                cancel_check = partial(self.store.is_cancel_requested, job_id)
                pool_observer = partial(self._observe_pool, job_id)
                if "optimization" in request:
                    optimization_result = run_optimization_document(
                        request,
                        self.settings,
                        pool_manager=self.pool_manager,
                        cancel_check=cancel_check,
                        pool_observer=pool_observer,
                    )
                    results = [optimization_result]
                else:
                    results = run_batch_document(
                        request,
                        self.settings,
                        pool_manager=self.pool_manager,
                        cancel_check=cancel_check,
                        pool_observer=pool_observer,
                    )
                last_completed = self._last_completed_point(results)
                self.store.append_progress(job_id, results, last_completed)
                record = self.store.get(job_id)
                bundle = write_run_bundle(
                    request=request,
                    results=results,
                    output_path=self.settings.state_dir / "bundles" / f"{job_id}.zip",
                )
                if record and record["cancel_requested"]:
                    self.store.finalize_cancelled(job_id, results, bundle)
                else:
                    self.store.complete(
                        job_id,
                        results,
                        bundle,
                        commit_token=canonical_hash(results),
                    )
            except Exception as exc:
                error_class, retryable = self._classify_error(exc)
                self.store.retry_or_fail(
                    job_id,
                    f"{type(exc).__name__}: {exc}",
                    error_class,
                    retryable=retryable,
                )
            finally:
                self._observe_pool(job_id, None)
