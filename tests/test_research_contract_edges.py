from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Callable

import pytest

from aspenops_nexus import research
from aspenops_nexus.research import (
    ArtifactRef,
    Assumption,
    Calibration,
    Dataset,
    ObjectRef,
    Parameter,
    ResearchIssue,
    ResearchStudyDocument,
    ResearchValidationError,
    ResearchValidationReport,
    SourceRef,
    Study,
    Target,
    Validation,
    validate_research_document,
)

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "research-study.example.json"


def _document() -> dict[str, object]:
    value = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _first(document: dict[str, object], key: str) -> dict[str, object]:
    values = document[key]
    assert isinstance(values, list) and values
    value = values[0]
    assert isinstance(value, dict)
    return value


def _codes(document: dict[str, object]) -> set[str]:
    return {item.code for item in validate_research_document(document).issues}


@pytest.mark.parametrize(
    ("call", "message"),
    [
        (lambda: research._mapping([], "value"), "must be an object"),
        (lambda: research._sequence({}, "value"), "must be an array"),
        (lambda: research._text(1, "value"), "must be a string"),
        (lambda: research._text("  ", "value"), "non-empty string"),
        (lambda: research._text("x\ny", "value"), "safe text line"),
        (lambda: research._boolean("true", "value"), "must be a boolean"),
        (lambda: research._finite_number(True, "value"), "finite number"),
        (lambda: research._finite_number(float("inf"), "value"), "finite number"),
        (lambda: research._scalar(None, "value"), "finite scalar"),
        (lambda: research._enum("bad", {"good"}, "value"), "must be one of"),
        (
            lambda: research._reject_unknown({"bad": 1}, {"good"}, "value"),
            "unsupported fields",
        ),
        (lambda: research._safe_json(float("nan"), "value"), "non-finite"),
        (lambda: research._safe_json({1, 2}, "value"), "non-JSON"),
        (lambda: research._strings([], "value", nonempty=True), "at least one"),
        (lambda: research._strings(["x", "x"], "value"), "duplicates"),
        (lambda: research._id("wrong.prefix", "study", "value"), "study. prefix"),
        (lambda: research._optional_sha256("bad", "value"), "SHA-256"),
    ],
)
def test_low_level_rejections(call: Callable[[], object], message: str) -> None:
    with pytest.raises(ResearchValidationError, match=message):
        call()


def test_low_level_success_and_depth_paths() -> None:
    nested: object = "end"
    for _ in range(research.MAX_JSON_DEPTH + 2):
        nested = [nested]
    with pytest.raises(ResearchValidationError, match="nesting depth"):
        research._safe_json(nested, "nested")

    assert research._optional_text(None, "value") is None
    assert research._optional_sha256(None, "value") is None
    assert research._scalar(True, "value") is True
    assert research._scalar("value", "value") == "value"
    assert research._scalar(3, "value") == 3
    assert research._scalar(3.5, "value") == 3.5
    assert research._safe_json({"items": [1, 2.5, None]}, "value") == {
        "items": [1, 2.5, None]
    }


