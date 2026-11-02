from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "verify_delivery.py"


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("verify_delivery", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_repository_delivery_contract_passes() -> None:
    module = _load_module()
    report = module.verify_delivery(ROOT)
    assert report["schema"] == "aspenops.delivery-acceptance/v1"
    assert report["status"] == "PASS"
    assert report["visual_asset_count"] == 29
    assert report["required_file_count"] >= 16
    assert report["baseline_qualification"]["passed"] >= 1200
    assert report["baseline_qualification"]["branch_coverage_percent"] >= 95.0
    assert report["baseline_qualification"]["real_aspen_status"] == (
        "PENDING_REAL_ASPEN_CERTIFICATION"
    )
    assert report["current_qualification"]["required"] is False
    assert report["issues"] == []


def test_strict_json_rejects_duplicates_and_nonfinite(tmp_path: Path) -> None:
    module = _load_module()
    duplicate = tmp_path / "duplicate.json"
    duplicate.write_text('{"status":"PASS","status":"FAIL"}', encoding="utf-8")
    with pytest.raises(module.DeliveryVerificationError, match="Duplicate JSON key"):
        module.load_strict_json(duplicate)

    nonfinite = tmp_path / "nonfinite.json"
    nonfinite.write_text('{"coverage":NaN}', encoding="utf-8")
    with pytest.raises(module.DeliveryVerificationError, match="Non-standard JSON"):
        module.load_strict_json(nonfinite)


def test_temporary_artifact_detection(tmp_path: Path) -> None:
    module = _load_module()
    workflow_dir = tmp_path / ".github" / "workflows"
    docs_dir = tmp_path / "docs"
    scripts_dir = tmp_path / "scripts"
    workflow_dir.mkdir(parents=True)
    docs_dir.mkdir()
    scripts_dir.mkdir()
    (workflow_dir / "acceptance-finalizer-once.yml").write_text("name: temporary\n")
    (docs_dir / "ACCEPTANCE_RUNNING.json").write_text("{}\n")
    (scripts_dir / "normal.py").write_text("pass\n")
    assert module.temporary_artifacts(tmp_path) == [
        ".github/workflows/acceptance-finalizer-once.yml",
        "docs/ACCEPTANCE_RUNNING.json",
    ]


def test_current_qualification_is_optional_or_fail_closed(tmp_path: Path) -> None:
    module = _load_module()
    issues: list[dict[str, str]] = []
    assert module._check_current_qualification(tmp_path, issues, required=False) is None
    assert issues == []

    assert module._check_current_qualification(tmp_path, issues, required=True) is None
    assert issues[-1]["code"] == "current_qualification_missing"

    path = tmp_path / "docs" / "DELIVERY_QUALIFICATION.json"
    path.parent.mkdir(parents=True)
    path.write_text('{"schema":"wrong","status":"PASS"}\n', encoding="utf-8")
    malformed_issues: list[dict[str, str]] = []
    evidence = module._check_current_qualification(
        tmp_path,
        malformed_issues,
        required=False,
    )
    assert evidence is not None
    assert any(
        issue["code"] == "current_qualification_field_mismatch" for issue in malformed_issues
    )


def test_current_qualification_binds_expected_git_identity(tmp_path: Path) -> None:
    module = _load_module()
    path = tmp_path / "docs" / "DELIVERY_QUALIFICATION.json"
    path.parent.mkdir(parents=True)
    source_sha = "a" * 40
    tree_sha = "b" * 40
    path.write_text(
        json.dumps(
            {
                "schema": "aspenops.delivery-qualification/v2",
                "status": "PASS",
                "failed": 0,
                "errors": 0,
                "skipped": 0,
                "passed": 1204,
                "branch_coverage_percent": 95.2,
                "reverse_order_gate": "PASS",
                "real_aspen_status": "PENDING_REAL_ASPEN_CERTIFICATION",
                "validated_source_parent": source_sha,
                "qualified_content_tree_sha": tree_sha,
            }
        ),
        encoding="utf-8",
    )
    issues: list[dict[str, str]] = []
    module._check_current_qualification(
        tmp_path,
        issues,
        required=True,
        expected_source_sha=source_sha,
        expected_tree_sha=tree_sha,
    )
    assert issues == []

    mismatch: list[dict[str, str]] = []
    module._check_current_qualification(
        tmp_path,
        mismatch,
        required=True,
        expected_source_sha="c" * 40,
        expected_tree_sha="d" * 40,
    )
    assert {item["code"] for item in mismatch} >= {
        "current_qualification_source_mismatch",
        "current_qualification_tree_mismatch",
    }


def test_cli_writes_json_report(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    module = _load_module()
    output = tmp_path / "delivery.json"
    assert module.main(["--root", str(ROOT), "--output", str(output)]) == 0
    written = json.loads(output.read_text(encoding="utf-8"))
    printed = json.loads(capsys.readouterr().out)
    assert written == printed
    assert written["schema"] == "aspenops.delivery-acceptance/v1"


@pytest.mark.parametrize(
    "changed",
    [
        '<svg viewBox="0 0 10 10" role="img" lang="en"><title>Missing desc</title></svg>',
        '<svg viewBox="0 0 10 10" role="img" lang="zh-CN"><title>A</title><desc>B</desc></svg>',
        '<svg viewBox="0 0 10 10" role="img" lang="en"><title>A</title><desc>\ufffd</desc></svg>',
        '<svg viewBox="0 0 10 10" role="img" lang="en">'
        "<title>A</title><desc>B</desc><script/></svg>",
        '<svg viewBox="0 0 10 10" role="img" lang="en" onload="bad()">'
        "<title>A</title><desc>B</desc></svg>",
        '<svg viewBox="0 0 10 10" role="img" lang="en"><title>A</title><desc>B</desc><image href="https://example.invalid/a.png"/></svg>',
        '<svg viewBox="0 0 10 10" role="img" lang="en"><title>A</title><desc>B</desc>'
        '<image href="data:image/svg+xml;base64,PHN2Zz4="/></svg>',
        '<svg viewBox="0 0 10 10" role="img" lang="en"><title>A</title><desc>B</desc><style>.a{fill:url(https://example.invalid/a)}</style></svg>',
    ],
)
def test_localized_art_rejects_wrong_language_corrupt_text_and_active_resources(
    tmp_path: Path, changed: str
) -> None:
    module = _load_module()
    art = tmp_path / "hero.en.svg"
    art.write_text(changed, encoding="utf-8")
    issues: list[dict[str, str]] = []
    module._check_localized_visual(art, "en", issues)
    assert [issue["code"] for issue in issues] == ["localized_visual_invalid"]


def test_localized_art_accepts_self_contained_vector_and_raster(tmp_path: Path) -> None:
    module = _load_module()
    art = tmp_path / "hero.zh-CN.svg"
    art.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10" role="img" lang="zh-CN">'
        "<title>中文概念图</title><desc>控制面示意，不是实测结果。</desc>"
        '<defs><linearGradient id="g"/></defs><rect style="fill:url(#g)"/>'
        '<image href="data:image/png;base64,iVBORw0KGgo="/>'
        "</svg>",
        encoding="utf-8",
    )
    issues: list[dict[str, str]] = []
    module._check_localized_visual(art, "zh-CN", issues)
    assert issues == []
