from __future__ import annotations

import statistics
from pathlib import Path
from typing import Any

import pytest
from test_benchmark_scripts import MODEL, REGISTRY, benchmark_script


def measurement(
    throughput: float,
    elapsed: float,
    *,
    marker: int,
) -> Any:
    return benchmark_script.Measurement(
        scenario="worker_matrix",
        points=10,
        workers=2,
        duplicate_ratio=0.0,
        cache_mode="cold",
        elapsed_s=elapsed,
        throughput_points_s=throughput,
        p50_point_s=marker + 0.1,
        p95_point_s=marker + 0.2,
        p99_point_s=marker + 0.3,
        rss_before=100 + marker,
        rss_after=200 + marker,
        rss_delta=100 + marker,
        ok_points=10,
        failed_points=0,
        cache_sources={f"trial-{marker}": 10},
    )


def test_measure_pool_aggregates_independent_trials_by_median(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    trials = iter(
        [
            measurement(10.0, 3.0, marker=1),
            measurement(30.0, 1.0, marker=3),
            measurement(20.0, 2.0, marker=2),
        ]
    )
    monkeypatch.setattr(benchmark_script, "_measure_pool_once", lambda **kwargs: next(trials))

    result = benchmark_script.measure_pool(
        scenario="worker_matrix",
        model_path=MODEL,
        registry_path=REGISTRY,
        points=10,
        workers=2,
        trials=3,
    )

    assert result.throughput_points_s == 20.0
    assert result.elapsed_s == 2.0
    assert result.p50_point_s == 2.1
    assert result.p95_point_s == 2.2
    assert result.p99_point_s == 2.3
    assert result.rss_before == 102
    assert result.rss_after == 202
    assert result.rss_delta == 102
    assert result.cache_sources == {"trial-2": 10}
    assert result.trial_count == 3
    assert result.elapsed_samples_s == (3.0, 1.0, 2.0)
    assert result.throughput_samples_points_s == (10.0, 30.0, 20.0)
    expected_cv = statistics.pstdev([10.0, 30.0, 20.0]) / statistics.fmean(
        [10.0, 30.0, 20.0]
    )
    assert result.throughput_cv == pytest.approx(expected_cv)


def test_measure_pool_single_trial_has_zero_cv(monkeypatch: pytest.MonkeyPatch) -> None:
    sample = measurement(15.0, 2.0, marker=1)
    monkeypatch.setattr(benchmark_script, "_measure_pool_once", lambda **kwargs: sample)
    result = benchmark_script.measure_pool(
        scenario="worker_matrix",
        model_path=MODEL,
        registry_path=REGISTRY,
        points=10,
        workers=1,
    )
    assert result.trial_count == 1
    assert result.throughput_cv == 0.0
    assert result.elapsed_samples_s == (2.0,)
    assert result.throughput_samples_points_s == (15.0,)


def test_measure_pool_rejects_nonpositive_trials() -> None:
    with pytest.raises(ValueError, match="trials must be positive"):
        benchmark_script.measure_pool(
            scenario="worker_matrix",
            model_path=MODEL,
            registry_path=REGISTRY,
            points=10,
            workers=1,
            trials=0,
        )


def test_run_matrix_selects_trial_policy_and_serializes_schema(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls: list[dict[str, Any]] = []

    def fake_measure_pool(**kwargs: Any) -> Any:
        calls.append(kwargs)
        return measurement(10.0, 1.0, marker=1)

    monkeypatch.setattr(benchmark_script, "measure_pool", fake_measure_pool)
    monkeypatch.setattr(
        benchmark_script,
        "sequential_job_measurement",
        lambda **kwargs: {"available": True},
    )

    smoke = benchmark_script.run_matrix(tmp_path, smoke=True)
    assert smoke["schema"] == "aspenops.benchmark-matrix/v3"
    assert smoke["trials"] == 1
    assert len(smoke["measurements"]) == 2
    assert {call["trials"] for call in calls} == {1}

    calls.clear()
    full = benchmark_script.run_matrix(tmp_path, smoke=False)
    assert full["trials"] == 3
    assert len(full["measurements"]) == 22
    assert {call["trials"] for call in calls} == {3}

    calls.clear()
    explicit = benchmark_script.run_matrix(tmp_path, smoke=True, trials=2)
    assert explicit["trials"] == 2
    assert {call["trials"] for call in calls} == {2}

    with pytest.raises(ValueError, match="trials must be positive"):
        benchmark_script.run_matrix(tmp_path, smoke=True, trials=0)


def test_cache_source_uses_explicit_source_then_legacy_flag() -> None:
    explicit = type("Result", (), {"cache_source": "same_batch_dedup"})()
    legacy_hit = type("Result", (), {"cache_source": None, "cache_hit": True})()
    legacy_miss = type("Result", (), {"cache_source": None, "cache_hit": False})()
    assert benchmark_script.cache_source(explicit) == "same_batch_dedup"
    assert benchmark_script.cache_source(legacy_hit) == "persistent_cache"
    assert benchmark_script.cache_source(legacy_miss) == "computed"
