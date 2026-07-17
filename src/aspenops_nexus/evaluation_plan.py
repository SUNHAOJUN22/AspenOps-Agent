from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .models import (
    BalanceSpec,
    BalanceTerm,
    ConstraintSpec,
    EvaluationRequest,
    VariableRead,
    VariableWrite,
)
from .policy import Policy
from .registry import NodeRegistry, ResolvedNode


def node_identity(node: ResolvedNode) -> str:
    suffix = ",".join(f"{key}={value}" for key, value in sorted(node.identifiers.items()))
    return node.key if not suffix else f"{node.key}:{suffix}"


@dataclass(frozen=True, slots=True)
class CompiledWrite:
    spec: VariableWrite
    node: ResolvedNode
    native_value: float | int | str | bool


@dataclass(frozen=True, slots=True)
class OutputBinding:
    spec: VariableRead
    node: ResolvedNode
    identity: str
    output_key: str


@dataclass(frozen=True, slots=True)
class CompiledConstraint:
    spec: ConstraintSpec
    node: ResolvedNode
    identity: str


@dataclass(frozen=True, slots=True)
class CompiledBalanceTerm:
    spec: BalanceTerm
    node: ResolvedNode
    identity: str


@dataclass(frozen=True, slots=True)
class CompiledBalance:
    spec: BalanceSpec
    terms: tuple[CompiledBalanceTerm, ...]


@dataclass(frozen=True, slots=True)
class IOEstimate:
    declared_writes: int
    unique_write_nodes: int
    declared_reads: int
    unique_read_nodes: int
    avoided_duplicate_reads: int


@dataclass(frozen=True, slots=True)
class EvaluationPlan:
    writes: tuple[CompiledWrite, ...]
    unique_reads: tuple[ResolvedNode, ...]
    output_bindings: tuple[OutputBinding, ...]
    constraints: tuple[CompiledConstraint, ...]
    balances: tuple[CompiledBalance, ...]
    physical_identity: dict[str, Any]
    estimated_io: IOEstimate


class EvaluationPlanCompiler:
    @staticmethod
    def compile(
        registry: NodeRegistry,
        request: EvaluationRequest,
        policy: Policy | None = None,
    ) -> EvaluationPlan:
        if request.writes and policy is not None:
            policy.assert_writes_allowed()

        compiled_writes: list[CompiledWrite] = []
        write_identities: set[str] = set()
        for spec in request.writes:
            node = registry.resolve(spec.key, spec.identifiers)
            registry.validate_backend(node, request.backend)
            native_value = registry.validate_write(node, spec.value, spec.unit)
            compiled_writes.append(CompiledWrite(spec, node, native_value))
            write_identities.add(node_identity(node))

        unique_reads: dict[str, ResolvedNode] = {}
        output_bindings: list[OutputBinding] = []
        for spec in request.reads:
            node = registry.resolve(spec.key, spec.identifiers)
            registry.validate_backend(node, request.backend)
            identity = node_identity(node)
            unique_reads.setdefault(identity, node)
            output_bindings.append(OutputBinding(spec, node, identity, identity))

        constraints: list[CompiledConstraint] = []
        for spec in request.constraints:
            node = registry.resolve(spec.key, spec.identifiers)
            registry.validate_backend(node, request.backend)
            identity = node_identity(node)
            unique_reads.setdefault(identity, node)
            constraints.append(CompiledConstraint(spec, node, identity))

        balances: list[CompiledBalance] = []
        for spec in request.balances:
            terms: list[CompiledBalanceTerm] = []
            for term_spec in spec.terms:
                node = registry.resolve(term_spec.key, term_spec.identifiers)
                registry.validate_backend(node, request.backend)
                identity = node_identity(node)
                unique_reads.setdefault(identity, node)
                terms.append(CompiledBalanceTerm(term_spec, node, identity))
            balances.append(CompiledBalance(spec, tuple(terms)))

        declared_reads = (
            len(output_bindings)
            + len(constraints)
            + sum(len(balance.terms) for balance in balances)
        )
        estimate = IOEstimate(
            declared_writes=len(compiled_writes),
            unique_write_nodes=len(write_identities),
            declared_reads=declared_reads,
            unique_read_nodes=len(unique_reads),
            avoided_duplicate_reads=max(0, declared_reads - len(unique_reads)),
        )
        return EvaluationPlan(
            writes=tuple(compiled_writes),
            unique_reads=tuple(unique_reads.values()),
            output_bindings=tuple(output_bindings),
            constraints=tuple(constraints),
            balances=tuple(balances),
            physical_identity=request.physical_identity(),
            estimated_io=estimate,
        )
