from __future__ import annotations

from collections import defaultdict
from typing import Any

from . import process_ir as _ir
from .process_ir import (
    IssueSeverity,
    ParameterSpec,
    PortSpec,
    ProcessIntent,
    StreamSpec,
    UnitOperationSpec,
    ValidationIssue,
    ValidationReport,
)


def _duplicate_ids(items: tuple[Any, ...], label: str) -> list[ValidationIssue]:
    positions: dict[str, list[int]] = defaultdict(list)
    for index, item in enumerate(items):
        positions[str(item.id)].append(index)
    return [
        ValidationIssue(
            "error",
            f"{label}.duplicate_id",
            f"{label}[{indices[1]}].id",
            f"Duplicate {label[:-1]} id: {identifier}",
        )
        for identifier, indices in sorted(positions.items())
        if len(indices) > 1
    ]


def _duplicate_names(
    parameters: tuple[ParameterSpec, ...],
    *,
    path: str,
) -> list[ValidationIssue]:
    positions: dict[str, list[int]] = defaultdict(list)
    for index, item in enumerate(parameters):
        positions[item.name].append(index)
    return [
        ValidationIssue(
            "error",
            "parameter.duplicate_name",
            f"{path}[{indices[1]}].name",
            f"Duplicate parameter name: {name}",
        )
        for name, indices in sorted(positions.items())
        if len(indices) > 1
    ]


def _cycle_paths(
    units: tuple[UnitOperationSpec, ...],
    streams: tuple[StreamSpec, ...],
) -> list[str]:
    known = {unit.id for unit in units}
    adjacency: dict[str, set[str]] = defaultdict(set)
    for stream in streams:
        if stream.source.unit in known and stream.target.unit in known:
            adjacency[stream.source.unit].add(stream.target.unit)
    visited: set[str] = set()
    active: list[str] = []
    active_set: set[str] = set()
    cycles: set[tuple[str, ...]] = set()

    def visit(node: str) -> None:
        visited.add(node)
        active.append(node)
        active_set.add(node)
        for target in sorted(adjacency.get(node, set())):
            if target not in visited:
                visit(target)
            elif target in active_set:
                start = active.index(target)
                nodes = active[start:]
                rotations = []
                for index in range(len(nodes)):
                    rotated = nodes[index:] + nodes[:index]
                    rotations.append(tuple(rotated + [rotated[0]]))
                cycles.add(min(rotations))
        active.pop()
        active_set.remove(node)

    for unit in sorted(known):
        if unit not in visited:
            visit(unit)
    return [" -> ".join(cycle) for cycle in sorted(cycles)]


