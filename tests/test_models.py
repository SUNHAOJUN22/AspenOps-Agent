import math

import pytest

from aspenops_nexus.models import BalanceSpec, ConstraintSpec, EvaluationRequest

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
    with pytest.raises(ValueError):
        EvaluationRequest.from_dict({**BASE, "timeout_s": math.nan})
    with pytest.raises(ValueError):
        EvaluationRequest.from_dict({**BASE, "timeout_s": math.inf})


def test_metadata_is_excluded_from_physical_identity() -> None:
    first = EvaluationRequest.from_dict({**BASE, "metadata": {"label": "a"}})
    second = EvaluationRequest.from_dict({**BASE, "metadata": {"label": "b"}})
    assert first.physical_identity() == second.physical_identity()


@pytest.mark.parametrize(
    "field",
    [
        {"value": math.nan},
        {"tolerance": math.inf},
        {"scale": 0.0},
        {"scale": math.nan},
        {"weight": -1.0},
    ],
)
def test_constraint_numeric_domain_is_finite_and_scaled(field: dict[str, float]) -> None:
    data = {
        "key": "x",
        "identifiers": {},
        "operator": "<=",
        "value": 1.0,
        **field,
    }
    with pytest.raises(ValueError):
        ConstraintSpec.from_dict(data)


def test_balance_requires_finite_values_and_positive_floor() -> None:
    term = {"key": "x", "identifiers": {}, "coefficient": 1.0, "unit": "kg/h"}
    with pytest.raises(ValueError):
        BalanceSpec.from_dict({"name": "b", "terms": [term], "floor": 0.0})
    with pytest.raises(ValueError):
        BalanceSpec.from_dict({"name": "b", "terms": [term], "expected": math.nan})
    with pytest.raises(ValueError):
        BalanceSpec.from_dict(
            {
                "name": "b",
                "terms": [{**term, "coefficient": math.inf}],
            }
        )
