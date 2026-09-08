from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from aspenops_nexus.research import (
    RESEARCH_SCHEMA,
    ResearchStudyDocument,
    ResearchValidationError,
    validate_research_document,
)

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "research-study.example.json"


def _document() -> dict[str, object]:
    value = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _codes(document: dict[str, object]) -> set[str]:
    return {item.code for item in validate_research_document(document).issues}


def test_valid_research_study_passes_and_round_trips() -> None:
    document = ResearchStudyDocument.from_dict(_document())
    report = document.validate()

    assert document.schema == RESEARCH_SCHEMA
    assert report.ok
    assert report.status == "PASS"
    assert report.computed_claim_ceiling == "VALIDATED_HELD_OUT"
    assert report.object_counts == {
        "study": 1,
        "dataset": 2,
        "target": 2,
        "parameter": 1,
        "assumption": 1,
        "calibration": 1,
        "validation": 1,
        "claim": 1,
    }
    reconstructed = ResearchStudyDocument.from_dict(document.to_dict())
    assert reconstructed.canonical_sha256() == document.canonical_sha256()


def test_duplicate_research_object_is_rejected() -> None:
    document = _document()
    datasets = document["datasets"]
    assert isinstance(datasets, list)
    datasets.append(copy.deepcopy(datasets[0]))

    with pytest.raises(ResearchValidationError, match="duplicate research object"):
        ResearchStudyDocument.from_dict(document).validate()


def test_raw_simulator_path_is_rejected() -> None:
    document = _document()
    targets = document["targets"]
    assert isinstance(targets, list)
    target = targets[0]
    assert isinstance(target, dict)
    binding = target["semantic_binding"]
    assert isinstance(binding, dict)
    binding["key"] = r"\Data\Blocks\R1\Output"

    with pytest.raises(ResearchValidationError, match="semantic Registry key"):
        ResearchStudyDocument.from_dict(document)


def test_arbitrary_executable_metadata_is_rejected() -> None:
    document = _document()
    study = document["study"]
    assert isinstance(study, dict)
    domain = study["domain"]
    assert isinstance(domain, dict)
    domain["shell"] = "echo unsafe"

    with pytest.raises(ResearchValidationError, match="forbidden key"):
        ResearchStudyDocument.from_dict(document)


def test_calibration_cannot_consume_validation_dataset() -> None:
    document = _document()
    calibrations = document["calibrations"]
    assert isinstance(calibrations, list)
    calibration = calibrations[0]
    assert isinstance(calibration, dict)
    calibration["dataset_refs"] = [{"type": "dataset", "id": "dataset.epm.validation"}]

    assert "calibration_dataset_role" in _codes(document)


def test_calibration_validation_artifact_leakage_is_rejected() -> None:
    document = _document()
    datasets = document["datasets"]
    assert isinstance(datasets, list)
    calibration = datasets[0]
    validation = datasets[1]
    assert isinstance(calibration, dict)
    assert isinstance(validation, dict)
    calibration_artifact = calibration["data_artifact"]
    validation_artifact = validation["data_artifact"]
    assert isinstance(calibration_artifact, dict)
    assert isinstance(validation_artifact, dict)
    validation_artifact["sha256"] = calibration_artifact["sha256"]

    assert "calibration_validation_artifact_leakage" in _codes(document)


def test_validation_requires_exact_accepted_parameter_snapshot() -> None:
    document = _document()
    validations = document["validations"]
    assert isinstance(validations, list)
    validation = validations[0]
    assert isinstance(validation, dict)
    snapshot = validation["parameter_snapshot"]
    assert isinstance(snapshot, dict)
    snapshot["sha256"] = "b" * 64

    assert "validation_snapshot_mismatch" in _codes(document)


def test_claim_cannot_exceed_validation_ceiling() -> None:
    document = _document()
    claims = document["claims"]
    assert isinstance(claims, list)
    claim = claims[0]
    assert isinstance(claim, dict)
    claim["maturity"] = "ROBUSTNESS_TESTED"
    claim["claim_sha256"] = None

    codes = _codes(document)
    assert "claim_exceeds_study_ceiling" in codes
    assert "claim_exceeds_validation_ceiling" in codes


def test_claim_must_propagate_assumption_restrictions() -> None:
    document = _document()
    claims = document["claims"]
    assert isinstance(claims, list)
    claim = claims[0]
    assert isinstance(claim, dict)
    claim["prohibited_interpretations"] = [
        "Mock validation is not real Aspen engineering qualification."
    ]
    claim["claim_sha256"] = None

    assert "claim_missing_assumption_restriction" in _codes(document)


def test_licensed_claim_requires_real_approved_validation() -> None:
    document = _document()
    study = document["study"]
    claims = document["claims"]
    assert isinstance(study, dict)
    assert isinstance(claims, list)
    claim = claims[0]
    assert isinstance(claim, dict)
    study["claim_ceiling"] = "LICENSED_ENGINEERING_REVIEWED"
    claim["maturity"] = "LICENSED_ENGINEERING_REVIEWED"
    claim["claim_type"] = "engineering_qualification"
    claim["claim_sha256"] = None

    codes = _codes(document)
    assert "claim_exceeds_validation_ceiling" in codes
    assert "licensed_claim_backend_policy" in codes
    assert "licensed_claim_missing_engineering_validation" in codes


def test_claim_hash_detects_silent_scope_change() -> None:
    document = _document()
    claims = document["claims"]
    assert isinstance(claims, list)
    claim = claims[0]
    assert isinstance(claim, dict)
    scope = claim["scope"]
    assert isinstance(scope, dict)
    scope["grades"] = ["G1", "G2", "G3", "G4"]

    assert "claim_hash_mismatch" in _codes(document)


def test_source_contradiction_requires_explicit_group() -> None:
    document = _document()
    assumptions = document["assumptions"]
    assert isinstance(assumptions, list)
    assumption = assumptions[0]
    assert isinstance(assumption, dict)
    assumption["category"] = "source_contradiction"
    assumption["contradiction_group"] = None

    assert "contradiction_group_required" in _codes(document)
