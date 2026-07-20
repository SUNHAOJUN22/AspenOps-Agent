from __future__ import annotations

from pathlib import Path


def main() -> None:
    script = Path(__file__)
    path = Path("src/aspenops_nexus/scheduler.py")
    text = path.read_text(encoding="utf-8")

    old_helper = '''    def _commit_bundle(
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
    new_helper = '''    def _commit_bundle(
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
        record = self.store.get(job_id) if committed else None
        adopted = record is not None and record.get("bundle_path") == str(bundle)
        if not adopted:
            bundle.unlink(missing_ok=True)
        return committed
'''
    adoption_guard = (
        '        adopted = record is not None and record.get("bundle_path") '
        '== str(bundle)\n'
    )
    if old_helper not in text:
        if adoption_guard not in text:
            raise RuntimeError("scheduler bundle helper anchor not found")
    else:
        text = text.replace(old_helper, new_helper, 1)

    text = text.replace(
        '''                if not self._commit_bundle(job_id, results, bundle):
                    bundle.unlink(missing_ok=True)
''',
        '''                self._commit_bundle(job_id, results, bundle)
''',
        1,
    )
    path.write_text(text, encoding="utf-8")
    script.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
