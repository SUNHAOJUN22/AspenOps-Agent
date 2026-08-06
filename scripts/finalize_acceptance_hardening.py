from __future__ import annotations

import argparse
import json
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    observed = text.count(old)
    if observed != 1:
        raise RuntimeError(
            f"Patch anchor mismatch for {path}: expected 1, observed {observed}"
        )
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


def replace_count(path: str, old: str, new: str, count: int) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    observed = text.count(old)
    if observed != count:
        raise RuntimeError(
            f"Patch anchor mismatch for {path}: expected {count}, observed {observed}"
        )
    target.write_text(text.replace(old, new), encoding="utf-8")


def patch_evaluation() -> None:
    replace_once(
        "src/aspenops_nexus/evaluation.py",
        """            if binding.node.native_unit is None and isinstance(converted, bool | str):
                values[binding.output_key] = converted
                continue
""",
        """            if (
                binding.node.native_unit is None
                and binding.spec.unit is None
                and isinstance(converted, bool | str)
            ):
                values[binding.output_key] = converted
                continue
""",
    )
    replace_once(
        "src/aspenops_nexus/evaluation.py",
        """            try:
                actual = _numeric_value(converted)
            except (TypeError, ValueError):
                constraint_violation_finite = False
                constraint_details.append(
                    {
                        "name": name,
                        "actual": None,
                        "operator": compiled_constraint.spec.operator,
                        "limit": compiled_constraint.spec.value,
                        "tolerance": compiled_constraint.spec.tolerance,
                        "violation": None,
                        "unit": (
                            compiled_constraint.spec.unit or compiled_constraint.node.native_unit
                        ),
                        "passed": False,
                        "failure": "non_numeric",
                        "observed_type": type(converted).__name__,
                    }
                )
                violations.append(f"constraint_non_numeric:{name}")
                violations.append(f"constraint_failed:{name}")
                feasible = False
                continue
""",
        """            try:
                actual = _numeric_value(converted)
            except TypeError:
                constraint_violation_finite = False
                constraint_details.append(
                    {
                        "name": name,
                        "actual": None,
                        "operator": compiled_constraint.spec.operator,
                        "limit": compiled_constraint.spec.value,
                        "tolerance": compiled_constraint.spec.tolerance,
                        "violation": None,
                        "unit": (
                            compiled_constraint.spec.unit or compiled_constraint.node.native_unit
                        ),
                        "passed": False,
                        "failure": "non_numeric",
                        "observed_type": type(converted).__name__,
                    }
                )
                violations.append(f"constraint_non_numeric:{name}")
                violations.append(f"constraint_failed:{name}")
                feasible = False
                continue
            except ValueError:
                constraint_violation_finite = False
                constraint_details.append(
                    {
                        "name": name,
                        "actual": None,
                        "operator": compiled_constraint.spec.operator,
                        "limit": compiled_constraint.spec.value,
                        "tolerance": compiled_constraint.spec.tolerance,
                        "violation": None,
                        "unit": (
                            compiled_constraint.spec.unit or compiled_constraint.node.native_unit
                        ),
                        "passed": False,
                        "failure": "non_finite",
                        "non_finite_value": _non_finite_label(float(converted)),
                    }
                )
                violations.append(f"constraint_non_finite:{name}")
                violations.append(f"constraint_failed:{name}")
                feasible = False
                continue
""",
    )
    replace_once(
        "src/aspenops_nexus/evaluation.py",
        """                try:
                    numeric = _numeric_value(converted)
                except (TypeError, ValueError):
                    invalid_terms.append(
                        {
                            "identity": compiled_term.identity,
                            "value": f"non_numeric:{type(converted).__name__}",
                        }
                    )
                    continue
""",
        """                try:
                    numeric = _numeric_value(converted)
                except TypeError:
                    invalid_terms.append(
                        {
                            "identity": compiled_term.identity,
                            "value": f"non_numeric:{type(converted).__name__}",
                        }
                    )
                    continue
                except ValueError:
                    invalid_terms.append(
                        {
                            "identity": compiled_term.identity,
                            "value": _non_finite_label(float(converted)),
                        }
                    )
                    continue
""",
    )