def test_artifact_source_semantic_and_reference_contracts() -> None:
    with pytest.raises(ResearchValidationError, match="mutable web URL"):
        ArtifactRef.from_dict({"uri": "https://example.invalid/file", "sha256": "a" * 64})
    with pytest.raises(ResearchValidationError, match="sha256 is required"):
        ArtifactRef.from_dict({"uri": "artifact:no-hash", "sha256": None})

    artifact = ArtifactRef.from_dict(
        {
            "uri": "artifact:test/value.json",
            "sha256": "a" * 64,
            "media_type": "application/json",
            "producer": {"type": "calibration", "id": "calibration.test"},
        }
    )
    assert artifact.to_dict()["media_type"] == "application/json"
    assert artifact.to_dict()["producer"] == {
        "type": "calibration",
        "id": "calibration.test",
    }

    source = SourceRef.from_dict(
        {
            "source_id": "source.test",
            "kind": "literature",
            "citation": "Citation",
            "locator": "p. 1",
            "sha256": "b" * 64,
        },
        label="source",
    )
    assert source.to_dict()["locator"] == "p. 1"
    assert source.to_dict()["sha256"] == "b" * 64

    binding = research.SemanticBinding.from_dict(
        {"key": "safe.key", "identifiers": {"site": "1"}, "access": "read"},
        label="binding",
    )
    assert binding.to_dict() == {
        "key": "safe.key",
        "identifiers": {"site": "1"},
        "access": "read",
    }

    with pytest.raises(ResearchValidationError):
        research._refs([], "refs", nonempty=True)
    with pytest.raises(ResearchValidationError):
        research._refs(
            [
                {"type": "dataset", "id": "dataset.one"},
                {"type": "dataset", "id": "dataset.one"},
            ],
            "refs",
        )
    with pytest.raises(ResearchValidationError):
        research._sources([], "sources", nonempty=True)
    with pytest.raises(ResearchValidationError):
        research._sources(
            [
                {"source_id": "source.one", "kind": "model", "citation": "one"},
                {"source_id": "source.one", "kind": "model", "citation": "two"},
            ],
            "sources",
        )


def test_dataset_target_parameter_and_assumption_shapes() -> None:
    with pytest.raises(ResearchValidationError, match="Registry key"):
        research.DatasetVariable.from_dict(
            {
                "name": "bad",
                "semantic_key": "\\Data\\bad",
                "unit": "1",
                "data_type": "number",
                "role": "target",
                "missing_policy": "reject",
            },
            label="variable",
        )

    dataset = _first(_document(), "datasets")
    no_variables = copy.deepcopy(dataset)
    no_variables["variables"] = []
    with pytest.raises(ResearchValidationError, match="must not be empty"):
        Dataset.from_dict(no_variables)
    duplicate_variables = copy.deepcopy(dataset)
    variables = duplicate_variables["variables"]
    assert isinstance(variables, list)
    variables.append(copy.deepcopy(variables[0]))
    with pytest.raises(ResearchValidationError, match="variable names must be unique"):
        Dataset.from_dict(duplicate_variables)
    missing_identity = copy.deepcopy(dataset)
    missing_identity["record_identity"] = ["undeclared"]
    with pytest.raises(ResearchValidationError, match="undeclared variables"):
        Dataset.from_dict(missing_identity)

    optional_dataset = copy.deepcopy(dataset)
    optional_dataset["operating_envelope"] = None
    optional_dataset["reconciliation"] = None
    optional_dataset["sampling"] = None
    parsed_dataset = Dataset.from_dict(optional_dataset)
    assert parsed_dataset.operating_envelope is None
    assert parsed_dataset.reconciliation is None
    assert parsed_dataset.sampling is None

    target = _first(_document(), "targets")
    no_transform = copy.deepcopy(target)
    no_transform["transform"] = None
    assert Target.from_dict(no_transform).transform is None
    declared_transform = copy.deepcopy(target)
    declared_transform["transform"] = {"name": "declared", "version": 1}
    assert Target.from_dict(declared_transform).transform == {
        "name": "declared",
        "version": 1,
    }
    wrong_access = copy.deepcopy(target)
    binding = wrong_access["semantic_binding"]
    assert isinstance(binding, dict)
    binding["access"] = "write"
    with pytest.raises(ResearchValidationError, match="access must be read"):
        Target.from_dict(wrong_access)

    parameter = _first(_document(), "parameters")
    wrong_access = copy.deepcopy(parameter)
    binding = wrong_access["semantic_binding"]
    assert isinstance(binding, dict)
    binding["access"] = "read"
    with pytest.raises(ResearchValidationError, match="access must be write"):
        Parameter.from_dict(wrong_access)
    invalid_bounds = copy.deepcopy(parameter)
    invalid_bounds["bounds"] = {"lower": 2.0, "upper": 1.0}
    with pytest.raises(ResearchValidationError, match="lower < upper"):
        Parameter.from_dict(invalid_bounds)
    missing_bounds = copy.deepcopy(parameter)
    missing_bounds["bounds"] = None
    with pytest.raises(ResearchValidationError, match="requires finite bounds"):
        Parameter.from_dict(missing_bounds)
    bad_initial = copy.deepcopy(parameter)
    bad_initial["initial_value"] = 0.0
    with pytest.raises(ResearchValidationError, match="initial_value must be positive"):
        Parameter.from_dict(bad_initial)
    bad_lower = copy.deepcopy(parameter)
    bad_lower["bounds"] = {"lower": 0.0, "upper": 1.0}
    bad_lower["initial_value"] = 0.5
    with pytest.raises(ResearchValidationError, match="lower bound must be positive"):
        Parameter.from_dict(bad_lower)
    diagnostic = copy.deepcopy(parameter)
    diagnostic["identifiability"] = {"condition_number": 12.0, "status": "acceptable"}
    assert Parameter.from_dict(diagnostic).identifiability == {
        "condition_number": 12.0,
        "status": "acceptable",
    }

    assumption = _first(_document(), "assumptions")
    structured = copy.deepcopy(assumption)
    structured["risk"] = {"severity": "critical", "likelihood": "possible"}
    structured["falsification_test"] = {"kind": "experiment", "required": True}
    structured["resolution"] = {"decision": "retain"}
    parsed = Assumption.from_dict(structured)
    assert isinstance(parsed.risk, dict)
    assert isinstance(parsed.falsification_test, dict)
    assert parsed.resolution == {"decision": "retain"}
    absent = copy.deepcopy(assumption)
    absent["falsification_test"] = None
    assert Assumption.from_dict(absent).falsification_test is None


