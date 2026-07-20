from __future__ import annotations

import math

import pytest

from aspenops_nexus.models import (
    BalanceSpec,
    BalanceTerm,
    ConstraintSpec,
    EvaluationRequest,
    VariableRead,
    VariableWrite,
)


@pytest.mark.parametrize("value", [True, False, float("nan"), float("inf"), -float("inf")])
def test_timeout_requires_finite_non_boolean_number(value: object) -> None:
    with pytest.raises(ValueError, match="timeout_s must be a finite positive number"):
        EvaluationRequest.from_dict(
            {
                "model_path": "model.json",
                "registry_path": "registry.json",
                "timeout_s": value,
            }
        )


def test_request_rejects_non_string_paths_and_non_object_metadata() -> None:
    with pytest.raises(ValueError, match="model_path must be a non-empty string"):
        EvaluationRequest.from_dict(
            {"model_path": ["model.json"], "registry_path": "registry.json"}
        )
    with pytest.raises(ValueError, match="metadata must be an object"):
        EvaluationRequest.from_dict(
            {
                "model_path": "model.json",
                "registry_path": "registry.json",
                "metadata": [],
            }
        )


def test_write_requires_nonempty_key_object_identifiers_and_scalar_value() -> None:
    with pytest.raises(ValueError, match="write key must be a non-empty string"):
        VariableWrite.from_dict({"key": [], "value": 1})
    with pytest.raises(ValueError, match="write identifiers must be an object"):
        VariableWrite.from_dict({"key": "x", "identifiers": [], "value": 1})
    with pytest.raises(ValueError, match="write value must be a finite scalar JSON value"):
        VariableWrite.from_dict({"key": "x", "value": {"bad": True}})
    with pytest.raises(ValueError, match="write value must be a finite scalar JSON value"):
        VariableWrite.from_dict({"key": "x", "value": float("nan")})


def test_read_required_is_strict_boolean() -> None:
    with pytest.raises(ValueError, match="read required must be a boolean"):
        VariableRead.from_dict({"key": "x", "required": "false"})
    assert VariableRead.from_dict({"key": "x", "required": False}).required is False


@pytest.mark.parametrize("field", ["value", "tolerance"])
def test_constraint_numbers_are_finite_and_not_boolean(field: str) -> None:
    payload: dict[str, object] = {"key": "x", "value": 1.0, field: float("nan")}
    with pytest.raises(ValueError, match=f"constraint {field} must be a finite number"):
        ConstraintSpec.from_dict(payload)
    payload[field] = True
    with pytest.raises(ValueError, match=f"constraint {field} must be a finite number"):
        ConstraintSpec.from_dict(payload)


def test_balance_contract_rejects_nonfinite_numbers_and_nonarray_terms() -> None:
    with pytest.raises(ValueError, match="balance terms must be an array"):
        BalanceSpec.from_dict({"name": "mass", "terms": {"bad": True}})
    with pytest.raises(ValueError, match="balance coefficient must be a finite number"):
        BalanceTerm.from_dict({"key": "x", "coefficient": float("inf")})
    with pytest.raises(ValueError, match="balance expected must be a finite number"):
        BalanceSpec.from_dict(
            {
                "name": "mass",
                "terms": [{"key": "x"}],
                "expected": float("nan"),
            }
        )
    with pytest.raises(ValueError, match="balance floor must be a finite non-negative number"):
        BalanceSpec.from_dict(
            {
                "name": "mass",
                "terms": [{"key": "x"}],
                "floor": float("inf"),
            }
        )


def test_valid_request_remains_round_trippable_and_finite() -> None:
    request = EvaluationRequest.from_dict(
        {
            "model_path": "model.json",
            "registry_path": "registry.json",
            "backend": "mock",
            "writes": [
                {
                    "key": "stream.input.temperature",
                    "identifiers": {"stream": "FEED"},
                    "value": 80.0,
                    "unit": "C",
                }
            ],
            "reads": [
                {
                    "key": "stream.output.purity",
                    "identifiers": {"stream": "PRODUCT"},
                    "required": True,
                }
            ],
            "timeout_s": 12.5,
            "metadata": {"source": "test"},
        }
    )
    assert math.isfinite(request.timeout_s)
    assert EvaluationRequest.from_dict(request.to_dict()) == request
