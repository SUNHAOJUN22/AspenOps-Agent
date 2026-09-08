from __future__ import annotations

import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any, Literal

from .process_ir_v2 import (
    EquipmentDefinition,
    ParameterDefinition,
    PortDefinition,
    ProcessDesignIR,
    ReactionDefinition,
)
from .units import UnitError, convert, dimension

IssueSeverity = Literal["HARD_ERROR", "ENGINEERING_BLOCKER", "WARNING", "INFORMATION"]

_BLOCKING = {"HARD_ERROR", "ENGINEERING_BLOCKER"}
_MATERIAL_KINDS = {"material", "tear", "feed", "product", "waste"}
_REACTOR_KINDS = {
    "reactor_cstr",
    "reactor_pfr",
    "reactor_equilibrium",
    "reactor_gibbs",
    "reactor_yield",
}
_COLUMN_KINDS = {"radfrac", "distillation_column", "dstwu"}
_PARAMETER_DIMENSIONS: dict[str, frozenset[str]] = {
    "SPLIT_FRACTION": frozenset({"dimensionless"}),
    "FLOW_SPEC": frozenset({"mass_flow", "molar_flow", "volumetric_flow"}),
    "OUTLET_TEMPERATURE": frozenset({"temperature"}),
    "TEMPERATURE": frozenset({"temperature"}),
    "DUTY": frozenset({"power"}),
    "CONDENSER_DUTY": frozenset({"power"}),
    "REBOILER_DUTY": frozenset({"power"}),
    "VAPOR_FRACTION": frozenset({"dimensionless"}),
    "PRESSURE": frozenset({"pressure"}),
    "OUTLET_PRESSURE": frozenset({"pressure"}),
    "PRESSURE_INCREASE": frozenset({"pressure"}),
    "PRESSURE_DROP": frozenset({"pressure"}),
    "PRESSURE_RATIO": frozenset({"dimensionless"}),
    "EFFICIENCY": frozenset({"dimensionless"}),
    "TOTAL_STAGES": frozenset({"dimensionless"}),
    "FEED_STAGE": frozenset({"dimensionless"}),
    "REFLUX_RATIO": frozenset({"dimensionless"}),
    "DISTILLATE_RATE": frozenset({"mass_flow", "molar_flow", "volumetric_flow"}),
    "BOTTOMS_RATE": frozenset({"mass_flow", "molar_flow", "volumetric_flow"}),
    "DISTILLATE_RECOVERY": frozenset({"dimensionless"}),
    "BOTTOMS_RECOVERY": frozenset({"dimensionless"}),
    "DISTILLATE_PURITY": frozenset({"dimensionless"}),
    "BOTTOMS_PURITY": frozenset({"dimensionless"}),
    "VOLUME": frozenset({"volume"}),
    "RESIDENCE_TIME": frozenset({"time"}),
    "CONVERSION": frozenset({"dimensionless"}),
    "TOTAL_FLOW": frozenset({"mass_flow", "molar_flow", "volumetric_flow"}),
}
_INTEGER_PARAMETERS = frozenset({"TOTAL_STAGES", "FEED_STAGE"})
_FRACTION_PARAMETERS = frozenset(
    {
        "SPLIT_FRACTION",
        "VAPOR_FRACTION",
        "EFFICIENCY",
        "DISTILLATE_RECOVERY",
        "BOTTOMS_RECOVERY",
        "DISTILLATE_PURITY",
        "BOTTOMS_PURITY",
        "CONVERSION",
    }
)
_ABSOLUTE_TEMPERATURE_PARAMETERS = frozenset({"OUTLET_TEMPERATURE", "TEMPERATURE"})
_POSITIVE_PARAMETERS = frozenset(
    {
        "FLOW_SPEC",
        "PRESSURE",
        "OUTLET_PRESSURE",
        "PRESSURE_RATIO",
        "TOTAL_STAGES",
        "FEED_STAGE",
        "REFLUX_RATIO",
        "DISTILLATE_RATE",
        "BOTTOMS_RATE",
        "VOLUME",
        "RESIDENCE_TIME",
        "TOTAL_FLOW",
    }
)


