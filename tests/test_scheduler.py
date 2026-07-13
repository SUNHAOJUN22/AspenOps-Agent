import time
from pathlib import Path

from test_batch import request

from aspenops_nexus.config import Settings
from aspenops_nexus.scheduler import BackgroundScheduler


def test_background_scheduler(tmp_path: Path) -> None:
    scheduler = BackgroundScheduler(Settings(state_dir=tmp_path, max_workers=1, license_slots=1))
    job_id = scheduler.submit(request())
    deadline = time.time() + 20
    record = None
    while time.time() < deadline:
        record = scheduler.store.get(job_id)
        if record and record["status"] in {"completed", "failed"}:
            break
        time.sleep(0.1)
    scheduler.stop()
    assert record is not None
    assert record["status"] == "completed", record
    assert Path(record["bundle_path"]).exists()
