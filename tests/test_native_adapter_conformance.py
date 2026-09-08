from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from aspenops_nexus.compilation_plan import CompilationPlan, compile_process_design
from aspenops_nexus.native_adapter_conformance import (
    MANIFEST_SCHEMA,
    NativeAdapterManifest,
    evaluate_native_adapter_conformance,
)
from aspenops_nexus.process_ir_v2 import ProcessDesignIR
from aspenops_nexus.simulator_capabilities import get_builtin_capability_profile

ROOT = Path(__file__).resolve().parents[1]
DESIGN = ROOT / "examples/process-design-v2.example.json"


def plan() -> CompilationPlan:
    raw = json.loads(DESIGN.read_text(encoding="utf-8"))
    design = ProcessDesignIR.from_dict(raw)
    profile = get_builtin_capability_profile("aspen_plus", "15")
    return compile_process_design(design, profile)


def manifest(value: CompilationPlan | None = None) -> NativeAdapterManifest:
    target = value or plan()
    return NativeAdapterManifest(
        profile_id=target.profile_id,
        profile_sha256=target.profile_hash,
        adapter_contract=target.adapter_contract,
        adapter_code_sha256="a" * 64,
        runtime_identity_sha256="b" * 64,
        supported_operations=tuple(sorted({step.operation for step in target.steps})),
        supported_adapter_keys=tuple(sorted({step.adapter_key for step in target.steps})),
        supports_topology_readback=True,
        supports_layout_readback=True,
        supports_save_reopen=True,
        failure_isolation="PRIVATE_CASE_DISCARD",
        source_boundary="Synthetic adapter manifest for deterministic tests.",
    )


def test_manifest_roundtrip_is_strict_and_deterministic() -> None:
    original = manifest()
    restored = NativeAdapterManifest.from_dict(original.to_dict())
    assert restored == original
    assert restored.schema == MANIFEST_SCHEMA
    assert restored.digest() == original.digest()
    assert len(restored.digest()) == 64

    without_schema = original.to_dict()
    without_schema.pop("schema")
    assert NativeAdapterManifest.from_dict(without_schema).schema == MANIFEST_SCHEMA


@pytest.mark.parametrize(
    ("mutation", "match"),
    [
        ({"extra": True}, "unsupported fields"),
        ({"schema": "wrong"}, "Unsupported native adapter manifest schema"),
        ({"profile_sha256": "bad"}, "64-character"),
        ({"supported_operations": []}, "must not be empty"),
        ({"supported_adapter_keys": ["x", "x"]}, "unique values"),
        ({"supports_save_reopen": "true"}, "must be a Boolean"),
        ({"failure_isolation": "NONE"}, "Unsupported failure isolation"),
        ({"source_boundary": ""}, "non-empty string"),
    ],
)
def test_manifest_rejects_invalid_shapes(mutation: dict[str, object], match: str) -> None:
    value = manifest().to_dict()
    value.update(mutation)
    with pytest.raises(ValueError, match=match):
        NativeAdapterManifest.from_dict(value)


def test_manifest_rejects_non_object_and_non_array_values() -> None:
    with pytest.raises(ValueError, match="must be an object"):
        NativeAdapterManifest.from_dict([])

    value = manifest().to_dict()
    value["supported_operations"] = "create_case"
    with pytest.raises(ValueError, match="must be an array"):
        NativeAdapterManifest.from_dict(value)


def test_conformance_success_binds_plan_and_manifest() -> None:
    target = plan()
    declaration = manifest(target)
    report = evaluate_native_adapter_conformance(target, declaration)
    assert report.conformant is True
    assert report.plan_hash == target.digest()
    assert report.manifest_hash == declaration.digest()
    assert report.required_operations == declaration.supported_operations
    assert report.required_adapter_keys == declaration.supported_adapter_keys
    assert report.issues == ()
    assert len(report.digest()) == 64
    assert report.to_dict()["conformant"] is True
    report.assert_conformant()


def test_missing_operation_and_adapter_key_are_reported() -> None:
    target = plan()
    declaration = manifest(target)
    changed = replace(
        declaration,
        supported_operations=declaration.supported_operations[1:],
        supported_adapter_keys=declaration.supported_adapter_keys[1:],
    )
    report = evaluate_native_adapter_conformance(target, changed)
    codes = [item.code for item in report.issues]
    assert report.conformant is False
    assert "operation.missing" in codes
    assert "adapter_key.missing" in codes
    assert all(item.to_dict()["message"] for item in report.issues)
    with pytest.raises(ValueError, match="not conformant"):
        report.assert_conformant()


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("profile_id", "wrong", "identity.profile_id"),
        ("profile_sha256", "0" * 64, "identity.profile_sha256"),
        ("adapter_contract", "wrong", "identity.adapter_contract"),
    ],
)
def test_identity_mismatch_is_reported(field: str, value: str, code: str) -> None:
    target = plan()
    changed = replace(manifest(target), **{field: value})
    report = evaluate_native_adapter_conformance(target, changed)
    assert code in {item.code for item in report.issues}


def test_required_readback_and_save_reopen_features_fail_closed() -> None:
    target = plan()
    changed = replace(
        manifest(target),
        supports_topology_readback=False,
        supports_layout_readback=False,
        supports_save_reopen=False,
    )
    codes = {item.code for item in evaluate_native_adapter_conformance(target, changed).issues}
    assert codes == {
        "persistence.save_reopen_missing",
        "readback.layout_missing",
        "readback.topology_missing",
    }


def test_blocked_plan_is_not_conformant() -> None:
    target = plan()
    blocked = replace(target, status="BLOCKED")
    report = evaluate_native_adapter_conformance(blocked, manifest(blocked))
    assert report.conformant is False
    assert "plan.blocked" in {item.code for item in report.issues}


def test_evaluator_rejects_wrong_object_types_and_invalid_direct_manifest() -> None:
    with pytest.raises(TypeError, match="CompilationPlan"):
        evaluate_native_adapter_conformance(object(), manifest())  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="NativeAdapterManifest"):
        evaluate_native_adapter_conformance(plan(), object())  # type: ignore[arg-type]

    invalid = replace(manifest(), failure_isolation="NONE")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="Unsupported failure isolation"):
        evaluate_native_adapter_conformance(plan(), invalid)
