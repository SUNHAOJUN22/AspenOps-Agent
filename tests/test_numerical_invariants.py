from importlib.resources import as_file, files
from pathlib import Path

import pytest

from aspenops_nexus.backends.mock import MockBackend
from aspenops_nexus.evaluation import _constraint_assessment, _constraint_scale, evaluate
from aspenops_nexus.models import ConstraintSpec, EvaluationRequest
from aspenops_nexus.registry import NodeRegistry


def resource(name: str) -> Path:
    with as_file(files("aspenops_nexus.data").joinpath(name)) as path:
        return Path(path)


def test_strict_constraint_rejects_exact_boundary() -> None:
    spec = ConstraintSpec(
        key="x",
        identifiers={},
        operator="<",
        value=1.0,
        tolerance=0.0,
    )
    violation, passed = _constraint_assessment(spec, 1.0)
    assert not passed
    assert violation > 0.0


def test_constraint_scale_is_fixed_and_normalizes_units() -> None:
    derived = ConstraintSpec(
        key="x",
        identifiers={},
        operator="<=",
        value=1000.0,
        tolerance=0.1,
    )
    explicit = ConstraintSpec(
        key="x",
        identifiers={},
        operator="<=",
        value=1000.0,
        tolerance=0.1,
        scale=10.0,
        weight=2.0,
    )
    assert _constraint_scale(derived) == (1000.0, "derived_from_limit")
    assert _constraint_scale(explicit) == (10.0, "explicit")


def test_combined_balance_tolerance_uses_expected_scale() -> None:
    request = EvaluationRequest.from_dict(
        {
            "model_path": str(resource("mock-case.json")),
            "registry_path": str(resource("node-registry.json")),
            "backend": "mock",
            "writes": [],
            "reads": [],
            "balances": [
                {
                    "name": "combined_tolerance",
                    "terms": [
                        {
                            "key": "stream.input.mass_flow",
                            "identifiers": {"stream": "FEED"},
                            "coefficient": 0.0,
                            "unit": "kg/h",
                        }
                    ],
                    "expected": -8e-7,
                    "unit": "kg/h",
                    "abs_tol": 5e-7,
                    "rel_tol": 0.625,
                    "floor": 1e-12,
                }
            ],
        }
    )
    backend = MockBackend()
    backend.open(resource("mock-case.json"))
    result = evaluate(backend, NodeRegistry(resource("node-registry.json")), request)
    backend.close()

    residual = result.balance_residuals["combined_tolerance"]
    assert residual["absolute"] == pytest.approx(8e-7)
    assert residual["threshold"] == pytest.approx(1e-6)
    assert residual["passed"] == 1.0
    assert result.ok


def test_balance_terms_are_converted_to_one_canonical_unit() -> None:
    request = EvaluationRequest.from_dict(
        {
            "model_path": str(resource("mock-case.json")),
            "registry_path": str(resource("node-registry.json")),
            "backend": "mock",
            "writes": [],
            "reads": [],
            "balances": [
                {
                    "name": "same_flow",
                    "unit": "kg/s",
                    "terms": [
                        {
                            "key": "stream.input.mass_flow",
                            "identifiers": {"stream": "FEED"},
                            "coefficient": 1.0,
                            "unit": "kg/h",
                        },
                        {
                            "key": "stream.input.mass_flow",
                            "identifiers": {"stream": "FEED"},
                            "coefficient": -1.0,
                            "unit": "kg/s",
                        },
                    ],
                    "abs_tol": 0.0,
                    "rel_tol": 0.0,
                }
            ],
        }
    )
    backend = MockBackend()
    backend.open(resource("mock-case.json"))
    result = evaluate(backend, NodeRegistry(resource("node-registry.json")), request)
    backend.close()

    residual = result.balance_residuals["same_flow"]
    assert residual["unit"] == "kg/s"
    assert residual["residual"] == pytest.approx(0.0)
    assert result.ok


def test_incompatible_balance_units_fail_closed() -> None:
    request = EvaluationRequest.from_dict(
        {
            "model_path": str(resource("mock-case.json")),
            "registry_path": str(resource("node-registry.json")),
            "backend": "mock",
            "writes": [],
            "reads": [],
            "balances": [
                {
                    "name": "invalid_units",
                    "unit": "kg/h",
                    "terms": [
                        {
                            "key": "stream.input.mass_flow",
                            "identifiers": {"stream": "FEED"},
                            "coefficient": 1.0,
                            "unit": "kW",
                        }
                    ],
                }
            ],
        }
    )
    backend = MockBackend()
    backend.open(resource("mock-case.json"))
    result = evaluate(backend, NodeRegistry(resource("node-registry.json")), request)
    backend.close()

    assert not result.ok
    assert "execution_error:ValueError" in result.violations