@dataclass(frozen=True, slots=True, order=True)
class RuleIssue:
    severity: IssueSeverity
    code: str
    path: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {
            "severity": self.severity,
            "code": self.code,
            "path": self.path,
            "message": self.message,
        }


@dataclass(frozen=True, slots=True)
class EngineeringValidationReport:
    valid: bool
    design_hash: str
    counts: dict[str, int]
    issues: tuple[RuleIssue, ...]

    @property
    def blockers(self) -> tuple[RuleIssue, ...]:
        return tuple(issue for issue in self.issues if issue.severity in _BLOCKING)

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "design_hash": self.design_hash,
            "counts": dict(self.counts),
            "issues": [item.to_dict() for item in self.issues],
            "blockers": [item.to_dict() for item in self.blockers],
        }


def _issue(
    severity: IssueSeverity,
    code: str,
    path: str,
    message: str,
) -> RuleIssue:
    return RuleIssue(severity, code, path, message)


def _approved_parameters(equipment: EquipmentDefinition) -> dict[str, ParameterDefinition]:
    values = (*equipment.parameters, *equipment.design_specs)
    return {item.name: item for item in values if item.approved}


def _port_groups(equipment: EquipmentDefinition) -> dict[tuple[str, str], list[PortDefinition]]:
    groups: dict[tuple[str, str], list[PortDefinition]] = defaultdict(list)
    for port in equipment.ports:
        groups[(port.direction, port.domain)].append(port)
    return groups


def _finite_parameter(
    parameters: dict[str, ParameterDefinition],
    name: str,
) -> float | None:
    parameter = parameters.get(name)
    if parameter is None or isinstance(parameter.value, bool | str) or parameter.value is None:
        return None
    number = float(parameter.value)
    return number if math.isfinite(number) else None


def _validate_parameter_contracts(
    parameters: tuple[ParameterDefinition, ...],
    path: str,
) -> list[RuleIssue]:
    issues: list[RuleIssue] = []
    for parameter in parameters:
        expected_dimensions = _PARAMETER_DIMENSIONS.get(parameter.name)
        if expected_dimensions is None or not parameter.approved:
            continue
        parameter_path = f"{path}.parameters.{parameter.name}"
        if isinstance(parameter.value, bool | str) or parameter.value is None:
            issues.append(
                _issue(
                    "ENGINEERING_BLOCKER",
                    "parameter.numeric_type",
                    parameter_path,
                    f"Parameter {parameter.name} requires a finite numeric value",
                )
            )
            continue
        number = float(parameter.value)
        if not math.isfinite(number):
            issues.append(
                _issue(
                    "ENGINEERING_BLOCKER",
                    "parameter.non_finite",
                    parameter_path,
                    f"Parameter {parameter.name} requires a finite numeric value",
                )
            )
            continue
        if parameter.unit is not None:
            try:
                observed_dimension = dimension(parameter.unit)
            except UnitError:
                observed_dimension = None
            if observed_dimension not in expected_dimensions:
                issues.append(
                    _issue(
                        "ENGINEERING_BLOCKER",
                        "parameter.unit_dimension",
                        parameter_path,
                        f"Parameter {parameter.name} unit {parameter.unit!r} is incompatible with "
                        f"{sorted(expected_dimensions)}",
                    )
                )
        if parameter.name in _ABSOLUTE_TEMPERATURE_PARAMETERS and parameter.unit is not None:
            try:
                absolute_temperature = convert(number, parameter.unit, "K")
            except UnitError:
                absolute_temperature = None
            if absolute_temperature is not None and absolute_temperature <= 0.0:
                issues.append(
                    _issue(
                        "ENGINEERING_BLOCKER",
                        "parameter.absolute_temperature",
                        parameter_path,
                        f"Parameter {parameter.name} must be above absolute zero",
                    )
                )
        if parameter.name in _INTEGER_PARAMETERS and not number.is_integer():
            issues.append(
                _issue(
                    "ENGINEERING_BLOCKER",
                    "parameter.integer_required",
                    parameter_path,
                    f"Parameter {parameter.name} must be integral",
                )
            )
        if parameter.name in _FRACTION_PARAMETERS and not 0.0 <= number <= 1.0:
            issues.append(
                _issue(
                    "ENGINEERING_BLOCKER",
                    "parameter.fraction_range",
                    parameter_path,
                    f"Parameter {parameter.name} must lie between zero and one",
                )
            )
        if parameter.name in _POSITIVE_PARAMETERS and number <= 0.0:
            issues.append(
                _issue(
                    "ENGINEERING_BLOCKER",
                    "parameter.positive_required",
                    parameter_path,
                    f"Parameter {parameter.name} must be positive",
                )
            )
    return issues


