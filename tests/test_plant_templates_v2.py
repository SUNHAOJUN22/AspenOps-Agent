from __future__ import annotations

import pytest

from aspenops_nexus.plant_templates import (
    get_plant_template,
    instantiate_template_plan,
    list_plant_templates,
)

EXPECTED_IDS = {
    "HEATER_FLASH",
    "MIXER_HEATER_SEPARATOR",
    "COMPRESSION_COOLING_SEPARATION",
    "REACTOR_COOLER_FLASH_RECYCLE",
    "TWO_COLUMN_SEQUENCE",
    "ABSORBER_REGENERATOR",
    "GAS_DEHYDRATION",
    "DISTILLATION_COLUMN",
    "REACTION_SEPARATION_RECYCLE",
    "HYSYS_NATURAL_GAS_PRETREATMENT",
}


def test_template_catalog_contains_required_families_with_unique_digests() -> None:
    templates = list_plant_templates()
    assert {item.id for item in templates} == EXPECTED_IDS
    assert len(templates) == 10
    assert len({item.digest() for item in templates}) == len(templates)
    for template in templates:
        assert template.equipment
        assert template.connections
        assert template.required_inputs
        assert template.balance_scopes
        assert template.initialization_sequence
        assert template.versions == ("14", "15")


def test_template_lookup_is_case_insensitive() -> None:
    template = get_plant_template("heater_flash")
    assert template.id == "HEATER_FLASH"
    assert template.title == "Heater–Flash separation"


def test_template_instantiation_reports_unresolved_engineering_inputs() -> None:
    plan = instantiate_template_plan(
        "HEATER_FLASH",
        target_simulator="aspen_plus",
        target_version="15",
    )
    assert plan.status == "NEEDS_ENGINEERING_INPUT"
    assert plan.unresolved_inputs
    assert plan.template_hash == get_plant_template("HEATER_FLASH").digest()


def test_template_instantiation_can_reach_plan_only_after_all_inputs_are_approved() -> None:
    template = get_plant_template("HEATER_FLASH")
    plan = instantiate_template_plan(
        template.id,
        target_simulator="aspen_plus",
        target_version="15",
        approved_inputs=template.required_inputs,
    )
    assert plan.status == "PLAN_ONLY"
    assert plan.unresolved_inputs == ()
    assert plan.equipment == template.equipment
    assert plan.connections == template.connections


def test_hysys_only_template_rejects_aspen_plus() -> None:
    with pytest.raises(ValueError, match="not available"):
        instantiate_template_plan(
            "HYSYS_NATURAL_GAS_PRETREATMENT",
            target_simulator="aspen_plus",
            target_version="15",
        )


def test_template_rejects_unqualified_version() -> None:
    with pytest.raises(ValueError, match="not qualified"):
        instantiate_template_plan(
            "HEATER_FLASH",
            target_simulator="aspen_plus",
            target_version="13",
        )


def test_unknown_template_fails_closed() -> None:
    with pytest.raises(KeyError, match="Unknown plant template"):
        get_plant_template("does_not_exist")
