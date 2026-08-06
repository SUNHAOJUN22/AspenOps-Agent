from __future__ import annotations

import json
import math
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

import pytest

from aspenops_nexus.backends.aspen_plus import AspenPlusBackend
from aspenops_nexus.backends.mock import MockBackend
from aspenops_nexus.batch import dry_run_document, expand_batch_document, run_batch_document
from aspenops_nexus.cache import ResultCache
from aspenops_nexus.config import Settings
from aspenops_nexus.engineering_rules import validate_process_design
from aspenops_nexus.evaluation import evaluate
from aspenops_nexus.evaluation_plan import EvaluationPlanCompiler
from aspenops_nexus.models import EvaluationRequest
from aspenops_nexus.optimization import (
    OptimizationProblem,
    _finite_output,
    _strict_finite_output,
)
from aspenops_nexus.policy import Policy
from aspenops_nexus.process_ir_v2 import ProcessDesignIR
from aspenops_nexus.registry import NodeRegistry, ResolvedNode
from aspenops_nexus.simulator_capabilities import get_builtin_capability_profile
from aspenops_nexus.units import convert, dimension

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "src/aspenops_nexus/data/mock-case.json"
REGISTRY = ROOT / "src/aspenops_nexus/data/node-registry.json"
DESIGN = ROOT / "examples/process-design-v2.example.json"
OPTIMIZATION = ROOT / "examples/optimization-request.example.json"


class OverrideReadBackend(MockBackend):
    def __init__(self, key: str, value: Any) -> None:
        super().__init__()
        self.key = key
        self.value = value

    def read(self, node: ResolvedNode) -> Any:
        if node.key == self.key:
            return self.value
        return super().read(node)


class ExplodingRunBackend(MockBackend):
    def run(self) -> dict[str, Any]:
        raise RuntimeError("solver transport failed after writes")


def read_request() -> EvaluationRequest:
    return EvaluationRequest.from_dict(
        {
            "model_path": str(MODEL),
            "registry_path": str(REGISTRY),
            "backend": "mock",
            "writes": [],
            "reads": [
                {
                    "key": "stream.output.purity",
                    "identifiers": {"stream": "PRODUCT"},
                    "unit": "fraction",
                }
            ],
        }
    )


def test_numeric_output_rejects_boolean() -> None:
    backend = OverrideReadBackend("stream.output.purity", True)
    backend.open(MODEL)
    result = evaluate(backend, NodeRegistry(REGISTRY), read_request())
    backend.close()
    assert result.ok is False
    key = "stream.output.purity:stream=PRODUCT"
    assert f"non_numeric_required_output:{key}" in result.violations
    assert result.values[key] is None


def test_non_finite_constraint_and_balance_keep_distinct_evidence() -> None:
    constraint_request = EvaluationRequest.from_dict(
        {
            "model_path": str(MODEL),
            "registry_path": str(REGISTRY),
            "backend": "mock",
            "writes": [],
            "reads": [],
            "constraints": [
                {
                    "name": "finite_purity",
                    "key": "stream.output.purity",
                    "identifiers": {"stream": "PRODUCT"},
                    "operator": ">=",
                    "value": 0.5,
                    "unit": "fraction",
                }
            ],
        }
    )
    backend = OverrideReadBackend("stream.output.purity", math.inf)
    backend.open(MODEL)
    constraint_result = evaluate(backend, NodeRegistry(REGISTRY), constraint_request)
    backend.close()
    assert "constraint_non_finite:finite_purity" in constraint_result.violations
    assert constraint_result.diagnostics["constraints"][0]["failure"] == "non_finite"

    balance_request = EvaluationRequest.from_dict(
        {
            "model_path": str(MODEL),
            "registry_path": str(REGISTRY),
            "backend": "mock",
            "writes": [],
            "reads": [],
            "balances": [
                {
                    "name": "finite_mass",
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
                }
            ],
        }
    )
    backend = OverrideReadBackend("stream.output.mass_flow", -math.inf)
    backend.open(MODEL)
    balance_result = evaluate(backend, NodeRegistry(REGISTRY), balance_request)
    backend.close()
    assert "balance_non_finite:finite_mass" in balance_result.violations
    assert (
        balance_result.diagnostics["non_finite_balances"]["finite_mass"][0]["value"]
        == "negative_infinity"
    )


def test_post_write_execution_exception_taints_worker() -> None:
    request = EvaluationRequest.from_dict(
        {
            **read_request().to_dict(),
            "writes": [
                {
                    "key": "stream.input.temperature",
                    "identifiers": {"stream": "FEED"},
                    "value": 100,
                    "unit": "C",
                }
            ],
        }
    )
    backend = ExplodingRunBackend()
    backend.open(MODEL)
    result = evaluate(backend, NodeRegistry(REGISTRY), request)
    backend.close()
    assert result.ok is False
    assert result.diagnostics["worker_tainted"] is True


