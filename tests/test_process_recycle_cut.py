from __future__ import annotations

import json
from dataclasses import replace
from itertools import permutations, product
from pathlib import Path
from typing import Any

import pytest

from aspenops_nexus.compilation_plan import compile_process_design
from aspenops_nexus.engineering_rules import validate_process_design
from aspenops_nexus.process_ir_v2 import ProcessDesignIR
from aspenops_nexus.simulator_capabilities import get_builtin_capability_profile

ROOT = Path(__file__).resolve().parents[1]


def graph_design(edges: list[tuple[str, str, str, str]]) -> ProcessDesignIR:
    value: dict[str, Any] = json.loads(
        (ROOT / "examples/process-design-v2.example.json").read_text(encoding="utf-8")
    )
    value["equipment"] = [
        {
            "id": name,
            "display_name": name,
            "kind": "mixer",
            "vendor_type": "MIXER",
            "ports": [
                {
                    "id": port,
                    "direction": direction,
                    "domain": "material",
                    "required": False,
                    "multiple": True,
                }
                for port, direction in [("IN", "in"), ("OUT", "out")]
            ],
            "parameters": [],
            "design_specs": [],
            "contract_version": "1",
        }
        for name in ("A", "B", "C")
    ]
    value["streams"] = [
        {
            "id": identity,
            "display_name": identity,
            "kind": kind,
            "source": {"equipment_id": source, "port_id": "OUT"},
            "target": {"equipment_id": target, "port_id": "IN"},
            "components": ["ETHANOL", "WATER"],
            "parameters": [],
        }
        for identity, source, target, kind in edges
    ]
    value["recycles"] = [
        {
            "id": f"R_{identity}",
            "stream_id": identity,
            "tear_stream_id": identity,
            "convergence_variables": ["FLOW"],
            "tolerance": 1e-6,
            "max_iterations": 50,
            "acceleration": "wegstein",
            "status": "USER_PROVIDED",
        }
        for identity, _, _, kind in edges
        if kind == "tear"
    ]
    return ProcessDesignIR.from_dict(value)


@pytest.mark.parametrize(
    "edges",
    [
        [
            ("TEAR_AB", "A", "B", "tear"),
            ("S_BA", "B", "A", "material"),
            ("S_AC", "A", "C", "material"),
            ("S_CB", "C", "B", "material"),
        ],
        [
            ("TEAR_AB", "A", "B", "tear"),
            ("S_AB", "A", "B", "material"),
            ("S_BA", "B", "A", "material"),
        ],
    ],
    ids=["overlapping_cycles", "parallel_material_edge"],
)
def test_owned_tears_must_cut_every_directed_material_cycle(
    edges: list[tuple[str, str, str, str]],
) -> None:
    design = graph_design(edges)
    report = validate_process_design(design)
    assert not report.valid, report.to_dict()
    assert "topology.recycle_contract_missing" in {issue.code for issue in report.blockers}
    # This is a synthetic capability fixture; no Aspen execution is requested.
    profile = replace(
        get_builtin_capability_profile("aspen_plus", "15"),
        qualification="VERIFIED_ON_TARGET_RUNTIME",
    )
    plan = compile_process_design(design, profile)
    assert plan.status == "BLOCKED"
    assert not plan.executable


def test_one_owned_tear_can_cut_multiple_cycles() -> None:
    design = graph_design(
        [
            ("TEAR_AB", "A", "B", "tear"),
            ("S_BA", "B", "A", "material"),
            ("S_BC", "B", "C", "material"),
            ("S_CA", "C", "A", "material"),
        ]
    )
    assert validate_process_design(design).valid


def test_three_node_cut_gate_matches_independent_topological_enumeration() -> None:
    nodes = ("A", "B", "C")
    directed_pairs = tuple(permutations(nodes, 2))
    orders = tuple(permutations(nodes))
    # 729 distinct graphs: each possible directed edge is absent, material, or owned tear.
    for choices in product((None, "material", "tear"), repeat=len(directed_pairs)):
        edges = [
            (f"S{index}", source, target, kind)
            for index, ((source, target), kind) in enumerate(
                zip(directed_pairs, choices, strict=True)
            )
            if kind is not None
        ]
        residual = [(source, target) for _, source, target, kind in edges if kind != "tear"]
        # Independent exhaustive order search, not the implementation's DFS.
        expected = any(
            all(order.index(source) < order.index(target) for source, target in residual)
            for order in orders
        )
        report = validate_process_design(graph_design(edges))
        assert report.valid == expected, (choices, report.to_dict())
