from pathlib import Path

from aspenops_nexus.backends.mock import MockBackend
from aspenops_nexus.evaluation import evaluate
from aspenops_nexus.models import EvaluationRequest
from aspenops_nexus.registry import NodeRegistry

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "src/aspenops_nexus/data/mock-case.json"
REGISTRY = ROOT / "src/aspenops_nexus/data/node-registry.json"


def test_constraints_and_balances_are_enforced() -> None:
    request = EvaluationRequest.from_dict(
        {
            "model_path": str(MODEL),
            "registry_path": str(REGISTRY),
            "backend": "mock",
            "writes": [
                {
                    "key": "stream.input.temperature",
                    "identifiers": {"stream": "FEED"},
                    "value": 100,
                    "unit": "C",
                }
            ],
            "reads": [],
            "constraints": [
                {
                    "name": "minimum_conversion",
                    "key": "reactor.output.conversion",
                    "identifiers": {"block": "R1"},
                    "operator": ">=",
                    "value": 0.5,
                    "unit": "fraction",
                }
            ],
            "balances": [
                {
                    "name": "deliberately_strict_mass_balance",
                    "terms": [
                        {
                            "key": "stream.input.mass_flow",
                            "identifiers": {"stream": "FEED"},
                            "coefficient": 1,
                            "unit": "kg/h",
                        },
                        {
                            "key": "stream.output.mass_flow",
                            "identifiers": {"stream": "PRODUCT"},
                            "coefficient": -1,
                            "unit": "kg/h",
                        },
                    ],
                    "abs_tol": 0.01,
                    "rel_tol": 0.0001,
                }
            ],
        }
    )
    backend = MockBackend()
    backend.open(MODEL)
    result = evaluate(backend, NodeRegistry(REGISTRY), request)
    backend.close()

    assert result.communication_ok
    assert result.converged
    assert not result.feasible
    assert "balance_failed:deliberately_strict_mass_balance" in result.violations
    assert result.diagnostics["constraints"][0]["passed"] is True
    assert result.balance_residuals["deliberately_strict_mass_balance"]["relative"] > 0


def test_constraint_failure_is_named() -> None:
    request = EvaluationRequest.from_dict(
        {
            "model_path": str(MODEL),
            "registry_path": str(REGISTRY),
            "backend": "mock",
            "writes": [],
            "reads": [],
            "constraints": [
                {
                    "name": "impossible_purity",
                    "key": "stream.output.purity",
                    "identifiers": {"stream": "PRODUCT"},
                    "operator": ">=",
                    "value": 0.99999,
                    "unit": "fraction",
                }
            ],
        }
    )
    backend = MockBackend()
    backend.open(MODEL)
    result = evaluate(backend, NodeRegistry(REGISTRY), request)
    backend.close()

    assert not result.ok
    assert "constraint_failed:impossible_purity" in result.violations


def test_constraint_tolerance_is_applied() -> None:
    request = EvaluationRequest.from_dict(
        {
            "model_path": str(MODEL),
            "registry_path": str(REGISTRY),
            "backend": "mock",
            "writes": [],
            "reads": [],
            "constraints": [
                {
                    "name": "purity_with_tolerance",
                    "key": "stream.output.purity",
                    "identifiers": {"stream": "PRODUCT"},
                    "operator": "==",
                    "value": 0.8685,
                    "tolerance": 0.001,
                    "unit": "fraction",
                }
            ],
        }
    )
    backend = MockBackend()
    backend.open(MODEL)
    result = evaluate(backend, NodeRegistry(REGISTRY), request)
    backend.close()
    assert result.ok
    assert result.engine_ok
    assert result.diagnostics["state_trace"][-1] == "verified"
