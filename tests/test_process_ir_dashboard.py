from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

SCRIPT = Path("scripts/render_process_ir_dashboard.py")


def load_module():
    spec = importlib.util.spec_from_file_location("render_process_ir_dashboard", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def report_payload(*, valid: bool = True) -> dict:
    return {
        "schema": "aspenops.flowsheet/v1",
        "name": "Water heating",
        "report": {
            "valid": valid,
            "digest": "a" * 64,
            "counts": {
                "components": 1,
                "units": 3,
                "streams": 2,
                "ports": 4,
                "parameters": 4,
            },
            "issues": []
            if valid
            else [
                {
                    "severity": "error",
                    "code": "stream.unknown_unit",
                    "path": "streams[0].source.unit",
                    "message": "Unknown unit",
                }
            ],
        },
        "backends": [
            {
                "backend": "mock",
                "execution": "available",
                "ir_compiler": "planned",
                "requires_license": False,
            },
            {
                "backend": "aspen_plus",
                "execution": "available",
                "ir_compiler": "planned",
                "requires_license": True,
            },
        ],
        "agent_pipeline": [
            {
                "id": "concept",
                "responsibility": "Generate topology",
                "permitted_output": "aspenops.flowsheet/v1",
            }
        ],
    }


def test_dashboard_renders_self_contained_html_and_svg(tmp_path: Path) -> None:
    module = load_module()
    path = tmp_path / "report.json"
    path.write_text(json.dumps(report_payload()), encoding="utf-8")
    data = module._load_report(path)
    page = module.render_html(data)
    svg = module.render_svg(data)

    assert "VALID" in page
    assert "Backend capability declaration" in page
    assert "No planned compiler is represented as implemented" in page
    assert "fetch(" not in page
    assert "http://" not in page
    assert "https://" not in page
    assert "<svg" in svg
    assert "IR compilers" in svg


def test_invalid_report_renders_invalid_status(tmp_path: Path) -> None:
    module = load_module()
    path = tmp_path / "report.json"
    path.write_text(json.dumps(report_payload(valid=False)), encoding="utf-8")
    data = module._load_report(path)
    assert "INVALID" in module.render_html(data)
    assert "stream.unknown_unit" in module.render_html(data)


def test_malformed_report_fails_closed(tmp_path: Path) -> None:
    module = load_module()
    path = tmp_path / "report.json"
    path.write_text('{"name":"missing report"}', encoding="utf-8")
    with pytest.raises(ValueError, match="report must be a JSON object"):
        module._load_report(path)


def test_dashboard_cli_writes_both_outputs(tmp_path: Path) -> None:
    module = load_module()
    report = tmp_path / "report.json"
    report.write_text(json.dumps(report_payload()), encoding="utf-8")
    html_output = tmp_path / "dashboard.html"
    svg_output = tmp_path / "dashboard.svg"
    assert (
        module.main(
            [
                "--input",
                str(report),
                "--output-html",
                str(html_output),
                "--output-svg",
                str(svg_output),
            ]
        )
        == 0
    )
    assert html_output.is_file()
    assert svg_output.is_file()


def test_process_ir_is_integrated_and_documented() -> None:
    workflows = (
        Path(".github/workflows/ci.yml"),
        Path(".github/workflows/windows-control-plane.yml"),
        Path(".github/workflows/licensed-aspen-certification.yml"),
    )
    test_markers = (
        "tests/test_process_ir.py",
        "tests/test_process_ir_edges.py",
        "tests/test_process_ir_dashboard.py",
    )
    for workflow in workflows:
        text = workflow.read_text(encoding="utf-8")
        for marker in test_markers:
            assert marker in text
        assert "scripts/validate_process_ir.py" in text
        assert "scripts/render_process_ir_dashboard.py" in text
        assert "process-ir-dashboard" in text

    for readme in (Path("README.md"), Path("README.en.md")):
        text = readme.read_text(encoding="utf-8")
        assert "aspenops.flowsheet/v1" in text
        assert "scripts/validate_process_ir.py" in text
        assert "process-ir-dashboard.html" in text
        assert "DWSIM" in text
        assert "IDAES" in text
        assert "no adapter" in text.casefold() or "未实现" in text

    assert Path("docs/process-intent-ir.md").is_file()
    assert Path("docs/external-agent-integration.md").is_file()
