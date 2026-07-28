from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GRAPH_PARTS = ROOT / ".github" / "rsl-source" / "research_graph.py"
EDGE_PARTS = ROOT / ".github" / "rsl-source" / "test_research_contract_edges.py"
GRAPH_OUTPUT = ROOT / "src" / "aspenops_nexus" / "research_graph.py"
EDGE_OUTPUT = ROOT / "tests" / "test_research_contract_edges.py"
WHEEL_TEST = ROOT / "tests" / "test_wheel_metadata_edges.py"


def replace_once(text: str, old: str, new: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected exactly one patch target, found {count}: {old[:100]!r}")
    return text.replace(old, new, 1)


def reconstruct_graph() -> str:
    part0 = (GRAPH_PARTS / "part-00").read_text(encoding="utf-8")
    part1_lines = (GRAPH_PARTS / "part-01").read_text(encoding="utf-8").splitlines(keepends=True)
    part1 = "".join(part1_lines[2:])
    part2 = (GRAPH_PARTS / "part-02").read_text(encoding="utf-8")
    part3 = (GRAPH_PARTS / "part-03").read_text(encoding="utf-8")
    return part0 + part1 + part2 + part3


def repair_graph(text: str) -> str:
    text = replace_once(text, "from typing import Any, cast", "from typing import Any, Literal, cast")
    text = replace_once(
        text,
        """    datasets_by_id = {item.dataset_id: item for item in document.datasets}
    targets_by_id = {item.target_id: item for item in document.targets}
    parameters_by_id = {item.parameter_id: item for item in document.parameters}
    assumptions_by_id = {item.assumption_id: item for item in document.assumptions}
    calibrations_by_id = {item.calibration_id: item for item in document.calibrations}
    validations_by_id = {item.validation_id: item for item in document.validations}
""",
        """    datasets_by_id = {item.dataset_id: item for item in document.datasets}
    calibrations_by_id = {item.calibration_id: item for item in document.calibrations}
""",
    )
    text = replace_once(
        text,
        """            target = resolve(
                ref,
                owner=owner,
                path=f"calibration.target_refs[{index}]",
            )
            if ref.object_type != "target" or not isinstance(target, Target):
""",
        """            resolved_target = resolve(
                ref,
                owner=owner,
                path=f"calibration.target_refs[{index}]",
            )
            if ref.object_type != "target" or not isinstance(resolved_target, Target):
""",
    )
    text = replace_once(
        text,
        """            elif target.role not in {"fit", "acceptance", "diagnostic"}:
                add(
                    "error",
                    "calibration_target_role",
                    f"Calibration cannot use Target with role={target.role}",
""",
        """            elif resolved_target.role not in {"fit", "acceptance", "diagnostic"}:
                add(
                    "error",
                    "calibration_target_role",
                    f"Calibration cannot use Target with role={resolved_target.role}",
""",
    )
    text = replace_once(
        text,
        """            parameter = resolve(
                ref,
                owner=owner,
                path=f"calibration.parameter_refs[{index}]",
            )
            if ref.object_type != "parameter" or not isinstance(parameter, Parameter):
""",
        """            resolved_parameter = resolve(
                ref,
                owner=owner,
                path=f"calibration.parameter_refs[{index}]",
            )
            if ref.object_type != "parameter" or not isinstance(
                resolved_parameter, Parameter
            ):
""",
    )
    text = replace_once(
        text,
        """            elif parameter.mode == "estimated":
                estimated_count += 1
""",
        """            elif resolved_parameter.mode == "estimated":
                estimated_count += 1
""",
    )
    text = replace_once(
        text,
        """            target = resolve(
                ref,
                owner=owner,
                path=f"validation.target_refs[{index}]",
            )
            if ref.object_type != "target" or not isinstance(target, Target):
""",
        """            resolved_target = resolve(
                ref,
                owner=owner,
                path=f"validation.target_refs[{index}]",
            )
            if ref.object_type != "target" or not isinstance(resolved_target, Target):
""",
    )
    text = replace_once(
        text,
        """            calibration = calibrations_by_id.get(producer.object_id)
            if calibration is None:
""",
        """            resolved_calibration = calibrations_by_id.get(producer.object_id)
            if resolved_calibration is None:
""",
    )
    text = replace_once(
        text,
        '            elif calibration.status != "accepted":',
        '            elif resolved_calibration.status != "accepted":',
    )
    text = replace_once(
        text,
        """            elif calibration.accepted_parameter_snapshot is None or (
                calibration.accepted_parameter_snapshot.sha256
""",
        """            elif resolved_calibration.accepted_parameter_snapshot is None or (
                resolved_calibration.accepted_parameter_snapshot.sha256
""",
    )
    text = replace_once(
        text,
        '    validation_ceiling = "STRUCTURE_ONLY"',
        '    validation_ceiling: Maturity = "STRUCTURE_ONLY"',
    )
    text = replace_once(
        text,
        """    computed_ceiling = cast(
        Maturity,
        min(
            (document.study.claim_ceiling, validation_ceiling),
            key=lambda item: _MATURITY_RANK[item],
        ),
    )
    if not document.validations:
        computed_ceiling = cast(
            Maturity,
            min(
                (document.study.claim_ceiling, "SOURCE_CASE_REPRODUCED"),
                key=lambda item: _MATURITY_RANK[item],
            ),
        )
""",
        """    computed_ceiling: Maturity = (
        document.study.claim_ceiling
        if _MATURITY_RANK[document.study.claim_ceiling]
        <= _MATURITY_RANK[validation_ceiling]
        else validation_ceiling
    )
    if not document.validations:
        source_reproduced: Maturity = "SOURCE_CASE_REPRODUCED"
        computed_ceiling = (
            document.study.claim_ceiling
            if _MATURITY_RANK[document.study.claim_ceiling]
            <= _MATURITY_RANK[source_reproduced]
            else source_reproduced
        )
""",
    )
    text = replace_once(
        text,
        """            validation = resolve(
                ref,
                owner=owner,
                path=f"claim.validation_refs[{index}]",
            )
            if ref.object_type != "validation" or not isinstance(validation, Validation):
""",
        """            resolved_validation = resolve(
                ref,
                owner=owner,
                path=f"claim.validation_refs[{index}]",
            )
            if ref.object_type != "validation" or not isinstance(
                resolved_validation, Validation
            ):
""",
    )
    text = replace_once(
        text,
        """            else:
                linked_validations.append(validation)
        linked_assumptions: list[Assumption] = []
""",
        """            else:
                linked_validations.append(resolved_validation)
        linked_assumptions: list[Assumption] = []
""",
    )
    text = replace_once(
        text,
        """            assumption = resolve(
                ref,
                owner=owner,
                path=f"claim.assumption_refs[{index}]",
            )
            if ref.object_type != "assumption" or not isinstance(assumption, Assumption):
""",
        """            resolved_assumption = resolve(
                ref,
                owner=owner,
                path=f"claim.assumption_refs[{index}]",
            )
            if ref.object_type != "assumption" or not isinstance(
                resolved_assumption, Assumption
            ):
""",
    )
    text = replace_once(
        text,
        """            else:
                linked_assumptions.append(assumption)
        if _MATURITY_RANK[claim.maturity] > _MATURITY_RANK[document.study.claim_ceiling]:
""",
        """            else:
                linked_assumptions.append(resolved_assumption)
        if (
            document.study.purpose == "source_reproduction"
            and _MATURITY_RANK[claim.maturity]
            > _MATURITY_RANK["SOURCE_CASE_REPRODUCED"]
        ):
            add(
                "error",
                "source_reproduction_claim_ceiling",
                "Source-reproduction Study cannot support independent validation maturity",
                owner,
                "claim.maturity",
            )
        for linked_assumption in linked_assumptions:
            if (
                linked_assumption.risk == "critical"
                and linked_assumption.status in {"proposed", "challenged", "unresolved"}
                and claim.maturity != "STRUCTURE_ONLY"
            ):
                add(
                    "error",
                    "claim_blocked_by_critical_assumption",
                    "Critical unresolved Assumption limits Claim to STRUCTURE_ONLY",
                    owner,
                    "claim.maturity",
                )
        if _MATURITY_RANK[claim.maturity] > _MATURITY_RANK[document.study.claim_ceiling]:
""",
    )
    return text


def main() -> int:
    GRAPH_OUTPUT.write_text(repair_graph(reconstruct_graph()), encoding="utf-8")
    edge_parts = sorted(EDGE_PARTS.glob("part-*"))
    if len(edge_parts) != 3:
        raise RuntimeError(f"expected three edge-test parts, found {len(edge_parts)}")
    EDGE_OUTPUT.write_text(
        "".join(path.read_text(encoding="utf-8") for path in edge_parts),
        encoding="utf-8",
    )
    wheel_test = WHEEL_TEST.read_text(encoding="utf-8")
    wheel_test = replace_once(
        wheel_test,
        '("mcp>=1.9,<2; extra == \'other\'", "not enabled by the agent extra")',
        '("mcp>=1.9,<2; extra == \'other\'", "scoped to the agent extra")',
    )
    WHEEL_TEST.write_text(wheel_test, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
