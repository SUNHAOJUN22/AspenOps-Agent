from __future__ import annotations

from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"scheduler patch anchor not found: {label}")
    return text.replace(old, new, 1)


def main() -> None:
    script = Path(__file__)
    path = Path("src/aspenops_nexus/scheduler.py")
    text = path.read_text(encoding="utf-8")

    text = replace_once(
        text,
        '''            WHERE status IN ('claimed','running','cancelling') AND cancel_requested=1
            """,
            (now, now),
''',
        '''            WHERE status IN ('claimed','running','cancelling') AND cancel_requested=1
              AND (lease_expires_at IS NULL OR lease_expires_at <= ?)
            """,
            (now, now, now),
''',
        "cancelled restart recovery lease fence",
    )
    text = replace_once(
        text,
        '''            WHERE status IN ('claimed','running') AND cancel_requested=0
            """,
            (now, now),
''',
        '''            WHERE status IN ('claimed','running') AND cancel_requested=0
              AND (lease_expires_at IS NULL OR lease_expires_at <= ?)
            """,
            (now, now, now),
''',
        "running restart recovery lease fence",
    )

    loop_anchor = "    def _loop(self) -> None:\n"
    helper = '''    def _commit_bundle(
        self,
        job_id: str,
        results: list[dict[str, Any]],
        bundle: Path,
    ) -> bool:
        if self.store.is_cancel_requested(job_id):
            committed = self.store.finalize_cancelled(
                job_id,
                results,
                bundle,
                owner=self.owner,
            )
        else:
            committed = self.store.complete(
                job_id,
                results,
                bundle,
                commit_token=canonical_hash(results),
                owner=self.owner,
            )
            if not committed and self.store.is_cancel_requested(job_id):
                committed = self.store.finalize_cancelled(
                    job_id,
                    results,
                    bundle,
                    owner=self.owner,
                )
        record = self.store.get(job_id)
        if not committed or record is None or record.get("bundle_path") != str(bundle):
            bundle.unlink(missing_ok=True)
        return committed

'''
    if "    def _commit_bundle(\n" not in text:
        index = text.index(loop_anchor)
        text = text[:index] + helper + text[index:]

    old_commit = '''                record = self.store.get(job_id)
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
    new_commit = '''                bundle_path = self.settings.state_dir / "bundles" / f"{job_id}.{self.owner}.zip"
                bundle = write_run_bundle(
                    request=request,
                    results=results,
                    output_path=bundle_path,
                )
                self._commit_bundle(job_id, results, bundle)
'''
    text = replace_once(text, old_commit, new_commit, "scheduler bundle commit flow")

    path.write_text(text, encoding="utf-8")
    script.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
