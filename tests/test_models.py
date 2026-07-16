import math

import pytest

from aspenops_nexus.models import (
    BalanceSpec,
    ConstraintSpec,
    EvaluationRequest,
    EvaluationResult,
    VariableRead,
)

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


def test_legacy_reinitialize_requires_boolean_and_cannot_conflict() -> None:
    with pytest.raises(ValueError, match="Boolean"):
        EvaluationRequest.from_dict({**BASE, "reinitialize": "false"})
    with pytest.raises(ValueError, match="conflicts"):
        EvaluationRequest.from_dict({**BASE, "reinitialize": False, "reset_mode": "reinitialize"})


def test_invalid_backend_and_timeout_are_rejected() -> None:
    with pytest.raises(ValueError):
        EvaluationRequest.from_dict({**BASE, "backend": "unknown"})
    with pytest.raises(ValueError):
        EvaluationRequest.from_dict({**BASE, "timeout_s": 0})
    with pytest.raises(ValueError):
        EvaluationRequest.from_dict({**BASE, "timeout_s": math.nan})
    with pytest.raises(ValueError):
        EvaluationRequest.from_dict({**BASE, "timeout_s": math.inf})


def test_unknown_fields_fail_closed_at_every_schema_boundary() -> None:
    with pytest.raises(ValueError, match="Unknown fields"):
        EvaluationRequest.from_dict({**BASE, "typo_timeout": 5})
    with pytest.raises(ValueError, match="Unknown fields"):
        VariableRead.from_dict({"key": "x", "required": True, "requird": False})


def test_boolean_strings_are_not_coerced() -> None:
    with pytest.raises(ValueError, match="Boolean"):
        VariableRead.from_dict({"key": "x", "required": "false"})


def test_metadata_path_and_timeout_are_excluded_from_physical_identity() -> None:
    first = EvaluationRequest.from_dict(
        {
            **BASE,
            "model_path": "first/case.json",
            "registry_path": "first/registry.json",
            "timeout_s": 5,
            "metadata": {"label": "a"},
        }
    )
    second = EvaluationRequest.from_dict(
        {
            **BASE,
            "model_path": "second/case.json",
            "registry_path": "second/registry.json",
            "timeout_s": 50,
            "metadata": {"label": "b"},
        }
    )
    assert first.physical_identity() == second.physical_identity()


def test_duplicate_reads_writes_and_balance_names_are_rejected() -> None:
    duplicate_write = {
        "key": "stream.input.temperature",
        "identifiers": {"stream": "FEED"},
        "value": 300.0,
        "unit": "K",
    }
    with pytest.raises(ValueError, match="Duplicate write"):
        EvaluationRequest.from_dict({**BASE, "writes": [duplicate_write, duplicate_write]})
    duplicate_read = {
        "key": "stream.output.purity",
        "identifiers": {"stream": "PRODUCT"},
        "unit": "fraction",
    }
    with pytest.raises(ValueError, match="Duplicate read"):
        EvaluationRequest.from_dict({**BASE, "reads": [duplicate_read, duplicate_read]})
    balance = {
        "name": "mass",
        "terms": [{"key": "x", "identifiers": {}, "coefficient": 1.0}],
    }
    with pytest.raises(ValueError, match="Balance names"):
        EvaluationRequest.from_dict({**BASE, "balances": [balance, balance]})


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


def test_result_truth_flags_and_json_shape_are_invariant() -> None:
    with pytest.raises(ValueError, match="ok must equal"):
        EvaluationResult(
            ok=True,
            communication_ok=True,
            engine_ok=True,
            converged=False,
            feasible=True,
            values={},
            units={},
            violations=[],
            diagnostics={},
            elapsed_s=0.0,
        )
    with pytest.raises(ValueError, match="same keys"):
        EvaluationResult(
            ok=True,
            communication_ok=True,
            engine_ok=True,
            converged=True,
            feasible=True,
            values={"x": 1.0},
            units={},
            violations=[],
            diagnostics={},
            elapsed_s=0.0,
        )


def test_result_parser_rejects_unknown_and_string_booleans() -> None:
    result = {
        "ok": True,
        "communication_ok": True,
        "engine_ok": True,
        "converged": True,
        "feasible": True,
        "values": {},
        "units": {},
        "violations": [],
        "diagnostics": {},
        "elapsed_s": 0.1,
    }
    with pytest.raises(ValueError, match="Unknown fields"):
        EvaluationResult.from_dict({**result, "unexpected": 1})
    with pytest.raises(ValueError, match="Boolean"):
        EvaluationResult.from_dict({**result, "ok": "true"})
