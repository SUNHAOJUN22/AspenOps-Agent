from pathlib import Path

import pytest

from aspenops_nexus.backends.aspen_plus import AspenPlusBackend
from aspenops_nexus.backends.factory import create_backend
from aspenops_nexus.backends.hysys import HysysBackend
from aspenops_nexus.backends.mock import MockBackend
from aspenops_nexus.benchmark import benchmark_worker_matrix
from aspenops_nexus.policy import Policy, PolicyError

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "src/aspenops_nexus/data/mock-case.json"
REGISTRY = ROOT / "src/aspenops_nexus/data/node-registry.json"


@pytest.mark.parametrize(
    ("name", "backend_type"),
    [
        (" mock ", MockBackend),
        ("aspen", AspenPlusBackend),
        ("ASPEN_PLUS", AspenPlusBackend),
        ("aspenplus", AspenPlusBackend),
        ("hysys", HysysBackend),
    ],
)
def test_backend_factory_normalizes_supported_aliases(
    name: str,
    backend_type: type[MockBackend | AspenPlusBackend | HysysBackend],
) -> None:
    assert isinstance(create_backend(name), backend_type)


def test_backend_factory_rejects_unknown_backend() -> None:
    with pytest.raises(ValueError, match="Unknown backend"):
        create_backend("unrestricted-com")


def test_policy_without_roots_returns_resolved_path(tmp_path: Path) -> None:
    candidate = tmp_path / "models" / "case.json"
    assert Policy("default", ()).assert_path(candidate) == candidate.resolve()


def test_policy_allows_descendant_and_rejects_sibling(tmp_path: Path) -> None:
    allowed = (tmp_path / "allowed").resolve()
    policy = Policy("default", (allowed,))

    assert policy.assert_path(allowed / "case.json") == (allowed / "case.json").resolve()
    with pytest.raises(PolicyError, match="outside ASPENOPS_ALLOWED_ROOTS"):
        policy.assert_path(tmp_path / "other" / "case.json")


def test_policy_enforces_readonly_and_enhanced_modes() -> None:
    with pytest.raises(PolicyError, match="Writes are disabled"):
        Policy("readonly", ()).assert_writes_allowed()
    Policy("default", ()).assert_writes_allowed()

    with pytest.raises(PolicyError, match="requires ASPENOPS_MODE=enhanced"):
        Policy("default", ()).assert_enhanced()
    Policy("enhanced", ()).assert_enhanced()


@pytest.mark.parametrize(
    ("points", "workers", "message"),
    [
        (0, [1], "points must be positive"),
        (1, [], "worker_candidates must not be empty"),
        (1, [0], "worker candidates must be positive"),
    ],
)
def test_benchmark_rejects_invalid_matrix(
    tmp_path: Path,
    points: int,
    workers: list[int],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        benchmark_worker_matrix(
            model_path=MODEL,
            registry_path=REGISTRY,
            points=points,
            worker_candidates=workers,
            state_dir=tmp_path,
        )


def test_benchmark_runs_worker_matrix_and_cleans_cache_dirs(tmp_path: Path) -> None:
    result = benchmark_worker_matrix(
        model_path=MODEL,
        registry_path=REGISTRY,
        points=2,
        worker_candidates=[1, 2],
        state_dir=tmp_path,
    )

    assert result["kind"] == "portable_mock_worker_matrix"
    assert result["points"] == 2
    assert result["recommended_workers"] in {1, 2}
    assert [item["workers"] for item in result["measurements"]] == [1, 2]
    assert all(item["ok_points"] == 2 for item in result["measurements"])
    assert all(item["throughput_points_s"] > 0 for item in result["measurements"])
    assert list(tmp_path.iterdir()) == []
