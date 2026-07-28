from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GRAPH_PARTS = ROOT / ".github" / "rsl-source" / "research_graph.py"
EDGE_PARTS = ROOT / ".github" / "rsl-source" / "test_research_contract_edges.py"
GRAPH_OUTPUT = ROOT / "src" / "aspenops_nexus" / "research_graph.py"
EDGE_OUTPUT = ROOT / "tests" / "test_research_contract_edges.py"
WHEEL_TEST = ROOT / "tests" / "test_wheel_metadata_edges.py"
SELF_WORKFLOW = ROOT / ".github" / "workflows" / "research-p0-final-once.yml"


def patch(text: str, old: str, new: str, *, count: int = 1) -> str:
    actual = text.count(old)
    if actual != count:
        raise RuntimeError(f"expected {count} patch targets, found {actual}: {old[:100]!r}")
    return text.replace(old, new)


def reconstruct_graph() -> str:
    parts = [
        (GRAPH_PARTS / "part-00").read_text(encoding="utf-8"),
        "".join(
            (GRAPH_PARTS / "part-01")
            .read_text(encoding="utf-8")
            .splitlines(keepends=True)[2:]
        ),
        (GRAPH_PARTS / "part-02").read_text(encoding="utf-8"),
        (GRAPH_PARTS / "part-03").read_text(encoding="utf-8"),
    ]
    return "".join(parts)


def repair_graph(text: str) -> str:
    text = patch(
        text,
        "from typing import Any, cast",
        "from typing import Any, Literal, cast",
    )
    for unused in (
        "    targets_by_id = {item.target_id: item for item in document.targets}\n",
        "    parameters_by_id = {item.parameter_id: item for item in document.parameters}\n",
        "    assumptions_by_id = {item.assumption_id: item for item in document.assumptions}\n",
        "    validations_by_id = {item.validation_id: item for item in document.validations}\n",
    ):
        text = patch(text, unused, "")

    text = patch(
        text,
        "            target = resolve(\n",
        "            resolved_target = resolve(\n",
        count=2,
    )
    text = patch(
        text,
        "not isinstance(target, Target)",
        "not isinstance(resolved_target, Target)",
        count=2,
    )
    text = patch(text, "target.role", "resolved_target.role", count=2)
    text = patch(
        text,
        "            parameter = resolve(\n",
        "            resolved_parameter = resolve(\n",
    )
    text = patch(
        text,
        "not isinstance(parameter, Parameter)",
        "not isinstance(resolved_parameter, Parameter)",
    )
    text = patch(text, "parameter.mode", "resolved_parameter.mode")
    text = patch(
        text,
        "            calibration = calibrations_by_id.get(producer.object_id)\n",
        "            resolved_calibration = calibrations_by_id.get(producer.object_id)\n",
    )
    text = patch(text, "calibration is None", "resolved_calibration is None")
    text = patch(text, "calibration.status", "resolved_calibration.status")
    text = patch(
        text,
        "calibration.accepted_parameter_snapshot",
        "resolved_calibration.accepted_parameter_snapshot",
        count=2,
    )
    text = patch(
        text,
        "            validation = resolve(\n",
        "            resolved_validation = resolve(\n",
    )
    text = patch(
        text,
        "not isinstance(validation, Validation)",
        "not isinstance(resolved_validation, Validation)",
    )
    text = patch(
        text,
        "linked_validations.append(validation)",
        "linked_validations.append(resolved_validation)",
    )
    text = patch(
        text,
        "            assumption = resolve(\n",
        "            resolved_assumption = resolve(\n",
    )
    text = patch(
        text,
        "not isinstance(assumption, Assumption)",
        "not isinstance(resolved_assumption, Assumption)",
    )
    text = patch(
        text,
        "linked_assumptions.append(assumption)",
        "linked_assumptions.append(resolved_assumption)",
    )
    text = patch(
        text,
        '    validation_ceiling = "STRUCTURE_ONLY"',
        '    validation_ceiling: Maturity = "STRUCTURE_ONLY"',
    )
    text = patch(
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
        """    computed_ceiling: Maturity = min(
        (document.study.claim_ceiling, validation_ceiling),
        key=lambda item: _MATURITY_RANK[item],
    )
    if not document.validations:
        source_reproduced: Maturity = "SOURCE_CASE_REPRODUCED"
        computed_ceiling = min(
            (document.study.claim_ceiling, source_reproduced),
            key=lambda item: _MATURITY_RANK[item],
        )
""",
    )
    claim_guard = """        if (
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
"""
    study_ceiling = (
        "        if _MATURITY_RANK[claim.maturity] "
        "> _MATURITY_RANK[document.study.claim_ceiling]:\n"
    )
    return patch(text, study_ceiling, claim_guard + study_ceiling)


def main() -> int:
    GRAPH_OUTPUT.write_text(repair_graph(reconstruct_graph()), encoding="utf-8")
    edge_parts = sorted(EDGE_PARTS.glob("part-*"))
    if len(edge_parts) != 3:
        raise RuntimeError(f"expected three edge-test parts, found {len(edge_parts)}")
    EDGE_OUTPUT.write_text(
        "".join(path.read_text(encoding="utf-8") for path in edge_parts),
        encoding="utf-8",
    )
    wheel_text = WHEEL_TEST.read_text(encoding="utf-8")
    wheel_text = patch(
        wheel_text,
        "not enabled by the agent extra",
        "scoped to the agent extra",
    )
    WHEEL_TEST.write_text(wheel_text, encoding="utf-8")
    SELF_WORKFLOW.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