def test_calibration_validation_study_and_report_structures(tmp_path: Path) -> None:
    calibration = _first(_document(), "calibrations")
    invalid_calibration = copy.deepcopy(calibration)
    invalid_calibration["accepted_parameter_snapshot"] = None
    with pytest.raises(ResearchValidationError, match="accepted_parameter_snapshot"):
        Calibration.from_dict(invalid_calibration)

    validation = _first(_document(), "validations")
    missing_result = copy.deepcopy(validation)
    missing_result["results_artifact"] = None
    with pytest.raises(ResearchValidationError, match="requires results_artifact"):
        Validation.from_dict(missing_result)
    blocked_pass = copy.deepcopy(validation)
    blocked_pass["blockers"] = ["missing evidence"]
    with pytest.raises(ResearchValidationError, match="requires results_artifact"):
        Validation.from_dict(blocked_pass)

    study = _document()["study"]
    assert isinstance(study, dict)
    empty = copy.deepcopy(study)
    policy = empty["backend_policy"]
    assert isinstance(policy, dict)
    policy["allowed_backends"] = []
    with pytest.raises(ResearchValidationError, match="non-empty array"):
        Study.from_dict(empty)
    wrong_boolean = copy.deepcopy(study)
    policy = wrong_boolean["backend_policy"]
    assert isinstance(policy, dict)
    policy["allow_mock"] = "yes"
    with pytest.raises(ResearchValidationError, match="requires boolean"):
        Study.from_dict(wrong_boolean)
    inconsistent_mock = copy.deepcopy(study)
    policy = inconsistent_mock["backend_policy"]
    assert isinstance(policy, dict)
    policy["allow_mock"] = False
    with pytest.raises(ResearchValidationError, match="cannot include mock"):
        Study.from_dict(inconsistent_mock)
    no_real = copy.deepcopy(study)
    policy = no_real["backend_policy"]
    assert isinstance(policy, dict)
    policy["allowed_backends"] = ["mock"]
    policy["require_licensed_windows"] = True
    with pytest.raises(ResearchValidationError, match="requires aspen_plus or hysys"):
        Study.from_dict(no_real)

    issue = ResearchIssue(
        severity="error",
        code="example",
        message="message",
        object_ref=ObjectRef("study", "study.example"),
        path="study.field",
    )
    report = ResearchValidationReport(
        status="FAIL",
        issues=(issue,),
        object_counts={"study": 1},
        canonical_sha256="a" * 64,
        computed_claim_ceiling="STRUCTURE_ONLY",
    )
    assert report.ok is False
    assert report.to_dict()["schema"] == "aspenops.research-validation/v1"

    valid = tmp_path / "valid.json"
    valid.write_text(json.dumps(_document()), encoding="utf-8")
    assert ResearchStudyDocument.load(valid).schema == research.RESEARCH_SCHEMA
    invalid = tmp_path / "invalid.json"
    invalid.write_bytes(b"{not-json")
    with pytest.raises(ResearchValidationError, match="invalid research JSON"):
        ResearchStudyDocument.load(invalid)


