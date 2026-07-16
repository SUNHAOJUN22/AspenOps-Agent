import math

import pytest

from aspenops_nexus.approval import ApprovalRecord, approval_binding_hash
from aspenops_nexus.drift import DriftThresholds, population_stability_index
from aspenops_nexus.errors import SurrogateDomainError
from aspenops_nexus.surrogate import (
    FeatureSpec,
    OutputSpec,
    SurrogateManifest,
    assess_domain,
    validate_covariance,
)
from aspenops_nexus.twin import TwinSignals, route_twin

HASH_A = "a" * 64
HASH_B = "b" * 64
HASH_C = "c" * 64


def manifest(**overrides) -> SurrogateManifest:
    values = {
        "aspen_model_sha256": HASH_A,
        "registry_sha256": HASH_B,
        "dataset_sha256": HASH_C,
        "features": (
            FeatureSpec("temperature", "K", 280.0, 420.0, 350.0, 20.0),
            FeatureSpec("pressure", "bar", 1.0, 20.0, 10.0, 2.0),
        ),
        "outputs": (OutputSpec("purity", "fraction"),),
        "training_version": "1.0",
        "provider": "test",
        "metrics": {"rmse": 0.01},
        "standardized_distance_limit": 4.0,
        "uncertainty_limit": 0.05,
        "covariance": ((1.0, 0.0), (0.0, 1.0)),
        "mahalanobis_limit": 4.0,
    }
    values.update(overrides)
    return SurrogateManifest(**values)


def test_manifest_binds_model_registry_dataset_and_is_deterministic() -> None:
    first = manifest()
    second = manifest()
    assert first.manifest_sha256 == second.manifest_sha256
    assert first.compatible_with(HASH_A, HASH_B)
    assert not first.compatible_with(HASH_C, HASH_B)
    assert first.covariance_space == "standardized"


def test_manifest_metrics_are_immutable_after_hash_binding() -> None:
    surrogate = manifest()
    original_hash = surrogate.manifest_sha256
    with pytest.raises(TypeError):
        surrogate.metrics["rmse"] = 2.0
    assert surrogate.manifest_sha256 == original_hash


def test_box_standardized_and_mahalanobis_domain_pass() -> None:
    assessment = assess_domain(manifest(), {"temperature": 350.0, "pressure": 10.0})
    assert assessment.applicable
    assert assessment.standardized_distance == 0.0
    assert assessment.mahalanobis_distance == 0.0
    assert assessment.mahalanobis_space == "standardized"


def test_mahalanobis_uses_dimensionless_standardized_coordinates() -> None:
    assessment = assess_domain(manifest(), {"temperature": 370.0, "pressure": 10.0})
    assert math.isclose(assessment.standardized_distance, 1.0, rel_tol=0.0, abs_tol=1e-12)
    assert math.isclose(assessment.mahalanobis_distance or math.nan, 1.0, abs_tol=1e-12)


def test_out_of_domain_input_requires_fallback_without_clipping() -> None:
    assessment = assess_domain(manifest(), {"temperature": 500.0, "pressure": 10.0})
    assert not assessment.applicable
    assert "outside_box_domain" in assessment.reasons
    assert "standardized_distance_exceeded" in assessment.reasons


def test_feature_set_mismatch_fails_closed() -> None:
    with pytest.raises(SurrogateDomainError, match="Feature set mismatch"):
        assess_domain(manifest(), {"temperature": 350.0})


def test_singular_covariance_is_regularized_with_bounded_condition() -> None:
    _matrix, _cholesky, condition, regularization = validate_covariance(
        ((1.0, 1.0), (1.0, 1.0)),
        dimension=2,
        max_condition=1e8,
    )
    assert condition <= 1e8
    assert regularization > 0.0


def test_asymmetric_covariance_is_rejected() -> None:
    with pytest.raises(SurrogateDomainError, match="symmetric"):
        validate_covariance(((1.0, 0.1), (0.2, 1.0)), dimension=2, max_condition=1e8)


def test_nonpositive_covariance_variance_is_rejected() -> None:
    with pytest.raises(SurrogateDomainError, match="variances"):
        validate_covariance(((0.0, 0.0), (0.0, 1.0)), dimension=2, max_condition=1e8)


