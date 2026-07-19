from __future__ import annotations

from pathlib import Path


def main() -> None:
    script = Path(__file__)
    path = Path("src/aspenops_nexus/scheduler.py")
    text = path.read_text(encoding="utf-8")
    old = '''            for job_id in self.store.cancellation_due(owner=self.owner):
                pool = self._active_snapshot().get(job_id)
                if pool is None:
                    continue
                events = pool.force_recycle_all("cancel_deadline")
                self.store.mark_abort_dispatched(job_id, events, owner=self.owner)
'''
    new = '''            for job_id in self.store.cancellation_due(owner=self.owner):
                due_pool = self._active_snapshot().get(job_id)
                if due_pool is None:
                    continue
                events = due_pool.force_recycle_all("cancel_deadline")
                self.store.mark_abort_dispatched(job_id, events, owner=self.owner)
'''
    if old not in text:
        raise RuntimeError("scheduler cancellation pool block not found")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    script.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
