from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .hashing import canonical_hash
from .process_ir_v2 import ProcessDesignIR

# Private compatibility alias; implementation lives in hashing.py.
_canonical_hash = canonical_hash

TOPOLOGY_SCHEMA = "aspenops.native-topology/v1"


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return value.strip()


@dataclass(frozen=True, slots=True, order=True)
class TopologyNode:
    id: str
    kind: str

    @classmethod
    def from_dict(cls, value: Any, *, label: str) -> TopologyNode:
        if not isinstance(value, dict):
            raise ValueError(f"{label} must be an object")
        if set(value) != {"id", "kind"}:
            raise ValueError(f"{label} must contain exactly id and kind")
        return cls(
            id=_text(value.get("id"), f"{label}.id"),
            kind=_text(value.get("kind"), f"{label}.kind").casefold(),
        )

    def to_dict(self) -> dict[str, str]:
        return {"id": self.id, "kind": self.kind}


@dataclass(frozen=True, slots=True, order=True)
class TopologyEdge:
    id: str
    kind: str
    source_equipment_id: str
    source_port_id: str
    target_equipment_id: str
    target_port_id: str

    @classmethod
    def from_dict(cls, value: Any, *, label: str) -> TopologyEdge:
        if not isinstance(value, dict):
            raise ValueError(f"{label} must be an object")
        required = {
            "id",
            "kind",
            "source_equipment_id",
            "source_port_id",
            "target_equipment_id",
            "target_port_id",
        }
        if set(value) != required:
            raise ValueError(f"{label} must contain exactly {sorted(required)}")
        return cls(
            id=_text(value.get("id"), f"{label}.id"),
            kind=_text(value.get("kind"), f"{label}.kind").casefold(),
            source_equipment_id=_text(
                value.get("source_equipment_id"),
                f"{label}.source_equipment_id",
            ),
            source_port_id=_text(value.get("source_port_id"), f"{label}.source_port_id"),
            target_equipment_id=_text(
                value.get("target_equipment_id"),
                f"{label}.target_equipment_id",
            ),
            target_port_id=_text(value.get("target_port_id"), f"{label}.target_port_id"),
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "id": self.id,
            "kind": self.kind,
            "source_equipment_id": self.source_equipment_id,
            "source_port_id": self.source_port_id,
            "target_equipment_id": self.target_equipment_id,
            "target_port_id": self.target_port_id,
        }


@dataclass(frozen=True, slots=True)
class NativeTopologySnapshot:
    simulator: str
    marketing_version: str
    nodes: tuple[TopologyNode, ...]
    edges: tuple[TopologyEdge, ...]
    source: str
    schema: str = TOPOLOGY_SCHEMA

    @classmethod
    def from_dict(cls, value: Any) -> NativeTopologySnapshot:
        if not isinstance(value, dict):
            raise ValueError("native topology snapshot must be an object")
        allowed = {
            "schema",
            "simulator",
            "marketing_version",
            "nodes",
            "edges",
            "source",
        }
        unknown = sorted(set(value) - allowed)
        if unknown:
            raise ValueError(
                "native topology snapshot contains unsupported fields: " + ", ".join(unknown)
            )
        schema = _text(value.get("schema", TOPOLOGY_SCHEMA), "native topology.schema")
        if schema != TOPOLOGY_SCHEMA:
            raise ValueError(f"Unsupported native topology schema: {schema}")
        raw_nodes = value.get("nodes", [])
        raw_edges = value.get("edges", [])
        if not isinstance(raw_nodes, list) or not isinstance(raw_edges, list):
            raise ValueError("native topology nodes and edges must be arrays")
        nodes = tuple(
            TopologyNode.from_dict(item, label=f"native topology.nodes[{index}]")
            for index, item in enumerate(raw_nodes)
        )
        edges = tuple(
            TopologyEdge.from_dict(item, label=f"native topology.edges[{index}]")
            for index, item in enumerate(raw_edges)
        )
        if len({item.id for item in nodes}) != len(nodes):
            raise ValueError("native topology node IDs must be unique")
        if len({item.id for item in edges}) != len(edges):
            raise ValueError("native topology edge IDs must be unique")
        return cls(
            simulator=_text(value.get("simulator"), "native topology.simulator").casefold(),
            marketing_version=_text(
                value.get("marketing_version"),
                "native topology.marketing_version",
            ),
            nodes=tuple(sorted(nodes)),
            edges=tuple(sorted(edges)),
            source=_text(value.get("source"), "native topology.source"),
            schema=schema,
        )

    @classmethod
    def from_design(cls, design: ProcessDesignIR) -> NativeTopologySnapshot:
        return cls(
            simulator=design.target_simulator,
            marketing_version=design.target_version,
            nodes=tuple(sorted(TopologyNode(item.id, item.kind) for item in design.equipment)),
            edges=tuple(
                sorted(
                    TopologyEdge(
                        id=item.id,
                        kind=item.kind,
                        source_equipment_id=item.source.equipment_id,
                        source_port_id=item.source.port_id,
                        target_equipment_id=item.target.equipment_id,
                        target_port_id=item.target.port_id,
                    )
                    for item in design.streams
                )
            ),
            source="ProcessDesignIR",
        )

    def identity_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "simulator": self.simulator,
            "marketing_version": self.marketing_version,
            "nodes": [item.to_dict() for item in self.nodes],
            "edges": [item.to_dict() for item in self.edges],
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self.identity_dict(), "source": self.source}

    def digest(self) -> str:
        return canonical_hash(self.identity_dict())


