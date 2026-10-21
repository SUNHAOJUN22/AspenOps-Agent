from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

from aspenops_nexus import optimization
from aspenops_nexus.config import Settings
from aspenops_nexus.design import bounded_grid, latin_hypercube, nearest_neighbor_order
from aspenops_nexus.engineering_rules import _validate_parameter_contracts, validate_process_design
from aspenops_nexus.optimizer import ParetoPoint, pareto_front
from aspenops_nexus.process_ir_v2 import ParameterDefinition, ProcessDesignIR
from aspenops_nexus.units import UnitError, convert


@pytest.mark.parametrize(("source", "target"), [("bogus", None), (None, "bogus")])
def test_unknown_unit_cannot_hide_behind_an_unspecified_endpoint(source, target):
    with pytest.raises(UnitError):
        convert(1.0, source, target)


@pytest.mark.parametrize(
    ("name", "value", "unit", "valid"),
    [
        ("EFFICIENCY", 80, "%", True),
        ("EFFICIENCY", 120, "%", False),
        ("CONVERSION", 500000, "ppm", True),
        ("CONVERSION", 1500000, "ppm", False),
        ("TEMPERATURE", -1, None, False),
        ("TEMPERATURE", -273.15, "C", False),
        ("TEMPERATURE", 25, "C", True),
    ],
)
def test_parameter_physics_use_canonical_units(name, value, unit, valid):
    p = ParameterDefinition(name, value, unit, "USER_PROVIDED")
    assert (not _validate_parameter_contracts((p,), "parameter")) is valid


@pytest.mark.parametrize("bounds", [[], [(0, float("inf"))], [(float("nan"), 1)], [(1, 0)]])
def test_sampling_rejects_invalid_domains(bounds):
    with pytest.raises(ValueError):
        latin_hypercube(bounds, 3)
    with pytest.raises(ValueError):
        bounded_grid(bounds, [2] * len(bounds))


@pytest.mark.parametrize("n", [True, 1.5])
def test_lhs_rejects_unbounded_or_noninteger_sizes(n):
    with pytest.raises(ValueError):
        latin_hypercube([(0, 1)], n)


def test_grid_budget_is_checked_before_allocation():
    with pytest.raises(ValueError):
        bounded_grid([(0, 1)] * 20, [10] * 20)


@pytest.mark.parametrize("points", [[[float("nan")], [1]], [[], []], [[1], [1, 2]]])
def test_nearest_neighbor_rejects_malformed_geometry(points):
    with pytest.raises(ValueError):
        nearest_neighbor_order(points)


@pytest.mark.parametrize(
    "point",
    [
        ParetoPoint((1,), (float("nan"),)),
        ParetoPoint((1,), (1,), float("nan")),
        ParetoPoint((1,), (1,), -1),
    ],
)
def test_pareto_rejects_invalid_scientific_evidence(point):
    with pytest.raises(ValueError):
        pareto_front([point])


def _design(formulas, coefficients, *, weights=None):
    doc = json.loads(Path("examples/process-design-v2.example.json").read_text())
    doc["components"] = [
        {
            "id": key,
            "display_name": key,
            "vendor_ids": {"aspen_plus": key},
            "formula": formula,
            "status": "USER_PROVIDED",
            **({"molecular_weight": weights[key]} if weights else {}),
        }
        for key, formula in formulas.items()
    ]
    for stream in doc["streams"]:
        stream["components"] = list(formulas)
    doc["reactions"] = [
        {
            "id": "R1",
            "kind": "stoichiometric",
            "stoichiometry": coefficients,
            "phase": "liquid",
            "status": "USER_PROVIDED",
        }
    ]
    return ProcessDesignIR.from_dict(doc)


@pytest.mark.parametrize(
    ("formulas", "coefficients", "expected"),
    [
        ({"A": "H2", "B": "O2", "C": "H2O"}, {"A": -2, "B": -1, "C": 2}, True),
        ({"A": "H2", "B": "O2", "C": "H2O"}, {"A": -1, "B": -1, "C": 1}, False),
        ({"A": "Na+", "B": "Cl-", "C": "NaCl"}, {"A": -1, "B": -1, "C": 1}, True),
        ({"A": "Na+", "B": "Na"}, {"A": -1, "B": 1}, False),
        ({"A": "Ca(OH)2", "B": "CaO", "C": "H2O"}, {"A": -1, "B": 1, "C": 1}, True),
        ({"A": "Xx2", "B": "H2"}, {"A": -1, "B": 1}, False),
        ({"A": None, "B": "H2"}, {"A": -1, "B": 1}, False),
    ],
)
def test_real_design_validator_requires_element_and_charge_conservation(
    formulas, coefficients, expected
):
    result = validate_process_design(_design(formulas, coefficients))
    assert result.valid is expected, result.to_dict()


def test_declared_molecular_weights_must_conserve_mass():
    design = _design({"A": "H2", "B": "H2"}, {"A": -1, "B": 1}, weights={"A": 2.0, "B": 20.0})
    assert not validate_process_design(design).valid