def test_psi_uses_fixed_bins_and_sample_gate() -> None:
    thresholds = DriftThresholds(warning=0.05, block=0.2, min_samples=4)
    identical = population_stability_index(
        [0.0, 0.2, 0.8, 1.0],
        [0.0, 0.2, 0.8, 1.0],
        [0.5],
        thresholds,
    )
    assert identical.level == "OK"
    assert math.isclose(identical.psi, 0.0, abs_tol=1e-15)

    shifted = population_stability_index(
        [0.0, 0.1, 0.2, 0.3],
        [0.7, 0.8, 0.9, 1.0],
        [0.5],
        thresholds,
    )
    assert shifted.level == "BLOCK"
    with pytest.raises(ValueError, match="below the drift minimum"):
        population_stability_index([0.0], [0.0], [0.5], thresholds)


@pytest.mark.parametrize("invalid", [True, 2.5, 1])
def test_drift_minimum_sample_count_requires_a_real_integer(invalid: object) -> None:
    with pytest.raises(ValueError, match="integer"):
        DriftThresholds(min_samples=invalid)  # type: ignore[arg-type]


def test_boolean_psi_samples_and_bins_are_rejected() -> None:
    thresholds = DriftThresholds(min_samples=2)
    with pytest.raises(ValueError, match="Boolean"):
        population_stability_index([True, 0.0], [0.0, 1.0], [0.5], thresholds)
    with pytest.raises(ValueError, match="Boolean"):
        population_stability_index([0.0, 1.0], [0.0, 1.0], [True], thresholds)


def test_approval_is_invalidated_when_any_bound_input_changes() -> None:
    first_hash = approval_binding_hash(
        request={"x": 1},
        model_sha256=HASH_A,
        registry_sha256=HASH_B,
        prediction={"y": 2},
        constraints={"passed": True},
        balances={"passed": True},
        commit="abc",
    )
    changed_hash = approval_binding_hash(
        request={"x": 2},
        model_sha256=HASH_A,
        registry_sha256=HASH_B,
        prediction={"y": 2},
        constraints={"passed": True},
        balances={"passed": True},
        commit="abc",
    )
    approval = ApprovalRecord("approval-1", first_hash, "APPROVED", "operator")
    assert approval.is_valid_for(first_hash)
    invalidated = approval.invalidate_if_changed(changed_hash)
    assert invalidated.status == "INVALIDATED"
    assert not invalidated.is_valid_for(changed_hash)


def base_signals(**overrides) -> TwinSignals:
    values = {
        "data_quality_ok": True,
        "freshness_ok": True,
        "state_estimation_ok": True,
        "surrogate_compatible": True,
        "in_applicability_domain": True,
        "drift": "OK",
        "uncertainty": 0.01,
        "uncertainty_limit": 0.05,
        "constraints_feasible": True,
        "near_constraint_boundary": False,
        "approval_required": False,
        "approval_valid": False,
        "aspen_available": True,
    }
    values.update(overrides)
    return TwinSignals(**values)


def test_twin_governance_order_and_routes() -> None:
    assert route_twin(base_signals()).route == "SURROGATE"
    assert route_twin(base_signals(in_applicability_domain=False)).route == "ASPEN"
    assert route_twin(base_signals(drift="WARNING")).route == "ASPEN"
    assert route_twin(base_signals(drift="BLOCK")).route == "ASPEN"
    assert route_twin(base_signals(constraints_feasible=False)).route == "BLOCKED"
    assert route_twin(base_signals(near_constraint_boundary=True)).route == "APPROVAL_REQUIRED"
    assert route_twin(base_signals(approval_required=True)).route == "APPROVAL_REQUIRED"
    approved = route_twin(
        base_signals(near_constraint_boundary=True, approval_valid=True)
    )
    assert approved.route == "SURROGATE"
    no_fallback = route_twin(
        base_signals(in_applicability_domain=False, aspen_available=False)
    )
    assert no_fallback.route == "BLOCKED"


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_twin_uncertainty_must_be_finite(value: float) -> None:
    with pytest.raises(ValueError, match="finite"):
        base_signals(uncertainty=value)
