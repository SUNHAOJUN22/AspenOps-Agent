from __future__ import annotations

import json
from copy import deepcopy
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


@pytest.mark.parametrize("unsafe", ["value\x00x", "value\u202ex", "value\ufffdx"])
def test_requirement_rejects_unsafe_string_scalar_metadata(unsafe: str) -> None:
    value = load(REQUIREMENT)
    value["metadata"]["operator_note"] = unsafe
    with pytest.raises(ValueError, match="unsafe Unicode|bidirectional"):
        ProcessRequirementDocument.from_dict(value)


@pytest.mark.parametrize("unsafe", ["value\x00x", "value\u202ex", "value\ufffdx"])
def test_design_rejects_unsafe_string_parameter(unsafe: str) -> None:
    value = load(DESIGN)
    value["equipment"][1]["parameters"][0]["value"] = unsafe
    with pytest.raises(ValueError, match="unsafe Unicode|bidirectional"):
        ProcessDesignIR.from_dict(value)


def test_requirement_rejects_excessive_feed_count_before_materialization() -> None:
    value = load(REQUIREMENT)
    template = deepcopy(value["feeds"][0])
    value["feeds"] = []
    for index in range(129):
        item = deepcopy(template)
        item["id"] = f"FEED_{index:03d}"
        value["feeds"].append(item)
    with pytest.raises(ValueError, match="limit is 128"):
        ProcessRequirementDocument.from_dict(value)


def test_design_rejects_excessive_stream_component_count_before_validation() -> None:
    value = load(DESIGN)
    value["streams"][0]["components"] = [f"C{index:03d}" for index in range(257)]
    with pytest.raises(ValueError, match="limit is 256"):
        ProcessDesignIR.from_dict(value)


def test_design_rejects_nonfinite_parameter_values() -> None:
    value = load(DESIGN)
    value["equipment"][1]["parameters"][0]["value"] = float("nan")
    with pytest.raises(ValueError, match="finite scalar"):
        ProcessDesignIR.from_dict(value)
