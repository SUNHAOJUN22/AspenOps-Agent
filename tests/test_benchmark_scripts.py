from pathlib import Path

import pytest

from aspenops_nexus.hashing import canonical_hash
from scripts.compare_benchmarks import format_change, key, percent_change, regression_label
from scripts.run_benchmark_matrix import build_requests, percentile

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "src/aspenops_nexus/data/mock-case.json"
REGISTRY = ROOT / "src/aspenops_nexus/data/node-registry.json"


def physical_hashes(points: int, duplicate_ratio: float, *, failing: bool = False) -> set[str]:
    requests = build_requests(
        model_path=MODEL,
        registry_path=REGISTRY,
        points=points,
        duplicate_ratio=duplicate_ratio,
        failing=failing,
    )
    return {canonical_hash(request.physical_identity()) for request in requests}


def test_zero_duplicate_benchmark_requests_are_physically_unique() -> None:
    assert len(physical_hashes(1000, 0.0)) == 1000


def test_duplicate_ratio_controls_unique_request_count_exactly() -> None:
    assert len(physical_hashes(100, 0.25)) == 75
    assert len(physical_hashes(100, 0.75)) == 25


def test_nonconvergence_inputs_remain_unique_and_above_failure_threshold() -> None:
    requests = build_requests(
        model_path=MODEL,
        registry_path=REGISTRY,
        points=20,
        failing=True,
    )
    assert len({canonical_hash(request.physical_identity()) for request in requests}) == 20
    temperatures = [float(request.writes[0].value) for request in requests]
    assert min(temperatures) > 220.0
    assert max(temperatures) <= 500.0


@pytest.mark.parametrize(
    ("points", "duplicate_ratio", "message"),
    [
        (0, 0.0, "points must be positive"),
        (1, -0.1, "duplicate_ratio must be in"),
        (1, 1.0, "duplicate_ratio must be in"),
    ],
)
def test_request_builder_rejects_invalid_dimensions(
    points: int,
    duplicate_ratio: float,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        build_requests(
            model_path=MODEL,
            registry_path=REGISTRY,
            points=points,
            duplicate_ratio=duplicate_ratio,
        )


def test_percentile_handles_empty_and_bounded_probabilities() -> None:
    assert percentile([], 0.95) == 0.0
    assert percentile([1.0, 2.0, 3.0], -1.0) == 1.0
    assert percentile([1.0, 2.0, 3.0], 2.0) == 3.0


def test_benchmark_identity_includes_duplicate_ratio_and_cache_mode() -> None:
    item = {
        "scenario": "duplicate_ratio",
        "points": 100,
        "workers": 4,
        "duplicate_ratio": 0.75,
        "cache_mode": "cold",
    }
    assert key(item) == ("duplicate_ratio", 100, 4, 0.75, "cold")


def test_change_formatting_and_regression_labels() -> None:
    assert percent_change(100.0, 120.0) == 20.0
    assert percent_change(0.0, 1.0) is None
    assert format_change(None) == "n/a"
    assert format_change(-7.5) == "-7.50%"
    assert regression_label(-5.01, 0.0) == "throughput regression >5%"
    assert regression_label(0.0, 5.01) == "P95 regression >5%"
    assert regression_label(-5.0, 5.0) == "none"
