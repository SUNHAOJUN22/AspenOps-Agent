from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal, Protocol, runtime_checkable

from .process_ir import IR_SCHEMA, Identifier, ProcessIntent

CapabilityStatus = Literal["available", "planned", "unavailable"]
_IDENTIFIER = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,63}$")


def _object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return {str(key): item for key, item in value.items()}


def _text(value: Any, label: str, *, nonempty: bool = True) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a string")
    normalized = value.strip()
    if nonempty and not normalized:
        raise ValueError(f"{label} must be a non-empty string")
    return normalized


def _identifier(value: Any, label: str) -> str:
    identifier = _text(value, label)
    if not _IDENTIFIER.fullmatch(identifier):
        raise ValueError(f"{label} must be a stable identifier")
    return identifier


def _boolean(value: Any, label: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{label} must be a boolean")
    return value


def _nonnegative_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{label} must be a non-negative integer")
    return value


def _reject_unknown(mapping: dict[str, Any], allowed: set[str], label: str) -> None:
    unknown = sorted(set(mapping) - allowed)
    if unknown:
        raise ValueError(f"{label} contains unsupported fields: {', '.join(unknown)}")


@dataclass(frozen=True, slots=True)
class BackendCapability:
    backend: str
    execution: CapabilityStatus
    ir_compiler: CapabilityStatus
    steady_state: bool
    dynamic: bool
    optimization: bool
    requires_license: bool
    platforms: tuple[str, ...]
    note: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "backend": self.backend,
            "execution": self.execution,
            "ir_compiler": self.ir_compiler,
            "steady_state": self.steady_state,
            "dynamic": self.dynamic,
            "optimization": self.optimization,
            "requires_license": self.requires_license,
            "platforms": list(self.platforms),
            "note": self.note,
        }


class BackendUnavailableError(RuntimeError):
    """Raised when a requested simulator-neutral compiler is not implemented."""


@runtime_checkable
class ProcessIRCompiler(Protocol):
    backend: str

    def compile(self, intent: ProcessIntent) -> dict[str, Any]:
        """Compile validated IR into a backend-specific, non-executable plan."""


def backend_capabilities() -> tuple[BackendCapability, ...]:
    return (
        BackendCapability(
            "mock",
            "available",
            "planned",
            True,
            False,
            True,
            False,
            ("linux", "windows", "macos"),
            "Portable execution exists; topology compilation from IR is not implemented.",
        ),
        BackendCapability(
            "aspen_plus",
            "available",
            "planned",
            True,
            False,
            True,
            True,
            ("windows",),
            "Licensed execution exists; automatic flowsheet construction remains planned.",
        ),
        BackendCapability(
            "hysys",
            "available",
            "planned",
            True,
            False,
            True,
            True,
            ("windows",),
            "Licensed execution exists; automatic flowsheet construction remains planned.",
        ),
        BackendCapability(
            "dwsim",
            "planned",
            "planned",
            True,
            True,
            True,
            False,
            ("linux", "windows", "macos"),
            "Open simulation backend candidate; no adapter is claimed in this release.",
        ),
        BackendCapability(
            "idaes",
            "planned",
            "planned",
            True,
            True,
            True,
            False,
            ("linux", "windows", "macos"),
            "Equation-oriented optimization backend candidate; adapter is not implemented.",
        ),
        BackendCapability(
            "modelica",
            "planned",
            "planned",
            True,
            True,
            True,
            False,
            ("linux", "windows", "macos"),
            "FMI/Modelica backend candidate; adapter is not implemented.",
        ),
    )


def capability_matrix() -> list[dict[str, Any]]:
    return [item.to_dict() for item in backend_capabilities()]


def require_ir_compiler(backend: str) -> None:
    normalized = backend.strip().casefold()
    capability = next(
        (item for item in backend_capabilities() if item.backend == normalized),
        None,
    )
    if capability is None:
        raise BackendUnavailableError(f"Unknown simulator backend: {backend}")
    if capability.ir_compiler != "available":
        raise BackendUnavailableError(
            f"Process IR compiler for {normalized} is {capability.ir_compiler}; "
            "the project will not pretend it can construct this simulator model"
        )


@dataclass(frozen=True, slots=True)
class AgentStageSpec:
    id: str
    responsibility: str
    permitted_output: str

    def to_dict(self) -> dict[str, str]:
        return {
            "id": self.id,
            "responsibility": self.responsibility,
            "permitted_output": self.permitted_output,
        }