@pytest.mark.parametrize(
    ("actual_unit", "expected_ok", "expected_value"),
    [("W", True, 1), ("kW", True, 1000), ("bar", False, None), (None, False, None)],
)
def test_objective_evaluator_binds_actual_output_units(
    tmp_path, monkeypatch, actual_unit, expected_ok, expected_value
):
    document: dict[str, Any] = {
        "backend": "mock",
        "model_path": "model.json",
        "registry_path": "registry.json",
        "optimization": {
            "variables": [{"key": "temperature", "lower": 0, "upper": 1}],
            "objectives": [
                {
                    "output_key": "duty",
                    "unit": "kW",
                    "dimension": "power",
                    "reference_value": 0,
                    "reference_scale": 1,
                }
            ],
            "budget": {"population_size": 4, "generations": 0},
        },
    }
    result = {
        "ok": True,
        "values": {"duty": 1000},
        "units": {"duty": actual_unit},
        "request_hash": "synthetic",
    }
    monkeypatch.setattr(optimization, "run_batch_document", lambda *args, **kwargs: [result])
    evaluator = optimization._Evaluator(
        optimization.OptimizationProblem.from_document(document),
        Settings(state_dir=tmp_path),
        None,
        None,
        None,
    )
    evaluator.evaluate_many([(0.5,)])
    assert evaluator.trace[0].ok is expected_ok
    if expected_ok:
        assert evaluator.trace[0].objectives[0] == expected_value


def _dashboard():
    spec = importlib.util.spec_from_file_location(
        "repair_dashboard", "scripts/render_test_dashboard.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    "xml",
    [
        '<testsuite tests="3" failures="bad" errors="0" skipped="0" time="1"/>',
        '<testsuite tests="3.5" failures="0" errors="0" skipped="0" time="1"/>',
        '<testsuite tests="3" failures="0" errors="0" skipped="0" time="NaN"/>',
        '<testsuite tests="3" failures="4" errors="0" skipped="0" time="1"/>',
        '<testsuite tests="3" failures="0" errors="0" skipped="0" time="1">'
        "<testcase><failure/></testcase></testsuite>",
    ],
)
def test_malformed_junit_cannot_be_rendered_as_pass(tmp_path, xml):
    path = tmp_path / "junit.xml"
    path.write_text(xml)
    with pytest.raises(ValueError):
        _dashboard().parse_junit([path])


@pytest.mark.parametrize(
    "formula",
    [
        "H" * 257,
        "H?",
        "((H)",
        "H)",
        "(H]",
        "()",
        "H0",
        "H1000001",
        "2H1000000",
        "(" * 17 + "H" + ")" * 17,
    ],
)
def test_real_reaction_path_rejects_unsupported_compositions(formula):
    assert not validate_process_design(_design({"A": formula, "B": "H"}, {"A": -1, "B": 1})).valid


def test_hydrate_composition_and_explicit_charge_are_conserved():
    design = _design({"A": "CuSO4·5H2O", "B": "CuSO4", "C": "H2O"}, {"A": -1, "B": 1, "C": 5})
    assert validate_process_design(design).valid
    design = _design({"A": "Fe^3+", "B": "Cl-", "C": "FeCl3"}, {"A": -1, "B": -3, "C": 1})
    assert validate_process_design(design).valid


def test_conservation_overflow_is_a_blocker_not_a_zero_residual():
    assert not validate_process_design(
        _design({"A": "H99", "B": "H99"}, {"A": -1e308, "B": 1e308})
    ).valid


@pytest.mark.parametrize("bounds", [[(True, 1)], [("bad", 1)], [(10**400, 10**401)]])
def test_design_public_entry_rejects_nonreal_bounds(bounds):
    with pytest.raises(ValueError):
        bounded_grid(bounds, [2])


def test_sampling_budget_precedes_materialization():
    with pytest.raises(ValueError):
        latin_hypercube([(0, 1)], 10000001)
    with pytest.raises(ValueError):
        nearest_neighbor_order([[0]] * 5001)


@pytest.mark.parametrize(
    "points", [[[True], [1]], [["bad"], [1]], [[10**400], [1]], [[-1e308], [1e308]]]
)
def test_nearest_neighbor_rejects_unrepresentable_distances(points):
    with pytest.raises(ValueError):
        nearest_neighbor_order(points)


@pytest.mark.parametrize("field", ["reads", "constraints", "writes"])
def test_registered_unknown_quantity_cannot_be_relabelled(tmp_path, field):
    from aspenops_nexus.evaluation_plan import EvaluationPlanCompiler
    from aspenops_nexus.models import EvaluationRequest
    from aspenops_nexus.registry import NodeRegistry

    path = tmp_path / "registry.json"
    path.write_text(
        json.dumps(
            {
                "nodes": {
                    "x": {
                        "backend": "mock",
                        "access": "readwrite",
                        "unit": None,
                        "paths": [r"\Data\VALUE"],
                    }
                }
            }
        )
    )
    spec = {"key": "x", "unit": "K"}
    if field == "constraints":
        spec.update(name="temperature", operator=">=", value=0)
    if field == "writes":
        spec["value"] = 10
    request = EvaluationRequest.from_dict(
        {"backend": "mock", "model_path": "model.json", "registry_path": str(path), field: [spec]}
    )
    with pytest.raises(ValueError, match="no registered native unit"):
        EvaluationPlanCompiler.compile(NodeRegistry(path), request)


def test_nested_junit_is_counted_once_and_parent_contradictions_fail(tmp_path):
    module = _dashboard()
    path = tmp_path / "nested.xml"
    leaf = '<testsuite tests="2" failures="0" errors="0" skipped="1" time="1"/>'
    path.write_text("<testsuites><testsuites>" + leaf + "</testsuites></testsuites>")
    summary = module.parse_junit([path])
    assert (summary.tests, summary.passed) == (2, 1)
    path.write_text(
        '<testsuites tests="3" failures="0" errors="0" skipped="1" time="1">'
        + leaf
        + "</testsuites>"
    )
    with pytest.raises(ValueError, match="contradicts"):
        module.parse_junit([path])
