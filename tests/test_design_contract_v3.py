from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

from aspenops_nexus.design_contract import validate_design_against_requirement
from aspenops_nexus.process_ir_v2 import ProcessDesignIR
from aspenops_nexus.process_requirement import ProcessRequirementDocument

ROOT = Path(__file__).resolve().parents[1]
REQUIREMENT = ROOT / "examples/process-requirement-v1.example.json"
DESIGN = ROOT / "examples/process-design-v2.example.json"


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def linked_documents() -> tuple[ProcessRequirementDocument, ProcessDesignIR]:
    requirement = ProcessRequirementDocument.from_dict(load(REQUIREMENT))
    design = ProcessDesignIR.from_dict(load(DESIGN))
    return requirement, replace(design, requirement_hash=requirement.digest())


def test_design_contract_accepts_exact_requirement_identity() -> None:
    requirement, design = linked_documents()
    report = validate_design_against_requirement(requirement, design)
    assert report.valid is True
    assert report.issues == ()
    assert report.requirement_hash == requirement.digest()
    assert report.design_hash == design.digest()


def test_design_contract_rejects_requirement_hash_mismatch() -> None:
    requirement, design = linked_documents()
    report = validate_design_against_requirement(
        requirement,
        replace(design, requirement_hash="0" * 64),
    )
    assert report.valid is False
    assert {item.code for item in report.issues} == {"identity.requirement_hash_mismatch"}


def test_design_contract_rejects_target_and_property_method_changes() -> None:
    requirement, design = linked_documents()
    changed_method = replace(design.property_method, id="PENG_ROBINSON")
    changed = replace(
        design,
        target_simulator="hysys",
        target_version="14",
        property_method=changed_method,
    )
    codes = {
        item.code for item in validate_design_against_requirement(requirement, changed).issues
    }
    assert codes == {
        "target.simulator_mismatch",
        "target.version_mismatch",
        "property_method.mismatch",
    }


def test_design_contract_rejects_missing_components_and_boundaries() -> None:
    requirement, design = linked_documents()
    changed = replace(
        design,
        components=tuple(item for item in design.components if item.id != "WATER"),
        equipment=tuple(
            item for item in design.equipment if item.id not in {"FEED_001", "LIQ_PROD_001"}
        ),
    )
    codes = {
        item.code for item in validate_design_against_requirement(requirement, changed).issues
    }
    assert codes == {"components.missing", "feeds.missing", "products.missing"}


def test_design_contract_rejects_unapproved_extra_component() -> None:
    requirement, design = linked_documents()
    extra = replace(
        design.components[0],
        id="METHANOL",
        display_name="Methanol",
        vendor_ids={"aspen_plus": "METHANOL"},
        cas="67-56-1",
        formula="CH4O",
        molecular_weight=32.04186,
    )
    changed = replace(design, components=(*design.components, extra))
    report = validate_design_against_requirement(requirement, changed)
    assert report.valid is False
    assert {item.code for item in report.issues} == {"components.unapproved"}


def test_design_contract_rejects_unapproved_extra_boundaries() -> None:
    requirement, design = linked_documents()
    extra_feed = replace(design.equipment[0], id="FEED_999")
    extra_product = replace(design.equipment[-1], id="PROD_999")
    changed = replace(
        design,
        equipment=(*design.equipment, extra_feed, extra_product),
    )
    codes = {
        item.code for item in validate_design_against_requirement(requirement, changed).issues
    }
    assert {"feeds.unapproved", "products.unapproved"}.issubset(codes)


def test_design_contract_rejects_requirement_with_pending_assumptions() -> None:
    raw = load(REQUIREMENT)
    raw["assumptions"]["unresolved"] = ["Confirm flash pressure"]
    requirement = ProcessRequirementDocument.from_dict(raw)
    design = ProcessDesignIR.from_dict(load(DESIGN))
    design = replace(design, requirement_hash=requirement.digest())
    report = validate_design_against_requirement(requirement, design)
    assert report.valid is False
    assert any(item.code == "requirement.not_ready" for item in report.issues)
