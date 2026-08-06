from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "write_delivery_qualification.py"
SHA = "a" * 40


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("write_delivery_qualification", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _evidence(tmp_path: Path, *, coverage: float = 95.25) -> tuple[Path, Path, Path]:
    coverage_path = tmp_path / "coverage.json"
    coverage_path.write_text(
        json.dumps({"totals": {"percent_covered": coverage}}), encoding="utf-8"
    )
    junit_path = tmp_path / "junit.xml"
    junit_path.write_text(
        '<testsuite tests="12" failures="0" errors="0" skipped="1"/>',
        encoding="utf-8",
    )
    delivery_path = tmp_path / "delivery.json"
    delivery_path.write_text(
        json.dumps({"schema": "aspenops.delivery-acceptance/v1", "status": "PASS"}),
        encoding="utf-8",
    )
    return coverage_path, junit_path, delivery_path


def test_writer_binds_test_coverage_and_delivery_evidence(tmp_path: Path) -> None:
    module = _load_module()
    coverage, junit, delivery = _evidence(tmp_path)
    output = tmp_path / "qualification.json"
    evidence = module.write_delivery_qualification(
        coverage_path=coverage,
        junit_path=junit,
        delivery_report_path=delivery,
        output_path=output,
        source_sha=SHA,
        qualified_tree_sha="b" * 40,
        run_id=123,
    )
    assert evidence["status"] == "PASS"
    assert evidence["passed"] == 11
    assert evidence["skipped"] == 1
    assert evidence["branch_coverage_percent"] == 95.25
    assert evidence["real_aspen_status"] == "PENDING_REAL_ASPEN_CERTIFICATION"
    assert json.loads(output.read_text(encoding="utf-8")) == evidence


def test_writer_fails_closed_on_low_coverage_and_failed_delivery(tmp_path: Path) -> None:
    module = _load_module()
    coverage, junit, delivery = _evidence(tmp_path, coverage=94.99)
    with pytest.raises(module.DeliveryQualificationError, match="at least 95"):
        module.write_delivery_qualification(
            coverage_path=coverage,
            junit_path=junit,
            delivery_report_path=delivery,
            output_path=tmp_path / "low.json",
            source_sha=SHA,
            qualified_tree_sha="b" * 40,
            run_id=1,
        )

    coverage.write_text(json.dumps({"totals": {"percent_covered": 95.0}}), encoding="utf-8")
    delivery.write_text(json.dumps({"status": "FAIL"}), encoding="utf-8")
    with pytest.raises(module.DeliveryQualificationError, match="must report PASS"):
        module.write_delivery_qualification(
            coverage_path=coverage,
            junit_path=junit,
            delivery_report_path=delivery,
            output_path=tmp_path / "delivery-fail.json",
            source_sha=SHA,
            qualified_tree_sha="b" * 40,
            run_id=1,
        )


def test_writer_rejects_nonstandard_json_and_invalid_identity(tmp_path: Path) -> None:
    module = _load_module()
    coverage, junit, delivery = _evidence(tmp_path)
    coverage.write_text('{"totals":{"percent_covered":NaN}}', encoding="utf-8")
    with pytest.raises(module.DeliveryQualificationError, match="Non-standard JSON"):
        module.write_delivery_qualification(
            coverage_path=coverage,
            junit_path=junit,
            delivery_report_path=delivery,
            output_path=tmp_path / "nan.json",
            source_sha=SHA,
            qualified_tree_sha="b" * 40,
            run_id=1,
        )
