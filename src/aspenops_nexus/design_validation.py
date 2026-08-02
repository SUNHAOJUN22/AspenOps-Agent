from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .design_contract import validate_design_against_requirement
from .engineering_rules import validate_process_design
from .flowsheet_preview import render_flowsheet_preview
from .process_ir_v2 import ProcessDesignIR
from .process_requirement import ProcessRequirementDocument


def _duplicate_key_rejected(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in pairs:
        if key in output:
            raise ValueError(f"Duplicate JSON key: {key}")
        output[key] = value
    return output


def _nonfinite_rejected(value: str) -> Any:
    raise ValueError(f"JSON contains non-finite constant: {value}")


def load_strict_json_object(path: str | Path) -> dict[str, Any]:
    value = json.loads(
        Path(path).read_text(encoding="utf-8"),
        object_pairs_hook=_duplicate_key_rejected,
        parse_constant=_nonfinite_rejected,
    )
    if not isinstance(value, dict):
        raise ValueError("JSON document root must be an object")
    return value


def validate_design_documents(
    requirement_document: dict[str, Any],
    design_document: dict[str, Any],
) -> dict[str, Any]:
    requirement = ProcessRequirementDocument.from_dict(requirement_document)
    design = ProcessDesignIR.from_dict(design_document)
    readiness = requirement.readiness()
    identity = validate_design_against_requirement(requirement, design)
    engineering = validate_process_design(design)
    valid = readiness.status == "READY_FOR_DESIGN" and identity.valid and engineering.valid
    preview = render_flowsheet_preview(design) if valid else None
    return {
        "schema": "aspenops.design-validation/v1",
        "valid": valid,
        "status": "PLAN_ONLY" if valid else "NEEDS_ENGINEERING_INPUT",
        "requirement_hash": requirement.digest(),
        "design_hash": design.digest(),
        "requirement_readiness": readiness.to_dict(),
        "design_contract": identity.to_dict(),
        "engineering_validation": engineering.to_dict(),
        "preview": None if preview is None else preview.to_dict(),
        "boundary": (
            "A valid result authorizes only an offline deterministic design plan. It does not "
            "authorize COM execution or prove Aspen/HYSYS native topology or physics."
        ),
    }


def validate_design_files(
    requirement_path: str | Path,
    design_path: str | Path,
) -> dict[str, Any]:
    return validate_design_documents(
        load_strict_json_object(requirement_path),
        load_strict_json_object(design_path),
    )
