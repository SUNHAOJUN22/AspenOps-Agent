from pathlib import Path

import pytest

from aspenops.accessor import SemanticAccessor
from aspenops.backends.mock import MockBackend
from aspenops.errors import WorkerError
from aspenops.models import ValueRead, ValueWrite
from aspenops.registry import load_bundled_registry
from aspenops.worker import _dispatch, _make_backend


def test_worker_dispatch_operations(tmp_path: Path) -> None:
    backend = MockBackend()
    accessor = SemanticAccessor(backend, load_bundled_registry())
    state: dict[str, object] = {"read_only": False, "opened": False}
    case = tmp_path / "case.json"
    case.write_text("{}", encoding="utf-8")

    opened = _dispatch("open", {"path": str(case)}, backend, accessor, state)
    assert opened["opened"]
    writes = [
        ValueWrite(
            key="block.input.temperature",
            identifiers={"block": "R-101"},
            value=450,
            unit="C",
        ).model_dump(mode="json")
    ]
    assert len(_dispatch("set_many", {"writes": writes}, backend, accessor, state)) == 1
    _dispatch("reinitialize", {}, backend, accessor, state)
    run = _dispatch("run", {}, backend, accessor, state)
    assert run["state"] == "converged"
    reads = [
        ValueRead(
            key="block.output.conversion",
            identifiers={"block": "R-101"},
        ).model_dump(mode="json")
    ]
    assert _dispatch("get_many", {"reads": reads}, backend, accessor, state)[0]["value"] > 0
    evaluation = _dispatch(
        "evaluate",
        {"writes": writes, "reads": reads, "reinitialize": True},
        backend,
        accessor,
        state,
    )
    assert evaluation["run"]["state"] == "converged"
    assert _dispatch("diagnose", {}, backend, accessor, state)["path_cache_size"] >= 1
    saved = tmp_path / "saved.json"
    _dispatch("save", {"path": str(saved)}, backend, accessor, state)
    assert saved.exists()
    assert _dispatch("close", {}, backend, accessor, state) is None

    with pytest.raises(WorkerError):
        _dispatch("unknown", {}, backend, accessor, state)


def test_backend_factory_rejects_unknown() -> None:
    assert _make_backend("mock", {}).name == "mock"
    assert _make_backend("aspen_plus", {}).name == "aspen_plus"
    with pytest.raises(WorkerError):
        _make_backend("other", {})
