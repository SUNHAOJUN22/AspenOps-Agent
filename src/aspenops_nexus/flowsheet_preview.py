from __future__ import annotations

import hashlib
import html
import json
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any

from .process_ir_v2 import ProcessDesignIR


@dataclass(frozen=True, slots=True)
class EquipmentPosition:
    equipment_id: str
    x: int
    y: int
    layer: int

    def to_dict(self) -> dict[str, int | str]:
        return {
            "equipment_id": self.equipment_id,
            "x": self.x,
            "y": self.y,
            "layer": self.layer,
        }


@dataclass(frozen=True, slots=True)
class FlowsheetPreview:
    design_hash: str
    layout_hash: str
    positions: tuple[EquipmentPosition, ...]
    graph: dict[str, Any]
    svg: str
    boundary: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "design_hash": self.design_hash,
            "layout_hash": self.layout_hash,
            "positions": [item.to_dict() for item in self.positions],
            "graph": self.graph,
            "svg": self.svg,
            "boundary": self.boundary,
        }


def _layout_layers(design: ProcessDesignIR) -> dict[str, int]:
    equipment_ids = {item.id for item in design.equipment}
    adjacency: dict[str, set[str]] = defaultdict(set)
    indegree = {equipment_id: 0 for equipment_id in equipment_ids}
    # Tear streams are excluded from the forward layout graph so recycle loops return visually.
    for stream in design.streams:
        if stream.kind == "tear":
            continue
        source = stream.source.equipment_id
        target = stream.target.equipment_id
        if source not in equipment_ids or target not in equipment_ids or target in adjacency[source]:
            continue
        adjacency[source].add(target)
        indegree[target] += 1

    queue = deque(sorted(item for item, count in indegree.items() if count == 0))
    layers = {equipment_id: 0 for equipment_id in equipment_ids}
    visited: set[str] = set()
    while queue:
        source = queue.popleft()
        visited.add(source)
        for target in sorted(adjacency.get(source, set())):
            layers[target] = max(layers[target], layers[source] + 1)
            indegree[target] -= 1
            if indegree[target] == 0:
                queue.append(target)
    if len(visited) != len(equipment_ids):
        highest = max(layers.values(), default=0)
        for offset, equipment_id in enumerate(sorted(equipment_ids - visited), start=1):
            layers[equipment_id] = highest + offset
    return layers


def _positions(design: ProcessDesignIR) -> tuple[EquipmentPosition, ...]:
    layers = _layout_layers(design)
    by_layer: dict[int, list[str]] = defaultdict(list)
    for equipment_id, layer in layers.items():
        by_layer[layer].append(equipment_id)
    output: list[EquipmentPosition] = []
    for layer in sorted(by_layer):
        for ordinal, equipment_id in enumerate(sorted(by_layer[layer])):
            output.append(
                EquipmentPosition(
                    equipment_id=equipment_id,
                    x=80 + 240 * layer,
                    y=80 + 130 * ordinal,
                    layer=layer,
                )
            )
    return tuple(sorted(output, key=lambda item: item.equipment_id))


def _graph(design: ProcessDesignIR, positions: tuple[EquipmentPosition, ...]) -> dict[str, Any]:
    position_map = {item.equipment_id: item for item in positions}
    equipment_map = {item.id: item for item in design.equipment}
    return {
        "schema": "aspenops.flowsheet-preview/v1",
        "design_hash": design.digest(),
        "nodes": [
            {
                "id": equipment_id,
                "display_name": equipment_map[equipment_id].display_name,
                "kind": equipment_map[equipment_id].kind,
                "x": position_map[equipment_id].x,
                "y": position_map[equipment_id].y,
            }
            for equipment_id in sorted(equipment_map)
        ],
        "edges": [
            {
                "id": stream.id,
                "display_name": stream.display_name,
                "kind": stream.kind,
                "source": stream.source.equipment_id,
                "source_port": stream.source.port_id,
                "target": stream.target.equipment_id,
                "target_port": stream.target.port_id,
            }
            for stream in sorted(design.streams, key=lambda item: item.id)
        ],
    }


