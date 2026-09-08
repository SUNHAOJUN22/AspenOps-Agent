from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

import aspenops_nexus.simulator_capabilities as capabilities
from aspenops_nexus.process_ir_v2 import ProcessDesignIR
from aspenops_nexus.simulator_capabilities import (
    EquipmentCapability,
    SimulatorCapabilityProfile,
    get_builtin_capability_profile,
    list_builtin_capability_profiles,
)

ROOT = Path(__file__).resolve().parents[1]
DESIGN = ROOT / "examples/process-design-v2.example.json"


def load_design() -> ProcessDesignIR:
    value = json.loads(DESIGN.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return ProcessDesignIR.from_dict(value)


def test_builtin_profiles_cover_two_simulators_and_two_versions() -> None:
    profiles = list_builtin_capability_profiles()
    assert {(item.simulator, item.marketing_version) for item in profiles} == {
        ("aspen_plus", "14"),
        ("aspen_plus", "15"),
        ("hysys", "14"),
        ("hysys", "15"),
    }
    assert len({item.profile_id for item in profiles}) == 4
    assert len({item.digest() for item in profiles}) == 4
    assert all(item.qualification == "OFFLINE_CONTRACT_ONLY" for item in profiles)
    assert all(item.executable is False for item in profiles)
    assert all(item.equipment for item in profiles)
    assert all("material" in item.supported_stream_kinds for item in profiles)
    assert all("does not assert" in item.source_boundary for item in profiles)


def test_profile_roundtrip_and_design_match() -> None:
    profile = get_builtin_capability_profile("ASPEN_PLUS", "15")
    restored = SimulatorCapabilityProfile.from_dict(profile.to_dict())
    assert restored == profile
    assert restored.digest() == profile.digest()
    restored.assert_matches_design(load_design())
    by_kind = restored.equipment_by_kind()
    assert by_kind["heater"].adapter_key == "unit.heater"
    assert by_kind["feed"].notes.startswith("Boundary")


def test_hysys_profile_contract_and_extension() -> None:
    profile = get_builtin_capability_profile("hysys", "15")
    assert profile.model_extensions == (".hsc",)
    assert profile.adapter_contract == "aspenops.hysys-native-builder/v1"
    assert "project-owned" in profile.equipment_by_kind()["heater"].notes.casefold()


def test_verified_profile_becomes_executable() -> None:
    profile = get_builtin_capability_profile("aspen_plus", "15")
    verified = replace(profile, qualification="VERIFIED_ON_TARGET_RUNTIME")
    assert verified.executable is True
    revoked = replace(profile, qualification="REVOKED")
    assert revoked.executable is False


def test_profile_rejects_target_mismatch() -> None:
    design = load_design()
    with pytest.raises(ValueError, match="simulator"):
        get_builtin_capability_profile("hysys", "15").assert_matches_design(design)
    with pytest.raises(ValueError, match="version"):
        get_builtin_capability_profile("aspen_plus", "14").assert_matches_design(design)


def test_unknown_builtin_profile_fails_closed() -> None:
    with pytest.raises(KeyError, match="No built-in capability profile"):
        get_builtin_capability_profile("aspen_plus", "13")
    with pytest.raises(KeyError, match="No built-in capability profile"):
        get_builtin_capability_profile("unknown", "15")


def test_equipment_capability_roundtrip() -> None:
    capability = EquipmentCapability.from_dict(
        {
            "ir_kind": "heater",
            "adapter_key": "unit.heater",
            "state": "DECLARED",
            "required_port_domains": ["material", "energy"],
            "supported_parameter_names": ["DUTY"],
            "notes": "test",
        },
        label="capability",
    )
    assert capability.to_dict()["state"] == "DECLARED"
    unsupported = replace(capability, state="UNSUPPORTED")
    assert unsupported.to_dict()["state"] == "UNSUPPORTED"


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {
            "ir_kind": "heater",
            "adapter_key": "unit.heater",
            "state": "BAD",
            "notes": "test",
        },
        {
            "ir_kind": "heater",
            "adapter_key": "unit.heater",
            "state": "DECLARED",
            "notes": "test",
            "bad": True,
        },
        {
            "ir_kind": "heater",
            "adapter_key": "unit.heater",
            "state": "DECLARED",
            "required_port_domains": ["material", "material"],
            "notes": "test",
        },
    ],
)
def test_equipment_capability_rejects_invalid_shapes(payload: Any) -> None:
    with pytest.raises(ValueError):
        EquipmentCapability.from_dict(payload, label="capability")


def valid_profile_dict() -> dict[str, Any]:
    return get_builtin_capability_profile("aspen_plus", "15").to_dict()


@pytest.mark.parametrize(
    "mutate",
    [
        lambda value: value.update({"schema": "other/v1"}),
        lambda value: value.update({"simulator": "unknown"}),
        lambda value: value.update({"marketing_version": "13"}),
        lambda value: value.update({"qualification": "BAD"}),
        lambda value: value.update({"model_extensions": ["bkp"]}),
        lambda value: value.update({"equipment": {}}),
        lambda value: value.update({"bad": True}),
    ],
)
def test_profile_rejects_invalid_shapes(mutate: Callable[[dict[str, Any]], None]) -> None:
    value = valid_profile_dict()
    mutate(value)
    with pytest.raises(ValueError):
        SimulatorCapabilityProfile.from_dict(value)


def test_profile_rejects_duplicate_equipment_kinds_and_streams() -> None:
    value = valid_profile_dict()
    value["equipment"].append(dict(value["equipment"][0]))
    with pytest.raises(ValueError, match="equipment kinds must be unique"):
        SimulatorCapabilityProfile.from_dict(value)

    value = valid_profile_dict()
    value["supported_stream_kinds"].append(value["supported_stream_kinds"][0])
    with pytest.raises(ValueError, match="unique"):
        SimulatorCapabilityProfile.from_dict(value)


def test_internal_helpers_cover_success_and_failure_paths() -> None:
    assert len(capabilities._canonical_hash({"x": 1})) == 64
    assert capabilities._text(" x ", "value") == "x"
    assert capabilities._string_tuple(["a", "b"], "value") == ("a", "b")
    with pytest.raises(ValueError):
        capabilities._text("", "value")
    with pytest.raises(ValueError):
        capabilities._string_tuple("bad", "value")
    with pytest.raises(ValueError):
        capabilities._string_tuple(["a", "a"], "value")
