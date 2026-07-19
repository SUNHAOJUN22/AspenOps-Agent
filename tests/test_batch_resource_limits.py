from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from aspenops_nexus import batch
from aspenops_nexus.batch import dry_run_document, expand_batch_document, run_batch_document
from aspenops_nexus.config import Settings
from aspenops_nexus.policy import PolicyError

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "src/aspenops_nexus/data/mock-case.json"
REGISTRY = ROOT / "src/aspenops_nexus/data/node-registry.json"


def document(*, points: int = 1, workers: Any = 1) -> dict[str, Any]:
    return {
        "backend": "mock",
        "model_path": str(MODEL),
        "registry_path": str(REGISTRY),
        "workers": workers,
        "points": [{} for _ in range(points)],
        "reads": [
            {
                "key": "stream.output.purity",
                "identifiers": {"stream": "PRODUCT"},
                "unit": "fraction",
            }
        ],
    }


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("reads", {}, "reads must be a list"),
        ("constraints", {}, "constraints must be a list"),
        ("balances", {}, "balances must be a list"),
        ("base_writes", {}, "base_writes must be a list"),
        ("metadata", [], "metadata must be a JSON object"),
        ("points", {}, "points must be a list"),
    ],
)
def test_batch_rejects_invalid_root_collection_shapes(
    field: str,
    value: Any,
    message: str,
) -> None:
    request = document()
    request[field] = value
    with pytest.raises(ValueError, match=message):
        expand_batch_document(request)


def test_batch_rejects_invalid_point_shapes_and_missing_paths() -> None:
    request = document()
    request["points"] = [{"writes": {}, "metadata": []}]
    with pytest.raises(ValueError, match=r"points\[0\]\.writes must be a list"):
        expand_batch_document(request)

    missing = document()
    missing.pop("model_path")
    with pytest.raises(ValueError, match="missing required fields: model_path"):
        expand_batch_document(missing)


@pytest.mark.parametrize("workers", [True, False, 0, -1, 1.5, "2"])
def test_batch_rejects_nonpositive_or_noninteger_worker_requests(workers: Any) -> None:
    with pytest.raises(ValueError, match="workers must"):
        dry_run_document(document(workers=workers), Settings())


def test_batch_caps_workers_and_reports_request_size(tmp_path: Path) -> None:
    validation = dry_run_document(
        document(workers=8),
        Settings(state_dir=tmp_path, max_workers=4, license_slots=2),
    )
    assert validation["requested_workers"] == 8
    assert validation["effective_workers"] == 2
    assert validation["effective_worker_cap"] == 2
    assert validation["request_bytes"] > 0


def test_batch_enforces_point_operation_and_byte_budgets(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="2 points; limit is 1"):
        dry_run_document(
            document(points=2),
            Settings(state_dir=tmp_path, max_batch_points=1),
        )

    with pytest.raises(ValueError, match="2 semantic operations; limit is 1"):
        dry_run_document(
            document(points=2),
            Settings(state_dir=tmp_path, max_semantic_operations=1),
        )

    with pytest.raises(ValueError, match="bytes; limit is 10"):
        dry_run_document(
            document(),
            Settings(state_dir=tmp_path, max_request_bytes=10),
        )


def test_batch_rejects_nonfinite_or_non_json_request_values(tmp_path: Path) -> None:
    nonfinite = document()
    nonfinite["metadata"] = {"bad": float("nan")}
    with pytest.raises(ValueError, match="finite JSON-compatible"):
        dry_run_document(nonfinite, Settings(state_dir=tmp_path))

    non_json = document()
    non_json["metadata"] = {"bad": object()}
    with pytest.raises(ValueError, match="finite JSON-compatible"):
        dry_run_document(non_json, Settings(state_dir=tmp_path))


def test_real_simulator_requires_explicit_allowed_roots(tmp_path: Path) -> None:
    request = document()
    request["backend"] = "aspen_plus"
    with pytest.raises(PolicyError, match="require ASPENOPS_ALLOWED_ROOTS"):
        dry_run_document(request, Settings(state_dir=tmp_path))

    validation = dry_run_document(
        request,
        Settings(state_dir=tmp_path, allowed_roots=(ROOT,)),
    )
    assert validation["ok"] is True


def test_run_batch_prepares_request_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0
    original = batch._prepare_batch_document

    def prepare(data: dict[str, Any], settings: Settings) -> Any:
        nonlocal calls
        calls += 1
        return original(data, settings)

    monkeypatch.setattr(batch, "_prepare_batch_document", prepare)
    monkeypatch.setattr(
        batch,
        "_evaluate_with_new_pool",
        lambda **kwargs: [{"ok": True, "workers": kwargs["workers"]}],
    )
    result = run_batch_document(document(workers=4), Settings(state_dir=tmp_path))
    assert calls == 1
    assert result == [{"ok": True, "workers": 1}]
