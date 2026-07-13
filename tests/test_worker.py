from pathlib import Path

import pytest

from aspenops.errors import WorkerError, WorkerTimeout
from aspenops.models import RunReport, RunState, ValueRead, ValueResult, ValueWrite
from aspenops.worker import WorkerClient


def test_worker_full_lifecycle(tmp_path: Path) -> None:
    case = tmp_path / "case.json"
    case.write_text("{}", encoding="utf-8")
    with WorkerClient("mock", timeout_s=10) as worker:
        worker.call("open", {"path": str(case)})
        writes = [
            ValueWrite(
                key="block.input.temperature",
                identifiers={"block": "R-101"},
                value=445,
                unit="C",
            ).model_dump(mode="json")
        ]
        worker.call("set_many", {"writes": writes, "atomic": True})
        run = RunReport.model_validate(worker.call("run"))
        assert run.state == RunState.CONVERGED
        reads = [
            ValueRead(
                key="block.output.conversion",
                identifiers={"block": "R-101"},
                unit="fraction",
            ).model_dump(mode="json")
        ]
        values = [
            ValueResult.model_validate(item) for item in worker.call("get_many", {"reads": reads})
        ]
        assert float(values[0].value) > 0.5
        diagnosis = worker.call("diagnose")
        assert diagnosis["path_cache_size"] >= 2


def test_worker_timeout_terminates_process_without_implicit_restart(tmp_path: Path) -> None:
    case = tmp_path / "case.json"
    case.write_text("{}", encoding="utf-8")
    worker = WorkerClient("mock", timeout_s=0.05, backend_options={"run_delay_s": 0.3})
    worker.start()
    worker.call("open", {"path": str(case)})
    with pytest.raises(WorkerTimeout):
        worker.call("run")
    assert not worker.alive
    with pytest.raises(WorkerError, match="explicit session recovery"):
        worker.call("diagnose")
    assert not worker.alive
