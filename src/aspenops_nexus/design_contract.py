from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .process_ir_v2 import ProcessDesignIR
from .process_requirement import ProcessRequirementDocument


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
