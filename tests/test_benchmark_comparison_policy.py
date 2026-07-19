from __future__ import annotations

from typing import Any

from test_benchmark_scripts import compare_script


def item(
    *,
    points: int = 100,
    workers: int = 4,
    trials: int = 3,
    coefficient: float = 0.01,
) -> dict[str, Any]:
    return {
        "scenario": "worker_matrix",
        "points": points,
        "workers": workers,
        "duplicate_ratio": 0.0,
        "cache_mode": "cold",
        "trial_count": trials,
        "throughput_cv": coefficient,
    }


def test_measurement_stability_requires_repeats_low_cv_and_steady_load() -> None:
    assert compare_script.measurement_stability(item()) == "stable"
    assert compare_script.measurement_stability(item(trials=1)) == "insufficient-trials"
    assert compare_script.measurement_stability(item(coefficient=0.051)) == "unstable-cv"
    assert compare_script.measurement_stability(item(points=1, workers=4)) == (
        "startup-sensitive"
    )
    assert compare_script.measurement_stability(item(points=10, workers=8)) == (
        "startup-sensitive"
    )


def test_stable_regression_is_gated() -> None:
    baseline = item()
    candidate = item()
    assessment = compare_script.regression_assessment(
        baseline,
        candidate,
        -5.1,
        0.0,
    )
    assert assessment == "throughput regression >5%"
    assert compare_script.is_stable_regression(
        baseline,
        candidate,
        -5.1,
        0.0,
    ) is True


def test_noise_sensitive_regression_remains_visible_but_not_gated() -> None:
    baseline = item(points=1, workers=4)
    candidate = item(points=1, workers=4)
    assessment = compare_script.regression_assessment(
        baseline,
        candidate,
        -10.0,
        0.0,
    )
    assert assessment == (
        "throughput regression >5%; not-gated "
        "(startup-sensitive/startup-sensitive)"
    )
    assert compare_script.is_stable_regression(
        baseline,
        candidate,
        -10.0,
        0.0,
    ) is False


def test_high_cv_or_insufficient_trials_are_not_gated() -> None:
    stable = item()
    unstable = item(coefficient=0.1)
    single = item(trials=1)
    assert "unstable-cv" in compare_script.regression_assessment(
        stable,
        unstable,
        0.0,
        6.0,
    )
    assert "insufficient-trials" in compare_script.regression_assessment(
        single,
        stable,
        -6.0,
        0.0,
    )
    assert compare_script.is_stable_regression(stable, unstable, 0.0, 6.0) is False
    assert compare_script.is_stable_regression(single, stable, -6.0, 0.0) is False


def test_no_regression_bypasses_stability_classification() -> None:
    baseline = item(trials=1, coefficient=0.5)
    candidate = item(points=1, workers=8, trials=1, coefficient=0.5)
    assert compare_script.regression_assessment(
        baseline,
        candidate,
        -5.0,
        5.0,
    ) == "none"
    assert compare_script.is_stable_regression(
        baseline,
        candidate,
        -5.0,
        5.0,
    ) is False