def _require_any_parameter(
    equipment: EquipmentDefinition,
    path: str,
    names: tuple[str, ...],
    issues: list[RuleIssue],
) -> None:
    approved = _approved_parameters(equipment)
    if not any(name in approved for name in names):
        issues.append(
            _issue(
                "ENGINEERING_BLOCKER",
                "equipment.specification_missing",
                path,
                f"Equipment {equipment.id} requires one approved specification from {names}",
            )
        )


def _validate_equipment_contract(
    equipment: EquipmentDefinition,
    path: str,
    reaction_count: int,
) -> list[RuleIssue]:
    issues: list[RuleIssue] = []
    groups = _port_groups(equipment)
    material_in = groups.get(("in", "material"), [])
    material_out = groups.get(("out", "material"), [])
    energy_in = groups.get(("in", "energy"), [])
    energy_out = groups.get(("out", "energy"), [])
    kind = equipment.kind
    approved = _approved_parameters(equipment)

    if kind == "feed":
        if material_in or len(material_out) != 1:
            issues.append(
                _issue(
                    "HARD_ERROR",
                    "equipment.feed_ports",
                    path,
                    "Feed requires exactly one material output and no material input",
                )
            )
    elif kind == "product":
        if len(material_in) != 1 or material_out:
            issues.append(
                _issue(
                    "HARD_ERROR",
                    "equipment.product_ports",
                    path,
                    "Product requires exactly one material input and no material output",
                )
            )
    elif kind == "mixer":
        if not material_in or len(material_out) != 1:
            issues.append(
                _issue(
                    "HARD_ERROR",
                    "equipment.mixer_ports",
                    path,
                    "Mixer requires at least one material input and exactly one material output",
                )
            )
    elif kind == "splitter":
        if len(material_in) != 1 or len(material_out) < 2:
            issues.append(
                _issue(
                    "HARD_ERROR",
                    "equipment.splitter_ports",
                    path,
                    "Splitter requires one material input and at least two material outputs",
                )
            )
        _require_any_parameter(equipment, path, ("SPLIT_FRACTION", "FLOW_SPEC"), issues)
    elif kind in {"heater", "cooler"}:
        if len(material_in) != 1 or len(material_out) != 1:
            issues.append(
                _issue(
                    "HARD_ERROR",
                    "equipment.thermal_ports",
                    path,
                    f"{kind} requires one material input and one material output",
                )
            )
        if len(energy_in) + len(energy_out) > 1:
            issues.append(
                _issue(
                    "HARD_ERROR",
                    "equipment.thermal_energy_ports",
                    path,
                    f"{kind} cannot declare multiple energy connections",
                )
            )
        _require_any_parameter(
            equipment,
            path,
            ("OUTLET_TEMPERATURE", "DUTY", "VAPOR_FRACTION"),
            issues,
        )
    elif kind in {"flash", "flash2", "separator"}:
        if len(material_in) != 1 or len(material_out) < 2:
            issues.append(
                _issue(
                    "HARD_ERROR",
                    "equipment.separator_ports",
                    path,
                    f"{kind} requires one material input and at least two material outputs",
                )
            )
        _require_any_parameter(
            equipment,
            path,
            ("TEMPERATURE", "PRESSURE", "DUTY", "VAPOR_FRACTION"),
            issues,
        )
    elif kind in {"pump", "compressor"}:
        if len(material_in) != 1 or len(material_out) != 1:
            issues.append(
                _issue(
                    "HARD_ERROR",
                    "equipment.pressure_ports",
                    path,
                    f"{kind} requires one material input and one material output",
                )
            )
        _require_any_parameter(
            equipment,
            path,
            ("OUTLET_PRESSURE", "PRESSURE_RATIO", "PRESSURE_INCREASE"),
            issues,
        )
        efficiency = _finite_parameter(approved, "EFFICIENCY")
        if efficiency is not None and not 0.0 < efficiency <= 1.0:
            issues.append(
                _issue(
                    "ENGINEERING_BLOCKER",
                    "equipment.efficiency_range",
                    f"{path}.parameters.EFFICIENCY",
                    f"{kind} efficiency must be greater than zero and no greater than one",
                )
            )
    elif kind in _COLUMN_KINDS:
        if not material_in or len(material_out) < 2:
            issues.append(
                _issue(
                    "HARD_ERROR",
                    "equipment.column_ports",
                    path,
                    "Column requires a material feed and at least two material products",
                )
            )
        stages = _finite_parameter(approved, "TOTAL_STAGES")
        if stages is None or stages < 2 or not stages.is_integer():
            issues.append(
                _issue(
                    "ENGINEERING_BLOCKER",
                    "equipment.column_stages",
                    f"{path}.parameters.TOTAL_STAGES",
                    "Column requires an approved integral stage count of at least two",
                )
            )
        feed_stage = _finite_parameter(approved, "FEED_STAGE")
        if feed_stage is not None and stages is not None and not 1 <= feed_stage <= stages:
            issues.append(
                _issue(
                    "ENGINEERING_BLOCKER",
                    "equipment.column_feed_stage",
                    f"{path}.parameters.FEED_STAGE",
                    "Column feed stage must lie within the approved stage range",
                )
            )
        independent_specs = [
            item
            for item in equipment.design_specs
            if item.approved and item.name not in {"TOTAL_STAGES", "FEED_STAGE"}
        ]
        if len(independent_specs) < 2:
            issues.append(
                _issue(
                    "ENGINEERING_BLOCKER",
                    "equipment.column_degrees_of_freedom",
                    path,
                    "Column requires at least two approved independent design specifications",
                )
            )
    elif kind in _REACTOR_KINDS:
        if len(material_in) != 1 or len(material_out) != 1:
            issues.append(
                _issue(
                    "HARD_ERROR",
                    "equipment.reactor_ports",
                    path,
                    "Reactor requires one material input and one material output",
                )
            )
        if reaction_count == 0:
            issues.append(
                _issue(
                    "ENGINEERING_BLOCKER",
                    "equipment.reaction_set_missing",
                    path,
                    "Reactor cannot be compiled without an approved reaction definition",
                )
            )
        _require_any_parameter(
            equipment,
            path,
            ("VOLUME", "RESIDENCE_TIME", "CONVERSION"),
            issues,
        )
    elif kind == "valve":
        if len(material_in) != 1 or len(material_out) != 1:
            issues.append(
                _issue(
                    "HARD_ERROR",
                    "equipment.valve_ports",
                    path,
                    "Valve requires one material input and one material output",
                )
            )
        _require_any_parameter(
            equipment,
            path,
            ("OUTLET_PRESSURE", "PRESSURE_DROP"),
            issues,
        )
    else:
        issues.append(
            _issue(
                "ENGINEERING_BLOCKER",
                "equipment.contract_unavailable",
                path,
                f"No deterministic equipment contract is registered for kind {kind}",
            )
        )

    issues.extend(
        _validate_parameter_contracts(
            (*equipment.parameters, *equipment.design_specs),
            path,
        )
    )
    if any(not item.approved for item in (*equipment.parameters, *equipment.design_specs)):
        issues.append(
            _issue(
                "ENGINEERING_BLOCKER",
                "equipment.parameter_unapproved",
                path,
                f"Equipment {equipment.id} contains an unknown or pending parameter",
            )
        )
    return issues


