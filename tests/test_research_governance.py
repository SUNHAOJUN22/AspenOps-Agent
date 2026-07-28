from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable

import pytest

from aspenops_nexus.research import ResearchStudyDocument

ROOT = Path(__file__).resolve().parents[1]
EPM = ROOT / "examples" / "research-study.example.json"
EPDM = ROOT / "examples" / "research-epdm-structure-only.example.json"


def _payload(path: Path = EPM) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _codes(payload: dict[str, Any]) -> set[str]:
    document = ResearchStudyDocument.from_dict(payload)
    return {item.code for item in document.validate().issues}


def _study(payload: dict[str, Any]) -> dict[str, Any]:
    value = payload["study"]
    assert isinstance(value, dict)
    return value


def _item(payload: dict[str, Any], collection: str, index: int = 0) -> dict[str, Any]:
    values = payload[collection]
    assert isinstance(values, list)
    value = values[index]
    assert isinstance(value, dict)
    return value


def test_complete_examples_and_canonical_hashes_are_stable() -> None:
    epm = ResearchStudyDocument.from_dict(_payload())
    epdm = ResearchStudyDocument.from_dict(_payload(EPDM))

    assert epm.validate().status == "PASS"
    assert epdm.validate().status == "PASS"
    assert epdm.validate().computed_claim_ceiling == "STRUCTURE_ONLY"
    round_trip = ResearchStudyDocument.from_dict(epm.to_dict())
    assert epm.canonical_sha256() == round_trip.canonical_sha256()


def test_epdm_template_is_structure_only_without_estimation_or_validation() -> None:
    document = ResearchStudyDocument.from_dict(_payload(EPDM))

    assert document.study.domain["polymer_system"] == "EPDM"
    assert document.study.claim_ceiling == "STRUCTURE_ONLY"
    assert not document.parameters
    assert not document.calibrations
    assert not document.validations
    assert document.assumptions[0].category == "source_contradiction"
    assert document.assumptions[0].contradiction_group


@pytest.mark.parametrize(
    ("mutate", "expected"),
    [
        (
            lambda value: _study(value)["object_refs"].pop(),
            "study_missing_object_ref",
        ),
        (
            lambda value: _study(value)["object_refs"].append(
                {"type": "target", "id": "target.missing"}
            ),
            "study_unresolved_object_ref",
        ),
        (
            lambda value: _item(value, "targets")["dataset_binding"].update(
                {"dataset_id": "dataset.missing"}
            ),
            "target_dataset_missing",
        ),
        (
            lambda value: _item(value, "targets")["dataset_binding"].update(
                {"variable": "missing"}
            ),
            "target_variable_missing",
        ),
        (
            lambda value: _item(value, "assumptions").update(
                {"category": "source_contradiction", "contradiction_group": None}
            ),
            "contradiction_group_required",
        ),
    ],
)
def test_inventory_target_and_assumption_edges(
    mutate: Callable[[dict[str, Any]], object],
    expected: str,
) -> None:
    payload = _payload()
    mutate(payload)
    assert expected in _codes(payload)


@pytest.mark.parametrize(
    ("collection", "role", "expected"),
    [
        ("datasets", "validation", "calibration_dataset_role"),
        ("datasets", "calibration", "validation_dataset_role"),
    ],
)
def test_calibration_and_validation_dataset_roles(
    collection: str,
    role: str,
    expected: str,
) -> None:
    payload = _payload()
    index = 0 if expected.startswith("calibration") else 1
    _item(payload, collection, index)["role"] = role
    assert expected in _codes(payload)


@pytest.mark.parametrize(
    ("field", "digest", "expected"),
    [
        ("parameter_snapshot", "0" * 64, "validation_snapshot_mismatch"),
        ("model_snapshot", "0" * 64, "validation_model_snapshot_mismatch"),
        ("registry_snapshot", "0" * 64, "validation_registry_snapshot_mismatch"),
    ],
)
def test_validation_snapshot_binding(field: str, digest: str, expected: str) -> None:
    payload = _payload()
    snapshot = _item(payload, "validations")[field]
    assert isinstance(snapshot, dict)
    snapshot["sha256"] = digest
    assert expected in _codes(payload)


@pytest.mark.parametrize(
    ("field", "expected"),
    [
        ("data_artifact", "calibration_validation_artifact_leakage"),
        ("split_group", "calibration_validation_split_group_leakage"),
        ("record_set_sha256", "calibration_validation_record_leakage"),
    ],
)
def test_calibration_validation_leakage(field: str, expected: str) -> None:
    payload = _payload()
    calibration = _item(payload, "datasets", 0)
    validation = _item(payload, "datasets", 1)
    if field == "data_artifact":
        validation[field] = deepcopy(calibration[field])
    else:
        validation[field] = calibration[field]
    assert expected in _codes(payload)


def test_same_dataset_cannot_serve_calibration_and_validation() -> None:
    payload = _payload()
    validation = _item(payload, "validations")
    validation["dataset_refs"] = [{"type": "dataset", "id": "dataset.epm.calibration"}]
    assert "calibration_validation_dataset_leakage" in _codes(payload)


def test_source_reproduction_cannot_be_relabelled_as_independent_validation() -> None:
    payload = _payload()
    _study(payload)["purpose"] = "source_reproduction"
    assert "source_reproduction_claim_ceiling" in _codes(payload)


def test_unresolved_critical_assumption_caps_claim_at_structure_only() -> None:
    payload = _payload()
    _item(payload, "assumptions")["status"] = "unresolved"
    assert "claim_blocked_by_critical_assumption" in _codes(payload)


def test_claim_must_propagate_assumption_restrictions() -> None:
    payload = _payload()
    claim = _item(payload, "claims")
    claim["limitations"] = ["Only the declared grades are covered."]
    claim["prohibited_interpretations"] = ["Mock evidence is not engineering qualification."]
    assert "claim_missing_assumption_restriction" in _codes(payload)


def test_claim_requires_passed_validation_and_respects_validation_ceiling() -> None:
    payload = _payload()
    validation = _item(payload, "validations")
    validation["status"] = "failed"
    validation["blockers"] = ["declared failure"]
    validation["results_artifact"] = None
    codes = _codes(payload)
    assert "claim_requires_passed_validation" in codes
    assert "claim_exceeds_validation_ceiling" in codes


def test_licensed_claim_requires_real_engineering_approval() -> None:
    payload = _payload()
    study = _study(payload)
    study["claim_ceiling"] = "LICENSED_ENGINEERING_REVIEWED"
    claim = _item(payload, "claims")
    claim["maturity"] = "LICENSED_ENGINEERING_REVIEWED"
    validation = _item(payload, "validations")
    validation["claim_ceiling_result"] = "LICENSED_ENGINEERING_REVIEWED"
    codes = _codes(payload)
    assert "licensed_claim_backend_policy" in codes
    assert "licensed_claim_missing_engineering_validation" in codes


def test_claim_hash_mismatch_is_rejected() -> None:
    payload = _payload()
    _item(payload, "claims")["claim_sha256"] = "0" * 64
    assert "claim_hash_mismatch" in _codes(payload)


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        ("calibrated", "study_lifecycle_missing_calibration"),
        ("validated", "study_lifecycle_missing_validation"),
        ("claim_ready", "study_lifecycle_missing_claim"),
    ],
)
def test_model_qualification_lifecycle_is_evidence_driven(state: str, expected: str) -> None:
    payload = _payload(EPDM)
    _study(payload)["lifecycle_state"] = state
    assert expected in _codes(payload)