@dataclass(frozen=True, slots=True, order=True)
class TopologyMismatch:
    code: str
    object_id: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "object_id": self.object_id,
            "message": self.message,
        }


@dataclass(frozen=True, slots=True)
class TopologyComparisonReport:
    matches: bool
    expected_hash: str
    observed_hash: str
    mismatches: tuple[TopologyMismatch, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "matches": self.matches,
            "expected_hash": self.expected_hash,
            "observed_hash": self.observed_hash,
            "mismatches": [item.to_dict() for item in self.mismatches],
        }


def compare_topology(
    expected: NativeTopologySnapshot,
    observed: NativeTopologySnapshot,
) -> TopologyComparisonReport:
    mismatches: list[TopologyMismatch] = []
    if expected.simulator != observed.simulator:
        mismatches.append(
            TopologyMismatch(
                "target.simulator",
                "topology",
                "Observed topology simulator differs from the expected simulator",
            )
        )
    if expected.marketing_version != observed.marketing_version:
        mismatches.append(
            TopologyMismatch(
                "target.version",
                "topology",
                "Observed topology version differs from the expected version",
            )
        )

    expected_nodes = {item.id: item for item in expected.nodes}
    observed_nodes = {item.id: item for item in observed.nodes}
    for node_id in sorted(expected_nodes.keys() - observed_nodes.keys()):
        mismatches.append(
            TopologyMismatch("node.missing", node_id, "Expected topology node is missing")
        )
    for node_id in sorted(observed_nodes.keys() - expected_nodes.keys()):
        mismatches.append(
            TopologyMismatch("node.extra", node_id, "Observed topology contains an extra node")
        )
    for node_id in sorted(expected_nodes.keys() & observed_nodes.keys()):
        if expected_nodes[node_id].kind != observed_nodes[node_id].kind:
            mismatches.append(
                TopologyMismatch(
                    "node.kind",
                    node_id,
                    "Observed topology node kind differs from the expected kind",
                )
            )

    expected_edges = {item.id: item for item in expected.edges}
    observed_edges = {item.id: item for item in observed.edges}
    for edge_id in sorted(expected_edges.keys() - observed_edges.keys()):
        mismatches.append(
            TopologyMismatch("edge.missing", edge_id, "Expected topology edge is missing")
        )
    for edge_id in sorted(observed_edges.keys() - expected_edges.keys()):
        mismatches.append(
            TopologyMismatch("edge.extra", edge_id, "Observed topology contains an extra edge")
        )
    for edge_id in sorted(expected_edges.keys() & observed_edges.keys()):
        if expected_edges[edge_id] != observed_edges[edge_id]:
            mismatches.append(
                TopologyMismatch(
                    "edge.contract",
                    edge_id,
                    "Observed edge kind, endpoints or ports differ from the expected contract",
                )
            )

    ordered = tuple(sorted(mismatches))
    return TopologyComparisonReport(
        matches=not ordered,
        expected_hash=expected.digest(),
        observed_hash=observed.digest(),
        mismatches=ordered,
    )
