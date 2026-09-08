from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from aspenops_nexus.design_validation import (
    load_strict_json_object,
    validate_design_documents,
)
from aspenops_nexus.process_requirement import ProcessRequirementDocument

ROOT = Path(__file__).resolve().parents[1]
REQUIREMENT = ROOT / "examples/process-requirement-v1.example.json"
DESIGN = ROOT / "examples/process-design-v2.example.json"


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def linked_documents() -> tuple[dict[str, Any], dict[str, Any]]:
    requirement = load(REQUIREMENT)
    design = load(DESIGN)
    requirement_hash = ProcessRequirementDocument.from_dict(requirement).digest()
    design["requirement_hash"] = requirement_hash
    return requirement, design


def test_offline_design_validation_emits_plan_only_preview() -> None:
    requirement, design = linked_documents()
    report = validate_design_documents(requirement, design)
    assert report["valid"] is True
    assert report["status"] == "PLAN_ONLY"
    assert report["preview"]["design_hash"] == report["design_hash"]
    assert "does not authorize COM execution" in report["boundary"]


def test_offline_design_validation_suppresses_preview_on_blocker() -> None:
    requirement, design = linked_documents()
    design["equipment"][1]["parameters"][0]["status"] = "UNKNOWN"
    report = validate_design_documents(requirement, design)
    assert report["valid"] is False
    assert report["status"] == "NEEDS_ENGINEERING_INPUT"
    assert report["preview"] is None
    assert report["engineering_validation"]["blockers"]


def test_offline_design_validation_rejects_unlinked_design() -> None:
    requirement, design = linked_documents()
    design["requirement_hash"] = "0" * 64
    report = validate_design_documents(requirement, design)
    assert report["valid"] is False
    assert any(
        issue["code"] == "identity.requirement_hash_mismatch"
        for issue in report["design_contract"]["issues"]
    )


def test_strict_loader_rejects_duplicate_keys_nonfinite_and_nonobject(tmp_path: Path) -> None:
    duplicate = tmp_path / "duplicate.json"
    duplicate.write_text('{"a":1,"a":2}', encoding="utf-8")
    with pytest.raises(ValueError, match="Duplicate JSON key"):
        load_strict_json_object(duplicate)

    nonfinite = tmp_path / "nonfinite.json"
    nonfinite.write_text('{"a":NaN}', encoding="utf-8")
    with pytest.raises(ValueError, match="non-finite"):
        load_strict_json_object(nonfinite)

    array = tmp_path / "array.json"
    array.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="root must be an object"):
        load_strict_json_object(array)
