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


def test_preview_is_deterministic_and_bound_to_design_hash() -> None:
    design = ProcessDesignIR.from_dict(document())
    first = render_flowsheet_preview(design)
    second = render_flowsheet_preview(design)
    assert first.design_hash == design.digest()
    assert first.layout_hash == second.layout_hash
    assert first.positions == second.positions
    assert first.svg == second.svg
    assert first.graph == second.graph
    assert "does not prove" in first.boundary


def test_preview_is_stable_under_ir_list_reordering() -> None:
    first_document = document()
    second_document = deepcopy(first_document)
    second_document["equipment"].reverse()
    second_document["streams"].reverse()
    first = render_flowsheet_preview(ProcessDesignIR.from_dict(first_document))
    second = render_flowsheet_preview(ProcessDesignIR.from_dict(second_document))
    assert first.design_hash == second.design_hash
    assert first.layout_hash == second.layout_hash
    assert first.graph == second.graph
    assert first.svg == second.svg


def test_preview_escapes_unicode_and_markup_in_display_names() -> None:
    value = document()
    value["equipment"][1]["display_name"] = "加热器 <script>alert(1)</script>"
    value["streams"][0]["display_name"] = "进料 & heater"
    preview = render_flowsheet_preview(ProcessDesignIR.from_dict(value))
    assert "加热器" in preview.svg
    assert "<script>" not in preview.svg
    assert "&lt;script&gt;" in preview.svg
    assert "进料 &amp; heater" in preview.svg


def test_preview_graph_has_all_nodes_edges_and_integer_positions() -> None:
    design = ProcessDesignIR.from_dict(document())
    preview = render_flowsheet_preview(design)
    assert len(preview.graph["nodes"]) == len(design.equipment)
    assert len(preview.graph["edges"]) == len(design.streams)
    assert {item["id"] for item in preview.graph["nodes"]} == {
        item.id for item in design.equipment
    }
    assert all(isinstance(item.x, int) and isinstance(item.y, int) for item in preview.positions)


def test_preview_layout_hash_changes_when_topology_changes() -> None:
    first = render_flowsheet_preview(ProcessDesignIR.from_dict(document()))
    changed = document()
    changed["streams"][1]["target"] = {
        "equipment_id": "VAP_PROD_001",
        "port_id": "IN",
    }
    second = render_flowsheet_preview(ProcessDesignIR.from_dict(changed))
    assert first.design_hash != second.design_hash
    assert first.layout_hash != second.layout_hash
