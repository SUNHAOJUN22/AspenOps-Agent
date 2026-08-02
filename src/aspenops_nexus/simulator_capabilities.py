from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Literal, cast

from .process_ir_v2 import ProcessDesignIR

PROFILE_SCHEMA = "aspenops.simulator-capability-profile/v1"

SimulatorFamily = Literal["aspen_plus", "hysys"]
ProfileQualification = Literal[
    "OFFLINE_CONTRACT_ONLY",
    "VERIFIED_ON_TARGET_RUNTIME",
    "REVOKED",
]
CapabilityState = Literal["DECLARED", "UNSUPPORTED"]

_SUPPORTED_SIMULATORS = {"aspen_plus", "hysys"}
_SUPPORTED_VERSIONS = {"14", "15"}
_SUPPORTED_QUALIFICATIONS = {
    "OFFLINE_CONTRACT_ONLY",
    "VERIFIED_ON_TARGET_RUNTIME",
    "REVOKED",
}
_SUPPORTED_CAPABILITY_STATES = {"DECLARED", "UNSUPPORTED"}


def _canonical_hash(value: Any) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return value.strip()


def _string_tuple(value: Any, label: str) -> tuple[str, ...]:
    if not isinstance(value, list | tuple):
        raise ValueError(f"{label} must be an array")
    result = tuple(_text(item, f"{label} item") for item in value)
    if len(set(result)) != len(result):
        raise ValueError(f"{label} must contain unique values")
    return result


@dataclass(frozen=True, slots=True)
class EquipmentCapability:
    ir_kind: str
    adapter_key: str
    state: CapabilityState
    required_port_domains: tuple[str, ...]
    supported_parameter_names: tuple[str, ...]
    notes: str

    @classmethod
    def from_dict(cls, value: Any, *, label: str) -> EquipmentCapability:
        if not isinstance(value, dict):
            raise ValueError(f"{label} must be an object")
        allowed = {
            "ir_kind",
            "adapter_key",
            "state",
            "required_port_domains",
            "supported_parameter_names",
            "notes",
        }
        unknown = sorted(set(value) - allowed)
        if unknown:
            raise ValueError(f"{label} contains unsupported fields: {', '.join(unknown)}")
        state = _text(value.get("state"), f"{label}.state")
        if state not in _SUPPORTED_CAPABILITY_STATES:
            raise ValueError(f"{label}.state is unsupported: {state}")
        return cls(
            ir_kind=_text(value.get("ir_kind"), f"{label}.ir_kind").casefold(),
            adapter_key=_text(value.get("adapter_key"), f"{label}.adapter_key"),
            state=cast(CapabilityState, state),
            required_port_domains=_string_tuple(
                value.get("required_port_domains", []),
                f"{label}.required_port_domains",
            ),
            supported_parameter_names=_string_tuple(
                value.get("supported_parameter_names", []),
                f"{label}.supported_parameter_names",
            ),
            notes=_text(value.get("notes"), f"{label}.notes"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "ir_kind": self.ir_kind,
            "adapter_key": self.adapter_key,
            "state": self.state,
            "required_port_domains": list(self.required_port_domains),
            "supported_parameter_names": list(self.supported_parameter_names),
            "notes": self.notes,
        }


@dataclass(frozen=True, slots=True)
class SimulatorCapabilityProfile:
    profile_id: str
    simulator: SimulatorFamily
    marketing_version: str
    qualification: ProfileQualification
    adapter_contract: str
    model_extensions: tuple[str, ...]
    supported_stream_kinds: tuple[str, ...]
    equipment: tuple[EquipmentCapability, ...]
    source_boundary: str
    schema: str = PROFILE_SCHEMA

    @classmethod
    def from_dict(cls, value: Any) -> SimulatorCapabilityProfile:
        if not isinstance(value, dict):
            raise ValueError("capability profile must be an object")
        allowed = {
            "schema",
            "profile_id",
            "simulator",
            "marketing_version",
            "qualification",
            "adapter_contract",
            "model_extensions",
            "supported_stream_kinds",
            "equipment",
            "source_boundary",
        }
        unknown = sorted(set(value) - allowed)
        if unknown:
            raise ValueError(
                "capability profile contains unsupported fields: " + ", ".join(unknown)
            )
        schema = _text(value.get("schema", PROFILE_SCHEMA), "capability profile.schema")
        if schema != PROFILE_SCHEMA:
            raise ValueError(f"Unsupported capability profile schema: {schema}")
        simulator = _text(value.get("simulator"), "capability profile.simulator").casefold()
        if simulator not in _SUPPORTED_SIMULATORS:
            raise ValueError(f"Unsupported capability profile simulator: {simulator}")
        marketing_version = _text(
            value.get("marketing_version"),
            "capability profile.marketing_version",
        )
        if marketing_version not in _SUPPORTED_VERSIONS:
            raise ValueError(
                f"Unsupported capability profile marketing version: {marketing_version}"
            )
        qualification = _text(
            value.get("qualification"),
            "capability profile.qualification",
        )
        if qualification not in _SUPPORTED_QUALIFICATIONS:
            raise ValueError(f"Unsupported profile qualification: {qualification}")
        raw_equipment = value.get("equipment", [])
        if not isinstance(raw_equipment, list):
            raise ValueError("capability profile.equipment must be an array")
        equipment = tuple(
            EquipmentCapability.from_dict(item, label=f"capability profile.equipment[{index}]")
            for index, item in enumerate(raw_equipment)
        )
        kinds = [item.ir_kind for item in equipment]
        if len(set(kinds)) != len(kinds):
            raise ValueError("capability profile equipment kinds must be unique")
        model_extensions = tuple(
            item.casefold()
            for item in _string_tuple(
                value.get("model_extensions", []),
                "capability profile.model_extensions",
            )
        )
        if any(not item.startswith(".") for item in model_extensions):
            raise ValueError("Every model extension must begin with a period")
        stream_kinds = tuple(
            item.casefold()
            for item in _string_tuple(
                value.get("supported_stream_kinds", []),
                "capability profile.supported_stream_kinds",
            )
        )
        return cls(
            profile_id=_text(value.get("profile_id"), "capability profile.profile_id"),
            simulator=cast(SimulatorFamily, simulator),
            marketing_version=marketing_version,
            qualification=cast(ProfileQualification, qualification),
            adapter_contract=_text(
                value.get("adapter_contract"),
                "capability profile.adapter_contract",
            ),
            model_extensions=model_extensions,
            supported_stream_kinds=stream_kinds,
            equipment=equipment,
            source_boundary=_text(
                value.get("source_boundary"),
                "capability profile.source_boundary",
            ),
            schema=schema,
        )

    @property
    def executable(self) -> bool:
        return self.qualification == "VERIFIED_ON_TARGET_RUNTIME"

    def equipment_by_kind(self) -> dict[str, EquipmentCapability]:
        return {item.ir_kind: item for item in self.equipment}

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "profile_id": self.profile_id,
            "simulator": self.simulator,
            "marketing_version": self.marketing_version,
            "qualification": self.qualification,
            "adapter_contract": self.adapter_contract,
            "model_extensions": list(self.model_extensions),
            "supported_stream_kinds": list(self.supported_stream_kinds),
            "equipment": [item.to_dict() for item in self.equipment],
            "source_boundary": self.source_boundary,
        }

    def digest(self) -> str:
        return _canonical_hash(self.to_dict())

    def assert_matches_design(self, design: ProcessDesignIR) -> None:
        if design.target_simulator != self.simulator:
            raise ValueError("Capability profile simulator does not match ProcessDesignIR target")
        if design.target_version != self.marketing_version:
            raise ValueError("Capability profile version does not match ProcessDesignIR target")


