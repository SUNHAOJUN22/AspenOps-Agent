from __future__ import annotations

from collections.abc import Callable

import pytest

from aspenops_nexus.convergence import (
    ConvergenceState,
    IdleObservation,
    classify_convergence,
    normalize_running_flag,
    poll_engine_idle,
)


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


def sequence_reader(values: list[bool | None]) -> Callable[[], bool | None]:
    remaining = iter(values)
    last = values[-1]

    def read() -> bool | None:
        nonlocal last
        last = next(remaining, last)
        return last

    return read


def test_running_flag_normalization_is_explicit_and_com_compatible() -> None:
    accepted = [
        (True, True),
        (False, False),
        (-1, True),
        (1, True),
        (0, False),
        ("TRUE", True),
        ("false", False),
        ("running", True),
        ("idle", False),
        ("not running", False),
    ]
    for value, expected in accepted:
        assert normalize_running_flag(value) is expected

    for value in (2, -2, float("nan"), float("inf"), "unknown", object(), None):
        assert normalize_running_flag(value) is None


def test_poll_requires_a_stable_idle_window() -> None:
    clock = FakeClock()
    result = poll_engine_idle(
        sequence_reader([True, False, False]),
        timeout_s=1.0,
        poll_interval_s=0.1,
        stable_samples=2,
        clock=clock.monotonic,
        sleeper=clock.sleep,
    )
    assert result.engine_idle is True
    assert result.samples == 3
    assert result.state is ConvergenceState.UNKNOWN


def test_poll_fails_closed_after_async_startup_window_without_running() -> None:
    clock = FakeClock()
    result = poll_engine_idle(
        sequence_reader([False]),
        timeout_s=1200.0,
        startup_timeout_s=0.3,
        poll_interval_s=0.1,
        stable_samples=2,
        require_running_observation=True,
        clock=clock.monotonic,
        sleeper=clock.sleep,
    )
    assert result.state is ConvergenceState.TIMEOUT
    assert result.engine_idle is True
    assert result.samples == 4
    assert abs(result.elapsed_s - 0.3) < 1e-12
    assert result.error == "engine never reported running within the startup confirmation window"


def test_poll_allows_delayed_async_start_before_startup_deadline() -> None:
    clock = FakeClock()
    result = poll_engine_idle(
        sequence_reader([False, False, True, False, False]),
        timeout_s=1200.0,
        startup_timeout_s=0.3,
        poll_interval_s=0.1,
        stable_samples=2,
        require_running_observation=True,
        clock=clock.monotonic,
        sleeper=clock.sleep,
    )
    assert result.state is ConvergenceState.UNKNOWN
    assert result.engine_idle is True
    assert result.samples == 5
    assert abs(result.elapsed_s - 0.4) < 1e-12


def test_poll_rejects_first_async_start_observed_after_startup_deadline() -> None:
    clock = FakeClock()
    idle = poll_engine_idle(
        sequence_reader([False, False, False, True, False, False]),
        timeout_s=1200.0,
        startup_timeout_s=0.25,
        poll_interval_s=0.1,
        stable_samples=2,
        require_running_observation=True,
        clock=clock.monotonic,
        sleeper=clock.sleep,
    )
    evidence = classify_convergence(
        engine_returned=True,
        idle=idle,
        status_nodes=[{"path": "status", "value": "Run completed and converged"}],
        messages=[],
        source="fake-aspen",
    )
    assert idle.state is ConvergenceState.TIMEOUT
    assert idle.engine_idle is False
    assert idle.samples == 4
    assert abs(idle.elapsed_s - 0.3) < 1e-12
    assert evidence.state is ConvergenceState.TIMEOUT


def test_poll_times_out_when_engine_never_stops() -> None:
    clock = FakeClock()
    result = poll_engine_idle(
        lambda: True,
        timeout_s=0.3,
        poll_interval_s=0.1,
        stable_samples=2,
        clock=clock.monotonic,
        sleeper=clock.sleep,
    )
    assert result.state is ConvergenceState.TIMEOUT
    assert result.engine_idle is False


def test_poll_returns_unknown_when_runtime_exposes_no_state() -> None:
    clock = FakeClock()
    result = poll_engine_idle(
        lambda: None,
        timeout_s=0.2,
        poll_interval_s=0.1,
        stable_samples=2,
        clock=clock.monotonic,
        sleeper=clock.sleep,
    )
    assert result.state is ConvergenceState.UNKNOWN
    assert result.engine_idle is None


def test_poll_discards_non_boolean_reader_values() -> None:
    clock = FakeClock()

    def invalid_reader() -> bool | None:
        return "false"  # type: ignore[return-value]

    result = poll_engine_idle(
        invalid_reader,
        timeout_s=0.2,
        poll_interval_s=0.1,
        stable_samples=1,
        clock=clock.monotonic,
        sleeper=clock.sleep,
    )
    assert result.state is ConvergenceState.UNKNOWN
    assert result.engine_idle is None


