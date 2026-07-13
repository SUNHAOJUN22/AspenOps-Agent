import pytest

from aspenops_nexus.models import EvaluationRequest

BASE = {
    "model_path": "case.json",
    "registry_path": "registry.json",
    "backend": "mock",
    "writes": [],
    "reads": [],
}


def test_legacy_reinitialize_maps_to_reset_mode() -> None:
    request = EvaluationRequest.from_dict({**BASE, "reinitialize": False})
    assert request.reset_mode == "warm_start"
    assert request.reinitialize is False


def test_invalid_backend_and_timeout_are_rejected() -> None:
    with pytest.raises(ValueError):
        EvaluationRequest.from_dict({**BASE, "backend": "unknown"})
    with pytest.raises(ValueError):
        EvaluationRequest.from_dict({**BASE, "timeout_s": 0})


def test_metadata_is_excluded_from_physical_identity() -> None:
    first = EvaluationRequest.from_dict({**BASE, "metadata": {"label": "a"}})
    second = EvaluationRequest.from_dict({**BASE, "metadata": {"label": "b"}})
    assert first.physical_identity() == second.physical_identity()
