from pathlib import Path

import pytest

from aspenops.errors import WorkerTimeout
from aspenops.models import RunState, ValueRead, ValueWrite
from aspenops.pool import CasePool, decode_worker_evaluation


def test_persistent_case_pool_evaluates_points_in_original_order(tmp_path: Path) -> None:
    case = tmp_path / "case.json"
    case.write_text("{}", encoding="utf-8")
    temperatures = [420.0, 500.0, 440.0, 460.0, 400.0, 480.0]
    points = [
        [
            ValueWrite(
                key="block.input.temperature",
                identifiers={"block": "R-101"},
                value=temperature,
                unit="C",
            )
        ]
        for temperature in temperatures
    ]
    outputs = [
        ValueRead(
            key="block.output.conversion",
            identifiers={"block": "R-101"},
            unit="fraction",
        )
    ]
    with CasePool(backend="mock", case_path=case, workers=2, timeout_s=10) as pool:
        payloads = pool.evaluate_many(points, outputs)
    decoded = [decode_worker_evaluation(payload) for payload in payloads]
    assert all(run.state == RunState.CONVERGED for run, _ in decoded)
    conversions = [float(values[0].value) for _, values in decoded]
    assert conversions[1] > conversions[0]
    assert conversions[3] > conversions[2]


def test_pool_recovers_dead_worker_without_retrying_failed_point(tmp_path: Path) -> None:
    case = tmp_path / "case.json"
    case.write_text("{}", encoding="utf-8")
    point = [
        ValueWrite(
            key="block.input.temperature",
            identifiers={"block": "R-101"},
            value=440.0,
            unit="C",
        )
    ]
    outputs = [
        ValueRead(
            key="block.output.conversion",
            identifiers={"block": "R-101"},
            unit="fraction",
        )
    ]
    with CasePool(
        backend="mock",
        case_path=case,
        workers=1,
        timeout_s=0.05,
        backend_options={"run_delay_s": 0.3},
    ) as pool:
        with pytest.raises(WorkerTimeout):
            pool.evaluate_many([point], outputs)
        assert pool._clients[0].alive
        pool.backend_options["run_delay_s"] = 0.0
        pool.recover_worker(0)
        payload = pool.evaluate_many([point], outputs)[0]
        run, values = decode_worker_evaluation(payload)
        assert run.state == RunState.CONVERGED
        assert values