_COMMON_STREAM_KINDS = (
    "material",
    "energy",
    "information",
    "tear",
    "feed",
    "product",
    "waste",
    "utility",
)


def _capability(
    ir_kind: str,
    adapter_key: str,
    parameters: tuple[str, ...],
    *,
    domains: tuple[str, ...] = ("material",),
    state: CapabilityState = "DECLARED",
    notes: str,
) -> EquipmentCapability:
    return EquipmentCapability(
        ir_kind=ir_kind,
        adapter_key=adapter_key,
        state=state,
        required_port_domains=domains,
        supported_parameter_names=parameters,
        notes=notes,
    )


_ASPEN_PLUS_EQUIPMENT = (
    _capability("feed", "boundary.feed", (), notes="Boundary object; no block is implied."),
    _capability("product", "boundary.product", (), notes="Boundary object; no block is implied."),
    _capability("mixer", "unit.mixer", (), notes="Native mapping requires runtime verification."),
    _capability(
        "splitter",
        "unit.splitter",
        ("SPLIT_FRACTION", "FLOW_SPEC"),
        notes="Native mapping requires runtime verification.",
    ),
    _capability(
        "heater",
        "unit.heater",
        ("OUTLET_TEMPERATURE", "DUTY", "VAPOR_FRACTION"),
        domains=("material", "energy"),
        notes="Native mapping requires runtime verification.",
    ),
    _capability(
        "cooler",
        "unit.cooler",
        ("OUTLET_TEMPERATURE", "DUTY", "VAPOR_FRACTION"),
        domains=("material", "energy"),
        notes="Native mapping requires runtime verification.",
    ),
    _capability(
        "flash2",
        "unit.flash",
        ("TEMPERATURE", "PRESSURE", "DUTY", "VAPOR_FRACTION"),
        notes="Native mapping requires runtime verification.",
    ),
    _capability(
        "separator",
        "unit.separator",
        ("TEMPERATURE", "PRESSURE", "DUTY", "VAPOR_FRACTION"),
        notes="Native mapping requires runtime verification.",
    ),
    _capability(
        "pump",
        "unit.pump",
        ("OUTLET_PRESSURE", "PRESSURE_RATIO", "PRESSURE_INCREASE", "EFFICIENCY"),
        domains=("material", "energy"),
        notes="Native mapping requires runtime verification.",
    ),
    _capability(
        "compressor",
        "unit.compressor",
        ("OUTLET_PRESSURE", "PRESSURE_RATIO", "PRESSURE_INCREASE", "EFFICIENCY"),
        domains=("material", "energy"),
        notes="Native mapping requires runtime verification.",
    ),
    _capability(
        "valve",
        "unit.valve",
        ("OUTLET_PRESSURE", "PRESSURE_DROP"),
        notes="Native mapping requires runtime verification.",
    ),
    _capability(
        "distillation_column",
        "unit.distillation_column",
        ("TOTAL_STAGES", "FEED_STAGE"),
        domains=("material", "energy"),
        notes="Native mapping requires runtime verification.",
    ),
    _capability(
        "radfrac",
        "unit.distillation_column",
        ("TOTAL_STAGES", "FEED_STAGE"),
        domains=("material", "energy"),
        notes="Alias contract; native mapping requires runtime verification.",
    ),
    _capability(
        "reactor_cstr",
        "unit.reactor_cstr",
        ("VOLUME", "RESIDENCE_TIME", "CONVERSION"),
        domains=("material", "energy"),
        notes="Native mapping requires runtime verification.",
    ),
    _capability(
        "reactor_pfr",
        "unit.reactor_pfr",
        ("VOLUME", "RESIDENCE_TIME", "CONVERSION"),
        domains=("material", "energy"),
        notes="Native mapping requires runtime verification.",
    ),
    _capability(
        "reactor_equilibrium",
        "unit.reactor_equilibrium",
        ("VOLUME", "RESIDENCE_TIME", "CONVERSION"),
        domains=("material", "energy"),
        notes="Native mapping requires runtime verification.",
    ),
    _capability(
        "reactor_gibbs",
        "unit.reactor_gibbs",
        ("VOLUME", "RESIDENCE_TIME", "CONVERSION"),
        domains=("material", "energy"),
        notes="Native mapping requires runtime verification.",
    ),
    _capability(
        "reactor_yield",
        "unit.reactor_yield",
        ("VOLUME", "RESIDENCE_TIME", "CONVERSION"),
        domains=("material", "energy"),
        notes="Native mapping requires runtime verification.",
    ),
)