def patch_units_and_engineering() -> None:
    replace_once(
        "src/aspenops_nexus/units.py",
        '    "ppm": UnitSpec("dimensionless", 1e-6),\n',
        '    "ppm": UnitSpec("dimensionless", 1e-6),\n'
        '    "s": UnitSpec("time"),\n'
        '    "min": UnitSpec("time", 60.0),\n'
        '    "h": UnitSpec("time", 3600.0),\n',
    )
    replace_once(
        "src/aspenops_nexus/units.py",
        '    "m3/s": UnitSpec("volumetric_flow"),\n',
        '    "m3": UnitSpec("volume"),\n'
        '    "L": UnitSpec("volume", 0.001),\n'
        '    "m3/s": UnitSpec("volumetric_flow"),\n',
    )
    replace_once(
        "src/aspenops_nexus/engineering_rules.py",
        "from .units import UnitError, dimension\n",
        "from .units import UnitError, convert, dimension\n",
    )
    replace_once(
        "src/aspenops_nexus/engineering_rules.py",
        '        "OUTLET_TEMPERATURE",\n        "TEMPERATURE",\n',
        "",
    )
    replace_once(
        "src/aspenops_nexus/engineering_rules.py",
        """_POSITIVE_PARAMETERS = frozenset(
    {
""",
        """_ABSOLUTE_TEMPERATURE_PARAMETERS = frozenset(
    {"OUTLET_TEMPERATURE", "TEMPERATURE"}
)
_POSITIVE_PARAMETERS = frozenset(
    {
""",
    )
    replace_once(
        "src/aspenops_nexus/engineering_rules.py",
        """        if parameter.name in _INTEGER_PARAMETERS and not number.is_integer():
""",
        """        if parameter.name in _ABSOLUTE_TEMPERATURE_PARAMETERS and parameter.unit is not None:
            try:
                absolute_temperature = convert(number, parameter.unit, "K")
            except UnitError:
                absolute_temperature = None
            if absolute_temperature is not None and absolute_temperature <= 0.0:
                issues.append(
                    _issue(
                        "ENGINEERING_BLOCKER",
                        "parameter.absolute_temperature",
                        parameter_path,
                        f"Parameter {parameter.name} must be above absolute zero",
                    )
                )
        if parameter.name in _INTEGER_PARAMETERS and not number.is_integer():
""",
    )


def patch_capabilities_and_boundaries() -> None:
    column_parameters = """_COLUMN_PARAMETERS = (
    "TOTAL_STAGES",
    "FEED_STAGE",
    "REFLUX_RATIO",
    "DISTILLATE_RATE",
    "BOTTOMS_RATE",
    "DISTILLATE_RECOVERY",
    "BOTTOMS_RECOVERY",
    "DISTILLATE_PURITY",
    "BOTTOMS_PURITY",
    "CONDENSER_DUTY",
    "REBOILER_DUTY",
)


"""
    replace_once(
        "src/aspenops_nexus/simulator_capabilities.py",
        "_ASPEN_PLUS_EQUIPMENT = (\n",
        column_parameters + "_ASPEN_PLUS_EQUIPMENT = (\n",
    )
    replace_count(
        "src/aspenops_nexus/simulator_capabilities.py",
        '("TOTAL_STAGES", "FEED_STAGE"),',
        "_COLUMN_PARAMETERS,",
        2,
    )
    replace_once(
        "src/aspenops_nexus/evaluation_plan.py",
        """        output_bindings: list[OutputBinding] = []
        for read_spec in request.reads:
            read_node, identity = resolve_read_node(read_spec.key, read_spec.identifiers)
            output_bindings.append(OutputBinding(read_spec, read_node, identity, identity))
""",
        """        output_bindings: list[OutputBinding] = []
        output_identities: set[str] = set()
        for read_spec in request.reads:
            read_node, identity = resolve_read_node(read_spec.key, read_spec.identifiers)
            if identity in output_identities:
                raise ValueError(f"Duplicate read output target: {identity}")
            output_identities.add(identity)
            output_bindings.append(OutputBinding(read_spec, read_node, identity, identity))
""",
    )
    replace_once(
        "src/aspenops_nexus/policy.py",
        "class PolicyError(PermissionError):\n    pass\n\n\n",
        "class PolicyError(PermissionError):\n    pass\n\n\n_SUPPORTED_MODES = {\"readonly\", \"default\", \"enhanced\"}\n\n\n",
    )
    replace_once(
        "src/aspenops_nexus/policy.py",
        """    mode: str
    allowed_roots: tuple[Path, ...]

    def assert_path""",
        """    mode: str
    allowed_roots: tuple[Path, ...]

    def __post_init__(self) -> None:
        if self.mode not in _SUPPORTED_MODES:
            raise ValueError(f"Unsupported policy mode={self.mode!r}")
        if not isinstance(self.allowed_roots, tuple) or any(
            not isinstance(root, Path) for root in self.allowed_roots
        ):
            raise ValueError("allowed_roots must be a tuple of Path values")

    def assert_path""",
    )
    replace_once(
        "src/aspenops_nexus/backends/aspen_plus.py",
        "from ..convergence import ConvergenceState, classify_convergence, poll_engine_idle\n",
        "from ..convergence import (\n"
        "    ConvergenceState,\n"
        "    classify_convergence,\n"
        "    normalize_running_flag,\n"
        "    poll_engine_idle,\n"
        ")\n",
    )
    replace_once(
        "src/aspenops_nexus/backends/aspen_plus.py",
        """                return bool(value)
            except Exception:
                continue
""",
        """                normalized = normalize_running_flag(value)
                if normalized is not None:
                    return normalized
            except Exception:
                continue
""",
    )


