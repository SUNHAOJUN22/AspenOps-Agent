from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from .process_ir_v2 import ParameterDefinition, ProcessDesignIR
from .process_requirement import ProcessRequirementDocument, QualifiedScalar
from .units import UnitError, convert, dimension

_FEED_QUANTITY_UNITS = {
    "TOTAL_FLOW": {"mass_flow": "kg/s", "molar_flow": "mol/s", "volumetric_flow": "m3/s"},
    "TEMPERATURE": {"temperature": "K"},
    "PRESSURE": {"pressure": "Pa"},
}


@dataclass(frozen=True, slots=True, order=True)
class DesignContractIssue:
    code: str
    path: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "path": self.path, "message": self.message}


@dataclass(frozen=True, slots=True)
class DesignContractReport:
    valid: bool
    requirement_hash: str
    design_hash: str
    issues: tuple[DesignContractIssue, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "requirement_hash": self.requirement_hash,
            "design_hash": self.design_hash,
            "issues": [item.to_dict() for item in self.issues],
        }


def _issue(code: str, path: str, message: str) -> DesignContractIssue:
    return DesignContractIssue(code, path, message)


def _approved_feed_value(value: QualifiedScalar | ParameterDefinition, unit: str) -> float:
    if not value.approved:
        raise UnitError("quantity is unknown or pending approval")
    if value.unit is None:
        raise UnitError("quantity requires an explicit physical unit")
    if isinstance(value.value, bool) or not isinstance(value.value, int | float):
        raise UnitError("quantity requires a finite numeric value")
    normalized = convert(value.value, value.unit, unit)
    if normalized <= 0.0:
        raise UnitError("flow, absolute temperature and absolute pressure must be positive")
    return normalized


def _feed_contract_issues(
    requirement: ProcessRequirementDocument, design: ProcessDesignIR
) -> list[DesignContractIssue]:
    issues: list[DesignContractIssue] = []
    feed_equipment = {
        item.id: (index, item) for index, item in enumerate(design.equipment) if item.kind == "feed"
    }
    for feed in requirement.feeds:
        if feed.id not in feed_equipment:
            # The boundary identity check already reports missing feed equipment.
            continue
        equipment_index, equipment = feed_equipment[feed.id]
        # Both locations enter separate compiler steps. A requirement-bound feed
        # has one authoritative parameter source: its outgoing material stream.
        for location, parameters in (
            ("parameters", equipment.parameters),
            ("design_specs", equipment.design_specs),
        ):
            if any(item.name in _FEED_QUANTITY_UNITS for item in parameters):
                issues.append(
                    _issue(
                        "feeds.quantity_location_ambiguous",
                        f"design.equipment[{equipment_index}].{location}",
                        f"Feed {feed.id} quantities belong on its boundary stream, not in a "
                        "second equipment parameter source",
                    )
                )
        streams = [
            (index, item)
            for index, item in enumerate(design.streams)
            if item.source.equipment_id == feed.id and item.domain == "material"
        ]
        if len(streams) != 1:
            issues.append(
                _issue(
                    "feeds.boundary_stream_count",
                    "design.streams",
                    f"Feed {feed.id} requires exactly one outgoing material boundary stream; "
                    f"found {len(streams)}. A split requires an explicit downstream splitter.",
                )
            )
            continue
        stream_index, stream = streams[0]
        path = f"design.streams[{stream_index}]"
        if set(stream.components) != set(feed.components):
            issues.append(
                _issue(
                    "feeds.components_mismatch",
                    f"{path}.components",
                    f"Boundary stream {stream.id} component scope differs from feed {feed.id}",
                )
            )
        parameters_by_name = {item.name: item for item in stream.parameters}
        for name, expected in (
            ("TOTAL_FLOW", feed.total_flow),
            ("TEMPERATURE", feed.temperature),
            ("PRESSURE", feed.pressure),
        ):
            quantity_path = f"{path}.parameters.{name}"
            parameter = parameters_by_name.get(name)
            if parameter is None:
                issues.append(
                    _issue(
                        "feeds.quantity_missing",
                        quantity_path,
                        f"Boundary stream {stream.id} omits approved feed {feed.id} {name}",
                    )
                )
                continue
            try:
                expected_dimension = dimension(expected.unit)
                unit = _FEED_QUANTITY_UNITS[name].get(expected_dimension or "")
                if unit is None:
                    raise UnitError(f"Requirement {name} has a missing or incompatible unit")
                expected_value = _approved_feed_value(expected, unit)
                actual_value = _approved_feed_value(parameter, unit)
            except UnitError as exc:
                issues.append(
                    _issue(
                        "feeds.quantity_invalid",
                        quantity_path,
                        f"Cannot bind feed {feed.id} {name}: {exc}",
                    )
                )
                continue
            # Only binary conversion roundoff is allowed, not a process tolerance
            # or the requirement's measurement uncertainty. Never infer molar/mass
            # or volumetric basis conversions from component names or properties.
            if not math.isclose(
                actual_value, expected_value, rel_tol=8 * math.ulp(1.0), abs_tol=0.0
            ):
                issues.append(
                    _issue(
                        "feeds.quantity_mismatch",
                        quantity_path,
                        f"Boundary stream {stream.id} {name} differs from approved feed "
                        f"{feed.id}: {actual_value!r} {unit} != {expected_value!r} {unit}",
                    )
                )
    return issues