_HYSYS_EQUIPMENT = tuple(
    _capability(
        item.ir_kind,
        item.adapter_key,
        item.supported_parameter_names,
        domains=item.required_port_domains,
        state=item.state,
        notes=(
            "Project-owned adapter contract only; native HYSYS object and port mapping "
            "requires target-runtime verification."
        ),
    )
    for item in _ASPEN_PLUS_EQUIPMENT
)


def _offline_profile(
    simulator: SimulatorFamily,
    version: str,
) -> SimulatorCapabilityProfile:
    extensions: tuple[str, ...]
    equipment: tuple[EquipmentCapability, ...]
    if simulator == "aspen_plus":
        extensions = (".bkp", ".apw", ".apwz")
        equipment = _ASPEN_PLUS_EQUIPMENT
        adapter_contract = "aspenops.aspen-plus-native-builder/v1"
    else:
        extensions = (".hsc",)
        equipment = _HYSYS_EQUIPMENT
        adapter_contract = "aspenops.hysys-native-builder/v1"
    return SimulatorCapabilityProfile(
        profile_id=f"{simulator}-{version}-offline-contract-v1",
        simulator=simulator,
        marketing_version=version,
        qualification="OFFLINE_CONTRACT_ONLY",
        adapter_contract=adapter_contract,
        model_extensions=extensions,
        supported_stream_kinds=_COMMON_STREAM_KINDS,
        equipment=equipment,
        source_boundary=(
            "This built-in profile is an offline AspenOps contract. It does not assert that "
            "vendor-native object names, COM methods, ports or save/reopen behavior have been "
            "verified on the requested commercial runtime."
        ),
    )


_BUILTIN_PROFILES = {
    (simulator, version): _offline_profile(cast(SimulatorFamily, simulator), version)
    for simulator in sorted(_SUPPORTED_SIMULATORS)
    for version in sorted(_SUPPORTED_VERSIONS)
}


def get_builtin_capability_profile(
    simulator: str,
    marketing_version: str,
) -> SimulatorCapabilityProfile:
    key = (simulator.strip().casefold(), marketing_version.strip())
    try:
        return _BUILTIN_PROFILES[key]
    except KeyError as exc:
        raise KeyError(
            f"No built-in capability profile for simulator={key[0]!r}, version={key[1]!r}"
        ) from exc


def list_builtin_capability_profiles() -> tuple[SimulatorCapabilityProfile, ...]:
    return tuple(_BUILTIN_PROFILES[key] for key in sorted(_BUILTIN_PROFILES))
