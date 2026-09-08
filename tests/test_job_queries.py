from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

import pytest

import aspenops_nexus.job_queries as job_queries
from aspenops_nexus.config import Settings
from aspenops_nexus.job_queries import list_recent_job_records, recent_jobs_query_plan
from aspenops_nexus.mcp_server import AspenOpsTools
from aspenops_nexus.scheduler import JobStore


def _seed_jobs(path: Path) -> tuple[JobStore, list[str]]:
    store = JobStore(path)
    job_ids = [store.create({"ordinal": index}) for index in range(3)]
    with closing(sqlite3.connect(path)) as connection, connection:
        for index, job_id in enumerate(job_ids):
            connection.execute(
                "UPDATE jobs SET created_at=?, updated_at=? WHERE job_id=?",
                (
                    f"2026-07-27T00:00:0{index}+00:00",
                    f"2026-07-27T00:00:0{index}+00:00",
                    job_id,
                ),
            )
    return store, job_ids


def _indexes(path: Path) -> set[str]:
    with closing(sqlite3.connect(path)) as connection, connection:
        return {str(row[1]) for row in connection.execute("PRAGMA index_list('jobs')")}


def _remove_sqlite_files(path: Path) -> None:
    for suffix in ("", "-wal", "-shm"):
        Path(f"{path}{suffix}").unlink(missing_ok=True)


def test_recent_job_reader_matches_job_store_records_and_order(tmp_path: Path) -> None:
    path = tmp_path / "jobs.sqlite3"
    store, job_ids = _seed_jobs(path)

    records = list_recent_job_records(path, 2)
    expected = [store.get(job_ids[2]), store.get(job_ids[1])]

    assert records == expected
    assert all(record is not None for record in records)
    assert list_recent_job_records(path, 0)[0]["job_id"] == job_ids[2]
    assert len(list_recent_job_records(path, 500)) == 3


def test_recent_job_reader_uses_one_select_and_persistent_index(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "jobs.sqlite3"
    _seed_jobs(path)
    statements: list[str] = []
    connection_calls = 0
    original_connect = job_queries._connect

    def traced_connect(database: Path) -> sqlite3.Connection:
        nonlocal connection_calls
        connection_calls += 1
        connection = original_connect(database)
        connection.set_trace_callback(statements.append)
        return connection

    monkeypatch.setattr(job_queries, "_connect", traced_connect)

    assert len(list_recent_job_records(path, 20)) == 3
    selects = [
        statement for statement in statements if statement.lstrip().upper().startswith("SELECT")
    ]
    assert connection_calls == 1
    assert len(selects) == 1
    assert "idx_jobs_recent_created_job" in _indexes(path)

    plan = recent_jobs_query_plan(path)
    assert any("idx_jobs_recent_created_job" in detail for detail in plan)
    assert all("USE TEMP B-TREE" not in detail.upper() for detail in plan)


def test_recent_job_reader_recreates_index_after_same_path_database_replacement(
    tmp_path: Path,
) -> None:
    path = tmp_path / "jobs.sqlite3"
    _, first_job_ids = _seed_jobs(path)
    assert list_recent_job_records(path, 20)
    assert "idx_jobs_recent_created_job" in _indexes(path)

    _remove_sqlite_files(path)
    _, replacement_job_ids = _seed_jobs(path)
    assert not set(first_job_ids) & set(replacement_job_ids)
    assert "idx_jobs_recent_created_job" not in _indexes(path)

    records = list_recent_job_records(path, 20)
    assert {str(record["job_id"]) for record in records} == set(replacement_job_ids)
    assert "idx_jobs_recent_created_job" in _indexes(path)


def test_mcp_recent_jobs_does_not_call_legacy_n_plus_one_reader(tmp_path: Path) -> None:
    path = tmp_path / "jobs.sqlite3"
    store, job_ids = _seed_jobs(path)

    def forbidden_list_recent(limit: int = 20) -> list[dict[str, Any]]:
        del limit
        raise AssertionError("MCP must use the indexed single-query reader")

    store.list_recent = forbidden_list_recent  # type: ignore[method-assign]

    class FakeScheduler:
        def __init__(self) -> None:
            self.store = store

    tools = AspenOpsTools(
        Settings(state_dir=tmp_path / "state"),
        FakeScheduler(),  # type: ignore[arg-type]
    )
    result = tools.list_recent_jobs(2)

    assert [record["job_id"] for record in result["jobs"]] == [job_ids[2], job_ids[1]]
