from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from aspenops_nexus.process_requirement import ProcessRequirementDocument

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples/process-requirement-v1.example.json"


def document() -> dict[str, Any]:
    value = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_process_requirement_roundtrip_is_ready_and_deterministic() -> None:
    requirement = ProcessRequirementDocument.from_dict(document())
    assert requirement.readiness().status == "READY_FOR_DESIGN"
    assert requirement.readiness().blockers == ()
    assert requirement.feeds[0].display_name == "乙醇水进料"
    assert ProcessRequirementDocument.from_dict(requirement.to_dict()).digest() == requirement.digest()


def test_process_requirement_pending_values_fail_closed() -> None:
    value = document()
    value["property_method"] = {
        "value": "NRTL",
        "status": "INFERRED_PENDING_APPROVAL",
    }
    feed = value["feeds"][0]
    feed["pressure"] = {"value": None, "status": "UNKNOWN"}
    value["assumptions"]["unresolved"] = ["Confirm operating pressure"]

    readiness = ProcessRequirementDocument.from_dict(value).readiness()
    assert readiness.status == "NEEDS_ENGINEERING_INPUT"
    assert "Property method requires explicit engineering approval" in readiness.blockers
    assert "Feed FEED_001 pressure is incomplete or unapproved" in readiness.blockers
    assert readiness.pending_assumptions == ("Confirm operating pressure",)


def test_process_requirement_rejects_composition_not_summing_to_one() -> None:
    value = document()
    value["feeds"][0]["composition"][1]["fraction"] = 0.5
    with pytest.raises(ValueError, match="fractions must sum to one"):
        ProcessRequirementDocument.from_dict(value)


def test_process_requirement_rejects_undeclared_composition_component() -> None:
    value = document()
    value["feeds"][0]["composition"][1]["component_id"] = "METHANOL"
    with pytest.raises(ValueError, match="undeclared components"):
        ProcessRequirementDocument.from_dict(value)


@pytest.mark.parametrize("unsafe", ["bad\x00name", "bad\u202ename", "bad\ufffdname"])
def test_process_requirement_rejects_unsafe_unicode(unsafe: str) -> None:
    value = document()
    value["project"]["name"] = unsafe
    with pytest.raises(ValueError, match="unsafe Unicode|bidirectional"):
        ProcessRequirementDocument.from_dict(value)


def test_process_requirement_rejects_lowercase_internal_id() -> None:
    value = document()
    value["feeds"][0]["id"] = "feed_001"
    with pytest.raises(ValueError, match="must match"):
        ProcessRequirementDocument.from_dict(value)


def test_process_requirement_digest_ignores_object_key_order_but_not_content() -> None:
    first = ProcessRequirementDocument.from_dict(document())
    reordered = deepcopy(document())
    reordered["metadata"] = {"case_id": reordered["metadata"]["case_id"]}
    second = ProcessRequirementDocument.from_dict(reordered)
    assert first.digest() == second.digest()

    changed = deepcopy(document())
    changed["feeds"][0]["total_flow"]["value"] = 101.0
    assert ProcessRequirementDocument.from_dict(changed).digest() != first.digest()
