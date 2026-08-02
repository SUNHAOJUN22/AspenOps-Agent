from __future__ import annotations

import pytest

from aspenops_nexus.plant_templates import (
    get_plant_template,
    instantiate_template_plan,
    list_plant_templates,
)


def test_catalog_contains_ten_governed_templates_with_stable_digests() -> None:
    templates = list_plant_templates()
    assert len(templates) == 10
    assert len({item.id for item in templates}) == 10
    assert all(len(item.digest()) == 64 for item in templates)
    assert all(item.required_inputs for item in templates)
    assert all(item.balance_scopes for item in templates)
    assert all(item.initialization_sequence for item in templates)


def test_template_lookup_is_case_insensitive() -> None:
    assert get_plant_template("heater_flash").id == "HEATER_FLASH"
    with pytest.raises(KeyError, match="Unknown plant template"):
        get_plant_template("unknown")


def test_template_plan_fails_closed_until_inputs_are_approved() -> None:
    template = get_plant_template("HEATER_FLASH")
    pending = instantiate_template_plan(
        template.id,
        target_simulator="aspen_plus",
        target_version="15",
    )
    assert pending.status == "NEEDS_ENGINEERING_INPUT"
    assert pending.unresolved_inputs == template.required_inputs

    approved = instantiate_template_plan(
        template.id,
        target_simulator="aspen_plus",
        target_version="15",
        approved_inputs=template.required_inputs,
    )
    assert approved.status == "PLAN_ONLY"
    assert approved.unresolved_inputs == ()
    assert approved.template_hash == template.digest()


def test_template_plan_rejects_unqualified_simulator_or_version() -> None:
    with pytest.raises(ValueError, match="not available"):
        instantiate_template_plan(
            "HYSYS_NATURAL_GAS_PRETREATMENT",
            target_simulator="aspen_plus",
            target_version="15",
        )
    with pytest.raises(ValueError, match="not qualified"):
        instantiate_template_plan(
            "HEATER_FLASH",
            target_simulator="aspen_plus",
            target_version="13",
        )


def test_template_connections_reference_declared_equipment() -> None:
    for template in list_plant_templates():
        equipment_ids = {item.id for item in template.equipment}
        for connection in template.connections:
            assert connection.source in equipment_ids
            assert connection.target in equipment_ids
            assert connection.source != connection.target