def _cycle_paths(design: ProcessDesignIR) -> list[tuple[str, ...]]:
    known = {item.id for item in design.equipment}
    adjacency: dict[str, set[str]] = defaultdict(set)
    for stream in design.streams:
        if stream.domain == "material":
            adjacency[stream.source.equipment_id].add(stream.target.equipment_id)
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
                rotations = [
                    tuple(nodes[index:] + nodes[:index] + [nodes[index]])
                    for index in range(len(nodes))
                ]
                cycles.add(min(rotations))
        active.pop()
        active_set.remove(node)

    for equipment_id in sorted(known):
        if equipment_id not in visited:
            visit(equipment_id)
    return sorted(cycles)


def _validate_reaction(
    reaction: ReactionDefinition,
    component_ids: set[str],
    path: str,
) -> list[RuleIssue]:
    issues: list[RuleIssue] = []
    unknown = sorted(set(reaction.stoichiometry) - component_ids)
    if unknown:
        issues.append(
            _issue(
                "HARD_ERROR",
                "reaction.unknown_component",
                path,
                "Reaction references unknown components: " + ", ".join(unknown),
            )
        )
    coefficients = tuple(reaction.stoichiometry.values())
    if coefficients and not (
        any(item < 0 for item in coefficients) and any(item > 0 for item in coefficients)
    ):
        issues.append(
            _issue(
                "ENGINEERING_BLOCKER",
                "reaction.stoichiometry_direction",
                path,
                "Reaction stoichiometry requires at least one reactant and one product",
            )
        )
    if reaction.status not in {"USER_PROVIDED", "APPROVED_DEFAULT"}:
        issues.append(
            _issue(
                "ENGINEERING_BLOCKER",
                "reaction.unapproved",
                path,
                f"Reaction {reaction.id} requires engineering approval",
            )
        )
    issues.extend(_validate_parameter_contracts(reaction.parameters, path))
    if any(not item.approved for item in reaction.parameters):
        issues.append(
            _issue(
                "ENGINEERING_BLOCKER",
                "reaction.parameter_unapproved",
                path,
                f"Reaction {reaction.id} contains an unknown or pending parameter",
            )
        )
    return issues