def agent_pipeline() -> tuple[AgentStageSpec, ...]:
    return (
        AgentStageSpec("knowledge", "Resolve process facts and evidence", "cited assumptions"),
        AgentStageSpec("concept", "Generate and normalize flowsheet topology", IR_SCHEMA),
        AgentStageSpec("parameter", "Declare scalar parameters and units", IR_SCHEMA),
        AgentStageSpec("execution", "Submit only validated backend plans", "execution request"),
        AgentStageSpec(
            "repair",
            "Use simulator diagnostics to propose bounded IR edits",
            IR_SCHEMA,
        ),
        AgentStageSpec(
            "review",
            "Check convergence, balances and approval boundaries",
            "review report",
        ),
    )


@dataclass(frozen=True, slots=True)
class FlowsheetBenchmarkRecord:
    scenario_id: Identifier
    backend: str
    topology_valid: bool
    compiler_available: bool
    execution_attempted: bool
    converged: bool | None
    material_balance_ok: bool | None
    energy_balance_ok: bool | None
    repair_iterations: int = 0
    human_intervention: bool = False
    note: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FlowsheetBenchmarkRecord:
        mapping = _object(data, "benchmark record")
        _reject_unknown(
            mapping,
            {
                "scenario_id",
                "backend",
                "topology_valid",
                "compiler_available",
                "execution_attempted",
                "converged",
                "material_balance_ok",
                "energy_balance_ok",
                "repair_iterations",
                "human_intervention",
                "note",
            },
            "benchmark record",
        )
        required = {
            "scenario_id",
            "backend",
            "topology_valid",
            "compiler_available",
            "execution_attempted",
        }
        missing = sorted(required - set(mapping))
        if missing:
            raise ValueError(f"benchmark record is missing: {', '.join(missing)}")

        attempted = _boolean(mapping["execution_attempted"], "execution_attempted")

        def optional_bool(name: str) -> bool | None:
            value = mapping.get(name)
            if value is None:
                return None
            return _boolean(value, name)

        converged = optional_bool("converged")
        material = optional_bool("material_balance_ok")
        energy = optional_bool("energy_balance_ok")
        if not attempted and any(value is not None for value in (converged, material, energy)):
            raise ValueError(
                "non-attempted execution cannot declare convergence or balance results"
            )
        return cls(
            scenario_id=_identifier(mapping["scenario_id"], "scenario_id"),
            backend=_text(mapping["backend"], "backend").casefold(),
            topology_valid=_boolean(mapping["topology_valid"], "topology_valid"),
            compiler_available=_boolean(mapping["compiler_available"], "compiler_available"),
            execution_attempted=attempted,
            converged=converged,
            material_balance_ok=material,
            energy_balance_ok=energy,
            repair_iterations=_nonnegative_int(
                mapping.get("repair_iterations", 0),
                "repair_iterations",
            ),
            human_intervention=_boolean(
                mapping.get("human_intervention", False),
                "human_intervention",
            ),
            note=_text(mapping.get("note", ""), "note", nonempty=False),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "backend": self.backend,
            "topology_valid": self.topology_valid,
            "compiler_available": self.compiler_available,
            "execution_attempted": self.execution_attempted,
            "converged": self.converged,
            "material_balance_ok": self.material_balance_ok,
            "energy_balance_ok": self.energy_balance_ok,
            "repair_iterations": self.repair_iterations,
            "human_intervention": self.human_intervention,
            "note": self.note,
        }


def summarize_benchmarks(records: tuple[FlowsheetBenchmarkRecord, ...]) -> dict[str, Any]:
    attempted = [item for item in records if item.execution_attempted]
    converged = [item for item in attempted if item.converged is True]
    balanced = [
        item
        for item in attempted
        if item.material_balance_ok is True and item.energy_balance_ok is True
    ]

    def rate(numerator: int, denominator: int) -> float | None:
        return None if denominator == 0 else 100.0 * numerator / denominator

    return {
        "scenarios": len(records),
        "topology_valid": sum(item.topology_valid for item in records),
        "compiler_available": sum(item.compiler_available for item in records),
        "execution_attempted": len(attempted),
        "converged": len(converged),
        "balanced": len(balanced),
        "convergence_rate_percent": rate(len(converged), len(attempted)),
        "balance_rate_percent": rate(len(balanced), len(attempted)),
        "repair_iterations": sum(item.repair_iterations for item in records),
        "human_interventions": sum(item.human_intervention for item in records),
    }
