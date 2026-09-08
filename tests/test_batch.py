from importlib.resources import as_file, files
from pathlib import Path

from aspenops_nexus.batch import run_batch_document
from aspenops_nexus.config import Settings


def resource(name: str) -> Path:
    with as_file(files("aspenops_nexus.data").joinpath(name)) as path:
        return Path(path)


def request() -> dict:
    return {
        "backend": "mock",
        "model_path": str(resource("mock-case.json")),
        "registry_path": str(resource("node-registry.json")),
        "workers": 2,
        "base_writes": [
            {
                "key": "stream.input.mass_flow",
                "identifiers": {"stream": "F"},
                "value": 100,
                "unit": "kg/h",
            },
            {"key": "block.input.stages", "identifiers": {"block": "C1"}, "value": 24, "unit": "1"},
        ],
        "points": [
            {
                "writes": [
                    {
                        "key": "stream.input.temperature",
                        "identifiers": {"stream": "F"},
                        "value": 80,
                        "unit": "C",
                    },
                    {
                        "key": "block.input.reflux_ratio",
                        "identifiers": {"block": "C1"},
                        "value": 2,
                        "unit": "1",
                    },
                ]
            },
            {
                "writes": [
                    {
                        "key": "stream.input.temperature",
                        "identifiers": {"stream": "F"},
                        "value": 100,
                        "unit": "C",
                    },
                    {
                        "key": "block.input.reflux_ratio",
                        "identifiers": {"block": "C1"},
                        "value": 3,
                        "unit": "1",
                    },
                ]
            },
        ],
        "reads": [
            {"key": "stream.output.purity", "identifiers": {"stream": "P"}, "unit": "fraction"},
            {"key": "block.output.reboiler_duty", "identifiers": {"block": "C1"}, "unit": "kW"},
        ],
        "timeout_s": 10,
    }


def test_batch_runs_and_caches(tmp_path: Path) -> None:
    settings = Settings(state_dir=tmp_path, max_workers=2, license_slots=2)
    first = run_batch_document(request(), settings)
    second = run_batch_document(request(), settings)
    assert len(first) == 2
    assert all(item["ok"] for item in first)
    assert all(item["cache_hit"] for item in second)


def test_duplicate_points_ignore_nonphysical_metadata(tmp_path: Path) -> None:
    from aspenops_nexus.models import EvaluationRequest
    from aspenops_nexus.pool import CasePool

    first = EvaluationRequest.from_dict(
        {
            "model_path": str(resource("mock-case.json")),
            "registry_path": str(resource("node-registry.json")),
            "backend": "mock",
            "writes": [],
            "reads": [
                {
                    "key": "stream.output.purity",
                    "identifiers": {"stream": "PRODUCT"},
                    "unit": "fraction",
                }
            ],
            "metadata": {"point_index": 1, "label": "first"},
        }
    )
    second = EvaluationRequest.from_dict(
        {
            **first.to_dict(),
            "metadata": {"point_index": 99, "label": "duplicate"},
        }
    )
    with CasePool(
        backend_name="mock",
        model_path=resource("mock-case.json"),
        registry_path=resource("node-registry.json"),
        workers=1,
        visible=False,
        cache_path=tmp_path / "cache.sqlite3",
    ) as pool:
        results = pool.evaluate_many([first, second])

    assert results[0].request_hash == results[1].request_hash
    assert results[1].cache_hit is True


def test_worker_recycles_after_point_budget(tmp_path: Path) -> None:
    from aspenops_nexus.models import EvaluationRequest
    from aspenops_nexus.pool import CasePool

    base = {
        "model_path": str(resource("mock-case.json")),
        "registry_path": str(resource("node-registry.json")),
        "backend": "mock",
        "writes": [],
        "reads": [
            {
                "key": "stream.output.purity",
                "identifiers": {"stream": "PRODUCT"},
                "unit": "fraction",
            }
        ],
    }
    requests = [
        EvaluationRequest.from_dict({**base, "metadata": {"i": i}, "timeout_s": 10})
        for i in range(2)
    ]
    requests[1] = EvaluationRequest.from_dict(
        {
            **base,
            "writes": [
                {
                    "key": "stream.input.temperature",
                    "identifiers": {"stream": "FEED"},
                    "value": 101,
                    "unit": "C",
                }
            ],
            "timeout_s": 10,
        }
    )
    with CasePool(
        backend_name="mock",
        model_path=resource("mock-case.json"),
        registry_path=resource("node-registry.json"),
        workers=1,
        visible=False,
        cache_path=tmp_path / "cache.sqlite3",
        worker_max_points=1,
    ) as pool:
        results = pool.evaluate_many(requests)
    assert [item.diagnostics["worker"]["generation"] for item in results] == [0, 1]