def test_warm_start_executes_each_step_without_cache_or_dedup(tmp_path: Path) -> None:
    document = {
        "backend": "mock",
        "model_path": str(MODEL),
        "registry_path": str(REGISTRY),
        "workers": 1,
        "reset_mode": "warm_start",
        "metadata": {"warm_start_session": "trajectory-a"},
        "points": [
            {
                "writes": [
                    {
                        "key": "stream.input.temperature",
                        "identifiers": {"stream": "FEED"},
                        "value": 80,
                        "unit": "C",
                    }
                ]
            },
            {
                "writes": [
                    {
                        "key": "stream.input.temperature",
                        "identifiers": {"stream": "FEED"},
                        "value": 90,
                        "unit": "C",
                    }
                ]
            },
        ],
        "reads": [
            {
                "key": "stream.output.purity",
                "identifiers": {"stream": "PRODUCT"},
                "unit": "fraction",
            }
        ],
    }
    requests = expand_batch_document(document)
    assert [item.metadata["warm_start_step"] for item in requests] == [0, 1]
    assert requests[0].physical_identity() != requests[1].physical_identity()
    results = run_batch_document(
        document,
        Settings(state_dir=tmp_path, max_workers=1, license_slots=1),
    )
    assert [item["diagnostics"]["run"]["solve_count"] for item in results] == [1, 2]
    assert all(item["cache_hit"] is False for item in results)


def test_warm_start_requires_one_ordered_trajectory(tmp_path: Path) -> None:
    payload = read_request().to_dict()
    payload["reset_mode"] = "warm_start"
    compatible = EvaluationRequest.from_dict(payload)
    assert compatible.metadata == {
        "warm_start_session": "unscoped-single-worker",
        "warm_start_step": 0,
    }

    document = {
        "backend": "mock",
        "model_path": str(MODEL),
        "registry_path": str(REGISTRY),
        "workers": 2,
        "reset_mode": "warm_start",
        "metadata": {"warm_start_session": "trajectory-a"},
        "points": [{}, {}],
        "reads": [],
    }
    with pytest.raises(ValueError, match="workers=1"):
        dry_run_document(
            document,
            Settings(state_dir=tmp_path, max_workers=2, license_slots=2),
        )


def test_optimization_and_objectives_are_strictly_reinitialized_numeric() -> None:
    assert _finite_output(True) == 1.0
    assert _finite_output(False) == 0.0
    assert _strict_finite_output(True) is None
    assert _strict_finite_output(False) is None
    assert _strict_finite_output(1) == 1.0
    document = json.loads(OPTIMIZATION.read_text(encoding="utf-8"))
    document["reset_mode"] = "warm_start"
    document["metadata"] = {
        "warm_start_session": "invalid-optimization",
        "warm_start_step": 0,
    }
    with pytest.raises(ValueError, match="reinitialize"):
        OptimizationProblem.from_document(document)


def test_parameter_contracts_units_and_absolute_temperature() -> None:
    raw = json.loads(DESIGN.read_text(encoding="utf-8"))
    heater = next(item for item in raw["equipment"] if item["kind"] == "heater")
    parameter = heater["parameters"][0]
    parameter["value"] = "hot"
    report = validate_process_design(ProcessDesignIR.from_dict(raw))
    assert "parameter.numeric_type" in {item.code for item in report.issues}

    parameter["value"] = 90.0
    parameter["unit"] = "kg/s"
    report = validate_process_design(ProcessDesignIR.from_dict(raw))
    assert "parameter.unit_dimension" in {item.code for item in report.issues}

    parameter["value"] = -10.0
    parameter["unit"] = "degC"
    report = validate_process_design(ProcessDesignIR.from_dict(raw))
    assert "parameter.absolute_temperature" not in {item.code for item in report.issues}

    parameter["value"] = -274.0
    report = validate_process_design(ProcessDesignIR.from_dict(raw))
    assert "parameter.absolute_temperature" in {item.code for item in report.issues}
    assert dimension("h") == "time"
    assert dimension("m3") == "volume"
    assert convert(1.0, "L", "m3") == pytest.approx(0.001)


def test_column_capability_exposes_independent_specs() -> None:
    profile = get_builtin_capability_profile("aspen_plus", "15")
    column = profile.equipment_by_kind()["distillation_column"]
    supported = set(column.supported_parameter_names)
    assert {"REFLUX_RATIO", "DISTILLATE_RATE", "BOTTOMS_RATE"}.issubset(supported)