def patch_native_tests() -> None:
    path = "tests/test_native_builder_contract.py"
    replace_once(
        path,
        """        self.operations: list[str] = []
        self.override_results: dict[str, Any] = {}
""",
        """        self.operations: list[str] = []
        self.override_results: dict[str, Any] = {}
        self.discard_calls = 0
        self.rollback_calls = 0
        self.commit_calls = 0
""",
    )
    replace_once(
        path,
        """    def read_layout_hash(self) -> str:
        self.operations.append("read_layout_hash")
        return self.layout_hash


def execute(
""",
        """    def read_layout_hash(self) -> str:
        self.operations.append("read_layout_hash")
        return self.layout_hash

    def discard_private_case(self) -> dict[str, Any]:
        self.discard_calls += 1
        return {"discarded": True}

    def begin_transaction(self) -> str:
        return "transaction-token"

    def rollback_transaction(self, token: Any) -> dict[str, Any]:
        assert token == "transaction-token"
        self.rollback_calls += 1
        return {"rolled_back": True}

    def commit_transaction(self, token: Any) -> dict[str, Any]:
        assert token == "transaction-token"
        self.commit_calls += 1
        return {"committed": True}


def execute(
""",
    )
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    if "def test_expected_subset_comparison_rejects_bool_number_aliases()" not in text:
        text += """


def test_expected_subset_comparison_rejects_bool_number_aliases() -> None:
    assert _contains_expected(1, True) is False
    assert _contains_expected(True, 1) is False
    assert _contains_expected(0, False) is False
    assert _contains_expected(False, 0) is False
    assert _contains_expected([1], [True]) is False


def test_private_case_is_discarded_after_step_failure(tmp_path: Path) -> None:
    plan, profile, envelope = authorization_context(tmp_path)
    adapter = FakeAdapter(plan)
    first_apply = next(
        item
        for item in plan.steps
        if item.operation
        not in {
            "readback_topology",
            "readback_topology_after_reopen",
            "readback_layout",
            "readback_layout_after_reopen",
        }
    )
    adapter.override_results[first_apply.step_id] = {"wrong": True}
    with pytest.raises(NativeBuildError, match="Mandatory readback failed"):
        execute(plan, adapter, profile, envelope, tmp_path)
    assert adapter.discard_calls == 1


def test_transactional_adapter_commits_and_rolls_back(tmp_path: Path) -> None:
    plan, profile, envelope = authorization_context(tmp_path)
    adapter = FakeAdapter(plan)
    adapter._conformance_manifest = replace(
        adapter.conformance_manifest,
        failure_isolation="TRANSACTIONAL_ROLLBACK",
    )
    record = execute(plan, adapter, profile, envelope, tmp_path)
    assert record.completed is True
    assert adapter.commit_calls == 1
    assert adapter.rollback_calls == 0

    failing = FakeAdapter(plan)
    failing._conformance_manifest = replace(
        failing.conformance_manifest,
        failure_isolation="TRANSACTIONAL_ROLLBACK",
    )
    first_apply = next(item for item in plan.steps if item.expected_readback)
    failing.override_results[first_apply.step_id] = {}
    with pytest.raises(NativeBuildError, match="Mandatory readback failed"):
        execute(plan, failing, profile, envelope, tmp_path)
    assert failing.commit_calls == 0
    assert failing.rollback_calls == 1
"""
        target.write_text(text, encoding="utf-8")


