from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from aspenops_nexus.engineering_rules import validate_process_design
from aspenops_nexus.process_ir_v2 import ProcessDesignIR

ROOT = Path(__file__).resolve().parents[1]
DESIGN = ROOT / "examples/process-design-v2.example.json"


def document() -> dict[str, Any]:
    value = json.loads(DESIGN.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("target_simulator", "raw_com", "Unsupported process design simulator"),
        ("target_version", "13", "Unsupported process design version"),
    ],
)
def test_design_rejects_unsupported_target_contracts(
    field: str,
    value: str,
    message: str,
) -> None:
    payload = document()
    payload[field] = value
    with pytest.raises(ValueError, match=message):
        ProcessDesignIR.from_dict(payload)


def test_unknown_equipment_kind_is_an_engineering_blocker() -> None:
    payload = document()
    payload["equipment"][1]["kind"] = "llm_invented_unit"
    report = validate_process_design(ProcessDesignIR.from_dict(payload))
    assert report.valid is False
    assert any(
        issue.code == "equipment.contract_unavailable" for issue in report.blockers
    )