def test_unrelated_recycle_does_not_cover_material_cycle() -> None:
    raw = json.loads(DESIGN.read_text(encoding="utf-8"))
    equipment = {item["id"]: item for item in raw["equipment"]}
    for equipment_id, port_id in (
        ("HTR_001", "IN"),
        ("HTR_001", "OUT"),
        ("FEED_001", "OUT"),
        ("VAP_PROD_001", "IN"),
    ):
        port = next(item for item in equipment[equipment_id]["ports"] if item["id"] == port_id)
        port["multiple"] = True
    raw["streams"].extend(
        [
            {
                "id": "S005",
                "display_name": "Artificial local cycle",
                "kind": "material",
                "source": {"equipment_id": "HTR_001", "port_id": "OUT"},
                "target": {"equipment_id": "HTR_001", "port_id": "IN"},
                "components": ["ETHANOL", "WATER"],
                "parameters": [],
            },
            {
                "id": "S006",
                "display_name": "Unrelated tear",
                "kind": "tear",
                "source": {"equipment_id": "FEED_001", "port_id": "OUT"},
                "target": {"equipment_id": "VAP_PROD_001", "port_id": "IN"},
                "components": ["ETHANOL", "WATER"],
                "parameters": [],
            },
        ]
    )
    raw["recycles"] = [
        {
            "id": "RECYCLE_001",
            "stream_id": "S005",
            "tear_stream_id": "S006",
            "convergence_variables": ["TEMPERATURE"],
            "tolerance": 1e-6,
            "max_iterations": 50,
            "acceleration": "wegstein",
            "status": "USER_PROVIDED",
        }
    ]
    report = validate_process_design(ProcessDesignIR.from_dict(raw))
    assert "topology.recycle_contract_missing" in {item.code for item in report.issues}


def test_duplicate_read_output_is_rejected() -> None:
    request = EvaluationRequest.from_dict(
        {
            **read_request().to_dict(),
            "reads": [
                {
                    "key": "stream.output.purity",
                    "identifiers": {"stream": "PRODUCT"},
                    "unit": "fraction",
                },
                {
                    "key": "stream.output.purity",
                    "identifiers": {"stream": "PRODUCT"},
                    "unit": "%",
                },
            ],
        }
    )
    with pytest.raises(ValueError, match="Duplicate read output"):
        EvaluationPlanCompiler.compile(NodeRegistry(REGISTRY), request)


def test_policy_and_aspen_running_flags_fail_closed() -> None:
    with pytest.raises(ValueError, match="Unsupported policy mode"):
        Policy("unknown", ())

    class Engine:
        Running = "false"

    assert AspenPlusBackend._engine_running(Engine()) is False
    Engine.Running = "true"
    assert AspenPlusBackend._engine_running(Engine()) is True
    Engine.Running = "unknown"
    assert AspenPlusBackend._engine_running(Engine()) is None


def test_cache_discards_nonfinite_json_constants(tmp_path: Path) -> None:
    path = tmp_path / "cache.sqlite3"
    cache = ResultCache(path)
    with closing(sqlite3.connect(path)) as connection, connection:
        connection.execute(
            "INSERT INTO result_cache(cache_key, payload) VALUES (?, ?)",
            ("nan", '{"value": NaN}'),
        )
    assert cache.get("nan") is None
    assert cache.stats()["entries"] == 0


def test_additional_acceptance_branch_contracts(tmp_path: Path) -> None:
    payload = read_request().to_dict()
    payload["reset_mode"] = "warm_start"
    payload["metadata"] = {"warm_start_session": "s", "warm_start_step": True}
    with pytest.raises(ValueError, match="warm_start_step"):
        EvaluationRequest.from_dict(payload)
    payload["metadata"] = {"warm_start_session": "", "warm_start_step": 0}
    with pytest.raises(ValueError, match="warm_start_session"):
        EvaluationRequest.from_dict(payload)

    warm = EvaluationRequest.from_dict(
        {
            **read_request().to_dict(),
            "reset_mode": "warm_start",
        }
    )
    from aspenops_nexus.pool import CasePool

    pool = CasePool(
        backend_name="mock",
        model_path=MODEL,
        registry_path=REGISTRY,
        workers=2,
        visible=False,
        cache_path=tmp_path / "cache.sqlite3",
    )
    with pytest.raises(ValueError, match="single-worker"):
        pool.evaluate_many([warm])
    pool.close()

    with pytest.raises(ValueError, match="allowed_roots"):
        Policy("default", [])  # type: ignore[arg-type]