def validate_design_against_requirement(
    requirement: ProcessRequirementDocument,
    design: ProcessDesignIR,
) -> DesignContractReport:
    issues: list[DesignContractIssue] = []
    requirement_hash = requirement.digest()
    readiness = requirement.readiness()
    if readiness.status != "READY_FOR_DESIGN":
        issues.append(
            _issue(
                "requirement.not_ready",
                "requirement",
                "Process requirement still contains engineering blockers or pending assumptions",
            )
        )
    if design.requirement_hash != requirement_hash:
        issues.append(
            _issue(
                "identity.requirement_hash_mismatch",
                "design.requirement_hash",
                "ProcessDesignIR is not bound to the exact requirement document",
            )
        )
    if design.target_simulator != requirement.target_simulator:
        issues.append(
            _issue(
                "target.simulator_mismatch",
                "design.target_simulator",
                "Design target simulator differs from the approved requirement",
            )
        )
    if design.target_version != requirement.target_version:
        issues.append(
            _issue(
                "target.version_mismatch",
                "design.target_version",
                "Design target version differs from the approved requirement",
            )
        )

    design_components = {item.id for item in design.components}
    required_components = {
        component_id for feed in requirement.feeds for component_id in feed.components
    }
    missing_components = sorted(required_components - design_components)
    unapproved_components = sorted(design_components - required_components)
    if missing_components:
        issues.append(
            _issue(
                "components.missing",
                "design.components",
                "Design omits required components: " + ", ".join(missing_components),
            )
        )
    if unapproved_components:
        issues.append(
            _issue(
                "components.unapproved",
                "design.components",
                "Design introduces components absent from the approved requirement: "
                + ", ".join(unapproved_components),
            )
        )

    feed_equipment = {item.id for item in design.equipment if item.kind == "feed"}
    product_equipment = {item.id for item in design.equipment if item.kind == "product"}
    required_feeds = {item.id for item in requirement.feeds}
    required_products = {item.id for item in requirement.products}
    missing_feeds = sorted(required_feeds - feed_equipment)
    extra_feeds = sorted(feed_equipment - required_feeds)
    missing_products = sorted(required_products - product_equipment)
    extra_products = sorted(product_equipment - required_products)
    if missing_feeds:
        issues.append(
            _issue(
                "feeds.missing",
                "design.equipment",
                "Design omits required feed boundary objects: " + ", ".join(missing_feeds),
            )
        )
    if extra_feeds:
        issues.append(
            _issue(
                "feeds.unapproved",
                "design.equipment",
                "Design introduces unapproved feed boundary objects: " + ", ".join(extra_feeds),
            )
        )
    if missing_products:
        issues.append(
            _issue(
                "products.missing",
                "design.equipment",
                "Design omits required product boundary objects: " + ", ".join(missing_products),
            )
        )
    if extra_products:
        issues.append(
            _issue(
                "products.unapproved",
                "design.equipment",
                "Design introduces unapproved product boundary objects: "
                + ", ".join(extra_products),
            )
        )

    issues.extend(_feed_contract_issues(requirement, design))

    required_method = requirement.property_method.value
    if not isinstance(required_method, str):
        issues.append(
            _issue(
                "property_method.requirement_invalid",
                "requirement.property_method",
                "Approved requirement must name a property method",
            )
        )
    elif design.property_method.id.casefold() != required_method.casefold():
        issues.append(
            _issue(
                "property_method.mismatch",
                "design.property_method.id",
                "Design property method differs from the approved requirement",
            )
        )

    ordered = tuple(sorted(issues))
    return DesignContractReport(
        valid=not ordered,
        requirement_hash=requirement_hash,
        design_hash=design.digest(),
        issues=ordered,
    )