def validate_process_design(design: ProcessDesignIR) -> EngineeringValidationReport:
    issues: list[RuleIssue] = []
    component_ids = {item.id for item in design.components}
    equipment_map = {item.id: item for item in design.equipment}
    stream_map = {item.id: item for item in design.streams}
    port_map: dict[tuple[str, str], PortDefinition] = {}
    connections: Counter[tuple[str, str]] = Counter()

    if not design.components:
        issues.append(
            _issue(
                "HARD_ERROR", "components.empty", "components", "At least one component is required"
            )
        )
    if not design.equipment:
        issues.append(
            _issue(
                "HARD_ERROR",
                "equipment.empty",
                "equipment",
                "At least one equipment item is required",
            )
        )
    if not design.property_method.approved:
        issues.append(
            _issue(
                "ENGINEERING_BLOCKER",
                "property_method.unapproved",
                "property_method",
                "Property method requires explicit engineering approval",
            )
        )
    if design.property_method.vendor not in {design.target_simulator, "any"}:
        issues.append(
            _issue(
                "HARD_ERROR",
                "property_method.vendor_mismatch",
                "property_method.vendor",
                "Property method vendor does not match the target simulator",
            )
        )
    if (
        design.property_method.supported_versions
        and design.target_version not in design.property_method.supported_versions
        and "any" not in design.property_method.supported_versions
    ):
        issues.append(
            _issue(
                "ENGINEERING_BLOCKER",
                "property_method.version_unqualified",
                "property_method.supported_versions",
                "Property method is not approved for the requested simulator version",
            )
        )

    for index, component in enumerate(design.components):
        path = f"components[{index}]"
        if component.status not in {"USER_PROVIDED", "APPROVED_DEFAULT"}:
            issues.append(
                _issue(
                    "ENGINEERING_BLOCKER",
                    "component.unapproved",
                    path,
                    f"Component {component.id} requires engineering approval",
                )
            )
        if not component.pseudo_component and design.target_simulator not in component.vendor_ids:
            issues.append(
                _issue(
                    "ENGINEERING_BLOCKER",
                    "component.vendor_mapping_missing",
                    path,
                    f"Component {component.id} has no target-simulator identifier",
                )
            )

    for equipment_index, equipment in enumerate(design.equipment):
        path = f"equipment[{equipment_index}]"
        for port in equipment.ports:
            port_map[(equipment.id, port.id)] = port
        issues.extend(_validate_equipment_contract(equipment, path, len(design.reactions)))

    for stream_index, stream in enumerate(design.streams):
        path = f"streams[{stream_index}]"
        source_equipment = equipment_map.get(stream.source.equipment_id)
        target_equipment = equipment_map.get(stream.target.equipment_id)
        if source_equipment is None:
            issues.append(
                _issue(
                    "HARD_ERROR",
                    "stream.source_equipment_missing",
                    f"{path}.source",
                    f"Stream {stream.id} references unknown source equipment",
                )
            )
        if target_equipment is None:
            issues.append(
                _issue(
                    "HARD_ERROR",
                    "stream.target_equipment_missing",
                    f"{path}.target",
                    f"Stream {stream.id} references unknown target equipment",
                )
            )
        source_port = port_map.get((stream.source.equipment_id, stream.source.port_id))
        target_port = port_map.get((stream.target.equipment_id, stream.target.port_id))
        if source_port is None:
            issues.append(
                _issue(
                    "HARD_ERROR",
                    "stream.source_port_missing",
                    f"{path}.source",
                    f"Stream {stream.id} references an unknown source port",
                )
            )
        elif source_port.direction != "out":
            issues.append(
                _issue(
                    "HARD_ERROR",
                    "stream.source_direction",
                    f"{path}.source",
                    "Stream source must reference an output port",
                )
            )
        elif source_port.domain != stream.domain:
            issues.append(
                _issue(
                    "HARD_ERROR",
                    "stream.source_domain",
                    f"{path}.source",
                    "Stream domain does not match its source port",
                )
            )
        if target_port is None:
            issues.append(
                _issue(
                    "HARD_ERROR",
                    "stream.target_port_missing",
                    f"{path}.target",
                    f"Stream {stream.id} references an unknown target port",
                )
            )
        elif target_port.direction != "in":
            issues.append(
                _issue(
                    "HARD_ERROR",
                    "stream.target_direction",
                    f"{path}.target",
                    "Stream target must reference an input port",
                )
            )
        elif target_port.domain != stream.domain:
            issues.append(
                _issue(
                    "HARD_ERROR",
                    "stream.target_domain",
                    f"{path}.target",
                    "Stream domain does not match its target port",
                )
            )
        if stream.source.equipment_id == stream.target.equipment_id:
            issues.append(
                _issue(
                    "HARD_ERROR",
                    "stream.self_connection",
                    path,
                    f"Stream {stream.id} connects equipment to itself",
                )
            )
        for endpoint in (stream.source, stream.target):
            connections[(endpoint.equipment_id, endpoint.port_id)] += 1
        if stream.domain == "material":
            unknown_components = sorted(set(stream.components) - component_ids)
            if unknown_components:
                issues.append(
                    _issue(
                        "HARD_ERROR",
                        "stream.unknown_component",
                        f"{path}.components",
                        "Stream references unknown components: " + ", ".join(unknown_components),
                    )
                )
            if not stream.components:
                issues.append(
                    _issue(
                        "ENGINEERING_BLOCKER",
                        "stream.components_empty",
                        f"{path}.components",
                        f"Material stream {stream.id} must declare its component scope",
                    )
                )
        elif stream.components:
            issues.append(
                _issue(
                    "HARD_ERROR",
                    "stream.nonmaterial_components",
                    f"{path}.components",
                    "Energy and information streams cannot carry material components",
                )
            )
        issues.extend(_validate_parameter_contracts(stream.parameters, path))
        if any(not item.approved for item in stream.parameters):
            issues.append(
                _issue(
                    "ENGINEERING_BLOCKER",
                    "stream.parameter_unapproved",
                    path,
                    f"Stream {stream.id} contains an unknown or pending parameter",
                )
            )

    for equipment_index, equipment in enumerate(design.equipment):
        for port_index, port in enumerate(equipment.ports):
            count = connections[(equipment.id, port.id)]
            path = f"equipment[{equipment_index}].ports[{port_index}]"
            if port.required and count == 0:
                issues.append(
                    _issue(
                        "HARD_ERROR",
                        "port.required_unconnected",
                        path,
                        f"Required port is unconnected: {equipment.id}.{port.id}",
                    )
                )
            if count > 1 and not port.multiple:
                issues.append(
                    _issue(
                        "HARD_ERROR",
                        "port.multiple_connections",
                        path,
                        f"Port {equipment.id}.{port.id} does not allow multiple streams",
                    )
                )

    for reaction_index, reaction in enumerate(design.reactions):
        issues.extend(
            _validate_reaction(
                reaction,
                component_ids,
                f"reactions[{reaction_index}]",
            )
        )

    recycle_streams: set[str] = set()
    for recycle_index, recycle in enumerate(design.recycles):
        path = f"recycles[{recycle_index}]"
        recycle_stream = stream_map.get(recycle.stream_id)
        tear = stream_map.get(recycle.tear_stream_id)
        if recycle_stream is None:
            issues.append(
                _issue(
                    "HARD_ERROR",
                    "recycle.stream_missing",
                    path,
                    f"Recycle {recycle.id} references an unknown recycle stream",
                )
            )
        if tear is None or tear.kind != "tear":
            issues.append(
                _issue(
                    "HARD_ERROR",
                    "recycle.tear_missing",
                    path,
                    f"Recycle {recycle.id} requires a declared tear stream",
                )
            )
        if recycle.status not in {"USER_PROVIDED", "APPROVED_DEFAULT"}:
            issues.append(
                _issue(
                    "ENGINEERING_BLOCKER",
                    "recycle.unapproved",
                    path,
                    f"Recycle {recycle.id} requires engineering approval",
                )
            )
        recycle_streams.update({recycle.stream_id, recycle.tear_stream_id})

    cycles = _cycle_paths(design)
    owned_tear_edges = {
        (tear.source.equipment_id, tear.target.equipment_id)
        for recycle in design.recycles
        if (tear := stream_map.get(recycle.tear_stream_id)) is not None and tear.kind == "tear"
    }
    for cycle in cycles:
        cycle_edges = set(zip(cycle, cycle[1:], strict=False))
        if not cycle_edges.intersection(owned_tear_edges):
            issues.append(
                _issue(
                    "ENGINEERING_BLOCKER",
                    "topology.recycle_contract_missing",
                    "streams",
                    "Directed material cycle has no owned tear edge: " + " -> ".join(cycle),
                )
            )
    if design.recycles and not cycles:
        issues.append(
            _issue(
                "WARNING",
                "recycle.no_graph_cycle",
                "recycles",
                "Recycle contracts are declared but no directed material cycle was detected",
            )
        )
    undeclared_tears = sorted(
        stream.id
        for stream in design.streams
        if stream.kind == "tear" and stream.id not in recycle_streams
    )
    if undeclared_tears:
        issues.append(
            _issue(
                "ENGINEERING_BLOCKER",
                "recycle.tear_unowned",
                "streams",
                "Tear streams are not owned by a recycle contract: " + ", ".join(undeclared_tears),
            )
        )

    ordered = tuple(sorted(issues))
    counts = {
        "components": len(design.components),
        "equipment": len(design.equipment),
        "streams": len(design.streams),
        "reactions": len(design.reactions),
        "recycles": len(design.recycles),
        "blockers": sum(issue.severity in _BLOCKING for issue in ordered),
        "warnings": sum(issue.severity == "WARNING" for issue in ordered),
    }
    return EngineeringValidationReport(
        valid=not any(issue.severity in _BLOCKING for issue in ordered),
        design_hash=design.digest(),
        counts=counts,
        issues=ordered,
    )