def test_graph_inventory_target_and_assumption_edges() -> None:
    missing_decl = _document()
    study = missing_decl["study"]
    assert isinstance(study, dict)
    refs = study["object_refs"]
    assert isinstance(refs, list)
    refs.pop()
    assert "study_missing_object_ref" in _codes(missing_decl)

    extra_decl = _document()
    study = extra_decl["study"]
    assert isinstance(study, dict)
    refs = study["object_refs"]
    assert isinstance(refs, list)
    refs.append({"type": "claim", "id": "claim.missing"})
    assert "study_unresolved_object_ref" in _codes(extra_decl)

    unresolved_dependency = _document()
    _first(unresolved_dependency, "targets")["dependencies"] = [
        {"type": "target", "id": "target.missing"}
    ]
    assert "unresolved_reference" in _codes(unresolved_dependency)

    missing_dataset = _document()
    binding = _first(missing_dataset, "targets")["dataset_binding"]
    assert isinstance(binding, dict)
    binding["dataset_id"] = "dataset.missing"
    assert "target_dataset_missing" in _codes(missing_dataset)

    missing_variable = _document()
    binding = _first(missing_variable, "targets")["dataset_binding"]
    assert isinstance(binding, dict)
    binding["variable"] = "missing"
    assert "target_variable_missing" in _codes(missing_variable)

    rejected = _document()
    assumption = _first(rejected, "assumptions")
    assumption["status"] = "rejected"
    assert "assumption_resolution_missing" in _codes(rejected)

    unresolved = _document()
    assumption = _first(unresolved, "assumptions")
    assumption["affected_objects"] = [{"type": "claim", "id": "claim.missing"}]
    assert "unresolved_reference" in _codes(unresolved)


