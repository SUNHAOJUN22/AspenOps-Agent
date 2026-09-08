from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from aspenops_nexus.research import ResearchStudyDocument

ROOT = Path(__file__).resolve().parents[1]
EPM_EXAMPLE = ROOT / "examples" / "research-study.example.json"
EPDM_EXAMPLE = ROOT / "examples" / "research-epdm-structure-only.example.json"


def _payload(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _codes(document: ResearchStudyDocument) -> set[str]:
    return {issue.code for issue in document.validate().issues}


def test_complete_research_examples_validate() -> None:
    epm = ResearchStudyDocument.from_dict(_payload(EPM_EXAMPLE))
    epdm = ResearchStudyDocument.from_dict(_payload(EPDM_EXAMPLE))

    assert epm.validate().status == "PASS"
    epdm_report = epdm.validate()
    assert epdm_report.status == "PASS"
    assert epdm_report.computed_claim_ceiling == "STRUCTURE_ONLY"
    assert epdm.study.domain["polymer_system"] == "EPDM"
    assert epdm.assumptions[0].category == "source_contradiction"
    assert epdm.assumptions[0].contradiction_group


def test_source_reproduction_cannot_claim_independent_validation() -> None:
    payload = deepcopy(_payload(EPM_EXAMPLE))
    study = payload["study"]
    assert isinstance(study, dict)
    study["purpose"] = "source_reproduction"

    document = ResearchStudyDocument.from_dict(payload)
    assert "source_reproduction_claim_ceiling" in _codes(document)


def test_unresolved_critical_assumption_limits_claim_maturity() -> None:
    payload = deepcopy(_payload(EPM_EXAMPLE))
    assumptions = payload["assumptions"]
    assert isinstance(assumptions, list)
    assumption = assumptions[0]
    assert isinstance(assumption, dict)
    assumption["status"] = "unresolved"

    document = ResearchStudyDocument.from_dict(payload)
    assert "claim_blocked_by_critical_assumption" in _codes(document)


def test_epdm_example_has_no_parameter_estimation_or_validation() -> None:
    payload = _payload(EPDM_EXAMPLE)
    assert payload["parameters"] == []
    assert payload["calibrations"] == []
    assert payload["validations"] == []

    study = payload["study"]
    assert isinstance(study, dict)
    assert study["claim_ceiling"] == "STRUCTURE_ONLY"
    policy = study["calibration_validation_policy"]
    assert isinstance(policy, dict)
    assert policy["parameter_estimation_allowed"] is False