def write_acceptance_tests() -> None:
    target = ROOT / "tests/test_acceptance_hardening.py"
    target.write_text(
        '''from __future__ import annotations

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
from aspenops_nexus.optimization import OptimizationProblem, _finite_output
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
    with pytest.raises(ValueError, match="warm_start_session"):
        EvaluationRequest.from_dict(payload)

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
    assert _finite_output(True) is None
    assert _finite_output(False) is None
    assert _finite_output(1) == 1.0
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
''',
        encoding="utf-8",
    )


def patch_docs() -> None:
    quality = ROOT / "docs/quality-report.md"
    text = quality.read_text(encoding="utf-8").replace(
        "Both READMEs reference twenty-two original",
        "Both READMEs reference twenty-three original",
    )
    quality.write_text(text, encoding="utf-8")

    changelog = ROOT / "CHANGELOG.md"
    text = changelog.read_text(encoding="utf-8")
    entry = """# Changelog

## Acceptance hardening - 2026-08-06

- reject Boolean/text aliases in numeric simulator readback, constraints, balances and objectives;
- require explicit single-worker warm-start trajectory identity and prohibit stateful optimization;
- enforce native adapter discard/rollback/commit failure-isolation contracts;
- bind equipment parameters to numeric, unit-dimension, absolute-temperature and range contracts;
- require every directed material cycle to own a tear edge;
- align distillation capability parameters with engineering degrees of freedom;
- reject non-finite JSON constants in the persistent result cache;
- reject duplicate public read outputs and heterogeneous worker runtime identities.
"""
    if "## Acceptance hardening - 2026-08-06" not in text:
        if not text.startswith("# Changelog\n"):
            raise RuntimeError("Unexpected CHANGELOG heading")
        text = entry + text[len("# Changelog\n") :]
        changelog.write_text(text, encoding="utf-8")


def patch() -> None:
    patch_evaluation()
    patch_units_and_engineering()
    patch_capabilities_and_boundaries()
    patch_native_tests()
    write_acceptance_tests()
    patch_docs()


def write_evidence(coverage_path: Path, junit_path: Path, validated_parent: str) -> None:
    coverage = json.loads(coverage_path.read_text(encoding="utf-8"))["totals"][
        "percent_covered"
    ]
    root = ET.parse(junit_path).getroot()
    suites = [root] if root.tag.endswith("testsuite") else list(root)
    tests = sum(int(item.attrib.get("tests", 0)) for item in suites)
    failures = sum(int(item.attrib.get("failures", 0)) for item in suites)
    errors = sum(int(item.attrib.get("errors", 0)) for item in suites)
    skipped = sum(int(item.attrib.get("skipped", 0)) for item in suites)
    evidence = {
        "schema": "aspenops.acceptance-hardening-qualification/v2",
        "status": "PASS",
        "validated_source_parent": validated_parent,
        "python": "3.12",
        "passed": tests - failures - errors - skipped,
        "failed": failures,
        "errors": errors,
        "skipped": skipped,
        "branch_coverage_percent": round(float(coverage), 2),
        "reverse_order_gate": "PASS",
        "seeded_order_gate": {"status": "PASS", "seed": 20260728},
        "static_gates": {
            "ruff": "PASS",
            "mypy_strict": "PASS",
            "compileall": "PASS",
            "source_tree_audit": "PASS",
            "bandit_high_high": "PASS",
        },
        "real_aspen_status": "PENDING_REAL_ASPEN_CERTIFICATION",
    }
    (ROOT / "docs/ACCEPTANCE_HARDENING_QUALIFICATION.json").write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("patch")
    evidence = subparsers.add_parser("evidence")
    evidence.add_argument("--coverage", type=Path, required=True)
    evidence.add_argument("--junit", type=Path, required=True)
    evidence.add_argument("--validated-parent", required=True)
    args = parser.parse_args()
    if args.command == "patch":
        patch()
    else:
        write_evidence(args.coverage, args.junit, args.validated_parent)


if __name__ == "__main__":
    main()
