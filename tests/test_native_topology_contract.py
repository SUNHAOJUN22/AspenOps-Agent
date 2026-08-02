from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

import aspenops_nexus.native_topology as topology
from aspenops_nexus.native_topology import (
    NativeTopologySnapshot,
    TopologyEdge,
    TopologyNode,
    compare_topology,
)
from aspenops_nexus.process_ir_v2 import ProcessDesignIR

ROOT = Path(__file__).resolve().parents[1]
DESIGN = ROOT / "examples/process-design-v2.example.json"


def design() -> ProcessDesignIR:
    value = json.loads(DESIGN.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return ProcessDesignIR.from_dict(value)


def snapshot() -> NativeTopologySnapshot:
    return NativeTopologySnapshot.from_design(design())


def test_snapshot_from_design_roundtrip_and_digest() -> None:
    expected = snapshot()
    restored = NativeTopologySnapshot.from_dict(expected.to_dict())
    assert restored == expected
    assert restored.digest() == expected.digest()
    assert restored.source == "ProcessDesignIR"
    assert len(restored.nodes) == 5
    assert len(restored.edges) == 4
    assert restored.nodes == tuple(sorted(restored.nodes))
    assert restored.edges == tuple(sorted(restored.edges))


def test_topology_source_metadata_does_not_change_identity() -> None:
    expected = snapshot()
    observed = replace(expected, source="native-readback")
    assert observed.to_dict()["source"] == "native-readback"
    assert observed.identity_dict() == expected.identity_dict()
    assert observed.digest() == expected.digest()
    assert compare_topology(expected, observed).matches is True


def test_topology_exact_match() -> None:
    expected = snapshot()
    report = compare_topology(expected, expected)
    assert report.matches is True
    assert report.mismatches == ()
    assert report.expected_hash == expected.digest()
    assert report.observed_hash == expected.digest()
    assert report.to_dict()["matches"] is True


def test_topology_detects_target_node_and_edge_changes() -> None:
    expected = snapshot()
    observed = replace(
        expected,
        simulator="hysys",
        marketing_version="14",
        nodes=(
            *expected.nodes[1:-1],
            TopologyNode(expected.nodes[-1].id, "changed_kind"),
            TopologyNode("EXTRA_001", "heater"),
        ),
        edges=(
            *expected.edges[1:-1],
            replace(expected.edges[-1], target_port_id="WRONG"),
            TopologyEdge("EXTRA_EDGE", "material", "A", "OUT", "B", "IN"),
        ),
        source="native-readback",
    )
    report = compare_topology(expected, observed)
    assert report.matches is False
    codes = {item.code for item in report.mismatches}
    assert {
        "target.simulator",
        "target.version",
        "node.missing",
        "node.extra",
        "node.kind",
        "edge.missing",
        "edge.extra",
        "edge.contract",
    }.issubset(codes)


def test_node_and_edge_roundtrip() -> None:
    node = TopologyNode.from_dict({"id": "HTR_001", "kind": "Heater"}, label="node")
    assert node == TopologyNode("HTR_001", "heater")
    assert node.to_dict() == {"id": "HTR_001", "kind": "heater"}

    edge = TopologyEdge.from_dict(
        {
            "id": "S001",
            "kind": "Material",
            "source_equipment_id": "FEED_001",
            "source_port_id": "OUT",
            "target_equipment_id": "HTR_001",
            "target_port_id": "IN",
        },
        label="edge",
    )
    assert edge.kind == "material"
    assert edge.to_dict()["target_port_id"] == "IN"


@pytest.mark.parametrize(
    "call",
    [
        lambda: TopologyNode.from_dict([], label="node"),
        lambda: TopologyNode.from_dict({"id": "A"}, label="node"),
        lambda: TopologyEdge.from_dict([], label="edge"),
        lambda: TopologyEdge.from_dict({"id": "S"}, label="edge"),
    ],
)
def test_node_and_edge_reject_invalid_shapes(call: Callable[[], Any]) -> None:
    with pytest.raises(ValueError):
        call()


def valid_snapshot_dict() -> dict[str, Any]:
    return snapshot().to_dict()


@pytest.mark.parametrize(
    "mutate",
    [
        lambda value: value.update({"schema": "other/v1"}),
        lambda value: value.update({"nodes": {}}),
        lambda value: value.update({"edges": {}}),
        lambda value: value.update({"bad": True}),
    ],
)
def test_snapshot_rejects_invalid_shapes(mutate: Callable[[dict[str, Any]], None]) -> None:
    value = valid_snapshot_dict()
    mutate(value)
    with pytest.raises(ValueError):
        NativeTopologySnapshot.from_dict(value)


def test_snapshot_rejects_duplicate_node_and_edge_ids() -> None:
    value = valid_snapshot_dict()
    value["nodes"].append(dict(value["nodes"][0]))
    with pytest.raises(ValueError, match="node IDs must be unique"):
        NativeTopologySnapshot.from_dict(value)

    value = valid_snapshot_dict()
    value["edges"].append(dict(value["edges"][0]))
    with pytest.raises(ValueError, match="edge IDs must be unique"):
        NativeTopologySnapshot.from_dict(value)


def test_topology_internal_helpers() -> None:
    assert topology._text(" x ", "value") == "x"
    assert len(topology._canonical_hash({"x": 1})) == 64
    with pytest.raises(ValueError):
        topology._text("", "value")