def test_poll_reports_status_access_errors() -> None:
    def fail() -> bool | None:
        raise RuntimeError("status unavailable")

    result = poll_engine_idle(
        fail,
        timeout_s=1.0,
        poll_interval_s=0.1,
        stable_samples=2,
    )
    assert result.state is ConvergenceState.ERROR
    assert result.error == "RuntimeError: status unavailable"


@pytest.mark.parametrize(
    ("read_duration_s", "expected"),
    [
        (0.2, ConvergenceState.UNKNOWN),
        (0.9, ConvergenceState.TIMEOUT),
        (2.0, ConvergenceState.TIMEOUT),
    ],
    ids=["before-deadline", "at-deadline", "after-deadline"],
)
def test_stable_idle_observation_must_arrive_before_total_deadline(
    read_duration_s: float, expected: ConvergenceState
) -> None:
    clock = FakeClock()
    reads = 0

    def read_running() -> bool:
        nonlocal reads
        reads += 1
        if reads == 1:
            return True
        clock.sleep(read_duration_s)
        return False

    idle = poll_engine_idle(
        read_running,
        timeout_s=1.0,
        poll_interval_s=0.1,
        stable_samples=1,
        require_running_observation=True,
        startup_timeout_s=0.5,
        clock=clock.monotonic,
        sleeper=clock.sleep,
    )
    assert idle.state is expected
    assert idle.engine_idle is True
    assert idle.samples == 2
    assert idle.elapsed_s == pytest.approx(0.1 + read_duration_s)


def test_late_idle_without_a_running_sample_is_also_a_timeout() -> None:
    clock = FakeClock()

    def slow_idle() -> bool:
        clock.sleep(2.0)
        return False

    idle = poll_engine_idle(
        slow_idle,
        timeout_s=1.0,
        poll_interval_s=0.1,
        stable_samples=1,
        clock=clock.monotonic,
        sleeper=clock.sleep,
    )
    assert idle.state is ConvergenceState.TIMEOUT
    assert idle.engine_idle is True
    assert idle.elapsed_s == 2.0


def test_unstable_idle_after_total_deadline_is_a_timeout() -> None:
    clock = FakeClock()

    def slow_idle() -> bool:
        clock.sleep(1.1)
        return False

    idle = poll_engine_idle(
        slow_idle,
        timeout_s=1.0,
        poll_interval_s=0.1,
        stable_samples=2,
        clock=clock.monotonic,
        sleeper=clock.sleep,
    )
    evidence = classify_convergence(
        engine_returned=True,
        idle=idle,
        status_nodes=[{"path": "status", "value": "Run completed and converged"}],
        messages=[],
        source="Aspen",
    )
    assert idle.state is ConvergenceState.TIMEOUT
    assert idle.engine_idle is None
    assert evidence.state is ConvergenceState.TIMEOUT
    assert set(evidence.positive_markers) == {"completed", "converged"}
    assert idle.samples == 1
    assert idle.elapsed_s == pytest.approx(1.1)


def idle_observation() -> IdleObservation:
    return IdleObservation(
        state=ConvergenceState.UNKNOWN,
        engine_idle=True,
        elapsed_s=0.2,
        samples=3,
    )


def test_explicit_success_and_idle_engine_converge() -> None:
    evidence = classify_convergence(
        engine_returned=True,
        idle=idle_observation(),
        status_nodes=[{"path": "status", "value": "Run completed and converged"}],
        messages=[],
        source="fake-aspen",
    )
    assert evidence.state is ConvergenceState.CONVERGED
    assert evidence.positive_markers == ("converged", "completed")


def test_negative_evidence_dominates_embedded_positive_word() -> None:
    evidence = classify_convergence(
        engine_returned=True,
        idle=idle_observation(),
        status_nodes=[{"path": "status", "value": "not converged"}],
        messages=["run failed"],
        source="fake-aspen",
    )
    assert evidence.state is ConvergenceState.NOT_CONVERGED
    assert "not_converged" in evidence.negative_markers
    assert "converged" in evidence.positive_markers


def test_idle_without_explicit_success_fails_closed() -> None:
    evidence = classify_convergence(
        engine_returned=True,
        idle=idle_observation(),
        status_nodes=[],
        messages=[],
        source="fake-aspen",
    )
    assert evidence.state is ConvergenceState.UNKNOWN


def test_timeout_and_engine_error_are_preserved() -> None:
    timeout = IdleObservation(
        state=ConvergenceState.TIMEOUT,
        engine_idle=False,
        elapsed_s=10.0,
        samples=100,
    )
    timeout_evidence = classify_convergence(
        engine_returned=True,
        idle=timeout,
        status_nodes=[{"value": "converged"}],
        messages=[],
        source="fake-aspen",
    )
    assert timeout_evidence.state is ConvergenceState.TIMEOUT

    error_evidence = classify_convergence(
        engine_returned=False,
        idle=idle_observation(),
        status_nodes=[{"value": "converged"}],
        messages=[],
        source="fake-aspen",
    )
    assert error_evidence.state is ConvergenceState.ERROR
