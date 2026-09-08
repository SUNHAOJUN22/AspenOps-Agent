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


def _evidence(
    tmp_path: Path,
    *,
    coverage: float = 95.25,
    tests: int = 1204,
    failures: int = 0,
    errors: int = 0,
    skipped: int = 0,
) -> tuple[Path, Path, Path]:
    coverage_path = tmp_path / "coverage.json"
    coverage_path.write_text(
        json.dumps({"totals": {"percent_covered": coverage}}),
        encoding="utf-8",
    )
    junit_path = tmp_path / "junit.xml"
    junit_path.write_text(
        (
            f'<testsuite tests="{tests}" failures="{failures}" '
            f'errors="{errors}" skipped="{skipped}"/>'
        ),
        encoding="utf-8",
    )
    delivery_path = tmp_path / "delivery.json"
    delivery_path.write_text(
        json.dumps(
            {
                "schema": "aspenops.delivery-acceptance/v1",
                "status": "PASS",
                "issues": [],
                "baseline_qualification": {"real_aspen_status": "PENDING_REAL_ASPEN_CERTIFICATION"},
            }
        ),
        encoding="utf-8",
    )
    return coverage_path, junit_path, delivery_path


def test_writer_binds_full_suite_coverage_and_delivery_evidence(tmp_path: Path) -> None:
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
    assert evidence["passed"] == 1204
    assert evidence["skipped"] == 0
    assert evidence["branch_coverage_percent"] == 95.25
    assert evidence["delivery_report_schema"] == "aspenops.delivery-acceptance/v1"
    assert evidence["real_aspen_status"] == "PENDING_REAL_ASPEN_CERTIFICATION"
    assert json.loads(output.read_text(encoding="utf-8")) == evidence


@pytest.mark.parametrize(
    ("coverage", "match"),
    [
        (94.99, "at least 95"),
        (float("inf"), "Non-standard JSON"),
    ],
)
def test_writer_fails_closed_on_invalid_coverage(
    tmp_path: Path,
    coverage: float,
    match: str,
) -> None:
    module = _load_module()
    coverage_path, junit, delivery = _evidence(tmp_path, coverage=coverage)
    with pytest.raises(module.DeliveryQualificationError, match=match):
        module.write_delivery_qualification(
            coverage_path=coverage_path,
            junit_path=junit,
            delivery_report_path=delivery,
            output_path=tmp_path / "invalid.json",
            source_sha=SHA,
            qualified_tree_sha="b" * 40,
            run_id=1,
        )


def test_writer_rejects_failed_spoofed_or_ambiguous_delivery_report(tmp_path: Path) -> None:
    module = _load_module()
    coverage, junit, delivery = _evidence(tmp_path)

    delivery.write_text(json.dumps({"status": "FAIL"}), encoding="utf-8")
    with pytest.raises(module.DeliveryQualificationError, match="schema"):
        module.write_delivery_qualification(
            coverage_path=coverage,
            junit_path=junit,
            delivery_report_path=delivery,
            output_path=tmp_path / "delivery-fail.json",
            source_sha=SHA,
            qualified_tree_sha="b" * 40,
            run_id=1,
        )

    _, _, delivery = _evidence(tmp_path)
    payload = json.loads(delivery.read_text(encoding="utf-8"))
    payload["issues"] = [{"code": "fake"}]
    delivery.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(module.DeliveryQualificationError, match="zero issues"):
        module.write_delivery_qualification(
            coverage_path=coverage,
            junit_path=junit,
            delivery_report_path=delivery,
            output_path=tmp_path / "issues.json",
            source_sha=SHA,
            qualified_tree_sha="b" * 40,
            run_id=1,
        )

    _, _, delivery = _evidence(tmp_path)
    payload = json.loads(delivery.read_text(encoding="utf-8"))
    payload["baseline_qualification"]["real_aspen_status"] = "REAL_ASPEN_CERTIFIED"
    delivery.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(module.DeliveryQualificationError, match="external Aspen"):
        module.write_delivery_qualification(
            coverage_path=coverage,
            junit_path=junit,
            delivery_report_path=delivery,
            output_path=tmp_path / "certified.json",
            source_sha=SHA,
            qualified_tree_sha="b" * 40,
            run_id=1,
        )


@pytest.mark.parametrize(
    ("tests", "skipped", "match"),
    [
        (1199, 0, "at least 1200"),
        (1204, 1, "must not skip"),
    ],
)
def test_writer_requires_complete_acceptance_sized_suite(
    tmp_path: Path,
    tests: int,
    skipped: int,
    match: str,
) -> None:
    module = _load_module()
    coverage, junit, delivery = _evidence(
        tmp_path,
        tests=tests,
        skipped=skipped,
    )
    with pytest.raises(module.DeliveryQualificationError, match=match):
        module.write_delivery_qualification(
            coverage_path=coverage,
            junit_path=junit,
            delivery_report_path=delivery,
            output_path=tmp_path / "suite.json",
            source_sha=SHA,
            qualified_tree_sha="b" * 40,
            run_id=1,
        )


@pytest.mark.parametrize(
    ("source_sha", "tree_sha", "run_id", "match"),
    [
        ("g" * 40, "b" * 40, 1, "source_sha"),
        ("a" * 40, "B" * 40, 1, "qualified_tree_sha"),
        ("a" * 39, "b" * 40, 1, "source_sha"),
        ("a" * 40, "b" * 40, True, "positive integer"),
    ],
)
def test_writer_rejects_invalid_identity(
    tmp_path: Path,
    source_sha: str,
    tree_sha: str,
    run_id: int,
    match: str,
) -> None:
    module = _load_module()
    coverage, junit, delivery = _evidence(tmp_path)
    with pytest.raises(module.DeliveryQualificationError, match=match):
        module.write_delivery_qualification(
            coverage_path=coverage,
            junit_path=junit,
            delivery_report_path=delivery,
            output_path=tmp_path / "identity.json",
            source_sha=source_sha,
            qualified_tree_sha=tree_sha,
            run_id=run_id,
        )


def test_writer_rejects_nonstandard_json(tmp_path: Path) -> None:
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
