from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class TemplateEquipment:
    id: str
    kind: str
    display_name: str

    def to_dict(self) -> dict[str, str]:
        return {"id": self.id, "kind": self.kind, "display_name": self.display_name}


@dataclass(frozen=True, slots=True)
class TemplateConnection:
    id: str
    source: str
    target: str
    kind: str = "material"

    def to_dict(self) -> dict[str, str]:
        return {
            "id": self.id,
            "source": self.source,
            "target": self.target,
            "kind": self.kind,
        }


@dataclass(frozen=True, slots=True)
class PlantTemplate:
    id: str
    title: str
    description: str
    simulators: tuple[str, ...]
    versions: tuple[str, ...]
    equipment: tuple[TemplateEquipment, ...]
    connections: tuple[TemplateConnection, ...]
    required_inputs: tuple[str, ...]
    balance_scopes: tuple[str, ...]
    initialization_sequence: tuple[str, ...]
    unsupported_conditions: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "simulators": list(self.simulators),
            "versions": list(self.versions),
            "equipment": [item.to_dict() for item in self.equipment],
            "connections": [item.to_dict() for item in self.connections],
            "required_inputs": list(self.required_inputs),
            "balance_scopes": list(self.balance_scopes),
            "initialization_sequence": list(self.initialization_sequence),
            "unsupported_conditions": list(self.unsupported_conditions),
        }

    def digest(self) -> str:
        payload = json.dumps(
            self.to_dict(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True, slots=True)
class TemplateInstantiationPlan:
    template_id: str
    template_hash: str
    target_simulator: str
    target_version: str
    status: str
    equipment: tuple[TemplateEquipment, ...]
    connections: tuple[TemplateConnection, ...]
    unresolved_inputs: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "template_id": self.template_id,
            "template_hash": self.template_hash,
            "target_simulator": self.target_simulator,
            "target_version": self.target_version,
            "status": self.status,
            "equipment": [item.to_dict() for item in self.equipment],
            "connections": [item.to_dict() for item in self.connections],
            "unresolved_inputs": list(self.unresolved_inputs),
        }


def _equipment(*items: tuple[str, str, str]) -> tuple[TemplateEquipment, ...]:
    return tuple(TemplateEquipment(*item) for item in items)


def _connections(*items: tuple[str, str, str, str]) -> tuple[TemplateConnection, ...]:
    return tuple(TemplateConnection(*item) for item in items)


_COMMON_INPUTS = (
    "approved component list and simulator identifiers",
    "approved property method and version scope",
    "feed flow, composition, temperature and pressure",
    "product specifications and engineering tolerances",
)
_COMMON_BALANCES = ("overall mass", "component", "energy when available")

