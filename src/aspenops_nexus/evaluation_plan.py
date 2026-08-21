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
from .registry import NodeRegistry, RegistryError, ResolvedNode
from .units import dimension as unit_dimension


def _semantic_identity(key: str, identifiers: dict[str, str]) -> str:
    suffix = ",".join(f"{name}={value}" for name, value in sorted(identifiers.items()))
    return key if not suffix else f"{key}:{suffix}"


def node_identity(node: ResolvedNode) -> str:
    return _semantic_identity(node.key, node.identifiers)


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
    dimension: str | None = None
    base_unit: str | None = None


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
        for write_spec in request.writes:
            write_node = registry.resolve(write_spec.key, write_spec.identifiers)
            registry.validate_backend(write_node, request.backend)
            identity = node_identity(write_node)
            if identity in write_identities:
                raise ValueError(f"Duplicate write target: {identity}")
            native_value = registry.validate_write(write_node, write_spec.value, write_spec.unit)
            compiled_writes.append(CompiledWrite(write_spec, write_node, native_value))
            write_identities.add(identity)

        unique_reads: dict[str, ResolvedNode] = {}

        def resolve_read_node(key: str, identifiers: dict[str, str]) -> tuple[ResolvedNode, str]:
            identity = _semantic_identity(key, identifiers)
            node = unique_reads.get(identity)
            if node is None:
                node = registry.resolve(key, identifiers)
                registry.validate_backend(node, request.backend)
                if node.access not in {"read", "readwrite"}:
                    raise RegistryError(f"Semantic key is write-only: {node.key}")
                unique_reads[identity] = node
            return node, identity

        output_bindings: list[OutputBinding] = []
        output_identities: set[str] = set()
        for read_spec in request.reads:
            read_node, identity = resolve_read_node(read_spec.key, read_spec.identifiers)
            if identity in output_identities:
                raise ValueError(f"Duplicate read output target: {identity}")
            output_identities.add(identity)
            output_bindings.append(OutputBinding(read_spec, read_node, identity, identity))

        constraints: list[CompiledConstraint] = []
        for constraint_spec in request.constraints:
            constraint_node, identity = resolve_read_node(
                constraint_spec.key,
                constraint_spec.identifiers,
            )
            constraints.append(CompiledConstraint(constraint_spec, constraint_node, identity))

        balances: list[CompiledBalance] = []
        for balance_spec in request.balances:
            terms: list[CompiledBalanceTerm] = []
            effective_units: list[str] = []
            inferred_dimensions: set[str] = set()
            for term_spec in balance_spec.terms:
                term_node, identity = resolve_read_node(term_spec.key, term_spec.identifiers)
                native_unit = term_node.native_unit
                if native_unit is None:
                    raise ValueError(
                        f"Balance {balance_spec.name} term {identity} has no registered native unit"
                    )
                native_dimension = unit_dimension(native_unit)
                effective_unit = term_spec.unit or native_unit
                effective_dimension = unit_dimension(effective_unit)
                if native_dimension != effective_dimension:
                    raise ValueError(
                        f"Balance {balance_spec.name} term {identity} requests incompatible unit "
                        f"{effective_unit!r} for registered unit {native_unit!r}"
                    )
                if effective_dimension is None:
                    raise ValueError(
                        f"Balance {balance_spec.name} term {identity} has no physical dimension"
                    )
                effective_units.append(effective_unit)
                inferred_dimensions.add(effective_dimension)
                terms.append(CompiledBalanceTerm(term_spec, term_node, identity))
            if len(inferred_dimensions) != 1:
                observed = ", ".join(sorted(inferred_dimensions))
                raise ValueError(
                    f"Balance {balance_spec.name} mixes physical dimensions: {observed}"
                )
            inferred_dimension = next(iter(inferred_dimensions))
            if balance_spec.dimension is not None and balance_spec.dimension != inferred_dimension:
                raise ValueError(
                    f"Balance {balance_spec.name} declares dimension "
                    f"{balance_spec.dimension!r} but terms are {inferred_dimension!r}"
                )
            resolved_dimension = balance_spec.dimension or inferred_dimension
            resolved_base_unit = balance_spec.base_unit or effective_units[0]
            base_dimension = unit_dimension(resolved_base_unit)
            if base_dimension != resolved_dimension:
                raise ValueError(
                    f"Balance {balance_spec.name} base unit {resolved_base_unit!r} has "
                    f"dimension {base_dimension!r}, expected {resolved_dimension!r}"
                )
            balances.append(
                CompiledBalance(
                    balance_spec,
                    tuple(terms),
                    resolved_dimension,
                    resolved_base_unit,
                )
            )

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
