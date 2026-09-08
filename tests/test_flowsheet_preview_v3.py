from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from aspenops_nexus.flowsheet_preview import render_flowsheet_preview
from aspenops_nexus.process_ir_v2 import ProcessDesignIR

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples/process-design-v2.example.json"


def document() -> dict[str, Any]:
    value = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_preview_is_deterministic_and_contains_safe_unicode() -> None:
    design = ProcessDesignIR.from_dict(document())
    first = render_flowsheet_preview(design)
    second = render_flowsheet_preview(design)
    assert first.layout_hash == second.layout_hash
    assert first.graph == second.graph
    assert first.svg == second.svg
    assert "乙醇水进料" in first.svg
    assert "\ufffd" not in first.svg
    assert "<script" not in first.svg.casefold()
    assert "does not prove" in first.boundary


def test_preview_layout_is_stable_under_ir_list_order() -> None:
    value = document()
    reordered = deepcopy(value)
    reordered["equipment"].reverse()
    reordered["streams"].reverse()
    first = render_flowsheet_preview(ProcessDesignIR.from_dict(value))
    second = render_flowsheet_preview(ProcessDesignIR.from_dict(reordered))
    assert first.design_hash == second.design_hash
    assert first.layout_hash == second.layout_hash
    assert first.graph == second.graph


def test_preview_escapes_display_text() -> None:
    value = document()
    value["equipment"][1]["display_name"] = "Heater <review> & confirm"
    preview = render_flowsheet_preview(ProcessDesignIR.from_dict(value))
    assert "Heater &lt;review&gt; &amp; confirm" in preview.svg
    assert "Heater <review>" not in preview.svg


def test_preview_graph_carries_canonical_ids_and_ports() -> None:
    preview = render_flowsheet_preview(ProcessDesignIR.from_dict(document()))
    nodes = {item["id"]: item for item in preview.graph["nodes"]}
    edges = {item["id"]: item for item in preview.graph["edges"]}
    assert nodes["HTR_001"]["kind"] == "heater"
    assert edges["S002"] == {
        "id": "S002",
        "display_name": "Heater outlet",
        "kind": "material",
        "source": "HTR_001",
        "source_port": "OUT",
        "target": "SEP_001",
        "target_port": "IN",
    }