_TEMPLATES = (
    PlantTemplate(
        id="HEATER_FLASH",
        title="Heater–Flash separation",
        description="Single feed heating followed by equilibrium phase separation.",
        simulators=("aspen_plus", "hysys"),
        versions=("14", "15"),
        equipment=_equipment(
            ("FEED_001", "feed", "Feed"),
            ("HTR_001", "heater", "Heater"),
            ("SEP_001", "flash2", "Flash separator"),
            ("VAP_PROD_001", "product", "Vapor product"),
            ("LIQ_PROD_001", "product", "Liquid product"),
        ),
        connections=_connections(
            ("S001", "FEED_001", "HTR_001", "material"),
            ("S002", "HTR_001", "SEP_001", "material"),
            ("S003", "SEP_001", "VAP_PROD_001", "material"),
            ("S004", "SEP_001", "LIQ_PROD_001", "material"),
        ),
        required_inputs=(*_COMMON_INPUTS, "heater outlet temperature or duty", "flash pressure"),
        balance_scopes=_COMMON_BALANCES,
        initialization_sequence=("feed", "heater", "flash", "products"),
        unsupported_conditions=("reactive separation", "three-solid-phase equilibrium"),
    ),
    PlantTemplate(
        id="MIXER_HEATER_SEPARATOR",
        title="Mixer–Heater–Separator",
        description="Multiple feeds are mixed, thermally conditioned and phase separated.",
        simulators=("aspen_plus", "hysys"),
        versions=("14", "15"),
        equipment=_equipment(
            ("FEED_001", "feed", "Feed 1"),
            ("FEED_002", "feed", "Feed 2"),
            ("MIX_001", "mixer", "Mixer"),
            ("HTR_001", "heater", "Heater"),
            ("SEP_001", "separator", "Separator"),
            ("VAP_PROD_001", "product", "Vapor product"),
            ("LIQ_PROD_001", "product", "Liquid product"),
        ),
        connections=_connections(
            ("S001", "FEED_001", "MIX_001", "material"),
            ("S002", "FEED_002", "MIX_001", "material"),
            ("S003", "MIX_001", "HTR_001", "material"),
            ("S004", "HTR_001", "SEP_001", "material"),
            ("S005", "SEP_001", "VAP_PROD_001", "material"),
            ("S006", "SEP_001", "LIQ_PROD_001", "material"),
        ),
        required_inputs=(*_COMMON_INPUTS, "mixer pressure rule", "thermal specification"),
        balance_scopes=_COMMON_BALANCES,
        initialization_sequence=("feeds", "mixer", "heater", "separator"),
        unsupported_conditions=("reaction in mixer", "unapproved feed pressure reconciliation"),
    ),
    PlantTemplate(
        id="COMPRESSION_COOLING_SEPARATION",
        title="Compression–Cooling–Separation",
        description="Gas compression followed by cooling and condensate separation.",
        simulators=("aspen_plus", "hysys"),
        versions=("14", "15"),
        equipment=_equipment(
            ("FEED_001", "feed", "Gas feed"),
            ("COMP_001", "compressor", "Compressor"),
            ("CLR_001", "cooler", "Aftercooler"),
            ("SEP_001", "separator", "Knockout drum"),
            ("GAS_PROD_001", "product", "Gas product"),
            ("LIQ_PROD_001", "product", "Condensate"),
        ),
        connections=_connections(
            ("S001", "FEED_001", "COMP_001", "material"),
            ("S002", "COMP_001", "CLR_001", "material"),
            ("S003", "CLR_001", "SEP_001", "material"),
            ("S004", "SEP_001", "GAS_PROD_001", "material"),
            ("S005", "SEP_001", "LIQ_PROD_001", "material"),
        ),
        required_inputs=(*_COMMON_INPUTS, "discharge pressure", "compressor efficiency", "cooler outlet temperature"),
        balance_scopes=(*_COMMON_BALANCES, "shaft work"),
        initialization_sequence=("feed", "compressor", "cooler", "separator"),
        unsupported_conditions=("liquid-dominant compressor feed", "surge/control dynamics"),
    ),
    PlantTemplate(
        id="REACTOR_COOLER_FLASH_RECYCLE",
        title="Reactor–Cooler–Flash–Recycle",
        description="Reaction and separation loop with an explicit tear stream and recycle contract.",
        simulators=("aspen_plus", "hysys"),
        versions=("14", "15"),
        equipment=_equipment(
            ("FEED_001", "feed", "Fresh feed"),
            ("MIX_001", "mixer", "Feed mixer"),
            ("RCTR_001", "reactor_cstr", "Reactor"),
            ("CLR_001", "cooler", "Reactor cooler"),
            ("SEP_001", "flash2", "Product separator"),
            ("PROD_001", "product", "Product"),
            ("RECYCLE_001", "mixer", "Recycle return"),
        ),
        connections=_connections(
            ("S001", "FEED_001", "MIX_001", "material"),
            ("TEAR_001", "RECYCLE_001", "MIX_001", "material"),
            ("S002", "MIX_001", "RCTR_001", "material"),
            ("S003", "RCTR_001", "CLR_001", "material"),
            ("S004", "CLR_001", "SEP_001", "material"),
            ("S005", "SEP_001", "PROD_001", "material"),
            ("S006", "SEP_001", "RECYCLE_001", "material"),
        ),
        required_inputs=(
            *_COMMON_INPUTS,
            "approved reaction definition",
            "reactor volume or residence time",
            "tear initial values and convergence tolerances",
        ),
        balance_scopes=(*_COMMON_BALANCES, "elemental reaction balance", "recycle boundary"),
        initialization_sequence=("fresh feed", "open-loop reaction", "separator", "tear initialization", "recycle"),
        unsupported_conditions=("unapproved kinetics", "multiple coupled recycles without staged plan"),
    ),
    PlantTemplate(
        id="TWO_COLUMN_SEQUENCE",
        title="Two-column distillation sequence",
        description="Two serial columns for ternary or multicomponent fractionation.",
        simulators=("aspen_plus", "hysys"),
        versions=("14", "15"),
        equipment=_equipment(
            ("FEED_001", "feed", "Feed"),
            ("COL_001", "distillation_column", "Column 1"),
            ("COL_002", "distillation_column", "Column 2"),
            ("DIST_001", "product", "Light product"),
            ("DIST_002", "product", "Intermediate product"),
            ("BTM_002", "product", "Heavy product"),
        ),
        connections=_connections(
            ("S001", "FEED_001", "COL_001", "material"),
            ("S002", "COL_001", "DIST_001", "material"),
            ("S003", "COL_001", "COL_002", "material"),
            ("S004", "COL_002", "DIST_002", "material"),
            ("S005", "COL_002", "BTM_002", "material"),
        ),
        required_inputs=(
            *_COMMON_INPUTS,
            "stage counts and feed stages",
            "condenser/reboiler types",
            "two independent specifications per column",
            "column pressure profiles",
        ),
        balance_scopes=(*_COMMON_BALANCES, "column 1", "column 2"),
        initialization_sequence=("feed", "shortcut estimates", "column 1", "column 2", "full sequence"),
        unsupported_conditions=("reactive distillation", "unapproved azeotropic entrainer"),
    ),
    PlantTemplate(
        id="ABSORBER_REGENERATOR",
        title="Absorber–Regenerator",
        description="Solvent absorption followed by thermal regeneration and recycle.",
        simulators=("aspen_plus", "hysys"),
        versions=("14", "15"),
        equipment=_equipment(
            ("GAS_FEED_001", "feed", "Gas feed"),
            ("SOLV_FEED_001", "feed", "Solvent makeup"),
            ("ABS_001", "distillation_column", "Absorber"),
            ("REG_001", "distillation_column", "Regenerator"),
            ("GAS_PROD_001", "product", "Treated gas"),
            ("ACID_PROD_001", "product", "Regenerator overhead"),
        ),
        connections=_connections(
            ("S001", "GAS_FEED_001", "ABS_001", "material"),
            ("S002", "SOLV_FEED_001", "ABS_001", "material"),
            ("S003", "ABS_001", "GAS_PROD_001", "material"),
            ("S004", "ABS_001", "REG_001", "material"),
            ("S005", "REG_001", "ACID_PROD_001", "material"),
            ("TEAR_001", "REG_001", "ABS_001", "material"),
        ),
        required_inputs=(*_COMMON_INPUTS, "solvent loading model", "absorber and regenerator specifications", "solvent recycle initialization"),
        balance_scopes=(*_COMMON_BALANCES, "absorber", "regenerator", "solvent loop"),
        initialization_sequence=("open solvent loop", "absorber", "regenerator", "solvent recycle"),
        unsupported_conditions=("electrolyte chemistry without approved model", "solvent degradation chemistry"),
    ),
    PlantTemplate(
        id="GAS_DEHYDRATION",
        title="Gas dehydration",
        description="Contacting and regeneration skeleton for a dehydration solvent loop.",
        simulators=("hysys", "aspen_plus"),
        versions=("14", "15"),
        equipment=_equipment(
            ("WET_GAS_001", "feed", "Wet gas"),
            ("CONTACTOR_001", "distillation_column", "Contactor"),
            ("DRY_GAS_001", "product", "Dry gas"),
            ("REGEN_001", "distillation_column", "Regenerator"),
            ("WATER_PROD_001", "product", "Water-rich overhead"),
        ),
        connections=_connections(
            ("S001", "WET_GAS_001", "CONTACTOR_001", "material"),
            ("S002", "CONTACTOR_001", "DRY_GAS_001", "material"),
            ("S003", "CONTACTOR_001", "REGEN_001", "material"),
            ("S004", "REGEN_001", "WATER_PROD_001", "material"),
            ("TEAR_001", "REGEN_001", "CONTACTOR_001", "material"),
        ),
        required_inputs=(*_COMMON_INPUTS, "solvent identity and purity", "water specification", "solvent circulation rate", "recycle initialization"),
        balance_scopes=(*_COMMON_BALANCES, "water", "solvent loop"),
        initialization_sequence=("wet gas", "open solvent loop", "contactor", "regenerator", "recycle"),
        unsupported_conditions=("hydrate formation assessment", "solvent degradation"),
    ),
    PlantTemplate(
        id="DISTILLATION_COLUMN",
        title="Distillation column",
        description="Single rigorous column with condenser, reboiler and two products.",
        simulators=("aspen_plus", "hysys"),
        versions=("14", "15"),
        equipment=_equipment(
            ("FEED_001", "feed", "Feed"),
            ("COL_001", "distillation_column", "Distillation column"),
            ("DIST_001", "product", "Distillate"),
            ("BTM_001", "product", "Bottoms"),
        ),
        connections=_connections(
            ("S001", "FEED_001", "COL_001", "material"),
            ("S002", "COL_001", "DIST_001", "material"),
            ("S003", "COL_001", "BTM_001", "material"),
        ),
        required_inputs=(*_COMMON_INPUTS, "stage count", "feed stage", "condenser and reboiler types", "two independent column specifications", "pressure profile"),
        balance_scopes=(*_COMMON_BALANCES, "column"),
        initialization_sequence=("feed flash", "shortcut estimate", "rigorous column"),
        unsupported_conditions=("reactive distillation", "unapproved rate-based model"),
    ),
    PlantTemplate(
        id="REACTION_SEPARATION_RECYCLE",
        title="Reaction–Separation–Recycle",
        description="Generic reaction and product-separation loop with explicit recycle governance.",
        simulators=("aspen_plus", "hysys"),
        versions=("14", "15"),
        equipment=_equipment(
            ("FEED_001", "feed", "Fresh feed"),
            ("MIX_001", "mixer", "Feed mixer"),
            ("RCTR_001", "reactor_pfr", "Reactor"),
            ("SEP_001", "separator", "Separator"),
            ("PROD_001", "product", "Product"),
            ("RECYCLE_001", "mixer", "Recycle return"),
        ),
        connections=_connections(
            ("S001", "FEED_001", "MIX_001", "material"),
            ("TEAR_001", "RECYCLE_001", "MIX_001", "material"),
            ("S002", "MIX_001", "RCTR_001", "material"),
            ("S003", "RCTR_001", "SEP_001", "material"),
            ("S004", "SEP_001", "PROD_001", "material"),
            ("S005", "SEP_001", "RECYCLE_001", "material"),
        ),
        required_inputs=(*_COMMON_INPUTS, "approved reaction model", "separator specifications", "purge policy when required", "tear initialization"),
        balance_scopes=(*_COMMON_BALANCES, "elemental reaction balance", "recycle boundary"),
        initialization_sequence=("fresh feed", "open-loop reactor", "separator", "tear values", "recycle"),
        unsupported_conditions=("unapproved reaction mechanism", "uncontrolled inert accumulation"),
    ),
    PlantTemplate(
        id="HYSYS_NATURAL_GAS_PRETREATMENT",
        title="HYSYS natural-gas pretreatment",
        description="Inlet separation, compression/cooling and liquid removal for a HYSYS gas case.",
        simulators=("hysys",),
        versions=("14", "15"),
        equipment=_equipment(
            ("FEED_001", "feed", "Raw gas"),
            ("INLET_SEP_001", "separator", "Inlet separator"),
            ("COMP_001", "compressor", "Compressor"),
            ("CLR_001", "cooler", "Aftercooler"),
            ("KO_001", "separator", "Knockout drum"),
            ("GAS_PROD_001", "product", "Pretreated gas"),
            ("LIQ_PROD_001", "product", "Separated liquid"),
        ),
        connections=_connections(
            ("S001", "FEED_001", "INLET_SEP_001", "material"),
            ("S002", "INLET_SEP_001", "COMP_001", "material"),
            ("S003", "COMP_001", "CLR_001", "material"),
            ("S004", "CLR_001", "KO_001", "material"),
            ("S005", "KO_001", "GAS_PROD_001", "material"),
            ("S006", "INLET_SEP_001", "LIQ_PROD_001", "material"),
        ),
        required_inputs=(*_COMMON_INPUTS, "HYSYS fluid package", "compressor pressure and efficiency", "cooler temperature", "liquid product routing"),
        balance_scopes=(*_COMMON_BALANCES, "inlet separator", "compression train"),
        initialization_sequence=("raw gas", "inlet separator", "compressor", "aftercooler", "knockout drum"),
        unsupported_conditions=("acid-gas treatment", "hydrate control", "dynamic anti-surge controls"),
    ),
)

