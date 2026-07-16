from importlib.resources import as_file, files
from pathlib import Path

import pytest

from aspenops_nexus.batch import dry_run_document, expand_batch_document, run_batch_file
from aspenops_nexus.config import Settings


def resource(name: str) -> Path:
    with as_file(files("aspenops_nexus.data").joinpath(name)) as path:
        return Path(path)


def base_request() -> dict:
    return {
        "model_path": str(resource("mock-case.json")),
        "registry_path": str(resource("node-registry.json")),
        "points": [{}],
        "reads": [],
    }


def test_default_backend_is_shared_by_request_identity() -> None:
    requests = expand_batch_document(base_request(), default_backend="hysys")
    assert [request.backend for request in requests] == ["hysys"]


def test_unknown_batch_and_point_fields_fail_closed() -> None:
    with pytest.raises(ValueError, match="Unknown fields in Batch request"):
        expand_batch_document({**base_request(), "workres": 2})
    with pytest.raises(ValueError, match="Unknown fields in Point 0"):
        expand_batch_document({**base_request(), "points": [{"writse": []}]})


def test_legacy_boolean_is_not_coerced_from_string() -> None:
    with pytest.raises(ValueError, match="Boolean"):
        expand_batch_document({**base_request(), "reinitialize": "false"})


def test_point_and_operation_limits_are_hard_failures() -> None:
    with pytest.raises(ValueError, match="points count"):
        expand_batch_document(
            {**base_request(), "points": [{}, {}]},
            max_points=1,
        )
    with pytest.raises(ValueError, match="semantic operations"):
        expand_batch_document(
            {
                **base_request(),
                "reads": [
                    {
                        "key": "stream.output.purity",
                        "identifiers": {"stream": "PRODUCT"},
                        "unit": "fraction",
                    }
                ],
            },
            max_operations_per_request=1,
        )


def test_worker_count_is_strict_and_never_silently_clamped(tmp_path: Path) -> None:
    settings = Settings(state_dir=tmp_path, max_workers=1, license_slots=1)
    with pytest.raises(ValueError, match="integer"):
        dry_run_document({**base_request(), "workers": True}, settings)
    with pytest.raises(ValueError, match="exceeds effective worker cap"):
        dry_run_document({**base_request(), "workers": 2}, settings)


def test_request_file_size_and_duplicate_json_keys_are_rejected(tmp_path: Path) -> None:
    oversized = tmp_path / "oversized.json"
    oversized.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="maximum"):
        run_batch_file(oversized, Settings(state_dir=tmp_path, max_request_bytes=1))

    duplicate = tmp_path / "duplicate.json"
    duplicate.write_text(
        '{"model_path":"a","model_path":"b","registry_path":"c"}',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="duplicate JSON key"):
        run_batch_file(duplicate, Settings(state_dir=tmp_path))
