from __future__ import annotations

from pathlib import Path


def replace_between(text: str, start: str, end: str, replacement: str) -> str:
    begin = text.index(start)
    finish = text.index(end, begin)
    return text[:begin] + replacement + text[finish:]


def patch_scheduler() -> None:
    path = Path("src/aspenops_nexus/scheduler.py")
    text = path.read_text(encoding="utf-8")
    recovery = '''    def _recover_after_restart(self, connection: sqlite3.Connection) -> None:
        now = _now()
        self._recover_expired(connection, now)

        cancelled = connection.execute(
            """
            SELECT job_id FROM jobs
            WHERE status IN ('claimed','running','cancelling')
              AND cancel_requested=1 AND lease_expires_at IS NULL
            """
        ).fetchall()
        connection.execute(
            """
            UPDATE jobs
            SET status='cancelled', error='service restarted during cancellation',
                error_class='service_restart', finished_at=?, updated_at=?,
                lease_owner=NULL, lease_expires_at=NULL
            WHERE status IN ('claimed','running','cancelling')
              AND cancel_requested=1 AND lease_expires_at IS NULL
            """,
            (now, now),
        )
        for row in cancelled:
            self._event(connection, str(row[0]), "cancelled_after_service_restart")

        orphaned = connection.execute(
            """
            SELECT job_id,attempt,max_attempts FROM jobs
            WHERE status IN ('claimed','running') AND cancel_requested=0
              AND lease_expires_at IS NULL
            """
        ).fetchall()
        connection.execute(
            """
            UPDATE jobs
            SET status=CASE
                    WHEN attempt < max_attempts THEN 'retry_wait'
                    ELSE 'dead_letter'
                END,
                error=CASE
                    WHEN attempt < max_attempts
                        THEN 'service restarted while job had no lease'
                    ELSE 'service restarted after final unleased attempt'
                END,
                error_class='service_restart',
                finished_at=CASE
                    WHEN attempt < max_attempts THEN NULL ELSE ?
                END,
                updated_at=?, lease_owner=NULL, lease_expires_at=NULL
            WHERE status IN ('claimed','running') AND cancel_requested=0
              AND lease_expires_at IS NULL
            """,
            (now, now),
        )
        for row in orphaned:
            attempt = int(row[1])
            max_attempts = int(row[2])
            event = (
                "service_restart"
                if attempt < max_attempts
                else "dead_letter_after_service_restart"
            )
            self._event(
                connection,
                str(row[0]),
                event,
                {"attempt": attempt, "max_attempts": max_attempts},
            )

'''
    text = replace_between(
        text,
        "    def _recover_after_restart(",
        "    def create(",
        recovery,
    )

    if "    def _commit_bundle(" not in text:
        helper = '''    def _commit_bundle(
        self,
        job_id: str,
        results: list[dict[str, Any]],
        bundle: Path,
    ) -> bool:
        if self.store.is_cancel_requested(job_id):
            return self.store.finalize_cancelled(
                job_id,
                results,
                bundle,
                owner=self.owner,
            )
        committed = self.store.complete(
            job_id,
            results,
            bundle,
            commit_token=canonical_hash(results),
            owner=self.owner,
        )
        if committed:
            return True
        if self.store.is_cancel_requested(job_id):
            return self.store.finalize_cancelled(
                job_id,
                results,
                bundle,
                owner=self.owner,
            )
        return False

'''
        marker = "    def _loop(self) -> None:\n"
        text = text.replace(marker, helper + marker, 1)

    old = '''                record = self.store.get(job_id)
                bundle_path = self.settings.state_dir / "bundles" / f"{job_id}.{self.owner}.zip"
                bundle = write_run_bundle(
                    request=request,
                    results=results,
                    output_path=bundle_path,
                )
                if record and record["cancel_requested"]:
                    committed = self.store.finalize_cancelled(
                        job_id, results, bundle, owner=self.owner
                    )
                else:
                    committed = self.store.complete(
                        job_id,
                        results,
                        bundle,
                        commit_token=canonical_hash(results),
                        owner=self.owner,
                    )
                if not committed:
                    bundle.unlink(missing_ok=True)
'''
    new = '''                bundle_path = self.settings.state_dir / "bundles" / f"{job_id}.{self.owner}.zip"
                bundle = write_run_bundle(
                    request=request,
                    results=results,
                    output_path=bundle_path,
                )
                if not self._commit_bundle(job_id, results, bundle):
                    bundle.unlink(missing_ok=True)
'''
    if old in text:
        text = text.replace(old, new, 1)
    elif "if not self._commit_bundle(job_id, results, bundle):" not in text:
        raise RuntimeError("Scheduler bundle commit block not found")
    path.write_text(text, encoding="utf-8")


def patch_legacy_tests() -> None:
    path = Path("tests/test_scheduler_edge_cases.py")
    text = path.read_text(encoding="utf-8")
    if "test_service_restart_recovers_unleased_running_job" in text:
        return
    first = text.index("def test_service_restart_recovers_running_lease")
    second = text.index("def test_service_restart_finalizes_cancelling_job", first)
    third = text.index("def test_schema_migrates_legacy_job_table", second)
    replacement = '''def test_service_restart_recovers_unleased_running_job(tmp_path: Path) -> None:
    path = tmp_path / "jobs.sqlite3"
    store = JobStore(path)
    job_id = store.create({"x": 1})
    assert store.claim_next("worker-a") is not None
    assert store.mark_running(job_id, "worker-a")
    with sqlite3.connect(path) as connection:
        connection.execute(
            "UPDATE jobs SET lease_expires_at=NULL WHERE job_id=?",
            (job_id,),
        )
    restarted = JobStore(path)
    record = restarted.get(job_id)
    assert record is not None
    assert record["status"] == "retry_wait"
    assert record["lease_owner"] is None


def test_service_restart_finalizes_unleased_cancelling_job(tmp_path: Path) -> None:
    path = tmp_path / "jobs.sqlite3"
    store = JobStore(path)
    job_id = store.create({"x": 1})
    assert store.claim_next("worker-a") is not None
    assert store.mark_running(job_id, "worker-a")
    assert store.cancel(job_id, grace_s=100)
    with sqlite3.connect(path) as connection:
        connection.execute(
            "UPDATE jobs SET lease_expires_at=NULL WHERE job_id=?",
            (job_id,),
        )
    restarted = JobStore(path)
    record = restarted.get(job_id)
    assert record is not None
    assert record["status"] == "cancelled"
    assert "restart" in record["error"]


'''
    path.write_text(text[:first] + replacement + text[third:], encoding="utf-8")


def main() -> None:
    patch_scheduler()
    patch_legacy_tests()
    Path(__file__).unlink(missing_ok=True)


if __name__ == "__main__":
    main()