_TEMPLATE_BY_ID = {item.id: item for item in _TEMPLATES}
if len(_TEMPLATE_BY_ID) != len(_TEMPLATES):
    raise RuntimeError("Plant template IDs must be unique")


def list_plant_templates() -> tuple[PlantTemplate, ...]:
    return _TEMPLATES


def get_plant_template(template_id: str) -> PlantTemplate:
    try:
        return _TEMPLATE_BY_ID[template_id.strip().upper()]
    except KeyError as exc:
        raise KeyError(f"Unknown plant template: {template_id}") from exc


def instantiate_template_plan(
    template_id: str,
    *,
    target_simulator: str,
    target_version: str,
    approved_inputs: tuple[str, ...] = (),
) -> TemplateInstantiationPlan:
    template = get_plant_template(template_id)
    simulator = target_simulator.strip().casefold()
    version = target_version.strip().casefold()
    if simulator not in template.simulators:
        raise ValueError(
            f"Template {template.id} is not available for target simulator {simulator}"
        )
    if version not in template.versions:
        raise ValueError(f"Template {template.id} is not qualified for version {version}")
    approved = {item.strip().casefold() for item in approved_inputs}
    unresolved = tuple(
        item for item in template.required_inputs if item.casefold() not in approved
    )
    status = "PLAN_ONLY" if not unresolved else "NEEDS_ENGINEERING_INPUT"
    return TemplateInstantiationPlan(
        template_id=template.id,
        template_hash=template.digest(),
        target_simulator=simulator,
        target_version=version,
        status=status,
        equipment=template.equipment,
        connections=template.connections,
        unresolved_inputs=unresolved,
    )