def validate_process_intent(
    intent: ProcessIntent,
    *,
    allow_recycles: bool = True,
) -> ValidationReport:
    issues: list[ValidationIssue] = []
    counts = {
        "components": len(intent.components),
        "units": len(intent.units),
        "streams": len(intent.streams),
        "ports": sum(len(unit.ports) for unit in intent.units),
        "parameters": sum(len(unit.parameters) for unit in intent.units)
        + sum(len(stream.parameters) for stream in intent.streams),
    }

    for label, value, limit in (
        ("components", counts["components"], _ir.MAX_COMPONENTS),
        ("units", counts["units"], _ir.MAX_UNITS),
        ("streams", counts["streams"], _ir.MAX_STREAMS),
    ):
        if value > limit:
            issues.append(
                ValidationIssue(
                    "error",
                    f"resource.{label}_limit",
                    label,
                    f"{label} count {value} exceeds limit {limit}",
                )
            )

    if not intent.components:
        issues.append(
            ValidationIssue(
                "error",
                "components.empty",
                "components",
                "A process intent requires at least one component",
            )
        )
    if not intent.units:
        issues.append(
            ValidationIssue(
                "error",
                "units.empty",
                "units",
                "A process intent requires at least one unit operation",
            )
        )
    if intent.property_package is None:
        issues.append(
            ValidationIssue(
                "warning",
                "property_package.missing",
                "property_package",
                "No thermodynamic property package is declared",
            )
        )

    issues.extend(_duplicate_ids(intent.components, "components"))
    issues.extend(_duplicate_ids(intent.units, "units"))
    issues.extend(_duplicate_ids(intent.streams, "streams"))

    component_ids = {item.id for item in intent.components}
    unit_map = {item.id: item for item in intent.units}
    port_map: dict[tuple[str, str], PortSpec] = {}
    for unit_index, unit in enumerate(intent.units):
        if unit.kind not in _ir._CANONICAL_UNIT_KINDS:
            issues.append(
                ValidationIssue(
                    "warning",
                    "unit.noncanonical_kind",
                    f"units[{unit_index}].kind",
                    f"Unit kind is not in the canonical vocabulary: {unit.kind}",
                )
            )
        if len(unit.ports) > _ir.MAX_PORTS_PER_UNIT:
            issues.append(
                ValidationIssue(
                    "error",
                    "resource.port_limit",
                    f"units[{unit_index}].ports",
                    f"Unit {unit.id} has more than {_ir.MAX_PORTS_PER_UNIT} ports",
                )
            )
        if len(unit.parameters) > _ir.MAX_PARAMETERS_PER_ENTITY:
            issues.append(
                ValidationIssue(
                    "error",
                    "resource.parameter_limit",
                    f"units[{unit_index}].parameters",
                    f"Unit {unit.id} has too many parameters",
                )
            )
        if not unit.ports:
            issues.append(
                ValidationIssue(
                    "error",
                    "unit.ports_empty",
                    f"units[{unit_index}].ports",
                    f"Unit {unit.id} requires at least one declared port",
                )
            )
        port_positions: dict[str, list[int]] = defaultdict(list)
        for port_index, port in enumerate(unit.ports):
            port_positions[port.id].append(port_index)
            port_map[(unit.id, port.id)] = port
        for port_id, positions in sorted(port_positions.items()):
            if len(positions) > 1:
                issues.append(
                    ValidationIssue(
                        "error",
                        "port.duplicate_id",
                        f"units[{unit_index}].ports[{positions[1]}].id",
                        f"Duplicate port id on unit {unit.id}: {port_id}",
                    )
                )
        issues.extend(
            _duplicate_names(unit.parameters, path=f"units[{unit_index}].parameters")
        )

    endpoint_connections: dict[tuple[str, str, str], list[str]] = defaultdict(list)
    connection_pairs: dict[tuple[str, str, str, str], list[int]] = defaultdict(list)
    for stream_index, stream in enumerate(intent.streams):
        if len(stream.parameters) > _ir.MAX_PARAMETERS_PER_ENTITY:
            issues.append(
                ValidationIssue(
                    "error",
                    "resource.parameter_limit",
                    f"streams[{stream_index}].parameters",
                    f"Stream {stream.id} has too many parameters",
                )
            )
        issues.extend(
            _duplicate_names(stream.parameters, path=f"streams[{stream_index}].parameters")
        )
        duplicate_components = sorted(
            component
            for component in set(stream.components)
            if stream.components.count(component) > 1
        )
        for component in duplicate_components:
            issues.append(
                ValidationIssue(
                    "error",
                    "stream.duplicate_component",
                    f"streams[{stream_index}].components",
                    f"Stream {stream.id} repeats component {component}",
                )
            )
        for component_index, component in enumerate(stream.components):
            if component not in component_ids:
                issues.append(
                    ValidationIssue(
                        "error",
                        "stream.unknown_component",
                        f"streams[{stream_index}].components[{component_index}]",
                        f"Stream {stream.id} references unknown component {component}",
                    )
                )

        for side, endpoint, expected_direction in (
            ("source", stream.source, "out"),
            ("target", stream.target, "in"),
        ):
            if endpoint.unit not in unit_map:
                issues.append(
                    ValidationIssue(
                        "error",
                        "stream.unknown_unit",
                        f"streams[{stream_index}].{side}.unit",
                        f"Stream {stream.id} references unknown unit {endpoint.unit}",
                    )
                )
                continue
            port = port_map.get((endpoint.unit, endpoint.port))
            if port is None:
                issues.append(
                    ValidationIssue(
                        "error",
                        "stream.unknown_port",
                        f"streams[{stream_index}].{side}.port",
                        "Stream "
                        f"{stream.id} references unknown port "
                        f"{endpoint.unit}.{endpoint.port}",
                    )
                )
                continue
            if port.direction != expected_direction:
                issues.append(
                    ValidationIssue(
                        "error",
                        "stream.port_direction",
                        f"streams[{stream_index}].{side}.port",
                        f"Stream {stream.id} {side} must reference an {expected_direction} port",
                    )
                )
            endpoint_connections[(endpoint.unit, endpoint.port, side)].append(stream.id)

        if stream.source.unit == stream.target.unit:
            issues.append(
                ValidationIssue(
                    "error",
                    "stream.self_connection",
                    f"streams[{stream_index}]",
                    f"Stream {stream.id} connects unit {stream.source.unit} to itself",
                )
            )
        pair = (
            stream.source.unit,
            stream.source.port,
            stream.target.unit,
            stream.target.port,
        )
        connection_pairs[pair].append(stream_index)

    for pair, positions in sorted(connection_pairs.items()):
        if len(positions) > 1:
            issues.append(
                ValidationIssue(
                    "error",
                    "stream.duplicate_connection",
                    f"streams[{positions[1]}]",
                    "Multiple streams declare the same source and target endpoints: "
                    f"{pair[0]}.{pair[1]} -> {pair[2]}.{pair[3]}",
                )
            )

    for (unit_id, port_id, side), stream_ids in sorted(endpoint_connections.items()):
        if len(stream_ids) > 1:
            issues.append(
                ValidationIssue(
                    "error",
                    "port.multiple_connections",
                    f"units.{unit_id}.ports.{port_id}",
                    f"Port {unit_id}.{port_id} has multiple {side} streams: "
                    + ", ".join(sorted(stream_ids)),
                )
            )

    for unit_index, unit in enumerate(intent.units):
        for port_index, port in enumerate(unit.ports):
            side = "target" if port.direction == "in" else "source"
            if port.required and not endpoint_connections.get((unit.id, port.id, side)):
                issues.append(
                    ValidationIssue(
                        "error",
                        "port.required_unconnected",
                        f"units[{unit_index}].ports[{port_index}]",
                        f"Required port is unconnected: {unit.id}.{port.id}",
                    )
                )

    cycle_severity: IssueSeverity = "warning" if allow_recycles else "error"
    for cycle in _cycle_paths(intent.units, intent.streams):
        issues.append(
            ValidationIssue(
                cycle_severity,
                "topology.recycle_cycle",
                "streams",
                f"Directed recycle cycle detected: {cycle}",
            )
        )

    ordered = tuple(sorted(issues))
    return ValidationReport(
        valid=not any(item.severity == "error" for item in ordered),
        digest=intent.digest(),
        counts=counts,
        issues=ordered,
    )
