from __future__ import annotations

import pytest

from aspenops_nexus.optimization import ObjectiveSpec, OptimizationProblem


def _problem(objectives: list[dict[str, object]]) -> dict[str, object]:
    return {
        "optimization": {
            "variables": [
                {
                    "name": "x",
                    "key": "x",
                    "kind": "continuous",
                    "lower": 0,
                    "upper": 1,
                }
            ],
            "objectives": objectives,
        }
    }


def _normalized(
    output_key: str,
    *,
    unit: str,
    dimension: str,
    reference_value: float,
    reference_scale: float,
    direction: str = "minimize",
) -> dict[str, object]:
    return {
        "output_key": output_key,
        "direction": direction,
        "unit": unit,
        "dimension": dimension,
        "reference_value": reference_value,
        "reference_scale": reference_scale,
    }


def test_multiobjective_scalarization_fails_closed_without_normalization() -> None:
    with pytest.raises(ValueError, match="dimensionless normalization for every objective"):
        OptimizationProblem.from_document(
            _problem(
                [
                    {"output_key": "duty", "direction": "minimize"},
                    {"output_key": "purity", "direction": "maximize"},
                ]
            )
        )


def test_normalization_requires_complete_compatible_quantity_metadata() -> None:
    with pytest.raises(ValueError, match="requires unit, dimension"):
        ObjectiveSpec.from_mapping({"output_key": "duty", "unit": "kW", "reference_scale": 100})
    with pytest.raises(ValueError, match="has dimension 'power', not 'pressure'"):
        ObjectiveSpec.from_mapping(
            _normalized(
                "duty",
                unit="kW",
                dimension="pressure",
                reference_value=0,
                reference_scale=100,
            )
        )
    with pytest.raises(ValueError, match="reference_scale must be positive"):
        ObjectiveSpec.from_mapping(
            _normalized(
                "duty",
                unit="kW",
                dimension="power",
                reference_value=0,
                reference_scale=0,
            )
        )


def test_dimensionless_scalarization_is_invariant_to_kw_w_representation() -> None:
    kilowatts = ObjectiveSpec.from_mapping(
        _normalized(
            "duty",
            unit="kW",
            dimension="power",
            reference_value=100,
            reference_scale=50,
        )
    )
    watts = ObjectiveSpec.from_mapping(
        _normalized(
            "duty",
            unit="W",
            dimension="power",
            reference_value=100_000,
            reference_scale=50_000,
        )
    )
    assert kilowatts.scalarized_value(125) == pytest.approx(0.5)
    assert watts.scalarized_value(125_000) == pytest.approx(0.5)


def test_normalized_multiobjective_contract_is_explicitly_dimensionless() -> None:
    problem = OptimizationProblem.from_document(
        _problem(
            [
                _normalized(
                    "duty",
                    unit="kW",
                    dimension="power",
                    reference_value=100,
                    reference_scale=50,
                ),
                _normalized(
                    "purity",
                    unit="fraction",
                    dimension="dimensionless",
                    reference_value=0.9,
                    reference_scale=0.1,
                    direction="maximize",
                ),
            ]
        )
    )
    assert problem.scalarization_contract() == {
        "mode": "dimensionless-affine-weighted-sum",
        "dimensionless": True,
        "formula": "sum(weight_i * sign_i * (value_i-reference_i)/scale_i)",
    }


def test_single_objective_legacy_scalar_remains_explicit_and_supported() -> None:
    problem = OptimizationProblem.from_document(
        _problem([{"output_key": "duty", "direction": "minimize"}])
    )
    assert problem.objectives[0].scalarized_value(12.5) == 12.5
    assert problem.scalarization_contract()["mode"] == "single-objective-raw"
    assert problem.scalarization_contract()["dimensionless"] is False
