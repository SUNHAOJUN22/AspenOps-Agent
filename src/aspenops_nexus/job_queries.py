from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import closing
from pathlib import Path
from typing import Any

_JOB_COLUMNS = (
    "job_id",
    "request_hash",
    "status",
    "result_json",
    "error",
    "bundle_path",
    "worker_owner",
    "cancel_requested",
    "created_at",
    "started_at",
    "finished_at",
    "updated_at",
    "lease_owner",
    "lease_expires_at",
    "heartbeat_at",
    "attempt",
    "max_attempts",
    "last_completed_point",
    "cancel_deadline",
    "result_commit_token",
    "error_class",
    "case_key",
)
_SELECT_JOB_COLUMNS = ",".join(_JOB_COLUMNS)
_RECENT_INDEX = "idx_jobs_recent_created_job"
_index_lock = threading.Lock()


def _connect(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path, timeout=30)
    connection.execute("PRAGMA busy_timeout=30000")
    return connection


def _has_recent_index(connection: sqlite3.Connection) -> bool:
    with closing(connection.execute("PRAGMA index_list('jobs')")) as cursor:
        return any(str(row[1]) == _RECENT_INDEX for row in cursor)


def _ensure_recent_index(connection: sqlite3.Connection) -> None:
    if _has_recent_index(connection):
        return
    with _index_lock:
        if _has_recent_index(connection):
            return
        connection.execute(
            f"CREATE INDEX IF NOT EXISTS {_RECENT_INDEX} ON jobs(created_at DESC, job_id DESC)"
        )
        connection.execute("PRAGMA optimize")
        connection.commit()


def _decode_job_row(row: tuple[Any, ...]) -> dict[str, Any]:
    if len(row) != len(_JOB_COLUMNS):
        raise ValueError("Unexpected jobs row shape")
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


def list_recent_job_records(path: str | Path, limit: int = 20) -> list[dict[str, Any]]:
    """Read recent durable jobs in one indexed snapshot without request bodies."""

    bounded_limit = max(1, min(limit, 200))
    database = Path(path)
    with closing(_connect(database)) as connection, connection:
        _ensure_recent_index(connection)
        rows = connection.execute(
            f"SELECT {_SELECT_JOB_COLUMNS} FROM jobs ORDER BY created_at DESC, job_id DESC LIMIT ?",
            (bounded_limit,),
        ).fetchall()
    return [_decode_job_row(tuple(row)) for row in rows]


def recent_jobs_query_plan(path: str | Path, limit: int = 20) -> list[str]:
    """Return SQLite plan details for the governed recent-job query."""

    bounded_limit = max(1, min(limit, 200))
    database = Path(path)
    with closing(_connect(database)) as connection, connection:
        _ensure_recent_index(connection)
        rows = connection.execute(
            f"EXPLAIN QUERY PLAN SELECT {_SELECT_JOB_COLUMNS} FROM jobs "
            "ORDER BY created_at DESC, job_id DESC LIMIT ?",
            (bounded_limit,),
        ).fetchall()
    return [str(row[3]) for row in rows]
