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


@pytest.mark.parametrize("value", [True, False, 0, -1, float("nan"), float("inf")])
def test_timeout_requires_finite_positive_non_boolean_number(value: object) -> None:
    with pytest.raises(ValueError, match="timeout_s must be a finite positive number"):
        EvaluationRequest.from_dict(
            {
                "model_path": "model.json",
                "registry_path": "registry.json",
                "timeout_s": value,
            }
        )


def test_request_rejects_invalid_paths_metadata_backend_and_reset() -> None:
    with pytest.raises(ValueError, match="model_path must be a string"):
        EvaluationRequest.from_dict(
            {"model_path": ["model.json"], "registry_path": "registry.json"}
        )
    with pytest.raises(ValueError, match="registry_path must be a non-empty string"):
        EvaluationRequest.from_dict({"model_path": "model.json", "registry_path": " "})
    with pytest.raises(ValueError, match="metadata must be an object"):
        EvaluationRequest.from_dict(
            {
                "model_path": "model.json",
                "registry_path": "registry.json",
                "metadata": [],
            }
        )
    with pytest.raises(ValueError, match="Unsupported backend"):
        EvaluationRequest.from_dict(
            {
                "model_path": "model.json",
                "registry_path": "registry.json",
                "backend": True,
            }
        )
    with pytest.raises(ValueError, match="Unsupported reset_mode"):
        EvaluationRequest.from_dict(
            {
                "model_path": "model.json",
                "registry_path": "registry.json",
                "reset_mode": [],
            }
        )
    with pytest.raises(ValueError, match="reinitialize must be a boolean"):
        EvaluationRequest.from_dict(
            {
                "model_path": "model.json",
                "registry_path": "registry.json",
                "reinitialize": "yes",
            }
        )


def test_request_rejects_missing_fields_and_nonarray_sections() -> None:
    with pytest.raises(ValueError, match="missing model_path"):
        EvaluationRequest.from_dict({"registry_path": "registry.json"})
    with pytest.raises(ValueError, match="missing registry_path"):
        EvaluationRequest.from_dict({"model_path": "model.json"})
    for field in ("writes", "reads", "constraints", "balances"):
        with pytest.raises(ValueError, match=f"{field} must be an array"):
            EvaluationRequest.from_dict(
                {
                    "model_path": "model.json",
                    "registry_path": "registry.json",
                    field: {},
                }
            )


def test_write_requires_nonempty_key_object_identifiers_and_scalar_value() -> None:
    with pytest.raises(ValueError, match="write is missing key"):
        VariableWrite.from_dict({"value": 1})
    with pytest.raises(ValueError, match="write is missing value"):
        VariableWrite.from_dict({"key": "x"})
    with pytest.raises(ValueError, match="write key must be a string"):
        VariableWrite.from_dict({"key": [], "value": 1})
    with pytest.raises(ValueError, match="write key must be a non-empty string"):
        VariableWrite.from_dict({"key": " ", "value": 1})
    with pytest.raises(ValueError, match="write identifiers must be an object"):
        VariableWrite.from_dict({"key": "x", "identifiers": [], "value": 1})
    with pytest.raises(ValueError, match="identifier values must be finite scalar"):
        VariableWrite.from_dict(
            {"key": "x", "identifiers": {"stream": []}, "value": 1}
        )
    with pytest.raises(ValueError, match="write value must be a finite scalar JSON value"):
        VariableWrite.from_dict({"key": "x", "value": {"bad": True}})
    with pytest.raises(ValueError, match="write value must be a finite scalar JSON value"):
        VariableWrite.from_dict({"key": "x", "value": float("nan")})
    with pytest.raises(ValueError, match="write unit must be a string"):
        VariableWrite.from_dict({"key": "x", "value": 1, "unit": 5})


def test_identifier_scalars_have_deterministic_text_encoding() -> None:
    write = VariableWrite.from_dict(
        {
            "key": "x",
            "value": 1,
            "identifiers": {"flag": True, "stage": 5, "ratio": 1.5, "name": "A"},
        }
    )
    assert write.identifiers == {
        "flag": "true",
        "stage": "5",
        "ratio": "1.5",
        "name": "A",
    }


def test_read_contract_rejects_missing_key_invalid_required_and_unit() -> None:
    with pytest.raises(ValueError, match="read is missing key"):
        VariableRead.from_dict({})
    with pytest.raises(ValueError, match="read required must be a boolean"):
        VariableRead.from_dict({"key": "x", "required": "false"})
    with pytest.raises(ValueError, match="read unit must be a string"):
        VariableRead.from_dict({"key": "x", "unit": 1})
    assert VariableRead.from_dict({"key": "x", "required": False}).required is False


@pytest.mark.parametrize("field", ["value", "tolerance"])
def test_constraint_numbers_are_finite_and_not_boolean(field: str) -> None:
    payload: dict[str, object] = {"key": "x", "value": 1.0, field: float("nan")}
    with pytest.raises(ValueError, match=f"constraint {field} must be a finite number"):
        ConstraintSpec.from_dict(payload)
    payload[field] = True
    with pytest.raises(ValueError, match=f"constraint {field} must be a finite number"):
        ConstraintSpec.from_dict(payload)


def test_constraint_contract_rejects_missing_invalid_and_negative_fields() -> None:
    with pytest.raises(ValueError, match="constraint is missing key"):
        ConstraintSpec.from_dict({"value": 1})
    with pytest.raises(ValueError, match="constraint is missing value"):
        ConstraintSpec.from_dict({"key": "x"})
    with pytest.raises(ValueError, match="Unsupported constraint operator"):
        ConstraintSpec.from_dict({"key": "x", "value": 1, "operator": "!="})
    with pytest.raises(ValueError, match="tolerance cannot be negative"):
        ConstraintSpec.from_dict({"key": "x", "value": 1, "tolerance": -1})
    with pytest.raises(ValueError, match="constraint name must be a string"):
        ConstraintSpec.from_dict({"key": "x", "value": 1, "name": 2})


def test_balance_contract_rejects_malformed_and_nonfinite_fields() -> None:
    with pytest.raises(ValueError, match="balance is missing name"):
        BalanceSpec.from_dict({"terms": [{"key": "x"}]})
    with pytest.raises(ValueError, match="balance terms must be an array"):
        BalanceSpec.from_dict({"name": "mass", "terms": {"bad": True}})
    with pytest.raises(ValueError, match="requires at least one term"):
        BalanceSpec.from_dict({"name": "mass", "terms": []})
    with pytest.raises(ValueError, match="balance term is missing key"):
        BalanceTerm.from_dict({})
    with pytest.raises(ValueError, match="balance coefficient must be a finite number"):
        BalanceTerm.from_dict({"key": "x", "coefficient": float("inf")})
    with pytest.raises(ValueError, match="balance expected must be a finite number"):
        BalanceSpec.from_dict(
            {"name": "mass", "terms": [{"key": "x"}], "expected": float("nan")}
        )
    for field in ("abs_tol", "rel_tol", "floor"):
        with pytest.raises(ValueError, match=f"balance {field} must be a finite non-negative"):
            BalanceSpec.from_dict(
                {"name": "mass", "terms": [{"key": "x"}], field: -1}
            )


def test_valid_request_remains_round_trippable_and_json_shaped() -> None:
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
    document = request.to_dict()
    assert math.isfinite(request.timeout_s)
    assert isinstance(document["writes"], list)
    assert isinstance(document["reads"], list)
    assert EvaluationRequest.from_dict(document) == request