def test_calibration_and_validation_graph_edges() -> None:
    wrong_dataset_type = _document()
    calibration = _first(wrong_dataset_type, "calibrations")
    calibration["dataset_refs"] = [
        {"type": "target", "id": "target.production.calibration"}
    ]
    assert "calibration_dataset_type" in _codes(wrong_dataset_type)

    wrong_target_type = _document()
    calibration = _first(wrong_target_type, "calibrations")
    calibration["target_refs"] = [
        {"type": "parameter", "id": "parameter.kinetic.propagation"}
    ]
    assert "calibration_target_type" in _codes(wrong_target_type)

    bad_target_role = _document()
    _first(bad_target_role, "targets")["role"] = "monitoring"
    assert "calibration_target_role" in _codes(bad_target_role)

    wrong_parameter_type = _document()
    calibration = _first(wrong_parameter_type, "calibrations")
    calibration["parameter_refs"] = [
        {"type": "target", "id": "target.production.calibration"}
    ]
    assert "calibration_parameter_type" in _codes(wrong_parameter_type)

    no_estimated = _document()
    _first(no_estimated, "parameters")["mode"] = "fixed"
    assert "calibration_no_estimated_parameter" in _codes(no_estimated)

    wrong_producer = _document()
    snapshot = _first(wrong_producer, "calibrations")["accepted_parameter_snapshot"]
    assert isinstance(snapshot, dict)
    snapshot["producer"] = {"type": "calibration", "id": "calibration.other"}
    assert "calibration_snapshot_producer" in _codes(wrong_producer)

    wrong_validation_dataset_type = _document()
    validation = _first(wrong_validation_dataset_type, "validations")
    validation["dataset_refs"] = [
        {"type": "target", "id": "target.production.validation"}
    ]
    assert "validation_dataset_type" in _codes(wrong_validation_dataset_type)

    bad_dataset_role = _document()
    datasets = bad_dataset_role["datasets"]
    assert isinstance(datasets, list)
    assert isinstance(datasets[1], dict)
    datasets[1]["role"] = "calibration"
    assert "validation_dataset_role" in _codes(bad_dataset_role)

    wrong_validation_target_type = _document()
    validation = _first(wrong_validation_target_type, "validations")
    validation["target_refs"] = [
        {"type": "parameter", "id": "parameter.kinetic.propagation"}
    ]
    assert "validation_target_type" in _codes(wrong_validation_target_type)

    no_producer = _document()
    snapshot = _first(no_producer, "validations")["parameter_snapshot"]
    assert isinstance(snapshot, dict)
    snapshot["producer"] = None
    assert "validation_snapshot_missing_calibration" in _codes(no_producer)

    missing_calibration = _document()
    snapshot = _first(missing_calibration, "validations")["parameter_snapshot"]
    assert isinstance(snapshot, dict)
    snapshot["producer"] = {"type": "calibration", "id": "calibration.missing"}
    assert "validation_calibration_missing" in _codes(missing_calibration)

    not_accepted = _document()
    _first(not_accepted, "calibrations")["status"] = "converged"
    assert "validation_calibration_not_accepted" in _codes(not_accepted)


def test_leakage_claim_and_lifecycle_edges() -> None:
    same_dataset = _document()
    _first(same_dataset, "validations")["dataset_refs"] = [
        {"type": "dataset", "id": "dataset.epm.calibration"}
    ]
    assert "calibration_validation_dataset_leakage" in _codes(same_dataset)

    wrong_validation_type = _document()
    claim = _first(wrong_validation_type, "claims")
    claim["validation_refs"] = [
        {"type": "calibration", "id": "calibration.epm.production"}
    ]
    claim["claim_sha256"] = None
    assert "claim_validation_type" in _codes(wrong_validation_type)

    wrong_assumption_type = _document()
    claim = _first(wrong_assumption_type, "claims")
    claim["assumption_refs"] = [
        {"type": "validation", "id": "validation.epm.heldout-grade"}
    ]
    claim["claim_sha256"] = None
    assert "claim_assumption_type" in _codes(wrong_assumption_type)

    no_passed = _document()
    claim = _first(no_passed, "claims")
    claim["validation_refs"] = []
    claim["claim_sha256"] = None
    assert "claim_requires_passed_validation" in _codes(no_passed)

    no_validation = _document()
    no_validation["validations"] = []
    no_validation["claims"] = []
    study = no_validation["study"]
    assert isinstance(study, dict)
    study["lifecycle_state"] = "specified"
    refs = study["object_refs"]
    assert isinstance(refs, list)
    refs[:] = [
        item
        for item in refs
        if isinstance(item, dict) and item.get("type") not in {"validation", "claim"}
    ]
    report = validate_research_document(no_validation)
    assert report.computed_claim_ceiling == "SOURCE_CASE_REPRODUCED"

    missing_calibration = _document()
    _first(missing_calibration, "calibrations")["status"] = "rejected"
    assert "study_lifecycle_missing_calibration" in _codes(missing_calibration)

    missing_validation = _document()
    _first(missing_validation, "validations")["status"] = "failed"
    assert "study_lifecycle_missing_validation" in _codes(missing_validation)

    missing_claim = _document()
    claim = _first(missing_claim, "claims")
    claim["status"] = "proposed"
    claim["claim_sha256"] = None
    assert "study_lifecycle_missing_claim" in _codes(missing_claim)