def _layout_hash(graph: dict[str, Any]) -> str:
    payload = json.dumps(
        graph,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _svg(design: ProcessDesignIR, positions: tuple[EquipmentPosition, ...]) -> str:
    position_map = {item.equipment_id: item for item in positions}
    equipment_map = {item.id: item for item in design.equipment}
    width = max((item.x for item in positions), default=80) + 220
    height = max((item.y for item in positions), default=80) + 150
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" ',
        f'viewBox="0 0 {width} {height}" role="img" ',
        f'aria-label="{html.escape(design.name, quote=True)}">',
        "<defs>",
        '<marker id="arrow" markerWidth="10" markerHeight="7" refX="9" refY="3.5" ',
        'orient="auto"><path d="M0,0 L10,3.5 L0,7 Z" fill="#222"/></marker>',
        "</defs>",
    ]
    for stream in sorted(design.streams, key=lambda item: item.id):
        source = position_map.get(stream.source.equipment_id)
        target = position_map.get(stream.target.equipment_id)
        if source is None or target is None:
            continue
        start_x = source.x + 150
        start_y = source.y + 35
        end_x = target.x
        end_y = target.y + 35
        if stream.kind == "tear" or end_x <= start_x:
            bend_y = max(start_y, end_y) + 70
            path = (
                f"M {start_x} {start_y} L {start_x + 30} {start_y} "
                f"L {start_x + 30} {bend_y} L {end_x - 30} {bend_y} "
                f"L {end_x - 30} {end_y} L {end_x} {end_y}"
            )
        else:
            midpoint = (start_x + end_x) // 2
            path = (
                f"M {start_x} {start_y} L {midpoint} {start_y} "
                f"L {midpoint} {end_y} L {end_x} {end_y}"
            )
        label_x = (start_x + end_x) // 2
        label_y = min(start_y, end_y) - 8
        lines.append(
            f'<path d="{path}" fill="none" stroke="#222" stroke-width="1.5" '
            'marker-end="url(#arrow)"/>'
        )
        lines.append(
            f'<text x="{label_x}" y="{label_y}" text-anchor="middle" '
            f'font-family="Arial, sans-serif" font-size="11">'
            f"{html.escape(stream.display_name)}</text>"
        )
    for equipment_id in sorted(equipment_map):
        equipment = equipment_map[equipment_id]
        position = position_map[equipment_id]
        lines.append(
            f'<rect x="{position.x}" y="{position.y}" width="150" height="70" '
            'rx="8" fill="#f4f4f4" stroke="#111" stroke-width="1.5"/>'
        )
        lines.append(
            f'<text x="{position.x + 75}" y="{position.y + 28}" text-anchor="middle" '
            f'font-family="Arial, sans-serif" font-size="12" font-weight="bold">'
            f"{html.escape(equipment.display_name)}</text>"
        )
        lines.append(
            f'<text x="{position.x + 75}" y="{position.y + 48}" text-anchor="middle" '
            f'font-family="Arial, sans-serif" font-size="10">'
            f"{html.escape(equipment.kind)}</text>"
        )
        lines.append(
            f'<text x="{position.x + 75}" y="{position.y + 63}" text-anchor="middle" '
            f'font-family="Arial, sans-serif" font-size="9">'
            f"{html.escape(equipment.id)}</text>"
        )
    lines.append("</svg>")
    return "".join(lines)


def render_flowsheet_preview(design: ProcessDesignIR) -> FlowsheetPreview:
    positions = _positions(design)
    graph = _graph(design, positions)
    return FlowsheetPreview(
        design_hash=design.digest(),
        layout_hash=_layout_hash(graph),
        positions=positions,
        graph=graph,
        svg=_svg(design, positions),
        boundary=(
            "This deterministic SVG is a design preview only. It does not prove that Aspen Plus "
            "or HYSYS contains the same native objects, ports, connections or layout."
        ),
    )
