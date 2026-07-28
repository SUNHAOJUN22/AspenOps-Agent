from __future__ import annotations

import argparse
import json
import os
import platform
import sqlite3
import tempfile
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import psutil

import aspenops_nexus.job_queries as job_queries
from aspenops_nexus.job_queries import list_recent_job_records, recent_jobs_query_plan
from aspenops_nexus.scheduler import JobStore


def _seed(path: Path, count: int) -> None:
    JobStore(path)
    origin = datetime(2026, 7, 27, tzinfo=UTC)
    rows = []
    for index in range(count):
        created_at = (origin + timedelta(seconds=index)).isoformat()
        rows.append(
            (
                f"job-{index:06d}",
                f"hash-{index:06d}",
                "pending",
                json.dumps({"ordinal": index}, separators=(",", ":")),
                3,
                created_at,
                created_at,
            )
        )
    with closing(sqlite3.connect(path)) as connection, connection:
        connection.executemany(
            """
            INSERT INTO jobs(
                job_id,request_hash,status,request_json,max_attempts,created_at,updated_at
            ) VALUES(?,?,?,?,?,?,?)
            """,
            rows,
        )


def environment() -> dict[str, Any]:
    memory = psutil.virtual_memory()
    return {
        "git_commit": os.getenv("GITHUB_SHA") or os.getenv("ASPENOPS_GIT_COMMIT"),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "cpu_logical": psutil.cpu_count(logical=True),
        "memory_total_bytes": int(memory.total),
        "sqlite_version": sqlite3.sqlite_version,
    }


def run_probe(*, records: int = 1000, limit: int = 20) -> dict[str, Any]:
    if records < 1:
        raise ValueError("records must be positive")
    if limit < 1:
        raise ValueError("limit must be positive")

    with tempfile.TemporaryDirectory(prefix="aspenops-job-query-") as temporary:
        path = Path(temporary) / "jobs.sqlite3"
        _seed(path, records)
        statements: list[str] = []
        connection_calls = 0
        original_connect = job_queries._connect

        def traced_connect(database: Path) -> sqlite3.Connection:
            nonlocal connection_calls
            connection_calls += 1
            connection = original_connect(database)
            connection.set_trace_callback(statements.append)
            return connection

        job_queries._connect = traced_connect
        try:
            rows = list_recent_job_records(path, limit)
        finally:
            job_queries._connect = original_connect

        selects = [
            statement for statement in statements if statement.lstrip().upper().startswith("SELECT")
        ]
        plan = recent_jobs_query_plan(path, limit)
        with closing(sqlite3.connect(path)) as connection, connection:
            indexes = sorted(str(row[1]) for row in connection.execute("PRAGMA index_list('jobs')"))

    return {
        "schema": "aspenops.job-store-query-plan/v1",
        "kind": "portable-deterministic-sql-evidence",
        "boundary": (
            "This evidence measures SQLite control-plane reads only. It does not measure licensed "
            "Aspen Plus/HYSYS model-open or solve performance."
        ),
        "environment": environment(),
        "records": records,
        "requested_limit": limit,
        "returned_records": len(rows),
        "connection_calls": connection_calls,
        "select_statements": len(selects),
        "query_plan": plan,
        "indexes": indexes,
        "expected": {
            "connection_calls": 1,
            "select_statements": 1,
            "returned_records": min(records, limit),
            "required_index": "idx_jobs_recent_created_job",
            "temporary_sort": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--records", type=int, default=1000)
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()

    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            run_probe(records=args.records, limit=args.limit),
            indent=2,
            ensure_ascii=False,
            allow_nan=False,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
