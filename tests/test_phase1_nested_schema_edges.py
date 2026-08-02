from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from aspenops_nexus.process_ir_v2 import ProcessDesignIR
from aspenops_nexus.process_requirement import ProcessRequirementDocument

ROOT = Path(__file__).resolve().parents[1]
REQUIREMENT = ROOT / "examples/process-requirement-v1.example.json"
DESIGN = ROOT / "examples/process-design-v2.example.json"


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


@pytest.mark.parametrize(
    ("section", "field"),
    [
        ("project", "raw_com_path"),
        ("process_objective", "shell"),
        ("assumptions", "auto_approve"),
    ],
)
def test_requirement_rejects_unknown_nested_fields(section: str, field: str) -> None:
    value = load(REQUIREMENT)
    value[section][field] = "not governed"
    with pytest.raises(ValueError, match="unsupported fields"):
        ProcessRequirementDocument.from_dict(value)


def test_requirement_rejects_excessive_metadata_entries() -> None:
    value = load(REQUIREMENT)
    value["metadata"] = {f"k{index}": index for index in range(1025)}
    with pytest.raises(ValueError, match="metadata contains 1025 entries"):
        ProcessRequirementDocument.from_dict(value)


def test_design_rejects_excessive_metadata_entries() -> None:
    value = load(DESIGN)
    value["metadata"] = {f"k{index}": index for index in range(1025)}
    with pytest.raises(ValueError, match="metadata contains 1025 entries"):
        ProcessDesignIR.from_dict(value)


def test_design_rejects_excessive_vendor_identifiers() -> None:
    value = load(DESIGN)
    value["components"][0]["vendor_ids"] = {
        f"vendor_{index}": f"ID_{index}" for index in range(17)
    }
    with pytest.raises(ValueError, match="vendor_ids contains 17 entries"):
        ProcessDesignIR.from_dict(value)


def test_design_rejects_excessive_reaction_stoichiometry() -> None:
    value = load(DESIGN)
    value["reactions"] = [
        {
            "id": "RXN_001",
            "kind": "stoichiometric",
            "stoichiometry": {f"C{index:03d}": 1.0 for index in range(257)},
            "phase": "liquid",
            "status": "USER_PROVIDED",
            "parameters": [],
        }
    ]
    with pytest.raises(ValueError, match="stoichiometry contains 257 entries"):
        ProcessDesignIR.from_dict(value)
