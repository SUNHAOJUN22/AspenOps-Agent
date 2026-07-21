from __future__ import annotations

import time
from pathlib import Path

from test_optimization import document

from aspenops_nexus.cli import build_parser
from aspenops_nexus.config import Settings
from aspenops_nexus.scheduler import BackgroundScheduler


def test_cli_exposes_optimize_command() -> None:
    parser = build_parser()
    args = parser.parse_args(["optimize", "request.json"])
    assert args.command == "optimize"
    assert args.output == "var/optimization-result.json"


def test_scheduler_runs_durable_optimization(tmp_path: Path) -> None:
    scheduler = BackgroundScheduler(
        Settings(
            state_dir=tmp_path,
            max_workers=2,
            license_slots=2,
            scheduler_poll_s=0.02,
        )
    )
    job_id = scheduler.submit(document())
    deadline = time.time() + 30
    record = None
    while time.time() < deadline:
        record = scheduler.store.get(job_id)
        if record and record["status"] in {"completed", "failed", "dead_letter"}:
            break
        time.sleep(0.05)
    scheduler.stop()
    assert record is not None
    assert record["status"] == "completed", record
    assert record["results"][0]["schema"] == "aspenops.optimization-result/v1"
    assert record["results"][0]["evaluations"] == 8
    assert Path(record["bundle_path"]).exists()
